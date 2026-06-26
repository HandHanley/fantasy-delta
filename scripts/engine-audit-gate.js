/**
 * DELTA Engine Audit Gate — CI regression check
 * Run in GitHub Actions after data refresh: node scripts/engine-audit-gate.js
 *
 * Recomputes the scarcity-engine directional validation (the ?dev=1 Engine
 * Audit tab) headlessly and FAILS the workflow if the engine's direction
 * disagrees with the market in any setting, or if the validation is
 * incomplete. Mirrors renderScarcityAudit() in index.html exactly:
 *   dirOf(f): >1.02 → +1, <0.98 → -1, else 0  (0.02 dead band)
 *   agree: directions match, or either side is flat
 *   bad:   strictly opposite directions  ← the gate condition
 *
 * The engine (SCAR_STARTERS/SCAR_CURVE/curveVal/scarcity) is extracted from
 * delta-engine.js at run time so the gate always audits the SHIPPED logic — if
 * extraction fails because the code moved, the gate fails loudly instead of
 * silently testing a stale copy.
 *
 * Exit 0: 32/32 complete, zero opposite-direction flags.
 * Exit 1: any regression, sample data, or extraction failure.
 */

const fs = require('fs');
const path = require('path');

const EXPECTED_TOTAL = 32; // 8 settings × 4 positions

function fail(msg) {
  console.error('\n[GATE] ❌ FAIL: ' + msg);
  process.exit(1);
}

// ── 1. Extract the live scarcity engine from delta-engine.js ──
function extractEngine(src) {
  const startIdx = src.indexOf('const SCAR_STARTERS');
  if (startIdx === -1) fail('Could not find SCAR_STARTERS in delta-engine.js — engine moved or renamed.');
  const fnIdx = src.indexOf('function scarcity(', startIdx);
  if (fnIdx === -1) fail('Could not find function scarcity() after SCAR_STARTERS.');
  // brace-match to the end of function scarcity
  const braceStart = src.indexOf('{', fnIdx);
  let depth = 0, end = -1;
  for (let i = braceStart; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') { depth--; if (depth === 0) { end = i; break; } }
  }
  if (end === -1) fail('Brace matching failed extracting scarcity().');
  return src.slice(startIdx, end + 1);
}

const enginePath = path.join(process.cwd(), 'delta-engine.js');
if (!fs.existsSync(enginePath)) fail('delta-engine.js not found at ' + enginePath);
const engineSrc = extractEngine(fs.readFileSync(enginePath, 'utf8'));

let scarcity;
try {
  scarcity = new Function(engineSrc + '\nreturn scarcity;')();
  const probe = scarcity('QB', 12, 'sf');
  if (typeof probe !== 'number' || !isFinite(probe)) throw new Error('scarcity() returned ' + probe);
} catch (e) {
  fail('Extracted engine failed to evaluate: ' + e.message);
}

// ── 2. Load fresh validation data ──
const dataPath = path.join(process.cwd(), 'data', 'scarcity-validation.json');
if (!fs.existsSync(dataPath)) fail('data/scarcity-validation.json missing — run fetch-scarcity-validation.js first.');
const SCARV = JSON.parse(fs.readFileSync(dataPath, 'utf8'));
if (SCARV.sample) fail('Validation file is SAMPLE/synthetic data — gate requires real FantasyCalc values.');
if (!Array.isArray(SCARV.settings) || !SCARV.settings.length) fail('Validation file has no settings.');

// ── 3. Recompute agreement (identical to renderScarcityAudit) ──
const POS = ['QB', 'RB', 'WR', 'TE'];
const dirOf = (f, band = 0.02) => f > 1 + band ? 1 : f < 1 - band ? -1 : 0;

let agree = 0, total = 0, bad = 0;
const badRows = [], magRows = [];
const pad = (s, n) => String(s).padEnd(n);

console.log('[GATE] DELTA Engine Audit — scarcity directional validation');
console.log('[GATE] data generated: ' + (SCARV.generated || '?') + '\n');
console.log(pad('setting', 14) + pad('pos', 5) + pad('DELTA', 8) + pad('market', 8) + pad('diff', 7) + 'dir');

const rows = SCARV.settings.slice().sort((a, b) => a.qb === b.qb ? a.teams - b.teams : (a.qb === 'sf' ? -1 : 1));
for (const s of rows) {
  for (const pos of POS) {
    const cell = s.positions && s.positions[pos];
    if (!cell || cell.marketFactor == null) continue;
    const dF = scarcity(pos, s.teams, s.qb);
    const mF = cell.marketFactor;
    const dd = dirOf(dF), dm = dirOf(mF);
    const diffPct = ((mF / dF) - 1) * 100;
    total++;
    let mark;
    if (dd === dm)            { agree++; mark = Math.abs(diffPct) < 8 ? '✓' : '≈'; }
    else if (dd === 0 || dm === 0) { agree++; mark = '≈'; }
    else                      { bad++;   mark = '✗ OPPOSITE'; }
    const label = s.teams + '-' + (s.qb === 'sf' ? 'SF' : '1QB');
    const line = pad(label, 14) + pad(pos, 5) + pad(dF.toFixed(3), 8) + pad(mF.toFixed(3), 8)
               + pad((diffPct >= 0 ? '+' : '') + diffPct.toFixed(0) + '%', 7) + mark;
    console.log(line);
    if (mark.startsWith('✗')) badRows.push(label + ' ' + pos);
    else if (mark === '≈') magRows.push(label + ' ' + pos + ' (' + (diffPct >= 0 ? '+' : '') + diffPct.toFixed(0) + '%)');
  }
}

console.log('\n[GATE] ' + agree + '/' + total + ' settings agree directionally; '
            + bad + ' opposite-direction flag(s).');
if (magRows.length) console.log('[GATE] magnitude-divergence (informational): ' + magRows.join(', '));

// ── 4. Verdict ──
if (total < EXPECTED_TOTAL) fail('Incomplete validation: ' + total + '/' + EXPECTED_TOTAL
  + ' comparisons present. FantasyCalc data may be partial — investigate before trusting the engine.');
if (bad > 0) fail('Opposite-direction regression in: ' + badRows.join(', ')
  + '. The scarcity engine now disagrees with market direction — review SCAR_CURVE / recent changes.');

console.log('[GATE] ✅ PASS — ' + agree + '/' + total + ', zero opposite-direction flags.');
