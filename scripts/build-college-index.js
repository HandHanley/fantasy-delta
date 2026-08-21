#!/usr/bin/env node
/**
 * DELTA — BUILD COLLEGE INDEX
 *
 * Emits data/college-index.json: the college record for every player who is ALSO in
 * DELTA's NFL universe, across every season on disk, with dDOM and PPA percentiles
 * PRE-COMPUTED against each season's full pool.
 *
 * WHY THIS FILE EXISTS:
 *   The player page needs two things the raw season files can't give it cheaply.
 *   1. SIZE. The six season files are ~4.2 MB. A player drafted in 2026 could appear
 *      in five of them, so a College tab that loaded season files would pull megabytes
 *      on a phone. Restricted to the NFL universe it is ~0.7 MB in ONE file.
 *   2. PERCENTILES. A percentile only means anything against the full season pool
 *      (all 953 players in 2025), which the slim file by definition does not contain.
 *      So the rank is computed HERE, where the pool is present, and baked in.
 *
 * The percentile maths is copied from cfb-player.html so both pages rank identically.
 *
 * Run from the repo root, same as freeze-snapshot.js:
 *   node scripts/build-college-index.js
 *   node scripts/build-college-index.js --dry-run
 */
const fs = require('fs'), path = require('path'), vm = require('vm');

const OUT = 'data/college-index.json';
const DRY = process.argv.includes('--dry-run');
const MIN_UNIVERSE = 300;   // RAW should hold ~409; a parse that yields less is broken

// ── dDOM maths — identical to cfb-player.html ────────────────────────────────
const DDOM_SWING = 0.50;
const cfbMult = t => t == null ? 1.0
  : Math.max(1 - DDOM_SWING, Math.min(1 + DDOM_SWING, 1 + DDOM_SWING * (t - 0.5) * 2));
function cfbAdjVal(p) {
  const m = cfbMult(p.tpct);
  if (p.pos === 'QB') return p.anya == null ? null : p.anya * m;
  if (p.pos === 'RB') return p.rdom == null ? null : p.rdom * m;
  if (p.pos === 'WR' || p.pos === 'TE') return p.dom == null ? null : p.dom * m;
  return null;
}
function cfbQualifies(p) {
  if ((p.gms || 0) < 6) return false;
  if (p.pos === 'WR' || p.pos === 'TE') return (p.rec || 0) >= 20;
  if (p.pos === 'RB') return (p.car || 0) >= 60;
  if (p.pos === 'QB') return (p.att || 0) >= 120;
  return false;
}
// Percentile of v within an ascending peer list. Same form as cfbPct().
function pctOf(peers, v) {
  if (peers.length < 2 || v == null) return null;
  let below = 0; for (const x of peers) if (x < v) below++;
  return Math.round(100 * below / (peers.length - 1));
}
const PPA_KEY = { QB: 'ppaPass', RB: 'ppaRush', WR: 'ppa', TE: 'ppa' };

// ── name key — mirrors fetch-college.py's norm() ──────────────────────────────
function norm(s) {
  if (!s) return '';
  return String(s).normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase().replace(/[^a-z0-9]/g, '');
}
// Generational suffixes are carried inconsistently between the NFL and college feeds
// ("Marvin Harrison Jr." vs "Marvin Harrison"). Strict key first, this only as a
// fallback, and the run reports how many matched loosely so a bad join is visible.
function normLoose(s) {
  if (!s) return '';
  return String(s).normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase().replace(/\b(jr|sr|ii|iii|iv|v)\b/g, '').replace(/[^a-z0-9]/g, '');
}

// ── the NFL universe, read from the engine itself (no regex parsing) ──────────
function loadUniverse() {
  if (!fs.existsSync('delta-engine.js')) {
    console.error('ERROR: delta-engine.js not found. Run from the repo root.');
    process.exit(1);
  }
  const src = fs.readFileSync('delta-engine.js', 'utf8') +
    ';globalThis.__U__ = RAW.map(p => ({ n: p.n, pos: p.p }));';
  const sb = {
    console, setTimeout, Date, Math, JSON, Promise, URLSearchParams,
    location: { search: '' },
    fetch: async () => ({ ok: false, status: 404 }),
    localStorage: { getItem: () => null, setItem: () => {} },
    document: { getElementById: () => null, createElement: () => ({ style: {} }),
                body: { appendChild: () => {} }, querySelectorAll: () => [] },
  };
  sb.window = sb; sb.globalThis = sb;
  vm.createContext(sb); vm.runInContext(src, sb);
  return sb.__U__;
}

function seasonFiles() {
  return fs.readdirSync('data')
    .map(f => (f.match(/^college-players-(\d{4})\.json$/) || [])[1])
    .filter(Boolean).map(Number).sort();
}

// ── build ────────────────────────────────────────────────────────────────────
const universe = loadUniverse();
if (universe.length < MIN_UNIVERSE) {
  console.error(`ERROR: only ${universe.length} players read from RAW (expected >= ${MIN_UNIVERSE}).`);
  process.exit(1);
}
const want = new Set(universe.map(p => norm(p.n) + '|' + p.pos));
const wantLoose = new Set(universe.map(p => normLoose(p.n) + '|' + p.pos));
console.log('='.repeat(72));
console.log('DELTA — BUILD COLLEGE INDEX' + (DRY ? '   (DRY RUN)' : ''));
console.log('='.repeat(72));
console.log(`NFL universe: ${universe.length} players`);

const years = seasonFiles();
if (!years.length) { console.error('ERROR: no data/college-players-YYYY.json files found.'); process.exit(1); }
console.log(`college seasons on disk: ${years.join(', ')}`);

const out = {};           // playerName -> { season -> record }
let seasonRows = 0;
for (const y of years) {
  const pool = JSON.parse(fs.readFileSync(`data/college-players-${y}.json`, 'utf8')).players || [];

  // peer lists per position, built ONCE per season from the full pool
  const dPeers = {}, pPeers = {};
  for (const pos of ['QB', 'RB', 'WR', 'TE']) {
    const q = pool.filter(p => p.pos === pos && cfbQualifies(p));
    dPeers[pos] = q.map(cfbAdjVal).filter(v => v != null).sort((a, b) => a - b);
    const k = PPA_KEY[pos];
    pPeers[pos] = q.map(p => p[k]).filter(v => v != null).sort((a, b) => a - b);
  }

  let hit = 0, loose = 0;
  for (const p of pool) {
    const strict = want.has(norm(p.n) + '|' + p.pos);
    if (!strict && !wantLoose.has(normLoose(p.n) + '|' + p.pos)) continue;
    if (!strict) loose++;
    hit++; seasonRows++;
    const pos = p.pos, q = cfbQualifies(p);
    const rawD = pos === 'QB' ? p.anya : pos === 'RB' ? p.rdom : p.dom;
    const ppaRaw = p[PPA_KEY[pos]];
    const rec = Object.assign({}, p);
    rec._season = y;
    rec._qual = q;
    rec._ddomPct = q ? pctOf(dPeers[pos], cfbAdjVal(p)) : null;
    rec._ddomRaw = rawD == null ? null : (pos === 'QB' ? Math.round(rawD * 10) / 10 : Math.round(rawD * 1000) / 10);
    rec._ddomPeers = dPeers[pos].length;
    rec._ppaPct = q ? pctOf(pPeers[pos], ppaRaw) : null;
    rec._ppaRaw = ppaRaw == null ? null : ppaRaw;
    rec._ppaPeers = pPeers[pos].length;
    (out[p.n] = out[p.n] || {})[y] = rec;
  }
  console.log(`  ${y}: pool ${String(pool.length).padStart(4)} · in NFL universe ${String(hit).padStart(3)}` +
              (loose ? ` (${loose} via suffix fallback)` : '') +
              ` · qualifying peers QB/RB/WR/TE ${['QB','RB','WR','TE'].map(x=>dPeers[x].length).join('/')}`);
}

const players = Object.keys(out).length;
const withPpa = Object.values(out).reduce((a, seasons) =>
  a + Object.values(seasons).filter(r => r._ppaPct != null).length, 0);
console.log(`\nplayers covered: ${players} · player-seasons: ${seasonRows} · with a PPA percentile: ${withPpa}`);

const payload = {
  generated: new Date().toISOString(),
  seasons: years,
  note: ('Slim college index for the NFL player page. Contains only players who are also in ' +
         "DELTA's NFL universe. _ddomPct and _ppaPct are percentiles computed against the FULL " +
         'season pool at build time, because the pool is not present in this file. Tracking data ' +
         'only — nothing here feeds the DELTA Score, the projection or the buy/sell call.'),
  players: out,
};
const json = JSON.stringify(payload);
console.log(`size: ${(json.length / 1e6).toFixed(2)} MB`);

if (DRY) { console.log(`\nDRY RUN — ${OUT} not written.`); }
else {
  fs.writeFileSync(OUT + '.tmp', json); fs.renameSync(OUT + '.tmp', OUT);
  console.log(`\nWROTE ${OUT}`);
}
console.log('='.repeat(72));
