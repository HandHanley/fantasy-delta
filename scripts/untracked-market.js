/**
 * DELTA — Market players DELTA does not track (9 Oct 2026).
 *
 * Writes data/untracked-market.json: every QB/RB/WR/TE FantasyCalc prices in the
 * default 12-team superflex slice who matches no player in DELTA's RAW universe,
 * by the same three-step match the engine uses (exact name, FC_ALIASES, fcNorm).
 * Shown on the ?dev=1 Engine Audit panel so the owner can decide whether to add
 * anyone. Adding players stays a human call (rankings shift); this only lists them.
 * DISPLAY ONLY: nothing scored reads this file.
 *
 *   node scripts/untracked-market.js
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');
const MV = path.join(ROOT, 'data', 'market-values.json');
const OUT = path.join(ROOT, 'data', 'untracked-market.json');
const SKILL = new Set(['QB', 'RB', 'WR', 'TE']);
const TOP = 60;

function engine() {
  const src = fs.readFileSync(path.join(ROOT, 'delta-engine.js'), 'utf8') +
    '\n;globalThis.__U__={ RAW, FC_ALIASES:(typeof FC_ALIASES!=="undefined"?FC_ALIASES:{}), fcNorm };';
  const sb = {
    console: { log() {}, warn() {}, error() {} }, setTimeout, Date, Math, JSON, Promise, URLSearchParams,
    location: { search: '' }, fetch: async () => ({ ok: false, status: 404 }),
    localStorage: { getItem: () => null, setItem() {} },
    document: { getElementById: () => null, createElement: () => ({ style: {} }), body: { appendChild() {} }, querySelectorAll: () => [] },
  };
  sb.window = sb; sb.globalThis = sb; vm.createContext(sb); vm.runInContext(src, sb);
  return sb.__U__;
}

function main() {
  let mv;
  try { mv = JSON.parse(fs.readFileSync(MV, 'utf8')); }
  catch (e) { console.warn('[DELTA] untracked: cannot read market-values.json — skipped'); return; }
  const key = mv.default || '12|sf';
  const slice = mv.settings && mv.settings[key];
  if (!slice) { console.warn('[DELTA] untracked: no ' + key + ' slice — skipped'); return; }

  const E = engine();
  const exact = new Set(), norm = new Set();
  for (const p of E.RAW) {
    if (!p || !p.n) continue;
    exact.add(p.n); norm.add(E.fcNorm(p.n));
    const al = E.FC_ALIASES[p.n];
    if (al) { exact.add(al); norm.add(E.fcNorm(al)); }
  }
  const list = [];
  for (const [name, v] of Object.entries(slice)) {
    if (!v || !SKILL.has(v.position)) continue;              // picks and other positions
    if (exact.has(name) || norm.has(E.fcNorm(name))) continue;
    list.push({ n: name, pos: v.position, team: v.team || null, value: v.value,
                rank: v.overallRank || null, trend30: v.trend30Day || 0 });
  }
  list.sort((a, b) => b.value - a.value);
  const out = { generated: new Date().toISOString(), setting: key, universe: E.RAW.length,
                count: list.length, players: list.slice(0, TOP),
                note: 'QB/RB/WR/TE that FantasyCalc prices but DELTA does not track (exact, alias, normalized name). Display only.' };
  fs.writeFileSync(OUT, JSON.stringify(out));
  console.log(`[DELTA] untracked market players: ${list.length} (top ${Math.min(TOP, list.length)} saved)`);
  for (const p of list.slice(0, 12))
    console.log(`  ${String(p.rank || '-').padStart(4)}  ${p.n} (${p.pos} ${p.team || 'FA'})  ${p.value}  30d ${p.trend30 >= 0 ? '+' : ''}${p.trend30}`);
}

main();
