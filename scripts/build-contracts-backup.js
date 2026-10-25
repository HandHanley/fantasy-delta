#!/usr/bin/env node
/**
 * DELTA — Contracts Backup (25 Oct 2026, owner: "a copy of this table ... so that if the actual
 * table ever fails, we can just use the static copy until fixed").
 *
 * data/delta-contracts.json is DELTA's own contracts table: one row per player, built from the
 * original news reports, each with its link. The engine reads it on every visit. This script
 * writes a built-in copy of it into delta-engine.js, between the two marker lines
 *     // <contracts-backup>   ...   // </contracts-backup>
 * The engine fills its contracts from that copy as it loads (so the first draw already matches
 * the table) and keeps using it if the table file fails to load.
 *
 * The copy carries only what the site reads: team, end year, kind, $M per year, $M total and the
 * fifth-year option status. The reports, links and notes stay in the table.
 *
 *   node scripts/build-contracts-backup.js           rewrite the copy from the table
 *   node scripts/build-contracts-backup.js --check   change nothing; exit 1 if the copy is out of date
 *                                                    (the nightly runs this as an alarm)
 *
 * After any change to the table: run this, commit both files together.
 */
'use strict';
const fs = require('fs'), path = require('path');

const ROOT = path.resolve(__dirname, '..');
const TABLE = path.join(ROOT, 'data', 'delta-contracts.json');
const ENGINE = path.join(ROOT, 'delta-engine.js');
const START = '// <contracts-backup>', END = '// </contracts-backup>';
const CHECK = process.argv.includes('--check');

function fail(msg) { console.error('[CONTRACTS BACKUP] FAIL: ' + msg); process.exit(1); }

const table = JSON.parse(fs.readFileSync(TABLE, 'utf8'));
const rows = table && table.players;
if (!rows || typeof rows !== 'object') fail('data/delta-contracts.json has no "players" map.');
const names = Object.keys(rows).sort();
if (names.length < 350) fail(`only ${names.length} rows in the table (expected ~409); refusing to write a short copy.`);

/* One line per player, fixed field order, so a diff of the engine shows exactly which rows moved. */
const num = (v) => (v == null ? 'null' : String(+v));
const str = (v) => (v == null ? 'null' : JSON.stringify(String(v)));
const lines = names.map((n) => {
  const r = rows[n];
  const opt = r.option && r.option.status ? `,option:${str(r.option.status)}` : '';
  return `  ${JSON.stringify(n)}:{team:${str(r.team)},end:${num(r.end)},kind:${str(r.kind)},aav:${num(r.aav)},total:${num(r.total)}${opt}},`;
});
const block = [
  START,
  '/* Built-in copy of data/delta-contracts.json, written by scripts/build-contracts-backup.js.',
  '   Do not edit by hand: change the table, then run the script. The nightly fails if they differ. */',
  `const DL_CONTRACTS_BACKUP_ASOF=${JSON.stringify(table.updated || null)};`,
  'const DL_CONTRACTS_BACKUP={',
  ...lines,
  '};',
  END,
].join('\n');

const src = fs.readFileSync(ENGINE, 'utf8');
const a = src.indexOf(START), b = src.indexOf(END);
if (a < 0 || b < 0 || b < a) fail('marker lines not found in delta-engine.js.');
if (src.indexOf(START, a + 1) >= 0 || src.indexOf(END, b + 1) >= 0) fail('marker lines appear more than once in delta-engine.js.');
const current = src.slice(a, b + END.length);

if (CHECK) {
  if (current === block) { console.log(`[CONTRACTS BACKUP] OK: built-in copy matches the table (${names.length} players).`); process.exit(0); }
  // Name the rows that differ, so the alarm says what to fix.
  const have = {};
  for (const ln of current.split('\n')) { const m = ln.match(/^\s+("(?:[^"\\]|\\.)*"):\{/); if (m) have[JSON.parse(m[1])] = ln.trim(); }
  const want = {};
  for (const ln of lines) { const m = ln.match(/^\s+("(?:[^"\\]|\\.)*"):\{/); want[JSON.parse(m[1])] = ln.trim(); }
  const diff = [...new Set([...Object.keys(have), ...Object.keys(want)])].filter((n) => have[n] !== want[n]).sort();
  console.error(`::error title=Contracts backup out of date::${diff.length} player(s) differ between data/delta-contracts.json and the copy in delta-engine.js: ${diff.slice(0, 20).join(', ')}${diff.length > 20 ? ' …' : ''}. Run node scripts/build-contracts-backup.js and commit both files.`);
  process.exit(1);
}

if (current === block) { console.log('[CONTRACTS BACKUP] already up to date; nothing written.'); process.exit(0); }
fs.writeFileSync(ENGINE, src.slice(0, a) + block + src.slice(b + END.length));
console.log(`[CONTRACTS BACKUP] wrote ${names.length} players into delta-engine.js.`);
