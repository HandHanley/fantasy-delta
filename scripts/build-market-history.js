/**
 * DELTA — Market value history, one file per league format (9 Oct 2026).
 *
 * Feeds the Market Value card on player.html. DISPLAY ONLY: nothing scored reads
 * these files, and data/market-price-log.jsonl (12-SF only, used by the 2027
 * accuracy comparison) is left exactly as it is.
 *
 * Output: data/market-history/<teams>-<qb>.json, e.g. 12-sf.json
 *   { setting:"12|sf", dates:["2026-06-09", ...],
 *     players:{ "<FantasyCalc name>":[value|null per date] } }
 * Values only, no ranks: the file holds the whole board for every date, so a
 * player's overall rank on any day is recomputed from it on the page.
 * The page loads ONE file (the reader's format) and only when the card scrolls
 * into view.
 *
 * Usage:
 *   node scripts/build-market-history.js              nightly: fold today's
 *                                                     data/market-values.json in
 *   node scripts/build-market-history.js --backfill   rebuild from git history of
 *                                                     data/market-values.json
 *                                                     (needs a full clone; the
 *                                                     per-format grid starts 9 Jun 2026)
 */
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const SRC = 'data/market-values.json';
const OUT_DIR = path.join('data', 'market-history');
const fileFor = (setting) => path.join(OUT_DIR, setting.replace('|', '-') + '.json');

function load(setting) {
  try {
    const j = JSON.parse(fs.readFileSync(fileFor(setting), 'utf8'));
    if (j && Array.isArray(j.dates) && j.players) return j;
  } catch (e) {}
  return { setting, dates: [], players: {} };
}

/* Put one day's slice into a history: replace that date's column if it already
   exists (a re-run on the same day), otherwise append it in date order. */
function fold(hist, date, slice) {
  let i = hist.dates.indexOf(date);
  if (i < 0) {
    hist.dates.push(date);
    hist.dates.sort();
    i = hist.dates.indexOf(date);
    for (const n in hist.players) hist.players[n].splice(i, 0, null);
  }
  const len = hist.dates.length;
  for (const n in hist.players) hist.players[n][i] = null;
  for (const [name, v] of Object.entries(slice)) {
    if (!v || v.value == null) continue;
    if (!hist.players[name]) hist.players[name] = new Array(len).fill(null);
    hist.players[name][i] = Math.round(v.value);
  }
}

function save(hist) {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  // Drop anyone with no value on any date (can happen after a re-run replaces a day).
  for (const n in hist.players) if (!hist.players[n].some((v) => v != null)) delete hist.players[n];
  fs.writeFileSync(fileFor(hist.setting), JSON.stringify(hist));
}

function nightly() {
  let src;
  try { src = JSON.parse(fs.readFileSync(SRC, 'utf8')); }
  catch (e) { console.warn('[DELTA] market history: cannot read ' + SRC + ' — skipped'); return; }
  if (!src || !src.settings || !src.fetched) { console.warn('[DELTA] market history: no per-format grid — skipped'); return; }
  const date = String(src.fetched).slice(0, 10);
  for (const [setting, slice] of Object.entries(src.settings)) {
    const h = load(setting);
    fold(h, date, slice);
    save(h);
    console.log(`[DELTA] market history ${setting}: ${h.dates.length} days, ${Object.keys(h.players).length} players, ` +
                `${Math.round(fs.statSync(fileFor(setting)).size / 1024)}KB`);
  }
}

function backfill() {
  const shallow = execSync('git rev-parse --is-shallow-repository').toString().trim();
  if (shallow === 'true') { console.error('REFUSED — shallow clone; run `git fetch --unshallow` first.'); process.exit(2); }
  const lines = execSync(`git log --reverse --format=%H -- ${SRC}`).toString().trim().split('\n');
  const byDate = {};                      // date -> the LAST commit's grid for that fetched date
  for (const h of lines) {
    let j;
    try { j = JSON.parse(execSync(`git show ${h}:${SRC}`, { maxBuffer: 64 * 1024 * 1024 }).toString()); }
    catch (e) { continue; }
    if (!j || !j.settings || !j.fetched) continue;
    byDate[String(j.fetched).slice(0, 10)] = j.settings;
  }
  const dates = Object.keys(byDate).sort();
  if (!dates.length) { console.error('No per-format snapshots found.'); process.exit(1); }
  const hists = {};
  for (const d of dates) for (const [setting, slice] of Object.entries(byDate[d])) {
    if (!hists[setting]) hists[setting] = { setting, dates: [], players: {} };
    fold(hists[setting], d, slice);
  }
  for (const h of Object.values(hists)) {
    save(h);
    console.log(`[DELTA] backfill ${h.setting}: ${h.dates[0]} → ${h.dates[h.dates.length - 1]}, ${h.dates.length} days, ` +
                `${Object.keys(h.players).length} players, ${Math.round(fs.statSync(fileFor(h.setting)).size / 1024)}KB`);
  }
}

if (process.argv.includes('--backfill')) backfill(); else nightly();
