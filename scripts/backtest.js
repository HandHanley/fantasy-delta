/**
 * DELTA Projection Backtest — scripts/backtest.js
 * Run from the repo root:  node scripts/backtest.js [--season 2025]
 *
 * Out-of-sample test of the projection CORE: for the target season Y, project
 * every player's PPG using ONLY seasons before Y (the engine's recency
 * weighting, renormalized over available prior seasons, with per-season weight
 * shrunk by sample size), then compare against what actually happened in Y.
 * Data: data/backtest-data.json (8 seasons, full league, bust-inclusive).
 *
 * NOTE: rebuilt 2026-06-30 after the original June-4 harness was lost locally
 * (never committed). This version tests the projection core only — recency
 * blend + sample shrinkage — NOT the situational multipliers (system, OC,
 * ripples, QB quality), which cannot be reconstructed as-of a past date.
 * Metrics are therefore re-baselined; do not compare directly to the
 * historical 1.16 MAE figure, which included the full multiplier stack.
 *
 * Scoring: half-PPR, TE premium +1.0/rec (the model's half_tep basis).
 * Eligibility: >=8 prior-season games total to project; >=6 actual games in Y
 * to grade (small denominators grade noise, not skill).
 */

const fs = require('fs');
const path = require('path');

const TARGET = (() => {
  const i = process.argv.indexOf('--season');
  return i > -1 ? parseInt(process.argv[i + 1], 10) : null;
})();

const D = JSON.parse(fs.readFileSync(path.join(process.cwd(), 'data/backtest-data.json'), 'utf8'));
const seasonsAll = new Set();
for (const p of Object.values(D.players)) for (const y of Object.keys(p.seasons)) seasonsAll.add(+y);
const LATEST = Math.max(...seasonsAll);
const Y = TARGET || LATEST;

// half_tep PPG from a season line
function ppg(s, pos) {
  if (!s || !s.games) return null;
  const recPt = pos === 'TE' ? 1.0 : 0.5;
  const fp = (s.rush_yds || 0) * 0.1 + (s.rush_td || 0) * 6 +
             (s.rec_yds || 0) * 0.1 + (s.rec_td || 0) * 6 + (s.rec || 0) * recPt +
             (s.pass_yds || 0) * 0.04 + (s.pass_td || 0) * 4 + (s.pass_int || 0) * -2;
  return fp / s.games;
}

// Engine recency weights (60/30/10 over Y-1, Y-2, Y-3), each shrunk by sample
// (min(1, games/8) — mirrors the engine's minimum-sample principle), then
// renormalized over whatever prior seasons exist.
const BASE_W = [0.6, 0.3, 0.1];
function project(p, pos) {
  let num = 0, den = 0, priorGames = 0;
  for (let k = 1; k <= 3; k++) {
    const s = p.seasons[String(Y - k)];
    const v = ppg(s, pos);
    if (v === null) continue;
    const w = BASE_W[k - 1] * Math.min(1, (s.games || 0) / 8);
    num += w * v; den += w; priorGames += s.games || 0;
  }
  if (den === 0 || priorGames < 8) return null;
  return num / den;
}

const rows = [];
for (const [name, p] of Object.entries(D.players)) {
  if (!['QB', 'RB', 'WR', 'TE'].includes(p.pos)) continue;
  const act = p.seasons[String(Y)];
  if (!act || (act.games || 0) < 6) continue;
  const proj = project(p, p.pos);
  if (proj === null) continue;
  const actual = ppg(act, p.pos);
  rows.push({ name, pos: p.pos, proj, actual, err: proj - actual });
}

if (!rows.length) { console.error(`No gradable players for season ${Y}.`); process.exit(1); }

function stats(rs) {
  const n = rs.length;
  const mae = rs.reduce((s, r) => s + Math.abs(r.err), 0) / n;
  const bias = rs.reduce((s, r) => s + r.err, 0) / n;
  const within2 = rs.filter(r => Math.abs(r.err) <= 2).length / n;
  const within3 = rs.filter(r => Math.abs(r.err) <= 3).length / n;
  return { n, mae, bias, within2, within3 };
}

console.log(`DELTA projection-core backtest — target season ${Y} (projected from ${Y - 3}–${Y - 1} only)`);
console.log(`Gradable players: ${rows.length} (>=8 prior games, >=6 actual games)\n`);
console.log(`${'pos'.padEnd(6)}${'N'.padStart(5)}${'MAE'.padStart(8)}${'bias'.padStart(8)}${'±2pts'.padStart(8)}${'±3pts'.padStart(8)}`);
const all = stats(rows);
for (const pos of ['QB', 'RB', 'WR', 'TE']) {
  const s = stats(rows.filter(r => r.pos === pos));
  console.log(`${pos.padEnd(6)}${String(s.n).padStart(5)}${s.mae.toFixed(2).padStart(8)}${(s.bias >= 0 ? '+' : '') + s.bias.toFixed(2).padStart(7)}${(s.within2 * 100).toFixed(0).padStart(7)}%${(s.within3 * 100).toFixed(0).padStart(7)}%`);
}
console.log('─'.repeat(43));
console.log(`${'ALL'.padEnd(6)}${String(all.n).padStart(5)}${all.mae.toFixed(2).padStart(8)}${(all.bias >= 0 ? '+' : '') + all.bias.toFixed(2).padStart(7)}${(all.within2 * 100).toFixed(0).padStart(7)}%${(all.within3 * 100).toFixed(0).padStart(7)}%`);

console.log('\nLargest misses (model too HIGH):');
for (const r of [...rows].sort((a, b) => b.err - a.err).slice(0, 5))
  console.log(`  ${r.name} (${r.pos}): proj ${r.proj.toFixed(1)}, actual ${r.actual.toFixed(1)} (+${r.err.toFixed(1)})`);
console.log('Largest misses (model too LOW):');
for (const r of [...rows].sort((a, b) => a.err - b.err).slice(0, 5))
  console.log(`  ${r.name} (${r.pos}): proj ${r.proj.toFixed(1)}, actual ${r.actual.toFixed(1)} (${r.err.toFixed(1)})`);
console.log('\nRun with --season <year> to backtest a different target (e.g. --season 2024).');
