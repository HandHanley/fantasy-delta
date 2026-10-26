#!/usr/bin/env node
/**
 * DELTA — College board files for the published site (25 Oct 2026, legal compliance plan step 9).
 *
 * WHY: data/college-players*.json are CollegeFootballData (CFBD) season files with every game for
 * ~1,000 players a season. CFBD allows commercial use, but its terms bar publishing its data "as a
 * standalone dataset or bulk download" or running a "public database mirror". DELTA's own analysis
 * is fine. So the published site no longer carries those files. The deploy runs this script, which
 * writes a trimmed copy of each season for the pages:
 *
 *   data/college-board.json        from college-players.json (the season the app opens on)
 *   data/college-board-YYYY.json   from college-players-YYYY.json
 *
 * Each player keeps his season line and DELTA's measures, and loses the game-by-game rows (`g`).
 * The one thing the lists drew from those rows, the "last 3 games vs the 3 before" trend
 * (cfbRecentSplit in index.html), is worked out here as `rs3: [recent, prior]`, the same sums the
 * page used to make. Game-by-game rows now come only from each player's own card
 * (data/cfb-cards, scripts/build-cfb-cards.js).
 *
 * The repo copies are untouched: the nightly scripts and studies keep reading them.
 *
 *   node scripts/build-college-board.js            write next to the source files (data/)
 *   node scripts/build-college-board.js <outdir>   write into another folder
 */
'use strict';
const fs = require('fs'), path = require('path');

const DATA = path.resolve(__dirname, '..', 'data');
const OUT = path.resolve(process.argv[2] || DATA);
const K = 3;

function fail(m) { console.error('[COLLEGE BOARD] FAIL: ' + m); process.exit(1); }

// MUST MATCH cfbRecentSplit() in index.html: last K games vs the K before, sorted by week, on
// scrimmage yards (passing yards for QBs); null when there are fewer than 2K games.
function recentSplit(p) {
  const g = (p.g || []).slice().sort((a, b) => (a.w || 0) - (b.w || 0));
  if (g.length < K * 2) return null;
  const val = (r) => (p.pos === 'QB' ? (+r.py || 0) : (+r.rey || 0) + (+r.ry || 0));
  const recent = g.slice(-K).reduce((s, r) => s + val(r), 0) / K;
  const prior = g.slice(-K * 2, -K).reduce((s, r) => s + val(r), 0) / K;
  return [recent, prior];
}

const files = fs.readdirSync(DATA).filter((f) => /^college-players(-\d{4})?\.json$/.test(f)).sort();
if (!files.some((f) => f === 'college-players.json')) fail('data/college-players.json not found.');
fs.mkdirSync(OUT, { recursive: true });
let total = 0;
for (const f of files) {
  const src = JSON.parse(fs.readFileSync(path.join(DATA, f), 'utf8'));
  if (!src || !Array.isArray(src.players) || !src.players.length) fail(f + ' has no players.');
  const players = src.players.map((p) => {
    const out = {};
    for (const k of Object.keys(p)) if (k !== 'g') out[k] = p[k];
    const rs = recentSplit(p);
    if (rs) out.rs3 = rs;
    return out;
  });
  const board = Object.assign({}, src, {
    note: 'DELTA college board: each player\'s season line and DELTA\'s own measures; no game-by-game rows '
      + '(those are on each player\'s card). Built from CollegeFootballData.com data by scripts/build-college-board.js.',
    players,
  });
  const name = f.replace('college-players', 'college-board');
  fs.writeFileSync(path.join(OUT, name), JSON.stringify(board));
  total += players.length;
  console.log(`[COLLEGE BOARD] ${name}: ${players.length} players`);
}
console.log(`[COLLEGE BOARD] ${files.length} files, ${total} player lines, written to ${OUT}`);
