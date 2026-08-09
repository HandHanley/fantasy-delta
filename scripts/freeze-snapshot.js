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
const fs = require('fs'), path = require('path'), vm = require('vm');

const src = fs.readFileSync('delta-engine.js', 'utf8') + `
;globalThis.__H__={
  get COMP(){return COMP}, mvAsset, glOf, vTag, computeMvCenter,
  get PLAYER_STATS(){ return typeof PLAYER_STATS!=='undefined' ? PLAYER_STATS : null; },
  get MKT_LOADED(){ return typeof MKT!=='undefined' ? MKT : null; },
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

  const out = {
    frozen_at: new Date().toISOString(),
    basis: { teams:12, superflex:true, scoring:'half_tep',
      note: 'League-invariant anchor — same basis as the live verdict engine.' },
    engine_note: 'Includes System Score v2 offense-style factors (motion/TE2/PROE, validated 2022-25).',
    count: Object.keys(players).length,
    excluded_stale: excluded.sort(),
    headline: { top_buys: buys, top_sells: sells },
    players,
  };
  fs.mkdirSync('data', { recursive: true });
  fs.writeFileSync('data/freeze-2026.json', JSON.stringify(out, null, 1));
  console.log(`FREEZE SNAPSHOT: ${out.count} players graded · ${excluded.length} excluded (stale/no market)`);
  console.log(`top buy:  ${buys[0] || '—'}`);
  console.log(`top sell: ${sells[0] || '—'}`);
  console.log('wrote data/freeze-2026.json');
})().catch(e => { console.error('SNAPSHOT FAILED:', e.stack || e.message); process.exit(1); });
