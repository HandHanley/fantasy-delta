/**
 * DELTA Scarcity-Engine Validation — Fetch Script
 * ------------------------------------------------------------------
 * PURPOSE (read this before touching anything):
 *   This script does NOT feed FantasyCalc into any DELTA score or ranking.
 *   It builds an EXTERNAL YARDSTICK only. The app reads this JSON and compares
 *   DELTA's own scarcity() factor against the market's observed behavior. FC is
 *   a measuring stick here, never an ingredient — this is the "interpret, not
 *   import" use. If FantasyCalc vanished, every DELTA score/ranking is unchanged;
 *   only this diagnostic panel would go dark.
 *
 * WHAT IT COMPUTES (apples-to-apples with the engine):
 *   DELTA's scarcity(pos,teams,qb) = gap(setting) / gap(12SF),
 *     where gap = 1 - curveVal(replRank), replRank = teams * starters[pos][qb],
 *     using a STATIC normalized talent curve (SCAR_CURVE in index.html).
 *   We mirror that EXACT formula but substitute the MARKET's observed
 *   value-by-rank curve for SCAR_CURVE:
 *     marketGap(setting) = 1 - V_repl/V_top   (V from FC, priced at that setting)
 *     marketFactor       = marketGap(setting) / marketGap(12SF anchor)
 *   So the ONLY thing differing between DELTA's factor and the market factor is
 *   the curve shape — which is precisely what we're validating. Same VOR basis,
 *   same 12-team-SF anchor (= 1.00), judged by DIRECTION not curve-fit.
 *
 *   NOTE: this script bakes ONLY the market side. It deliberately does NOT
 *   reimplement scarcity() — the app computes DELTA's factor live from the
 *   single source of truth, so the two can never silently drift.
 *
 * USAGE:  node scripts/fetch-scarcity-validation.js
 *         (run alongside fetch-market-values.js; same nightly Action is fine)
 *
 * Player stats / market values are handled by their own scripts.
 */

const https = require('https');
const fs    = require('fs');
const path  = require('path');

// MUST MATCH SCAR_STARTERS in index.html. If you change one, change both.
// (Different files, so unavoidable duplication — flagged on purpose.)
const STARTERS = { QB: { '1qb': 1.0, 'sf': 1.8 }, RB: 2.4, WR: 3.0, TE: 1.1 };
const POSITIONS = ['QB', 'RB', 'WR', 'TE'];

// Settings grid. ppr held CONSTANT at 1 (matches fetch-market-values.js) so we
// isolate the teams x qb scarcity dimension — the only thing scarcity() reads.
const TEAMS   = [8, 10, 12, 14];
const QBFMTS  = ['1qb', 'sf'];          // sf -> numQbs=2, 1qb -> numQbs=1
const PPR     = 1;
const ANCHOR  = { teams: 12, qb: 'sf' }; // factor == 1.00 here by construction

const fcUrl = (teams, qb) =>
  `https://api.fantasycalc.com/values/current?isDynasty=true&numQbs=${qb === 'sf' ? 2 : 1}` +
  `&numTeams=${teams}&ppr=${PPR}`;

function fetchUrl(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; DELTA/1.0)', 'Accept': 'application/json' }
    }, (res) => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => { try { resolve(JSON.parse(data)); } catch (e) { reject(new Error(`JSON parse failed: ${e.message}`)); } });
    });
    req.on('error', reject);
    req.setTimeout(30000, () => { req.destroy(); reject(new Error('Timeout')); });
  });
}

// starters for a position under a given qb format
const startersOf = (pos, qb) => (pos === 'QB' ? STARTERS.QB[qb] : STARTERS[pos]);

// 1-indexed, linearly-interpolated value at a (possibly fractional) rank
function valueAtRank(sortedVals, rank) {
  if (!sortedVals.length) return { v: 0, lowConf: true };
  if (rank <= 1) return { v: sortedVals[0], lowConf: false };
  if (rank >= sortedVals.length) return { v: sortedVals[sortedVals.length - 1], lowConf: true }; // clamped: too few players
  const lo = Math.floor(rank), hi = Math.ceil(rank), frac = rank - lo;
  const vLo = sortedVals[lo - 1], vHi = sortedVals[hi - 1];
  return { v: vLo + frac * (vHi - vLo), lowConf: false };
}

async function gapsForSetting(teams, qb) {
  const data = await fetchUrl(fcUrl(teams, qb));
  if (!Array.isArray(data) || !data.length) throw new Error(`Bad FC response @ ${teams}/${qb}`);

  // group player values by position (exclude draft picks)
  const byPos = { QB: [], RB: [], WR: [], TE: [] };
  for (const item of data) {
    const name = item?.player?.name;
    const pos  = item?.player?.position;
    const val  = item?.value;
    if (!name || val == null || !byPos[pos]) continue;
    if (name.includes('Round Pick')) continue;
    byPos[pos].push(val);
  }

  const out = {};
  for (const pos of POSITIONS) {
    const vals = byPos[pos].slice().sort((a, b) => b - a);
    const replRank = teams * startersOf(pos, qb);
    const vTop = vals.length ? vals[0] : 0;
    const { v: vRepl, lowConf } = valueAtRank(vals, replRank);
    const gap = vTop > 0 ? 1 - vRepl / vTop : 0;
    out[pos] = {
      replRank: +replRank.toFixed(2),
      vTop: Math.round(vTop),
      vRepl: Math.round(vRepl),
      gap: +gap.toFixed(4),
      poolSize: vals.length,
      lowConf,                 // replacement rank beyond FC's valued pool
    };
  }
  return out;
}

async function main() {
  console.log(`[DELTA] Scarcity validation — fetching FC grid at ${new Date().toISOString()}`);

  // 1) raw gaps for every setting
  const grid = []; // { teams, qb, gaps:{pos:{...}} }
  for (const qb of QBFMTS) {
    for (const teams of TEAMS) {
      const gaps = await gapsForSetting(teams, qb);
      grid.push({ teams, qb, gaps });
      console.log(`  fetched ${teams}-team ${qb}`);
    }
  }

  // 2) anchor gap per position (12-team SF) → normalize into a market factor
  const anchor = grid.find(g => g.teams === ANCHOR.teams && g.qb === ANCHOR.qb);
  if (!anchor) throw new Error('Anchor setting (12SF) missing from grid');
  const anchorGap = {};
  for (const pos of POSITIONS) anchorGap[pos] = anchor.gaps[pos].gap;

  const settings = grid.map(({ teams, qb, gaps }) => {
    const positions = {};
    for (const pos of POSITIONS) {
      const g = gaps[pos];
      const denom = anchorGap[pos];
      positions[pos] = {
        replRank:     g.replRank,
        vTop:         g.vTop,
        vRepl:        g.vRepl,
        gap:          g.gap,
        marketFactor: denom > 0 ? +(g.gap / denom).toFixed(3) : null,
        poolSize:     g.poolSize,
        lowConf:      g.lowConf,
      };
    }
    return { teams, qb, positions };
  });

  const output = {
    generated: new Date().toISOString(),
    generator: 'scripts/fetch-scarcity-validation.js',
    sample: false,
    isDynasty: true,
    ppr: PPR,
    anchor: ANCHOR,
    starters: STARTERS,
    note: 'External yardstick only. FantasyCalc value-by-rank vs DELTA SCAR_CURVE, ' +
          'same VOR formula and 12SF anchor. FC never enters any DELTA score or ranking.',
    settings,
  };

  const outDir = path.join(process.cwd(), 'data');
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(path.join(outDir, 'scarcity-validation.json'), JSON.stringify(output, null, 2));
  console.log(`[DELTA] scarcity-validation.json written — ${settings.length} settings`);

  // spot check: QB should crater in 1qb (marketFactor < 1)
  const q12_1qb = settings.find(s => s.teams === 12 && s.qb === '1qb');
  if (q12_1qb) console.log(`  spot check — QB factor @12-team 1QB (expect <1): ${q12_1qb.positions.QB.marketFactor}`);
}

main().catch(err => { console.error('[DELTA] Fatal error:', err.message); process.exit(1); });
