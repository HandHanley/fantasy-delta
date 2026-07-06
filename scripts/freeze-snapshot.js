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

  const comp = H.COMP;
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

  // verdicts: center on the live population median, then read vTag — the same
  // code path the app uses, so the frozen verdicts match the site exactly
  H.setCenter(H.computeMvCenter());
  for (const c of comp) {
    if (!players[c.n]) continue;
    const vm = (H.vTag(c).match(/>([a-z ]+)</) || [, null])[1];
    players[c.n].verdict = vm;
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
