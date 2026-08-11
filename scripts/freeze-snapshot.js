#!/usr/bin/env node
/**
 * DELTA — Accuracy-Ledger Freeze Snapshot (scripts/freeze-snapshot.js)
 *
 * Captures DELTA's opinions at freeze time so the 2026 season can grade them.
 * Runs headlessly against the live engine + data (same vm harness as sweep.js),
 * computes everything at the LEAGUE-INVARIANT anchor (12-team · Superflex ·
 * half-PPR TE-premium — the same basis the verdict engine uses), and writes
 * data/freeze-2026.json as the immutable public record.
 *
 * LOCKED DESIGN RULES:
 *  - mktStale players are EXCLUDED from the graded set (their market values
 *    are unreliable at snapshot time); they are listed by name for transparency.
 *  - The snapshot contains everything grading needs: proj (the PPG prediction),
 *    model value, market value, gap, verdict, positional ranks — plus the
 *    style factors so the record shows System Score v2 was in the frozen model.
 *  - Run AFTER a green data nightly, with the stale badge in its normal band.
 */
const fs = require('fs'), path = require('path'), vm = require('vm'), crypto = require('crypto');

/* ── RUN GUARD ───────────────────────────────────────────────────────────
   THIS BLOCK MUST STAY ABOVE THE ENGINE LOAD. The `readFileSync` below runs
   at module top-level and is not wrapped by the .catch() at the foot of the
   file, so a guard placed after it turns "wrong directory" into an ENOENT
   stack trace instead of a refusal. A guard that crashes is not a guard.

   The freeze is the immutable baseline for the entire accuracy ledger. The
   pre-flight guards further down protect against BAD data; this one protects
   against an UNINTENDED run — a stray `node scripts/freeze-snapshot.js`, a
   re-run to "check something", a copy-pasted command. Both failure modes end
   the same way: a plausible file replacing the real record, with no complaint.

   Locks:
     --confirm   required for ANY write
     --force     required IN ADDITION when data/freeze-2026.json already exists
     --dry-run   runs every check and prints the headline, writes nothing
   A missed freeze day is recoverable. A wrong freeze is not. */
const OUT_PATH = path.join('data', 'freeze-2026.json');
const ARGS     = process.argv.slice(2);
const KNOWN    = ['--confirm', '--force', '--dry-run', '--help', '-h'];

const USAGE = [
  'Usage: node scripts/freeze-snapshot.js --confirm [--force]',
  '       node scripts/freeze-snapshot.js --dry-run',
  '',
  '  --confirm   Required for any write. Writes ' + OUT_PATH + '.',
  '  --force     Required IN ADDITION to --confirm when ' + OUT_PATH,
  '              already exists. Overwrites the frozen record.',
  '  --dry-run   Run the engine, the pre-flight guards and the full snapshot,',
  '              print the headline, and write nothing. Needs no --confirm.',
  '  --help      This message.',
  '',
  'Run from the repository root, after a green data nightly.',
].join('\n');

const refuse = (why, hint) => {
  console.error('FREEZE REFUSED — ' + why);
  if (hint) console.error(hint);
  console.error('Nothing was written.\n');
  console.error(USAGE);
  process.exit(1);
};

if (ARGS.includes('--help') || ARGS.includes('-h')) { console.log(USAGE); process.exit(0); }

// Reject typos rather than ignoring them: a silently-dropped "--confrim" would
// leave the operator believing a flag was honoured that never parsed.
const unknown = ARGS.filter(a => !KNOWN.includes(a));
if (unknown.length) refuse('unrecognised argument: ' + unknown.join(' '));

const DRY_RUN = ARGS.includes('--dry-run');
const CONFIRM = ARGS.includes('--confirm');
const FORCE   = ARGS.includes('--force');

if (DRY_RUN && (CONFIRM || FORCE))
  refuse('--dry-run cannot be combined with --confirm or --force.',
         'Pick one: rehearse with --dry-run, or write with --confirm.');

// Both the engine and the output path are resolved relative to the working
// directory, so the wrong cwd must fail here with an explanation.
if (!fs.existsSync('delta-engine.js'))
  refuse('delta-engine.js not found in the current directory.',
         'Run from the repository root: node scripts/freeze-snapshot.js --confirm');

if (!DRY_RUN && !CONFIRM)
  refuse(FORCE ? '--force does not imply --confirm.' : 'this run would write the frozen accuracy-ledger record.',
         FORCE ? 'Overwriting takes BOTH flags: --confirm --force.'
               : 'Add --confirm to write it, or --dry-run to rehearse without writing.');

const EXISTING = fs.existsSync(OUT_PATH);
if (EXISTING && !DRY_RUN) {
  // Name what would be destroyed. "Are you sure?" is useless without the stakes.
  let was = '';
  try {
    const prev = JSON.parse(fs.readFileSync(OUT_PATH, 'utf8'));
    was = `Existing snapshot: frozen_at ${prev.frozen_at || '?'} · ${prev.count != null ? prev.count : '?'} players graded.`;
  } catch (e) { was = 'Existing snapshot is present but could not be parsed.'; }

  if (!FORCE) refuse(OUT_PATH + ' already exists.', was + '\nOverwriting the frozen record takes --confirm --force.');
  console.warn('⚠  OVERWRITING an existing freeze snapshot (--force).');
  console.warn('   ' + was.replace('\n', '\n   '));
}

console.log(DRY_RUN ? 'mode: DRY RUN — nothing will be written' : 'mode: WRITE — ' + OUT_PATH + (EXISTING ? ' (overwrite)' : ' (new)'));

const src = fs.readFileSync('delta-engine.js', 'utf8') + `
;globalThis.__H__={
  get COMP(){return COMP}, mvAsset, glOf, vTag, computeMvCenter,
  get PLAYER_STATS(){ return typeof PLAYER_STATS!=='undefined' ? PLAYER_STATS : null; },
  get MKT_LOADED(){ return typeof MKT!=='undefined' ? MKT : null; },
  // Provenance: the constants that decide every league adjustment. Frozen alongside
  // the calls so a 2027 grader can tell WHICH curve produced them.
  get SCAR_CURVE(){ return typeof SCAR_CURVE!=='undefined' ? SCAR_CURVE : null; },
  get SCAR_STARTERS(){ return typeof SCAR_STARTERS!=='undefined' ? SCAR_STARTERS : null; },
  scarcity: (p,t,q)=>scarcity(p,t,q),
  setCenter:(v)=>{ MV_CENTER=v; },
  styleFactors:(typeof styleFactors!=='undefined'?styleFactors:null),
  set:(t,q,fmt)=>{ if(t)leagueTeams=t; if(q)qbFmt=q; if(fmt)scoringFmt=fmt; },
  recompute:()=>{ applyMarketForSetting(); },
  boot:async()=>{ await loadLiveMarketValues(); await loadPlayerStats(); await loadPlayerContracts();
    await loadRipples(); await loadReads();
    if(typeof ensureStartData==='function'){ try{ await ensureStartData(); }catch(e){} }
    applyMarketForSetting(); }
};`;

const sb = { console, setTimeout, Date, Math, JSON, Promise, URLSearchParams, location:{search:''},
  fetch: async u => { const c = String(u).replace(/\?.*$/,'').replace(/^\.\//,'');
    const p = path.join(process.cwd(), c);
    if (!fs.existsSync(p)) return { ok:false, status:404 };
    const b = fs.readFileSync(p, 'utf8');
    return { ok:true, json:async()=>JSON.parse(b), text:async()=>b }; },
  localStorage:{ getItem:()=>null, setItem:()=>{} },
  document:{ getElementById:()=>null, createElement:()=>({style:{}}), body:{appendChild:()=>{}}, querySelectorAll:()=>[] } };
sb.window = sb; sb.globalThis = sb;
vm.createContext(sb); vm.runInContext(src, sb);

(async () => {
  const H = sb.__H__;
  await H.boot();
  H.set(12, 'sf', 'half_tep');   // the anchor basis — matches the verdict engine
  H.recompute();

  /* ── PRE-FLIGHT GUARDS ───────────────────────────────────────────────────
     Every loader in delta-engine.js SWALLOWS its errors by design — a missing
     data file leaves the site fully usable on baked fallbacks rather than blank.
     That is right for the app and dangerous here: without these checks a run with
     no market data still writes data/freeze-2026.json, still prints a success
     line, and still exits 0. The freeze is the immutable baseline for the whole
     accuracy ledger, so it must refuse rather than record something plausible.
     Abort loudly; a missed freeze day is recoverable, a wrong freeze is not. */
  const die = m => { console.error('FREEZE ABORTED — ' + m); console.error('Nothing was written. Fix the data and re-run.'); process.exit(1); };

  const compAll = H.COMP;
  if (!compAll || compAll.length < 300) die(`only ${compAll ? compAll.length : 0} players in COMP (expected ~400) — player data did not load`);

  const withMkt = compAll.filter(c => (c.kMkt || 0) > 0).length;
  if (withMkt < 300) die(`only ${withMkt}/${compAll.length} players have a market value — data/market-values.json is missing, empty or stale`);

  /* Check the PARSED artefact, not fields that also exist as baked fallbacks.
     An earlier version of this guard tested c.g25 / c.ppg25, which are present in
     the baked RAW table — so a run with data/player-stats.json deleted sailed
     straight through and wrote a snapshot with a completely different top-sell. */
  const ps = H.PLAYER_STATS;
  const psCount = ps ? Object.keys(ps).length : 0;
  if (psCount < 250) die(`PLAYER_STATS holds ${psCount} players (expected ~325) — data/player-stats.json did not load; scores would come from baked fallbacks`);

  /* computeMvCenter() returns exactly 1 both as "raw basis" and as its own
     out-of-range fallback (see the warn inside it). Either way, a real freeze
     should land near the population median, not on the fallback. */
  const centerProbe = H.computeMvCenter();
  if (!(centerProbe > 0.6 && centerProbe < 1.3) || centerProbe === 1)
    die(`model-value population center is ${centerProbe} — out of range or on the 1.0 fallback; market/stats data is suspect`);

  console.log(`pre-flight OK · ${compAll.length} players · ${withMkt} with market · ${psCount} stat lines · center ${centerProbe.toFixed(4)}`);

  const comp = compAll;

  /* CENTER FIRST — ORDER IS LOAD-BEARING.
     mvAsset() runs values through applyCenter(), which divides by MV_CENTER.
     computeMvCenter() must itself run while MV_CENTER===1 (raw basis), so the
     sequence is: compute -> set -> read everything else.

     This block previously sat AFTER the player loop, so mv, gap AND the positional
     ranks were all recorded on the raw basis (MV_CENTER===1) while verdicts were
     read on the centered basis (~0.84). Measured against live data:
       - 76 of 409 players had a recorded gap whose SIGN contradicted their
         recorded verdict (Jalen Hurts: gap -1.6% but verdict "strong buy")
       - 262 of 409 positional ranks moved once centered (max shift 11 places)
     Ranks move because applyCenter() is SELECTIVE, not a uniform divisor: values
     already at/above market are left alone and only below-market values are
     scaled, so the transform does not preserve order. */
  H.setCenter(H.computeMvCenter());

  // positional ranks at the anchor
  const byPosMv = {}, byPosMk = {};
  for (const pos of ['QB','RB','WR','TE']) {
    byPosMv[pos] = comp.filter(c => c.pos === pos).sort((a,b) => H.mvAsset(b) - H.mvAsset(a)).map(c => c.n);
    byPosMk[pos] = comp.filter(c => c.pos === pos).sort((a,b) => (b.kMkt||0) - (a.kMkt||0)).map(c => c.n);
  }

  const players = {}, excluded = [];
  for (const c of comp) {
    if (c.mktStale) { excluded.push(c.n); continue; }
    const mv = Math.round(H.mvAsset(c));
    const mkt = Math.round(c.kMkt || 0);
    if (!mkt) { excluded.push(c.n); continue; }
    const sty = H.styleFactors ? H.styleFactors(c.n, c.pos, c.t) : { total:0 };
    players[c.n] = {
      pos: c.pos, t: c.t,
      mv, mkt,
      gap: +((mv / mkt - 1) * 100).toFixed(1),
      verdict: null,   // filled after centering (below) — exactly as the live app computes it
      ds: c.dsScore ?? null,
      proj: c.proj != null ? +c.proj.toFixed(2) : null,
      rankMv: byPosMv[c.pos].indexOf(c.n) + 1,
      rankMk: byPosMk[c.pos].indexOf(c.n) + 1,
      style: sty.total ? +(sty.total * 100).toFixed(1) : 0,
    };
  }

  // verdicts: MV_CENTER was set above, so these are read on the SAME basis the
  // mv/gap figures were recorded on — and the same basis the live app uses.
  for (const c of comp) {
    if (!players[c.n]) continue;
    const vTxt = (H.vTag(c).match(/>([a-z ]+)</) || [, null])[1];
    players[c.n].verdict = vTxt;
  }

  // human-readable headline: the calls the season will be judged on
  const graded = Object.entries(players).filter(([,p]) => p.mkt >= 1500);
  const buys  = graded.filter(([,p]) => p.gap > 0).sort((a,b) => b[1].gap - a[1].gap).slice(0,15)
    .map(([n,p]) => `${n} (${p.pos}${p.rankMv} model vs ${p.pos}${p.rankMk} mkt, +${p.gap}%)`);
  const sells = graded.filter(([,p]) => p.gap < 0).sort((a,b) => a[1].gap - b[1].gap).slice(0,15)
    .map(([n,p]) => `${n} (${p.pos}${p.rankMv} model vs ${p.pos}${p.rankMk} mkt, ${p.gap}%)`);

  /* ── PROVENANCE ──────────────────────────────────────────────────────────
     The ledger is graded in Feb 2027 and again before Week 1 2027. By then the
     engine will have moved on. Without this block the frozen calls cannot be
     attributed to a specific engine or scarcity curve, and "was this call made
     before or after the scarcity fix?" becomes unanswerable.

     Input files are FINGERPRINTED, not copied. market-values.json alone is 425 KB
     across 8 formats x 475 players; duplicating it here would multiply the freeze
     file for data already committed in the repo at the same SHA. A hash proves
     which bytes were used and stays a few dozen characters. */
  const sha = f => { try { return crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex').slice(0,16); }
                     catch(e){ return null; } };
  // Read the market file's own fetched stamp straight off disk — it records when
  // FantasyCalc was polled, which is not the same as when this snapshot ran.
  let mktFetched = null;
  try { mktFetched = JSON.parse(fs.readFileSync('data/market-values.json','utf8')).fetched || null; } catch(e) {}

  // Resolve every scarcity cell the engine can produce, so the curve is recorded
  // both as its source constants AND as the values actually applied.
  const scarTable = {};
  for (const t of [8,10,12,14]) for (const q of ['1qb','sf']) {
    const cell = {};
    for (const pos of ['QB','RB','WR','TE']) cell[pos] = +H.scarcity(pos,t,q).toFixed(4);
    scarTable[`${t}|${q}`] = cell;
  }

  const provenance = {
    engine_sha:       sha('delta-engine.js'),
    freeze_script_sha: sha('scripts/freeze-snapshot.js'),
    node_version:     process.version,
    inputs: {
      'market-values.json':    { sha: sha('data/market-values.json'),    fetched: mktFetched },
      'player-stats.json':     { sha: sha('data/player-stats.json') },
      'player-contracts.json': { sha: sha('data/player-contracts.json') },
      'injury-overrides.json': { sha: sha('data/injury-overrides.json') },
      'game-logs.json':        { sha: sha('data/game-logs.json') },
    },
    scarcity_curve:    H.SCAR_CURVE,
    scarcity_starters: H.SCAR_STARTERS,
    scarcity_resolved: scarTable,
    mv_center:         +centerProbe.toFixed(6),
    note: 'Fingerprints, not copies — the input files live in the repo at this commit. '
        + 'scarcity_resolved is the applied 32-cell table; scarcity_curve is its source.',
  };

  const out = {
    frozen_at: new Date().toISOString(),
    basis: { teams:12, superflex:true, scoring:'half_tep',
      note: 'League-invariant anchor — same basis as the live verdict engine.' },
    engine_note: 'Includes System Score v2 offense-style factors (motion/TE2/PROE, validated 2022-25).',
    provenance,
    count: Object.keys(players).length,
    excluded_stale: excluded.sort(),
    headline: { top_buys: buys, top_sells: sells },
    players,
  };
  // Serialise once so a dry run can report the exact size it would have written.
  const json = JSON.stringify(out, null, 1);
  const kb   = (Buffer.byteLength(json) / 1024).toFixed(1);

  console.log(`${DRY_RUN ? 'DRY RUN' : 'FREEZE SNAPSHOT'}: ${out.count} players graded · ${excluded.length} excluded (stale/no market)`);
  console.log(`top buy:  ${buys[0] || '—'}`);
  console.log(`top sell: ${sells[0] || '—'}`);

  if (DRY_RUN) {
    console.log(`nothing written — would have written ${OUT_PATH} (${kb} KB)`);
    console.log('Re-run with --confirm' + (EXISTING ? ' --force' : '') + ' to write it.');
  } else {
    fs.mkdirSync('data', { recursive: true });
    fs.writeFileSync(OUT_PATH, json);
    console.log(`wrote ${OUT_PATH} (${kb} KB)`);
  }
})().catch(e => { console.error('SNAPSHOT FAILED:', e.stack || e.message); process.exit(1); });
