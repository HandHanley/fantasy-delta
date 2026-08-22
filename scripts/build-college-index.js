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
// Hand-maintained identity links for players the name+position join cannot reach —
// almost always a position change between college and the NFL. Unverified entries are
// ignored: a wrong link here silently attaches another human's career to a player card.
let OVERRIDES = {};
const OVR_PATH = 'data/college-overrides.json';
if (fs.existsSync(OVR_PATH)) {
  const raw = JSON.parse(fs.readFileSync(OVR_PATH, 'utf8'));
  for (const [k, v] of Object.entries(raw)) {
    if (k.startsWith('_')) continue;
    if (v && v.verified === true && v.cfbName && v.cfbPos) OVERRIDES[k] = v;
  }
}

const universe = loadUniverse();
if (universe.length < MIN_UNIVERSE) {
  console.error(`ERROR: only ${universe.length} players read from RAW (expected >= ${MIN_UNIVERSE}).`);
  process.exit(1);
}
// Map the join key back to the NFL SPELLING. The index MUST be keyed by the name
// player.html looks up (p.n from RAW), not by the college feed's spelling — the two
// disagree often enough to matter ("Devon Achane" vs "De'Von Achane", "Luther Burden"
// vs "Luther Burden III"). Keying by the college name silently orphaned 16 of 269
// players: the record was built correctly and the page could never find it.
const want = new Map(universe.map(p => [norm(p.n) + '|' + p.pos, p.n]));
const wantOverride = new Map(
  Object.entries(OVERRIDES).map(([nflName, o]) => [norm(o.cfbName) + '|' + o.cfbPos, nflName]));
const wantLoose = new Map(universe.map(p => [normLoose(p.n) + '|' + p.pos, p.n]));
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

  let hit = 0, loose = 0, ovr = 0;
  for (const p of pool) {
    const nflName = want.get(norm(p.n) + '|' + p.pos)
                 || wantLoose.get(normLoose(p.n) + '|' + p.pos)
                 || wantOverride.get(norm(p.n) + '|' + p.pos);
    if (!nflName) continue;
    if (wantOverride.has(norm(p.n) + '|' + p.pos)) ovr++;
    else if (!want.has(norm(p.n) + '|' + p.pos)) loose++;
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
    rec._cfbName = p.n;                      // keep the college spelling for reference
    (out[nflName] = out[nflName] || {})[y] = rec;
  }
  console.log(`  ${y}: pool ${String(pool.length).padStart(4)} · in NFL universe ${String(hit).padStart(3)}` +
              (loose ? ` (${loose} via suffix fallback)` : '') +
              (ovr ? ` (${ovr} via override)` : '') +
              ` · qualifying peers QB/RB/WR/TE ${['QB','RB','WR','TE'].map(x=>dPeers[x].length).join('/')}`);
}

// Guard: every emitted key must be reachable from player.html.
const nflNames = new Set(universe.map(p => p.n));
const orphans = Object.keys(out).filter(k => !nflNames.has(k));
if (orphans.length) {
  console.error(`ERROR: ${orphans.length} index key(s) do not match an NFL name and would be ` +
                `unreachable from the player page: ${orphans.slice(0, 10).join(', ')}`);
  process.exit(1);
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

const ovrCount = Object.keys(OVERRIDES).length;
if (fs.existsSync(OVR_PATH)) {
  const rawOvr = JSON.parse(fs.readFileSync(OVR_PATH, 'utf8'));
  const pending = Object.entries(rawOvr).filter(([k, v]) => !k.startsWith('_') && v && v.verified !== true);
  console.log(`overrides: ${ovrCount} active` + (pending.length
    ? ` · ${pending.length} awaiting verification (ignored): ${pending.map(([k]) => k).join(', ')}` : ''));
}

// Companion manifest: just the covered names. player.html loads THIS at boot (a few KB)
// to decide whether to show the College tab at all, and only fetches the full index when
// the tab is actually opened. Without it the page would have to pull ~0.8 MB on every
// player view just to learn whether a tab should exist.
const NAMES_OUT = 'data/college-index-names.json';
const namesPayload = JSON.stringify({
  generated: payload.generated, seasons: years,
  note: 'Names present in college-index.json. Used to decide College tab visibility without loading the full index.',
  names: Object.keys(out).sort(),
});
console.log(`manifest: ${Object.keys(out).length} names, ${(namesPayload.length / 1024).toFixed(0)} KB`);

if (DRY) { console.log(`\nDRY RUN — ${OUT} and ${NAMES_OUT} not written.`); }
else {
  fs.writeFileSync(OUT + '.tmp', json); fs.renameSync(OUT + '.tmp', OUT);
  fs.writeFileSync(NAMES_OUT + '.tmp', namesPayload); fs.renameSync(NAMES_OUT + '.tmp', NAMES_OUT);
  console.log(`\nWROTE ${OUT}`);
  console.log(`WROTE ${NAMES_OUT}`);
}
console.log('='.repeat(72));
