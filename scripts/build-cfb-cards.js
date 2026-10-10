/**
 * DELTA — College player cards, one small file per bucket of players (10 Oct 2026, B4).
 *
 * cfb-player.html used to download every college season file (2020-2026, ~1 MB
 * compressed, one after another) to draw ONE player. This script does that work once,
 * at build time, and writes only what each page actually reads:
 *
 *   data/cfb-cards/<bucket>.json   { generated, buckets, players: [card, ...] }
 *   card = { n, pos, id,
 *            season,          the season the page header shows (newest visible)
 *            seasons,         the browse list from college-players.json
 *            hist,            every season held (college-seasons.json), oldest first
 *            p,  dd,          his current-season record and dDOM result
 *            s: { <yr>: { rec, dd, mates } } }   one entry per season he appears in;
 *                             mates = the teammates the Team Construction table reads
 *
 * The bucket is a hash of the lower-cased name, so the page can find a player from
 * the ?name= in its URL with one small download. Cards are listed in the current
 * pool's order, so the page's "exact name first, then any case" lookup returns the
 * same player it always did.
 *
 * THE MATH IS NOT COPIED. The dDOM functions are read out of cfb-player.html itself
 * (between the "shared dDOM math" and "data loading" markers) and run here, so the
 * page and this file cannot drift. If the markers move, this script fails loudly.
 *
 * DISPLAY ONLY: nothing scored reads these files. If a card is missing or fails to
 * load, the page falls back to the old full download.
 *
 *   node scripts/build-cfb-cards.js
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');
const D = (f) => path.join(ROOT, 'data', f);
const OUT_DIR = D('cfb-cards');
const BUCKETS = 64;

// FNV-1a over the lower-cased name. The page carries the same function (cfbCardBucket).
function bucketOf(name) {
  const s = String(name).toLowerCase();
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193); }
  return (h >>> 0) % BUCKETS;
}

function pageMath() {
  const html = fs.readFileSync(path.join(ROOT, 'cfb-player.html'), 'utf8');
  const a = html.indexOf('// ── shared dDOM math');
  const b = html.indexOf('// ── data loading ──');
  if (a < 0 || b < 0 || b < a) throw new Error('dDOM math markers not found in cfb-player.html');
  const sb = {};
  vm.createContext(sb);
  vm.runInContext(html.slice(a, b) + '\n;globalThis.__M__={ cfbDDOM };', sb);
  if (typeof sb.__M__.cfbDDOM !== 'function') throw new Error('cfbDDOM not found');
  return sb.__M__;
}

const readJSON = (f) => JSON.parse(fs.readFileSync(f, 'utf8'));

function main() {
  const M = pageMath();
  let data = readJSON(D('college-players.json'));
  // The page's own rule: show the newest season in the browse list.
  const vis = (data.seasons || []).slice().sort((a, b) => b - a);
  const newest = vis[0];
  if (newest && data.season !== newest) {
    const f = D('college-players-' + newest + '.json');
    const s = fs.existsSync(f) ? (readJSON(f).players || []) : [];
    if (s.length) data = { players: s, seasons: data.seasons, season: newest };
  }
  const season = data.season, seasons = data.seasons || [data.season];
  let hist;
  try { hist = readJSON(D('college-seasons.json')).seasons.slice(); } catch (e) { hist = seasons.slice(); }
  if (!hist || !hist.length) hist = seasons.slice();
  hist.sort((a, b) => a - b);

  const pools = {};
  for (const yr of hist) {
    const f = D('college-players-' + yr + '.json');
    pools[yr] = fs.existsSync(f) ? (readJSON(f).players || []) : [];
  }
  pools[season] = data.players;           // the page does the same (SEASON_CACHE)

  const MATE_KEYS = ['n', 'pos', 'tm', 'cls', 'rec', 'rey', 'rsh'];
  const matesFor = (rec, pool) => pool
    .filter((x) => x.tm === rec.tm && x.pos !== 'QB' && (x.rec || 0) > 0)
    .sort((a, b) => (b.rsh || 0) - (a.rsh || 0)).slice(0, 6)
    .map((x) => { const o = {}; for (const k of MATE_KEYS) if (x[k] !== undefined) o[k] = x[k]; return o; });

  const buckets = Array.from({ length: BUCKETS }, () => []);
  for (const p of data.players) {
    const card = { n: p.n, pos: p.pos, id: p.id, season, seasons, hist, p, dd: M.cfbDDOM(p, data.players), s: {} };
    for (const yr of hist) {
      const players = pools[yr];
      const rec = players.find((x) => x.id === p.id) || players.find((x) => x.n === p.n && x.pos === p.pos);
      if (!rec) continue;
      card.s[yr] = { rec: rec === p ? 'p' : rec, dd: M.cfbDDOM(rec, players), mates: matesFor(rec, players) };
    }
    buckets[bucketOf(p.n)].push(card);
  }

  if (data.players.length < 200) { console.error('REFUSED: implausibly small current pool'); process.exit(1); }
  // Stamped with the SOURCE file's time, not now, so a nightly rebuild of unchanged
  // college data writes identical files and commits nothing.
  const generated = data.generated || readJSON(D('college-players.json')).generated || null;
  // Write everything to a side folder, then swap, so a crash can never leave a half set.
  const TMP = OUT_DIR + '.tmp';
  fs.rmSync(TMP, { recursive: true, force: true });
  fs.mkdirSync(TMP, { recursive: true });
  let total = 0, biggest = 0;
  buckets.forEach((cards, i) => {
    const body = JSON.stringify({ generated, buckets: BUCKETS, players: cards });
    fs.writeFileSync(path.join(TMP, i + '.json'), body);
    total += body.length; biggest = Math.max(biggest, body.length);
  });
  fs.rmSync(OUT_DIR, { recursive: true, force: true });
  fs.renameSync(TMP, OUT_DIR);
  console.log(`[DELTA] cfb cards: ${data.players.length} players, season ${season}, history ${hist.join(',')}, ` +
              `${BUCKETS} files, ${Math.round(total / 1024)} KB total, largest ${Math.round(biggest / 1024)} KB`);
}

if (require.main === module) main();
module.exports = { bucketOf, BUCKETS };
