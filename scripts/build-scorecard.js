#!/usr/bin/env node
/* DELTA Scorecard — scripts/build-scorecard.js → data/scorecard.json
 *
 * How accurate is DELTA's projection? Every projection is graded ONLY on games
 * played after it was made, as points per game over a stretch — never single weeks.
 *
 *   node scripts/build-scorecard.js            nightly: add any missing weekly
 *                                              snapshot, regrade, write the file
 *   node scripts/build-scorecard.js --dry-run  same, print, write nothing
 *   node scripts/build-scorecard.js --backfill <dataDir> --week N --note "..."
 *                                              one-off: add the Week N snapshot
 *                                              using the data files in <dataDir>
 *
 * RULES (fixed here and printed into the file; change them only with a dated note):
 *  - Graded players: exactly the 376 in data/freeze-2026.json (the ledger's set).
 *  - Scoring: 12-team superflex, half PPR, TE premium (the freeze's basis),
 *    each game scored by the engine's own gamefp().
 *  - A game counts if the game log marks it played (the live DNP rule).
 *  - Frozen headline: players with 2+ games this season AND 4+ last season.
 *  - A weekly snapshot = the live projection with this season's games through
 *    Week N only (later rows hidden), taken the first night Week N is complete
 *    (no game of that week still upcoming). Snapshots are NEVER overwritten.
 *  - A snapshot is graded on games AFTER Week N, for players with 2+ such games,
 *    1+ game through Week N and 4+ last season. "Ready" once 100+ players qualify.
 *  - Closest / farthest: frozen projection vs this season so far, drawn only from
 *    the top 100 players by market value AT THE FREEZE (all positions; fixed before
 *    any game, so no hindsight), 3+ games once 100+ graded players have 3, else 2+.
 *    Players on data/injury-overrides.json (out for the season) are left out of these two
 *    lists and named underneath (owner, 10 Oct 2026): a season-ender's number can never
 *    move again, so he would hold a slot all year. Display only: he stays in the
 *    headline, the snapshots and the player table exactly as before.
 *  - QB yardstick (owner, 3 Oct 2026): every photo records the ruler its QB projections used —
 *    'played' (every game played; all photos before QB points per start) or 'full_start'
 *    (engine 2026-10-03a on: a QB's projection is points per FULL start). In a 'full_start'
 *    photo, QB rows count only full starts (game-log qs: his team's most pass attempts, 10+),
 *    after the photo and through its week, for EVERY forecast in the row — all compared on
 *    the same games. Photos are never re-labelled. The frozen headline and closest/farthest
 *    stay on every game played (the ledger's Test 1 yardstick).
 *  - Measures follow the Accuracy Ledger's Test 1 (docs/ACCURACY-LEDGER.md §2): the
 *    headline is MAE, the average miss in points per game; RMSE is secondary.
 *  - Yardsticks: the ledger's two baselines (§2), graded only on players where BOTH
 *    have a number:
 *      last season's PPG (4+ games in 2025);
 *      a plain 3-year average: the mean of 2023, 2024 and 2025 PPG over the seasons
 *        with 4+ games (the ledger's own computation is not in the repo).
 *  - StatHead is deliberately NOT shown (owner, 26 Sep 2026): a single developer's
 *    model with no track record, and comparing against it invites the charge of
 *    picking weak opponents. It stays in data/freeze-2026-comparators.json, untouched.
 */
'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm');
const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'data', 'scorecard.json');
const MIN_G_NOW = 2, MIN_G_LAST = 4, MIN_G_AFTER = 2, MIN_READY = 100, TOP_N = 5, TOP_POOL = 100;

const args = process.argv.slice(2);
const flag = (f) => args.includes(f);
const opt = (f) => { const i = args.indexOf(f); return i >= 0 ? args[i + 1] : null; };
const known = new Set(['--dry-run', '--backfill', '--week', '--note']);
for (const a of args) if (a.startsWith('--') && !known.has(a)) { console.error(`[SCORECARD] unknown argument ${a}`); process.exit(2); }

// ── headless engine: the freeze script's boot chain, reading files from dataRoot ──
async function bootEngine(dataRoot, maxWeek) {
  const src = fs.readFileSync(path.join(ROOT, 'delta-engine.js'), 'utf8') + `
;globalThis.__H__={ get COMP(){return COMP}, gamefp, get SEASON(){return SEASON_YEAR}, get BUILD(){return DL_BUILD}, get INJ(){ return typeof INJ_OUT!=='undefined' && INJ_OUT ? INJ_OUT : {}; }, get PERSTART(){ return typeof QB_PS!=='undefined' && !!(QB_PS && QB_PS_LEVEL>0 && GL_HAS_QS); },
  set:(t,q,f)=>{ leagueTeams=t; qbFmt=q; scoringFmt=f; }, recompute:()=>applyMarketForSetting(),
  boot:async()=>{ await loadLiveMarketValues(); await loadPlayerStats(); await loadPlayerContracts();
    await loadRipples();
    if(typeof loadInjuryOverrides==='function'){ try{ await loadInjuryOverrides(); }catch(e){} }
    if(typeof loadQBStarters==='function'){ try{ await loadQBStarters(); }catch(e){} }
    if(typeof ensureStartData==='function'){ try{ await ensureStartData(); }catch(e){} }
    applyMarketForSetting(); } };`;
  const readData = (rel) => {
    const p = path.join(dataRoot, rel);
    if (!fs.existsSync(p)) return null;
    let body = fs.readFileSync(p, 'utf8');
    if (maxWeek != null && rel === 'data/game-logs.json') {       // hide this season's games after Week N
      const j = JSON.parse(body), season = 2026;
      for (const n of Object.keys(j.games || {}))
        j.games[n] = j.games[n].filter((r) => !(r.s === season && !r.up && r.w > maxWeek));
      body = JSON.stringify(j);
    }
    return body;
  };
  const sb = {
    console: { log: () => {}, warn: () => {}, error: () => {} }, setTimeout, Date, Math, JSON, Promise, URLSearchParams,
    location: { search: '' },
    fetch: async (u) => {
      const rel = String(u).replace(/\?.*$/, '').replace(/^\.\//, '');
      const body = rel.startsWith('data/') ? readData(rel)
        : (fs.existsSync(path.join(ROOT, rel)) ? fs.readFileSync(path.join(ROOT, rel), 'utf8') : null);
      if (body == null) return { ok: false, status: 404 };
      return { ok: true, json: async () => JSON.parse(body), text: async () => body };
    },
    localStorage: { getItem: () => null, setItem: () => {} },
    document: { getElementById: () => null, createElement: () => ({ style: {} }), body: { appendChild: () => {} }, querySelectorAll: () => [] },
  };
  sb.window = sb; sb.globalThis = sb; vm.createContext(sb); vm.runInContext(src, sb);
  const H = sb.__H__; await H.boot(); H.set(12, 'sf', 'half_tep'); H.recompute();
  if (H.SEASON !== 2026) throw new Error(`engine SEASON_YEAR is ${H.SEASON}; this builder is for the 2026 freeze`);
  return H;
}

const r2 = (x) => Math.round(x * 100) / 100;
const rmse = (e) => Math.sqrt(e.reduce((s, x) => s + x * x, 0) / e.length);
const mae = (e) => e.reduce((s, x) => s + Math.abs(x), 0) / e.length;

async function main() {
  const freeze = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'freeze-2026.json'), 'utf8'));
  const FZ = freeze.players, names = Object.keys(FZ);
  const prev = fs.existsSync(OUT) ? JSON.parse(fs.readFileSync(OUT, 'utf8')) : { snapshots: [] };
  const snaps = prev.snapshots || [];
  const have = new Set(snaps.map((s) => s.week));
  const logs = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'game-logs.json'), 'utf8')).games;
  const season = 2026;

  const takeSnapshot = async (dataRoot, week, source, note) => {
    if (have.has(week)) { console.log(`[SCORECARD] Week ${week} snapshot already exists — never overwritten`); return; }
    const H = await bootEngine(dataRoot, week);
    const proj = {};
    for (const c of H.COMP) if (FZ[c.n] && c.proj != null) proj[c.n] = r2(c.proj);
    const rec = { week, taken_at: new Date().toISOString(), source, engine: H.BUILD, note: note || null,
                  qb: H.PERSTART ? 'full_start' : 'played', proj };
    snaps.push(rec); have.add(week);
    console.log(`[SCORECARD] Week ${week} snapshot added (${source}, engine ${H.BUILD}, ${Object.keys(proj).length} players)`);
  };

  if (flag('--backfill')) {
    const dir = opt('--backfill'), week = Number(opt('--week'));
    if (!dir || !Number.isInteger(week) || week < 1) { console.error('[SCORECARD] --backfill needs <dataDir> --week N'); process.exit(2); }
    await takeSnapshot(path.resolve(dir), week, 'rebuilt', opt('--note'));
  } else {
    // completed weeks: played rows exist this season and no row of that week is still upcoming
    const wk = {};
    for (const rows of Object.values(logs)) for (const r of rows) if (r.s === season) {
      const w = (wk[r.w] = wk[r.w] || { up: 0, played: 0 });
      if (r.up) w.up++; else if (!r.dnp) w.played++;
    }
    const done = Object.keys(wk).map(Number).filter((w) => wk[w].played > 0 && wk[w].up === 0).sort((a, b) => a - b);
    const latest = done.length ? done[done.length - 1] : null;
    for (const w of done) if (!have.has(w) && (snaps.length === 0 || w > Math.min(...snaps.map((s) => s.week))))
      await takeSnapshot(ROOT, w, w === latest ? 'nightly' : 'late', null);
  }
  snaps.sort((a, b) => a.week - b.week);

  // ── grade, from today's data ──
  const H = await bootEngine(ROOT, null);
  const live = {}; for (const c of H.COMP) live[c.n] = c.proj;
  const games = (n, s, wmin = 1, wmax = 99) => (logs[n] || [])
    .filter((r) => r.s === s && !r.up && !r.dnp && r.w >= wmin && r.w <= wmax)
    .map((r) => H.gamefp(r, FZ[n].pos, 'half_tep'));
  const avg = (a) => a.reduce((x, y) => x + y, 0) / a.length;
  // A photo's own yardstick: in a 'full_start' photo a QB counts only his full starts (see the rules above).
  const gamesFor = (n, snap, wmin = 1, wmax = 99) => (logs[n] || [])
    .filter((r) => r.s === season && !r.up && !r.dnp && r.w >= wmin && r.w <= wmax
                   && !(snap.qb === 'full_start' && FZ[n].pos === 'QB' && !r.qs))
    .map((r) => H.gamefp(r, FZ[n].pos, 'half_tep'));

  const P = {};
  for (const n of names) {
    const g25 = games(n, season - 1), g26 = games(n, season);
    const seas = [season - 3, season - 2, season - 1].map((y) => games(n, y)).filter((g) => g.length >= MIN_G_LAST).map(avg);
    P[n] = { n, pos: FZ[n].pos, t: FZ[n].t, pre: FZ[n].proj,
      last: g25.length ? avg(g25) : null, lastG: g25.length, sofar: g26.length ? avg(g26) : null, sofarG: g26.length,
      a3: seas.length ? avg(seas) : null,
      live: live[n] ?? null };
  }

  const both = (rows, pick) => ({ mae: r2(mae(rows.map((x) => pick(x) - x.act))), rmse: r2(rmse(rows.map((x) => pick(x) - x.act))) });
  const fr = names.map((n) => P[n]).filter((p) => p.sofarG >= MIN_G_NOW && p.lastG >= MIN_G_LAST && p.pre != null && p.a3 != null)
    .map((p) => ({ pre: p.pre, last: p.last, a3: p.a3, act: p.sofar }));
  const frozen = fr.length ? { n: fr.length, delta: both(fr, (x) => x.pre), avg3: both(fr, (x) => x.a3), last: both(fr, (x) => x.last) } : null;

  const graded = snaps.map((s) => {
    const rows = [];
    for (const n of names) {
      if (s.proj[n] == null) continue;
      const after = gamesFor(n, s, s.week + 1), thru = gamesFor(n, s, 1, s.week);
      const p = P[n];
      if (after.length >= MIN_G_AFTER && thru.length >= 1 && p.lastG >= MIN_G_LAST && p.pre != null && p.a3 != null)
        rows.push({ live: s.proj[n], pre: p.pre, last: p.last, a3: p.a3, thru: avg(thru), act: avg(after) });
    }
    const m = (k) => rows.length ? both(rows, (x) => x[k]) : null;
    return { week: s.week, source: s.source, engine: s.engine, qb: s.qb || 'played', n: rows.length, ready: rows.length >= MIN_READY,
             live: m('live'), frozen: m('pre'), avg3: m('a3'), last: m('last'), thru: m('thru') };
  });

  // per-player snapshot line: the latest snapshot with 2+ games after it, else the earliest with 1+
  for (const n of names) {
    let pick = null;
    for (const s of snaps) {
      if (s.proj[n] == null) continue;
      const after = gamesFor(n, s, s.week + 1);
      if (after.length >= MIN_G_AFTER) pick = { w: s.week, snap: s.proj[n], since: avg(after), sinceG: after.length };
    }
    if (!pick) for (const s of snaps) {
      if (s.proj[n] == null) continue;
      const after = gamesFor(n, s, s.week + 1);
      if (after.length >= 1) { pick = { w: s.week, snap: s.proj[n], since: avg(after), sinceG: after.length }; break; }
    }
    Object.assign(P[n], pick ? { snapW: pick.w, snap: pick.snap, since: pick.since, sinceG: pick.sinceG } : {});
  }

  const withNow = names.map((n) => P[n]).filter((p) => p.sofarG >= 1 && p.pre != null);
  const three = withNow.filter((p) => p.sofarG >= 3).length >= MIN_READY;
  const minTop = three ? 3 : 2;
  // overall market rank at the freeze (value desc, name breaks ties) — fixed before any game
  const mktRank = {}; names.slice().sort((a, b) => (FZ[b].mkt || 0) - (FZ[a].mkt || 0) || a.localeCompare(b)).forEach((n, i) => { mktRank[n] = i + 1; });
  const inPool = withNow.filter((p) => p.sofarG >= minTop && mktRank[p.n] <= TOP_POOL);
  const leftOut = inPool.filter((p) => H.INJ[p.n]).map((p) => ({ n: p.n, why: 'out for the season' }));
  const pool = inPool.filter((p) => !H.INJ[p.n])
    .map((p) => ({ n: p.n, pos: p.pos, t: p.t, r: mktRank[p.n], pre: r2(p.pre), sofar: r2(p.sofar), g: p.sofarG, off: r2(p.pre - p.sofar) }));
  pool.sort((a, b) => Math.abs(a.off) - Math.abs(b.off) || a.n.localeCompare(b.n));
  const closest = pool.slice(0, TOP_N), farthest = pool.slice(-TOP_N).reverse();

  const round = (p) => { const o = {}; for (const [k, v] of Object.entries(p)) o[k] = typeof v === 'number' && !Number.isInteger(v) ? r2(v) : v; return o; };
  const through = snaps.length ? Math.max(...snaps.map((s) => s.week)) : 0;
  const out = {
    built_at: new Date().toISOString(), season, basis: '12-team superflex · half PPR · TE premium', engine: H.BUILD,
    through_week: through,
    rules: { graded: 'the 376 players in data/freeze-2026.json', min_games_now: MIN_G_NOW, min_games_last: MIN_G_LAST,
             min_games_after: MIN_G_AFTER, ready_at: MIN_READY, top_min_games: minTop, top_pool: TOP_POOL,
             metric: 'MAE (average miss, points per game); RMSE secondary — ledger Test 1',
             qb_yardstick: "each photo's own ruler: 'played' = every game played; 'full_start' = QB rows on full starts only (3 Oct 2026)" },
    frozen, graded, closest, farthest, left_out: leftOut,
    players: names.map((n) => round(P[n])).filter((p) => p.sofarG >= 1),
    snapshots: snaps,
  };
  console.log(`[SCORECARD] through Week ${through} · frozen ${JSON.stringify(frozen)} · snapshots ${graded.map((g) => `W${g.week}:n${g.n}${g.ready ? '' : '(early)'}`).join(' ') || 'none'} · players ${out.players.length} · left out of closest/farthest: ${leftOut.map((x) => x.n).join(', ') || 'none'}`);
  if (flag('--dry-run')) { console.log('[SCORECARD] --dry-run: nothing written'); return; }
  fs.writeFileSync(OUT, JSON.stringify(out));
  console.log(`[SCORECARD] wrote ${path.relative(ROOT, OUT)} (${(fs.statSync(OUT).size / 1024).toFixed(0)} KB)`);
}
main().catch((e) => { console.error('[SCORECARD] FAILED:', e && e.stack || e); process.exit(1); });
