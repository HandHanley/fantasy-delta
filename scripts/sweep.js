/**
 * DELTA Regression Sweep — scripts/sweep.js
 * Run from the repo root:  node scripts/sweep.js
 *
 * Loads the SHIPPED delta-engine.js headlessly (stubbed fetch/localStorage,
 * no browser), runs the real loaders against ./data/*, then asserts a battery
 * of invariants across all 8 league settings (8/10/12/14 × 1QB/SF) and all
 * scoring formats. Pure read-only: changes nothing, exits 1 on any failure.
 *
 * NOTE: rebuilt 2026-06-30 after the original was lost locally (never
 * committed). Assertion set re-derived from the locked design decisions in
 * DELTA-checklist.md; counts differ from the historical "119" but coverage is
 * a superset (ripple + staleness checks are new).
 *
 * What it protects (the post-freeze contract):
 *   1. Engine loads; full universe present; COMP mirrors RAW.
 *   2. Data wiring: market grid, ripples (RP≡RIPPLE from ripple.json), contracts.
 *   3. Every setting: all projections/model values finite, positive where priced.
 *   4. Scarcity curves monotonically non-increasing; scarcity() bounded.
 *   5. TE reception premium (+0.5 in TEP formats) intact in fmtRecPts/gamefp.
 *   6. 12-SF anchor stability: cycling settings never changes 12-SF values
 *      (state-leak guard — the class of bug behind the old MV_CENTER issue).
 *   7. Ripples actually move projections in the stated direction.
 *   8. Rookie override path yields finite positive projections.
 *   9. Scoring-format wiring: std vs full changes reception-driven players.
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = process.cwd();
let PASS = 0, FAIL = 0;
const failures = [];
function ok(cond, label) {
  if (cond) { PASS++; }
  else { FAIL++; failures.push(label); }
}
function section(t) { console.log('\n── ' + t); }

// ── headless sandbox ────────────────────────────────────────────
function makeFetch() {
  return async function fetchStub(url) {
    const clean = String(url).replace(/\?.*$/, '').replace(/^\.\//, '');
    const p = path.join(ROOT, clean);
    if (!fs.existsSync(p)) return { ok: false, status: 404, json: async () => { throw new Error('404 ' + clean); }, text: async () => { throw new Error('404 ' + clean); } };
    const body = fs.readFileSync(p, 'utf8');
    return { ok: true, status: 200, json: async () => JSON.parse(body), text: async () => body };
  };
}

async function loadEngine() {
  let src = fs.readFileSync(path.join(ROOT, 'delta-engine.js'), 'utf8');
  // vm top-level let/const don't attach to the sandbox object — append an
  // export shim inside the engine's own scope handing out live refs + setters.
  src += `
;globalThis.__E__ = {
  get RAW(){return RAW;}, get COMP(){return COMP;}, get ASSETS(){return ASSETS;},
  get RP(){return RP;}, get RIPPLE(){return RIPPLE;}, get MARKET_SETTINGS(){return MARKET_SETTINGS;},
  calcProj, applyMarketForSetting, scarcity, scarCurveVal, fmtRecPts, gamefp, getAdjProj, getScoringDelta, glOf,
  loadLiveMarketValues, loadPlayerStats, loadPlayerContracts, loadRipples,
  ensureStartData: (typeof ensureStartData==='function'?ensureStartData:null),
  set(teams,qb,fmt){ if(teams)leagueTeams=teams; if(qb)qbFmt=qb; if(fmt)scoringFmt=fmt; },
  get settings(){ return {teams:leagueTeams, qb:qbFmt, fmt:scoringFmt}; },
};`;
  const sandbox = {
    console, setTimeout, clearTimeout, Date, Math, JSON, Promise,
    URLSearchParams, location: { search: '', href: 'https://sweep.local/' },
    fetch: makeFetch(),
    localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
    document: { getElementById: () => null, createElement: () => ({ style: {} }), body: { appendChild: () => {} }, querySelectorAll: () => [] },
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(src, sandbox, { filename: 'delta-engine.js' });
  const E = sandbox.__E__;
  // boot exactly like the pages do
  await E.loadLiveMarketValues();
  await E.loadPlayerStats();
  await E.loadPlayerContracts();
  await E.loadRipples();
  if (E.ensureStartData) { try { await E.ensureStartData(); } catch (e) { /* optional */ } }
  return E;
}

function recompute(S) { S.applyMarketForSetting(); }

(async () => {
  console.log('DELTA regression sweep — engine + data from ' + ROOT);
  const S = await loadEngine();

  // 1. load & universe
  section('1. Engine load & universe');
  ok(Array.isArray(S.RAW) && S.RAW.length >= 380, `RAW universe >= 380 (got ${S.RAW && S.RAW.length})`);
  ok(Array.isArray(S.COMP) && S.COMP.length === S.RAW.length, `COMP mirrors RAW (${S.COMP && S.COMP.length} vs ${S.RAW && S.RAW.length})`);
  ok(Array.isArray(S.ASSETS) && S.ASSETS.length > S.RAW.length, 'ASSETS includes players + picks');

  // 2. data wiring
  section('2. Data wiring');
  const rippleFile = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/ripple.json'), 'utf8'));
  ok(Object.keys(S.RP).length === rippleFile.length, `RP built from ripple.json (${Object.keys(S.RP).length}/${rippleFile.length})`);
  ok(S.RIPPLE.length === rippleFile.length, `RIPPLE display array matches ripple.json (${S.RIPPLE.length})`);
  for (const r of rippleFile.slice(0, 5))
    ok(Math.abs(S.RP[r.n] - (1 + parseFloat(r.delta) / 100)) < 1e-9, `RP[${r.n}] = 1${r.delta}`);
  ok(S.MARKET_SETTINGS && Object.keys(S.MARKET_SETTINGS).length === 8, `market grid has 8 settings (${S.MARKET_SETTINGS && Object.keys(S.MARKET_SETTINGS).length})`);
  const staleCnt = S.RAW.filter(p => p && p.mktStale).length;
  ok(S.RAW.every(p => !p || typeof p.mktStale === 'boolean'), `mktStale tagged on all players (stale: ${staleCnt})`);

  // 3. per-setting battery
  section('3. Per-setting battery (8 settings)');
  for (const teams of [8, 10, 12, 14]) for (const qb of ['1qb', 'sf']) {
    S.set(teams, qb); recompute(S);
    let nan = 0, nonpos = 0;
    for (const c of S.COMP) {
      if (!isFinite(c.proj) || !isFinite(c.mv)) nan++;
      if ((c.k || 0) > 0 && !(c.mv > 0)) nonpos++;
    }
    ok(nan === 0, `${teams}-team ${qb}: no NaN proj/mv (${nan})`);
    ok(nonpos === 0, `${teams}-team ${qb}: mv>0 for all priced players (${nonpos})`);
    for (const pos of ['QB', 'RB', 'WR', 'TE']) {
      const f = S.scarcity(pos, teams, qb);
      ok(isFinite(f) && f > 0 && f <= 1.5, `${teams}-team ${qb} scarcity(${pos}) sane (${f && f.toFixed(3)})`);
    }
  }

  // 4. scarcity monotonicity
  section('4. Scarcity curve monotonicity');
  for (const pos of ['QB', 'RB', 'WR', 'TE']) {
    let mono = true, prev = Infinity;
    for (let r = 1; r <= 40; r++) { const v = S.scarCurveVal(pos, r); if (v > prev + 1e-9) mono = false; prev = v; }
    ok(mono, `SCAR_CURVE.${pos} non-increasing over ranks 1..40`);
  }

  // 5. TE premium
  section('5. TE reception premium');
  // fmtRecPts is a DELTA off the half_tep base (TE 1.0/rec, WR 0.5/rec).
  // Absolute per-rec points = base + delta; the +0.5 premium must hold in the
  // TEP formats and be absent in non-TEP formats — by design.
  const absRec = (pos, fmt) => (pos === 'TE' ? 1.0 : 0.5) + S.fmtRecPts(pos, fmt);
  for (const fmt of ['half_tep', 'full_tep'])
    ok(Math.abs((absRec('TE', fmt) - absRec('WR', fmt)) - 0.5) < 1e-9, `TE premium +0.5/rec present in ${fmt}`);
  for (const fmt of ['half', 'full', 'std'])
    ok(Math.abs(absRec('TE', fmt) - absRec('WR', fmt)) < 1e-9, `TE premium absent in ${fmt} (by design)`);
  const gLine = { py:0, pt:0, pi:0, ry:0, rt:0, rec:6, rey:60, ret:0, fl:0, tp:0, rtd:0 };
  const dte = S.gamefp(gLine, 'TE', 'half_tep') - S.gamefp(gLine, 'WR', 'half_tep');
  ok(Math.abs(dte - 3.0) < 1e-6, `gamefp TE baseRec premium = rec×0.5 (${dte})`);

  // 6. 12-SF anchor stability (state-leak guard)
  section('6. 12-SF anchor stability across setting cycles');
  S.set(12,'sf'); recompute(S);
  const sample = S.COMP.filter(c => (c.k || 0) > 1000).slice(0, 25).map(c => ({ n: c.n, mv: c.mv, proj: c.proj }));
  for (const teams of [8, 14, 10]) for (const qb of ['1qb', 'sf']) { S.set(teams, qb); recompute(S); }
  S.set(12,'sf'); recompute(S);
  const byName = {}; S.COMP.forEach(c => byName[c.n] = c);
  let drift = 0;
  for (const s of sample) { const c = byName[s.n]; if (!c || Math.abs(c.mv - s.mv) > 1e-6 || Math.abs(c.proj - s.proj) > 1e-9) drift++; }
  ok(drift === 0, `12-SF values identical after cycling settings (${drift} drifted of ${sample.length})`);

  // 7. ripples move projections in the stated direction
  section('7. Ripple efficacy');
  let tested = 0;
  for (const r of rippleFile) {
    const raw = S.RAW.find(p => p && p.n === r.n && (p.g25 || 0) > 0);
    if (!raw || tested >= 5) continue;
    const withR = S.calcProj(raw).proj;
    const save = S.RP[r.n]; delete S.RP[r.n];
    const without = S.calcProj(raw).proj;
    S.RP[r.n] = save;
    const dir = r.d === 'up' ? withR > without : withR < without;
    ok(dir, `ripple ${r.n} ${r.delta} moves proj ${r.d} (${without.toFixed(2)} → ${withR.toFixed(2)})`);
    tested++;
  }
  ok(tested > 0, 'at least one ripple efficacy case ran');

  // 8. rookie override path
  section('8. Rookie override path');
  const rookies = S.RAW.filter(p => p && (p.g25 || 0) === 0 && (p.ppg25 || 0) > 0);
  ok(rookies.length > 0, `rookie-override players exist (${rookies.length})`);
  let rookieBad = 0;
  for (const rk of rookies) { const c = S.calcProj(rk); if (!isFinite(c.proj) || c.proj <= 0) rookieBad++; }
  ok(rookieBad === 0, `all rookie projections finite & positive (${rookieBad} bad)`);

  // 9. scoring-format wiring
  section('9. Scoring-format wiring');
  // Locked design: p.proj stays on the half_tep basis; per-format shift is
  // applied at display via getAdjProj. EXCEPTION (by design): Rule 4's
  // volatility penalty keys off format-aware start profiles (pos|fmt hit/elite
  // lines), so players with >=20 logged starts may drift slightly across
  // formats. Assert: (a) proj fully invariant across teams×QB at fixed fmt,
  // (b) fmt drift confined to logged-start players and small, (c) getAdjProj
  // carries the reception delta.
  S.set(12,'sf','half_tep'); recompute(S);
  const anchorProj = {}; S.COMP.forEach(c => anchorProj[c.n] = c.proj);
  S.set(8,'1qb'); recompute(S);
  let lgDrift = 0; S.COMP.forEach(c => { if (Math.abs((anchorProj[c.n] ?? c.proj) - c.proj) > 1e-9) lgDrift++; });
  ok(lgDrift === 0, `proj invariant across league settings at fixed fmt (${lgDrift} drifted)`);
  S.set(12,'sf','std'); recompute(S);
  const stdProj = {}, stdAdj = {};
  S.COMP.forEach(c => { stdProj[c.n] = c.proj; stdAdj[c.n] = S.getAdjProj(c); });
  S.set(null,null,'full'); recompute(S);
  let badDrift = 0, adjMoved = 0;
  for (const c of S.COMP) {
    const d = Math.abs((stdProj[c.n] ?? c.proj) - c.proj);
    if (d > 1e-9) {
      const gl = S.glOf(c);
      if (!(gl && gl.g >= 20) || d > Math.max(0.6, c.proj * 0.06)) badDrift++;   // outside Rule-4 bounds
    }
    if ((c.pos === 'WR' || c.pos === 'TE') && Math.abs((stdAdj[c.n] ?? 0) - S.getAdjProj(c)) > 0.5) adjMoved++;
  }
  ok(badDrift === 0, `fmt drift confined to Rule-4 (logged-start, small) players (${badDrift} out of bounds)`);
  ok(adjMoved > 50, `getAdjProj std→full moves reception-driven players (${adjMoved} moved)`);
  S.set(12,'sf','half_tep'); recompute(S);

  // ── summary ──
  console.log('\n════════════════════════════════════');
  console.log(`SWEEP: ${PASS} passed, ${FAIL} failed (${PASS + FAIL} assertions)`);
  if (FAIL) { console.log('\nFailures:'); failures.forEach(f => console.log('  ✗ ' + f)); process.exit(1); }
  console.log('All invariants hold.');
})().catch(e => { console.error('SWEEP CRASHED:', e.stack || e.message); process.exit(1); });
