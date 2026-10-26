// DELTA Engine — shared scoring, data, and loading functions
// Loaded by both index.html and player.html

// ============================================================
// DYNASTY MODEL v5.5
// KEY CHANGES FROM v5.4:
// 1. WR/TE role multiplier replaced by YPRR-based efficiency score
// 2. RB role multiplier replaced by snap%-based utilization score
// 3. QB superflex multiplier removed (already priced in by market)
// 4. All PPG from exact user scoring format (unchanged)
// ============================================================

/* BUILD MARKER for this file. index.html carries its own in .foot-build and shows both
   in the footer when they differ. Bump this one whenever delta-engine.js is handed over,
   and leave index.html's alone unless index.html changed too — they move independently
   on purpose, so neither file has to be re-uploaded just to keep the other quiet. */
const DL_BUILD='2026-10-26a';

let scoringFmt='half_tep'; // global scoring format
// Position-average rec/game for format sensitivity
const REC_PG_POS_AVG={WR:3.21,RB:1.76,TE:3.06};
const REC_FMT_SENSITIVITY=0.010; // mv delta per (rec_delta x format_pts)
const REC_FMT_CAP=0.10; // max +/-10% mv shift from format

// How many extra rec pts each format gives vs base (0.5PPR + TE Premium)
function fmtRecPts(pos,fmt){
  if(fmt==='half_tep') return 0;
  if(fmt==='std')   return pos==='TE'?-1.0:-0.5;
  if(fmt==='half')  return pos==='TE'?-0.5:0;
  if(fmt==='full_tep') return 0.5;
  if(fmt==='full')  return pos==='TE'?0:0.5;
  return 0;
}

function formatMvShift(name,pos,fmt){
  if(!fmt||fmt==='half_tep') return 0;
  const rpg=REC_PG[name]||0;
  if(!rpg) return 0;
  const avg=REC_PG_POS_AVG[pos]||0;
  const recDelta=rpg-avg;
  const pts=fmtRecPts(pos,fmt);
  const shift=recDelta*pts*REC_FMT_SENSITIVITY;
  return Math.max(-REC_FMT_CAP,Math.min(REC_FMT_CAP,shift));
}

// ════════════════════════════════════════════════════════════
// START PROFILE — Hit/Miss/Elite distribution from per-game logs.
// 2-year rolling window, equal weight. Lines = data-derived VOR thresholds
// (data/start-profile-thresholds.json) keyed pos|fmt|teams|qb. Per-game points
// use the same scoring as fmtRecPts. DNP exclusion is handled at bake time
// (game-logs.json contains only ACTIVE games), so a 0-pt game here = a real miss.
// Data is EAGER, not lazy. This comment used to claim ensureStartData() ran on first
// player-card open; both bootDelta() (index.html) and player.html await it before the
// first render, and freeze-snapshot.js calls it too. That is deliberate and load-
// bearing, not an oversight: ensureStartData() syncs g25 from the game logs for ~136
// players, and calcProj has a rookie branch gated on g25===0, so a veteran scored
// before the sync lands in the rookie path. Deferring it is what made player.html
// disagree with the rankings on 186 verdicts. The cost is real and should be stated
// honestly rather than wished away: game-logs.json is 2.1MB and sits on the critical
// boot path, which is felt on mobile. If that ever needs fixing, the fix is a slim
// g25-only index baked at pipeline time — NOT moving this call back off the boot path.
// ════════════════════════════════════════════════════════════
// ── Watchlist (localStorage — per-device, per-user; nothing global changes) ──
// Entries are NAMESPACED as "nfl:Name" / "cfb:Name". A bare name cannot identify a
// player once college data exists: cross-checking the two universes found 53 shared
// names, 52 of which are the same human (2026 rookies who are also 2025 college
// players — that overlap is a feature) but one, Malik Washington, is genuinely two
// people: an established NFL WR with 31 games, and a Maryland QB.
// Legacy bare entries migrate to nfl: on first read. The migration is idempotent,
// and every helper defaults to nfl:, so existing call sites need no changes.
const DW_LS = 'delta_watchlist';
function dwRaw(){
  let a;
  try{ a = JSON.parse(localStorage.getItem(DW_LS) || '[]'); }catch(e){ return []; }
  if(!Array.isArray(a)) return [];
  const out=[]; let migrated=false;
  for(const e of a){
    if(typeof e!=='string' || !e) continue;          // drop junk rather than crash
    if(e.indexOf(':')<0){ out.push('nfl:'+e); migrated=true; }
    else out.push(e);
  }
  if(migrated){ try{ localStorage.setItem(DW_LS, JSON.stringify(out)); }catch(e){} }
  return out;
}
function dwKey(n, ns){ return (ns||'nfl')+':'+n; }
function dwList(ns){
  const pre=(ns||'nfl')+':';
  return dwRaw().filter(e=>e.slice(0,pre.length)===pre).map(e=>e.slice(pre.length));
}
function dwGet(){ return dwList('nfl'); }            // back-compat alias
function dwHas(n, ns){ return dwRaw().indexOf(dwKey(n,ns))>=0; }
function dwToggle(n, ns){
  const k=dwKey(n,ns), a=dwRaw(), i=a.indexOf(k);
  if(i>=0) a.splice(i,1); else a.push(k);
  try{ localStorage.setItem(DW_LS, JSON.stringify(a)); }catch(e){}
  // Cloud sync. No-op when signed out or when delta-sync.js failed to load;
  // the local write above has already happened either way.
  try{ if(typeof DSYNC!=='undefined') DSYNC.noteWatch(ns||'nfl', n, i<0); }catch(e){}
  return i<0;                                        // true = now watched
}
function dwCount(ns){ return ns ? dwList(ns).length : dwRaw().length; }
let GAMELOGS=null, STARTLINES=null, GAMELOGS_MAX=null, START_DATA_STATE='idle', GL_HAS_QS=false, GL_HAS_ST=false;
const QB_SP_SNAP=0.75;   // QB Start Profile: a bench appearance counts at this share of snaps (see qbSpCounts)
/* ACROSS YOUR LEAGUES (9 Oct 2026). DISPLAY ONLY: reads the per-device record My Team
   writes (localStorage 'delta_my_roster': per connected league, your players, every
   DELTA player rostered by anyone in it, and look-alike keys for rostered players
   DELTA could not match by name). Used by the player-page header and the Free Agents
   panel: "Owned in 2 of 3 leagues \u00b7 Available in 1". A player counts as available
   only when nobody rosters him AND no unmatched rostered player shares his position,
   first initial and last name, so a name mismatch can never show a taken player as
   free. Leagues saved before 9 Oct have no roster-wide list and are left out until
   they refresh (My Team does that in the background). Nothing scored reads this. */
function dlNearKey(name,pos){
  const w=String(name||'').toLowerCase().replace(/[.'\u2019\-]/g,'').replace(/\s+/g,' ').trim()
    .replace(/\s+(jr|sr|ii|iii|iv)$/,'').split(' ').filter(Boolean);
  if(!w.length) return '';
  return String(pos||'')+'|'+w[0].charAt(0)+'|'+w[w.length-1];
}
function dlLeagueReach(name,pos){
  let st=null;
  try{ st=JSON.parse(localStorage.getItem('delta_my_roster')||'null'); }catch(e){ return null; }
  const L=st&&st.leagues; if(!L) return null;
  const key=dlNearKey(name,pos), out={n:0,own:[],avail:[]};
  for(const id in L){
    const r=L[id];
    if(!r||!Array.isArray(r.taken)) continue;
    out.n++;
    const nm=r.name||'League';
    if((r.players||[]).indexOf(name)>-1) out.own.push(nm);
    else if(r.taken.indexOf(name)<0&&(r.near||[]).indexOf(key)<0) out.avail.push(nm);
  }
  return out.n?out:null;
}
function dlLeagueReachText(r){
  if(!r) return '';
  if(r.n===1) return r.own.length?'On your roster':(r.avail.length?'Available in your league':'');
  if(!r.own.length&&!r.avail.length) return 'Rostered in all '+r.n+' of your leagues';
  if(!r.own.length) return 'Available in '+r.avail.length+' of '+r.n+' leagues';
  return 'Owned in '+r.own.length+' of '+r.n+' leagues'+(r.avail.length?' \u00b7 Available in '+r.avail.length:'');
}
function dlLeagueReachTitle(r){
  if(!r) return '';
  const t=[];
  if(r.own.length) t.push('Owned: '+r.own.join(', '));
  if(r.avail.length) t.push('Available: '+r.avail.join(', '));
  return t.join(' | ');
}

/* DATA THAT DID NOT LOAD (9 Oct 2026). Every boot loader already carries on when its
   file is missing or broken, falling back to the numbers built into this file, which
   is right, but it did so silently, so a reader could be looking at stale figures with
   no way to know. Loaders now note the failure here; the pages show one small,
   dismissible line (dlShowLoadNotice). Files whose absence is normal (injury and QB
   starter overrides) are noted only when they fail outright, not when they are absent. */
const DL_LOAD_FAIL = [];
function dlNoteFail(what){ if(DL_LOAD_FAIL.indexOf(what)<0) DL_LOAD_FAIL.push(what); }
function dlShowLoadNotice(){
  if(!DL_LOAD_FAIL.length||typeof document==='undefined'||!document.body) return;
  if(document.getElementById('dl-load-notice')) return;
  const el=document.createElement('div');
  el.id='dl-load-notice'; el.setAttribute('role','status');
  el.style.cssText='position:fixed;left:12px;right:12px;bottom:calc(12px + env(safe-area-inset-bottom,0px));z-index:99980;'
    +'max-width:520px;margin:0 auto;background:var(--panel);border:1px solid var(--line);border-radius:10px;'
    +'padding:10px 38px 10px 12px;font-size:12px;line-height:1.45;color:var(--fog)';
  el.innerHTML='Some data didn'+"\u2019"+'t load ('+DL_LOAD_FAIL.join(', ')+'), so a few numbers may be out of date. Refresh to try again.'
    +'<button type="button" aria-label="Dismiss" style="position:absolute;top:6px;right:8px;background:none;border:0;'
    +'color:var(--fog-2);font-size:18px;line-height:1;cursor:pointer;padding:4px">\u00d7</button>';
  el.querySelector('button').onclick=function(){ el.remove(); };
  document.body.appendChild(el);
}

/* BOOT PREFETCH (9 Oct 2026). Both pages boot by awaiting seven loaders in turn,
   and each loader downloads its file and then processes it. The PROCESSING order
   matters (stats before contracts before overrides, g25 after the logs); the
   DOWNLOAD order never did. dlPrefetchBoot() starts every boot download at once,
   and a loader's own request for the same address is handed that in-flight
   response instead of starting a new one, so the files arrive together while the
   chain still runs in today's order. Same addresses and options the loaders send,
   so caching behaves exactly as before. One use per address: any later call
   downloads fresh. Called only by the pages (index.html, player.html), never by
   the Node scripts that also load this file. */
const DL_PREFETCH = {};
const DL_BOOT_FILES = [
  ['./data/market-values.json', {cache:'no-cache'}],
  ['./data/player-stats.json', {cache:'no-cache'}],
  ['./data/delta-contracts.json', {cache:'no-cache'}],
  ['./data/ripple.json', {cache:'no-cache'}],
  ['./data/injury-overrides.json', undefined],
  ['./data/qb-starters.json', undefined],
  ['./data/game-logs.json', {cache:'no-cache'}],
  ['./data/start-profile-thresholds.json', {cache:'no-cache'}],
];
function dlPrefetchBoot(){
  if(typeof fetch!=='function') return;
  for(const [u,o] of DL_BOOT_FILES){
    if(DL_PREFETCH[u]) continue;
    try{
      const p = o ? fetch(u,o) : fetch(u);
      p.catch(function(){});          // a failure surfaces in the loader that awaits it
      DL_PREFETCH[u] = p;
    }catch(e){}
  }
}
function dlFetch(u,o){
  const p = DL_PREFETCH[u];
  if(p){ delete DL_PREFETCH[u]; return p; }
  return o ? fetch(u,o) : fetch(u);
}

async function ensureStartData(){
  if(START_DATA_STATE==='loaded'||START_DATA_STATE==='loading') return START_DATA_STATE;
  START_DATA_STATE='loading';
  try{
    const [gl,th]=await Promise.all([
// NOTE ON CACHING: these used to append ?t=<timestamp>, which guaranteed a unique URL
// on every single load and therefore a full re-download of every data file, every time,
// from origin — roughly 1.8 MB raw on each launch with no possibility of a cache hit.
// {cache:'no-cache'} asks the browser to REVALIDATE instead: it sends the ETag, and an
// unchanged file comes back as a 304 with no body. Same freshness guarantee, a fraction
// of the bytes and round trips on repeat visits.
      dlFetch('./data/game-logs.json',{cache:'no-cache'}).then(r=>r.ok?r.json():Promise.reject('logs '+r.status)),
      dlFetch('./data/start-profile-thresholds.json',{cache:'no-cache'}).then(r=>r.ok?r.json():Promise.reject('thresh '+r.status)),
    ]);
    GAMELOGS=gl.games||{}; STARTLINES=th.lines||{};
    // QB start marks (qs) arrive with the 3 Oct pipeline. Without any, the QB blend keeps counting
    // every game — older data files behave exactly as before.
    GL_HAS_QS=false; for(const k in GAMELOGS){ if(GAMELOGS[k].some(g=>g.qs)){ GL_HAS_QS=true; break; } }
    // Starter marks (st, 22 Oct 2026) drive the QB Start Profile rule below. A file without any
    // keeps every QB game in the profile, exactly as before.
    GL_HAS_ST=false; for(const k in GAMELOGS){ if(GAMELOGS[k].some(g=>g.st)){ GL_HAS_ST=true; break; } }
    let mx=0; for(const k in GAMELOGS){ for(const g of GAMELOGS[k]){ if(g.s>mx) mx=g.s; } }
    GAMELOGS_MAX=mx; START_DATA_STATE='loaded';
    // ── g25 sync from game logs ──────────────────────────────
    // Game logs are the canonical played-games count under the locked DNP rule
    // (a game counts iff ≥1 offensive snap; 0-snap weeks never enter the logs).
    // Baked g25 values drift (hand-entry era), and the stats file's `games`
    // field undercounts traded players (one row per team stint), so this is
    // the one true source. Distinct weeks guards against any future duplicate
    // rows; 18 games IS legitimate for a player traded across different byes.
    // Conservative: never zeroes g25 (absent/empty logs leave the baked value),
    // so 2026 rookies (g25:0, no logs) are untouched and the rookie path holds.
    if(typeof RAW!=='undefined'){
      let synced=0; const zeroed=[];
      for(const p of RAW){
        const logs=GAMELOGS[p.n];
        if(!logs||!logs.length) continue;
        const wk=new Set();
        for(const g of logs){ if(g.s===2025 && !g.up && !g.dnp) wk.add(g.w); }
        if(wk.size>0&&p.g25!==wk.size){ p.g25=wk.size; synced++; }
        // Zero an invented 2025 season (27 Sep 2026). The built-in RAW table credited four
        // players with 2025 games they never played (Brooks 8, Lloyd 12, Mattison 10, Osborn
        // 12). Zero ONLY when both sources agree he did not play: his logs (so he is a tracked
        // NFL player, never a 2026 rookie) show no 2025 game, AND the loaded stats file has no
        // 2025 row. He is then treated as having sat out 2025, as the missed-time rule wants.
        else if(wk.size===0 && (p.g25||0)>0 && Object.keys(PLAYER_STATS||{}).length
                && !(((PLAYER_STATS[p.n]||{})['2025']||{}).games)){
          p.g25=0; p.ppg25=0; delete p.ppgH25; zeroed.push(p.n);
        }
      }
      if(zeroed.length) console.log('[DELTA] 2025 zeroed (logs and stats agree he did not play): '+zeroed.join(', '));
      if(synced) console.log('[DELTA] g25 synced from game logs for '+synced+' players');
    }
  }catch(e){ dlNoteFail('game logs'); console.warn('[DELTA] Start Profile data load failed:',e); START_DATA_STATE='error'; }
  return START_DATA_STATE;
}
function gamefp(g,pos,fmt){
  const baseRec = pos==='TE'?1.0 : (pos==='QB'?0:0.5);          // half_tep base per rec: 0.5 PPR + 0.5 TE premium
  const recAbs = baseRec + (pos==='QB'?0:fmtRecPts(pos,fmt));
  return g.py*0.04 + g.pt*4 + g.pi*-2 + g.ry*0.1 + g.rt*6
       + g.rec*recAbs + g.rey*0.1 + g.ret*6 + g.fl*-2 + g.tp*2 + g.rtd*6;
}
/* QB START PROFILE RULE (owner, 21-22 Oct 2026). A quarterback's game counts toward his
   Start Profile if he STARTED it, however short (an injury exit is still a start; the 3 Oct
   rule stands), or if he came off the bench and played 75%+ of the snaps. A kneel-down or
   mop-up cameo is not a start.
   DECIDED 22 Oct (owner, option A): a PLANNED REST game is not a start either. Josh Allen's
   one-snap Week 18s (2024, 2025), Maye and Stroud 2024 Week 18 are left out: the schedule
   credits the backup, and nobody started him expecting a game. An INJURY EXIT is a start and
   counts (Darnold 2026 Wk1 at 10% of snaps, Daniels 2024 Wk7, Hurts 2024 Wk16: 72 short
   started games in the windows on 22 Oct). Rejected: counting "his team's starter going
   in" (adds the rest games but also 5 backup cameos after a starter returned). No source we
   can reach says who took the first snap, so do not reopen this without one.
   Shipped as a data correction, not a model change. Touches the Start Profile only: game
   logs, PPG, the in-season blend and the per-start projection all read every game as before.
   st comes from the pipeline (fetch-game-logs.py, WHO STARTED AT QUARTERBACK). Measured on
   22 Oct live data: 33 of 65 QB profiles change, 8 projections move (all backups), calls
   flip for Pickett (sell->buy), Flacco (sell->hold) and Jack Bech (buy->hold, through the
   model-value recentring), no DELTA Score moves. Without st marks in the file, no change. */
function qbSpCounts(g,pos){
  if(pos!=='QB'||!GL_HAS_ST) return true;
  return !!g.st || (g.snp||0)>=QB_SP_SNAP;
}
function computeStartProfile(name,pos,fmt){
  fmt=fmt||scoringFmt;   // optional: calcProj asks for its half PPR + TE premium basis; displays use the league's
  if(!GAMELOGS||!STARTLINES||!GAMELOGS[name]) return null;
  const line=STARTLINES[pos+'|'+fmt];   // league-invariant: game quality depends on position + scoring only
  if(!line) return null;
  const [hit,elite]=line;
  const played=GAMELOGS[name].filter(g=>!g.up && !g.dnp && qbSpCounts(g,pos))   // played games only — never score upcoming/DNP
    .sort((a,b)=>(a.s-b.s)||((a.w||0)-(b.w||0)));
  const games=played.slice(-34);   // rolling window: most recent 34 games played (~two full seasons; rolls as the season unfolds)
  if(!games.length) return null;
  let m=0,ho=0,e=0;
  for(const g of games){ const fp=gamefp(g,pos,fmt); if(fp>=elite)e++; else if(fp>=hit)ho++; else m++; }
  const n=games.length;
  return {n, miss:m, hitOnly:ho, elite:e,
          missPct:Math.round(100*m/n), hitOnlyPct:Math.round(100*ho/n), elitePct:Math.round(100*e/n),
          hitPct:Math.round(100*(ho+e)/n),   // cumulative: a Hit includes Elite (Serviceable and up)
          lo:games[0].s, hi:games[n-1].s, hitLine:hit, eliteLine:elite};
}
function glOf(p,fmt){
  if(!p) return null;
  const sp=computeStartProfile(p.n, p.pos||p.p||'WR', fmt);
  return sp ? {miss:sp.missPct, hit:sp.hitPct, elite:sp.elitePct, g:sp.n} : null;
}
function startProfileHTML(p){
  const pos=p.pos||p.p||'WR';
  const sp=computeStartProfile(p.n,pos);
  if(!sp) return '<div class="dd-section"><div class="dd-section-label">Start Profile</div>'
    +'<div style="font-size:11px;color:var(--fog)">No recent game data for this player/format.</div></div>';
  const seg=(pct,col)=> pct>0?'<div style="width:'+pct+'%;background:'+col+'"></div>':'';
  const cell=(lbl,pct,cnt,col)=>'<div style="text-align:center;flex:1">'
    +'<div style="font-size:18px;font-weight:800;color:'+col+';line-height:1">'+pct+'%</div>'
    +'<div style="font-size:9px;color:var(--fog);letter-spacing:.05em;margin-top:2px">'+lbl+'</div>'
    +'<div style="font-size:9px;color:var(--fog-2)">'+cnt+' g</div></div>';
  return '<div class="dd-section"><div class="dd-section-label">Start Profile</div>'
    +'<div style="display:flex;height:8px;border-radius:4px;overflow:hidden;background:var(--panel);margin-bottom:9px">'
    + seg(sp.missPct,'var(--coral)')+seg(sp.hitOnlyPct,'var(--sky)')+seg(sp.elitePct,'var(--emerald)')+'</div>'
    +'<div style="display:flex;gap:4px">'
    + cell('MISS',sp.missPct,sp.miss,'var(--coral)')+cell('HIT',sp.hitPct,sp.hitOnly+sp.elite,'var(--sky)')+cell('ELITE',sp.elitePct,sp.elite,'var(--emerald)')
    +'</div>'
    +'<div style="font-size:9px;color:var(--fog-2);text-align:center;margin-top:8px">'
    + sp.n+' starts · '+sp.lo+'\u2013'+String(sp.hi).slice(2)+' · hit \u2265'+sp.hitLine+' · elite \u2265'+sp.eliteLine+' pts</div></div>';
}


// ══ Game Log (shared by index.html card + player.html page) ══════════════════
// ── Game Log (per-week results flowing into upcoming fixtures) ──────────────
// Reuses gamefp() so the FP column is scored at the current scoring format, and
// rides on the Start Profile data load (ensureStartData) — no extra fetch. Scores
// at render/expand time, exactly like Start Profile; an open card is NOT live-
// refreshed on a format change (matches existing card behavior). Position-aware
// columns; upcoming (up:1) rows show the fixture only, never scored (gamefp would
// be NaN on stat-less rows). Missing opponent (Week-18 numbering gap) renders '—'.
let _glPlayer=null, _glSeason=null, _glView='trend';
function renderGameLog(p){
  const host=document.getElementById('dd-gamelog');
  if(!host) return;
  _glPlayer=p; _glSeason=null; _glView='trend';
  if(START_DATA_STATE==='error'){ host.innerHTML=''; return; }
  if(START_DATA_STATE==='loaded'){ host.innerHTML=gameLogShell(p); return; }
  host.innerHTML='<div class="dd-section"><div class="dd-section-label">Game Log</div>'
    +'<div style="font-size:11px;color:var(--fog)">Loading game logs\u2026</div></div>';
  ensureStartData().then(()=>{ const h=document.getElementById('dd-gamelog'); if(h&&_glPlayer===p) h.innerHTML=gameLogShell(p); });
}
function glSeasons(p){
  const rows=(typeof GAMELOGS!=='undefined'&&GAMELOGS&&GAMELOGS[p.n])||[];
  const set=new Set(); for(const g of rows){ if(g.s!=null) set.add(g.s); }
  return [...set].sort((a,b)=>b-a);
}
function glFmtLabel(f){return ({half_tep:'0.5 PPR + TE Prem',half:'0.5 PPR',full_tep:'Full PPR + TE Prem',full:'Full PPR',std:'Standard'})[f]||f;}
// Default the season pill to the newest season with at least one PLAYED game.
// GAMELOGS_MAX counts upcoming (up:1) rows, so in the offseason it points at a season
// that has no games yet — which left Startability / vs Avg / Usage / Mix empty on every
// card until Week 2 of the live season. GAMELOGS_MAX itself is deliberately NOT changed:
// vs Avg's `isCurrent` early-season blending keys off it and must keep meaning "the live
// season". Once the new season kicks off this returns it automatically, so the pill
// self-corrects with no seasonal maintenance.
function glDefaultSeason(p,seasons){
  const rows=(typeof GAMELOGS!=='undefined'&&GAMELOGS&&GAMELOGS[p.n])||[];
  const played=new Set();
  for(const g of rows) if(!g.up&&!g.dnp&&g.s!=null) played.add(g.s);
  for(const s of seasons) if(played.has(s)) return s;   // seasons is sorted newest-first
  return (typeof GAMELOGS_MAX!=='undefined'&&seasons.includes(GAMELOGS_MAX))?GAMELOGS_MAX:seasons[0];
}
function gameLogShell(p){
  const seasons=glSeasons(p);
  if(!seasons.length) return '';   // no logs → no section (keep the card clean)
  if(_glSeason==null || !seasons.includes(_glSeason))
    _glSeason=glDefaultSeason(p,seasons);
  return '<div class="dd-section">'
    +'<div class="dd-section-label" style="cursor:pointer;display:flex;align-items:center;gap:6px" onclick="glToggle()">'
      +'<span id="gl-chev" style="display:inline-block;transition:transform .15s;transform:rotate(90deg)">\u25b8</span> Game Log'
    +'</div>'
    +'<div id="dd-gamelog-body" style="display:block">'+gameLogInner(p)+'</div>'
  +'</div>';
}
function gameLogInner(p){
  const seasons=glSeasons(p);
  const views=[['table','Schedule'],['start','Startability'],['avg','vs Avg'],['usage','Usage'],['mix','Mix'],['trend','Trend'],['eff','Efficiency']];
  const vsw=views.map(v=>
    '<span class="gl-tab" onclick="glSetView(\''+v[0]+'\')" style="cursor:pointer;font-size:10px;font-weight:700;padding:4px 6px;border-radius:10px;white-space:nowrap;text-align:center;'
    +(v[0]===_glView?'background:var(--teal-br,#2DD4BF);color:var(--ink)':'background:var(--line);color:var(--fog)')+'">'+v[1]+'</span>'
  ).join('');
  const chips=seasons.map(s=>
    '<span onclick="glSetSeason('+s+')" style="cursor:pointer;font-size:10px;font-weight:700;padding:2px 8px;border-radius:10px;margin-right:5px;'
    +(s===_glSeason?'background:var(--emerald);color:var(--ink)':'background:var(--line);color:var(--fog)')+'">'+s+'</span>'
  ).join('');
  const content = _glView==='table'
    ? '<div style="overflow-x:auto">'+gameLogTable(p,_glSeason)+'</div>'
    : _glView==='avg'
    ? gameLogVsAvg(p,_glSeason)
    : _glView==='usage'
    ? gameLogUsage(p,_glSeason)
    : _glView==='mix'
    ? gameLogMix(p,_glSeason)
    : _glView==='trend'
    ? gameLogTrend(p,_glSeason)
    : _glView==='eff'
    ? gameLogEff(p)
    : gameLogChart(p,_glSeason,_glView);
  const subs={
    table:'Week-by-week opponents, box scores, and upcoming games.',
    start:'Each week vs your league\u2019s startable and elite bars.',
    avg:'Weekly margin vs the typical top-starter at the position.',
    usage:'The opportunity (touches, targets, snaps) underneath the points.',
    mix:'How much of the scoring came from repeatable yardage vs touchdowns.',
    trend:'Direction of form across seasons \u2014 gold marks a new play-caller.',
    eff:'This season, game by game, in the efficiency measure DELTA uses for his position.'
  };
  const sub='<div style="font-size:9.5px;color:var(--fog-2);margin:0 0 .45rem">'+(subs[_glView]||'')+'</div>';
  /* Even rows (4 Oct 2026): seven chips wrapped as six plus one alone on a phone. A grid of
     equal cells, at least 64px each, gives four and three on a phone and a single row where
     there is room for all seven. */
  return '<div class="gl-tabs" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(64px,1fr));gap:5px;margin:.35rem 0 .3rem">'+vsw+'</div>'
    +sub
    +((_glView==='trend'||_glView==='eff')?'':'<div style="display:flex;flex-wrap:wrap;align-items:center;margin:0 0 .55rem">'+chips+'</div>')
    +content;
}
function glToggle(){
  const b=document.getElementById('dd-gamelog-body'), c=document.getElementById('gl-chev');
  if(!b) return;
  const open=b.style.display!=='none';
  b.style.display=open?'none':'block';
  if(c) c.style.transform=open?'rotate(0deg)':'rotate(90deg)';
}
function glSetSeason(s){
  _glSeason=s;
  const b=document.getElementById('dd-gamelog-body');
  if(b&&_glPlayer) b.innerHTML=gameLogInner(_glPlayer);
}
function glSetView(v){
  _glView=v;
  const b=document.getElementById('dd-gamelog-body');
  if(b&&_glPlayer) b.innerHTML=gameLogInner(_glPlayer);
}
function gameLogTable(p,season){
  const pos=p.pos||p.p||'WR';
  const rows=((typeof GAMELOGS!=='undefined'&&GAMELOGS&&GAMELOGS[p.n])||[])
    .filter(g=>g.s===season).sort((a,b)=>(a.w||0)-(b.w||0));
  if(!rows.length) return '<div style="font-size:11px;color:var(--fog)">No games.</div>';
  const line=(typeof STARTLINES!=='undefined'&&STARTLINES)?STARTLINES[pos+'|'+scoringFmt]:null;
  const cols = pos==='QB'
    ? [['Wk','w'],['Opp','opp'],['C/A','ca'],['PaYd','py'],['TD','pt'],['Int','pi'],['Car','car'],['RuYd','ry'],['RuTD','rt'],['FL','fl'],['FP','fp']]
    : pos==='RB'
    ? [['Wk','w'],['Opp','opp'],['Snp','snp'],['Car','car'],['RuYd','ry'],['YPC','ypc'],['RuTD','rt'],['Rec/Tgt','rectgt'],['ReYd','rey'],['ReTD','ret'],['FL','fl'],['FP','fp']]
    : [['Wk','w'],['Opp','opp'],['Snp','snp'],['Rec/Tgt','rectgt'],['ReYd','rey'],['ReTD','ret'],['FP','fp']];
  const th=cols.map(c=>'<th style="text-align:'+(c[1]==='opp'?'left':'right')+';padding:3px 6px;font-size:9px;color:var(--fog-2);font-weight:700;white-space:nowrap">'+c[0]+'</th>').join('');
  const oppCell=g=>{ if(g.opp==null) return '<span style="color:var(--fog-2)">\u2014</span>'; return (g.h===1?'vs ':'@ ')+g.opp; };
  const body=rows.map(g=>{
    if(g.up||g.dnp){
      const span=cols.length-2;
      const lbl=g.dnp?'DNP \u2014 did not play':'upcoming';
      return '<tr style="opacity:'+(g.dnp?'.45':'.5')+';border-top:1px solid var(--line)">'
        +'<td style="padding:3px 6px;text-align:right">'+g.w+'</td>'
        +'<td style="padding:3px 6px;text-align:left;white-space:nowrap">'+oppCell(g)+'</td>'
        +'<td colspan="'+span+'" style="padding:3px 6px;text-align:right;font-style:italic;color:var(--fog-2)">'+lbl+'</td>'
        +'</tr>';
    }
    const fp=gamefp(g,pos,scoringFmt);
    const fpClr = line ? (fp>=line[1]?'var(--emerald)':fp>=line[0]?'var(--sky)':'var(--coral)') : 'var(--fog)';
    const R=v=>'<td style="padding:3px 6px;text-align:right">'+v+'</td>';
    const cell=c=>{
      const k=c[1];
      if(k==='w')   return R(g.w);
      if(k==='opp') return '<td style="padding:3px 6px;text-align:left;white-space:nowrap">'+oppCell(g)+'</td>';
      if(k==='snp') return R(g.snp!=null?Math.round(g.snp*100)+'%':'\u2014');
      if(k==='ca')  return R((g.cmp||0)+'/'+(g.pa||0));
      if(k==='ypc') return R(g.car?(g.ry/g.car).toFixed(1):'\u2014');
      if(k==='rectgt') return R((g.rec||0)+'/'+(g.tgt||0));
      if(k==='fp')  return '<td style="padding:3px 6px;text-align:right;font-weight:700;color:'+fpClr+'">'+fp.toFixed(1)+'</td>';
      const v=g[k]; return R(v!=null?v:0);
    };
    return '<tr style="border-top:1px solid var(--line)">'+cols.map(cell).join('')+'</tr>';
  }).join('');
  const legend = line
    ? '<div style="font-size:9px;color:var(--fog-2);margin-top:5px">FP at '+glFmtLabel(scoringFmt)
      +' \u00b7 <span style="color:var(--emerald)">elite \u2265'+line[1]+'</span>'
      +' \u00b7 <span style="color:var(--sky)">hit \u2265'+line[0]+'</span>'
      +' \u00b7 <span style="color:var(--coral)">miss</span></div>'
    : '';
  return '<table class="gl-tbl" style="width:100%;border-collapse:collapse;font-size:11px"><thead><tr>'+th+'</tr></thead><tbody>'+body+'</tbody></table>'+legend;
}
function gameLogChart(p,season,view){
  const pos=p.pos||p.p||'WR';
  const rows=((typeof GAMELOGS!=='undefined'&&GAMELOGS&&GAMELOGS[p.n])||[])
    .filter(g=>g.s===season&&!g.up&&!g.dnp).sort((a,b)=>(a.w||0)-(b.w||0));
  if(rows.length<3) return '<div style="font-size:11px;color:var(--fog);padding:8px 0">Not enough played games this season to chart.</div>';
  const line=(typeof STARTLINES!=='undefined'&&STARTLINES)?STARTLINES[pos+'|'+scoringFmt]:null;
  const fps=rows.map(g=>gamefp(g,pos,scoringFmt));
  const n=fps.length, avg=fps.reduce((a,b)=>a+b,0)/n;
  const sd=Math.sqrt(fps.reduce((a,b)=>a+(b-avg)*(b-avg),0)/n);
  const srt=[...fps].sort((a,b)=>a-b);
  const median=n%2?srt[(n-1)/2]:(srt[n/2-1]+srt[n/2])/2;
  const maxv=(Math.max.apply(null,fps.concat(line?[line[1]]:[]))*1.12)||10;
  const W=560, x0=20, x1=W-8, base=150, top=14, sc=(base-top)/maxv;
  const bxR=x1-52;   // reserve right margin so the hit/elite labels never sit behind the last bars
  const slot=(bxR-x0)/n, bw=Math.min(20,slot*0.66);
  const bx=i=>x0+slot*i+(slot-bw)/2, y=v=>base-v*sc;
  let s='';
  if(line){
    [[line[0],'hit \u2265'+line[0],'var(--sky)'],[line[1],'elite \u2265'+line[1],'var(--emerald)']].forEach(a=>{
      s+='<line x1="'+x0+'" y1="'+y(a[0]).toFixed(1)+'" x2="'+bxR+'" y2="'+y(a[0]).toFixed(1)+'" stroke="'+a[2]+'" stroke-width="1" stroke-dasharray="4 3"/>';
      s+='<text x="'+(bxR+5)+'" y="'+(y(a[0])+3).toFixed(1)+'" font-size="9" text-anchor="start" fill="var(--fog-2)">'+a[1]+'</text>';
    });
  }
  s+='<line x1="'+x0+'" y1="'+base+'" x2="'+bxR+'" y2="'+base+'" stroke="var(--line)"/>';
  rows.forEach((g,i)=>{
    const f=fps[i];
    const c = line ? (f>=line[1]?'var(--emerald)':f>=line[0]?'var(--sky)':'var(--coral)') : 'var(--fog)';
    const h=Math.max(2,f*sc), yy=base-h;
    s+='<rect x="'+bx(i).toFixed(1)+'" y="'+yy.toFixed(1)+'" width="'+bw.toFixed(1)+'" height="'+h.toFixed(1)+'" rx="2" fill="'+c+'"/>';
    s+='<text x="'+(bx(i)+bw/2).toFixed(1)+'" y="'+(base+11)+'" font-size="8" text-anchor="middle" fill="var(--fog-2)">'+g.w+'</text>';
  });
  let sum='';
  if(line){
    const nS=fps.filter(f=>f>=line[0]).length, nE=fps.filter(f=>f>=line[1]).length, nM=fps.filter(f=>f<line[0]).length;
    const cv=avg>0?sd/avg:0, vlabel=cv<0.35?'steady':cv<0.55?'moderate':'volatile';
    sum='<div>Startable <b>'+nS+'/'+n+' ('+Math.round(100*nS/n)+'%)</b> \u00b7 elite <b>'+nE+'</b> \u00b7 miss <b>'+nM+'</b> \u2014 vs your '+glFmtLabel(scoringFmt)+' bar</div>'
      +'<div style="margin-top:2px">floor <b>'+Math.min.apply(null,fps).toFixed(1)+'</b> \u00b7 median <b>'+median.toFixed(1)+'</b> \u00b7 ceiling <b>'+Math.max.apply(null,fps).toFixed(1)+'</b> \u00b7 <b style="color:var(--paper)">'+vlabel+'</b></div>';
  }
  return '<svg viewBox="0 0 '+W+' 168" width="100%" role="img"><title>Startability</title>'+s+'</svg>'
    +'<div style="font-size:10px;color:var(--fog-2);margin-top:4px;line-height:1.6">'+sum+'</div>';
}


// ── Positional-average baseline + "vs Avg" view ──────────────────────────────
// Compares a player's weekly score to the AVERAGE STARTER at his position (a
// higher, peer-relative bar than the startable floor). Baseline = mean per-game
// score of the top-N players at the position, N = starters × teams. Blended
// (flex-aware) starter counts come from the scarcity engine for RB/WR/TE; QB
// uses format (SF assumes 2 QB/roster). SCAR_STARTERS is READ, never mutated —
// the 32/32 scarcity validation is unaffected.
let _POS_BY_NAME=null;
function posByName(){
  if(_POS_BY_NAME) return _POS_BY_NAME;
  const m={};
  if(typeof RAW!=='undefined'&&RAW) for(const p of RAW){ if(p&&p.n) m[p.n]=p.p||p.pos||null; }
  _POS_BY_NAME=m; return m;
}
function vsAvgStarterN(pos,teams,fmt){
  const per = pos==='QB' ? (fmt==='sf'?2.0:1.0)
            : (typeof SCAR_STARTERS!=='undefined' ? (SCAR_STARTERS[pos]||3.0) : ({RB:2.4,WR:3.0,TE:1.1}[pos]||3.0));
  return Math.max(1, Math.round(per*teams));
}
const _posAvgCache={};
function posAvgRaw(pos,season,fmt,N){
  const key=pos+'|'+season+'|'+fmt+'|'+N;
  if(key in _posAvgCache) return _posAvgCache[key];
  const pm=posByName(); const players=[];
  for(const name in GAMELOGS){
    if(pm[name]!==pos) continue;
    const gs=GAMELOGS[name].filter(g=>g.s===season&&!g.up&&!g.dnp);
    if(!gs.length) continue;
    const fps=gs.map(g=>gamefp(g,pos,fmt));
    players.push({fps, avg:fps.reduce((a,b)=>a+b,0)/fps.length});
  }
  let v=null;
  if(players.length){
    players.sort((a,b)=>b.avg-a.avg);
    const all=[]; for(const t of players.slice(0,N)) for(const f of t.fps) all.push(f);
    all.sort((a,b)=>a-b);
    const mid=Math.floor(all.length/2);
    v = all.length%2 ? all[mid] : (all[mid-1]+all[mid])/2;   // MEDIAN of the top-N pool's games — the typical starter, immune to the elite-tail skew a mean carries
  }
  _posAvgCache[key]=v; return v;
}
// Public baseline. Early in the CURRENT season a 2-3 game sample is noisy, so
// blend toward the prior season's average until ~6 weeks of data exist.
function posAverage(pos,season,fmt,teams,qbf){
  const N=vsAvgStarterN(pos,teams,qbf);
  const cur=posAvgRaw(pos,season,fmt,N);
  const pm=posByName(); let maxWk=0;
  for(const name in GAMELOGS){ if(pm[name]!==pos) continue;
    for(const g of GAMELOGS[name]) if(g.s===season&&!g.up&&!g.dnp&&(g.w||0)>maxWk) maxWk=g.w; }
  const isCurrent = (typeof GAMELOGS_MAX!=='undefined') && season===GAMELOGS_MAX;
  if(isCurrent && maxWk>0 && maxWk<6){
    const prior=posAvgRaw(pos,season-1,fmt,N);
    if(prior!=null && cur!=null){ const w=maxWk/6; return {line:w*cur+(1-w)*prior, N, seeded:true}; }
    if(prior!=null){ return {line:prior, N, seeded:true}; }
  }
  return {line:cur, N, seeded:false};
}
// Diverging bar chart: center line = positional average; green up = above,
// red down = below; bar length = margin.
function gameLogVsAvg(p,season){
  const pos=p.pos||p.p||'WR';
  const rows=((typeof GAMELOGS!=='undefined'&&GAMELOGS&&GAMELOGS[p.n])||[])
    .filter(g=>g.s===season&&!g.up&&!g.dnp).sort((a,b)=>(a.w||0)-(b.w||0));
  if(rows.length<1) return '<div style="font-size:11px;color:var(--fog);padding:8px 0">No played games this season to chart.</div>';
  const teams=(typeof leagueTeams!=='undefined'?leagueTeams:12), qf=(typeof qbFmt!=='undefined'?qbFmt:'sf');
  const pa=posAverage(pos,season,scoringFmt,teams,qf);
  if(pa.line==null) return '<div style="font-size:11px;color:var(--fog);padding:8px 0">Not enough positional data to compute an average for this season yet.</div>';
  const base0=pa.line, fps=rows.map(g=>gamefp(g,pos,scoringFmt)), margins=fps.map(f=>f-base0);
  const n=rows.length, maxMag=Math.max(1, Math.max.apply(null,margins.map(Math.abs))*1.12);
  const W=560, x0=20, x1=W-8, bxR=x1-8, mid=82, half=60, sc=half/maxMag;
  const slot=(bxR-x0)/n, bw=Math.min(20,slot*0.66), bx=i=>x0+slot*i+(slot-bw)/2;
  let s='<line x1="'+x0+'" y1="'+mid+'" x2="'+bxR+'" y2="'+mid+'" stroke="var(--fog-2)" stroke-width="1.5"/>';
  rows.forEach((g,i)=>{
    const m=margins[i], up=m>=0, h=Math.max(2,Math.abs(m)*sc);
    s+='<rect x="'+bx(i).toFixed(1)+'" y="'+(up?mid-h:mid).toFixed(1)+'" width="'+bw.toFixed(1)+'" height="'+h.toFixed(1)+'" rx="2" fill="'+(up?'var(--emerald)':'var(--coral)')+'"/>';
    s+='<text x="'+(bx(i)+bw/2).toFixed(1)+'" y="156" font-size="8" text-anchor="middle" fill="var(--fog-2)">'+g.w+'</text>';
  });
  const nAbove=margins.filter(m=>m>=0).length, avgM=margins.reduce((a,b)=>a+b,0)/n;
  const sum='Above the top-'+pa.N+' '+pos+' median (<b>'+base0.toFixed(1)+'</b>) in <b>'+nAbove+'/'+n+' ('+Math.round(100*nAbove/n)+'%)</b> weeks \u00b7 avg margin <b style="color:'+(avgM>=0?'var(--emerald)':'var(--coral)')+'">'+(avgM>=0?'+':'')+avgM.toFixed(1)+'</b>'
    + (pa.seeded?' \u00b7 <span style="color:var(--fog-2)">early-season baseline seeded from prior year</span>':'');
  return '<svg viewBox="0 0 '+W+' 168" width="100%" role="img"><title>vs positional average</title>'+s+'</svg>'
    +'<div style="font-size:10px;color:var(--fog-2);margin-top:4px;line-height:1.6">'+sum+'</div>';
}


// ── Usage view: week-to-week opportunity (leading indicator the market lags) ──
// A DIVERGENCE screen. Position-aware bars = weekly opportunity (WR/TE targets;
// RB carries+targets; QB attempts+carries). White line = snap share (role).
// Violet = raw fantasy points that week. When bars and points track together the
// production matches the role; when they split, one is outrunning the other.
// Footer states the recent-vs-prior trend as pure facts.
function _avg(a){ return a.length? a.reduce((x,y)=>x+y,0)/a.length : 0; }
function gameLogUsage(p,season){
  const pos=p.pos||p.p||'WR';
  const rows=((typeof GAMELOGS!=='undefined'&&GAMELOGS&&GAMELOGS[p.n])||[])
    .filter(g=>g.s===season&&!g.up&&!g.dnp).sort((a,b)=>(a.w||0)-(b.w||0));
  if(rows.length<2) return '<div style="font-size:11px;color:var(--fog);padding:8px 0">Not enough games this season to chart usage.</div>';
  const n=rows.length;
  const pts=rows.map(g=>gamefp(g,pos,scoringFmt));
  const isQB=pos==='QB', isRB=pos==='RB', isRecv=!isQB&&!isRB;
  // WR/TE bars show TARGET SHARE (tgt / team targets that week) — the volume-blind read
  // on whether the offense is actually funneling through him, rather than just throwing
  // a lot. RB deliberately stays on RAW targets: backs rarely command a big share, but
  // the handful of targets they do get are highly fantasy-relevant, and a share view
  // would flatten that signal to near-zero. QB is unaffected.
  //
  // shareOK is ALL-OR-NOTHING per season: every week needs a usable denominator, because
  // mixing share weeks with raw-count weeks on one axis is a unit error. Two ways a week
  // qualifies — it carries `tt`, OR it had zero targets (zero targets is zero share no
  // matter the denominator). That second clause is load-bearing: snap-only rows (snaps
  // recorded, no stat line) have no team attribution at all, so without it a single such
  // week would deny a receiver the share view permanently, even on refreshed data.
  // If any week still fails, the whole view falls back to raw targets (pre-refresh state).
  const shareOK = isRecv && rows.every(g=>(g.tt||0)>0 || (g.tgt||0)===0);
  const shr = g=> (g.tt||0)>0 ? Math.min(1,(g.tgt||0)/g.tt) : 0;   // capped: a team-total mismatch can't exceed 100%
  const part1=rows.map(g=> isQB?(g.pa||0) : isRB?(g.car||0) : (shareOK?shr(g):(g.tgt||0)));  // att / carries / tgt share|tgt
  const part2=rows.map(g=> isQB?(g.car||0) : isRB?(g.tgt||0) : 0);          // carries / targets / —
  const l1= isQB?'att' : isRB?'car' : (shareOK?'tgt share':'tgt');
  const l2= isQB?'car' : isRB?'tgt' : '';
  const totU=rows.map((g,i)=>part1[i]+part2[i]);
  const useSnap=!isQB, snp=rows.map(g=>g.snp||0);
  const W=560,x0=20,x1=W-8,bxR=x1-8,top=30,base=150,plotH=base-top;
  // Share is a 0-1 fraction, so the Math.max(1,...) floor used for counts silently pinned it
  // to a 0-100% axis. No receiver cleared 59% in 2,252 charted weeks, so the top 40% of the
  // plot was dead space and a typical 15% week rendered as a stub. Cap share at 60% — never
  // clips, keeps every receiver on ONE comparable scale, and raises the typical week from
  // 15% to 25% of plot height. Auto-extends in 20pt steps if a week ever clears the cap.
  const uRaw=Math.max.apply(null,totU);
  const uMax = shareOK ? Math.min(1,Math.max(0.6,Math.ceil(uRaw/0.2)*0.2)) : Math.max(1,uRaw*1.15);
  const pMax=Math.max(1,Math.max.apply(null,pts)*1.15);
  const slot=(bxR-x0)/n, bw=Math.min(22,slot*0.6), bx=i=>x0+slot*i+(slot-bw)/2, cx=i=>bx(i)+bw/2;
  const yS=v=>base-v*plotH, yP=v=>base-(v/pMax)*plotH;
  // recent/prior comparison windows (match the footer) — faint bands so the readout is locatable on the chart
  const k = n>=8?4:Math.max(1,Math.floor(n/2));
  const bandX=(a,b)=>[x0+slot*a, x0+slot*(b+1)];
  let s='';
  if(n-k-1>=Math.max(0,n-2*k)){ const w=bandX(Math.max(0,n-2*k),n-k-1);
    s+='<rect x="'+w[0].toFixed(1)+'" y="'+top+'" width="'+(w[1]-w[0]).toFixed(1)+'" height="'+(base-top)+'" fill="var(--paper)" opacity="0.035"/>'; }
  { const w=bandX(n-k,n-1);
    s+='<rect x="'+w[0].toFixed(1)+'" y="'+top+'" width="'+(w[1]-w[0]).toFixed(1)+'" height="'+(base-top)+'" fill="var(--paper)" opacity="0.08"/>'; }
  rows.forEach((g,i)=>{
    const h1=(part1[i]/uMax)*plotH, h2=(part2[i]/uMax)*plotH;
    // Share bars carry a hover readout of the counts under the percentage (facts, not just a
    // ratio). Zero-target weeks qualify for share without a `tt` (see shareOK), so they have
    // no denominator to show — report the bare count instead of "0 of undefined".
    const t1 = shareOK
      ? '<title>Wk '+g.w+' \u2014 '+((g.tt||0)>0
          ? (g.tgt||0)+' of '+g.tt+' team targets ('+Math.round(part1[i]*100)+'%)'
          : '0 targets')+'</title>'
      : '';
    s+='<rect x="'+bx(i).toFixed(1)+'" y="'+(base-h1).toFixed(1)+'" width="'+bw.toFixed(1)+'" height="'+h1.toFixed(1)+'" fill="var(--teal-br)" opacity="0.85">'+t1+'</rect>';
    if(h2>0) s+='<rect x="'+bx(i).toFixed(1)+'" y="'+(base-h1-h2).toFixed(1)+'" width="'+bw.toFixed(1)+'" height="'+h2.toFixed(1)+'" fill="var(--topaz)" opacity="0.85"/>';
    s+='<text x="'+cx(i).toFixed(1)+'" y="164" font-size="10" text-anchor="middle" fill="var(--fog-2)">'+g.w+'</text>';
  });
  const poly=(vals,yf)=>vals.map((v,i)=>cx(i).toFixed(1)+','+yf(v).toFixed(1)).join(' ');
  const dots=(vals,yf,col,r)=>vals.map((v,i)=>'<circle cx="'+cx(i).toFixed(1)+'" cy="'+yf(v).toFixed(1)+'" r="'+(r||2.1)+'" fill="'+col+'" stroke="var(--ink)" stroke-width="0.6"/>').join('');
  // raw weekly fantasy points — brand violet, dashed + dots (production the usage is meant to produce)
  s+='<polyline points="'+poly(pts,yP)+'" fill="none" stroke="var(--violet)" stroke-width="1.8" stroke-dasharray="4 3"/>'+dots(pts,yP,'var(--violet)',2.1);
  // snap share (non-QB) — white line over a dark halo so it reads on top of the bright bars
  if(useSnap){ const sp=poly(snp,yS);
    s+='<polyline points="'+sp+'" fill="none" stroke="var(--ink)" stroke-width="3.6" stroke-linejoin="round" stroke-linecap="round"/>'
     +'<polyline points="'+sp+'" fill="none" stroke="var(--paper)" stroke-width="2"/>'+dots(snp,yS,'var(--paper)',2.3); }
  // ── peak-bar annotation: ONE number above the tallest bar calibrates every other bar by
  // eye — no axis needed. An axis was tried and failed: this plot carries three y-scales
  // (bars, snap%, fantasy pts), so any single labeled axis is actively wrong for two of the
  // three layers (a ~90% snap line "read" as 60% share). Share views label the peak share;
  // count views label peak total opportunities. Drawn LAST so the snap/points lines
  // cannot paint over it, with an ink halo (paint-order) for contrast either way — the
  // worst case is exactly a near-cap bar, whose label sits in snap-line territory.
  { let im=0; for(let i=1;i<n;i++) if(totU[i]>totU[im]) im=i;
    const pv = shareOK ? Math.round(part1[im]*100)+'%' : String(Math.round(totU[im]));
    const py_ = Math.max(top+9, base-(totU[im]/uMax)*plotH-5);
    s+='<text x="'+cx(im).toFixed(1)+'" y="'+py_.toFixed(1)+'" font-size="12" font-weight="700" text-anchor="middle" fill="var(--paper)" stroke="var(--ink)" stroke-width="3" paint-order="stroke" stroke-linejoin="round">'+pv+'</text>'; }
  // legend
  let lg='<g font-size="10" fill="var(--fog)">';
  lg+='<rect x="20" y="12" width="9" height="9" fill="var(--teal-br)" opacity="0.85"/><text x="32" y="20">'+l1+'</text>';
  let lx=32+l1.length*6+12;
  if(l2){ lg+='<rect x="'+lx+'" y="12" width="9" height="9" fill="var(--topaz)" opacity="0.85"/><text x="'+(lx+12)+'" y="20">'+l2+'</text>'; lx+=12+l2.length*6+14; }
  if(useSnap){ lg+='<line x1="'+lx+'" y1="16.5" x2="'+(lx+14)+'" y2="16.5" stroke="var(--paper)" stroke-width="2"/><text x="'+(lx+18)+'" y="20">snap%</text>'; lx+=18+40; }
  lg+='<line x1="'+lx+'" y1="16.5" x2="'+(lx+14)+'" y2="16.5" stroke="var(--violet)" stroke-width="1.8" stroke-dasharray="4 3"/><text x="'+(lx+18)+'" y="20">fantasy pts</text></g>';
  s=lg+s;
  // footer facts — recent window vs prior window
  const recIdx=[],priIdx=[];
  for(let i=n-k;i<n;i++) recIdx.push(i);
  for(let i=Math.max(0,n-2*k);i<n-k;i++) priIdx.push(i);
  const A=idxs=>({opp:_avg(idxs.map(i=>part1[i]+part2[i])),sn:_avg(idxs.map(i=>snp[i])),pt:_avg(idxs.map(i=>pts[i]))});
  const R=A(recIdx),P=A(priIdx.length?priIdx:recIdx);
  const trend=(rec,pri)=>{
    const d = pri>0 ? Math.round((rec-pri)/pri*100) : (rec>0?100:0);
    const up=d>=3, dn=d<=-3;
    const col = up?'var(--emerald)':dn?'var(--coral)':'var(--fog)';
    const arr = up?'\u2191':dn?'\u2193':'\u2192';
    return '<span style="color:'+col+';font-weight:700">'+arr+' '+Math.abs(d)+'%</span>';
  };
  // Share is already a percentage — report it as percentage POINTS (21→26%), matching the
  // snaps idiom. A relative "% change of a %" would be doubly confusing to read.
  let facts='<b>Last '+k+' vs prior '+k+':</b> '
    + (shareOK ? 'target share '+Math.round(P.opp*100)+'\u2192'+Math.round(R.opp*100)+'%'
               : 'opportunity '+trend(R.opp,P.opp))
    + ' \u00b7 fantasy points '+trend(R.pt,P.pt);
  if(!isQB) facts+=' \u00b7 snaps '+Math.round(P.sn*100)+'\u2192'+Math.round(R.sn*100)+'%';
  const help='<div style="font-size:9.5px;color:var(--fog-2);margin-top:6px;line-height:1.5;border-top:1px solid var(--line);padding-top:5px">Read the gap: bars ('
    +(shareOK?'target share':'opportunity')+') and the violet points line moving together = production matches the role. Splitting apart — bars up while points sag, or points holding while bars shrink — flags one outrunning the other.'
    +(shareOK?' Share is team-relative, so it holds when the offense simply throws less and falls when he is being designed out.':'')+'</div>';
  // Magnitude belongs in the footer, not on the chart: this is real HTML at 10px, versus
  // SVG text that the 560→340px mobile downscale renders at ~5px. Mirrors the floor/median/
  // ceiling idiom Startability already uses. "Typical" is the median — kept as a NUMBER but
  // deliberately not drawn as a line, because a central-tendency line puts ~half the bars
  // underneath by construction and always reads as underperformance.
  let range='';
  if(n){
    // Token-snap games (a handful of snaps, zero opportunities — e.g. a rested starter's
    // Week 18 cameo) legitimately count as played under the LOCKED ≥1-snap DNP rule, but
    // "low 0" as a season headline misreads a healthy player. Quote low over weeks with
    // any opportunity and count the cameos in words. The rule itself is untouched.
    // Cameo = zero opportunities AND <10% snaps (the rested-starter pattern). A zero-target
    // game on real snaps is NOT a cameo — a fringe WR playing 50% of snaps without a look is
    // exactly the goose egg the low should show. Snap threshold is footer wording only; the
    // LOCKED ≥1-snap game-counting rule is untouched.
    const act=[],cam=[];
    for(let i=0;i<n;i++) ((totU[i]===0&&(snp[i]||0)<0.10)?cam:act).push(totU[i]);
    const tv=(act.length?act:cam).slice().sort((a,b)=>a-b), m2=tv.length;
    const md = m2%2 ? tv[(m2-1)/2] : (tv[m2/2-1]+tv[m2/2])/2;
    const fmtV = shareOK ? (v=>Math.round(v*100)+'%') : (v=>String(Math.round(v)));
    const noun = shareOK ? 'Target share' : (isQB ? 'Att + carries' : isRB ? 'Touches (car + tgt)' : 'Targets');
    range='<div style="font-size:10px;color:var(--fog-2);margin-top:2px">'+noun+' \u2014 low <b>'+fmtV(tv[0])
      +'</b> \u00b7 typical <b style="color:var(--paper)">'+fmtV(md)+'</b> \u00b7 high <b>'+fmtV(tv[m2-1])+'</b>'
      +(act.length&&cam.length?' \u00b7 excl. '+cam.length+' token-snap game'+(cam.length>1?'s':''):'')+'</div>';
  }
  return '<svg viewBox="0 0 '+W+' 180" width="100%" role="img"><title>usage trend</title>'+s+'</svg>'
    +'<div style="font-size:10px;color:var(--fog-2);margin-top:4px;line-height:1.6">'+facts+'</div>'+range+help;
}

// ── Mix view: volume vs efficiency (regression radar) ────────────────────────
// Splits each week's fantasy points into a repeatable FLOOR (yards + receptions,
// which follow volume) and the VOLATILE part (touchdowns, which regress hardest).
// A wall of floor-colored bars = sustainable production; a tall gold (TD) share
// means the scoring is leaning on finishes. Footer states TD-share + yards/touch
// as neutral facts (no verdict).
function gameLogMix(p,season){
  const pos=p.pos||p.p||'WR', isQB=pos==='QB', isRB=pos==='RB';
  const rows=((typeof GAMELOGS!=='undefined'&&GAMELOGS&&GAMELOGS[p.n])||[])
    .filter(g=>g.s===season&&!g.up&&!g.dnp).sort((a,b)=>(a.w||0)-(b.w||0));
  if(rows.length<2) return '<div style="font-size:11px;color:var(--fog);padding:8px 0">Not enough games this season to chart.</div>';
  const n=rows.length;
  const total=rows.map(g=>gamefp(g,pos,scoringFmt));
  const td=rows.map(g=>(g.pt||0)*4+(g.rt||0)*6+(g.ret||0)*6+(g.rtd||0)*6);
  const floor=rows.map((g,i)=>total[i]-td[i]);
  const yards=rows.map(g=> isQB?((g.py||0)+(g.ry||0)) : isRB?((g.ry||0)+(g.rey||0)) : (g.rey||0));
  const touches=rows.map(g=> isQB?((g.pa||0)+(g.car||0)) : isRB?((g.car||0)+(g.rec||0)) : (g.rec||0));
  const W=560,x0=20,x1=W-8,bxR=x1-8,top=30,base=150,plotH=base-top;
  const vMax=Math.max(1,Math.max.apply(null,total)*1.15);
  const slot=(bxR-x0)/n, bw=Math.min(22,slot*0.6), bx=i=>x0+slot*i+(slot-bw)/2, cx=i=>bx(i)+bw/2;
  const k = n>=8?4:Math.max(1,Math.floor(n/2));
  const bandX=(a,b)=>[x0+slot*a, x0+slot*(b+1)];
  let s='';
  if(n-k-1>=Math.max(0,n-2*k)){ const w=bandX(Math.max(0,n-2*k),n-k-1);
    s+='<rect x="'+w[0].toFixed(1)+'" y="'+top+'" width="'+(w[1]-w[0]).toFixed(1)+'" height="'+(base-top)+'" fill="var(--paper)" opacity="0.035"/>'; }
  { const w=bandX(n-k,n-1);
    s+='<rect x="'+w[0].toFixed(1)+'" y="'+top+'" width="'+(w[1]-w[0]).toFixed(1)+'" height="'+(base-top)+'" fill="var(--paper)" opacity="0.08"/>'; }
  rows.forEach((g,i)=>{
    const fl=Math.max(0,floor[i]), t=Math.max(0,td[i]);
    const hf=(fl/vMax)*plotH, ht=(t/vMax)*plotH;
    if(hf>0.4) s+='<rect x="'+bx(i).toFixed(1)+'" y="'+(base-hf).toFixed(1)+'" width="'+bw.toFixed(1)+'" height="'+hf.toFixed(1)+'" rx="1.5" fill="var(--sky)" opacity="0.85"/>';
    if(ht>0.4) s+='<rect x="'+bx(i).toFixed(1)+'" y="'+(base-hf-ht).toFixed(1)+'" width="'+bw.toFixed(1)+'" height="'+ht.toFixed(1)+'" rx="1.5" fill="var(--topaz)" opacity="0.92"/>';
    s+='<text x="'+cx(i).toFixed(1)+'" y="164" font-size="10" text-anchor="middle" fill="var(--fog-2)">'+g.w+'</text>';
  });
  // legend
  let lg='<g font-size="10" fill="var(--fog)">';
  lg+='<rect x="20" y="12" width="9" height="9" fill="var(--sky)" opacity="0.85"/><text x="32" y="20">floor (yds+rec)</text>';
  const lx=32+15*6+14;
  lg+='<rect x="'+lx.toFixed(0)+'" y="12" width="9" height="9" fill="var(--topaz)" opacity="0.92"/><text x="'+(lx+12).toFixed(0)+'" y="20">touchdowns</text></g>';
  // ── peak-game annotation: one haloed number above the biggest game calibrates every
  // other bar by eye (same design as Usage; an axis was tried there and failed because
  // of multi-scale layers). Value = that game's total fantasy points. Drawn after the
  // bars so nothing paints over it.
  { let im=0; for(let i=1;i<n;i++) if(total[i]>total[im]) im=i;
    const py_=Math.max(top+9, base-(Math.max(0,floor[im])+Math.max(0,td[im]))/vMax*plotH-5);
    s+='<text x="'+cx(im).toFixed(1)+'" y="'+py_.toFixed(1)+'" font-size="12" font-weight="700" text-anchor="middle" fill="var(--paper)" stroke="var(--ink)" stroke-width="3" paint-order="stroke" stroke-linejoin="round">'+total[im].toFixed(1)+'</text>'; }
  s=lg+s;
  // footer — neutral facts: TD share of points + yards/touch, recent vs prior
  const recIdx=[],priIdx=[];
  for(let i=n-k;i<n;i++) recIdx.push(i);
  for(let i=Math.max(0,n-2*k);i<n-k;i++) priIdx.push(i);
  const sm=(idxs,arr)=>idxs.reduce((a,i)=>a+arr[i],0);
  const tdShare=idxs=>{const tt=sm(idxs,total); return tt>0?Math.round(100*sm(idxs,td)/tt):0;};
  const ypt=idxs=>{const tc=sm(idxs,touches); return tc>0?(sm(idxs,yards)/tc):0;};
  const pri=priIdx.length?priIdx:recIdx;
  const tLabel = isQB?'yds/play' : isRB?'yds/touch' : 'yds/catch';
  const facts='<b>Last '+k+' vs prior '+k+':</b> TDs '+tdShare(pri)+'%\u2192'+tdShare(recIdx)+'% of points \u00b7 '+tLabel+' '+ypt(pri).toFixed(1)+'\u2192'+ypt(recIdx).toFixed(1);
  const help='<div style="font-size:9.5px;color:var(--fog-2);margin-top:6px;line-height:1.5;border-top:1px solid var(--line);padding-top:5px">Blue = points from yards and catches (repeatable, follows volume). Gold = points from touchdowns (regresses hardest). A tall gold share means the scoring is leaning on finishes rather than a floor.</div>';
  return '<svg viewBox="0 0 '+W+' 180" width="100%" role="img"><title>scoring mix</title>'+s+'</svg>'
    +'<div style="font-size:10px;color:var(--fog-2);margin-top:4px;line-height:1.6">'+facts+'</div>'+help;
}


// ── Trend view: form trajectory + play-caller inflection markers ─────────────
// Continuous trailing-34-game timeline (same window as the Start Profile): faint
// per-game dots + a bold 4-game form line, with markers at season boundaries and
// wherever the player's PLAY-CALLER changed — sourced from the hand-verified
// 2017–2026 playcallers.csv (week-level, incl. mid-season firings). Game rows
// carry tm (own team that week), so trades map to the right caller.
let PC_DB=null, _pcFetching=false, _trendFit=null;   // _trendFit: one re-draw per player once the chart can be measured
const PC_ALIAS={JAX:'JAC', LA:'LAR', OAK:'LV', SD:'LAC', STL:'LAR'};   // nflverse code -> CSV code
function ensurePlaycallers(){
  if(PC_DB||_pcFetching) return;
  _pcFetching=true;
  fetch('playcallers.csv').then(r=>r.ok?r.text():null).then(txt=>{
    _pcFetching=false;
    if(!txt){PC_DB={};return;}
    const db={};
    const lines=txt.split(/\r?\n/); // header: season,team,playcaller,week_start,week_end,...
    for(let i=1;i<lines.length;i++){
      if(!lines[i]) continue;
      const c=lines[i].split(',');           // notes (last col) may hold commas; we only read 0-4
      const key=c[1]+'|'+c[0];
      (db[key]=db[key]||[]).push({pc:c[2], w0:+c[3], w1:+c[4]});
    }
    PC_DB=db;
    if(_glView==='trend'&&_glPlayer&&typeof glSetView==='function') glSetView('trend');  // re-render once loaded
  }).catch(()=>{_pcFetching=false;PC_DB={};});
}
function pcAt(team,season,week){
  if(!PC_DB||!team) return null;
  const t=PC_ALIAS[team]||team;
  const spans=PC_DB[t+'|'+season];
  if(!spans) return null;
  for(const s of spans) if(week>=s.w0&&week<=s.w1) return s.pc;
  return spans[0]?spans[0].pc:null;
}
function _lastName(pc){ const p=(pc||'').split(' '); return p.length>1?p.slice(1).join(' '):pc; }
function gameLogTrend(p,season){
  const pos=p.pos||p.p||'WR';
  ensurePlaycallers();
  const src=((typeof GAMELOGS!=='undefined'&&GAMELOGS&&GAMELOGS[p.n])||[]).filter(g=>!g.up&&!g.dnp);
  const all=src.sort((a,b)=>(a.s-b.s)||((a.w||0)-(b.w||0)));   // full history — Trend always runs to the latest game (season pills don't apply)
  const rows=all.slice(-34);
  if(rows.length<5) return '<div style="font-size:11px;color:var(--fog);padding:8px 0">Not enough games for a trend line.</div>';
  const n=rows.length;
  const pts=rows.map(g=>gamefp(g,pos,scoringFmt));
  const roll=pts.map((_,i)=>{let s=0,c=0;for(let j=Math.max(0,i-3);j<=i;j++){s+=pts[j];c++;}return s/c;});
  // markers: season boundaries + play-caller changes (needs tm on rows)
  const callers=rows.map(g=>pcAt(g.tm,g.s,g.w));
  const marks=[];   // {i, kind:'season'|'oc', label}
  for(let i=1;i<n;i++){
    if(rows[i].s!==rows[i-1].s) marks.push({i, kind:'season', label:"'"+String(rows[i].s).slice(2)});
    if(callers[i]&&callers[i-1]&&callers[i]!==callers[i-1])
      marks.push({i, kind:'oc', label:_lastName(callers[i])});
  }
  /* SIZED TO ITS REAL WIDTH (4 Oct 2026). The chart used a fixed 560-wide drawing
     stretched to fit, so on a desktop every label grew ~1.6x and on a phone shrank
     to ~5px. Now one drawing unit = one screen pixel: text is always the same size
     and only the spacing between games stretches. The legend moved out of the
     drawing into ordinary text above it. Labels can no longer collide: play-caller
     names get the top row (a second row if two would overlap), season ticks sit on
     the bottom axis — so a new caller AND a new season in the same week no longer
     print on top of each other ("Kub'26iak", owner, 4 Oct). */
  const host=(typeof document!=='undefined')&&document.getElementById('dd-gamelog-body');
  const hw=host&&host.clientWidth?host.clientWidth:0;
  if(!hw&&typeof requestAnimationFrame!=='undefined'&&_trendFit!==p.n){
    _trendFit=p.n;                       // not on the page yet: draw once more after it is
    requestAnimationFrame(()=>{ if(_glView==='trend'&&_glPlayer===p) glSetView('trend'); });
  }
  const W=Math.max(300,Math.round(hw||560));
  const ocM=marks.filter(m=>m.kind==='oc'), FS=10.5, CH=7.2;        // label size; generous px-per-character for bold text, so estimates never run short
  const x0=6,bxR=W-6,step=(bxR-x0)/Math.max(1,n-1), cx=i=>x0+step*i;
  // play-caller labels: row 0, or row 1 if they would overlap the previous label on row 0
  const rowEnd=[-1e9,-1e9];
  for(const m of ocM){
    const w=m.label.length*CH, mx=cx(m.i)-step/2;
    const l=Math.min(Math.max(mx-w/2,x0),bxR-w);                    // keep inside the drawing
    m.lx=l+w/2; m.row=(l>rowEnd[0]+8)?0:((l>rowEnd[1]+8)?1:-1);
    if(m.row>=0) rowEnd[m.row]=l+w;
  }
  const rows2=ocM.some(m=>m.row===1);
  const top=ocM.length?(rows2?38:24):8, base=top+150, plotH=base-top-6;
  const vMax=Math.max(1,Math.max.apply(null,pts)*1.1), y=v=>base-(v/vMax)*plotH;
  let s='';
  for(const m of marks){
    const mx=(cx(m.i)-step/2).toFixed(1);
    if(m.kind==='season'){
      s+='<line x1="'+mx+'" y1="'+top+'" x2="'+mx+'" y2="'+base+'" stroke="var(--fog-2)" stroke-width="1" stroke-dasharray="3 3" opacity="0.7"/>';
      // season tick on the axis, unless it would sit on the first/last game label
      if(+mx>x0+56&&+mx<bxR-56) s+='<text x="'+mx+'" y="'+(base+15)+'" font-size="'+FS+'" text-anchor="middle" fill="var(--fog-2)">'+m.label+'</text>';
    }else{
      s+='<line x1="'+mx+'" y1="'+top+'" x2="'+mx+'" y2="'+base+'" stroke="var(--topaz)" stroke-width="1.5"/>';
      if(m.row>=0) s+='<text x="'+m.lx.toFixed(1)+'" y="'+(m.row?top-18:top-5)+'" font-size="'+FS+'" text-anchor="middle" fill="var(--topaz)" font-weight="700">'+m.label+'</text>';
    }
  }
  s+=pts.map((v,i)=>'<circle cx="'+cx(i).toFixed(1)+'" cy="'+y(v).toFixed(1)+'" r="2.6" fill="var(--paper)" opacity="0.35"/>').join('');
  s+='<polyline points="'+roll.map((v,i)=>cx(i).toFixed(1)+','+y(v).toFixed(1)).join(' ')+'" fill="none" stroke="var(--teal-br)" stroke-width="2.4" stroke-linejoin="round"/>';
  s+='<line x1="'+x0+'" y1="'+base+'" x2="'+bxR+'" y2="'+base+'" stroke="var(--line)"/>';
  s+='<text x="'+x0+'" y="'+(base+15)+'" font-size="'+FS+'" fill="var(--fog-2)">'+"'"+String(rows[0].s).slice(2)+' wk'+rows[0].w+'</text>';
  s+='<text x="'+bxR+'" y="'+(base+15)+'" font-size="'+FS+'" text-anchor="end" fill="var(--fog-2)">'+"'"+String(rows[n-1].s).slice(2)+' wk'+rows[n-1].w+'</text>';
  const H=base+22;
  // legend: ordinary text above the drawing, so it never scales or collides
  const lg='<div style="display:flex;flex-wrap:wrap;gap:4px 16px;font-size:10.5px;color:var(--fog);margin:2px 0 6px">'
    +'<span><span style="display:inline-block;width:14px;height:2.4px;background:var(--teal-br);vertical-align:middle;margin-right:6px"></span>4-game form</span>'
    +'<span><span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--paper);opacity:.35;vertical-align:middle;margin-right:6px"></span>Single game</span>'
    +'<span><span style="display:inline-block;width:2px;height:11px;background:var(--topaz);vertical-align:middle;margin-right:6px"></span>Play-caller change</span>'
    +'<span><span style="display:inline-block;width:0;height:11px;border-left:1px dashed var(--fog-2);vertical-align:middle;margin-right:6px"></span>New season</span></div>';
  // footer: before/after at most recent marker (OC preferred), neutral facts
  const avg=a=>a.length?a.reduce((x,y)=>x+y,0)/a.length:0;
  let facts;
  const ocs=marks.filter(m=>m.kind==='oc');
  const mk=ocs.length?ocs[ocs.length-1]:(marks.length?marks[marks.length-1]:null);
  if(mk){
    const b4=pts.slice(0,mk.i), af=pts.slice(mk.i);
    const who=mk.kind==='oc'?('play-caller change (<b>'+mk.label+'</b>)'):('season start (<b>'+mk.label+'</b>)');
    facts='Since the last '+who+': <b>'+avg(af).toFixed(1)+'</b> ppg over '+af.length+' games \u00b7 before it (in window): <b>'+avg(b4).toFixed(1)+'</b> ppg over '+b4.length;
  }else{
    facts='<b>'+avg(pts.slice(-8)).toFixed(1)+'</b> ppg last 8 \u00b7 <b>'+avg(pts.slice(0,Math.max(1,n-8))).toFixed(1)+'</b> ppg before';
  }
  let note='';
  if(PC_DB===null) note=' \u00b7 <span style="color:var(--fog-2)">loading play-caller history\u2026</span>';
  else if(!rows.some(g=>g.tm)) note=' \u00b7 <span style="color:var(--fog-2)">play-caller markers appear after the next data refresh (game rows need team tags)</span>';
  const help='<div style="font-size:9.5px;color:var(--fog-2);margin-top:6px;line-height:1.5;border-top:1px solid var(--line);padding-top:5px">Dots are single games; the bold line averages the <b>last 4</b>, so it deliberately trails the dots \u2014 one spike pulls it up only a quarter of the way. Dots show what happened; the line shows what\u2019s sustained. Gold lines mark a new play-caller (hand-verified 2017\u201326, mid-season changes included): if form shifted right at a gold line, circumstances changed \u2014 if it shifted with no line, the player did.</div>';
  return lg+'<svg viewBox="0 0 '+W+' '+H+'" width="100%" role="img" style="display:block;overflow:visible"><title>form trend</title>'+s+'</svg>'
    +'<div style="font-size:10px;color:var(--fog-2);margin-top:4px;line-height:1.6">'+facts+note+'</div>'+help;
}

const REC_PG={
  'A.J. Brown':4.59,
  'AJ Barner':3.06,
  'Aaron Jones':1.65,
  'Adonai Mitchell':1.94,
  'Alec Pierce':2.76,
  'Alvin Kamara':1.94,
  'Amon-Ra St. Brown':6.88,
  'Ashton Jeanty':3.24,
  'Audric Estime':0.92,
  'Ben Sinnott':0.65,
  'Bhayshul Tuten':0.59,
  'Bijan Robinson':4.65,
  'Blake Corum':0.47,
  'Braelon Allen':0.25,
  'Breece Hall':2.12,
  'Brenton Strange':2.71,
  'Brian Robinson':0.47,
  'Brian Thomas Jr.':3.0,
  'Brock Bowers':3.76,
  'Bucky Irving':1.76,
  'Cade Otton':3.47,
  'Calvin Ridley':1.7,
  'Cam Skattebo':1.41,
  'Cedric Tillman':1.31,
  'CeeDee Lamb':4.69,
  'Charlie Kolar':0.83,
  'Chase Brown':4.06,
  'Chigoziem Okonkwo':3.29,
  'Chimere Dike':2.82,
  'Chris Godwin':3.0,
  'Chris Olave':5.88,
  'Chris Rodriguez':0.18,
  'Christian Kirk':1.75,
  'Christian McCaffrey':6.0,
  'Christian Watson':2.69,
  'Chuba Hubbard':1.76,
  'Colby Parkinson':2.87,
  'Cole Kmet':1.76,
  'Colston Loveland':3.62,
  'Cooper Kupp':2.76,
  'Courtland Sutton':4.35,
  "D'Andre Swift":2.0,
  'D.J. Moore':2.94,
  'DK Metcalf':3.47,
  'Dallas Goedert':3.53,
  'Dalton Kincaid':3.9,
  'Dalton Schultz':4.82,
  'Darius Slayton':2.18,
  'Darnell Mooney':1.88,
  'Davante Adams':4.0,
  'David Montgomery':1.41,
  'David Njoku':1.94,
  'Dawson Knox':2.4,
  "De'Von Achane":3.94,
  'DeMario Douglas':2.38,
  'DeVonta Smith':4.53,
  'Deebo Samuel':4.24,
  'Derrick Henry':0.88,
  'Devaughn Vele':1.56,
  'Dontayvion Wicks':1.88,
  'Drake London':5.67,
  'Dylan Sampson':1.94,
  'Elic Ayomanor':2.41,
  'Elijah Higgins':1.76,
  'Emeka Egbuka':3.71,
  'Evan Engram':2.94,
  'Garrett Wilson':3.0,
  'George Holani':0.14,
  'George Kittle':4.75,
  'George Pickens':5.47,
  'Greg Dulcich':1.86,
  'Gunnar Helm':2.59,
  'Harold Fannin Jr.':4.5,
  'Hunter Henry':3.53,
  'Isaac TeSlaa':1.07,
  'Isaiah Likely':1.59,
  'Isiah Pacheco':1.12,
  'J.K. Dobbins':0.79,
  "Ja'Marr Chase":7.35,
  'JaTavion Sanders':1.71,
  'Jack Bech':1.54,
  'Jacory Croskey-Merritt':0.56,
  'Jahmyr Gibbs':4.53,
  'Jake Ferguson':4.82,
  'Jake Tonges':2.0,
  'Jakobi Meyers':4.41,
  'Jalen Coker':1.94,
  'Jalen McMillan':1.5,
  'Jalen Nailor':1.71,
  'Jalen Tolbert':1.06,
  'James Conner':0.57,
  'James Cook':1.94,
  'Jameson Williams':3.82,
  'Jauan Jennings':3.24,
  'Javonte Williams':2.06,
  'Jaxon Smith-Njigba':7.0,
  'Jayden Higgins':2.41,
  'Jayden Reed':1.9,
  'Jaylen Waddle':4.0,
  'Jaylen Warren':2.35,
  'Jaylen Wright':0.29,
  'Jaylin Noel':1.62,
  'Jerry Jeudy':2.94,
  'Jonathan Taylor':2.71,
  'Jonnu Smith':2.24,
  'Jordan Addison':2.47,
  'Jordan Mason':0.88,
  'Josh Downs':3.41,
  'Josh Jacobs':2.12,
  'Justin Jefferson':4.94,
  'Juwan Johnson':4.53,
  'Kareem Hunt':1.06,
  'Kayshon Boutte':2.2,
  'Keaton Mitchell':0.9,
  'Kenneth Gainwell':4.29,
  'Kenneth Walker III':1.82,
  'Keon Coleman':2.24,
  'Khalil Shakir':4.24,
  'Kimani Vidal':0.94,
  'Kyle Monangai':1.06,
  'Kyle Pitts':5.18,
  'Kyle Williams':0.83,
  'Kyren Williams':2.12,
  'Ladd McConkey':3.88,
  'Luther Burden':3.13,
  'Malik Washington':2.71,
  'Mark Andrews':3.0,
  'Marquise Brown':2.88,
  'Marvin Harrison Jr.':2.93,
  'Marvin Mims':2.64,
  'Mason Taylor':2.59,
  'Matthew Golden':1.81,
  'Michael Mayer':2.06,
  'Michael Pittman Jr.':4.71,
  'Michael Wilson':4.33,
  'Mike Evans':2.73,
  'Nico Collins':4.44,
  'Noah Fant':2.0,
  'Omarion Hampton':1.88,
  'Oronde Gadsden':2.88,
  'Parker Washington':3.41,
  'Pat Bryant':1.82,
  'Pat Freiermuth':2.41,
  'Puka Nacua':7.59,
  'Quentin Johnston':3.0,
  'Quinshon Judkins':1.53,
  'RJ Harvey':2.76,
  'Rachaad White':2.35,
  'Rashee Rice':3.53,
  'Rashid Shaheed':3.47,
  'Rashod Bateman':1.12,
  'Ray Davis':0.71,
  'Rhamondre Stevenson':2.29,
  'Ricky Pearsall':3.0,
  'Rico Dowdle':2.29,
  'Rome Odunze':2.59,
  'Romeo Doubs':3.24,
  'Sam LaPorta':3.08,
  'Saquon Barkley':2.18,
  'Sean Tucker':0.47,
  'Stefon Diggs':5.0,
  'T.J. Hockenson':3.0,
  'Tank Bigsby':0.21,
  'Tee Higgins':3.47,
  'Terrance Ferguson':0.65,
  'Terry McLaurin':2.71,
  'Tetairoa McMillan':4.12,
  'Tez Johnson':1.75,
  'Theo Johnson':2.65,
  'Tony Pollard':1.94,
  'Travis Etienne':2.12,
  'Travis Hunter':1.65,
  'Travis Kelce':4.47,
  'Tre Harris':1.76,
  'Tre Tucker':3.35,
  'TreVeyon Henderson':2.06,
  'Trey Benson':1.0,
  'Trey McBride':7.41,
  'Troy Franklin':3.82,
  'Tucker Kraft':4.0,
  'Tyjae Spears':2.65,
  'Tyler Allgeier':0.82,
  'Tyler Warren':4.47,
  'Tyrone Tracy':2.12,
  "Wan'Dale Robinson":5.41,
  'Woody Marks':1.41,
  'Xavier Legette':2.06,
  'Xavier Worthy':2.47,
  'Zach Charbonnet':1.18,
  'Zach Ertz':3.33,
  'Zay Flowers':5.06
};

// ── Positional Scarcity Tiers ─────────────────────────────────
// TEs are scarcer than WRs at equivalent PPG — reflected in mv bonus
const SCARCITY_TIERS={
  TE:{elite:14,starter:9,eliteBonus:0.12,starterBonus:0.06},
  WR:{elite:18,starter:14,eliteBonus:0.05,starterBonus:0.02},
  RB:{elite:18,starter:10,eliteBonus:0.05,starterBonus:0.02},
  QB:{elite:22,starter:18,eliteBonus:0.03,starterBonus:0.01},
};
function scarcityBonus(pos,proj){
  const t=SCARCITY_TIERS[pos];if(!t)return 0;
  if(proj>=t.elite)return t.eliteBonus;
  if(proj>=t.starter)return t.starterBonus;
  return 0;
}

// ── Team Competition Index ─────────────────────────────────────
// Forward-looking crowding penalty for target-heavy teams
// Built from sum of top receiver market values per team
const COMP_IDX={
  SF:0.04,ARI:0.03,DET:0.03,CIN:0.03,PHI:0.02,
  MIA:0.03,MIN:0.02,KC:0.02,LAR:0.02,
};
// Players exempt from own-team competition (they ARE the alpha)
const DRAFT_PICKS={
  // Baked 10 Oct 2026 (nflverse draft_picks: CAR, 2026 Rd3 #83). The nightly feed matched him to
  // the 1998 Chris Brazzell; the feed is fixed, and this entry also anchors the namesake guard.
  'Chris Brazzell II':{y:2026,r:3,p:83},
  'Aaron Rodgers':{y:2005,r:1,p:24},
  'Andrew Luck':{y:2012,r:1,p:1},
  'Andy Dalton':{y:2011,r:2,p:35},
  'Anthony Richardson':{y:2023,r:1,p:4},
  'Baker Mayfield':{y:2018,r:1,p:1},
  'Blake Bortles':{y:2014,r:1,p:3},
  'Bo Nix':{y:2024,r:1,p:12},
  'Brandon Weeden':{y:2012,r:1,p:22},
  'Brock Purdy':{y:2022,r:7,p:262},
  'Bryce Young':{y:2023,r:1,p:1},
  'C.J. Stroud':{y:2023,r:1,p:2},
  'Caleb Williams':{y:2024,r:1,p:1},
  'Cam Newton':{y:2011,r:1,p:1},
  'Cam Ward':{y:2025,r:1,p:1},
  'Colin Kaepernick':{y:2011,r:2,p:36},
  'Dak Prescott':{y:2016,r:4,p:135},
  'Daniel Jones':{y:2019,r:1,p:6},
  'Derek Carr':{y:2014,r:2,p:36},
  'Deshaun Watson':{y:2017,r:1,p:12},
  'Drake Maye':{y:2024,r:1,p:3},
  'Geno Smith':{y:2013,r:2,p:39},
  'J.J. McCarthy':{y:2024,r:1,p:10},
  'Jacoby Brissett':{y:2016,r:3,p:91},
  'Jalen Hurts':{y:2020,r:2,p:53},
  'Jameis Winston':{y:2015,r:1,p:1},
  'Jared Goff':{y:2016,r:1,p:1},
  'Jaxson Dart':{y:2025,r:1,p:25},
  'Jayden Daniels':{y:2024,r:1,p:2},
  'Jimmy Garoppolo':{y:2014,r:2,p:62},
  'Joe Burrow':{y:2020,r:1,p:1},
  'Joe Flacco':{y:2008,r:1,p:18},
  'Jordan Love':{y:2020,r:1,p:26},
  'Josh Allen':{y:2018,r:1,p:7},
  'Josh Freeman':{y:2009,r:1,p:17},
  'Justin Fields':{y:2021,r:1,p:11},
  'Justin Herbert':{y:2020,r:1,p:6},
  'Kenny Pickett':{y:2022,r:1,p:20},
  'Kirk Cousins':{y:2012,r:4,p:102},
  'Kyler Murray':{y:2019,r:1,p:1},
  'Lamar Jackson':{y:2018,r:1,p:32},
  'Mac Jones':{y:2021,r:1,p:15},
  'Malik Willis':{y:2022,r:3,p:86},
  'Marcus Mariota':{y:2015,r:1,p:2},
  'Mason Rudolph':{y:2018,r:3,p:76},
  'Matt Ryan':{y:2008,r:1,p:3},
  'Matthew Stafford':{y:2009,r:1,p:1},
  'Michael Penix Jr.':{y:2024,r:1,p:8},
  'Nick Foles':{y:2012,r:3,p:88},
  'Patrick Mahomes':{y:2017,r:1,p:10},
  'Robert Griffin':{y:2012,r:1,p:2},
  'Russell Wilson':{y:2012,r:3,p:75},
  'Ryan Tannehill':{y:2012,r:1,p:8},
  'Sam Bradford':{y:2010,r:1,p:1},
  'Sam Darnold':{y:2018,r:1,p:3},
  'Shedeur Sanders':{y:2025,r:5,p:144},
  'Trevor Lawrence':{y:2021,r:1,p:1},
  'Tua Tagovailoa':{y:2020,r:1,p:5},
  'Tyler Shough':{y:2025,r:2,p:40},
  'Tyrod Taylor':{y:2011,r:6,p:180},
  'A.J. Brown':{y:2019,r:2,p:51},
  'Adonai Mitchell':{y:2024,r:2,p:52},
  'Alec Pierce':{y:2022,r:2,p:53},
  'Amon-Ra St. Brown':{y:2021,r:4,p:112},
  'Brandon Aiyuk':{y:2020,r:1,p:25},
  'Brian Thomas Jr.':{y:2024,r:1,p:23},
  'Calvin Ridley':{y:2018,r:1,p:26},
  'Cedric Tillman':{y:2023,r:3,p:74},
  'CeeDee Lamb':{y:2020,r:1,p:17},
  'Chimere Dike':{y:2025,r:4,p:103},
  'Chris Godwin':{y:2017,r:3,p:84},
  'Chris Olave':{y:2022,r:1,p:11},
  'Christian Kirk':{y:2018,r:2,p:47},
  'Christian Watson':{y:2022,r:2,p:34},
  'Cooper Kupp':{y:2017,r:3,p:69},
  'Courtland Sutton':{y:2018,r:2,p:40},
  'D.J. Moore':{y:2018,r:1,p:24},
  'D.K. Metcalf':{y:2019,r:2,p:64},
  'DK Metcalf':{y:2019,r:2,p:64},
  'Darius Slayton':{y:2019,r:5,p:171},
  'Darnell Mooney':{y:2020,r:5,p:173},
  'Davante Adams':{y:2014,r:2,p:53},
  'DeMario Douglas':{y:2023,r:6,p:210},
  'DeVonta Smith':{y:2021,r:1,p:10},
  'Deebo Samuel':{y:2019,r:2,p:36},
  'Devaughn Vele':{y:2024,r:7,p:235},
  'Dontayvion Wicks':{y:2023,r:5,p:159},
  'Drake London':{y:2022,r:1,p:8},
  'Elic Ayomanor':{y:2025,r:4,p:136},
  'Emeka Egbuka':{y:2025,r:1,p:19},
  'Garrett Wilson':{y:2022,r:1,p:10},
  'George Pickens':{y:2022,r:2,p:52},
  'Isaac TeSlaa':{y:2025,r:3,p:70},
  "Ja'Marr Chase":{y:2021,r:1,p:5},
  'Jack Bech':{y:2025,r:2,p:58},
  'Jakobi Meyers':{y:2019,r:6,p:203},
  'Jalen Coker':{y:2024,r:6,p:204},
  'Jalen McMillan':{y:2024,r:3,p:84},
  'Jalen Nailor':{y:2022,r:6,p:191},
  'Jalen Tolbert':{y:2022,r:3,p:88},
  'Jameson Williams':{y:2022,r:1,p:12},
  'Jauan Jennings':{y:2020,r:7,p:217},
  'Jaxon Smith-Njigba':{y:2023,r:1,p:20},
  'Jayden Higgins':{y:2025,r:2,p:34},
  'Jayden Reed':{y:2023,r:2,p:50},
  'Jaylen Waddle':{y:2021,r:1,p:6},
  'Jaylin Noel':{y:2025,r:3,p:79},
  'Jerry Jeudy':{y:2020,r:1,p:15},
  'Jordan Addison':{y:2023,r:1,p:23},
  'Josh Downs':{y:2023,r:3,p:79},
  'Justin Jefferson':{y:2020,r:1,p:22},
  'K.J. Osborn':{y:2020,r:5,p:176},
  'Kayshon Boutte':{y:2023,r:6,p:187},
  'Keon Coleman':{y:2024,r:2,p:33},
  'Khalil Shakir':{y:2022,r:5,p:148},
  'Kyle Williams':{y:2025,r:3,p:69},
  'Ladd McConkey':{y:2024,r:2,p:34},
  'Luther Burden':{y:2025,r:2,p:39},
  'Malik Nabers':{y:2024,r:1,p:6},
  'Malik Washington':{y:2024,r:6,p:184},
  'Marquise Brown':{y:2019,r:1,p:25},
  'Marvin Harrison Jr.':{y:2024,r:1,p:4},
  'Marvin Mims':{y:2023,r:2,p:63},
  'Matthew Golden':{y:2025,r:1,p:23},
  'Michael Pittman Jr.':{y:2020,r:2,p:34},
  'Michael Wilson':{y:2023,r:3,p:94},
  'Mike Evans':{y:2014,r:1,p:7},
  'Nico Collins':{y:2021,r:3,p:89},
  'Parker Washington':{y:2023,r:6,p:185},
  'Pat Bryant':{y:2025,r:3,p:74},
  'Puka Nacua':{y:2023,r:5,p:177},
  'Quentin Johnston':{y:2023,r:1,p:21},
  'Rashee Rice':{y:2023,r:2,p:55},
  'Rashod Bateman':{y:2021,r:1,p:27},
  'Ricky Pearsall':{y:2024,r:1,p:31},
  'Rome Odunze':{y:2024,r:1,p:9},
  'Romeo Doubs':{y:2022,r:4,p:132},
  'Stefon Diggs':{y:2015,r:5,p:146},
  'Tank Dell':{y:2023,r:3,p:69},
  'Tee Higgins':{y:2020,r:2,p:33},
  'Terry McLaurin':{y:2019,r:3,p:76},
  'Tetairoa McMillan':{y:2025,r:1,p:8},
  'Tez Johnson':{y:2025,r:7,p:235},
  'Travis Hunter':{y:2025,r:1,p:2},
  'Tre Harris':{y:2025,r:2,p:55},
  'Tre Tucker':{y:2023,r:3,p:100},
  'Troy Franklin':{y:2024,r:4,p:102},
  'Tyreek Hill':{y:2016,r:5,p:165},
  "Wan'Dale Robinson":{y:2022,r:2,p:43},
  'Xavier Legette':{y:2024,r:1,p:32},
  'Xavier Worthy':{y:2024,r:1,p:28},
  'Zay Flowers':{y:2023,r:1,p:22},
  'Aaron Jones':{y:2017,r:5,p:182},
  'Alexander Mattison':{y:2019,r:3,p:102},
  'Alvin Kamara':{y:2017,r:3,p:67},
  'Ashton Jeanty':{y:2025,r:1,p:6},
  'Audric Estime':{y:2024,r:5,p:147},
  'Bhayshul Tuten':{y:2025,r:4,p:104},
  'Bijan Robinson':{y:2023,r:1,p:8},
  'Blake Corum':{y:2024,r:3,p:83},
  'Braelon Allen':{y:2024,r:4,p:132},
  'Breece Hall':{y:2022,r:2,p:36},
  'Brian Robinson':{y:2022,r:3,p:98},
  'Bucky Irving':{y:2024,r:4,p:125},
  'Cam Skattebo':{y:2025,r:4,p:105},
  'Chase Brown':{y:2023,r:5,p:163},
  'Chris Rodriguez':{y:2023,r:6,p:193},
  'Christian McCaffrey':{y:2017,r:1,p:8},
  'Chuba Hubbard':{y:2021,r:4,p:126},
  "D'Andre Swift":{y:2020,r:2,p:35},
  'David Montgomery':{y:2019,r:3,p:73},
  "De'Von Achane":{y:2023,r:3,p:84},
  'Derrick Henry':{y:2016,r:2,p:45},
  'Dylan Sampson':{y:2025,r:4,p:126},
  'Isaac Guerendo':{y:2024,r:4,p:129},
  'Isiah Pacheco':{y:2022,r:7,p:251},
  'J.K. Dobbins':{y:2020,r:2,p:55},
  'Jacory Croskey-Merritt':{y:2025,r:7,p:245},
  'Jahmyr Gibbs':{y:2023,r:1,p:12},
  'James Conner':{y:2017,r:3,p:105},
  'James Cook':{y:2022,r:2,p:63},
  'Javonte Williams':{y:2021,r:2,p:35},
  'Jaylen Warren':{y:2022,r:7,p:241},
  'Jaylen Wright':{y:2024,r:4,p:120},
  'Jonathan Taylor':{y:2020,r:2,p:41},
  'Jonathon Brooks':{y:2024,r:2,p:46},
  'Jordan Mason':{y:2022,r:6,p:214},
  'Josh Jacobs':{y:2019,r:1,p:24},
  'Kareem Hunt':{y:2017,r:3,p:86},
  'Keaton Mitchell':{y:2023,r:5,p:166},
  'Kenneth Gainwell':{y:2021,r:5,p:150},
  'Kenneth Walker III':{y:2022,r:2,p:41},
  'Kimani Vidal':{y:2024,r:6,p:181},
  'Kyle Monangai':{y:2025,r:7,p:233},
  'Kyren Williams':{y:2022,r:5,p:164},
  'MarShawn Lloyd':{y:2024,r:3,p:88},
  'Ollie Gordon':{y:2025,r:6,p:179},
  'Omarion Hampton':{y:2025,r:1,p:22},
  'Quinshon Judkins':{y:2025,r:2,p:36},
  'RJ Harvey':{y:2025,r:2,p:60},
  'Rachaad White':{y:2022,r:3,p:91},
  'Ray Davis':{y:2024,r:4,p:128},
  'Rhamondre Stevenson':{y:2021,r:4,p:120},
  'Rico Dowdle':{y:2019,r:6,p:182},
  'Saquon Barkley':{y:2018,r:1,p:2},
  'Sean Tucker':{y:2023,r:7,p:248},
  'Tank Bigsby':{y:2023,r:3,p:88},
  'Tony Pollard':{y:2019,r:4,p:128},
  'Travis Etienne':{y:2021,r:1,p:25},
  'TreVeyon Henderson':{y:2025,r:2,p:38},
  'Trey Benson':{y:2024,r:3,p:66},
  'Tyjae Spears':{y:2023,r:3,p:81},
  'Tyler Allgeier':{y:2022,r:5,p:151},
  'Tyrone Tracy':{y:2024,r:5,p:166},
  'Woody Marks':{y:2025,r:4,p:116},
  'Zach Charbonnet':{y:2023,r:2,p:52},
  'AJ Barner':{y:2024,r:4,p:121},
  'Ben Sinnott':{y:2024,r:2,p:53},
  'Brenton Strange':{y:2023,r:2,p:61},
  'Brock Bowers':{y:2024,r:1,p:13},
  'Cade Otton':{y:2022,r:4,p:106},
  'Charlie Kolar':{y:2022,r:4,p:128},
  'Chigoziem Okonkwo':{y:2022,r:4,p:143},
  'Colby Parkinson':{y:2020,r:4,p:133},
  'Cole Kmet':{y:2020,r:2,p:43},
  'Colston Loveland':{y:2025,r:1,p:10},
  'Dallas Goedert':{y:2018,r:2,p:49},
  'Dalton Kincaid':{y:2023,r:1,p:25},
  'Dalton Schultz':{y:2018,r:4,p:137},
  'David Njoku':{y:2017,r:1,p:29},
  'Dawson Knox':{y:2019,r:3,p:96},
  'Elijah Higgins':{y:2023,r:6,p:197},
  'Evan Engram':{y:2017,r:1,p:23},
  'George Kittle':{y:2017,r:5,p:146},
  'Greg Dulcich':{y:2022,r:3,p:80},
  'Gunnar Helm':{y:2025,r:4,p:120},
  'Harold Fannin Jr.':{y:2025,r:3,p:67},
  'Hunter Henry':{y:2016,r:2,p:35},
  'Isaiah Likely':{y:2022,r:4,p:139},
  'JaTavion Sanders':{y:2024,r:4,p:101},
  'Jake Ferguson':{y:2022,r:4,p:129},
  'Jonnu Smith':{y:2017,r:3,p:100},
  'Kyle Pitts':{y:2021,r:1,p:4},
  'Mark Andrews':{y:2018,r:3,p:86},
  'Mason Taylor':{y:2025,r:2,p:42},
  'Michael Mayer':{y:2023,r:2,p:35},
  'Noah Fant':{y:2019,r:1,p:20},
  'Oronde Gadsden':{y:2025,r:5,p:165},
  'Pat Freiermuth':{y:2021,r:2,p:55},
  'Sam LaPorta':{y:2023,r:2,p:34},
  'T.J. Hockenson':{y:2019,r:1,p:8},
  'Terrance Ferguson':{y:2025,r:2,p:46},
  'Theo Johnson':{y:2024,r:4,p:107},
  'Travis Kelce':{y:2013,r:3,p:63},
  'Trey McBride':{y:2022,r:2,p:55},
  'Tucker Kraft':{y:2023,r:3,p:78},
  'Tyler Warren':{y:2025,r:1,p:14},
  'Zach Ertz':{y:2013,r:2,p:35}
};

const COMP_EXEMPT=new Set([
  'Brock Bowers','Trey McBride','Ja\'Marr Chase','Justin Jefferson',
  'CeeDee Lamb','Jaxon Smith-Njigba','Christian McCaffrey','Bijan Robinson',
  'George Kittle','Travis Kelce','Malik Nabers','Ashton Jeanty',
]);

const SYS={
  ARI:{s:55,c:.35,oc:'LaFleur',ch:true},ATL:{s:48,c:.35,oc:'Rees',ch:true},
  BAL:{s:44,c:.20,oc:'Doyle',ch:true},BUF:{s:68,c:.75,oc:'Brady',ch:false},
  CAR:{s:62,c:.75,oc:'Idzik',ch:true},CHI:{s:71,c:.75,oc:'B.Johnson',ch:false},
  CIN:{s:78,c:1.0,oc:'Taylor',ch:false},CLE:{s:46,c:.20,oc:'Monken',ch:true},
  DAL:{s:65,c:.75,oc:'Schotty',ch:false},DEN:{s:72,c:1.0,oc:'Webb',ch:true},
  DET:{s:66,c:.75,oc:'Petzing',ch:true},GB:{s:67,c:1.0,oc:'LaFleur',ch:false},
  HOU:{s:64,c:.75,oc:'Caley',ch:false},IND:{s:63,c:1.0,oc:'Steichen',ch:false},
  JAC:{s:60,c:.75,oc:'Coen',ch:false},KC:{s:72,c:1.0,oc:'Reid',ch:false},
  LV:{s:51,c:.20,oc:'Kubiak',ch:true},LAC:{s:62,c:.20,oc:'McDaniel',ch:true},
  LAR:{s:74,c:1.0,oc:'McVay',ch:false},MIA:{s:40,c:.20,oc:'Slowik',ch:true},
  MIN:{s:72,c:1.0,oc:"O'Connell",ch:false},NE:{s:55,c:.75,oc:'McDaniels',ch:false},
  NO:{s:61,c:.75,oc:'Moore',ch:false},NYG:{s:50,c:.20,oc:'Nagy',ch:true},
  NYJ:{s:44,c:.20,oc:'Reich',ch:true},PHI:{s:49,c:.20,oc:'Mannion',ch:true},
  PIT:{s:55,c:.20,oc:'McCarthy',ch:true},SF:{s:73,c:1.0,oc:'Shanahan',ch:false},
  SEA:{s:55,c:.20,oc:'Fleury',ch:true},TB:{s:55,c:.20,oc:'Robinson',ch:true},
  TEN:{s:58,c:.35,oc:'Daboll',ch:true},WAS:{s:55,c:.35,oc:'Blough',ch:true},
  FA:{s:50,c:.20,oc:'Unknown',ch:true}
};
// Team-code aliases: every spelling DELTA might receive -> the code the SYS,
// QBQ and COMP_IDX tables are actually keyed by. An unaliased code does not
// error; gs() falls through to SYS.FA and the player is silently scored as a
// free agent. 'AZ' (the 2026 nflverse roster spelling of Arizona) did exactly
// that to ten Cardinals before it was caught.
const AL={NEP:'NE',NOS:'NO',LVR:'LV',GBP:'GB',TBB:'TB',KCC:'KC',SFO:'SF',OAK:'LV',RFA:'FA',LA:'LAR',JAX:'JAC',WSH:'WAS',ARZ:'ARI',AZ:'ARI'};
function gs(t){return SYS[AL[t]||t]||SYS.FA;}

// ============================================================
// YPRR DATA — WR and TE (weighted: 2025x3, 2024x2, 2023x1)
// Format: [weighted, y25, y24, y23]
// ============================================================
const YPRR_WR={
  "Puka Nacua":[3.21,3.73,3.59,2.58],"Jaxon Smith-Njigba":[2.47,3.61,1.81,1.32],
  "Ja'Marr Chase":[2.17,2.23,2.46,2.03],"Amon-Ra St. Brown":[2.32,2.48,2.3,2.63],
  "George Pickens":[2.13,2.37,2.06,2.1],"Chris Olave":[1.97,1.99,2.09,2.07],
  "Zay Flowers":[2.19,2.55,2.24,1.64],"Davante Adams":[1.93,1.96,2.04,1.97],
  "Nico Collins":[2.47,2.32,2.87,3.06],"Jameson Williams":[1.85,1.9,2.1,1.46],
  "Courtland Sutton":[1.68,1.61,1.84,1.65],"Tee Higgins":[1.75,1.63,2.05,1.64],
  "Michael Wilson":[1.43,1.61,1.1,1.34],"A.J. Brown":[2.36,2.13,3.01,2.53],
  "Tetairoa McMillan":[1.88,1.88,0,0],"Wan'Dale Robinson":[1.57,1.9,1.21,1.3],
  "Drake London":[2.16,2.36,2.32,1.85],"Emeka Egbuka":[1.77,1.77,0,0],
  "CeeDee Lamb":[2.3,2.4,2.27,2.77],"DeVonta Smith":[1.93,1.96,2.13,1.79],
  "Michael Pittman Jr.":[1.64,1.49,1.68,2.03],"Jaylen Waddle":[1.98,2.18,1.54,2.63],
  "Alec Pierce":[1.77,2.1,1.82,0.85],"Justin Jefferson":[2.18,1.92,2.51,2.91],
  "DK Metcalf":[1.89,1.99,1.81,2.05],"Parker Washington":[1.52,2.1,1.01,0.75],
  "Ladd McConkey":[1.75,1.42,2.39,0.0],"D.J. Moore":[1.51,1.25,1.44,2.3],
  "Troy Franklin":[1.38,1.48,1.0,0.0],"Jakobi Meyers":[1.64,1.61,1.76,1.52],
  "Romeo Doubs":[1.64,1.73,1.67,1.32],"Quentin Johnston":[1.51,1.51,1.77,0.88],
  "Khalil Shakir":[1.85,1.74,2.15,1.83],"Rome Odunze":[1.5,1.63,1.18,0.0],
  "Rashee Rice":[2.4,2.19,3.16,2.39],"Christian Watson":[2.18,2.55,2.26,1.54],
  "Brian Thomas Jr.":[1.81,1.54,2.45,0.0],"Jordan Addison":[1.52,1.36,1.73,1.5],
  "Luther Burden":[2.71,2.71,0,0],"Elic Ayomanor":[1.06,1.06,0,0],
  "Terry McLaurin":[1.98,2.26,1.98,1.56],"Tre Harris":[1.13,1.13,0,0],
  "Jayden Higgins":[1.48,1.48,0,0],"Matthew Golden":[1.25,1.39,1.00,0],
  "Ricky Pearsall":[1.62,1.84,1.31,0.0],"Mike Evans":[1.95,1.64,2.41,2.32],
  "Marvin Harrison Jr.":[1.61,1.61,1.63,0.0],"Garrett Wilson":[1.67,1.73,1.69,1.55],
  "Xavier Worthy":[1.36,1.26,1.24,0.0],"Keon Coleman":[1.5,1.29,1.71,0.0],
  "Josh Downs":[1.73,1.5,2.2,1.6],"Travis Hunter":[1.32,1.32,0,0],
  "Brandon Aiyuk":[2.0,0.0,1.75,3.02],"Jalen Coker":[1.54,1.37,1.72,0.0],
  "Malik Nabers":[1.95,2.07,2.16,0.0],"Deebo Samuel":[1.74,1.68,1.6,2.34],
  "Jauan Jennings":[1.64,1.41,2.26,1.15],"Stefon Diggs":[2.07,2.41,1.84,1.99],
  // Batch 1 WRs
  "Adonai Mitchell":[1.55,1.47,1.52,1.78],
  "Calvin Ridley":[1.79,1.89,1.87,1.56],
  "Cedric Tillman":[1.03,0.85,1.22,0.61],
  "Chris Godwin":[1.74,1.34,2.37,1.81],
  "Christian Kirk":[1.38,0.85,1.72,2.07],
  "Cooper Kupp":[1.66,1.39,1.99,1.85],
  "Darius Slayton":[1.26,1.23,1.08,1.38],
  "Darnell Mooney":[1.31,0.96,1.89,0.89],
  "DeMario Douglas":[1.74,2.02,1.4,1.71],
  "Devaughn Vele":[1.41,1.2,1.51,0.0],
  "Dontayvion Wicks":[1.52,1.38,1.42,2.04],
  "Jack Bech":[1.36,1.15,1.26,1.92],
  "Jalen Nailor":[1.07,1.06,1.08,0.55],
  "Jalen Tolbert":[1.02,0.77,1.1,0.97],
  "Jaylin Noel":[1.52,1.44,0.0,0.0],
  "Jerry Jeudy":[1.39,1.02,1.72,1.64],
  "Kayshon Boutte":[1.26,1.47,1.27,0.23],
  "Kyle Williams":[1.55,1.17,1.96,1.84],
  "Malik Washington":[1.18,0.87,0.87,2.26],
  "Marquise Brown":[1.81,1.49,2.68,1.24],
  "Pat Bryant":[1.64,1.22,1.52,3.18],
  "Rashod Bateman":[1.17,0.7,1.69,1.1],
  "Tank Dell":[1.69,0.0,1.49,2.2],
  "Tez Johnson":[1.48,1.07,1.89,1.77],
  "Tre Tucker":[1.19,1.19,0.84,1.48],
  // New batch WRs
  "Chimere Dike":[1.31,1.03,0.0,0.0],
  "Isaac TeSlaa":[1.21,0.81,0.0,0.0],
  "Jalen McMillan":[1.71,2.14,1.18,0.0],
  "Jayden Reed":[1.94,1.85,2.21,2.03],
  "K.J. Osborn":[1.15,0.0,0.95,0.97],
  "Marvin Mims":[1.68,1.17,2.57,1.53],
  "Rashid Shaheed":[1.65,1.41,2.04,1.66],
  "Xavier Legette":[1.19,0.9,1.19,0.0],
};

const YPRR_TE={
  "Trey McBride":[1.79,1.78,2.14,2.02],"Kyle Pitts":[1.53,1.72,1.33,1.42],
  "Travis Kelce":[1.56,1.46,1.44,1.92],"Tyler Warren":[1.61,1.61,0,0],
  "Jake Ferguson":[1.32,1.2,1.27,1.46],"Harold Fannin Jr.":[1.66,1.66,0,0],
  "Dallas Goedert":[1.63,1.37,2.21,1.36],"Juwan Johnson":[1.48,1.69,1.34,1.19],
  "Hunter Henry":[1.46,1.66,1.39,1.15],"Dalton Schultz":[1.39,1.56,1.06,1.46],
  "Brock Bowers":[1.72,1.7,2.03,0.0],"Colston Loveland":[1.88,1.88,0,0],
  "George Kittle":[2.15,2.15,2.62,2.23],"AJ Barner":[1.37,1.46,1.14,0.0],
  "Oronde Gadsden":[1.54,1.64,0.0,0.0],"Mark Andrews":[1.56,1.21,1.86,1.95],
  "Theo Johnson":[1.19,1.2,0.91,0.0],"Zach Ertz":[1.29,1.36,1.29,1.01],
  "Dalton Kincaid":[2.07,2.8,1.62,1.46],"Chigoziem Okonkwo":[1.43,1.37,1.27,1.31],
  "Cade Otton":[1.13,1.06,1.29,0.81],"Brenton Strange":[1.43,1.74,1.48,0.41],
  "Tucker Kraft":[1.82,2.3,1.6,1.22],"Pat Freiermuth":[1.47,1.56,1.46,1.12],
  "T.J. Hockenson":[1.38,1.05,1.52,1.89],"Sam LaPorta":[1.77,1.99,1.62,1.76],
  "Dawson Knox":[1.19,1.35,1.05,0.77],"Evan Engram":[1.42,1.29,1.51,1.56],
  "Gunnar Helm":[1.47,1.47,0,0],"Mason Taylor":[1.13,1.04,0.91,0.0],
  "Isaiah Likely":[1.42,1.31,1.54,1.46],"Cole Kmet":[1.17,1.03,0.91,1.7],
  "Ben Sinnott":[0.95,1.06,0.26,0.0],
  "Colby Parkinson":[1.36,1.62,0.99,1.11],
  "David Njoku":[1.31,1.07,1.34,1.69],
  "Greg Dulcich":[1.43,2.29,0.26,1.25],
  "JaTavion Sanders":[1.09,0.83,1.11,0.0],
  "Jake Tonges":[1.51,1.27,1.54,2.26],
  "Michael Mayer":[1.2,1.47,0.69,1.11],
  "Terrance Ferguson":[1.52,1.37,1.59,1.92],
  // New batch TEs
  "Charlie Kolar":[1.84,1.41,2.91,1.47],
  "Elijah Higgins":[1.19,1.0,1.01,1.81],
  "Jonnu Smith":[1.33,0.77,1.96,1.56],
  "Noah Fant":[1.34,1.33,1.3,1.29],
};


  // RB Snap% [weighted, s25, s24, s23]
const RB_SNAP={
  "Bijan Robinson":[74.5,78.5,75.3,68.2],"Jahmyr Gibbs":[63.5,67.1,55.8,50.6],
  "De'Von Achane":[61.2,70.9,61.9,35.6],"James Cook":[51.7,56.4,44.6,54.5],
  "Jonathan Taylor":[70.3,82.4,65.0,44.3],"Derrick Henry":[55.3,54.7,57.2,53.1],
  "Kyren Williams":[73.3,68.0,81.5,75.9],"Saquon Barkley":[71.9,73.5,69.2,64.9],
  "Christian McCaffrey":[73.6,83.0,56.4,76.2],"Chase Brown":[57.8,66.4,60.4,11.2],
  "Travis Etienne":[57.5,60.1,47.8,73.4],"Javonte Williams":[59.0,68.0,52.1,46.0],
  "Josh Jacobs":[56.6,52.7,62.5,57.4],"Ashton Jeanty":[77.6,77.6,0,0],
  "D'Andre Swift":[56.9,53.8,66.1,54.9],"Jaylen Warren":[44.8,47.4,39.6,48.4],
  "Rico Dowdle":[46.6,55.7,54.3,20.9],"Breece Hall":[62.9,61.1,67.5,60.6],
  "TreVeyon Henderson":[45.8,45.8,0,0],"Kenneth Gainwell":[40.1,50.1,26.0,38.5],
  "RJ Harvey":[42.2,42.2,0,0],"Kenneth Walker III":[62.0,62.0,47.2,47.8],
  "Zach Charbonnet":[47.8,46.0,51.6,45.5],"Tony Pollard":[64.6,62.2,64.1,70.6],
  "Rhamondre Stevenson":[51.3,48.7,54.8,51.6],"Quinshon Judkins":[46.2,46.2,0,0],
  "David Montgomery":[36.6,37.1,34.0,38.5],"Woody Marks":[49.2,49.2,0,0],
  "Kyle Monangai":[41.4,41.4,0,0],"Kareem Hunt":[47.7,47.5,49.9,0],
  "Jacory Croskey-Merritt":[38.5,38.5,0,0],"Bucky Irving":[40.2,37.1,45.2,0],
  "Rachaad White":[59.5,50.6,51.8,78.1],"Jordan Mason":[37.2,41.3,0,9.3],
  "Omarion Hampton":[56.7,56.7,0,0],"Blake Corum":[22.7,29.3,10.9,0],
  "Cam Skattebo":[54.1,54.1,0,0],"J.K. Dobbins":[55.6,50.8,63.2,46.9],
  "Chuba Hubbard":[56.0,40.7,77.4,59.0],"Bhayshul Tuten":[45.0,55.0,34.0,0],
  "Aaron Jones":[47.7,50.1,62.7,32.3],"Tyjae Spears":[40.6,46.0,29.3,53.1],
  "Alvin Kamara":[47.0,40.7,58.9,58.4],"Ollie Gordon":[22.7,22.7,0,0],
  "Isaac Guerendo":[14.0,0,21.0,0],"Trey Benson":[36.6,48.4,13.3,0],
  "Dylan Sampson":[23.0,23.0,0,0],"Jaylen Wright":[13.3,12.9,15.0,0],
  "Braelon Allen":[25.0,23.9,26.5,0],"James Conner":[54.6,49.7,60.0,61.8],
  "Isiah Pacheco":[40.2,38.1,43.3,50.3],
  // Batch 1 RBs
  "Tyrone Tracy":[55.7,54.7,57.4,0],
  "Brian Robinson":[43.2,35.0,51.6,49.4],
  "George Holani":[12.1,15.2,4.0,0],
  "Keaton Mitchell":[18.6,17.5,13.5,28.0],
  "Chris Rodriguez":[22.4,31.2,15.1,15.3],
  "Sean Tucker":[15.4,17.9,13.1,12.5],
  "Ray Davis":[20.6,14.3,24.4,32.2],
  "Tyler Allgeier":[27.4,0,24.9,32.2],
  // New batch RBs
  "Alexander Mattison":[51.0,0,49.1,54.8],
  "Jonathon Brooks":[11.0,0,11.0,0],
  "Kimani Vidal":[45.4,57.2,27.7,0],
  "MarShawn Lloyd":[14.0,0,14.0,0],
  "Tank Bigsby":[23.6,17.2,38.5,13.1],
  "Audric Estime":[34.1,45.8,16.6,0],
};


// YPRR → role multiplier for WR/TE
// League average YPRR ~1.5 for WR, ~1.4 for TE
// Map to multiplier: elite (2.5+)→1.20, good (2.0-2.5)→1.10, avg (1.5-2.0)→1.00, below (1.0-1.5)→0.90, poor (<1.0)→0.80
function yprrMult(yprr, pos) {
  if (!yprr || yprr === 0) return 0.88; // no data = slight penalty
  const avg = pos === 'TE' ? 1.45 : 1.60;
  const ratio = yprr / avg;
  // Smooth multiplier centered on average
  const m = Math.max(0.78, Math.min(1.22, 0.88 + ratio * 0.12));
  return Math.round(m * 1000) / 1000;
}

// RB snap% → role multiplier
// 80%+ = true bellcow (1.15), 65%+ = featured (1.08), 50%+ = solid starter (1.00),
// 40%+ = committee (0.90), 30%+ = backup (0.80), <30% = depth (0.70)
function snapMult(snap) {
  if (!snap || snap === 0) return 0.82;
  if (snap >= 80) return 1.15;
  if (snap >= 65) return 1.08;
  if (snap >= 50) return 1.00;
  if (snap >= 40) return 0.90;
  if (snap >= 30) return 0.80;
  return 0.70;
}

function getRoleData(name, pos) {
  if (pos === 'RB') {
    const d = RB_SNAP[name];
    if (d) return { mult: snapMult(d[0]), label: d[1].toFixed(0)+'%', raw: d[0] };
    return { mult: 0.82, label: '—', raw: 0 };
  }
  if (pos === 'WR') {
    const d = YPRR_WR[name];
    if (d) return { mult: yprrMult(d[0], 'WR'), label: d[0].toFixed(2)+' YPRR', raw: d[0] };
    return { mult: 0.88, label: '—', raw: 0 };
  }
  if (pos === 'TE') {
    const d = YPRR_TE[name];
    if (d) return { mult: yprrMult(d[0], 'TE'), label: d[0].toFixed(2)+' YPRR', raw: d[0] };
    return { mult: 0.88, label: '—', raw: 0 };
  }
  return { mult: 1.0, label: '—', raw: 0 };
}

// RB Vol+YAC floor
const RBV={
  'Bijan Robinson':{r:287,y:1118},"De'Von Achane":{r:238,y:896},
  'James Cook':{r:309,y:1084},'Jonathan Taylor':{r:323,y:1222},
  'Derrick Henry':{r:307,y:1107},'Kyren Williams':{r:259,y:845},
  'Saquon Barkley':{r:280,y:812},'Christian McCaffrey':{r:311,y:874},
  'Chase Brown':{r:232,y:698},'Breece Hall':{r:243,y:741},
  'Ashton Jeanty':{r:266,y:922},'Kenneth Walker III':{r:221,y:677},
  'Travis Etienne':{r:260,y:835},'Javonte Williams':{r:252,y:928},
  'Tony Pollard':{r:242,y:770},'Rico Dowdle':{r:236,y:765},
  'Josh Jacobs':{r:234,y:766},'Zach Charbonnet':{r:184,y:561},
  'Bucky Irving':{r:173,y:488},"D'Andre Swift":{r:223,y:678},
  'Jaylen Warren':{r:211,y:706},'Quinshon Judkins':{r:230,y:687},
  'Woody Marks':{r:196,y:527},'Jahmyr Gibbs':{r:243,y:751},
  'Blake Corum':{r:145,y:426},'J.K. Dobbins':{r:153,y:503},
  'TreVeyon Henderson':{r:180,y:554},'Kyle Monangai':{r:169,y:517},
  'Jacory Croskey-Merritt':{r:175,y:646},'David Montgomery':{r:158,y:527},
  'Jordan Mason':{r:159,y:560},'RJ Harvey':{r:146,y:397},
};

function getFloor(n,pos){
  if(pos==='RB'){
    const v=RBV[n];if(!v)return null;
    const ypc=v.r>0?v.y/v.r:0;
    if(v.r>=140&&ypc>=3.0)return{f:1.0,r:'vol+YAC neutral'};
    if(v.r>=140)return{f:0.92,r:'vol floor'};
    return null;
  }
  const d=pos==='WR'?YPRR_WR[n]:pos==='TE'?YPRR_TE[n]:null;
  if(d&&d[1]>0){const tgt=(d[1]/1.5)*80;if(tgt>=80)return{f:0.92,r:'target vol floor'};}
  if(pos==='QB'){const QPV={'Josh Allen':612,'Lamar Jackson':405,'Joe Burrow':290,'Brock Purdy':328,'Jalen Hurts':591,'Patrick Mahomes':600,'Caleb Williams':669,'Drake Maye':642,'Justin Herbert':649,'Bo Nix':717,'Trevor Lawrence':683,'Jared Goff':635,'Dak Prescott':684,'Jordan Love':507,'Baker Mayfield':634};const p=QPV[n]||0;if(p>=300)return{f:0.88,r:'plays floor'};}
  return null;
}

const EPA={
  'Josh Allen':{e25:.17,e24:.31,e23:.18,e22:.18,ef25:.17},'Lamar Jackson':{e25:.07,e24:.28,e23:.09,e22:.09,ef25:.07},
  'Brock Purdy':{e25:.23,e24:.18,e23:.29,e22:.13,ef25:.23},'Patrick Mahomes':{e25:.16,e24:.14,e23:.05,e22:.27,ef25:.16},
  'Jalen Hurts':{e25:.07,e24:.15,e23:.09,e22:.13,ef25:.07},'Joe Burrow':{e25:.11,e24:.16,e23:-.01,e22:.12,ef25:.11},
  'Drake Maye':{e25:.26,e24:-.03,e23:0,e22:0,ef25:.26},'Jared Goff':{e25:.14,e24:.25,e23:.07,e22:.12,ef25:.14},
  'Dak Prescott':{e25:.14,e24:-.04,e23:.18,e22:.09,ef25:.14},'Justin Herbert':{e25:.03,e24:.11,e23:.03,e22:.02,ef25:.03},
  'Bo Nix':{e25:.09,e24:.06,e23:0,e22:0,ef25:.09},'Caleb Williams':{e25:.07,e24:-.06,e23:0,e22:0,ef25:.07},
  'Jayden Daniels':{e25:-.01,e24:.16,e23:0,e22:0,ef25:-.01},'Trevor Lawrence':{e25:.09,e24:.01,e23:-.03,e22:.12,ef25:.09},
  'Jordan Love':{e25:.24,e24:.12,e23:.11,e22:.16,ef25:.24},'Matthew Stafford':{e25:.17,e24:.06,e23:.09,e22:-.09,ef25:.17},
  'Baker Mayfield':{e25:.05,e24:.17,e23:.04,e22:-.16,ef25:.05},'Kyler Murray':{e25:.05,e24:.10,e23:-.02,e22:-.01,ef25:.05},
  'Sam Darnold':{e25:.09,e24:.05,e23:-.12,e22:.10,ef25:.09},'C.J. Stroud':{e25:.11,e24:-.03,e23:.11,e22:0,ef25:.11},
  'Cam Ward':{e25:-.17,e24:0,e23:0,e22:0,ef25:-.17},'Jaxson Dart':{e25:.06,e24:0,e23:0,e22:0,ef25:.06},
  'Shedeur Sanders':{e25:-.23,e24:0,e23:0,e22:0,ef25:-.23},'Bryce Young':{e25:-.03,e24:-.03,e23:-.23,e22:0,ef25:-.03},
  'Geno Smith':{e25:-.14,e24:.01,e23:.05,e22:.01,ef25:-.14},'J.J. McCarthy':{e25:-.15,e24:0,e23:0,e22:0,ef25:-.15},
  'Michael Penix Jr.':{e25:.02,e24:.13,e23:0,e22:0,ef25:.02},'Daniel Jones':{e25:.17,e24:-.06,e23:-.26,e22:.07,ef25:.17},
  'Tua Tagovailoa':{e25:.00,e24:.19,e23:.11,e22:.18,ef25:.00},'Tyler Shough':{e25:-.02,e24:0,e23:0,e22:0,ef25:-.02},
  "Ja'Marr Chase":{e25:2.23,e24:2.46,e23:2.03,e22:2.03,ef25:2.23},'Jaxon Smith-Njigba':{e25:3.67,e24:1.81,e23:1.32,e22:0,ef25:3.67},
  'Puka Nacua':{e25:3.73,e24:3.55,e23:2.56,e22:0,ef25:3.73},'Amon-Ra St. Brown':{e25:2.48,e24:2.30,e23:2.63,e22:2.41,ef25:2.48},
  'Justin Jefferson':{e25:1.92,e24:2.50,e23:2.92,e22:2.63,ef25:1.92},"Ja'Marr Chase":{e25:2.17,e24:2.50,e23:2.40,e22:2.20,ef25:2.17},'CeeDee Lamb':{e25:2.40,e24:2.27,e23:2.79,e22:2.41,ef25:2.40},
  'Malik Nabers':{e25:2.07,e24:2.15,e23:0,e22:0,ef25:2.07},'Drake London':{e25:2.36,e24:2.30,e23:1.86,e22:2.06,ef25:2.36},
  'George Pickens':{e25:2.37,e24:2.06,e23:2.10,e22:1.38,ef25:2.37},'Tetairoa McMillan':{e25:1.88,e24:0,e23:0,e22:0,ef25:1.88},
  'Emeka Egbuka':{e25:1.77,e24:0,e23:0,e22:0,ef25:1.77},'Garrett Wilson':{e25:1.78,e24:1.68,e23:1.55,e22:1.87,ef25:1.78},
  'Nico Collins':{e25:2.39,e24:2.87,e23:3.07,e22:1.67,ef25:2.39},'Chris Olave':{e25:1.99,e24:2.09,e23:2.06,e22:2.40,ef25:1.99},
  'Rome Odunze':{e25:1.63,e24:1.16,e23:0,e22:0,ef25:1.63},'Ladd McConkey':{e25:1.42,e24:2.37,e23:0,e22:0,ef25:1.42},
  'Marvin Harrison Jr.':{e25:1.61,e24:1.62,e23:0,e22:0,ef25:1.61},'Brian Thomas Jr.':{e25:1.54,e24:2.41,e23:0,e22:0,ef25:1.54},
  'Tee Higgins':{e25:1.63,e24:2.04,e23:1.64,e22:1.92,ef25:1.63},'Jaylen Waddle':{e25:2.28,e24:1.51,e23:2.63,e22:2.58,ef25:2.28},
  'DeVonta Smith':{e25:1.96,e24:2.13,e23:1.79,e22:2.00,ef25:1.96},'A.J. Brown':{e25:2.13,e24:3.01,e23:2.50,e22:2.60,ef25:2.13},
  'Zay Flowers':{e25:2.55,e24:2.24,e23:1.64,e22:0,ef25:2.55},'Rashee Rice':{e25:2.19,e24:3.16,e23:2.39,e22:0,ef25:2.19},
  'Jameson Williams':{e25:1.90,e24:2.10,e23:1.46,e22:1.11,ef25:1.90},'DK Metcalf':{e25:2.06,e24:1.80,e23:2.04,e22:1.81,ef25:2.06},
  'Luther Burden':{e25:2.71,e24:0,e23:0,e22:0,ef25:2.71},'Courtland Sutton':{e25:1.67,e24:1.84,e23:1.64,e22:1.55,ef25:1.67},
  'Terry McLaurin':{e25:2.26,e24:1.97,e23:1.56,e22:2.03,ef25:2.26},'Xavier Worthy':{e25:1.33,e24:1.24,e23:0,e22:0,ef25:1.33},
  'Christian Watson':{e25:2.55,e24:2.25,e23:1.53,e22:2.25,ef25:2.55},'Quentin Johnston':{e25:1.61,e24:1.76,e23:.88,e22:0,ef25:1.61},
  "D.J. Moore":{e25:1.25,e24:1.43,e23:2.31,e22:1.75,ef25:1.25},'Khalil Shakir':{e25:1.74,e24:2.14,e23:1.83,e22:1.15,ef25:1.74},
  'Ricky Pearsall':{e25:1.90,e24:1.31,e23:0,e22:0,ef25:1.90},'Romeo Doubs':{e25:1.82,e24:1.66,e23:1.32,e22:1.38,ef25:1.82},
  'Parker Washington':{e25:2.10,e24:1.01,e23:.74,e22:0,ef25:2.10},'Jayden Higgins':{e25:1.48,e24:0,e23:0,e22:0,ef25:1.48},
  'Michael Pittman Jr.':{e25:1.49,e24:1.67,e23:2.02,e22:1.44,ef25:1.49},'Davante Adams':{e25:1.96,e24:2.02,e23:1.97,e22:2.45,ef25:1.96},
  "Wan'Dale Robinson":{e25:1.90,e24:1.21,e23:1.30,e22:1.80,ef25:1.90},'Jordan Addison':{e25:1.42,e24:1.73,e23:1.50,e22:0,ef25:1.42},
  'Alec Pierce':{e25:2.19,e24:1.81,e23:.84,e22:1.24,ef25:2.19},'Josh Downs':{e25:1.50,e24:2.19,e23:1.60,e22:0,ef25:1.50},
  'Matthew Golden':{e25:1.39,e24:0,e23:0,e22:0,ef25:1.39},'Tre Harris':{e25:1.13,e24:0,e23:0,e22:0,ef25:1.13},
  'Mike Evans':{e25:1.64,e24:2.41,e23:2.31,e22:1.78,ef25:1.64},'Jakobi Meyers':{e25:1.61,e24:1.75,e23:1.52,e22:1.88,ef25:1.61},
  'Travis Hunter':{e25:1.32,e24:0,e23:0,e22:0,ef25:1.32},'Brandon Aiyuk':{e25:0,e24:1.75,e23:3.02,e22:1.90,ef25:0},
  'Elic Ayomanor':{e25:1.06,e24:0,e23:0,e22:0,ef25:1.06},'Jalen Coker':{e25:1.37,e24:1.72,e23:0,e22:0,ef25:1.37},
  'Bijan Robinson':{e25:-.05,e24:.06,e23:-.12,e22:0,ef25:5.15},'Jahmyr Gibbs':{e25:-.01,e24:.14,e23:-.03,e22:0,ef25:5.03},
  "De'Von Achane":{e25:.06,e24:-.06,e23:.32,e22:0,ef25:5.67},'James Cook':{e25:.02,e24:.05,e23:-.03,e22:.07,ef25:5.25},
  'Jonathan Taylor':{e25:.05,e24:-.07,e23:-.06,e22:-.15,ef25:4.91},'Derrick Henry':{e25:.03,e24:.12,e23:-.01,e22:-.06,ef25:5.20},
  'Kyren Williams':{e25:.02,e24:-.07,e23:.10,e22:-.12,ef25:4.83},'Saquon Barkley':{e25:-.09,e24:.10,e23:-.20,e22:-.05,ef25:4.07},
  'Christian McCaffrey':{e25:-.07,e24:-.06,e23:.05,e22:.02,ef25:3.86},'Chase Brown':{e25:-.01,e24:-.03,e23:-.20,e22:0,ef25:4.39},
  'Breece Hall':{e25:-.09,e24:-.11,e23:-.10,e22:.17,ef25:4.38},'Ashton Jeanty':{e25:-.24,e24:0,e23:0,e22:0,ef25:3.67},
  'Kenneth Walker III':{e25:-.06,e24:-.08,e23:-.04,e22:-.06,ef25:4.65},'Travis Etienne':{e25:-.07,e24:-.18,e23:-.13,e22:-.04,ef25:4.26},
  'TreVeyon Henderson':{e25:.05,e24:0,e23:0,e22:0,ef25:5.06},'Josh Jacobs':{e25:-.06,e24:-.06,e23:-.19,e22:.00,ef25:3.97},
  'Zach Charbonnet':{e25:-.01,e24:-.08,e23:-.07,e22:0,ef25:3.97},'Tony Pollard':{e25:-.09,e24:-.10,e23:-.07,e22:.02,ef25:4.47},
  'Rico Dowdle':{e25:-.01,e24:-.04,e23:-.06,e22:0,ef25:4.56},'Bucky Irving':{e25:-.21,e24:.10,e23:0,e22:0,ef25:3.40},
  'Jaylen Warren':{e25:.00,e24:-.12,e23:-.03,e22:.11,ef25:4.54},'Omarion Hampton':{e25:-.01,e24:0,e23:0,e22:0,ef25:4.40},
  'RJ Harvey':{e25:-.15,e24:0,e23:0,e22:0,ef25:3.70},'Jacory Croskey-Merritt':{e25:-.03,e24:0,e23:0,e22:0,ef25:4.60},
  'Kyle Monangai':{e25:.01,e24:0,e23:0,e22:0,ef25:4.63},'Bhayshul Tuten':{e25:-.11,e24:0,e23:0,e22:0,ef25:3.70},
  'Cam Skattebo':{e25:-.13,e24:0,e23:0,e22:0,ef25:4.06},'Quinshon Judkins':{e25:-.11,e24:0,e23:0,e22:0,ef25:3.60},
  'Ollie Gordon':{e25:-.14,e24:0,e23:0,e22:0,ef25:2.84},"D'Andre Swift":{e25:.07,e24:-.15,e23:.01,e22:.06,ef25:4.87},
  'Rhamondre Stevenson':{e25:-.15,e24:-.18,e23:-.08,e22:-.05,ef25:4.64},'J.K. Dobbins':{e25:.03,e24:.02,e23:-.23,e22:.10,ef25:5.05},
  'Aaron Jones':{e25:-.02,e24:-.05,e23:.02,e22:.06,ef25:4.15},'Chuba Hubbard':{e25:-.11,e24:.04,e23:-.09,e22:.02,ef25:3.81},
  'Isaac Guerendo':{e25:0,e24:.06,e23:0,e22:0,ef25:0},'Dylan Sampson':{e25:-.26,e24:0,e23:0,e22:0,ef25:2.69},
  'Javonte Williams':{e25:.05,e24:-.17,e23:-.17,e22:-.13,ef25:4.77},'Blake Corum':{e25:.11,e24:-.17,e23:0,e22:0,ef25:5.14},
  'Woody Marks':{e25:-.15,e24:0,e23:0,e22:0,ef25:3.59},'Kenneth Gainwell':{e25:-.01,e24:-.15,e23:-.15,e22:.15,ef25:4.71},
  'Jordan Mason':{e25:-.04,e24:-.04,e23:.14,e22:.07,ef25:4.77},'Alvin Kamara':{e25:-.22,e24:-.08,e23:-.02,e22:-.18,ef25:3.60},
  'David Montgomery':{e25:.00,e24:-.04,e23:.05,e22:-.08,ef25:4.53},'Tyjae Spears':{e25:-.05,e24:-.06,e23:-.01,e22:0,ef25:3.93},
  'Kimani Vidal':{e25:-.09,e24:-.20,e23:0,e22:0,ef25:4.15},'Brock Bowers':{e25:1.70,e24:2.01,e23:0,e22:0,ef25:1.70},
  'Trey McBride':{e25:1.78,e24:2.13,e23:2.00,e22:0.84,ef25:1.78},'Travis Kelce':{e25:1.46,e24:1.43,e23:1.91,e22:2.23,ef25:1.51},
  'George Kittle':{e25:2.15,e24:2.62,e23:2.24,e22:1.73,ef25:2.24},'Sam LaPorta':{e25:1.99,e24:1.61,e23:1.76,e22:0,ef25:1.99},
  'Kyle Pitts':{e25:1.72,e24:1.33,e23:1.42,e22:1.66,ef25:1.72},'Colston Loveland':{e25:1.88,e24:0,e23:0,e22:0,ef25:1.88},
  'Tyler Warren':{e25:1.61,e24:0,e23:0,e22:0,ef25:1.61},'Tucker Kraft':{e25:2.3,e24:1.59,e23:1.20,e22:0,ef25:2.40},
  'Harold Fannin Jr.':{e25:1.66,e24:0,e23:0,e22:0,ef25:1.66},'Oronde Gadsden':{e25:1.64,e24:0,e23:0,e22:0,ef25:1.69},
  'Mark Andrews':{e25:1.21,e24:1.86,e23:1.94,e22:1.96,ef25:1.21},'T.J. Hockenson':{e25:1.05,e24:1.52,e23:1.89,e22:1.60,ef25:1.05},
  'Dallas Goedert':{e25:1.37,e24:2.22,e23:1.35,e22:1.81,ef25:1.37},'Mason Taylor':{e25:1.04,e24:0.91,e23:0,e22:0,ef25:1.04},
  'AJ Barner':{e25:1.46,e24:1.12,e23:0,e22:0,ef25:1.46},'Pat Freiermuth':{e25:1.56,e24:1.45,e23:1.11,e22:1.70,ef25:1.56},
  'Dalton Kincaid':{e25:2.80,e24:1.62,e23:1.46,e22:0,ef25:2.80},'Chigoziem Okonkwo':{e25:1.37,e24:1.25,e23:1.30,e22:2.59,ef25:1.37},
  'Gunnar Helm':{e25:1.47,e24:0,e23:0,e22:0,ef25:1.47},'Cade Otton':{e25:1.06,e24:1.28,e23:.81,e22:.84,ef25:1.06},
  'Isaiah Likely':{e25:1.31,e24:1.53,e23:1.45,e22:1.41,ef25:1.31},'Juwan Johnson':{e25:1.69,e24:1.34,e23:1.18,e22:1.39,ef25:1.69},
  'Hunter Henry':{e25:1.66,e24:1.39,e23:1.14,e22:1.21,ef25:1.66},'Brenton Strange':{e25:1.74,e24:1.47,e23:0.41,e22:0,ef25:1.74},
  'Dalton Schultz':{e25:1.56,e24:1.05,e23:1.46,e22:1.40,ef25:1.56},'Evan Engram':{e25:1.29,e24:1.47,e23:1.55,e22:1.48,ef25:1.29},
  'Jake Ferguson':{e25:1.20,e24:1.26,e23:1.46,e22:1.66,ef25:1.20},'Theo Johnson':{e25:1.20,e24:.88,e23:0,e22:0,ef25:1.20},
  // Missing QBs from EPA document
  'Mac Jones':{e25:0.1,e24:0.0,e23:-0.18,e22:-0.09,ef25:0.1},
  'Malik Willis':{e25:0.49,e24:0.25,e23:-0.5,e22:-0.47,ef25:0.49},
  'Mason Rudolph':{e25:0.06,e24:-0.01,e23:0.09,e22:0.0,ef25:0.06},
  'Jacoby Brissett':{e25:0.0,e24:-0.18,e23:0.68,e22:0.08,ef25:0.0},
  'Kirk Cousins':{e25:-0.02,e24:0.12,e23:0.06,e22:0.03,ef25:-0.02},
  'Joe Flacco':{e25:-0.1,e24:-0.01,e23:-0.06,e22:-0.15,ef25:-0.1},
  'Justin Fields':{e25:-0.06,e24:0.02,e23:-0.03,e22:-0.03,ef25:-0.06},
  'Aaron Rodgers':{e25:0.02,e24:0.06,e23:0.12,e22:-0.04,ef25:0.02},
  // 2025 WR EPA (YPRR-based) from document
  'Stefon Diggs':{e25:2.41,e24:1.84,e23:1.99,e22:2.5,ef25:2.41},
  'Michael Wilson':{e25:1.59,e24:1.09,e23:1.34,e22:0,ef25:1.59},
  'Deebo Samuel':{e25:1.65,e24:1.6,e23:2.34,e22:1.68,ef25:1.65},
  'Troy Franklin':{e25:1.44,e24:1.0,e23:0.0,e22:0,ef25:1.44},
  'Tre Tucker':{e25:1.19,e24:0.84,e23:1.48,e22:0,ef25:1.19},
  'Rashid Shaheed':{e25:1.41,e24:2.04,e23:1.66,e22:2.6,ef25:1.41},
  'Jauan Jennings':{e25:1.38,e24:2.26,e23:1.15,e22:1.37,ef25:1.38},
  'Jerry Jeudy':{e25:1.02,e24:1.72,e23:1.64,e22:2.15,ef25:1.02},
  'Cooper Kupp':{e25:1.39,e24:1.99,e23:1.85,e22:2.44,ef25:1.39},
  'Marquise Brown':{e25:1.49,e24:2.68,e23:1.24,e22:1.43,ef25:1.49},
  'Kayshon Boutte':{e25:1.47,e24:1.27,e23:0.23,e22:0,ef25:1.47},
  'Darius Slayton':{e25:1.23,e24:1.08,e23:1.38,e22:1.78,ef25:1.23},
  'Adonai Mitchell':{e25:1.47,e24:1.52,e23:1.78,e22:0,ef25:1.47},
  'DeMario Douglas':{e25:2.02,e24:1.4,e23:1.71,e22:0,ef25:2.02},
  'Jalen Nailor':{e25:1.06,e24:1.08,e23:0.55,e22:0,ef25:1.06},
  'Darnell Mooney':{e25:0.96,e24:1.89,e23:0.89,e22:1.58,ef25:0.96},
  'Chimere Dike':{e25:1.03,e24:0.0,e23:0.0,e22:0,ef25:1.03},
  'Keon Coleman':{e25:1.27,e24:1.7,e23:0.0,e22:0,ef25:1.27},
  'Pat Bryant':{e25:1.22,e24:1.52,e23:3.18,e22:0,ef25:1.22},
  'Calvin Ridley':{e25:1.89,e24:1.85,e23:1.56,e22:0,ef25:1.89},
  'Xavier Legette':{e25:0.9,e24:1.19,e23:0.0,e22:0,ef25:0.9},
  'Chris Godwin':{e25:1.34,e24:2.37,e23:1.81,e22:1.75,ef25:1.34},
  'Dontayvion Wicks':{e25:1.38,e24:1.42,e23:2.04,e22:0,ef25:1.38},
  'Tez Johnson':{e25:1.07,e24:1.89,e23:1.77,e22:0,ef25:1.07},
  'Marvin Mims':{e25:1.17,e24:2.57,e23:1.53,e22:0,ef25:1.17},
  'Malik Washington':{e25:0.87,e24:0.87,e23:2.26,e22:0,ef25:0.87},
  'Jayden Reed':{e25:1.85,e24:2.21,e23:2.03,e22:0,ef25:1.85},
  'Jalen Tolbert':{e25:0.77,e24:1.1,e23:0.97,e22:0.3,ef25:0.77},
  'Cedric Tillman':{e25:0.85,e24:1.22,e23:0.61,e22:0,ef25:0.85},
  'Devaughn Vele':{e25:1.2,e24:1.51,e23:0.0,e22:0,ef25:1.2},
  'Jaylin Noel':{e25:1.44,e24:0.0,e23:0.0,e22:0,ef25:1.44},
  'Jack Bech':{e25:1.15,e24:1.26,e23:1.92,e22:0,ef25:1.15},
  'Rashod Bateman':{e25:0.7,e24:1.69,e23:1.1,e22:2.38,ef25:0.7},
  'Kyle Williams':{e25:1.17,e24:1.96,e23:1.84,e22:0,ef25:1.17},
  'Jalen McMillan':{e25:2.14,e24:1.18,e23:0.0,e22:0,ef25:2.14},
  'Christian Kirk':{e25:0.85,e24:1.72,e23:2.07,e22:1.78,ef25:0.85},
  'Isaac TeSlaa':{e25:0.81,e24:0.0,e23:0.0,e22:0,ef25:0.81},
  // 2025 RB EPA from document
  "De'Von Achane":{e25:0.06,e24:0,e23:0,e22:0,ef25:0.06},
  'Tyrone Tracy':{e25:-0.06,e24:-0.11,e23:0,e22:0,ef25:-0.06},
  'Kareem Hunt':{e25:0.06,e24:0,e23:-0.04,e22:-0.09,ef25:0.06},
  'Rachaad White':{e25:0.09,e24:-0.11,e23:-0.17,e22:-0.13,ef25:0.09},
  'Tyler Allgeier':{e25:-0.08,e24:0.03,e23:-0.12,e22:0.05,ef25:-0.08},
  'Chris Rodriguez':{e25:0.06,e24:0.23,e23:-0.07,e22:0,ef25:0.06},
  'Isiah Pacheco':{e25:-0.12,e24:-0.16,e23:0,e22:0,ef25:-0.12},
  'Brian Robinson':{e25:-0.01,e24:-0.06,e23:-0.12,e22:-0.03,ef25:-0.01},
  'Tank Bigsby':{e25:0.12,e24:0,e23:-0.25,e22:0,ef25:0.12},
  'Keaton Mitchell':{e25:0.04,e24:-0.35,e23:0.37,e22:0,ef25:0.04},
  'Sean Tucker':{e25:-0.04,e24:0.2,e23:-0.41,e22:0,ef25:-0.04},
  'Jaylen Wright':{e25:-0.08,e24:-0.3,e23:0,e22:0,ef25:-0.08},
  'Ray Davis':{e25:0.02,e24:-0.05,e23:0,e22:0,ef25:0.02},
  'Trey Benson':{e25:-0.01,e24:-0.08,e23:0,e22:0,ef25:-0.01},
  'George Holani':{e25:-0.42,e24:-0.26,e23:0,e22:0,ef25:-0.42},
  'James Conner':{e25:-0.09,e24:0,e23:0.07,e22:0,ef25:-0.09},
  'Audric Estime':{e25:0.1,e24:-0.1,e23:0,e22:0,ef25:0.1},
  'Braelon Allen':{e25:-0.43,e24:-0.08,e23:0,e22:0,ef25:-0.43},
  // 2024 RB EPA
  'MarShawn Lloyd':{e25:0,e24:-0.3,e23:0,e22:0,ef25:0},
  'Jonathon Brooks':{e25:0,e24:-0.31,e23:0,e22:0,ef25:0},
  'Alexander Mattison':{e25:0,e24:-0.23,e23:-0.18,e22:0,ef25:0},
  // 2025 TE EPA (YPRR-based)
  'Zach Ertz':{e25:1.35,e24:1.27,e23:1.01,e22:1.07,ef25:1.35},
  'Dawson Knox':{e25:1.33,e24:1.05,e23:0.77,e22:1.11,ef25:1.33},
  'Colby Parkinson':{e25:1.62,e24:0.99,e23:1.11,e22:1.57,ef25:1.62},
  'Cole Kmet':{e25:1.0,e24:0.89,e23:1.67,e22:1.28,ef25:1.0},
  'Greg Dulcich':{e25:2.29,e24:0.26,e23:1.29,e22:1.31,ef25:2.29},
  'Michael Mayer':{e25:1.47,e24:0.69,e23:1.11,e22:0,ef25:1.47},
  'Jake Tonges':{e25:1.27,e24:1.54,e23:2.26,e22:0,ef25:1.27},
  'Noah Fant':{e25:1.33,e24:1.3,e23:1.29,e22:1.38,ef25:1.33},
  'Elijah Higgins':{e25:1.0,e24:1.01,e23:1.81,e22:0,ef25:1.0},
  'David Njoku':{e25:1.07,e24:1.34,e23:1.69,e22:1.57,ef25:1.07},
  'Jonnu Smith':{e25:0.77,e24:1.96,e23:1.56,e22:1.43,ef25:0.77},
  'Charlie Kolar':{e25:1.41,e24:2.91,e23:1.47,e22:1.81,ef25:1.41},
  'Ben Sinnott':{e25:1.06,e24:0.26,e23:0.0,e22:0,ef25:1.06},
  'Terrance Ferguson':{e25:1.37,e24:1.59,e23:1.92,e22:0,ef25:1.37},
  'JaTavion Sanders':{e25:0.83,e24:1.11,e23:0.0,e22:0,ef25:0.83},
};

function calcEPA(n,pos){
  const d=EPA[n];
  if(!d)return{sc:1.0,raw:1.0,fl:false,fr:null,tr:'flat',ef25:0,ef24:0,e25:0,e24:0,e23:0,e22:0};
  let num=0,den=0;
  if(d.e25!==0){num+=d.e25*3;den+=3;}if(d.e24!==0){num+=d.e24*2;den+=2;}
  if(d.e23!==0){num+=d.e23*1;den+=1;}if(d.e22!==0){num+=d.e22*.5;den+=.5;}
  const raw=den>0?num/den:0;
  let sc=1.0;
  if(pos==='QB')sc=Math.max(.60,Math.min(1.40,1.0+(raw-.10)*3));
  else if(pos==='WR'||pos==='TE')sc=Math.max(.75,Math.min(1.30,1.0+(raw-1.80)*.15));
  else if(pos==='RB')sc=Math.max(.80,Math.min(1.20,1.0+(raw)*3));
  const rawSc=sc;
  const fld=getFloor(n,pos);
  let fl=false,fr=null;
  if(fld&&sc<fld.f){sc=fld.f;fl=true;fr=fld.r;}
  let tr='flat';
  // A trend badge requires THREE consecutive seasons moving the same direction
  // with a meaningful total move — one down year off a career-best is not a
  // trend (e.g. 1.46→2.10→1.90 must read flat, not down).
  if(d.e25!==0&&d.e24!==0&&d.e23!==0){
    const th=pos==='QB'?.05:.20;
    if(d.e25>d.e24&&d.e24>d.e23&&(d.e25-d.e23)>th)tr='up';
    else if(d.e25<d.e24&&d.e24<d.e23&&(d.e23-d.e25)>th)tr='down';
  }
  return{sc,raw:rawSc,fl,fr,tr,ef25:d.ef25||0,ef24:d.ef24||0,e25:d.e25||0,e24:d.e24||0,e23:d.e23||0,e22:d.e22||0};
}

const CB={
  'Josh Allen':1.05,'Drake Maye':.97,'Caleb Williams':1.03,'Jayden Daniels':1.08,'Bo Nix':1.05,
  'Jaxson Dart':1.06,'Cam Ward':1.03,'Shedeur Sanders':.98,
  "Ja'Marr Chase":1.02,'Rome Odunze':1.06,'Malik Nabers':1.05,'Brian Thomas Jr.':1.06,
  'Marvin Harrison Jr.':1.04,'Drake London':1.02,'Tetairoa McMillan':1.03,'Emeka Egbuka':1.01,
  'Tre Harris':1.08,'Luther Burden':1.02,'Jayden Higgins':1.02,'Matthew Golden':1.03,
  'Travis Hunter':1.04,'Bijan Robinson':1.08,'Jahmyr Gibbs':1.06,'Ashton Jeanty':1.10,
  'Omarion Hampton':1.04,'TreVeyon Henderson':1.05,'RJ Harvey':1.07,'Cam Skattebo':1.05,
  'Quinshon Judkins':1.02,'Bhayshul Tuten':1.01,'Ollie Gordon':.95,'Isaac Guerendo':1.04,
  'Brock Bowers':1.05,'Harold Fannin Jr.':1.06,'Tyler Warren':1.04,'Colston Loveland':1.02,
  'Javonte Williams':1.01,'Blake Corum':1.02,
};
const QBQ={
  ARI:.78,ATL:.83,BAL:1.0,BUF:1.0,CAR:.83,CHI:.92,CIN:.95,CLE:.82,
  DAL:.93,DEN:.93,DET:.95,GB:.96,HOU:.87,IND:.88,JAC:.90,KC:.95,
  LV:.74,LAC:.90,LAR:.96,MIA:.72,MIN:1.0,NE:.99,NO:.85,NYG:.84,
  NYJ:.76,PHI:.95,PIT:.79,SF:.95,SEA:.91,TB:.90,TEN:.85,WAS:.95,
};
const AC={
  QB:[[20,22,.88],[23,24,.94],[25,26,1.00],[27,28,1.03],[29,30,1.02],[31,32,.97],[33,99,.88]],
  WR:[[20,22,.90],[23,24,.97],[25,26,1.05],[27,28,1.02],[29,30,.95],[31,32,.85],[33,99,.75]],
  RB:[[20,22,.93],[23,24,1.00],[25,26,1.00],[27,28,.93],[29,30,.82],[31,32,.70],[33,99,.58]],
  TE:[[20,22,.88],[23,24,.96],[25,26,1.03],[27,28,1.05],[29,30,1.02],[31,32,.95],[33,99,.85]]
};
function am(pos,age){const c=AC[pos]||AC.WR;for(const[lo,hi,m]of c)if(age>=lo&&age<=hi)return m;return.75;}

/* ── PROJECTION AGE MULTIPLIER (variant C) ─────────────────────────────────
   Age may only ever HURT next season's projected PPG. It never helps.

   WHY THE PROJECTION AND THE SCORE TREAT AGE DIFFERENTLY
   Youth is genuinely valuable — but its value is LONGEVITY, which is a DELTA
   Score question, not a "what will he average in 2026" question. Two reasons a
   youth boost does not belong in the projection:
     * the base already leans young. It is a 3/2/1 recency weighting, so an
       ascending player's most recent (best) season carries triple weight.
     * ascent is already modelled with EVIDENCE — role, YPRR, opportunity, draft
       capital, EPA. A blind age boost stacks a prior on top of measured signals
       that capture the same thing, and double-counts it.
   Decline is different in kind: near-universal and monotonic, and NOT separately
   modelled anywhere else. So the curve keeps its downside and loses its upside.

   BACKTEST (2003-2024, 5,193 player-seasons of nflverse data rescored into
   DELTA's format, DELTA's own 3/2/1 base weighting, ages from birth dates):
     current curve         RMSE 3.299 (holdout 2019-24)
     cap at 1.0 only       +0.42%   p=0.003
     THIS (cap + no young penalty)  +1.25%   p<0.0001
     curve FITTED to 3,660 seasons  +1.27%   p=0.034   <- no better than this rule
   A fitted curve with 68 free parameters is statistically indistinguishable from
   this two-line rule (p=0.966), and a no-age control gains nothing (+0.02%,
   p=0.97) while the fitted curve beats that control (+1.24%, p=0.008). Read
   together: age carries real signal, ~1.3% is the ceiling of what it can carry,
   and this rule already reaches that ceiling.

   BELOW THE 2% SHIP GATE, SHIPPED DELIBERATELY. The gate exists to stop changes
   justified by intuition; this one is the measured maximum of its lever, is
   significant at p<0.0001 on 22 seasons, and follows from a stated principle
   rather than from tuning. RB alone is not individually significant (+0.16%,
   p=0.12); applied uniformly anyway, because a position-specific exception costs
   more clarity than it buys and the fitted RB curve puts any real young-RB
   penalty near zero (0.94 at 21).

   NOT CHANGED: the decline slopes. The backtest says they are too steep (RB 33+
   fits near 0.90 against the engine's 0.58), but the sample only contains players
   who still logged 8+ games, so collapse cases are absent and the old-age fits are
   survivor-biased. Over-penalising a 32-year-old back is a deliberate house bias.
   NOT CHANGED: mvAsset / mvAssetRaw, which also call am(). Only the PROJECTION was
   backtested, so only the projection moves. */
const PEAK_AGE={QB:27,WR:25,RB:23,TE:27};
function amProj(pos,age){
  const p=PEAK_AGE[pos]!==undefined?pos:'WR';
  if(age<PEAK_AGE[p]) return 1.0;      // young: no penalty
  return Math.min(1.0,am(pos,age));    // prime: no boost · old: full decline
}
function sm(s){return s>=70?1.12:s>=55?1.03:s>=40?.92:.78;}
function cm(c){return c>=.95?1.00:c>=.70?.96:c>=.50?.88:c>=.30?.80:.72;}
function ci(c){return c>=.95?.10:c>=.70?.15:c>=.50?.22:.32;}
// Ripple multipliers (name -> projection multiplier). Populated from
// data/ripple.json by loadRipples(); empty until then (no phantom values).
// Single source of truth — the display array RIPPLE is built from the same file,
// so the shown reason and the modeled effect can never drift.
let RP={};

// Target Share Trend Deltas — computed from 3-year weekly target share data
// Weighted: H1→H2 2025 trend (50%) + YoY 24→25 (30%) + YoY 23→24 (20%)
// Positive = ascending share, Negative = declining. Capped at ±8%.
const TS_DELTA={
  "Aaron Jones":0.05,"Alec Pierce":0.01,"Alvin Kamara":-0.08,"Amon-Ra St. Brown":-0.03,
  "Ashton Jeanty":0.03,"Bijan Robinson":0.01,"Breece Hall":-0.01,"Brian Thomas Jr.":-0.05,
  "Brock Bowers":-0.03,"Bucky Irving":-0.01,"CeeDee Lamb":-0.05,"Chase Brown":0.03,
  "Chris Olave":0.03,"Christian McCaffrey":-0.01,"Christian Watson":0.03,"Chuba Hubbard":-0.08,
  "Colston Loveland":-0.01,"D'Andre Swift":-0.03,"DK Metcalf":0.01,"Dalton Kincaid":-0.08,
  "Davante Adams":-0.01,"De'Von Achane":0.05,"DeVonta Smith":-0.01,"Deebo Samuel":-0.01,
  "Derrick Henry":0.03,"Drake London":-0.01,"Evan Engram":-0.01,"Garrett Wilson":-0.03,
  "George Kittle":0.03,"George Pickens":-0.01,"Harold Fannin Jr.":0.08,"Isaiah Likely":0.01,
  "Ja'Marr Chase":0.01,"Jahmyr Gibbs":0.05,"James Conner":-0.03,"James Cook":-0.05,
  "Jameson Williams":0.03,"Javonte Williams":-0.03,"Jaxon Smith-Njigba":0.03,"Jayden Reed":-0.03,
  "Jaylen Warren":-0.08,"Jonathan Taylor":0.01,"Jordan Addison":-0.01,"Josh Downs":0.01,
  "Justin Jefferson":0.01,"Keon Coleman":0.01,"Khalil Shakir":0.03,"Kyle Pitts":0.03,
  "Ladd McConkey":-0.03,"Luther Burden":0.05,"Malik Nabers":-0.01,"Mark Andrews":-0.05,
  "Marvin Harrison Jr.":-0.03,"Mason Taylor":-0.03,"Omarion Hampton":-0.01,"Parker Washington":0.03,
  "Pat Freiermuth":-0.03,"Puka Nacua":0.03,"Quentin Johnston":0.01,"RJ Harvey":0.03,
  "Rashee Rice":0.03,"Rashid Shaheed":0.01,"Rhamondre Stevenson":0.03,"Rome Odunze":0.03,
  "Sam LaPorta":-0.03,"Saquon Barkley":0.01,"T.J. Hockenson":-0.01,"Tee Higgins":0.01,
  "Terry McLaurin":0.03,"Tetairoa McMillan":-0.01,"Tony Pollard":-0.08,"Travis Kelce":0.01,
  "Trey McBride":0.01,"Troy Franklin":-0.01,"Tyler Warren":-0.03,"Xavier Worthy":-0.01,
  "Zach Charbonnet":-0.03,"Zay Flowers":0.05,
  // New batch TS
  "A.J. Brown":0.026,
  "AJ Barner":0.068,
  "Adonai Mitchell":0.08,
  "Ben Sinnott":0.069,
  "Bhayshul Tuten":-0.037,
  "Blake Corum":0.007,
  "Braelon Allen":-0.032,
  "Brandon Aiyuk":-0.08,
  "Brenton Strange":0.08,
  "Brian Robinson":-0.023,
  "Cade Otton":0.004,
  "Calvin Ridley":-0.08,
  "Cam Skattebo":-0.08,
  "Cedric Tillman":0.007,
  "Charlie Kolar":0.062,
  "Chigoziem Okonkwo":0.039,
  "Chimere Dike":0.076,
  "Chris Rodriguez":0.029,
  "Colby Parkinson":0.062,
  "Cole Kmet":-0.015,
  "Courtland Sutton":-0.001,
  "Dallas Goedert":0.007,
  "Dalton Schultz":0.015,
  "Darius Slayton":0.008,
  "Darnell Mooney":-0.054,
  "David Montgomery":0.08,
  "David Njoku":-0.08,
  "Dawson Knox":0.069,
  "DeMario Douglas":-0.059,
  "Devaughn Vele":0.004,
  "Dontayvion Wicks":-0.041,
  "Dylan Sampson":0.009,
  "Elic Ayomanor":-0.08,
  "Elijah Higgins":0.022,
  "Emeka Egbuka":-0.038,
  "George Holani":-0.006,
  "Gunnar Helm":0.041,
  "Hunter Henry":0.034,
  "Isaac Guerendo":-0.019,
  "Isaac TeSlaa":0.059,
  "Isiah Pacheco":-0.036,
  "J.K. Dobbins":-0.031,
  "Jack Bech":0.06,
  "Jacory Croskey-Merritt":-0.068,
  "Jake Ferguson":-0.046,
  "Jake Tonges":-0.006,
  "Jakobi Meyers":0.004,
  "Jalen Coker":0.08,
  "Jalen McMillan":0.001,
  "Jalen Nailor":-0.007,
  "Jalen Tolbert":-0.033,
  "Jayden Higgins":0.08,
  "Jaylen Waddle":-0.068,
  "Jaylen Wright":0.04,
  "Jaylin Noel":-0.032,
  "Jerry Jeudy":-0.018,
  "Jonnu Smith":-0.011,
  "Jordan Mason":-0.025,
  "Josh Jacobs":-0.08,
  "Juwan Johnson":0.018,
  "Kayshon Boutte":-0.014,
  "Keaton Mitchell":0.042,
  "Kenneth Gainwell":0.08,
  "Kenneth Walker III":0.05,
  "Kimani Vidal":0.028,
  "Kyle Monangai":0.011,
  "Kyle Williams":0.054,
  "Kyren Williams":-0.014,
  "Malik Washington":0.035,
  "Marvin Mims":-0.036,
  "Matthew Golden":-0.012,
  "Michael Mayer":0.011,
  "Michael Pittman Jr.":-0.044,
  "Michael Wilson":0.08,
  "Mike Evans":0.08,
  "Nico Collins":-0.021,
  "Noah Fant":-0.059,
  "Ollie Gordon":-0.034,
  "Oronde Gadsden":0.036,
  "Pat Bryant":0.08,
  "Quinshon Judkins":0.032,
  "Rachaad White":0.0,
  "Rashod Bateman":-0.08,
  "Ray Davis":-0.005,
  "Ricky Pearsall":0.013,
  "Rico Dowdle":0.016,
  "Romeo Doubs":-0.044,
  "Sean Tucker":0.006,
  "Tank Bigsby":0.003,
  "Tank Dell":0.039,
  "Terrance Ferguson":0.009,
  "Tez Johnson":-0.055,
  "Theo Johnson":0.023,
  "Travis Etienne":-0.033,
  "Travis Hunter":-0.08,
  "Tre Harris":0.08,
  "Tre Tucker":0.051,
  "TreVeyon Henderson":-0.032,
  "Trey Benson":-0.042,
  "Tucker Kraft":-0.08,
  "Tyjae Spears":0.052,
  "Tyler Allgeier":-0.033,
  "Tyrone Tracy":0.043,
  "Woody Marks":-0.035,
  "Xavier Legette":-0.039,
  "Zach Ertz":-0.035,
  // Remaining FA/late players TS
  "Chris Godwin":0.036,
  "Christian Kirk":0.013,
  "Cooper Kupp":-0.027,
  "D.J. Moore":-0.066,
  "Greg Dulcich":0.08,
  "Jauan Jennings":0.056,
  "Kareem Hunt":0.023,
  "Marquise Brown":-0.08,
  "Stefon Diggs":-0.048,
  "Wan'Dale Robinson":0.08,
};

// Rising/Fading trend tags — derived from target share H1→H2 and multi-year data
// Rising: H1→H2 > +10pp OR trend score > 7; Fading: H1→H2 < -10pp OR score < -8
const TREND_TAG={
  // Rising ↑ — confirmed ascending role trajectory
  "Luther Burden":"rising","Harold Fannin Jr.":"rising",
  "Jahmyr Gibbs":"rising","Zay Flowers":"rising","De'Von Achane":"rising",
  "George Kittle":"rising","Jaxon Smith-Njigba":"rising",
  "RJ Harvey":"rising","Ashton Jeanty":"rising",
  // Fading ↓ — confirmed declining role trajectory
  "Alvin Kamara":"fading","Tony Pollard":"fading","Chuba Hubbard":"fading",
  "Garrett Wilson":"fading",
  "Brian Thomas Jr.":"fading","Mark Andrews":"fading","Jayden Reed":"fading","Ladd McConkey":"fading",
  "DeVonta Smith":"fading","Pat Freiermuth":"fading","Mason Taylor":"fading","Marvin Harrison Jr.":"fading",
  "T.J. Hockenson":"fading",
  "George Pickens":"rising",
  "Jaxson Dart":"rising",
  
  "Rome Odunze":"rising",
  "Aaron Jones":"fading",
  "D'Andre Swift":"fading",
  "Derrick Henry":"fading",
  "Isaiah Likely":"fading",
  "Terry McLaurin":"fading",
};
// Rising/Fading BADGE removed June 2026 — the hand-maintained TREND_TAG table
// went stale and contradicted the live verdict (e.g. DeVonta Smith "fading"
// right after becoming Philly's WR1; D'Andre Swift "fading" + strong-buy).
// The table itself is intentionally retained: it still feeds the model-value
// nudge (d_trend) and the QB rising-CI multiplier in mvAssetRaw. Only the
// visual badge is gone. To revisit later as an ENGINE-DERIVED signal, drive it
// off nightly DELTA Score deltas, not a manual list.
function trendTag(n){ return ''; }
const OV={};let editTarget=null;

/* ── AVAILABILITY / EFFECTIVENESS MULTIPLIERS ──────────────────────────────
   Hand-maintained. A multiplier < 1 says: this player is expected to play, but
   the projection built from his history overstates what he can repeat.

   This is NOT the season-ender list (data/injury-overrides.json, which zeroes a
   projection outright). It is the middle case the engine previously could not
   express: available, but materially diminished.

   Add a name only with a written reason. Every entry is a judgement, not a
   measurement, and the accuracy ledger will grade it as such. */
const AVAIL={
  'Patrick Mahomes':{m:0.88, why:'Torn ACL. His passing PPG is flat across three seasons '
    +'(15.46 / 14.95 / 14.96); the entire 2025 rise to 20.1 came from rushing (2.43 -> 2.67 -> 5.16 PPG). '
    +'calcProj rewards that rise through d_curve (+0.039), so the model is crediting him for exactly the '
    +'production the injury removes. 0.88 reverts the rushing share toward his own pre-2025 norm and lands '
    +'at ~17.9 PPG, between CBS 18.0 and ESPN 17.1.'},
};

/* ── BACKUP ROLE SUPPRESSION ───────────────────────────────────────────────
   QB_ROLES already carries pipeline-emitted backup flags (loaded from
   data/player-stats.json) but until now they only reached dsOpportunity — the
   PROJECTION ignored them, so Justin Fields and Jameis Winston were projected as
   if they were starting. NON_QB_BACKUP is the hand-maintained equivalent for
   skill positions, where the pipeline has no depth-chart feed.

   The multiplier is deliberately NOT near zero. DELTA is a dynasty tool and a
   backup with starter upside holds real value; printing ~1 PPG would be as wrong
   in the other direction and would crater model value. This says "fewer snaps
   than his history implies", not "he will never play". */
const BACKUP_MULT=0.55;
const NON_QB_BACKUP={
  'Jake Tonges':'TE2 behind George Kittle — plays almost only when Kittle is off the field.',
};
function availMult(pl,withRole=true){
  let m=1;
  if(AVAIL[pl.n]) m*=AVAIL[pl.n].m;
  /* QB_ROLES is declared further down the file (beside its loader) but getEff runs
     during the FIRST COMP population, above that line — reading it directly here
     throws a ReferenceError from the temporal dead zone and blanks the whole app.
     The typeof guard makes the first pass see no flags; the flags land on the
     recompute that follows loadPlayerStats(), which is when they exist anyway. */
  const roles=(typeof QB_ROLES!=='undefined')?QB_ROLES:{};
  const isBackup=(roles[pl.n]&&roles[pl.n].role==='backup')||NON_QB_BACKUP[pl.n];
  if(isBackup && withRole) m*=BACKUP_MULT;   // withRole=false: a QB's points-per-start projection (role -> model value only)
  return m;
}

/* Injury state — see loadInjuryOverrides() below for the full rationale.
   Declared HERE rather than beside the loader because calcProj runs during
   initial COMP population, before the loader block is reached. */
let INJ_STATUS = {};
let INJ_OUT = {};

/* Hand-maintained: quarterbacks confirmed as their team's Week-1 starter. Consumed by
   the starter-baseline override in calcProj. Kept hand-maintained rather than derived
   because depth charts do not settle until the last week of August, which is after most
   data pulls and right on top of the freeze. Only 17 QBs in the current universe can
   possibly trigger the rule (under 8 games in 2025 with prior NFL history), so the file
   stays small. */
let QB_STARTERS = {};

/* ── QB POINTS PER START (3 Oct 2026) ─────────────────────────────────────
   docs/PREREG-qb-perstart.md, locked f56dcab, PASSED: on 277 thin-history QB-seasons
   (2002-2025, each season graded on a fit from the others) the typical miss fell 7.7%
   (p = 0.0005), both halves, and established QBs 1.5% better too.
   Owner's definition (2 Oct): a QB's projection is his points per game WHEN HE STARTS.
     base = (n x own + 13 x 0.87 x level) / (n + 13)
   n = his starts over the last three seasons; own = his points per start over them (3/2/1
   season weights, each also weighted by its starts); level = median points per start of
   every QB with 14+ starts last season (pipeline: qb_starter_level). A thin record is pulled
   toward 87% of an established starter, and trusted slowly — half weight at 13 starts.
   No backup cut (role -> model value only), no missed-time cut, no starter lift: this
   formula replaces all three for QBs. True rookies keep the rookie path. Without the
   pipeline fields (older data) this returns null and the old QB path runs unchanged. */
let QB_PS = null, QB_PS_LEVEL = 0;
const QB_PS_K = 13, QB_PS_ANCHOR = 0.87;
function qbPerStart(pl){
  if(!QB_PS || !(QB_PS_LEVEL>0) || pl.p!=='QB') return null;   // checked first: SEASON_YEAR is declared below
  const sp = QB_PS[pl.n] || {};
  const hist = (pl.g25||0)>0 || pl.ppg24>0 || pl.ppg23>0 || Object.keys(sp).length>0;
  if(!hist) return null;                                         // a true rookie
  let n=0, num=0, den=0;
  for(const [k,w] of [[1,3],[2,2],[3,1]]){
    const s = sp[String(SEASON_YEAR-k)];
    if(s && s.starts>0){ n+=s.starts; num+=w*s.starts*s.ppst; den+=w*s.starts; }
  }
  const own = den>0 ? num/den : 0;
  return {base:(n*own + QB_PS_K*QB_PS_ANCHOR*QB_PS_LEVEL)/(n+QB_PS_K), n, own};
}

/* Median PPG among quarterbacks who played a full season last year — the level a
   starting job is worth. Computed from live stats rather than hard-coded so it tracks
   the league and the selected scoring format (17.70 in half-PPR on 2025 data). Cached
   per COMP rebuild; the cache key is the format, since changing format changes PPG. */
let _qbSbCache = {fmt:null, val:0};
function qbStarterBaseline(){
  if(_qbSbCache.fmt === scoringFmt) return _qbSbCache.val;
  const v=[];
  for(const r of RAW){
    if(r.p!=='QB') continue;
    if((r.g25||0)>=14 && (r.ppg25||0)>0) v.push(r.ppg25);
  }
  v.sort((a,b)=>a-b);
  const val = v.length>=8 ? v[Math.floor(v.length/2)] : 0;   // too few to trust -> disable
  _qbSbCache={fmt:scoringFmt, val};
  return val;
}
function getEff(pl){
  const o=OV[pl.n]||{};
  const team=o.team||pl.t;
  const td=gs(team);
  return{team,s:o.s!==undefined?o.s:td.s,c:o.c!==undefined?o.c:td.c,
    oc:td.oc,ch:td.ch,inj:o.inj!==undefined?o.inj:availMult(pl),injP:o.inj!==undefined?o.inj:availMult(pl,false),
    ktc:o.ktc!==undefined?o.ktc:pl.k,notes:o.notes||'',hasOv:Object.keys(o).length>0};
}

/* k — the built-in market value (12-team superflex). A BACKUP ONLY: on every normal visit the
   nightly FantasyCalc file replaces it (loadLiveMarketValues), and it shows only when that file
   fails to load or does not list the player. Refreshed 25 Oct 2026 (legal compliance plan, step 5)
   to FantasyCalc's values of 24 Oct for the 363 players FantasyCalc lists. The older numbers sat
   on KTC's 0-9,999 scale and their source could not be traced. The 46 players FantasyCalc does
   not list keep their older numbers for now, because those are what the site shows for them;
   swapping them (44 have a last FantasyCalc price in data/market-history) moves their values and
   waits on the owner. Teammate order for the style factors no longer reads k: STYLE_ROLE_ORDER. */
const RAW=[
  // QBs — note: no superflex multiplier; market value already prices it in
  {n:'Josh Allen',t:'BUF',p:'QB',a:29.8,k:10783,ppg25:22.0,ppg24:22.7,ppg23:24.2,g25:17},
  {n:'Drake Maye',t:'NE',p:'QB',a:23.6,k:7100,ppg25:21.1,ppg24:14.4,ppg23:0,g25:17},
  {n:'Jayden Daniels',t:'WAS',p:'QB',a:25.2,k:5512,ppg25:16.7,ppg24:21.5,ppg23:0,g25:7},
  {n:'Caleb Williams',t:'CHI',p:'QB',a:24.3,k:7279,ppg25:19.0,ppg24:15.3,ppg23:0,g25:17},
  {n:'Lamar Jackson',t:'BAL',p:'QB',a:29.2,k:6827,ppg25:17.1,ppg24:25.6,ppg23:21.1,g25:13},
  {n:'Patrick Mahomes',t:'KC',p:'QB',a:30.5,k:5463,ppg25:21.1,ppg24:18.3,ppg23:18.4,g25:14},
  {n:'Jalen Hurts',t:'PHI',p:'QB',a:27.6,k:3485,ppg25:19.1,ppg24:21.3,ppg23:21.9,g25:16},
  {n:'Justin Herbert',t:'LAC',p:'QB',a:28.0,k:3767,ppg25:18.7,ppg24:17.0,ppg23:18.5,g25:16},
  {n:'Bo Nix',t:'DEN',p:'QB',a:26.1,k:3403,ppg25:18.6,ppg24:19.3,ppg23:0,g25:17},
  {n:'Trevor Lawrence',t:'JAC',p:'QB',a:26.4,k:5991,ppg25:20.6,ppg24:15.2,ppg23:17.3,g25:17},
  {n:'Jared Goff',t:'DET',p:'QB',a:31.4,k:4151,ppg25:17.9,ppg24:19.7,ppg23:17.7,g25:17},
  {n:'Dak Prescott',t:'DAL',p:'QB',a:32.6,k:3806,ppg25:19.0,ppg24:15.6,ppg23:20.7,g25:17},
  {n:'Brock Purdy',t:'SF',p:'QB',a:26.2,k:6273,ppg25:20.8,ppg24:18.6,ppg23:19.2,g25:9},
  {n:'Jordan Love',t:'GB',p:'QB',a:27.4,k:4739,ppg25:16.1,ppg24:16.3,ppg23:19.4,g25:15},
  {n:'Baker Mayfield',t:'TB',p:'QB',a:30.9,k:2620,ppg25:16.6,ppg24:22.5,ppg23:16.7,g25:17},
  {n:'Sam Darnold',t:'SEA',p:'QB',a:28.8,k:2729,ppg25:14.7,ppg24:18.8,ppg23:0,g25:17},
  {n:'C.J. Stroud',t:'HOU',p:'QB',a:24.4,k:4414,ppg25:15.5,ppg24:13.7,ppg23:18.7,g25:14},
  {n:'Jaxson Dart',t:'NYG',p:'QB',a:22.8,k:4036,ppg25:17.6,ppg24:0,ppg23:0,g25:14},
  {n:'Cam Ward',t:'TEN',p:'QB',a:23.8,k:2239,ppg25:11.4,ppg24:0,ppg23:0,g25:17},
  {n:'Bryce Young',t:'CAR',p:'QB',a:24.6,k:4510,ppg25:14.3,ppg24:14.6,ppg23:10.4,g25:16},
  {n:'Matthew Stafford',t:'LAR',p:'QB',a:38.1,k:2604,ppg25:21.1,ppg24:13.9,ppg23:17.0,g25:17},
  {n:'Kyler Murray',t:'MIN',p:'QB',a:28.6,k:2696,ppg25:16.2,ppg24:18.1,ppg23:18.9,g25:5},
  {n:'Joe Burrow',t:'CIN',p:'QB',a:29.3,k:6412,ppg25:17.4,ppg24:22.5,ppg23:15.3,g25:8},
  {n:'Tua Tagovailoa',t:'ATL',p:'QB',a:28.0,k:403,ppg25:12.5,ppg24:17.1,ppg23:16.7,g25:14},
  {n:'Geno Smith',t:'NYJ',p:'QB',a:35.0,k:1579,ppg25:12.7,ppg24:16.5,ppg23:15.7,g25:15},
  {n:'J.J. McCarthy',t:'MIN',p:'QB',a:23.2,k:1888,ppg25:13.7,ppg24:0,ppg23:0,g25:10},
  {n:'Daniel Jones',t:'IND',p:'QB',a:28.8,k:1752,ppg25:18.0,ppg24:14.2,ppg23:0,g25:13},
  {n:'Tyler Shough',t:'NO',p:'QB',a:26.5,k:3914,ppg25:14.9,ppg24:0,ppg23:0,g25:11},
  {n:'Michael Penix Jr.',t:'ATL',p:'QB',a:25.9,k:2405,ppg25:13.7,ppg24:9.4,ppg23:0,g25:9},
  {n:'Shedeur Sanders',t:'CLE',p:'QB',a:24.1,k:794,ppg25:11.9,ppg24:0,ppg23:0,g25:8},
  {n:'Mason Rudolph',t:'PIT',p:'QB',a:30.0,k:535,ppg25:3.4,ppg24:13.1,ppg23:9.9,g25:5},
  {n:'Aaron Rodgers',t:'PIT',p:'QB',a:42.3,k:1581,ppg25:14.2,ppg24:0,ppg23:18.5,g25:10},
  {n:'Malik Willis',t:'MIA',p:'QB',a:26.8,k:1893,ppg25:12.8,ppg24:7.4,ppg23:0,g25:4},
  {n:'Jacoby Brissett',t:'ARI',p:'QB',a:34.4,k:1439,ppg25:16.8,ppg24:6.6,ppg23:0,g25:14},
  // RBs
  {n:'Bijan Robinson',t:'ATL',p:'RB',a:24.1,k:10061,ppg25:19.5,ppg24:18.3,ppg23:19.5,g25:17},
  {n:'Jahmyr Gibbs',t:'DET',p:'RB',a:24.0,k:10650,ppg25:19.3,ppg24:19.8,ppg23:0,g25:17},
  {n:'James Cook',t:'BUF',p:'RB',a:26.5,k:5302,ppg25:16.8,ppg24:15.7,ppg23:12.4,g25:17},
  {n:'Jonathan Taylor',t:'IND',p:'RB',a:27.2,k:5968,ppg25:20.0,ppg24:16.8,ppg23:20.0,g25:17},
  {n:'Derrick Henry',t:'BAL',p:'RB',a:32.2,k:3562,ppg25:16.0,ppg24:19.2,ppg23:13.7,g25:17},
  {n:'Kyren Williams',t:'LAR',p:'RB',a:25.6,k:4407,ppg25:14.4,ppg24:15.9,ppg23:19.9,g25:17},
  {n:'Saquon Barkley',t:'PHI',p:'RB',a:29.1,k:2977,ppg25:13.4,ppg24:21.2,ppg23:14.5,g25:16},
  {n:'Christian McCaffrey',t:'SF',p:'RB',a:29.8,k:4492,ppg25:21.5,ppg24:10.1,ppg23:22.4,g25:17},
  {n:'Chase Brown',t:'CIN',p:'RB',a:25.0,k:3342,ppg25:14.6,ppg24:14.3,ppg23:3.9,g25:17},
  {n:'Travis Etienne',t:'NO',p:'RB',a:27.1,k:2035,ppg25:13.9,ppg24:7.4,ppg23:14.9,g25:17},
  {n:'Javonte Williams',t:'DAL',p:'RB',a:25.9,k:3672,ppg25:14.1,ppg24:7.8,ppg23:9.7,g25:16},
  {n:'Josh Jacobs',t:'GB',p:'RB',a:28.1,k:2458,ppg25:14.6,ppg24:16.2,ppg23:12.5,g25:15},
  {n:'Ashton Jeanty',t:'LV',p:'RB',a:22.3,k:5593,ppg25:12.8,ppg24:0,ppg23:0,g25:17},
  {n:"D'Andre Swift",t:'CHI',p:'RB',a:27.2,k:3010,ppg25:13.2,ppg24:11.4,ppg23:11.2,g25:16},
  {n:'Jaylen Warren',t:'PIT',p:'RB',a:27.4,k:2741,ppg25:12.3,ppg24:7.0,ppg23:9.8,g25:16},
  {n:'Rico Dowdle',t:'PIT',p:'RB',a:27.8,k:1233,ppg25:11.6,ppg24:11.1,ppg23:5.2,g25:17},
  {n:'Breece Hall',t:'NYJ',p:'RB',a:24.8,k:3683,ppg25:11.9,ppg24:13.3,ppg23:14.9,g25:16},
  {n:'TreVeyon Henderson',t:'NE',p:'RB',a:23.4,k:2350,ppg25:11.1,ppg24:0,ppg23:0,g25:17},
  {n:'Kenneth Gainwell',t:'TB',p:'RB',a:27.0,k:921,ppg25:10.9,ppg24:3.2,ppg23:5.2,g25:17},
  {n:'RJ Harvey',t:'DEN',p:'RB',a:25.1,k:1813,ppg25:10.8,ppg24:0,ppg23:0,g25:17},
  {n:'Kenneth Walker III',t:'KC',p:'RB',a:25.4,k:7109,ppg25:10.4,ppg24:14.4,ppg23:12.3,g25:17},
  {n:'Zach Charbonnet',t:'SEA',p:'RB',a:25.2,k:1840,ppg25:10.7,ppg24:9.8,ppg23:5.6,g25:16},
  {n:'Tony Pollard',t:'TEN',p:'RB',a:28.9,k:1347,ppg25:10.0,ppg24:11.3,ppg23:11.5,g25:17},
  {n:'Rhamondre Stevenson',t:'NE',p:'RB',a:28.1,k:1722,ppg25:11.6,ppg24:10.6,ppg23:10.6,g25:14},
  {n:'Quinshon Judkins',t:'CLE',p:'RB',a:22.4,k:2712,ppg25:11.2,ppg24:0,ppg23:0,g25:14},
  {n:'David Montgomery',t:'HOU',p:'RB',a:28.8,k:1506,ppg25:9.1,ppg24:14.6,ppg23:14.2,g25:17},
  {n:'Woody Marks',t:'HOU',p:'RB',a:25.2,k:1626,ppg25:8.7,ppg24:0,ppg23:0,g25:16},
  {n:'Kyle Monangai',t:'CHI',p:'RB',a:23.8,k:2104,ppg25:8.1,ppg24:0,ppg23:0,g25:17},
  {n:'Kareem Hunt',t:'FA',p:'RB',a:30.0,k:668,ppg25:8.0,ppg24:11.1,ppg23:7.4,g25:17},
  {n:'Jacory Croskey-Merritt',t:'WAS',p:'RB',a:24.9,k:1358,ppg25:8.0,ppg24:0,ppg23:0,g25:17},
  {n:'Bucky Irving',t:'TB',p:'RB',a:23.6,k:3596,ppg25:12.4,ppg24:13.0,ppg23:0,g25:10},
  {n:'Rachaad White',t:'WAS',p:'RB',a:27.2,k:1231,ppg25:7.2,ppg24:10.9,ppg23:13.9,g25:17},
  {n:'Jordan Mason',t:'MIN',p:'RB',a:26.8,k:1537,ppg25:7.6,ppg24:9.1,ppg23:2.7,g25:16},
  {n:'Omarion Hampton',t:'LAC',p:'RB',a:23.0,k:3173,ppg25:13.3,ppg24:0,ppg23:0,g25:9},
  {n:'Blake Corum',t:'LAR',p:'RB',a:25.3,k:1821,ppg25:7.0,ppg24:2.0,ppg23:0,g25:17},
  {n:'Cam Skattebo',t:'NYG',p:'RB',a:24.1,k:2107,ppg25:14.5,ppg24:0,ppg23:0,g25:8},
  {n:'J.K. Dobbins',t:'DEN',p:'RB',a:27.2,k:1335,ppg25:11.0,ppg24:13.5,ppg23:0,g25:10},
  {n:'Chuba Hubbard',t:'CAR',p:'RB',a:26.8,k:3131,ppg25:7.4,ppg24:14.7,ppg23:9.6,g25:15},
  {n:'Bhayshul Tuten',t:'JAC',p:'RB',a:23.1,k:3450,ppg25:5.6,ppg24:0,ppg23:0,g25:15},
  {n:'Aaron Jones',t:'MIN',p:'RB',a:31.3,k:1527,ppg25:8.7,ppg24:12.7,ppg23:10.9,g25:12},
  {n:'Tyjae Spears',t:'TEN',p:'RB',a:25.4,k:1016,ppg25:6.9,ppg24:8.2,ppg23:7.5,g25:13},
  {n:'Alvin Kamara',t:'NO',p:'RB',a:30.6,k:1087,ppg25:7.7,ppg24:16.5,ppg23:15.0,g25:11},
  {n:"De'Von Achane",t:'MIA',p:'RB',a:24.0,k:3965,ppg25:12.8,ppg24:18.7,ppg23:0,g25:14},
  {n:'Ollie Gordon',t:'MIA',p:'RB',a:22.2,k:1822,ppg25:3.0,ppg24:0,ppg23:0,g25:16},
  {n:'Isaac Guerendo',t:'SF',p:'RB',a:25.7,k:1689,ppg25:0,ppg24:5.4,ppg23:0,g25:0},
  {n:'Trey Benson',t:'ARI',p:'RB',a:23.6,k:141,ppg25:5.8,ppg24:3.4,ppg23:0,g25:4},
  {n:'Dylan Sampson',t:'CLE',p:'RB',a:22.8,k:1084,ppg25:4.7,ppg24:0,ppg23:0,g25:15},
  {n:'Jaylen Wright',t:'MIA',p:'RB',a:23.3,k:483,ppg25:4.2,ppg24:1.7,ppg23:0,g25:11},
  {n:'Braelon Allen',t:'NYJ',p:'RB',a:22.2,k:1594,ppg25:3.6,ppg24:4.5,ppg23:0,g25:4},
  {n:'James Conner',t:'ARI',p:'RB',a:30.2,k:258,ppg25:7.3,ppg24:14.4,ppg23:14.5,g25:4},
  {n:'Isiah Pacheco',t:'DET',p:'RB',a:27.3,k:395,ppg25:6.0,ppg24:7.3,ppg23:13.7,g25:13},
  
  
  {n:'Jonathon Brooks',t:'CAR',p:'RB',a:22.1,k:1300,ppg25:5.2,ppg24:0,ppg23:0,g25:8},
    {n:'Tank Bigsby',t:'JAC',p:'RB',a:23.8,k:623,ppg25:8.1,ppg24:6.2,ppg23:0,g25:15},
      {n:'Alexander Mattison',t:'FA',p:'RB',a:26.7,k:708,ppg25:4.8,ppg24:7.2,ppg23:13.4,g25:10},
  {n:'Audric Estime',t:'DEN',p:'RB',a:22.8,k:46,ppg25:6.3,ppg24:0,ppg23:0,g25:14},
  {n:'MarShawn Lloyd',t:'GB',p:'RB',a:24.2,k:966,ppg25:5.8,ppg24:0,ppg23:0,g25:12},
  {n:'Kimani Vidal',t:'LAC',p:'RB',a:23.5,k:832,ppg25:5.2,ppg24:2.1,ppg23:0,g25:11},
  // WRs
  {n:'Puka Nacua',t:'LAR',p:'WR',a:24.8,k:8274,ppg25:19.4,ppg24:15.2,ppg23:14.5,g25:16},
  {n:'Jaxon Smith-Njigba',t:'SEA',p:'WR',a:24.1,k:9922,ppg25:17.7,ppg24:11.9,ppg23:7.0,g25:17},
  {n:'Amon-Ra St. Brown',t:'DET',p:'WR',a:26.4,k:7356,ppg25:15.6,ppg24:15.2,ppg23:17.0,g25:17},
  {n:'George Pickens',t:'DAL',p:'WR',a:25.0,k:3897,ppg25:14.4,ppg24:9.6,ppg23:10.4,g25:17},
  {n:'Chris Olave',t:'NO',p:'WR',a:25.7,k:4898,ppg25:13.7,ppg24:7.6,ppg23:11.7,g25:16},
  {n:'Zay Flowers',t:'BAL',p:'WR',a:25.5,k:4916,ppg25:11.8,ppg24:10.1,ppg23:10.5,g25:17},
  {n:'Davante Adams',t:'LAR',p:'WR',a:33.2,k:1941,ppg25:13.8,ppg24:14.2,ppg23:12.6,g25:14},
  {n:'Nico Collins',t:'HOU',p:'WR',a:27.0,k:4529,ppg25:12.7,ppg24:14.7,ppg23:14.7,g25:15},
  {n:'Jameson Williams',t:'DET',p:'WR',a:25.0,k:2458,ppg25:11.0,ppg24:12.2,ppg23:5.7,g25:17},
  {n:'Courtland Sutton',t:'DEN',p:'WR',a:30.4,k:1168,ppg25:10.7,ppg24:11.8,ppg23:10.0,g25:17},
  {n:'Tee Higgins',t:'CIN',p:'WR',a:27.2,k:3341,ppg25:12.1,ppg24:15.5,ppg23:9.7,g25:15},
  {n:'A.J. Brown',t:'PHI',p:'WR',a:28.7,k:3159,ppg25:12.1,ppg24:14.1,ppg23:13.9,g25:15},
  {n:'Tetairoa McMillan',t:'CAR',p:'WR',a:23.0,k:4796,ppg25:10.4,ppg24:0,ppg23:0,g25:17},
  {n:"Wan'Dale Robinson",t:'TEN',p:'WR',a:25.2,k:1411,ppg25:10.7,ppg24:8.0,ppg23:6.9,g25:16},
  {n:'Drake London',t:'ATL',p:'WR',a:24.6,k:5198,ppg25:14.0,ppg24:13.6,ppg23:8.7,g25:12},
  {n:'Emeka Egbuka',t:'TB',p:'WR',a:23.4,k:3249,ppg25:9.7,ppg24:0,ppg23:0,g25:17},
  {n:"Ja'Marr Chase",t:'CIN',p:'WR',a:26.0,k:8435,ppg25:15.7,ppg24:20.0,ppg23:18.1,g25:17},
  {n:'CeeDee Lamb',t:'DAL',p:'WR',a:26.9,k:6588,ppg25:11.7,ppg24:14.2,ppg23:19.7,g25:14},
  {n:'DeVonta Smith',t:'PHI',p:'WR',a:27.3,k:3294,ppg25:9.6,ppg24:12.7,ppg23:11.7,g25:17},
  {n:'Michael Pittman Jr.',t:'PIT',p:'WR',a:28.4,k:909,ppg25:9.6,ppg24:8.2,ppg23:12.2,g25:17},
  {n:'Jaylen Waddle',t:'DEN',p:'WR',a:27.3,k:2180,ppg25:10.1,ppg24:7.5,ppg23:11.6,g25:16},
  {n:'Alec Pierce',t:'IND',p:'WR',a:25.9,k:1722,ppg25:10.7,ppg24:8.9,ppg23:4.7,g25:15},
  {n:'Justin Jefferson',t:'MIN',p:'WR',a:27.04,k:6419,ppg25:9.4,ppg24:15.6,ppg23:16.8,g25:17},
  {n:'DK Metcalf',t:'PIT',p:'WR',a:28.3,k:1950,ppg25:10.5,ppg24:10.5,ppg23:12.0,g25:15},
  {n:'Parker Washington',t:'JAC',p:'WR',a:24.0,k:4357,ppg25:9.7,ppg24:4.8,ppg23:3.5,g25:16},
  {n:'Ladd McConkey',t:'LAC',p:'WR',a:24.4,k:2510,ppg25:9.2,ppg24:12.5,ppg23:0,g25:16},
  {n:"D.J. Moore",t:'BUF',p:'WR',a:28.9,k:2089,ppg25:8.5,ppg24:11.1,ppg23:14.0,g25:17},
  {n:'Troy Franklin',t:'DEN',p:'WR',a:23.5,k:453,ppg25:8.5,ppg24:3.3,ppg23:0,g25:17},
  {n:'Jakobi Meyers',t:'JAC',p:'WR',a:29.4,k:1359,ppg25:8.6,ppg24:11.6,ppg23:11.4,g25:16},
  {n:'Romeo Doubs',t:'NE',p:'WR',a:25.9,k:1380,ppg25:8.6,ppg24:8.4,ppg23:8.5,g25:16},
  {n:'Quentin Johnston',t:'LAC',p:'WR',a:24.5,k:1184,ppg25:10.4,ppg24:9.8,ppg23:4.4,g25:14},
  {n:'Khalil Shakir',t:'BUF',p:'WR',a:26.1,k:1310,ppg25:8.2,ppg24:9.6,ppg23:5.5,g25:16},
  {n:'Rome Odunze',t:'CHI',p:'WR',a:23.5,k:2227,ppg25:10.3,ppg24:6.9,ppg23:0,g25:12},
  {n:'Rashee Rice',t:'KC',p:'WR',a:25.9,k:2939,ppg25:15.5,ppg24:13.2,ppg23:10.8,g25:8},
  {n:'Christian Watson',t:'GB',p:'WR',a:26.8,k:3781,ppg25:11.5,ppg24:6.1,ppg23:9.7,g25:10},
  {n:'Brian Thomas Jr.',t:'JAC',p:'WR',a:23.4,k:1868,ppg25:8.2,ppg24:14.1,ppg23:0,g25:14},
  {n:'Jordan Addison',t:'MIN',p:'WR',a:24.1,k:1666,ppg25:8.2,ppg24:12.1,ppg23:11.0,g25:14},
  {n:'Luther Burden',t:'CHI',p:'WR',a:22.3,k:3414,ppg25:7.0,ppg24:0,ppg23:0,g25:15},
  {n:'Elic Ayomanor',t:'TEN',p:'WR',a:22.8,k:397,ppg25:6.0,ppg24:0,ppg23:0,g25:16},
  {n:'Terry McLaurin',t:'WAS',p:'WR',a:30.5,k:1283,ppg25:9.5,ppg24:13.3,ppg23:10.0,g25:10},
  {n:'Tre Harris',t:'LAC',p:'WR',a:24.0,k:1029,ppg25:3.2,ppg24:0,ppg23:0,g25:17},
  {n:'Jayden Higgins',t:'HOU',p:'WR',a:23.2,k:1417,ppg25:6.4,ppg24:0,ppg23:0,g25:17},
  {n:'Matthew Golden',t:'GB',p:'WR',a:22.6,k:4097,ppg25:4.0,ppg24:0,ppg23:0,g25:14},
  {n:'Ricky Pearsall',t:'SF',p:'WR',a:25.5,k:1309,ppg25:7.1,ppg24:7.1,ppg23:0,g25:10},
  {n:'Mike Evans',t:'SF',p:'WR',a:32.6,k:2147,ppg25:8.7,ppg24:14.5,ppg23:14.3,g25:8},
  {n:'Marvin Harrison Jr.',t:'ARI',p:'WR',a:23.6,k:2368,ppg25:8.9,ppg24:9.7,ppg23:0,g25:12},
  {n:'Garrett Wilson',t:'NYJ',p:'WR',a:25.6,k:4370,ppg25:11.6,ppg24:11.8,ppg23:9.7,g25:7},
  {n:'Xavier Worthy',t:'KC',p:'WR',a:22.9,k:1666,ppg25:6.4,ppg24:9.3,ppg23:0,g25:14},
  {n:'Keon Coleman',t:'BUF',p:'WR',a:22.5,k:1481,ppg25:6.4,ppg24:7.5,ppg23:0,g25:13},
  {n:'Josh Downs',t:'IND',p:'WR',a:24.6,k:1530,ppg25:6.7,ppg24:10.5,ppg23:7.2,g25:16},
  {n:'Travis Hunter',t:'JAC',p:'WR',a:22.8,k:1669,ppg25:7.1,ppg24:0,ppg23:0,g25:7},
  {n:'Brandon Aiyuk',t:'FA',p:'WR',a:28.0,k:236,ppg25:0,ppg24:7.5,ppg23:13.1,g25:0},
  {n:'Jalen Coker',t:'CAR',p:'WR',a:24.4,k:2749,ppg25:6.7,ppg24:7.0,ppg23:0,g25:11},
  {n:'Malik Nabers',t:'NYG',p:'WR',a:22.6,k:6827,ppg25:12.0,ppg24:14.6,ppg23:0,g25:4},
  {n:'Deebo Samuel',t:'FA',p:'WR',a:29.4,k:1284,ppg25:9.5,ppg24:8.5,ppg23:14.2,g25:16},
  {n:'Jauan Jennings',t:'FA',p:'WR',a:29.0,k:473,ppg25:9.7,ppg24:11.5,ppg23:3.2,g25:15},
  {n:'Stefon Diggs',t:'FA',p:'WR',a:32.0,k:1604,ppg25:9.9,ppg24:12.3,ppg23:13.0,g25:17},
  
  {n:'Jayden Reed',t:'GB',p:'WR',a:25.3,k:1309,ppg25:10.4,ppg24:12.8,ppg23:9.6,g25:16},
  {n:'Calvin Ridley',t:'TEN',p:'WR',a:30.7,k:119,ppg25:5.5,ppg24:7.2,ppg23:13.8,g25:7},
  {n:'Rashid Shaheed',t:'SEA',p:'WR',a:27.4,k:1069,ppg25:9.4,ppg24:6.8,ppg23:10.2,g25:17},
    {n:'Darnell Mooney',t:'ATL',p:'WR',a:27.8,k:121,ppg25:8.6,ppg24:9.2,ppg23:6.4,g25:16},
    {n:'Rashod Bateman',t:'BAL',p:'WR',a:25.8,k:453,ppg25:9.8,ppg24:8.6,ppg23:6.2,g25:14},
    {n:'Jalen McMillan',t:'TB',p:'WR',a:23.1,k:661,ppg25:7.8,ppg24:0,ppg23:0,g25:14},
  {n:'Isaac TeSlaa',t:'DET',p:'WR',a:23.8,k:830,ppg25:6.4,ppg24:0,ppg23:0,g25:15},
  {n:'Xavier Legette',t:'CAR',p:'WR',a:24.2,k:209,ppg25:7.2,ppg24:5.8,ppg23:0,g25:16},
  {n:'Devaughn Vele',t:'DEN',p:'WR',a:28.7,k:1172,ppg25:7.6,ppg24:4.2,ppg23:0,g25:14},
  {n:'Chimere Dike',t:'TEN',p:'WR',a:23.4,k:133,ppg25:5.8,ppg24:0,ppg23:0,g25:13},
      {n:'Jalen Nailor',t:'LV',p:'WR',a:26.8,k:269,ppg25:9.6,ppg24:7.8,ppg23:4.2,g25:15},
  {n:'Marvin Mims',t:'DEN',p:'WR',a:23.8,k:179,ppg25:6.8,ppg24:6.2,ppg23:3.4,g25:14},
  {n:'K.J. Osborn',t:'FA',p:'WR',a:28.4,k:150,ppg25:6.2,ppg24:5.4,ppg23:8.6,g25:12},
  {n:'Dontayvion Wicks',t:'GB',p:'WR',a:24.4,k:1015,ppg25:7.4,ppg24:5.8,ppg23:4.2,g25:15},
  // TEs
  {n:'Trey McBride',t:'ARI',p:'TE',a:26.3,k:6482,ppg25:18.6,ppg24:15.6,ppg23:10.7,g25:17},
  {n:'Brock Bowers',t:'LV',p:'TE',a:23.3,k:7545,ppg25:14.7,ppg24:15.5,ppg23:0,g25:12},
  {n:'George Kittle',t:'SF',p:'TE',a:32.4,k:2879,ppg25:14.7,ppg24:15.8,ppg23:12.7,g25:11},
  {n:'Sam LaPorta',t:'DET',p:'TE',a:25.2,k:3458,ppg25:11.9,ppg24:10.9,ppg23:14.1,g25:9},
  {n:'Kyle Pitts',t:'ATL',p:'TE',a:25.4,k:2148,ppg25:12.4,ppg24:7.7,ppg23:8.1,g25:17},
  {n:'Travis Kelce',t:'KC',p:'TE',a:36.4,k:1652,ppg25:11.4,ppg24:12.2,ppg23:14.6,g25:17},
  {n:'Tyler Warren',t:'IND',p:'TE',a:23.8,k:4032,ppg25:11.1,ppg24:0,ppg23:0,g25:17},
  {n:'Harold Fannin Jr.',t:'CLE',p:'TE',a:21.7,k:2571,ppg25:11.7,ppg24:0,ppg23:0,g25:16},
  {n:'Dallas Goedert',t:'PHI',p:'TE',a:31.2,k:1542,ppg25:12.3,ppg24:10.4,ppg23:9.7,g25:15},
  {n:'Juwan Johnson',t:'NO',p:'TE',a:29.5,k:1491,ppg25:10.6,ppg24:7.2,ppg23:7.5,g25:17},
  {n:'Hunter Henry',t:'NE',p:'TE',a:31.3,k:1230,ppg25:10.5,ppg24:9.1,ppg23:8.6,g25:17},
  {n:'Dalton Schultz',t:'HOU',p:'TE',a:29.7,k:1018,ppg25:10.5,ppg24:7.0,ppg23:10.0,g25:17},
  {n:'Colston Loveland',t:'CHI',p:'TE',a:21.9,k:3868,ppg25:10.3,ppg24:0,ppg23:0,g25:16},
  {n:'AJ Barner',t:'SEA',p:'TE',a:23.9,k:1099,ppg25:8.7,ppg24:4.6,ppg23:0,g25:17},
  {n:'Oronde Gadsden',t:'LAC',p:'TE',a:22.7,k:1216,ppg25:8.8,ppg24:0,ppg23:0,g25:15},
  {n:'Mark Andrews',t:'BAL',p:'TE',a:30.5,k:1183,ppg25:7.7,ppg24:11.1,ppg23:13.5,g25:17},
  {n:'Theo Johnson',t:'NYG',p:'TE',a:25.0,k:138,ppg25:8.5,ppg24:5.7,ppg23:0,g25:15},
  {n:'Dalton Kincaid',t:'BUF',p:'TE',a:26.4,k:2160,ppg25:10.5,ppg24:7.8,ppg23:9.4,g25:12},
  {n:'Chigoziem Okonkwo',t:'WAS',p:'TE',a:26.5,k:1459,ppg25:7.3,ppg24:6.7,ppg23:6.7,g25:17},
  {n:'Cade Otton',t:'TB',p:'TE',a:26.9,k:696,ppg25:7.6,ppg24:10.0,ppg23:6.9,g25:16},
  {n:'Brenton Strange',t:'JAC',p:'TE',a:25.2,k:1855,ppg25:9.8,ppg24:5.4,ppg23:0,g25:12},
  {n:'Tucker Kraft',t:'GB',p:'TE',a:25.4,k:2931,ppg25:14.7,ppg24:9.6,ppg23:4.6,g25:8},
  {n:'Pat Freiermuth',t:'PIT',p:'TE',a:27.4,k:1348,ppg25:6.7,ppg24:9.9,ppg23:6.4,g25:17},
  {n:'T.J. Hockenson',t:'MIN',p:'TE',a:28.7,k:1409,ppg25:7.5,ppg24:8.7,ppg23:14.6,g25:15},
  {n:'Evan Engram',t:'DEN',p:'TE',a:31.5,k:332,ppg25:6.4,ppg24:9.9,ppg23:13.5,g25:16},
  {n:'Gunnar Helm',t:'TEN',p:'TE',a:23.5,k:449,ppg25:5.7,ppg24:0,ppg23:0,g25:16},
  {n:'Mason Taylor',t:'NYJ',p:'TE',a:21.9,k:633,ppg25:6.8,ppg24:0,ppg23:0,g25:13},
  {n:'Isaiah Likely',t:'NYG',p:'TE',a:25.9,k:3368,ppg25:4.4,ppg24:7.7,ppg23:5.9,g25:14},
  {n:'Cole Kmet',t:'CHI',p:'TE',a:26.6,k:245,ppg25:8.4,ppg24:8.8,ppg23:6.4,g25:16},
  {n:'Jake Ferguson',t:'DAL',p:'TE',a:26.2,k:1309,ppg25:9.2,ppg24:9.4,ppg23:10.8,g25:17},
  {n:'Dawson Knox',t:'BUF',p:'TE',a:30.2,k:2400,ppg25:7.8,ppg24:6.4,ppg23:8.2,g25:14},
  {n:'Noah Fant',t:'NO',p:'TE',a:27.4,k:171,ppg25:6.8,ppg24:8.2,ppg23:7.6,g25:15},
  {n:'Jonnu Smith',t:'ATL',p:'TE',a:30.0,k:1800,ppg25:7.4,ppg24:9.6,ppg23:6.2,g25:14},
  {n:'Charlie Kolar',t:'LAC',p:'TE',a:27.4,k:129,ppg25:7.2,ppg24:5.8,ppg23:3.4,g25:16},
  {n:'Elijah Higgins',t:'ARI',p:'TE',a:24.8,k:41,ppg25:5.6,ppg24:4.2,ppg23:0,g25:15},
    // Batch 4-7 — WRs
  {n:'Jalen Tolbert',t:'DAL',p:'WR',a:26.3,k:22,ppg25:5.6,ppg24:13.5,ppg23:8.6,g25:13},
  {n:'Christian Kirk',t:'FA',p:'WR',a:28.8,k:752,ppg25:5.8,ppg24:11.0,ppg23:9.1,g25:14},
  {n:'Jack Bech',t:'LV',p:'WR',a:23.5,k:413,ppg25:5.2,ppg24:0,ppg23:0,g25:12},
  {n:'Jerry Jeudy',t:'CLE',p:'WR',a:26.9,k:718,ppg25:9.6,ppg24:11.5,ppg23:12.6,g25:18},
  {n:'Cooper Kupp',t:'SEA',p:'WR',a:33.1,k:478,ppg25:10.2,ppg24:11.8,ppg23:11.2,g25:17},
  {n:'Tez Johnson',t:'TB',p:'WR',a:23.3,k:264,ppg25:9.3,ppg24:0,ppg23:0,g25:17},
  {n:'Chris Godwin',t:'FA',p:'WR',a:30.4,k:1133,ppg25:12.5,ppg24:16.1,ppg23:9.9,g25:10},
  {n:'Cedric Tillman',t:'CLE',p:'WR',a:24.4,k:1900,ppg25:5.2,ppg24:11.9,ppg23:5.5,g25:14},
  {n:'Pat Bryant',t:'DEN',p:'WR',a:23.2,k:1214,ppg25:7.8,ppg24:0,ppg23:0,g25:15},
  {n:'Tre Tucker',t:'LV',p:'WR',a:25.6,k:1474,ppg25:11.9,ppg24:11.5,ppg23:7.2,g25:18},
  {n:'Kyle Williams',t:'NE',p:'WR',a:23.4,k:514,ppg25:5.2,ppg24:0,ppg23:0,g25:17},
  {n:'Tank Dell',t:'HOU',p:'WR',a:24.1,k:1257,ppg25:0,ppg24:14.7,ppg23:14.2,g25:0},
  {n:'DeMario Douglas',t:'NE',p:'WR',a:25.4,k:1016,ppg25:8.4,ppg24:12.6,ppg23:10.6,g25:18},
  {n:'Adonai Mitchell',t:'IND',p:'WR',a:23.4,k:1268,ppg25:8.1,ppg24:4.9,ppg23:0,g25:17},
  {n:'Jaylin Noel',t:'IND',p:'WR',a:22.8,k:1253,ppg25:6.5,ppg24:0,ppg23:0,g25:17},
  {n:'Malik Washington',t:'MIA',p:'WR',a:24.6,k:1339,ppg25:9.7,ppg24:5.9,ppg23:0,g25:18},
  {n:'Kayshon Boutte',t:'NE',p:'WR',a:23.8,k:478,ppg25:12.7,ppg24:12.4,ppg23:0,g25:15},
  {n:'Michael Wilson',t:'ARI',p:'WR',a:25.8,k:2488,ppg25:10.7,ppg24:11.2,ppg23:13.0,g25:18},
  {n:'Darius Slayton',t:'NYG',p:'WR',a:28.6,k:1400,ppg25:10.2,ppg24:10.1,ppg23:13.4,g25:15},
  {n:'Marquise Brown',t:'FA',p:'WR',a:28.8,k:47,ppg25:11.8,ppg24:6.8,ppg23:13.1,g25:17},
  // Batch 4-7 — RBs
  {n:'Tyrone Tracy',t:'NYG',p:'RB',a:24.8,k:1046,ppg25:9.5,ppg24:9.6,ppg23:0,g25:16},
  {n:'Brian Robinson',t:'WAS',p:'RB',a:27.0,k:1221,ppg25:6.9,ppg24:10.7,ppg23:12.0,g25:17},
  {n:'George Holani',t:'LV',p:'RB',a:25.2,k:318,ppg25:6.6,ppg24:0,ppg23:0,g25:6},
  {n:'Keaton Mitchell',t:'CLE',p:'RB',a:24.2,k:863,ppg25:7.3,ppg24:4.2,ppg23:16.4,g25:14},
  {n:'Chris Rodriguez',t:'JAC',p:'RB',a:25.4,k:825,ppg25:12.9,ppg24:8.9,ppg23:9.1,g25:14},
  {n:'Sean Tucker',t:'TB',p:'RB',a:25.3,k:197,ppg25:13.5,ppg24:10.7,ppg23:2.1,g25:13},
  {n:'Ray Davis',t:'BUF',p:'RB',a:24.6,k:264,ppg25:6.6,ppg24:12.0,ppg23:0,g25:18},
  {n:'Tyler Allgeier',t:'ARI',p:'RB',a:25.4,k:1222,ppg25:12.9,ppg24:11.1,ppg23:14.3,g25:18},
  // Batch 4-7 — TEs
  {n:'Greg Dulcich',t:'FA',p:'TE',a:26.4,k:449,ppg25:10.2,ppg24:1.1,ppg23:2.3,g25:11},
  {n:'David Njoku',t:'FA',p:'TE',a:28.8,k:175,ppg25:12.4,ppg24:13.5,ppg23:12.6,g25:12},
  {n:'Colby Parkinson',t:'LAR',p:'TE',a:26.8,k:369,ppg25:8.6,ppg24:6.0,ppg23:6.1,g25:15},
  {n:'Terrance Ferguson',t:'LAR',p:'TE',a:23.8,k:1687,ppg25:7.8,ppg24:0,ppg23:0,g25:13},
  {n:'Jake Tonges',t:'SF',p:'TE',a:26.8,k:88,ppg25:9.9,ppg24:0,ppg23:0,g25:17},
  {n:'Michael Mayer',t:'LV',p:'TE',a:24.2,k:1401,ppg25:9.8,ppg24:6.1,ppg23:9.6,g25:14},
  {n:'JaTavion Sanders',t:'CAR',p:'TE',a:23.8,k:71,ppg25:6.8,ppg24:8.2,ppg23:0,g25:13},
  {n:'Ben Sinnott',t:'WAS',p:'TE',a:25.0,k:66,ppg25:3.3,ppg24:1.9,ppg23:0,g25:17},
  {n:'Zach Ertz',t:'WAS',p:'TE',a:35.8,k:18,ppg25:16.6,ppg24:10.4,ppg23:10.1,g25:13},
  // Batch 4-7 — QBs
  {n:'Mac Jones',t:'NE',p:'QB',a:27.8,k:730,ppg25:0,ppg24:8.2,ppg23:11.4,g25:0},
  {n:'Joe Flacco',t:'CIN',p:'QB',a:41.8,k:115,ppg25:0,ppg24:0,ppg23:14.2,g25:0},
  {n:'Justin Fields',t:'KC',p:'QB',a:26.8,k:281,ppg25:15.4,ppg24:19.2,ppg23:0,g25:9},
  {n:'Kirk Cousins',t:'LV',p:'QB',a:37.9,k:1622,ppg25:10.9,ppg24:13.7,ppg23:19.4,g25:10},  // data fix 2026-06-28: was 0/25.6/0,g25:0 (bad join; 25.6 = Lamar's value)
  // 2026 Rookies — post-draft Round 1
  {n:'Fernando Mendoza',t:'LV',p:'QB',a:23,k:3837,ppg25:0.0,ppg24:0,ppg23:0,g25:0},
  {n:'Jeremiyah Love',t:'ARI',p:'RB',a:22,k:5369,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Carnell Tate',t:'TEN',p:'WR',a:21,k:3631,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jordyn Tyson',t:'NO',p:'WR',a:23,k:3140,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Ty Simpson',t:'LAR',p:'QB',a:23,k:2073,ppg25:0.0,ppg24:0,ppg23:0,g25:0},
  {n:'Kenyon Sadiq',t:'NYJ',p:'TE',a:21,k:2301,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Makai Lemon',t:'PHI',p:'WR',a:22,k:2182,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'KC Concepcion',t:'CLE',p:'WR',a:22,k:2404,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Omar Cooper',t:'NYJ',p:'WR',a:22,k:2102,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jadarian Price',t:'SEA',p:'RB',a:22,k:2299,ppg25:0,ppg24:0,ppg23:0,g25:0},
  // 2026 Rookies — Day 2 & 3 picks
  {n:"De'Zhaun Stribling",t:'SF',p:'WR',a:24,k:1844,ppg25:7.2,ppg24:0,ppg23:0,g25:0},
  {n:'Denzel Boston',t:'CLE',p:'WR',a:23,k:2647,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Germie Bernard',t:'PIT',p:'WR',a:23,k:2365,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Eli Stowers',t:'PHI',p:'TE',a:24,k:1406,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Marlin Klein',t:'HOU',p:'TE',a:24,k:117,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Max Klare',t:'LAR',p:'TE',a:23,k:420,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Carson Beck',t:'ARI',p:'QB',a:24,k:1412,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Sam Roush',t:'CHI',p:'TE',a:24,k:129,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Antonio Williams',t:'WAS',p:'WR',a:23,k:1790,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Oscar Delp',t:'NO',p:'TE',a:23,k:341,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Malachi Fields',t:'NYG',p:'WR',a:23,k:1287,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Zachariah Branch',t:'ATL',p:'WR',a:22,k:726,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:"Ja'Kobi Lane",t:'BAL',p:'WR',a:23,k:1656,ppg25:6.4,ppg24:0,ppg23:0,g25:0},
  {n:'Chris Brazzell II',t:'CAR',p:'WR',a:23,k:680,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Ted Hurst',t:'TB',p:'WR',a:24,k:1248,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Drew Allar',t:'PIT',p:'QB',a:24,k:785,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Will Kacmarek',t:'MIA',p:'TE',a:24,k:79,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Chris Bell',t:'MIA',p:'WR',a:23,k:1426,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Eli Raridon',t:'NE',p:'TE',a:24,k:1415,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Caleb Douglas',t:'MIA',p:'WR',a:23,k:1242,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Zavion Thomas',t:'CHI',p:'WR',a:23,k:337,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Kaelon Black',t:'SF',p:'RB',a:23,k:1374,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Barion Brown',t:'NO',p:'WR',a:23,k:132,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Cyrus Allen',t:'KC',p:'WR',a:24,k:1124,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Reggie Virgil',t:'ARI',p:'WR',a:24,k:134,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Kendrick Law',t:'DET',p:'WR',a:23,k:150,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Kaden Wetjen',t:'PIT',p:'WR',a:24,k:141,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Colbie Young',t:'CIN',p:'WR',a:24,k:124,ppg25:0,ppg24:0,ppg23:0,g25:0},
  // Missing rookies — added from draft results
  {n:'Nicholas Singleton',t:'TEN',p:'RB',a:23,k:904,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Emmett Johnson',t:'KC',p:'RB',a:24,k:1521,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jonah Coleman',t:'DEN',p:'RB',a:24,k:1837,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Mike Washington Jr.',t:'LV',p:'RB',a:24,k:1592,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Adam Randall',t:'BAL',p:'RB',a:22,k:357,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Kaytron Allen',t:'WAS',p:'RB',a:23,k:348,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Demond Claiborne',t:'MIN',p:'RB',a:23,k:436,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Deion Burks',t:'IND',p:'WR',a:23,k:93,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Garrett Nussmeier',t:'KC',p:'QB',a:23,k:89,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Cade Klubnik',t:'NYJ',p:'QB',a:23,k:425,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Taylen Green',t:'CLE',p:'QB',a:25,k:83,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Bryce Lance',t:'NO',p:'WR',a:24,k:336,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Elijah Sarratt',t:'BAL',p:'WR',a:24,k:392,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Skyler Bell',t:'BUF',p:'WR',a:24,k:511,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Brenen Thompson',t:'LAC',p:'WR',a:24,k:138,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Justin Joly',t:'DEN',p:'TE',a:24,k:103,ppg25:0,ppg24:0,ppg23:0,g25:0},
  // === UNIVERSE EXPANSION (FantasyCalc full list) — seeded; pipeline populates stats/age ===
  {n:'Deshaun Watson',t:'CLE',p:'QB',a:25,k:1766,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Anthony Richardson',t:'IND',p:'QB',a:25,k:875,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jalen Milroe',t:'SEA',p:'QB',a:25,k:314,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Will Howard',t:'PIT',p:'QB',a:25,k:137,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Cole Payton',t:'PHI',p:'QB',a:25,k:241,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Marcus Mariota',t:'WAS',p:'QB',a:25,k:340,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Riley Leonard',t:'IND',p:'QB',a:25,k:87,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Quinn Ewers',t:'MIA',p:'QB',a:25,k:143,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jameis Winston',t:'NYG',p:'QB',a:25,k:686,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Joe Milton',t:'DAL',p:'QB',a:25,k:663,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Dillon Gabriel',t:'CLE',p:'QB',a:25,k:130,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Gardner Minshew',t:'ARI',p:'QB',a:25,k:118,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Kenny Pickett',t:'CAR',p:'QB',a:25,k:115,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Tyler Huntley',t:'BAL',p:'QB',a:25,k:976,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Will Levis',t:'TEN',p:'QB',a:25,k:110,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Tyson Bagent',t:'CHI',p:'QB',a:25,k:231,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Trey Lance',t:'LAC',p:'QB',a:25,k:79,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Tyrod Taylor',t:'GB',p:'QB',a:25,k:64,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Davis Mills',t:'HOU',p:'QB',a:25,k:56,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Tanner McKee',t:'PHI',p:'QB',a:25,k:1272,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Kaleb Johnson',t:'PIT',p:'RB',a:24,k:482,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jordan James',t:'SF',p:'RB',a:24,k:94,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Eli Heidenreich',t:'PIT',p:'RB',a:24,k:51,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jaydon Blue',t:'DAL',p:'RB',a:24,k:67,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:"J'Mari Taylor",t:'JAC',p:'RB',a:24,k:639,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Seth McGowan',t:'IND',p:'RB',a:24,k:1124,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'DJ Giddens',t:'IND',p:'RB',a:24,k:161,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jam Miller',t:'NE',p:'RB',a:24,k:532,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Emanuel Wilson',t:'SEA',p:'RB',a:24,k:1098,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Devin Neal',t:'NO',p:'RB',a:24,k:83,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'LeQuint Allen',t:'JAC',p:'RB',a:24,k:147,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Trevor Etienne',t:'CAR',p:'RB',a:24,k:147,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Tahj Brooks',t:'CIN',p:'RB',a:24,k:42,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Chris Brooks',t:'GB',p:'RB',a:24,k:78,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Robert Henry',t:'WAS',p:'RB',a:24,k:313,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Isaiah Davis',t:'NYJ',p:'RB',a:24,k:146,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Roman Hemby',t:'LV',p:'RB',a:24,k:301,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Brashard Smith',t:'KC',p:'RB',a:24,k:41,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Najee Harris',t:'None',p:'RB',a:24,k:255,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Joe Mixon',t:'None',p:'RB',a:24,k:194,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Malik Davis',t:'DAL',p:'RB',a:24,k:112,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Kendre Miller',t:'NO',p:'RB',a:24,k:944,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jarquez Hunter',t:'LAR',p:'RB',a:24,k:168,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Justice Hill',t:'BAL',p:'RB',a:24,k:296,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Emari Demercado',t:'KC',p:'RB',a:24,k:141,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Ty Johnson',t:'BUF',p:'RB',a:24,k:83,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Devin Singletary',t:'NYG',p:'RB',a:24,k:136,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jerome Ford',t:'WAS',p:'RB',a:24,k:110,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Will Shipley',t:'PHI',p:'RB',a:24,k:246,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Phil Mafah',t:'DAL',p:'RB',a:24,k:80,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Damien Martinez',t:'GB',p:'RB',a:24,k:74,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Samaje Perine',t:'CIN',p:'RB',a:24,k:543,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Michael Carter',t:'TEN',p:'RB',a:24,k:53,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Zonovan Knight',t:'ARI',p:'RB',a:24,k:289,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Roschon Johnson',t:'CHI',p:'RB',a:24,k:804,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Kenny McIntosh',t:'SEA',p:'RB',a:24,k:36,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Nick Chubb',t:'None',p:'RB',a:24,k:34,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Austin Ekeler',t:'None',p:'RB',a:24,k:165,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Raheim Sanders',t:'CLE',p:'RB',a:24,k:159,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Michael Trigg',t:'DAL',p:'TE',a:24,k:27,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Elijah Arroyo',t:'SEA',p:'TE',a:24,k:245,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jack Endries',t:'CIN',p:'TE',a:24,k:625,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Matt Hibner',t:'BAL',p:'TE',a:24,k:350,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Tanner Koziol',t:'JAC',p:'TE',a:24,k:457,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'John Michael Gyllenborg',t:'KC',p:'TE',a:24,k:270,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Darnell Washington',t:'PIT',p:'TE',a:24,k:512,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jaren Kanak',t:'TEN',p:'TE',a:24,k:229,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Mike Gesicki',t:'CIN',p:'TE',a:24,k:848,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Nate Boerkircher',t:'JAC',p:'TE',a:24,k:116,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Luke Musgrave',t:'GB',p:'TE',a:24,k:57,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Joe Royer',t:'CLE',p:'TE',a:24,k:113,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Noah Gray',t:'KC',p:'TE',a:24,k:68,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Tyler Higbee',t:'LAR',p:'TE',a:24,k:1054,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Erick All',t:'CIN',p:'TE',a:24,k:70,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Tory Horton',t:'SEA',p:'WR',a:24,k:403,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Tyreek Hill',t:'None',p:'WR',a:24,k:752,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Kevin Coleman',t:'MIA',p:'WR',a:24,k:195,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Ryan Flournoy',t:'DAL',p:'WR',a:24,k:868,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'CJ Daniels',t:'LAR',p:'WR',a:24,k:84,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:"Dont'e Thornton",t:'LV',p:'WR',a:24,k:119,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Isaiah Bond',t:'CLE',p:'WR',a:24,k:186,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jalen Royals',t:'KC',p:'WR',a:24,k:289,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Josh Cameron',t:'JAC',p:'WR',a:24,k:715,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jeff Caldwell',t:'KC',p:'WR',a:24,k:257,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jaylin Lane',t:'WAS',p:'WR',a:24,k:80,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jahan Dotson',t:'ATL',p:'WR',a:24,k:446,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Tyquan Thornton',t:'KC',p:'WR',a:24,k:275,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Malik Benson',t:'LV',p:'WR',a:24,k:87,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Savion Williams',t:'GB',p:'WR',a:24,k:237,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Odell Beckham',t:'None',p:'WR',a:24,k:18,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Andrei Iosivas',t:'CIN',p:'WR',a:24,k:84,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Calvin Austin',t:'NYG',p:'WR',a:24,k:142,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'KeAndre Lambert-Smith',t:'LAC',p:'WR',a:24,k:56,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'John Metchie',t:'CAR',p:'WR',a:24,k:57,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Luke McCaffrey',t:'WAS',p:'WR',a:24,k:125,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Noah Thomas',t:'CIN',p:'WR',a:24,k:122,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Keenan Allen',t:'None',p:'WR',a:24,k:1088,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Treylon Burks',t:'WAS',p:'WR',a:24,k:376,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jahdae Walker',t:'CHI',p:'WR',a:24,k:104,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:"Ja'Lynn Polk",t:'NO',p:'WR',a:24,k:99,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'KaVontae Turpin',t:'DAL',p:'WR',a:24,k:65,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Xavier Hutchinson',t:'HOU',p:'WR',a:24,k:131,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Kendrick Bourne',t:'ARI',p:'WR',a:24,k:955,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Roman Wilson',t:'PIT',p:'WR',a:24,k:910,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Mack Hollins',t:'NE',p:'WR',a:24,k:172,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Tai Felton',t:'MIN',p:'WR',a:24,k:38,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jimmy Horn',t:'CAR',p:'WR',a:24,k:61,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Konata Mumpfield',t:'LAR',p:'WR',a:24,k:816,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Arian Smith',t:'NYJ',p:'WR',a:24,k:47,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jordan Whittington',t:'LAR',p:'WR',a:24,k:47,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Xavier Restrepo',t:'TEN',p:'WR',a:24,k:42,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Joshua Palmer',t:'BUF',p:'WR',a:24,k:67,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Kameron Johnson',t:'TB',p:'WR',a:24,k:28,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Tutu Atwell',t:'MIA',p:'WR',a:24,k:27,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Olamide Zaccheaus',t:'ATL',p:'WR',a:24,k:17,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jacob Cowing',t:'SF',p:'WR',a:24,k:49,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Efton Chism',t:'NE',p:'WR',a:24,k:429,ppg25:0,ppg24:0,ppg23:0,g25:0},
];

const PICKS=[
  {n:'2026 1.01',k:6941,ip:true},
  {n:'2026 1.02',k:6294,ip:true},
  {n:'2026 1.03',k:5647,ip:true},
  {n:'2026 1.04',k:5000,ip:true},
  {n:'2026 1.05',k:5133,ip:true},
  {n:'2026 1.06',k:4880,ip:true},
  {n:'2026 1.07',k:4626,ip:true},
  {n:'2026 1.08',k:4373,ip:true},
  {n:'2026 1.09',k:4191,ip:true},
  {n:'2026 1.10',k:4033,ip:true},
  {n:'2026 1.11',k:3875,ip:true},
  {n:'2026 1.12',k:3717,ip:true},
  {n:'2026 Early 1st Round Pick',k:5882,ip:true,hidden:true},
  {n:'2026 Mid 1st Round Pick',k:4753,ip:true,hidden:true},
  {n:'2026 Late 1st Round Pick',k:3954,ip:true,hidden:true},
  {n:'2026 2.01',k:3959,ip:true},
  {n:'2026 2.02',k:3590,ip:true},
  {n:'2026 2.03',k:3221,ip:true},
  {n:'2026 2.04',k:2852,ip:true},
  {n:'2026 2.05',k:3285,ip:true},
  {n:'2026 2.06',k:3123,ip:true},
  {n:'2026 2.07',k:2961,ip:true},
  {n:'2026 2.08',k:2799,ip:true},
  {n:'2026 2.09',k:3007,ip:true},
  {n:'2026 2.10',k:2894,ip:true},
  {n:'2026 2.11',k:2780,ip:true},
  {n:'2026 2.12',k:2667,ip:true},
  {n:'2026 Early 2nd Round Pick',k:3355,ip:true,hidden:true},
  {n:'2026 Mid 2nd Round Pick',k:3042,ip:true,hidden:true},
  {n:'2026 Late 2nd Round Pick',k:2837,ip:true,hidden:true},
  {n:'2026 3.01',k:2805,ip:true},
  {n:'2026 3.02',k:2543,ip:true},
  {n:'2026 3.03',k:2282,ip:true},
  {n:'2026 3.04',k:2020,ip:true},
  {n:'2026 3.05',k:2454,ip:true},
  {n:'2026 3.06',k:2333,ip:true},
  {n:'2026 3.07',k:2211,ip:true},
  {n:'2026 3.08',k:2090,ip:true},
  {n:'2026 3.09',k:2280,ip:true},
  {n:'2026 3.10',k:2194,ip:true},
  {n:'2026 3.11',k:2108,ip:true},
  {n:'2026 3.12',k:2022,ip:true},
  {n:'2026 Early 3rd Round Pick',k:2377,ip:true,hidden:true},
  {n:'2026 Mid 3rd Round Pick',k:2272,ip:true,hidden:true},
  {n:'2026 Late 3rd Round Pick',k:2151,ip:true,hidden:true},
  {n:'2027 1.01',k:8031,ip:true},
  {n:'2027 1.02',k:7282,ip:true},
  {n:'2027 1.03',k:6534,ip:true},
  {n:'2027 1.04',k:5785,ip:true},
  {n:'2027 1.05',k:5988,ip:true},
  {n:'2027 1.06',k:5692,ip:true},
  {n:'2027 1.07',k:5396,ip:true},
  {n:'2027 1.08',k:5100,ip:true},
  {n:'2027 1.09',k:5118,ip:true},
  {n:'2027 1.10',k:4925,ip:true},
  {n:'2027 1.11',k:4731,ip:true},
  {n:'2027 1.12',k:4538,ip:true},
  {n:'2027 Early 1st Round Pick',k:6806,ip:true,hidden:true},
  {n:'2027 Mid 1st Round Pick',k:5544,ip:true,hidden:true},
  {n:'2027 Late 1st Round Pick',k:4828,ip:true,hidden:true},
  {n:'2027 2.01',k:4404,ip:true},
  {n:'2027 2.02',k:3993,ip:true},
  {n:'2027 2.03',k:3583,ip:true},
  {n:'2027 2.04',k:3172,ip:true},
  {n:'2027 2.05',k:3728,ip:true},
  {n:'2027 2.06',k:3544,ip:true},
  {n:'2027 2.07',k:3360,ip:true},
  {n:'2027 2.08',k:3176,ip:true},
  {n:'2027 2.09',k:3272,ip:true},
  {n:'2027 2.10',k:3149,ip:true},
  {n:'2027 2.11',k:3025,ip:true},
  {n:'2027 2.12',k:2902,ip:true},
  {n:'2027 Early 2nd Round Pick',k:3732,ip:true,hidden:true},
  {n:'2027 Mid 2nd Round Pick',k:3452,ip:true,hidden:true},
  {n:'2027 Late 2nd Round Pick',k:3087,ip:true,hidden:true},
  {n:'2027 3.01',k:3030,ip:true},
  {n:'2027 3.02',k:2748,ip:true},
  {n:'2027 3.03',k:2465,ip:true},
  {n:'2027 3.04',k:2183,ip:true},
  {n:'2027 3.05',k:2587,ip:true},
  {n:'2027 3.06',k:2459,ip:true},
  {n:'2027 3.07',k:2331,ip:true},
  {n:'2027 3.08',k:2203,ip:true},
  {n:'2027 3.09',k:2345,ip:true},
  {n:'2027 3.10',k:2256,ip:true},
  {n:'2027 3.11',k:2168,ip:true},
  {n:'2027 3.12',k:2079,ip:true},
  {n:'2027 Early 3rd Round Pick',k:2568,ip:true,hidden:true},
  {n:'2027 Mid 3rd Round Pick',k:2395,ip:true,hidden:true},
  {n:'2027 Late 3rd Round Pick',k:2212,ip:true,hidden:true},
  {n:'2028 1.01',k:5889,ip:true},
  {n:'2028 1.02',k:5340,ip:true},
  {n:'2028 1.03',k:4791,ip:true},
  {n:'2028 1.04',k:4242,ip:true},
  {n:'2028 1.05',k:4802,ip:true},
  {n:'2028 1.06',k:4565,ip:true},
  {n:'2028 1.07',k:4327,ip:true},
  {n:'2028 1.08',k:4090,ip:true},
  {n:'2028 1.09',k:4176,ip:true},
  {n:'2028 1.10',k:4019,ip:true},
  {n:'2028 1.11',k:3861,ip:true},
  {n:'2028 1.12',k:3704,ip:true},
  {n:'2028 Early 1st Round Pick',k:4991,ip:true,hidden:true},
  {n:'2028 Mid 1st Round Pick',k:4446,ip:true,hidden:true},
  {n:'2028 Late 1st Round Pick',k:3940,ip:true,hidden:true},
  {n:'2028 2.01',k:3647,ip:true},
  {n:'2028 2.02',k:3307,ip:true},
  {n:'2028 2.03',k:2967,ip:true},
  {n:'2028 2.04',k:2627,ip:true},
  {n:'2028 2.05',k:3091,ip:true},
  {n:'2028 2.06',k:2938,ip:true},
  {n:'2028 2.07',k:2786,ip:true},
  {n:'2028 2.08',k:2633,ip:true},
  {n:'2028 2.09',k:2756,ip:true},
  {n:'2028 2.10',k:2652,ip:true},
  {n:'2028 2.11',k:2548,ip:true},
  {n:'2028 2.12',k:2444,ip:true},
  {n:'2028 Early 2nd Round Pick',k:3091,ip:true,hidden:true},
  {n:'2028 Mid 2nd Round Pick',k:2862,ip:true,hidden:true},
  {n:'2028 Late 2nd Round Pick',k:2600,ip:true,hidden:true},
  {n:'2028 3.01',k:2554,ip:true},
  {n:'2028 3.02',k:2316,ip:true},
  {n:'2028 3.03',k:2077,ip:true},
  {n:'2028 3.04',k:1839,ip:true},
  {n:'2028 3.05',k:2286,ip:true},
  {n:'2028 3.06',k:2173,ip:true},
  {n:'2028 3.07',k:2061,ip:true},
  {n:'2028 3.08',k:1948,ip:true},
  {n:'2028 3.09',k:2051,ip:true},
  {n:'2028 3.10',k:1974,ip:true},
  {n:'2028 3.11',k:1896,ip:true},
  {n:'2028 3.12',k:1819,ip:true},
  {n:'2028 Early 3rd Round Pick',k:2164,ip:true,hidden:true},
  {n:'2028 Mid 3rd Round Pick',k:2117,ip:true,hidden:true},
  {n:'2028 Late 3rd Round Pick',k:1935,ip:true,hidden:true}
];


// Ripple display entries {n,d,reason,delta}. Populated from data/ripple.json by
// loadRipples() — the SAME file that builds RP, so display and math share one
// data-backed source (no hand-authored phantom values, no drift).
let RIPPLE=[];

// ============================================================
// GAME LOG CONSISTENCY DATA
// Computed from user's weekly game log workbook
// Miss = (Hurt You + Did Not Factor) / games played
// Hit = (Serviceable through Game Winning) / games played
// Elite = (Great + Game Winning) / games played
// WR/RB tiers: 0-5.9 HY, 6-9.9 DNF, 10-13.9 Svc, 14-17.9 Good, 18-26.9 Great, 27+ GW
// QB tiers: 0-11.9 HY, 12-15.9 DNF, 16-18.9 Svc, 19-24.9 Good, 25-31.9 Great, 32+ GW
// ============================================================
// (legacy hardcoded GAME_LOG removed — game logs live in data/game-logs.json via glOf())
function glTag(n){
  const p=COMP.find(x=>x.n===n); const d=glOf(p);if(!d)return'';
  const mc=d.miss<=35?'var(--emerald)':d.miss<=50?'var(--topaz)':'var(--coral)';
  const hc=d.hit>=65?'var(--emerald)':d.hit>=50?'var(--sky)':'var(--fog)';
  const ec=d.elite>=25?'var(--emerald)':d.elite>=15?'var(--sky)':'var(--fog)';
  return`<span style="font-size:9px;display:inline-flex;gap:3px;margin-left:4px">` +
    `<span style="background:var(--panel);border:1px solid var(--line);border-radius:3px;padding:1px 4px;color:${mc}">M${d.miss}%</span>` +
    `<span style="background:var(--panel);border:1px solid var(--line);border-radius:3px;padding:1px 4px;color:${hc}">H${d.hit}%</span>` +
    `<span style="background:var(--panel);border:1px solid var(--line);border-radius:3px;padding:1px 4px;color:${ec}">E${d.elite}%</span>` +
    `</span>`;
}

// ============================================================
// ADDITIVE DELTA PROJECTION FORMULA (v5.6 fix)
// proj = base * age_curve * (1 + capped_delta)
// Each factor contributes a small delta — no multiplicative stacking
// Total delta capped at ±0.20 for projections, ±0.25 for model value
// Model value hard-capped at 9,999 to match market value ceiling
// ============================================================
// ── OFFENSE STYLE FACTORS (System Score v2 — validated 2022-25) ─────────────
// Three INDEPENDENT coordinator-identity signals that survived the three-tier
// trial in scripts/validate-style.py (contemporaneous + persistence + next-
// season predictive, incl. partial-correlation independence proofs):
//   motion%  → RB1-role production   r=+0.271** (beats RB1's own persistence)
//   TE2-snap → WR3+-role suppression r=−0.256*  (12-personnel squeezes 3-WR sets)
//   PROE     → WR-room environment   r=+0.274** (pass-lean lifts the whole room)
// Rejected with reasons: play-action, screens, RPO, pace, no-huddle, aDOT,
// two-back, RZ-pass (PROE's shadow). Tiers are 2025 terciles (−1/0/+1) from
// data/style-rates.json — REGENERATE each offseason (rerun the fetch workflow,
// recompute terciles). Style is the COORDINATOR'S property: teams with an OC
// change get the adjustment scaled ×0.4 toward neutral.
const PC_FINGERPRINT={"ARI":{"pc":"Mike LaFleur","yrs":1,"d":{"moti":{"v":47.3,"p":29},"pa_p":{"v":17.6,"p":10},"proe":{"v":-2.7,"p":48},"pass":{"v":64.5,"p":90},"two_":{"v":16.9,"p":42},"te2":{"v":51.2,"p":90},"play":{"v":64.9,"p":55},"adot":{"v":8.2,"p":65}}},"ATL":{"pc":"Tommy Rees","yrs":1,"d":{"moti":{"v":49.4,"p":39},"pa_p":{"v":22.0,"p":32},"proe":{"v":-3.2,"p":35},"pass":{"v":63.2,"p":68},"two_":{"v":12.2,"p":16},"te2":{"v":56.5,"p":100},"play":{"v":63.4,"p":39},"adot":{"v":6.8,"p":3}}},"BAL":{"pc":"Declan Doyle","yrs":0,"d":{"moti":{"v":53.6,"p":61},"pa_p":{"v":22.3,"p":39},"proe":{"v":-8.2,"p":0},"pass":{"v":53.6,"p":3},"two_":{"v":28.1,"p":97},"te2":{"v":54.4,"p":97},"play":{"v":58.5,"p":0},"adot":{"v":8.2,"p":68}}},"BUF":{"pc":"Joe Brady","yrs":2,"d":{"moti":{"v":56.0,"p":74},"pa_p":{"v":22.1,"p":35},"proe":{"v":-2.5,"p":52},"pass":{"v":57.3,"p":19},"two_":{"v":19.3,"p":55},"te2":{"v":46.8,"p":71},"play":{"v":63.9,"p":42},"adot":{"v":7.7,"p":39}}},"CAR":{"pc":"Brad Idzik","yrs":0,"d":{"moti":{"v":42.2,"p":13},"pa_p":{"v":21.9,"p":29},"proe":{"v":-5.3,"p":16},"pass":{"v":59.7,"p":48},"two_":{"v":12.3,"p":19},"te2":{"v":47.7,"p":74},"play":{"v":61.2,"p":10},"adot":{"v":6.7,"p":0}}},"CHI":{"pc":"Ben Johnson","yrs":4,"d":{"moti":{"v":56.1,"p":77},"pa_p":{"v":30.6,"p":100},"proe":{"v":-3.2,"p":39},"pass":{"v":57.6,"p":23},"two_":{"v":18.7,"p":45},"te2":{"v":48.5,"p":81},"play":{"v":66.9,"p":84},"adot":{"v":7.4,"p":32}}},"CIN":{"pc":"Zac Taylor","yrs":4,"d":{"moti":{"v":45.4,"p":23},"pa_p":{"v":16.5,"p":3},"proe":{"v":5.8,"p":97},"pass":{"v":67.5,"p":100},"two_":{"v":12.3,"p":23},"te2":{"v":41.7,"p":52},"play":{"v":64.9,"p":58},"adot":{"v":7.0,"p":10}}},"CLE":{"pc":"Todd Monken","yrs":3,"d":{"moti":{"v":49.5,"p":42},"pa_p":{"v":22.7,"p":45},"proe":{"v":-6.0,"p":10},"pass":{"v":54.3,"p":6},"two_":{"v":23.8,"p":81},"te2":{"v":48.2,"p":77},"play":{"v":62.1,"p":19},"adot":{"v":8.4,"p":77}}},"DAL":{"pc":"Brian Schottenheimer","yrs":1,"d":{"moti":{"v":58.8,"p":87},"pa_p":{"v":26.8,"p":90},"proe":{"v":-0.2,"p":71},"pass":{"v":63.1,"p":65},"two_":{"v":22.0,"p":74},"te2":{"v":33.1,"p":10},"play":{"v":68.6,"p":100},"adot":{"v":8.2,"p":71}}},"DEN":{"pc":"Davis Webb","yrs":0,"d":{"moti":{"v":46.4,"p":26},"pa_p":{"v":24.1,"p":71},"proe":{"v":2.1,"p":90},"pass":{"v":63.3,"p":77},"two_":{"v":21.0,"p":65},"te2":{"v":40.5,"p":45},"play":{"v":66.0,"p":74},"adot":{"v":7.3,"p":29}}},"DET":{"pc":"Drew Petzing","yrs":3,"d":{"moti":{"v":38.7,"p":6},"pa_p":{"v":24.6,"p":74},"proe":{"v":-0.1,"p":74},"pass":{"v":64.3,"p":87},"two_":{"v":12.0,"p":13},"te2":{"v":43.7,"p":58},"play":{"v":65.5,"p":71},"adot":{"v":7.1,"p":19}}},"GB":{"pc":"Matt LaFleur","yrs":4,"d":{"moti":{"v":56.2,"p":81},"pa_p":{"v":23.9,"p":68},"proe":{"v":-4.1,"p":23},"pass":{"v":56.3,"p":10},"two_":{"v":19.1,"p":48},"te2":{"v":36.0,"p":23},"play":{"v":62.2,"p":23},"adot":{"v":8.6,"p":87}}},"HOU":{"pc":"Nick Caley","yrs":1,"d":{"moti":{"v":53.5,"p":55},"pa_p":{"v":22.8,"p":52},"proe":{"v":-0.4,"p":65},"pass":{"v":60.8,"p":55},"two_":{"v":21.0,"p":68},"te2":{"v":35.5,"p":19},"play":{"v":67.3,"p":94},"adot":{"v":8.2,"p":74}}},"IND":{"pc":"Shane Steichen","yrs":4,"d":{"moti":{"v":43.7,"p":16},"pa_p":{"v":26.2,"p":84},"proe":{"v":-3.5,"p":32},"pass":{"v":58.7,"p":32},"two_":{"v":10.7,"p":3},"te2":{"v":40.1,"p":35},"play":{"v":64.0,"p":45},"adot":{"v":8.8,"p":94}}},"JAC":{"pc":"Liam Coen","yrs":1,"d":{"moti":{"v":49.6,"p":45},"pa_p":{"v":18.3,"p":16},"proe":{"v":0.2,"p":81},"pass":{"v":61.1,"p":58},"two_":{"v":20.4,"p":61},"te2":{"v":26.9,"p":0},"play":{"v":66.4,"p":81},"adot":{"v":7.0,"p":13}}},"KC":{"pc":"Andy Reid","yrs":4,"d":{"moti":{"v":53.7,"p":65},"pa_p":{"v":17.6,"p":13},"proe":{"v":6.0,"p":100},"pass":{"v":66.4,"p":97},"two_":{"v":11.9,"p":10},"te2":{"v":52.1,"p":94},"play":{"v":65.3,"p":68},"adot":{"v":7.0,"p":16}}},"LAC":{"pc":"Mike McDaniel","yrs":4,"d":{"moti":{"v":73.8,"p":100},"pa_p":{"v":26.5,"p":87},"proe":{"v":-2.8,"p":45},"pass":{"v":59.9,"p":52},"two_":{"v":32.1,"p":100},"te2":{"v":40.1,"p":39},"play":{"v":61.9,"p":16},"adot":{"v":7.1,"p":23}}},"LAR":{"pc":"Sean McVay","yrs":4,"d":{"moti":{"v":66.6,"p":94},"pa_p":{"v":29.3,"p":97},"proe":{"v":-0.4,"p":68},"pass":{"v":59.6,"p":42},"two_":{"v":21.9,"p":71},"te2":{"v":34.3,"p":13},"play":{"v":64.2,"p":48},"adot":{"v":8.1,"p":61}}},"LV":{"pc":"Klint Kubiak","yrs":2,"d":{"moti":{"v":53.8,"p":68},"pa_p":{"v":22.9,"p":58},"proe":{"v":-5.5,"p":13},"pass":{"v":56.6,"p":13},"two_":{"v":27.1,"p":94},"te2":{"v":50.1,"p":84},"play":{"v":62.3,"p":26},"adot":{"v":8.0,"p":52}}},"MIA":{"pc":"Bobby Slowik","yrs":2,"d":{"moti":{"v":54.7,"p":71},"pa_p":{"v":22.7,"p":48},"proe":{"v":-0.1,"p":77},"pass":{"v":63.2,"p":71},"two_":{"v":22.0,"p":77},"te2":{"v":39.4,"p":32},"play":{"v":65.0,"p":65},"adot":{"v":8.4,"p":81}}},"MIN":{"pc":"Kevin O'Connell","yrs":4,"d":{"moti":{"v":49.9,"p":48},"pa_p":{"v":27.0,"p":94},"proe":{"v":2.2,"p":94},"pass":{"v":63.3,"p":81},"two_":{"v":20.1,"p":58},"te2":{"v":43.8,"p":61},"play":{"v":62.4,"p":29},"adot":{"v":8.0,"p":55}}},"NE":{"pc":"Josh McDaniels","yrs":2,"d":{"moti":{"v":49.1,"p":35},"pa_p":{"v":23.4,"p":65},"proe":{"v":1.7,"p":87},"pass":{"v":61.4,"p":61},"two_":{"v":26.3,"p":90},"te2":{"v":44.4,"p":65},"play":{"v":62.9,"p":32},"adot":{"v":9.2,"p":100}}},"NO":{"pc":"Kellen Moore","yrs":4,"d":{"moti":{"v":52.7,"p":52},"pa_p":{"v":21.0,"p":26},"proe":{"v":-3.8,"p":29},"pass":{"v":58.8,"p":35},"two_":{"v":14.0,"p":29},"te2":{"v":40.1,"p":42},"play":{"v":66.3,"p":77},"adot":{"v":7.9,"p":42}}},"NYG":{"pc":"Matt Nagy","yrs":0,"d":{"moti":{"v":38.1,"p":3},"pa_p":{"v":22.8,"p":55},"proe":{"v":-4.1,"p":26},"pass":{"v":59.2,"p":39},"two_":{"v":19.2,"p":52},"te2":{"v":40.6,"p":48},"play":{"v":67.1,"p":87},"adot":{"v":8.5,"p":84}}},"NYJ":{"pc":"Frank Reich","yrs":2,"d":{"moti":{"v":29.8,"p":0},"pa_p":{"v":14.3,"p":0},"proe":{"v":-4.4,"p":19},"pass":{"v":63.2,"p":74},"two_":{"v":7.7,"p":0},"te2":{"v":36.0,"p":26},"play":{"v":67.2,"p":90},"adot":{"v":7.2,"p":26}}},"PHI":{"pc":"Sean Mannion","yrs":0,"d":{"moti":{"v":47.3,"p":32},"pa_p":{"v":22.3,"p":42},"proe":{"v":-2.0,"p":58},"pass":{"v":58.5,"p":26},"two_":{"v":11.8,"p":6},"te2":{"v":38.5,"p":29},"play":{"v":60.9,"p":3},"adot":{"v":9.1,"p":97}}},"PIT":{"pc":"Mike McCarthy","yrs":2,"d":{"moti":{"v":44.3,"p":19},"pa_p":{"v":20.1,"p":19},"proe":{"v":0.2,"p":84},"pass":{"v":63.5,"p":84},"two_":{"v":15.3,"p":32},"te2":{"v":34.3,"p":16},"play":{"v":68.2,"p":97},"adot":{"v":7.5,"p":35}}},"SEA":{"pc":"Brian Fleury","yrs":0,"d":{"moti":{"v":56.9,"p":84},"pa_p":{"v":25.2,"p":77},"proe":{"v":-6.1,"p":6},"pass":{"v":52.9,"p":0},"two_":{"v":26.1,"p":87},"te2":{"v":43.5,"p":55},"play":{"v":61.3,"p":13},"adot":{"v":7.9,"p":45}}},"SF":{"pc":"Kyle Shanahan","yrs":4,"d":{"moti":{"v":67.0,"p":97},"pa_p":{"v":20.6,"p":23},"proe":{"v":-1.7,"p":61},"pass":{"v":58.5,"p":29},"two_":{"v":25.8,"p":84},"te2":{"v":28.3,"p":3},"play":{"v":63.2,"p":35},"adot":{"v":8.0,"p":58}}},"TB":{"pc":"Zac Robinson","yrs":2,"d":{"moti":{"v":65.0,"p":90},"pa_p":{"v":17.3,"p":6},"proe":{"v":-6.5,"p":3},"pass":{"v":56.9,"p":16},"two_":{"v":15.6,"p":39},"te2":{"v":44.9,"p":68},"play":{"v":64.8,"p":52},"adot":{"v":7.9,"p":48}}},"TEN":{"pc":"Brian Daboll","yrs":1,"d":{"moti":{"v":41.6,"p":10},"pa_p":{"v":22.9,"p":61},"proe":{"v":-2.5,"p":55},"pass":{"v":64.8,"p":94},"two_":{"v":13.1,"p":26},"te2":{"v":31.4,"p":6},"play":{"v":64.9,"p":61},"adot":{"v":6.9,"p":6}}},"WAS":{"pc":"David Blough","yrs":0,"d":{"moti":{"v":53.5,"p":58},"pa_p":{"v":25.8,"p":81},"proe":{"v":-3.1,"p":42},"pass":{"v":59.6,"p":45},"two_":{"v":15.5,"p":35},"te2":{"v":50.2,"p":87},"play":{"v":60.9,"p":6},"adot":{"v":8.6,"p":90}}}};
const VET_NO_FTN={"NYG":"Matt Nagy"};
const STYLE_2025={'ARI':{m:-1,t2:0,pr:1},'ATL':{m:1,t2:1,pr:-1},'BAL':{m:0,t2:1,pr:-1},'BUF':{m:1,t2:0,pr:-1},'CAR':{m:-1,t2:0,pr:-1},'CHI':{m:0,t2:1,pr:0},'CIN':{m:0,t2:0,pr:1},'CLE':{m:-1,t2:1,pr:0},'DAL':{m:0,t2:-1,pr:1},'DEN':{m:-1,t2:0,pr:1},'DET':{m:1,t2:0,pr:-1},'GB':{m:0,t2:-1,pr:-1},'HOU':{m:0,t2:-1,pr:0},'IND':{m:0,t2:-1,pr:0},'JAC':{m:1,t2:-1,pr:1},'KC':{m:-1,t2:1,pr:1},'LAC':{m:0,t2:-1,pr:1},'LAR':{m:1,t2:1,pr:1},'LV':{m:-1,t2:0,pr:0},'MIA':{m:1,t2:0,pr:-1},'MIN':{m:-1,t2:0,pr:0},'NE':{m:0,t2:1,pr:1},'NO':{m:1,t2:-1,pr:0},'NYG':{m:-1,t2:0,pr:-1},'NYJ':{m:1,t2:0,pr:-1},'PHI':{m:-1,t2:-1,pr:0},'PIT':{m:0,t2:1,pr:1},'SEA':{m:0,t2:0,pr:-1},'SF':{m:1,t2:-1,pr:0},'TB':{m:1,t2:-1,pr:0},'TEN':{m:-1,t2:1,pr:0},'WAS':{m:0,t2:1,pr:0}};
/* TEAMMATE ORDER FOR THE STYLE FACTORS, written down (25 Oct 2026, legal compliance plan step 5).
   styleRole() sorted each team's RBs and WRs by RAW's built-in market numbers (k), once, at
   page load, before the live market file arrives. Those numbers were refreshed (see the note
   above RAW), and re-sorting by the new ones would have moved 36 players' projections. So the
   order the engine has always used is written down here, unchanged: it is exactly what
   styleRole() built from the old numbers (checked against the live page, 64 groups of 64).
   Nothing on the site moves. NOTE: the study that validated these factors
   (scripts/validate-style.py) ranked teammates by TOTAL POINTS, not market value. Ordering by
   points would change 52 roles; that is a model change and waits for its own pre-registered
   test (backlog). Re-read this table at the offseason roll, when rosters turn over. */
const STYLE_ROLE_ORDER={
  "ARI|RB":["Jeremiyah Love","Trey Benson","James Conner","Tyler Allgeier","Zonovan Knight"],
  "ARI|WR":["Marvin Harrison Jr.","Michael Wilson","Reggie Virgil","Kendrick Bourne"],
  "ATL|RB":["Bijan Robinson"],
  "ATL|WR":["Drake London","Zachariah Branch","Darnell Mooney","Jahan Dotson","Olamide Zaccheaus"],
  "BAL|RB":["Derrick Henry","Adam Randall","Justice Hill"],
  "BAL|WR":["Zay Flowers","Ja'Kobi Lane","Rashod Bateman","Elijah Sarratt"],
  "BUF|RB":["James Cook","Ray Davis","Ty Johnson"],
  "BUF|WR":["D.J. Moore","Khalil Shakir","Keon Coleman","Skyler Bell","Joshua Palmer"],
  "CAR|RB":["Jonathon Brooks","Chuba Hubbard","Trevor Etienne"],
  "CAR|WR":["Tetairoa McMillan","Xavier Legette","Jalen Coker","Chris Brazzell II","John Metchie","Jimmy Horn"],
  "CHI|RB":["Kyle Monangai","D'Andre Swift","Roschon Johnson"],
  "CHI|WR":["Luther Burden","Rome Odunze","Zavion Thomas","Jahdae Walker"],
  "CIN|RB":["Chase Brown","Tahj Brooks","Samaje Perine"],
  "CIN|WR":["Ja'Marr Chase","Tee Higgins","Andrei Iosivas","Colbie Young","Noah Thomas"],
  "CLE|RB":["Quinshon Judkins","Dylan Sampson","Keaton Mitchell","Raheim Sanders"],
  "CLE|WR":["KC Concepcion","Denzel Boston","Jerry Jeudy","Cedric Tillman","Isaiah Bond"],
  "DAL|RB":["Javonte Williams","Jaydon Blue","Malik Davis","Phil Mafah"],
  "DAL|WR":["CeeDee Lamb","George Pickens","Jalen Tolbert","Ryan Flournoy","KaVontae Turpin"],
  "DEN|RB":["RJ Harvey","J.K. Dobbins","Jonah Coleman","Audric Estime"],
  "DEN|WR":["Jaylen Waddle","Courtland Sutton","Marvin Mims","Devaughn Vele","Pat Bryant","Troy Franklin"],
  "DET|RB":["Jahmyr Gibbs","Isiah Pacheco"],
  "DET|WR":["Amon-Ra St. Brown","Jameson Williams","Isaac TeSlaa","Kendrick Law"],
  "GB|RB":["Josh Jacobs","MarShawn Lloyd","Chris Brooks","Damien Martinez"],
  "GB|WR":["Jayden Reed","Christian Watson","Matthew Golden","Dontayvion Wicks","Savion Williams"],
  "HOU|RB":["David Montgomery","Woody Marks"],
  "HOU|WR":["Nico Collins","Jayden Higgins","Tank Dell","Xavier Hutchinson"],
  "IND|RB":["Jonathan Taylor","Seth McGowan","DJ Giddens"],
  "IND|WR":["Alec Pierce","Josh Downs","Adonai Mitchell","Jaylin Noel","Deion Burks"],
  "JAC|RB":["Bhayshul Tuten","Tank Bigsby","Chris Rodriguez","J'Mari Taylor","LeQuint Allen"],
  "JAC|WR":["Brian Thomas Jr.","Travis Hunter","Parker Washington","Jakobi Meyers","Josh Cameron"],
  "KC|RB":["Kenneth Walker III","Emmett Johnson","Brashard Smith","Emari Demercado"],
  "KC|WR":["Rashee Rice","Xavier Worthy","Cyrus Allen","Jalen Royals","Jeff Caldwell","Tyquan Thornton"],
  "LAC|RB":["Omarion Hampton","Kimani Vidal"],
  "LAC|WR":["Ladd McConkey","Quentin Johnston","Tre Harris","Brenen Thompson","KeAndre Lambert-Smith"],
  "LAR|RB":["Kyren Williams","Blake Corum","Jarquez Hunter"],
  "LAR|WR":["Puka Nacua","Davante Adams","CJ Daniels","Konata Mumpfield","Jordan Whittington"],
  "LV|RB":["Ashton Jeanty","Mike Washington Jr.","George Holani","Roman Hemby"],
  "LV|WR":["Jalen Nailor","Jack Bech","Tre Tucker","Dont'e Thornton","Malik Benson"],
  "MIA|RB":["De'Von Achane","Ollie Gordon","Jaylen Wright"],
  "MIA|WR":["Chris Bell","Caleb Douglas","Malik Washington","Kevin Coleman","Tutu Atwell"],
  "MIN|RB":["Jordan Mason","Aaron Jones","Demond Claiborne"],
  "MIN|WR":["Justin Jefferson","Jordan Addison","Tai Felton"],
  "NE|RB":["TreVeyon Henderson","Rhamondre Stevenson","Jam Miller"],
  "NE|WR":["Romeo Doubs","Kyle Williams","DeMario Douglas","Kayshon Boutte","Mack Hollins","Efton Chism"],
  "NO|RB":["Travis Etienne","Alvin Kamara","Devin Neal","Kendre Miller"],
  "NO|WR":["Jordyn Tyson","Chris Olave","Bryce Lance","Barion Brown","Ja'Lynn Polk"],
  "NYG|RB":["Cam Skattebo","Tyrone Tracy","Devin Singletary"],
  "NYG|WR":["Malik Nabers","Malachi Fields","Darius Slayton","Calvin Austin"],
  "NYJ|RB":["Breece Hall","Braelon Allen","Isaiah Davis"],
  "NYJ|WR":["Garrett Wilson","Omar Cooper","Arian Smith"],
  "PHI|RB":["Saquon Barkley","Will Shipley"],
  "PHI|WR":["Makai Lemon","DeVonta Smith","A.J. Brown"],
  "PIT|RB":["Rico Dowdle","Jaylen Warren","Kaleb Johnson","Eli Heidenreich"],
  "PIT|WR":["Germie Bernard","DK Metcalf","Michael Pittman Jr.","Kaden Wetjen","Roman Wilson"],
  "SEA|RB":["Jadarian Price","Zach Charbonnet","Emanuel Wilson","Kenny McIntosh"],
  "SEA|WR":["Jaxon Smith-Njigba","Rashid Shaheed","Cooper Kupp","Tory Horton"],
  "SF|RB":["Christian McCaffrey","Kaelon Black","Isaac Guerendo","Jordan James"],
  "SF|WR":["De'Zhaun Stribling","Ricky Pearsall","Mike Evans","Jacob Cowing"],
  "TB|RB":["Bucky Irving","Kenneth Gainwell","Sean Tucker"],
  "TB|WR":["Emeka Egbuka","Jalen McMillan","Tez Johnson","Ted Hurst","Kameron Johnson"],
  "TEN|RB":["Tyjae Spears","Tony Pollard","Nicholas Singleton","Michael Carter"],
  "TEN|WR":["Carnell Tate","Wan'Dale Robinson","Calvin Ridley","Elic Ayomanor","Chimere Dike","Xavier Restrepo"],
  "WAS|RB":["Jacory Croskey-Merritt","Rachaad White","Brian Robinson","Kaytron Allen","Robert Henry","Jerome Ford"],
  "WAS|WR":["Antonio Williams","Terry McLaurin","Jaylin Lane","Luke McCaffrey","Treylon Burks"]
};
let __styleRoleMemo=null;
function styleRole(name,team,pos){
  // Teammate order from STYLE_ROLE_ORDER (above). A team or position it doesn't cover
  // (none today) falls back to the old rule: sort by RAW's k, once.
  const fixed=STYLE_ROLE_ORDER[team+'|'+pos];
  if(fixed) return fixed.indexOf(name);
  if(!__styleRoleMemo)__styleRoleMemo={};
  const key=team+'|'+pos;
  if(!__styleRoleMemo[key]){
    const list=(typeof RAW!=='undefined'?RAW:[]).filter(p=>p&&p.t===team&&(p.p||p.pos)===pos)
      .sort((a,b)=>(b.k||0)-(a.k||0)).map(p=>p.n);
    __styleRoleMemo[key]=list;
  }
  return __styleRoleMemo[key].indexOf(name);
}
function styleFactors(name,pos,team){
  // returns {parts:[{label,pct}], total, scaled} — single source for the
  // projection delta AND the scheme-card explanation, so they cannot disagree
  const out={parts:[],total:0,scaled:false};
  if(pos==='QB'||typeof STYLE_2025==='undefined')return out;
  const st=team&&STYLE_2025[team]; if(!st)return out;
  if(pos==='RB'&&styleRole(name,team,'RB')===0&&st.m!==0){
    const pct=st.m*0.03;
    out.parts.push({label:(st.m>0?'High':'Low')+'-motion offense ('+(st.m>0?'top':'bottom')+' third) — motion schemes RB production',pct});
    out.total+=pct;
  }
  if(pos==='WR'){
    if(st.pr!==0){
      const pct=st.pr*0.02;
      out.parts.push({label:(st.pr>0?'Pass-lean':'Run-lean')+' identity (PROE '+(st.pr>0?'top':'bottom')+' third) — '+(st.pr>0?'lifts':'thins')+' the WR room',pct});
      out.total+=pct;
    }
    const r=styleRole(name,team,'WR');
    if(r>=2&&st.t2!==0){
      const pct=st.t2===1?-0.03:0.02;
      out.parts.push({label:st.t2===1?'Heavy 12-personnel (top third) — fewer 3-WR sets squeeze the WR3 role':'Light 12-personnel (bottom third) — extra 3-WR sets feed the WR3 role',pct});
      out.total+=pct;
    }
  }
  if(out.total!==0){
    // Trigger on the FACT (ch = did the playcaller change?), not on the continuity SCORE.
    // `c` also sets dOc, so `c<0.70` conflated the trigger with the penalty size -- you could
    // not correct one without firing the other. `ch` is the boolean built for exactly this.
    const tch=(typeof gs==='function'&&gs(team))?!!gs(team).ch:false;
    if(tch){out.total*=0.4;out.parts.forEach(p=>p.pct*=0.4);out.scaled=true;}
    out.total=Math.max(-0.06,Math.min(0.06,out.total));
  }
  return out;
}

function getDeltas(name,pos,sys,cont,yprr,snap,col,epa_sc,ripple,qbq){
  const isQB=pos==='QB';
  // System delta — QBs: near-zero (their PPG already fully reflects their system)
  // Skill positions: small adjustment for system quality
  const d_sys=isQB
    ?(sys>=70?.01:sys>=55?.0:sys>=40?-.03:-.07)
    :(sys>=70?.04:sys>=55?.01:sys>=40?-.04:-.10);
  // OC continuity delta — QBs feel this most, RBs least (scheme-independent)
  // Franchise cornerstones (COMP_EXEMPT): new OCs adapt to them, penalty halved
  const ocFranchise=COMP_EXEMPT.has(name);
  const d_oc=isQB
    ?(cont>=.95?.01:cont>=.70?.0:cont>=.50?-.04:cont>=.30?-.07:-.11)
    :pos==='RB'
      ?(cont>=.95?.01:cont>=.70?.01:cont>=.50?-.02:cont>=.30?-.03:-.05)
      :ocFranchise
        ?(cont>=.95?.03:cont>=.70?.01:cont>=.50?-.02:cont>=.30?-.04:-.06)
        :(cont>=.95?.03:cont>=.70?.01:cont>=.50?-.04:cont>=.30?-.08:-.12);
  // Role delta — QBs: zero (no depth chart role for QBs)
  let d_role=0;
  if(pos==='WR'){
    d_role=yprr>=2.5?.05:yprr>=2.0?.02:yprr>=1.5?.0:yprr>=1.0?-.03:-.08;
  } else if(pos==='TE'){
    // TEs have lower route volume — neutral floor at 1.2 not 1.5
    d_role=yprr>=2.5?.05:yprr>=2.0?.02:yprr>=1.2?.0:yprr>=0.8?-.03:-.08;
  } else if(pos==='RB'){
    d_role=snap>=75?.06:snap>=60?.03:snap>=45?.0:snap>=30?-.05:-.10;
  }
  // College bonus delta (tiny)
  const d_col=(col-1.0)*0.25;
  // EPA delta — QBs: halved (their EPA is already in their PPG baseline)
  const d_epa=isQB?(epa_sc-1.0)*0.15:(epa_sc-1.0)*0.30;
  // Ripple — QBs: halved (teammate additions are smaller signal for QB than for WR/RB)
  const d_rip=isQB?(ripple-1.0)*0.20:(ripple-1.0)*0.40;
  // QB quality penalty for skill positions only
  const d_qbq=!isQB?(qbq-0.90)*0.20:0;
  // Target share trend delta
  const d_ts=!isQB?(TS_DELTA[name]||0):0;
  // Offense style (validated signals — see block above); RAW lookup for team
  let d_style=0;
  if(typeof RAW!=='undefined'){
    const rp=RAW.find(p=>p&&p.n===name);
    if(rp&&rp.t) d_style=styleFactors(name,pos,rp.t).total;
  }
  // ---------------------------------------------------------------------------
  // dSys / dOc REMOVED FROM THE PROJECTION (2026-07 scheme investigation).
  // The scheme ship-gate study (1388 same-team player pairs, 2017-25) fitted the
  // real coordinator-change effect per position and its 95% CI EXCLUDED the engine's
  // hand-typed value at QB/WR/TE and could not distinguish RB from zero. Adding these
  // levers made out-of-sample prediction slightly WORSE. dSys additionally cannot be
  // backtested at all (no historical SYS table). Both are zeroed here rather than
  // deleted, so the popup can still SHOW the tendency descriptively (see explainSystem)
  // without it touching the number. styleFactors (d_style) STAYS: it passed a different
  // validation and its small edges are left for the accuracy ledger to judge.
  const d_sys_APPLIED = 0;
  const d_oc_APPLIED  = 0;
  return d_sys_APPLIED+d_oc_APPLIED+d_role+d_col+d_epa+d_rip+d_qbq+d_ts+d_style;
}

// ── Rookie baseline projections ────────────────────────────────────────────
// Median rookie-year PPG (0.5 PPR + TE premium) by position and draft capital,
// computed from every drafted skill player 2015-2025 who played at least one game
// (874 picks, 718 with a rookie season). Medians, not means, so one Puka Nacua does
// not lift an entire tier. Rows are forced non-increasing as capital falls: thin
// buckets (TE top-10 n=3, QB Rd2 n=5) produced noise like "Rd2 QB > Rd1 QB", and a
// later pick should never project above an earlier one at the same position.
//
// Pre-registered test, fit on 2015-2022 and scored on held-out 2023-2025:
//   flat 8.0 fallback (incumbent) RMSE 5.390
//   position median only          RMSE 4.440   (17.6% better)
//   position x capital            RMSE 3.776   (29.9% better)   <- shipped
// Ship gate was >=2%. This replaces a literal 8.0 that had no player information in
// it at all, which is why 63 of 81 prospects were being priced as injured veterans.
const ROOKIE_PPG = {
  QB: [15.20, 12.91, 12.91,  8.00, 5.44],
  RB: [15.22, 12.73, 10.79,  6.00, 3.18],
  TE: [10.32,  8.59,  4.93,  3.12, 3.12],
  WR: [ 9.39,  7.09,  6.16,  3.69, 1.74],
};
function rookieTier(pick){
  return pick<=10 ? 0 : pick<=32 ? 1 : pick<=64 ? 2 : pick<=105 ? 3 : 4;
}
/* ── UNDRAFTED ROOKIE BASELINE (29 Sep 2026) ───────────────────────────────
   docs/PREREG-rookie-baseline-v2.md Part B, locked e30e2bc, PASSED: 61.7% smaller average
   miss on 406 undrafted rookie seasons 2015-2025 (p = 0.0005, all 11 classes). Median rookie
   PPG of undrafted rookies who played, by position (QB rests on 12 players — thin). Replaces
   the literal 8.0 fallback and the "sat out two seasons" discount it used to take.
   Applies ONLY when the player has no draft record AND no NFL game before this season in the
   game logs — so a veteran whose stats are missing (a name mismatch) is never mistaken for a
   rookie. Until the logs load, it returns null and the old behaviour holds.
   Untested extension, flagged: an undrafted player in his SECOND year who has never played
   also gets it (the study graded first seasons only). Undrafted rookies stay out of the
   in-season blend (blendK = 0) — that would need its own test. */
const UNDRAFTED_PPG = {QB:4.74, RB:1.70, WR:0.76, TE:0.28};
function undraftedBaseline(pl){
  if(!GAMELOGS) return null;
  const earlier=(GAMELOGS[pl.n]||[]).some(r=>r.s<SEASON_YEAR && !r.up && !r.dnp);
  if(earlier) return null;
  return UNDRAFTED_PPG[pl.p] ?? null;
}
function rookieBaseline(pl){
  let di=null;
  try{ di = (typeof dsDraftInfo==='function') ? dsDraftInfo(pl.n) : null; }catch(e){}
  if(!di || di.pick==null) return undraftedBaseline(pl);
  const row = ROOKIE_PPG[pl.p];
  return row ? row[rookieTier(di.pick)] : null;
}

/* ── IN-SEASON BLEND (26 Sep 2026) ─────────────────────────────────────────
   docs/PREREG-in-season-blend.md, locked 0398624/c164ba0, PASSED: blending this
   season's points per game into the preseason projection cut the typical miss on
   rest-of-season PPG by 16.4% on 2023-25 (p=0.0005, every season and position).
   Winning form "D": (w x this-season PPG + (1-w) x preseason) x (1 + 0.5 x d_volatility),
   w = G/(G+BLEND_K). K=4 was the training peak (flat 3-6): this season counts 43%
   after 3 games, 60% after 6, 69% after 9.
   K depends on the player's HISTORY, not on which code path he takes (blendK below):
     >=8 played games in the three prior seasons  K=4  (Part 1)
     1-7 played games                              K=2  (Part 2, thin history: 22.3%, p=0.031)
     drafted rookie in his draft season            K=3  (Part 2, rookies: 23.3%, p=0.0005)
     undrafted rookie / no history                 no blend (untested)
   docs/PREREG-in-season-blend-rookies.md, locked b54b288, both groups PASSED 26 Sep 2026.
   Games = the live DNP rule (game-logs.json played rows). Points use gamefp() in
   half PPR + TE premium — the projection's basis (see calcProj). */
const BLEND_K=4;
function inSeasonForm(name,pos,startsOnly){
  if(!GAMELOGS||!GAMELOGS[name]) return null;
  let g=0,pts=0,prior=0;
  for(const r of GAMELOGS[name]){
    if(r.up||r.dnp) continue;
    if(r.s===SEASON_YEAR){ if(startsOnly && GL_HAS_QS && !r.qs) continue; g++; pts+=gamefp(r,pos,'half_tep'); }   // the projection's basis (see calcProj)
    else if(r.s<SEASON_YEAR && r.s>=SEASON_YEAR-3) prior++;
  }
  return {g, ppg:g?pts/g:0, prior};
}
const BLEND_K_THIN=2, BLEND_K_ROOKIE=3;
function blendK(pl,form){
  if(!form||form.g<1) return 0;
  if(form.prior>=8) return BLEND_K;
  if(form.prior>=1) return BLEND_K_THIN;
  const di=dsDraftInfo(pl.n);           // no prior games: only a drafted rookie in his draft year
  return (di&&di.pick!=null&&di.year===SEASON_YEAR) ? BLEND_K_ROOKIE : 0;
}
/* Missed-time sizes, fitted on 2018-2025 (docs/PREREG-missed-time.md). "Sat out" = no games
   last season; "sat out two" = no production the season before either (kept at the old
   relative gap to "sat out", 0.615/0.66 — too few cases to size alone). */
const MISSED_TIME_MULT={sat:0.721, sat2:0.672, g1to3:0.690, g4to7:0.797};
function missedTimeMult(g25,pl){
  if(g25===0 && !(pl.ppg25>0)) return pl.ppg24>0 ? MISSED_TIME_MULT.sat : MISSED_TIME_MULT.sat2;
  if(g25>=1 && g25<=3) return MISSED_TIME_MULT.g1to3;
  if(g25>=4 && g25<=7) return MISSED_TIME_MULT.g4to7;
  return 1;
}
/* ── TEAM-CHANGE ADJUSTMENT (28 Sep 2026) ─────────────────────────────────
   docs/PREREG-team-change-ship.md, locked 3ddb6b3, PASSED: 9.2% smaller miss on 265 held-out
   movers (p = 0.0005, every season, every position). Players who changed teams in the
   offseason scored ~17% below their own history relative to stayers, at every age and in the
   top 150; DELTA's directional team adjustments already allowed ~7%. This closes only the rest:
   x0.898 (0.834 / 0.929). The directional adjustments stay, so a move into a strong
   situation still helps. A MOVE = a veteran whose main team last season (most games) differs
   from his team in his first game this season (current team if he hasn't played yet).
   Mid-season trades are not caught (untested); rookies never reach this. */
const TEAM_CHANGE_MULT=0.898;
const TEAM_CODE_FIX={JAX:'JAC',LA:'LAR'};                 // game logs vs site codes
function changedTeamsThisSeason(pl){
  if(!GAMELOGS||!GAMELOGS[pl.n]) return false;
  const fix=t=>TEAM_CODE_FIX[t]||t;
  const last={}; let first=null, firstW=99;
  for(const r of GAMELOGS[pl.n]){
    if(r.up||r.dnp||!r.tm) continue;
    if(r.s===SEASON_YEAR-1) last[fix(r.tm)]=(last[fix(r.tm)]||0)+1;
    else if(r.s===SEASON_YEAR && r.w<firstW){ firstW=r.w; first=fix(r.tm); }
  }
  const prev=Object.keys(last).sort((a,b)=>last[b]-last[a]||a.localeCompare(b))[0];
  const now=first||fix(pl.t);
  if(!prev||!now||now==='FA') return false;
  return prev!==now;
}
function calcProj(plFmt){
  /* FORMAT BASIS (26 Sep 2026). The projection is built in ONE scoring — half PPR + TE
     premium, the freeze's and the ledger's basis — whatever the league's format, and
     getAdjProj() converts it to the league's format once, at display. Before this, season
     PPGs arrived already in the league's format and getAdjProj() converted AGAIN, so a
     full-PPR visitor saw every non-TE pass-catcher inflated (Nacua 26.3 vs 22.3).
     The league-format PPGs are handed back (fmtBack) before the DELTA Score and model
     value run, so those — and every season-PPG display — see exactly what they saw before. */
  let pl={...plFmt};
  for(const k of ['25','24','23']) if(plFmt['ppgH'+k]!=null) pl['ppg'+k]=plFmt['ppgH'+k];
  const fmtBack=r=>{ for(const k of ['25','24','23'])
    if(plFmt['ppgH'+k]!=null && r['ppg'+k]===plFmt['ppgH'+k]) r['ppg'+k]=plFmt['ppg'+k]; return r; };
  // A true rookie has no NFL history at all. Supply the draft-capital baseline as its
  // forward projection so the rookie override below fires; otherwise it falls to a
  // literal 8.0 AND takes the veteran stale-production discount, which is meant for
  // players whose past production is unconfirmed, not players who have none.
  if((pl.g25||0)===0 && !(pl.ppg25>0) && !(pl.ppg24>0) && !(pl.ppg23>0)){
    const rb=rookieBaseline(pl);
    if(rb) pl={...pl, ppg25: rb};
  }
  const ps=qbPerStart(plFmt);   // a QB's points-per-start base, or null (see QB POINTS PER START)
  const e=getEff(pl);
  const age=parseFloat(pl.a)||26;
  const agM=amProj(pl.p,Math.floor(age));
  const ciV=ci(e.c);
  const col=CB[pl.n]||1.0;
  const qbq=pl.p==='QB'?1.0:(QBQ[AL[e.team]||e.team]||0.85);
  const rip=RP[pl.n]||1.0;
  const epa=calcEPA(pl.n,pl.p);
  const roleData=getRoleData(pl.n,pl.p);

  // ── RULE 1: MINIMUM SAMPLE THRESHOLD ──────────────────────────
  // Seasons with very few games get reduced weight — prevents injury-year
  // or emergency-starter averages from being treated as full seasons.
  const g25=pl.g25||0;
  const w25 = g25>=10 ? 3 : g25>=8 ? 1.5 : g25>=4 ? 0.75 : 0;
  const w24 = pl.ppg24>0 ? 2 : 0;
  const w23 = pl.ppg23>0 ? 1 : 0;

  let num=0,den=0;
  if(w25>0&&pl.ppg25>0){num+=pl.ppg25*w25;den+=w25;}
  if(w24>0){num+=pl.ppg24*w24;den+=w24;}
  if(w23>0){num+=pl.ppg23*w23;den+=w23;}
  let base=den>0?num/den:pl.ppg25||pl.ppg24||8.0;
  if(ps) base=ps.base;

  /* ── QB STARTER-BASELINE OVERRIDE ──────────────────────────────────────
     A quarterback's per-game production is only meaningful if it was produced
     as a starter. Average a veteran's mop-up snaps and you get Jordan Love
     projected at 3.2 the year he threw for 4,000 yards.

     Measured over 25 seasons of Week-1 starters (n=97 veterans with a thin prior
     season, true rookies excluded since the rookie branch above already covers
     them): MAE 4.22 -> 2.64, a 37% reduction. Fitting K on 2000-2014 and testing
     on 2015-2024 gives 4.71 -> 3.10, a 34% reduction, paired 95% CI [+0.54, +2.80]
     — it holds out of sample, and K came back at 6 from the early era alone.

     Diagnosis behind it: split QB error by prior-season games and entrenched
     starters sit at 2.69 MAE while backups sit at 5.35. The same split at WR is
     2.33 vs 2.36 — no effect at all. DELTA projects quarterbacks fine; it just
     doesn't know who has the job. This supplies that one fact.

     Note the rule is self-limiting: a QB already projected near the baseline
     barely moves. It only does real work where the average is built on snaps
     that don't describe his coming role.

     NOT included: the rookie-threat signal. A veteran starting ahead of a top-64
     rookie QB loses the job 52% of the time vs 18% (n=52, significant), but
     fitting a PPG haircut for it returned lambda = 0.00 out of sample — the threat
     costs him GAMES, not points per game, and this projection is per-game. That
     finding belongs on the availability/opportunity side, not here. */
  let qbLift=false;                  // set when the lift fires — the missed-time cut skips these QBs
  if(!ps && pl.p==='QB' && QB_STARTERS[pl.n] && g25<8 && den>0){   // superseded by points per start when its data is present
    const sb=qbStarterBaseline();
    if(sb>0){
      const K=6;                      // fitted 2000-2014, flat from 4 to 12
      const w=g25/(g25+K);            // his own thin sample vs the starter baseline
      base = w*base + (1-w)*sb;
      qbLift=true;
    }
  }

  // ── MISSED-TIME MULTIPLIER (27 Sep 2026) ────────────────────────────────
  // docs/PREREG-missed-time.md, locked 9d81bd8, PASSED: 6.3% smaller miss on 360 cases
  // (p = 0.0005, 6 of 8 seasons, every position). One multiplier by games played last
  // season, applied to the starting number — outside the delta cap below, exactly as the
  // study tested it. Replaces the old x0.75 stale discount AND RULE 5's -12%/-18%/-8%/-4%.
  // Missed time counts (handoff §2); only the sizes were on trial.
  // QB EXCEPTION (2 Oct 2026): docs/PREREG-qb-missedtime.md, locked 633ba62, PASSED: where the QB
  // starter lift fired, removing this cut lowered the typical miss 11.8% on 103 Week-1 starters
  // 2002-2025 (p = 0.050, just inside the bar), better in both halves and every cut group. The
  // lift already pulls a thin-season starter to a starter's level; cutting again double-counted.
  if(!qbLift && !ps) base *= missedTimeMult(g25, pl);   // points per start: missed games don't lower his per-start level
  if(changedTeamsThisSeason(pl)) base *= TEAM_CHANGE_MULT;   // see TEAM_CHANGE_MULT above
  // Rookie override: if ppg25 is set as a forward projection (g25=0, ppg25>0),
  // skip all delta/efficiency adjustments — projection already accounts for situation.
  // Apply only the age curve multiplier since that's position-universal.
  if(g25===0 && pl.ppg25>0 && !ps){
    /* This early return previously bypassed TWO things that the main path applies,
       because both live below it:
         1. e.inj — the availability multiplier. Every forward-projected player was
            hard-coded to inj:1.0, so 19 of the 23 pipeline-flagged backup QBs
            (Winston, Mac Jones, Davis Mills, Tyrod Taylor...) kept a full starter
            projection no matter what the depth chart said.
         2. INJ_OUT — the season-ender list. A projected rookie confirmed out for
            the year would have kept his full projection, since the zeroing block
            sits after this return. Latent rather than live today (no current
            entry takes this path), but it would have failed silently. */
    const e2=getEff(pl);
    // Points per start covers rookie QBs too: no role cut on the PROJECTION once the per-start data is
    // live (model value keeps it). Without it (older data), exactly the old behaviour.
    const rookieInj = (pl.p==='QB' && QB_PS && QB_PS_LEVEL>0) ? e2.injP : e2.inj;
    const rookiePre = pl.ppg25 * agM * rookieInj;
    // In-season blend (blendK): this path also carries veterans with a forward
    // projection, so K comes from the player's history, not from this branch.
    const formR=inSeasonForm(pl.n,pl.p);
    const kR=blendK(pl,formR);
    const wR=kR?formR.g/(formR.g+kR):0;
    const rookieProj = kR ? wR*formR.ppg+(1-wR)*rookiePre : rookiePre;
    const mv2=mvAsset(fmtBack({...pl,proj:rookieProj,p:pl.p}));
    const ciV2=ci(e2.c);
    const rookieResult={...pl,pos:pl.p,t:e2.team,base:pl.ppg25,proj:rookieProj,
      floor:rookieProj*(1-ciV2),ceil:rookieProj*(1+ciV2),mv:mv2,
      gap:mv2-e2.ktc,s:e2.s,c:e2.c,oc:e2.oc,ch:e2.ch,inj:e2.inj,
      ktcEff:e2.ktc,notes:'',hasOv:true,projPre:rookiePre,
      inSeason:kR?{g:formR.g,ppg:formR.ppg,w:wR,k:kR}:null,
      epaSc:1.0,epaFl:false,epaFr:null,epaTr:'flat',
      role:0,roleLabel:'—',sys:50,oppSc:null};
    // Projected rookies (drafted, ppg25 set as a forward projection, no NFL
    // games yet) still get a DELTA Score — every player on the platform has one.
    // calcDynastyScore handles g25:0 correctly: it scores age + the projected
    // production + draft-capital-driven opportunity + contract, capped at the
    // rookie ceiling (DS_ROOKIE_CAP). Without this, projected rookies fell
    // through scoreless while rookies who logged any 2025 snap got a score —
    // an inconsistency (e.g. #33 pick Stribling blank, later picks scored).
    fmtBack(rookieResult);
    rookieResult.dsScore=calcDynastyScore(rookieResult);
    // Same intervention the main path makes below: projection zeroed and tagged,
    // model value and DELTA Score deliberately untouched.
    if (INJ_OUT[rookieResult.n]) {
      rookieResult.proj = 0; rookieResult.floor = 0; rookieResult.ceil = 0;
      rookieResult.outForSeason = true;
    }
    return rookieResult;
  }

  // ── RULE 2: VOLUME-ADJUSTED YPRR ──────────────────────────────
  // Regress YPRR toward league avg based on seasons of data available.
  // Also cap the role BONUS for players with thin data — prevents a WR
  // with 2 big-play targets from getting an elite efficiency designation.
  let adjYPRR = roleData.raw;
  if((pl.p==='WR'||pl.p==='TE') && adjYPRR>0){
    const d = pl.p==='WR' ? YPRR_WR[pl.n] : YPRR_TE[pl.n];
    if(d){
      const wrAvg = pl.p==='TE' ? 1.45 : 1.60;
      const seasons = (d[1]>0?1:0)+(d[2]>0?1:0)+(d[3]>0?1:0);
      // More regression for fewer seasons of data
      const regrFactor = seasons>=3 ? 0.85 : seasons===2 ? 0.70 : 0.50;
      adjYPRR = adjYPRR*regrFactor + wrAvg*(1-regrFactor);
      adjYPRR = Math.round(adjYPRR*100)/100;
    }
  }

  // ── RULE 3: ROLE STABILITY MODIFIER ───────────────────────────
  // Penalize players whose high PPG came from a temporary role spike.
  // Increased cap to -0.15 so meaningful spikes are properly dampened.
  let d_stability = 0;
  if(pl.ppg25>0 && pl.ppg24>0 && pl.ppg23>0){
    const avg2324 = (pl.ppg24*2+pl.ppg23)/3;
    const spike = pl.ppg25 - avg2324;
    if(spike>0 && avg2324>0 && spike/avg2324>0.35){
      // Stronger dampening — cap raised to -0.15
      d_stability = -Math.min(0.15, (spike/avg2324 - 0.35) * 0.30);
    }
  } else if(pl.ppg25>0 && pl.ppg24===0 && pl.ppg23===0 && g25<14){
    d_stability = -0.10; // only one season of data, limited games
  } else if(pl.ppg25>0 && (pl.ppg24===0||pl.ppg23===0) && g25<12){
    d_stability = -0.06;
  }
  // Two-year player (no 2023) with high variance between years
  if(pl.ppg25>0 && pl.ppg24>0 && pl.ppg23===0){
    const swing = Math.abs(pl.ppg25 - pl.ppg24) / Math.max(pl.ppg25, pl.ppg24);
    if(swing > 0.30) d_stability -= 0.04; // large swing between only 2 years
    // RBs with only 2 years of data and no prior baseline — unproven sustained role
    if(pl.p==='RB') d_stability -= 0.08;
  }
  // Stale spike: 2024 outlier with no 2025 confirmation
  if(pl.ppg24>0 && pl.ppg23>0 && pl.ppg25===0 && g25===0){
    if(pl.ppg24 > pl.ppg23*1.4) d_stability = -0.08;
  }
  // Single-year players (rookie or returning): apply regression
  // Catches Dart (g25=14, ppg24=0) and similar first-year starters
  // who slip through the g25<14 threshold with exactly 14+ games
  if(pl.ppg25>0 && pl.ppg24===0 && pl.ppg23===0){
    d_stability = pl.p==='QB' ? -0.08 : -0.10; // QB regresses less aggressively
  }

  // ── RULE 4: VOLATILITY PENALTY ────────────────────────────────
  let d_volatility = 0;
  const gl = glOf(pl,'half_tep');   // the projection's basis, not the league's
  if(gl && gl.g >= 20){
    if(gl.miss > 65) d_volatility = -0.09;
    else if(gl.miss > 55) d_volatility = -0.06;
    else if(gl.miss > 45) d_volatility = -0.03;
    else if(gl.miss > 40) d_volatility = -0.01;
    if(gl.elite > 30) d_volatility = Math.min(0, d_volatility + 0.03);
    else if(gl.elite > 20) d_volatility = Math.min(0, d_volatility + 0.01);
  }

  // ── RULE 5: INJURY / TIME-DECAY MODIFIER ─────────────────────
  let d_decay = 0;   // missed-time cuts moved to missedTimeMult() (27 Sep 2026); the decline rule stays
  if(pl.ppg25>0 && pl.ppg24>0 && pl.ppg23>0){
    if(pl.ppg25 < pl.ppg24 && pl.ppg24 < pl.ppg23) d_decay -= 0.03;
  }

  // ── FIX 1: DAMPEN OC CONTINUITY PENALTY FOR PROVEN PRODUCERS ──
  // A new OC should temper a proven WR1, not crater them.
  // Proven = base >= positional threshold OR recent season >= 15 PPG.
  // For proven players: pull continuity 60% toward neutral, and soften
  // system score by +10pts — preventing one bad-system + new-OC combo
  // from collapsing an established producer's entire projection.
  const provenThreshold = pl.p==='WR'?13.0:pl.p==='TE'?12.0:pl.p==='RB'?15.0:22.0;
  const provenPPG25 = pl.p==='WR'?15.0:pl.p==='TE'?13.0:pl.p==='RB'?16.0:24.0;
  const isProven = base >= provenThreshold || pl.ppg25 >= provenPPG25;
  // Soften OC continuity penalty: pull 60% toward neutral (0.70) for proven players
  const adjCont = isProven && e.c < 0.70
    ? e.c + (0.70 - e.c) * 0.60
    : e.c;
  // Soften system score: proven producers carry their role through bad environments
  const adjSys = isProven && e.s < 55
    ? Math.min(e.s + 10, 55)
    : e.s;

  // ── FIX 3: MULTI-YEAR YPRR CONFIRMATION FOR POSITIVE ROLE DELTA ─
  // A single season of high YPRR does not earn a positive role bonus.
  // Player must have 2+ seasons above league average YPRR to qualify.
  // If only 1 season above avg → treat as neutral (0 role delta, not positive).
  // This prevents speed-specialist or small-sample efficiency from
  // projecting fringe WRs into WR1 territory.
  let finalAdjYPRR = adjYPRR;
  if(pl.p==='WR'||pl.p==='TE'){
    const d = pl.p==='WR' ? YPRR_WR[pl.n] : YPRR_TE[pl.n];
    if(d){
      const avg = pl.p==='TE' ? 1.45 : 1.60;
      const seasonsAboveAvg = (d[1]>avg?1:0)+(d[2]>avg?1:0)+(d[3]>avg?1:0);
      // Only 1 season above avg → cap adjYPRR at league average (no role bonus)
      if(seasonsAboveAvg < 2 && finalAdjYPRR > avg){
        finalAdjYPRR = avg; // neutral — no positive role delta awarded
      }
    }
  }

  const rawDelta=getDeltas(pl.n,pl.p,adjSys,adjCont,finalAdjYPRR,roleData.raw,col,epa.sc,rip,qbq);

  // ── AGE-ADJUSTED PRODUCTION CURVE (existing) ──────────────────
  let d_curve=0;
  if(g25>=10 && base>0){
    let priorNum=0,priorDen=0;
    if(pl.ppg24>0){priorNum+=pl.ppg24*2;priorDen+=2;}
    if(pl.ppg23>0){priorNum+=pl.ppg23*1;priorDen+=1;}
    if(priorDen>0){
      const priorBase=priorNum/priorDen;
      const diff=pl.ppg25-priorBase;
      const pct=diff/priorBase;
      if(Math.abs(diff)>=1.5){
        const scale=priorDen===2?0.25:0.30;
        const isQB=pl.p==='QB';
        const capPos=isQB?0.04:0.06;
        const capNeg=(isQB||(parseFloat(pl.a)||26)<26)?-0.04:-0.08;
        d_curve=Math.max(capNeg,Math.min(capPos,pct*scale));
      }
    }
  }

  // ── COMBINE ALL DELTAS ─────────────────────────────────────────
  const cap=pl.p==='QB'?0.10:0.18;
  const floorD=pl.p==='QB'?-0.15:-0.25;
  // PENALTY SOFTENING (backtest-diagnosed): the stability & volatility penalties
  // were found to over-correct — they drag down players who actually sustained.
  // Halved to keep the intuition (spikes regress, boom/bust is real) while trusting
  // it less. NOT tuned to minimize backtest error; residual bias left uncorrected.
  const totalDelta=rawDelta+d_curve+0.5*d_stability+0.5*d_volatility+d_decay;
  const delta=Math.max(floorD,Math.min(cap,totalDelta));
  const injP=ps?e.injP:e.inj;   // a per-start QB takes no backup cut here; model value keeps it (e.inj)
  let proj=base*agM*(1+delta)*injP;
  // In-season blend (see BLEND_K above). The preseason number is rebuilt WITHOUT the
  // volatility term, blended, and the term applied once to the result — the tested
  // form D. The blended PPG is NOT run back through the team multipliers: it was
  // already scored in this system with this QB. projPre keeps today's number.
  const projPre=proj;
  const form=inSeasonForm(pl.n,pl.p,!!ps);   // per-start QBs: this season's STARTS only
  let blendW=0;
  const blendKv=blendK(pl,form);
  if(blendKv){
    const deltaNoVol=Math.max(floorD,Math.min(cap,totalDelta-0.5*d_volatility));
    const pre=base*agM*(1+deltaNoVol)*injP;
    blendW=form.g/(form.g+blendKv);
    proj=(blendW*form.ppg+(1-blendW)*pre)*(1+0.5*d_volatility);
  }

  // ── FIX 2: MISS% AS HARD PROJECTION CEILING ────────────────────
  // High Miss% players cannot project into reliable starter territory
  // regardless of other positive signals. A 65%+ Miss rate means the
  // player is genuinely unreliable — efficiency signals are misleading.
  // Ceiling is set relative to position average PPG:
  //   WR/RB avg starter: ~11.5 | TE avg starter: ~10.5 | QB: ~18.0
  if(gl && gl.g >= 20){
    const posCeil = pl.p==='QB'?22.0:pl.p==='TE'?11.5:12.5;
    if(gl.miss > 65) proj = Math.min(proj, posCeil * 0.92);       // hard ceiling
    else if(gl.miss > 55) proj = Math.min(proj, posCeil * 1.05);  // soft ceiling
  }

  // Model value: additive delta on market value, hard cap 19999 (raised from
  // 9999 after live FC anchors inflated past it and clipped elite model values;
  // the cap is a sanity ceiling only)
  // mv computed via mvAsset (includes all 5 features: contract, injury, scarcity, competition, volatility)
  const mv=mvAsset(fmtBack({...pl,proj,p:pl.p}));

  const oppSc=getOppScore(pl.n,pl.p);
  // ktcEff/gap compare against the MARKET in the SELECTED format (pl.kMkt).
  // e.ktc stays the 12-SF anchor the model rescales from via scarcity(); a manual
  // ktc override (OV) is an explicit market value and takes precedence.
  const kMkt=(OV[pl.n]&&OV[pl.n].ktc!==undefined)?e.ktc:(pl.kMkt!=null?pl.kMkt:e.ktc);
  const result={...pl,pos:pl.p,t:e.team,base,proj,projPre,inSeason:form&&blendW?{g:form.g,ppg:form.ppg,w:blendW,k:blendKv}:null,floor:proj*(1-ciV),ceil:proj*(1+ciV),mv,
    gap:mv-kMkt,sys:e.s,oc:e.oc,och:e.ch,ci:ciV,inj:e.inj,
    ktcEff:kMkt,notes:e.notes,hasOv:e.hasOv,role:roleData.mult,roleLabel:roleData.label,
    epaSc:epa.sc,epaRaw:epa.raw,epaFl:epa.fl,epaFr:epa.fr,epaTr:epa.tr,
    ef25:epa.ef25,ef24:epa.ef24,e25:epa.e25,e24:epa.e24,e23:epa.e23,e22:epa.e22,oppSc};
  fmtBack(result);
  result.dsScore=calcDynastyScore(result);

  // ── Season-ending injury ───────────────────────────────────────────────────
  // Applied LAST, and only to the projection. Deliberately after mvAsset and
  // calcDynastyScore have run, so:
  //   * model value is untouched — the market prices the absence, not us
  //   * DELTA Score is untouched — it measures DEMONSTRATED value, and a missed
  //     season is not demonstrated until it lands in the data at the offseason
  //     roll, where the zero-branch in dsProduction fires on its own
  // The agreed extent of intervention is the projection plus a visible tag.
  if (INJ_OUT[result.n]) {
    result.proj = 0; result.floor = 0; result.ceil = 0;
    result.outForSeason = true;
  }
  return result;
}

// ── Market calibration of model values ───────────────────────
// The mvDelta feature stack in mvAssetRaw is penalty-heavy by construction
// (competition ≤0 for all non-QBs; injury history, stability, volatility ≤0;
// clamp asymmetric at −0.35/+0.25), so raw model values run systematically
// below market — ~13% at the June 2026 calibration — and that bias moves
// whenever the engine changes. The bias carries no per-player information, so
// mvAsset() divides it out: MV_CENTER is the live population median of the
// raw anchor-basis model/market ratio, recomputed in renderAll(). Result: the
// MEDIAN tracked player shows Mod val ≈ Mkt val, displayed gaps align with
// buy/sell tags, and vTag's bands stay absolute (centered on 1.0). Picks and
// the rookie-override path are already market-scale and pass through raw.
// Note: the 2-team trade verdict (calcAdjustedSide) is built on market value,
// not mvAsset — calibration does not move trade verdicts.
let MV_CENTER=1;   // 1 = raw basis; computed per render in renderAll()

// ── Price-tapered centering (Aug 2026) ────────────────────────────
// Set as a side effect of computeMvCenter() so the two render call sites
// (renderAll in index.html, the player.html bootstrap) need no change.
// MV_FIT_B===null means "no usable fit" and applyCenter falls back to the
// flat MV_CENTER divide — i.e. exactly the behaviour before this change.
let MV_FIT_A=null, MV_FIT_B=null, MV_NORM=1;

// ── ANNUAL MAINTENANCE: bump this every offseason ──────────────────
// The upcoming NFL season. Used by vTag's thin-sample cap to work out how many
// games' worth of CHANCES a player has had (seasons since draft x 17). If this
// is left stale, every player looks a year less experienced than he is and the
// cap silences strong verdicts it should be allowing.
const SEASON_YEAR = 2026;
function marketSpread(pl){
  // Format rescale for MODEL VALUES: the market's own observed per-player
  // spread (kMkt/k from the per-format grid), NOT the theoretical scarcity
  // curve. DELTA's curve diverges from the market's actual format spread
  // (e.g. QBs: −19% vs −2% going 12→10 teams), and that POSITION-level
  // disagreement was landing inside per-player rows as phantom gap. With the
  // observed spread, the displayed Mod/Mkt ratio is identical at every format
  // to the league-invariant anchor-basis ratio that vTag thresholds — tags
  // and displayed gaps always agree. The scarcity curve still owns the
  // trade-calc verdict (calcAdjustedSide), where it is externally validated.
  if(leagueTeams===12&&qbFmt==='sf') return 1;              // anchor basis (also covers mvAssetBase's pin)
  if(OV[pl.n]&&OV[pl.n].ktc!=null) return 1;                // manual market override is anchor-basis at all formats
  if(pl.kMkt!=null&&(pl.k||0)>0) return pl.kMkt/pl.k;       // observed market spread for this player
  return scarcity(pl.p||pl.pos||'WR', leagueTeams, qbFmt);  // pre-grid / unmatched fallback: theoretical curve
}
// Symmetric, price-tapered calibration (Aug 2026). SUPERSEDES the June
// "Option B" ratchet, which scaled up ONLY players below market and exempted
// the rest. That exemption was measured and rejected: it was not order-
// preserving (3,164 inverted pairs — a player at 0.98x market was lifted above
// one at 1.11x).
//
// The penalty stack is one-directional by construction, which drags the
// population below market. But the drag is NOT the same size for everyone —
// it scales with price. Measured on live data, the top 50 players by market
// value carry essentially no drag (median model/market 1.01) while the cheapest
// tier carries 23%. Dividing everyone by one constant therefore over-corrects
// the top: it hands a 19% lift to players who never had the problem, which is
// what made 96% of the top 25 read buy-or-better.
//
// So the divisor tapers with price: each player is corrected by the drag that
// players at HIS price level actually suffer.
//
// The taper is CAPPED so that no player is ever lifted MORE than the old flat
// centering lifted him — every player is either unchanged or corrected less.
// The clamp is applied AFTER MV_NORM, which is what makes that guarantee exact:
// clamping first and then normalising re-inflates the cheap end by ~2.7pts and
// puts 192 players above their old values. Without the cap at all, the bottom of
// the market gets a ~30% lift and deep bench players start reading as bargains,
// which is the lottery-ticket behaviour DELTA exists to avoid.
//
// MV_NORM re-seats the population toward 1.0 after the taper, since vTag's bands
// are absolute. Because the clamp is applied last, the median lands at ~0.985
// rather than exactly 1.0 — a deliberate trade: a 1.5% offset well inside the
// hold band, in exchange for the bottom of the market being left exactly where
// flat centering had it.
//
// NOT evidence-backed: there is no historical market-value archive to test this
// against, so it rests on the measured drag gradient plus judgement. The cap in
// particular is a conservative choice, not a derivation. Revisit after the
// first frozen season provides a yardstick. See /areas/delta.md.
function applyCenter(raw, mkt){
  if(MV_CENTER===1) return raw;            // pass 1 / no center yet
  if(MV_FIT_B===null || !(mkt>0)) return raw/MV_CENTER;   // no fit / no price → flat
  const fitted=Math.exp(MV_FIT_A + MV_FIT_B*Math.log(mkt));
  return raw/Math.max(fitted*MV_NORM, MV_CENTER);
}
function computeMvCenter(){
  // Call ONLY while MV_CENTER===1 (raw basis) — mvAssetBase must return raw here.
  // Returns the population median as before (the freeze pre-flight guard and the
  // provenance block both read it), and ALSO fits the price taper used by
  // applyCenter — see MV_FIT_A / MV_FIT_B / MV_NORM above.
  MV_FIT_A=null; MV_FIT_B=null; MV_NORM=1;   // reset every render
  const rs=[]; const pts=[];
  if(typeof COMP!=='undefined'){
    for(const p of COMP){
      if(((p.g25||0)+(p.g24||0)+(p.g23||0))===0) continue;  // same gate as vTag's "no data"
      const mkt=(OV[p.n]&&OV[p.n].ktc!=null)?OV[p.n].ktc:p.k;
      const ratio=mvAssetBase(p)/Math.max(mkt,1);
      rs.push(ratio);
      // Rookie-override players are EXCLUDED from the taper fit: mvAsset returns
      // market x age curve for them, so their "ratio" is just the age curve and
      // would flatten the fitted slope with a value the model never produced.
      // They stay in rs so the median (and its guard) are unchanged.
      const rookiePath=(p.g25===0||p.g25===undefined)&&(p.ppg25||0)>0;
      if(!rookiePath && mkt>0) pts.push({m:mkt, r:ratio});
    }
  }
  if(!rs.length) return 1;
  rs.sort(function(a,b){return a-b;});
  let c=rs[Math.floor(rs.length/2)];
  if(c<0.6||c>1.3){
    console.warn('[DELTA] model-value population center out of range ('+c.toFixed(3)+') — falling back to 1.0 (raw); check market/stats data');
    return 1;   // no taper either — applyCenter's MV_CENTER===1 guard passes raw through
  }
  // Least-squares fit of log(model/market) against log(market).
  if(pts.length>=30){
    let sx=0,sy=0; for(const q of pts){ sx+=Math.log(q.m); sy+=Math.log(q.r); }
    const mx=sx/pts.length, my=sy/pts.length;
    let sxy=0,sxx=0;
    for(const q of pts){ const dx=Math.log(q.m)-mx; sxy+=dx*(Math.log(q.r)-my); sxx+=dx*dx; }
    if(sxx>0){
      const B=sxy/sxx, A=my-B*mx;
      // Slope must be positive (drag shrinks as price rises) and modest. Anything
      // else means the data changed shape — fall back to flat centering.
      if(B>0 && B<0.5){
        MV_FIT_A=A; MV_FIT_B=B;
        // MV_NORM is measured against the CLAMPED taper (same shape applyCenter
        // uses), so the population re-seats near 1.0. applyCenter then clamps the
        // product, which lands the median at ~0.985 rather than exactly 1.0.
        const cor=pts.map(function(q){
          return q.r/Math.max(Math.exp(A+B*Math.log(q.m)), c);
        }).sort(function(a,b){return a-b;});
        MV_NORM=cor[Math.floor(cor.length/2)];
        if(!(MV_NORM>0.5&&MV_NORM<2)){ MV_FIT_A=null; MV_FIT_B=null; MV_NORM=1; }
      } else {
        console.warn('[DELTA] price-taper slope out of range ('+B.toFixed(3)+') — using flat centering');
      }
    }
  }
  return c;
}
function mvAsset(pl){
  if(pl.ip)return (pl.kMkt!=null?pl.kMkt:pl.k);              // picks: market scale already
  // Rookie override: no NFL data yet — use market value × age curve as model value
  // Bypasses delta machinery that tanks players with zero snap/YPRR data
  // (market-based, so NOT divided by the center)
  if((pl.g25===0||pl.g25===undefined)&&(pl.ppg25||0)>0){
    const agMrk=am(pl.p||pl.pos,Math.floor(pl.a||22));
    return Math.min(19999,Math.round((pl.k||0)*agMrk*marketSpread(pl)));
  }
  const rawMV=mvAssetRaw(pl);                                   // anchor basis
  const mktMV=(OV[pl.n]&&OV[pl.n].ktc!=null)?OV[pl.n].ktc:(pl.k||0);
  const calibrated=applyCenter(rawMV,mktMV);                   // Option B, anchor basis
  return Math.min(19999,Math.round(calibrated*marketSpread(pl))); // format rescale last
}
function mvAssetRaw(pl){
  const e=getEff(pl);
  const epa=calcEPA(pl.n,pl.p||pl.pos);
  const roleData=getRoleData(pl.n,pl.p||pl.pos);
  const col=CB[pl.n]||1.0;
  // Ripple (RP) is a FORWARD-LOOKING speculation lever (trade/role-change) that
  // already flows into Projected PPG via calcProj. Letting it ALSO vote in model
  // value double-counted the same speculation (Walker's KC +8% landed twice).
  // Model value stays neutral on ripple; the projection owns the forward view.
  // Removed June 2026.
  const rip=1.0;
  const qbq=(pl.p||pl.pos)!=='QB'?(QBQ[AL[e.team]||e.team]||0.85):1.0;

  // Use same proven-player adjustments as calcProj so vTag matches rankings
  const pos_mv2=pl.p||pl.pos;
  const provenThreshMV=pos_mv2==='QB'?16:pos_mv2==='RB'?12:pos_mv2==='WR'?11:pos_mv2==='TE'?9:11;
  const baseMV=((pl.ppg25||0)*3+(pl.ppg24||0)*2+(pl.ppg23||0))/Math.max(((pl.ppg25||0)>0?3:0)+((pl.ppg24||0)>0?2:0)+((pl.ppg23||0)>0?1:0),1);
  const isProvenMV=baseMV>=provenThreshMV||(pl.ppg25||0)>=provenThreshMV;
  const adjContMV=isProvenMV&&e.c<0.70?e.c+(0.70-e.c)*0.60:e.c;
  const adjSysMV=isProvenMV&&e.s<55?Math.min(e.s+10,55):e.s;

  // Use regressed YPRR same as calcProj
  let adjRoleMV=roleData.raw;
  if((pos_mv2==='WR'||pos_mv2==='TE')&&adjRoleMV>0){
    const dMV=pos_mv2==='WR'?YPRR_WR[pl.n]:YPRR_TE[pl.n];
    if(dMV){
      const avgMV=pos_mv2==='TE'?1.45:1.60;
      const sabMV=(dMV[1]>avgMV?1:0)+(dMV[2]>avgMV?1:0)+(dMV[3]>avgMV?1:0);
      if(sabMV<2&&adjRoleMV>avgMV) adjRoleMV=avgMV;
    }
  }

  const rawDelta=getDeltas(pl.n,pos_mv2,adjSysMV,adjContMV,adjRoleMV,roleData.raw,col,epa.sc,rip,qbq);

  // Volatility penalty (miss% suppresses value regardless of system)
  const glMV=glOf(pl);
  let d_vol_mv=0;
  if(glMV && glMV.g>=20){
    if(glMV.miss>65) d_vol_mv=-0.10;
    else if(glMV.miss>55) d_vol_mv=-0.06;
    else if(glMV.miss>45) d_vol_mv=-0.03;
    if(glMV.elite>30) d_vol_mv=Math.min(0,d_vol_mv+0.03);
  }

  // Stability penalty (single-spike seasons)
  const g25mv=pl.g25||0;
  let d_stab_mv=0;
  if((pl.ppg25||0)>0&&(pl.ppg24||0)>0&&(pl.ppg23||0)>0){
    const avg2324=((pl.ppg24||0)*2+(pl.ppg23||0))/3;
    const spike=(pl.ppg25||0)-avg2324;
    if(spike>0&&avg2324>0&&spike/avg2324>0.35){
      d_stab_mv=-Math.min(0.12,(spike/avg2324-0.35)*0.25);
      // If EPA/YPRR also improved significantly, breakout is real not a fluke
      const epaChk=EPA[pl.n];
      if(epaChk&&epaChk.e25&&epaChk.e24&&(epaChk.e25-epaChk.e24>0.30))
        d_stab_mv*=0.4;
    }
  }
  if(g25mv===0&&(pl.ppg25||0)===0) d_stab_mv-=0.10;

  // ── FEATURE 1: Contract year signal ─────────────────────────
  let d_contract_mv=0;
  const ctEntry=CONTRACTS.find(c=>c.n===pl.n);
  if(!ctEntry){
    d_contract_mv=-0.02; // no contract = uncertainty
  } else {
    const expiresIn=ctEntry.end-SEASON_YEAR;
    if(expiresIn<=0){ // walk year or expired
      const isProductive=(pl.ppg25||0)>=12;
      const isYoung=(pl.a||30)<29;
      d_contract_mv=isProductive&&isYoung?0.04:-0.03;
    }
    // multi-year deals: slight positive for security
    else if(expiresIn>=3) d_contract_mv=0.01;
  }

  // ── FEATURE 2: Injury history signal ────────────────────────
  let d_inj_hist=0;
  const pos2=pl.p||pl.pos;
  const g25h=pl.g25||0;
  const ppg24h=pl.ppg24||0;
  const ppg23h=pl.ppg23||0;
  // Missed most of 2025 (not a known full-year injury that's already priced via inj)
  if(g25h>0&&g25h<9) d_inj_hist-=0.04;
  // Missed significant games multiple recent seasons
  // A blank season only counts if the player was in the league that year (26 Sep
  // 2026). Before this, "no 2024 production" could not tell an injury from a
  // player who hadn't been drafted yet: 25 of the 35 graded players reaching this
  // cut were docked for a season before their draft (2025 rookies up to -8%).
  // 2026 rookies never get here (rookie shortcut in mvAsset). No draft record
  // (undrafted) = unchanged behaviour.
  const dyH=(DRAFT_PICKS[pl.n]||{}).y;
  const inLeague=yr=>!dyH||dyH<=yr;
  if(g25h<14&&ppg24h===0&&(pl.a||30)>22&&inLeague(2024)) d_inj_hist-=0.03;
  if(g25h<14&&ppg23h===0&&ppg24h===0&&(pl.a||30)>23&&inLeague(2023)) d_inj_hist-=0.02;
  d_inj_hist=Math.max(-0.08,d_inj_hist);

  // ── FEATURE 3: Positional scarcity ──────────────────────────
  const proj_mv=pl.proj||0;
  const d_scarcity=scarcityBonus(pos2,proj_mv);

  // ── FEATURE 4: Team competition index ───────────────────────
  let d_comp=0;
  if(!COMP_EXEMPT.has(pl.n)&&pos2!=='QB'){
    d_comp=-(COMP_IDX[AL[e.team]||e.team]||0);
  }

  // ── Rising/Fading trend signal ───────────────────────────────
  const trendMV=TREND_TAG[pl.n];
  const d_trend=trendMV==='rising'?0.025:trendMV==='fading'?-0.015:0;

  // ── FEATURE 5b: Format-aware dynasty value ──────────────────
  const d_fmt=formatMvShift(pl.n,pos2,scoringFmt);

  // Franchise cornerstone players (COMP_EXEMPT) adapt new OCs to them, not vice versa
  const isFranchise=COMP_EXEMPT.has(pl.n);
  const trendForCi=TREND_TAG[pl.n];
  const ciMult=pos2==='RB'?0.5:isFranchise?0.4:(pos2==='QB'&&trendForCi==='rising')?0.5:1.0;
  const mvDelta=Math.max(-0.35,Math.min(0.25,
    rawDelta+((ci(e.c)-0.15)*(-0.3))*ciMult
    +d_vol_mv+d_stab_mv
    +d_contract_mv+d_inj_hist
    +d_scarcity+d_comp
    +d_trend+d_fmt
  ));
  const agM=am(pl.p||pl.pos,Math.floor(pl.a||26));
  // Anchor-basis raw (NO marketSpread here). Format rescale is applied by the
  // caller AFTER calibration so applyCenter compares anchor-raw vs anchor-market
  // consistently — composing marketSpread into raw broke that at 1QB formats.
  // No backup charge here (owner, 3 Oct 2026). Model value is built from the market price, and the
  // market already prices a backup's role — the x0.55 charged it a second time (flagged veteran QBs sat
  // at a median 46% of market vs 93% for everyone else). e.injP keeps AVAIL (per-game quality, e.g.
  // Mahomes) and drops only the role charge. Role news still reaches model value through the market.
  return Math.min(19999,Math.round(e.ktc*agM*(1+mvDelta)*e.injP));
}

/* CONTRACTS — DELTA's own contracts table (25 Oct 2026, legal compliance plan step 8).
   The source of truth is data/delta-contracts.json: one row per player, each built from the original
   news report of the signing, with its link (never OverTheCap or Spotrac). The owner's rules for end
   years (contract_rule, rookie_rule) are written in that file. The Score reads only `end`; the pages
   also show aav/total, `kind` (rookie deals show "Rookie Deal", no dollars) and the option status.
   This replaced the OverTheCap feed (data/player-contracts.json) and the hand list that used to sit
   here (its source line said "Spotrac screenshots").
   Filled as this file loads from the built-in copy below, so the first draw already matches the
   table; loadPlayerContracts() then refreshes it from the file. If the file fails to load, the
   copy stays in use (owner, 25 Oct 2026). A player whose row has no end year (free agent, retired,
   left his team) gets no entry here, which dsCont() scores as a neutral 5. */
// <contracts-backup>
/* Built-in copy of data/delta-contracts.json, written by scripts/build-contracts-backup.js.
   Do not edit by hand: change the table, then run the script. The nightly fails if they differ. */
const DL_CONTRACTS_BACKUP_ASOF="2026-10-25";
const DL_CONTRACTS_BACKUP={
  "A.J. Brown":{team:"NE",end:2029,kind:"extension",aav:32,total:96},
  "AJ Barner":{team:"SEA",end:2027,kind:"rookie",aav:null,total:null},
  "Aaron Jones":{team:"MIN",end:2026,kind:"veteran",aav:null,total:null},
  "Aaron Rodgers":{team:"PIT",end:2026,kind:"veteran",aav:22,total:22},
  "Adam Randall":{team:"BAL",end:2029,kind:"rookie",aav:null,total:null},
  "Adonai Mitchell":{team:"NYJ",end:2027,kind:"rookie",aav:null,total:null},
  "Alec Pierce":{team:"IND",end:2029,kind:"veteran",aav:28.5,total:114},
  "Alexander Mattison":{team:null,end:null,kind:"free_agent",aav:null,total:null},
  "Alvin Kamara":{team:"NO",end:2026,kind:"veteran",aav:null,total:null},
  "Amon-Ra St. Brown":{team:"DET",end:2028,kind:"extension",aav:30,total:120},
  "Andrei Iosivas":{team:"CIN",end:2026,kind:"rookie",aav:null,total:null},
  "Anthony Richardson":{team:"IND",end:2026,kind:"rookie",aav:null,total:null,option:"declined"},
  "Antonio Williams":{team:"WAS",end:2029,kind:"rookie",aav:null,total:null},
  "Arian Smith":{team:"NYJ",end:2028,kind:"rookie",aav:null,total:null},
  "Ashton Jeanty":{team:"LV",end:2028,kind:"rookie",aav:null,total:null,option:"available"},
  "Audric Estime":{team:"CLE",end:2026,kind:"veteran",aav:null,total:null},
  "Austin Ekeler":{team:"WAS",end:2026,kind:"veteran",aav:null,total:null},
  "Baker Mayfield":{team:"TB",end:2029,kind:"extension",aav:55,total:165},
  "Barion Brown":{team:"NO",end:2029,kind:"rookie",aav:null,total:null},
  "Ben Sinnott":{team:"WAS",end:2027,kind:"rookie",aav:null,total:null},
  "Bhayshul Tuten":{team:"JAC",end:2028,kind:"rookie",aav:null,total:null},
  "Bijan Robinson":{team:"ATL",end:2030,kind:"extension",aav:22.25,total:66.75},
  "Blake Corum":{team:"LAR",end:2027,kind:"rookie",aav:null,total:null},
  "Bo Nix":{team:"DEN",end:2027,kind:"rookie",aav:null,total:null,option:"available"},
  "Braelon Allen":{team:"NYJ",end:2027,kind:"rookie",aav:null,total:null},
  "Brandon Aiyuk":{team:"SF",end:null,kind:"left_team",aav:null,total:null},
  "Brashard Smith":{team:"KC",end:2028,kind:"rookie",aav:null,total:null},
  "Breece Hall":{team:"NYJ",end:2028,kind:"extension",aav:15.25,total:45.75},
  "Brenen Thompson":{team:"LAC",end:2029,kind:"rookie",aav:null,total:null},
  "Brenton Strange":{team:"JAC",end:2029,kind:"extension",aav:16,total:48},
  "Brian Robinson":{team:"ATL",end:2026,kind:"veteran",aav:null,total:null},
  "Brian Thomas Jr.":{team:"JAC",end:2027,kind:"rookie",aav:null,total:null,option:"available"},
  "Brock Bowers":{team:"LV",end:2027,kind:"rookie",aav:null,total:null,option:"available"},
  "Brock Purdy":{team:"SF",end:2030,kind:"extension",aav:53,total:265},
  "Bryce Lance":{team:"NO",end:2029,kind:"rookie",aav:null,total:null},
  "Bryce Young":{team:"CAR",end:2027,kind:"rookie_option",aav:null,total:null,option:"exercised"},
  "Bucky Irving":{team:"TB",end:2027,kind:"rookie",aav:null,total:null},
  "C.J. Stroud":{team:"HOU",end:2027,kind:"rookie_option",aav:null,total:null,option:"exercised"},
  "CJ Daniels":{team:"LAR",end:2029,kind:"rookie",aav:null,total:null},
  "Cade Klubnik":{team:"NYJ",end:2029,kind:"rookie",aav:null,total:null},
  "Cade Otton":{team:"TB",end:2028,kind:"veteran",aav:null,total:null},
  "Caleb Douglas":{team:"MIA",end:2029,kind:"rookie",aav:null,total:null},
  "Caleb Williams":{team:"CHI",end:2027,kind:"rookie",aav:null,total:null,option:"available"},
  "Calvin Austin":{team:"NYG",end:2026,kind:"veteran",aav:null,total:null},
  "Calvin Ridley":{team:"TEN",end:2027,kind:"veteran",aav:23,total:92},
  "Cam Skattebo":{team:"NYG",end:2028,kind:"rookie",aav:null,total:null},
  "Cam Ward":{team:"TEN",end:2028,kind:"rookie",aav:null,total:null,option:"available"},
  "Carnell Tate":{team:"TEN",end:2029,kind:"rookie",aav:null,total:null,option:"available"},
  "Carson Beck":{team:"ARI",end:2029,kind:"rookie",aav:null,total:null},
  "Cedric Tillman":{team:"NO",end:2026,kind:"practice_squad",aav:null,total:null},
  "CeeDee Lamb":{team:"DAL",end:2028,kind:"extension",aav:34,total:136},
  "Charlie Kolar":{team:"LAC",end:2028,kind:"veteran",aav:null,total:null},
  "Chase Brown":{team:"CIN",end:2026,kind:"rookie",aav:null,total:null},
  "Chigoziem Okonkwo":{team:"WAS",end:2028,kind:"veteran",aav:9,total:27},
  "Chimere Dike":{team:"TEN",end:2028,kind:"rookie",aav:null,total:null},
  "Chris Bell":{team:"MIA",end:2029,kind:"rookie",aav:null,total:null},
  "Chris Brazzell II":{team:"CAR",end:2029,kind:"rookie",aav:null,total:null},
  "Chris Brooks":{team:"GB",end:2027,kind:"veteran",aav:2.43,total:4.85},
  "Chris Godwin":{team:"TB",end:2027,kind:"veteran",aav:22,total:66},
  "Chris Olave":{team:"NO",end:2030,kind:"extension",aav:33,total:132,option:"exercised"},
  "Chris Rodriguez":{team:"JAC",end:2027,kind:"veteran",aav:5,total:10},
  "Christian Kirk":{team:"SF",end:2026,kind:"veteran",aav:6,total:6},
  "Christian McCaffrey":{team:"SF",end:2027,kind:"extension",aav:19,total:38},
  "Christian Watson":{team:"GB",end:2030,kind:"extension",aav:27.63,total:110.5},
  "Chuba Hubbard":{team:"CAR",end:2028,kind:"extension",aav:null,total:null},
  "Colbie Young":{team:"CIN",end:2029,kind:"rookie",aav:null,total:null},
  "Colby Parkinson":{team:"LAR",end:2026,kind:"veteran",aav:7.5,total:22.5},
  "Cole Kmet":{team:"CHI",end:2027,kind:"extension",aav:12.5,total:50},
  "Cole Payton":{team:"PHI",end:2029,kind:"rookie",aav:null,total:null},
  "Colston Loveland":{team:"CHI",end:2028,kind:"rookie",aav:null,total:null,option:"available"},
  "Cooper Kupp":{team:"SEA",end:2027,kind:"veteran",aav:15,total:45},
  "Courtland Sutton":{team:"DEN",end:2029,kind:"extension",aav:23,total:92},
  "Cyrus Allen":{team:"KC",end:2029,kind:"rookie",aav:null,total:null},
  "D'Andre Swift":{team:"CHI",end:2029,kind:"extension",aav:11.25,total:33.75},
  "D.J. Moore":{team:"BUF",end:2028,kind:"extension",aav:27.5,total:110},
  "DJ Giddens":{team:"IND",end:2028,kind:"rookie",aav:null,total:null},
  "DK Metcalf":{team:"PIT",end:2029,kind:"extension",aav:30,total:150},
  "Dak Prescott":{team:"DAL",end:2028,kind:"extension",aav:60,total:240},
  "Dallas Goedert":{team:"PHI",end:2026,kind:"veteran",aav:7,total:7},
  "Dalton Kincaid":{team:"BUF",end:2027,kind:"rookie_option",aav:null,total:null,option:"exercised"},
  "Dalton Schultz":{team:"HOU",end:2027,kind:"extension",aav:12.6,total:12.6},
  "Damien Martinez":{team:null,end:null,kind:"free_agent",aav:null,total:null},
  "Daniel Jones":{team:"IND",end:2027,kind:"veteran",aav:44,total:88},
  "Darius Slayton":{team:null,end:null,kind:"free_agent",aav:null,total:null},
  "Darnell Mooney":{team:"NYG",end:2026,kind:"veteran",aav:null,total:null},
  "Darnell Washington":{team:"PIT",end:2030,kind:"extension",aav:10.5,total:42},
  "Davante Adams":{team:"LAR",end:2026,kind:"veteran",aav:null,total:null},
  "David Montgomery":{team:"HOU",end:2027,kind:"veteran",aav:8.25,total:16.5},
  "David Njoku":{team:"LAC",end:2026,kind:"veteran",aav:null,total:null},
  "Davis Mills":{team:"HOU",end:2026,kind:"extension",aav:7,total:7},
  "Dawson Knox":{team:"BUF",end:2028,kind:"veteran",aav:null,total:null},
  "De'Von Achane":{team:"MIA",end:2030,kind:"extension",aav:16,total:64},
  "De'Zhaun Stribling":{team:"SF",end:2029,kind:"rookie",aav:null,total:null},
  "DeMario Douglas":{team:"NE",end:2026,kind:"rookie",aav:null,total:null},
  "DeVonta Smith":{team:"PHI",end:2028,kind:"extension",aav:25,total:75},
  "Deebo Samuel":{team:"SF",end:2026,kind:"veteran",aav:7,total:7},
  "Deion Burks":{team:"IND",end:2029,kind:"rookie",aav:null,total:null},
  "Demond Claiborne":{team:"MIN",end:2029,kind:"rookie",aav:null,total:null},
  "Denzel Boston":{team:"CLE",end:2029,kind:"rookie",aav:null,total:null},
  "Derrick Henry":{team:"BAL",end:2026,kind:"extension",aav:15,total:30},
  "Deshaun Watson":{team:"CLE",end:2029,kind:"veteran",aav:46,total:230},
  "Devaughn Vele":{team:"NO",end:2027,kind:"rookie",aav:null,total:null},
  "Devin Neal":{team:"WAS",end:2026,kind:"practice_squad",aav:null,total:null},
  "Devin Singletary":{team:"NYG",end:2026,kind:"veteran",aav:null,total:null},
  "Dillon Gabriel":{team:"CLE",end:2028,kind:"rookie",aav:null,total:null},
  "Dont'e Thornton":{team:"LV",end:2028,kind:"rookie",aav:null,total:null},
  "Dontayvion Wicks":{team:"PHI",end:2027,kind:"extension",aav:12.5,total:12.5},
  "Drake London":{team:"ATL",end:2030,kind:"extension",aav:35.25,total:141,option:"exercised"},
  "Drake Maye":{team:"NE",end:2027,kind:"rookie",aav:null,total:null,option:"available"},
  "Drew Allar":{team:"PIT",end:2029,kind:"rookie",aav:null,total:null},
  "Dylan Sampson":{team:"CLE",end:2028,kind:"rookie",aav:null,total:null},
  "Efton Chism":{team:"NE",end:2027,kind:"rookie",aav:null,total:null},
  "Eli Heidenreich":{team:"PIT",end:2029,kind:"rookie",aav:null,total:null},
  "Eli Raridon":{team:"NE",end:2029,kind:"rookie",aav:null,total:null},
  "Eli Stowers":{team:"PHI",end:2029,kind:"rookie",aav:null,total:null},
  "Elic Ayomanor":{team:"TEN",end:2028,kind:"rookie",aav:null,total:null},
  "Elijah Arroyo":{team:"SEA",end:2028,kind:"rookie",aav:null,total:null},
  "Elijah Higgins":{team:"ARI",end:2026,kind:"rookie",aav:null,total:null},
  "Elijah Sarratt":{team:"BAL",end:2029,kind:"rookie",aav:null,total:null},
  "Emanuel Wilson":{team:"SEA",end:2026,kind:"veteran",aav:2.1,total:2.1},
  "Emari Demercado":{team:"DAL",end:2026,kind:"veteran",aav:null,total:null},
  "Emeka Egbuka":{team:"TB",end:2028,kind:"rookie",aav:null,total:null,option:"available"},
  "Emmett Johnson":{team:"KC",end:2029,kind:"rookie",aav:null,total:null},
  "Erick All":{team:"CIN",end:2027,kind:"rookie",aav:null,total:null},
  "Evan Engram":{team:"DEN",end:2026,kind:"veteran",aav:null,total:null},
  "Fernando Mendoza":{team:"LV",end:2029,kind:"rookie",aav:null,total:null,option:"available"},
  "Gardner Minshew":{team:"ARI",end:2026,kind:"veteran",aav:8,total:8},
  "Garrett Nussmeier":{team:"KC",end:2029,kind:"rookie",aav:null,total:null},
  "Garrett Wilson":{team:"NYJ",end:2030,kind:"extension",aav:32.5,total:130,option:"exercised"},
  "Geno Smith":{team:"NYJ",end:2027,kind:"extension",aav:null,total:null},
  "George Holani":{team:"SEA",end:2026,kind:"veteran",aav:null,total:null},
  "George Kittle":{team:"SF",end:2029,kind:"extension",aav:19.1,total:76.4},
  "George Pickens":{team:"DAL",end:2026,kind:"franchise_tag",aav:null,total:null},
  "Germie Bernard":{team:"PIT",end:2029,kind:"rookie",aav:null,total:null},
  "Greg Dulcich":{team:"MIA",end:2026,kind:"veteran",aav:3.25,total:3.25},
  "Gunnar Helm":{team:"TEN",end:2028,kind:"rookie",aav:null,total:null},
  "Harold Fannin Jr.":{team:"CLE",end:2028,kind:"rookie",aav:null,total:null},
  "Hunter Henry":{team:"NE",end:2027,kind:"extension",aav:8,total:16},
  "Isaac Guerendo":{team:"SF",end:2027,kind:"rookie",aav:null,total:null},
  "Isaac TeSlaa":{team:"DET",end:2028,kind:"rookie",aav:null,total:null},
  "Isaiah Bond":{team:"CLE",end:2027,kind:"rookie",aav:null,total:null},
  "Isaiah Davis":{team:"NYJ",end:2027,kind:"rookie",aav:null,total:null},
  "Isaiah Likely":{team:"NYG",end:2028,kind:"veteran",aav:13.33,total:40},
  "Isiah Pacheco":{team:"DET",end:2026,kind:"veteran",aav:null,total:null},
  "J'Mari Taylor":{team:"JAC",end:2026,kind:"practice_squad",aav:null,total:null},
  "J.J. McCarthy":{team:"NYG",end:2027,kind:"rookie",aav:null,total:null,option:"available"},
  "J.K. Dobbins":{team:"DEN",end:2027,kind:"veteran",aav:null,total:null},
  "Ja'Kobi Lane":{team:"BAL",end:2029,kind:"rookie",aav:null,total:null},
  "Ja'Lynn Polk":{team:null,end:null,kind:"retired",aav:null,total:null},
  "Ja'Marr Chase":{team:"CIN",end:2029,kind:"extension",aav:40.25,total:161},
  "JaTavion Sanders":{team:"CAR",end:2027,kind:"rookie",aav:null,total:null},
  "Jack Bech":{team:"LV",end:2028,kind:"rookie",aav:null,total:null},
  "Jack Endries":{team:"CIN",end:2029,kind:"rookie",aav:null,total:null},
  "Jacob Cowing":{team:"SF",end:2027,kind:"rookie",aav:null,total:null},
  "Jacoby Brissett":{team:"ARI",end:2026,kind:"veteran",aav:21,total:21},
  "Jacory Croskey-Merritt":{team:"WAS",end:2028,kind:"rookie",aav:null,total:null},
  "Jadarian Price":{team:"SEA",end:2029,kind:"rookie",aav:null,total:null,option:"available"},
  "Jahan Dotson":{team:"ATL",end:2027,kind:"veteran",aav:7.5,total:15},
  "Jahdae Walker":{team:"CHI",end:2027,kind:"rookie",aav:null,total:null},
  "Jahmyr Gibbs":{team:"DET",end:2030,kind:"extension",aav:25.23,total:75.7},
  "Jake Ferguson":{team:"DAL",end:2029,kind:"extension",aav:13,total:52},
  "Jake Tonges":{team:"SF",end:2027,kind:"extension",aav:4,total:8},
  "Jakobi Meyers":{team:"JAC",end:2028,kind:"extension",aav:20,total:60},
  "Jalen Coker":{team:"CAR",end:2029,kind:"extension",aav:11.67,total:35},
  "Jalen Hurts":{team:"PHI",end:2028,kind:"extension",aav:51,total:255},
  "Jalen McMillan":{team:"TB",end:2027,kind:"rookie",aav:null,total:null},
  "Jalen Milroe":{team:"SEA",end:2028,kind:"rookie",aav:null,total:null},
  "Jalen Nailor":{team:"LV",end:2028,kind:"veteran",aav:null,total:null},
  "Jalen Royals":{team:"KC",end:2028,kind:"rookie",aav:null,total:null},
  "Jalen Tolbert":{team:"MIA",end:2026,kind:"veteran",aav:null,total:null},
  "Jam Miller":{team:"ATL",end:2026,kind:"practice_squad",aav:null,total:null},
  "Jameis Winston":{team:"NYG",end:2028,kind:"extension",aav:6.5,total:13},
  "James Conner":{team:"ARI",end:2026,kind:"veteran",aav:null,total:null},
  "James Cook":{team:"BUF",end:2029,kind:"extension",aav:12,total:48},
  "Jameson Williams":{team:"DET",end:2029,kind:"extension",aav:27.67,total:83,option:"exercised"},
  "Jared Goff":{team:"DET",end:2028,kind:"extension",aav:53,total:212},
  "Jaren Kanak":{team:"TEN",end:2029,kind:"rookie",aav:null,total:null},
  "Jarquez Hunter":{team:"NO",end:2026,kind:"practice_squad",aav:null,total:null},
  "Jauan Jennings":{team:"MIN",end:2026,kind:"veteran",aav:null,total:null},
  "Javonte Williams":{team:"DAL",end:2028,kind:"veteran",aav:8,total:24},
  "Jaxon Smith-Njigba":{team:"SEA",end:2031,kind:"extension",aav:42.2,total:168.8},
  "Jaxson Dart":{team:"NYG",end:2028,kind:"rookie",aav:null,total:null,option:"available"},
  "Jayden Daniels":{team:"WAS",end:2027,kind:"rookie",aav:null,total:null,option:"available"},
  "Jayden Higgins":{team:"HOU",end:2028,kind:"rookie",aav:null,total:null},
  "Jayden Reed":{team:"GB",end:2029,kind:"extension",aav:16.75,total:50.25},
  "Jaydon Blue":{team:"PHI",end:2026,kind:"practice_squad",aav:null,total:null},
  "Jaylen Waddle":{team:"DEN",end:2028,kind:"extension",aav:28.25,total:84.75},
  "Jaylen Warren":{team:"PIT",end:2027,kind:"extension",aav:5.83,total:17.5},
  "Jaylen Wright":{team:"MIA",end:2027,kind:"rookie",aav:null,total:null},
  "Jaylin Lane":{team:"WAS",end:2028,kind:"rookie",aav:null,total:null},
  "Jaylin Noel":{team:"HOU",end:2028,kind:"rookie",aav:null,total:null},
  "Jeff Caldwell":{team:"KC",end:2028,kind:"rookie",aav:null,total:null},
  "Jeremiyah Love":{team:"ARI",end:2029,kind:"rookie",aav:null,total:null,option:"available"},
  "Jerome Ford":{team:"WAS",end:2026,kind:"veteran",aav:null,total:null},
  "Jerry Jeudy":{team:"CLE",end:2027,kind:"extension",aav:19.33,total:58},
  "Jimmy Horn":{team:"CLE",end:2026,kind:"practice_squad",aav:null,total:null},
  "Joe Burrow":{team:"CIN",end:2029,kind:"extension",aav:55,total:275},
  "Joe Flacco":{team:"CIN",end:2026,kind:"veteran",aav:null,total:null},
  "Joe Milton":{team:"PHI",end:2026,kind:"veteran",aav:null,total:null},
  "Joe Mixon":{team:null,end:null,kind:"free_agent",aav:null,total:null},
  "Joe Royer":{team:"CLE",end:2029,kind:"rookie",aav:null,total:null},
  "John Metchie":{team:"CAR",end:2026,kind:"veteran",aav:null,total:null},
  "John Michael Gyllenborg":{team:"KC",end:2028,kind:"rookie",aav:null,total:null},
  "Jonah Coleman":{team:"DEN",end:2029,kind:"rookie",aav:null,total:null},
  "Jonathan Taylor":{team:"IND",end:2028,kind:"extension",aav:22,total:44},
  "Jonathon Brooks":{team:"CAR",end:2027,kind:"rookie",aav:null,total:null},
  "Jonnu Smith":{team:"GB",end:2026,kind:"veteran",aav:null,total:null},
  "Jordan Addison":{team:"MIN",end:2027,kind:"rookie_option",aav:null,total:null,option:"exercised"},
  "Jordan James":{team:"SF",end:2028,kind:"rookie",aav:null,total:null},
  "Jordan Love":{team:"GB",end:2028,kind:"extension",aav:55,total:220},
  "Jordan Mason":{team:"MIN",end:2026,kind:"veteran",aav:6,total:12},
  "Jordan Whittington":{team:"LAR",end:2027,kind:"rookie",aav:null,total:null},
  "Jordyn Tyson":{team:"NO",end:2029,kind:"rookie",aav:null,total:null,option:"available"},
  "Josh Allen":{team:"BUF",end:2030,kind:"extension",aav:55,total:330},
  "Josh Cameron":{team:"JAC",end:2029,kind:"rookie",aav:null,total:null},
  "Josh Downs":{team:"IND",end:2026,kind:"rookie",aav:null,total:null},
  "Josh Jacobs":{team:"GB",end:2027,kind:"veteran",aav:12,total:48},
  "Joshua Palmer":{team:"BUF",end:2027,kind:"veteran",aav:null,total:null},
  "Justice Hill":{team:"BAL",end:2026,kind:"extension",aav:3,total:6},
  "Justin Fields":{team:"KC",end:2026,kind:"veteran",aav:20,total:40},
  "Justin Herbert":{team:"LAC",end:2029,kind:"extension",aav:52.5,total:262.5},
  "Justin Jefferson":{team:"MIN",end:2028,kind:"extension",aav:35,total:140},
  "Justin Joly":{team:"MIA",end:2029,kind:"rookie",aav:null,total:null},
  "Juwan Johnson":{team:"NO",end:2027,kind:"veteran",aav:10,total:30},
  "K.J. Osborn":{team:"TEN",end:2026,kind:"veteran",aav:null,total:null},
  "KC Concepcion":{team:"CLE",end:2029,kind:"rookie",aav:null,total:null,option:"available"},
  "KaVontae Turpin":{team:"DAL",end:2027,kind:"veteran",aav:6,total:18},
  "Kaden Wetjen":{team:"PIT",end:2029,kind:"rookie",aav:null,total:null},
  "Kaelon Black":{team:"SF",end:2029,kind:"rookie",aav:null,total:null},
  "Kaleb Johnson":{team:"GB",end:2028,kind:"rookie",aav:null,total:null},
  "Kameron Johnson":{team:"TB",end:2026,kind:"rookie",aav:null,total:null},
  "Kareem Hunt":{team:null,end:null,kind:"free_agent",aav:null,total:null},
  "Kayshon Boutte":{team:"HOU",end:2026,kind:"rookie",aav:null,total:null},
  "Kaytron Allen":{team:"MIA",end:2029,kind:"rookie",aav:null,total:null},
  "KeAndre Lambert-Smith":{team:"LAC",end:2028,kind:"rookie",aav:null,total:null},
  "Keaton Mitchell":{team:"LAC",end:2027,kind:"veteran",aav:null,total:null},
  "Keenan Allen":{team:"IND",end:2026,kind:"veteran",aav:null,total:null},
  "Kendre Miller":{team:"NO",end:2026,kind:"rookie",aav:null,total:null},
  "Kendrick Bourne":{team:"ARI",end:2027,kind:"veteran",aav:5,total:10},
  "Kendrick Law":{team:"DET",end:2029,kind:"rookie",aav:null,total:null},
  "Kenneth Gainwell":{team:"TB",end:2027,kind:"veteran",aav:null,total:null},
  "Kenneth Walker III":{team:"KC",end:2028,kind:"veteran",aav:14.35,total:43.05},
  "Kenny McIntosh":{team:null,end:null,kind:"free_agent",aav:null,total:null},
  "Kenny Pickett":{team:"CAR",end:2026,kind:"veteran",aav:7.5,total:7.5},
  "Kenyon Sadiq":{team:"NYJ",end:2029,kind:"rookie",aav:null,total:null,option:"available"},
  "Keon Coleman":{team:"BUF",end:2027,kind:"rookie",aav:null,total:null},
  "Kevin Coleman":{team:"MIA",end:2029,kind:"rookie",aav:null,total:null},
  "Khalil Shakir":{team:"BUF",end:2029,kind:"extension",aav:13.25,total:53},
  "Kimani Vidal":{team:"LAC",end:2026,kind:"veteran",aav:null,total:null},
  "Kirk Cousins":{team:"LV",end:2028,kind:"veteran",aav:null,total:null},
  "Konata Mumpfield":{team:"LAR",end:2028,kind:"rookie",aav:null,total:null},
  "Kyle Monangai":{team:"CHI",end:2028,kind:"rookie",aav:null,total:null},
  "Kyle Pitts":{team:"ATL",end:2028,kind:"veteran",aav:18,total:54},
  "Kyle Williams":{team:"NE",end:2028,kind:"rookie",aav:null,total:null},
  "Kyler Murray":{team:"MIN",end:2026,kind:"veteran",aav:null,total:null},
  "Kyren Williams":{team:"LAR",end:2028,kind:"extension",aav:11,total:33},
  "Ladd McConkey":{team:"LAC",end:2027,kind:"rookie",aav:null,total:null},
  "Lamar Jackson":{team:"BAL",end:2027,kind:"veteran",aav:52,total:260},
  "LeQuint Allen":{team:"JAC",end:2028,kind:"rookie",aav:null,total:null},
  "Luke McCaffrey":{team:"WAS",end:2027,kind:"rookie",aav:null,total:null},
  "Luke Musgrave":{team:"GB",end:2026,kind:"rookie",aav:null,total:null},
  "Luther Burden":{team:"CHI",end:2028,kind:"rookie",aav:null,total:null},
  "Mac Jones":{team:"SF",end:2026,kind:"veteran",aav:4.2,total:8.4},
  "Mack Hollins":{team:"NE",end:2026,kind:"veteran",aav:4.2,total:8.4},
  "Makai Lemon":{team:"PHI",end:2029,kind:"rookie",aav:null,total:null,option:"available"},
  "Malachi Fields":{team:"NYG",end:2029,kind:"rookie",aav:null,total:null},
  "Malik Benson":{team:"LV",end:2029,kind:"rookie",aav:null,total:null},
  "Malik Davis":{team:"DAL",end:2026,kind:"veteran",aav:null,total:null},
  "Malik Nabers":{team:"NYG",end:2027,kind:"rookie",aav:null,total:null,option:"available"},
  "Malik Washington":{team:"MIA",end:2027,kind:"rookie",aav:null,total:null},
  "Malik Willis":{team:"MIA",end:2028,kind:"veteran",aav:22.5,total:67.5},
  "MarShawn Lloyd":{team:"GB",end:2027,kind:"rookie",aav:null,total:null},
  "Marcus Mariota":{team:"WAS",end:2026,kind:"veteran",aav:null,total:null},
  "Mark Andrews":{team:"BAL",end:2028,kind:"extension",aav:13.1,total:39.3},
  "Marlin Klein":{team:"HOU",end:2029,kind:"rookie",aav:null,total:null},
  "Marquise Brown":{team:"PHI",end:2026,kind:"veteran",aav:null,total:null},
  "Marvin Harrison Jr.":{team:"HOU",end:2027,kind:"rookie",aav:null,total:null,option:"available"},
  "Marvin Mims":{team:"DEN",end:2026,kind:"rookie",aav:null,total:null},
  "Mason Rudolph":{team:"PIT",end:2026,kind:"veteran",aav:null,total:null},
  "Mason Taylor":{team:"NYJ",end:2028,kind:"rookie",aav:null,total:null},
  "Matt Hibner":{team:"BAL",end:2029,kind:"rookie",aav:null,total:null},
  "Matthew Golden":{team:"GB",end:2028,kind:"rookie",aav:null,total:null,option:"available"},
  "Matthew Stafford":{team:"LAR",end:2027,kind:"extension",aav:55,total:55},
  "Max Klare":{team:"LAR",end:2029,kind:"rookie",aav:null,total:null},
  "Michael Carter":{team:"TEN",end:2026,kind:"veteran",aav:null,total:null},
  "Michael Mayer":{team:"LV",end:2029,kind:"extension",aav:15,total:45},
  "Michael Penix Jr.":{team:"ATL",end:2027,kind:"rookie",aav:null,total:null,option:"available"},
  "Michael Pittman Jr.":{team:"PIT",end:2028,kind:"extension",aav:19.67,total:59},
  "Michael Trigg":{team:"DAL",end:2026,kind:"practice_squad",aav:null,total:null},
  "Michael Wilson":{team:"ARI",end:2029,kind:"extension",aav:25,total:75},
  "Mike Evans":{team:"SF",end:2028,kind:"veteran",aav:14.17,total:42.5},
  "Mike Gesicki":{team:"CIN",end:2027,kind:"veteran",aav:8.5,total:25.5},
  "Mike Washington Jr.":{team:"LV",end:2029,kind:"rookie",aav:null,total:null},
  "Najee Harris":{team:"NYG",end:2026,kind:"veteran",aav:null,total:null},
  "Nate Boerkircher":{team:"JAC",end:2029,kind:"rookie",aav:null,total:null},
  "Nicholas Singleton":{team:"TEN",end:2029,kind:"rookie",aav:null,total:null},
  "Nick Chubb":{team:null,end:null,kind:"retired",aav:null,total:null},
  "Nico Collins":{team:"HOU",end:2027,kind:"extension",aav:24,total:72},
  "Noah Fant":{team:"NO",end:2027,kind:"veteran",aav:null,total:null},
  "Noah Gray":{team:"KC",end:2027,kind:"extension",aav:6.5,total:19.5},
  "Noah Thomas":{team:"CIN",end:2026,kind:"practice_squad",aav:null,total:null},
  "Odell Beckham":{team:"MIN",end:2026,kind:"practice_squad",aav:null,total:null},
  "Olamide Zaccheaus":{team:"ATL",end:2026,kind:"veteran",aav:null,total:null},
  "Ollie Gordon":{team:"MIA",end:2028,kind:"rookie",aav:null,total:null},
  "Omar Cooper":{team:"NYJ",end:2029,kind:"rookie",aav:null,total:null,option:"available"},
  "Omarion Hampton":{team:"LAC",end:2028,kind:"rookie",aav:null,total:null,option:"available"},
  "Oronde Gadsden":{team:"LAC",end:2028,kind:"rookie",aav:null,total:null},
  "Oscar Delp":{team:"NO",end:2029,kind:"rookie",aav:null,total:null},
  "Parker Washington":{team:"JAC",end:2026,kind:"rookie",aav:null,total:null},
  "Pat Bryant":{team:"DEN",end:2028,kind:"rookie",aav:null,total:null},
  "Pat Freiermuth":{team:"PIT",end:2028,kind:"extension",aav:12.1,total:48.4},
  "Patrick Mahomes":{team:"KC",end:2033,kind:"extension",aav:null,total:504.75},
  "Phil Mafah":{team:"NYG",end:2026,kind:"practice_squad",aav:null,total:null},
  "Puka Nacua":{team:"LAR",end:2026,kind:"rookie",aav:null,total:null},
  "Quentin Johnston":{team:"LAC",end:2027,kind:"rookie_option",aav:null,total:null,option:"exercised"},
  "Quinn Ewers":{team:"JAC",end:2028,kind:"rookie",aav:null,total:null},
  "Quinshon Judkins":{team:"CLE",end:2028,kind:"rookie",aav:null,total:null},
  "RJ Harvey":{team:"DEN",end:2028,kind:"rookie",aav:null,total:null},
  "Rachaad White":{team:"WAS",end:2026,kind:"veteran",aav:null,total:null},
  "Raheim Sanders":{team:"CLE",end:2027,kind:"rookie",aav:null,total:null},
  "Rashee Rice":{team:"KC",end:2026,kind:"rookie",aav:null,total:null},
  "Rashid Shaheed":{team:"SEA",end:2028,kind:"veteran",aav:17,total:51},
  "Rashod Bateman":{team:"BAL",end:2029,kind:"extension",aav:12.25,total:36.75},
  "Ray Davis":{team:"BUF",end:2027,kind:"rookie",aav:null,total:null},
  "Reggie Virgil":{team:"ARI",end:2029,kind:"rookie",aav:null,total:null},
  "Rhamondre Stevenson":{team:"NE",end:2028,kind:"extension",aav:9,total:36},
  "Ricky Pearsall":{team:"SF",end:2027,kind:"rookie",aav:null,total:null,option:"available"},
  "Rico Dowdle":{team:"PIT",end:2027,kind:"veteran",aav:6.13,total:12.25},
  "Riley Leonard":{team:"IND",end:2028,kind:"rookie",aav:null,total:null},
  "Robert Henry":{team:"SEA",end:2026,kind:"veteran",aav:null,total:null},
  "Roman Hemby":{team:"LV",end:2026,kind:"practice_squad",aav:null,total:null},
  "Roman Wilson":{team:"PIT",end:2027,kind:"rookie",aav:null,total:null},
  "Rome Odunze":{team:"CHI",end:2027,kind:"rookie",aav:null,total:null,option:"available"},
  "Romeo Doubs":{team:"NE",end:2029,kind:"veteran",aav:17.5,total:70},
  "Roschon Johnson":{team:"CHI",end:2026,kind:"rookie",aav:null,total:null},
  "Ryan Flournoy":{team:"DAL",end:2027,kind:"extension",aav:6,total:6},
  "Sam Darnold":{team:"SEA",end:2027,kind:"veteran",aav:33.5,total:100.5},
  "Sam LaPorta":{team:"DET",end:2026,kind:"rookie",aav:null,total:null},
  "Sam Roush":{team:"CHI",end:2029,kind:"rookie",aav:null,total:null},
  "Samaje Perine":{team:"CIN",end:2026,kind:"veteran",aav:null,total:null},
  "Saquon Barkley":{team:"PHI",end:2028,kind:"extension",aav:20.6,total:41.2},
  "Savion Williams":{team:"GB",end:2028,kind:"rookie",aav:null,total:null},
  "Sean Tucker":{team:"TB",end:2026,kind:"veteran",aav:null,total:null},
  "Seth McGowan":{team:"IND",end:2029,kind:"rookie",aav:null,total:null},
  "Shedeur Sanders":{team:"CLE",end:2028,kind:"rookie",aav:null,total:null},
  "Skyler Bell":{team:"BUF",end:2029,kind:"rookie",aav:null,total:null},
  "Stefon Diggs":{team:"WAS",end:2026,kind:"veteran",aav:null,total:null},
  "T.J. Hockenson":{team:"MIN",end:2027,kind:"extension",aav:16.5,total:66},
  "Tahj Brooks":{team:"CIN",end:2028,kind:"rookie",aav:null,total:null},
  "Tai Felton":{team:"MIN",end:2028,kind:"rookie",aav:null,total:null},
  "Tank Bigsby":{team:"PHI",end:2026,kind:"rookie",aav:null,total:null},
  "Tank Dell":{team:"HOU",end:2026,kind:"rookie",aav:null,total:null},
  "Tanner Koziol":{team:"JAC",end:2029,kind:"rookie",aav:null,total:null},
  "Tanner McKee":{team:"PHI",end:2026,kind:"rookie",aav:null,total:null},
  "Taylen Green":{team:"CLE",end:2029,kind:"rookie",aav:null,total:null},
  "Ted Hurst":{team:"TB",end:2029,kind:"rookie",aav:null,total:null},
  "Tee Higgins":{team:"CIN",end:2028,kind:"veteran",aav:28.75,total:115},
  "Terrance Ferguson":{team:"LAR",end:2028,kind:"rookie",aav:null,total:null},
  "Terry McLaurin":{team:"WAS",end:2028,kind:"extension",aav:32,total:96},
  "Tetairoa McMillan":{team:"CAR",end:2028,kind:"rookie",aav:null,total:null,option:"available"},
  "Tez Johnson":{team:"TB",end:2028,kind:"rookie",aav:null,total:null},
  "Theo Johnson":{team:"NYG",end:2027,kind:"rookie",aav:null,total:null},
  "Tony Pollard":{team:"TEN",end:2026,kind:"veteran",aav:8,total:24},
  "Tory Horton":{team:"SEA",end:2028,kind:"rookie",aav:null,total:null},
  "Travis Etienne":{team:"NO",end:2029,kind:"veteran",aav:12,total:48},
  "Travis Hunter":{team:"JAC",end:2028,kind:"rookie",aav:null,total:null,option:"available"},
  "Travis Kelce":{team:"KC",end:2026,kind:"veteran",aav:null,total:null},
  "Tre Harris":{team:"LAC",end:2028,kind:"rookie",aav:null,total:null},
  "Tre Tucker":{team:"LV",end:2026,kind:"rookie",aav:null,total:null},
  "TreVeyon Henderson":{team:"NE",end:2028,kind:"rookie",aav:null,total:null},
  "Trevor Etienne":{team:"CAR",end:2028,kind:"rookie",aav:null,total:null},
  "Trevor Lawrence":{team:"JAC",end:2030,kind:"extension",aav:55,total:275},
  "Trey Benson":{team:"ARI",end:2027,kind:"rookie",aav:null,total:null},
  "Trey Lance":{team:"LAC",end:2026,kind:"veteran",aav:6.75,total:6.75},
  "Trey McBride":{team:"ARI",end:2029,kind:"extension",aav:19,total:76},
  "Treylon Burks":{team:"WAS",end:2026,kind:"veteran",aav:null,total:null},
  "Troy Franklin":{team:"DEN",end:2027,kind:"rookie",aav:null,total:null},
  "Tua Tagovailoa":{team:"ATL",end:2026,kind:"veteran",aav:null,total:null},
  "Tucker Kraft":{team:"GB",end:2030,kind:"extension",aav:18.75,total:75},
  "Tutu Atwell":{team:"LAR",end:2026,kind:"veteran",aav:null,total:null},
  "Ty Johnson":{team:"BUF",end:2026,kind:"veteran",aav:null,total:null},
  "Ty Simpson":{team:"LAR",end:2029,kind:"rookie",aav:null,total:null,option:"available"},
  "Tyjae Spears":{team:"TEN",end:2026,kind:"rookie",aav:null,total:null},
  "Tyler Allgeier":{team:"ARI",end:2027,kind:"veteran",aav:6.13,total:12.25},
  "Tyler Higbee":{team:"LAR",end:2027,kind:"veteran",aav:null,total:null},
  "Tyler Huntley":{team:"BAL",end:2027,kind:"veteran",aav:null,total:null},
  "Tyler Shough":{team:"NO",end:2028,kind:"rookie",aav:null,total:null},
  "Tyler Warren":{team:"IND",end:2028,kind:"rookie",aav:null,total:null,option:"available"},
  "Tyquan Thornton":{team:"KC",end:2027,kind:"veteran",aav:null,total:null},
  "Tyreek Hill":{team:null,end:null,kind:"free_agent",aav:null,total:null},
  "Tyrod Taylor":{team:"GB",end:2026,kind:"veteran",aav:null,total:null},
  "Tyrone Tracy":{team:"NYG",end:2027,kind:"rookie",aav:null,total:null},
  "Tyson Bagent":{team:"CHI",end:2027,kind:"extension",aav:null,total:null},
  "Wan'Dale Robinson":{team:"TEN",end:2029,kind:"veteran",aav:19.5,total:78},
  "Will Howard":{team:"PIT",end:2028,kind:"rookie",aav:null,total:null},
  "Will Kacmarek":{team:"MIA",end:2029,kind:"rookie",aav:null,total:null},
  "Will Levis":{team:"NYJ",end:2026,kind:"practice_squad",aav:null,total:null},
  "Will Shipley":{team:"PHI",end:2027,kind:"rookie",aav:null,total:null},
  "Woody Marks":{team:"HOU",end:2028,kind:"rookie",aav:null,total:null},
  "Xavier Hutchinson":{team:"HOU",end:2026,kind:"rookie",aav:null,total:null},
  "Xavier Legette":{team:"CAR",end:2027,kind:"rookie",aav:null,total:null,option:"available"},
  "Xavier Restrepo":{team:"TEN",end:2026,kind:"practice_squad",aav:null,total:null},
  "Xavier Worthy":{team:"KC",end:2027,kind:"rookie",aav:null,total:null,option:"available"},
  "Zach Charbonnet":{team:"SEA",end:2026,kind:"rookie",aav:null,total:null},
  "Zach Ertz":{team:"PHI",end:2026,kind:"practice_squad",aav:null,total:null},
  "Zachariah Branch":{team:"ATL",end:2029,kind:"rookie",aav:null,total:null},
  "Zavion Thomas":{team:"CHI",end:2029,kind:"rookie",aav:null,total:null},
  "Zay Flowers":{team:"BAL",end:2031,kind:"extension",aav:35,total:140,option:"exercised"},
  "Zonovan Knight":{team:"ARI",end:2026,kind:"veteran",aav:null,total:null},
};
// </contracts-backup>
const CONTRACTS=[];
const DL_CONTRACT_ROWS={};        // every player's row, contract or not (team, kind, option): pages and ?dev=1
let DL_CONTRACTS_SOURCE='built-in copy';   // 'table' once data/delta-contracts.json has loaded
function dlContractsApply(rows){
  CONTRACTS.length=0;
  for(const k of Object.keys(DL_CONTRACT_ROWS)) delete DL_CONTRACT_ROWS[k];
  for(const r of RAW){
    const row=rows[r.n]; if(!row) continue;
    DL_CONTRACT_ROWS[r.n]=row;
    if(row.end==null) continue;
    const opt=row.option==null?null:(typeof row.option==='string'?row.option:row.option.status||null);
    CONTRACTS.push({ n:r.n, pos:r.p||r.pos||'', team:row.team||r.t||'',
      aav:Math.round((+row.aav||0)*1e6), total:Math.round((+row.total||0)*1e6),
      end:row.end, kind:row.kind||'', opt });
  }
}
dlContractsApply(DL_CONTRACTS_BACKUP);

const COLLEGES={
  'Jaxson Dart':'Ole Miss',
  'Cam Ward':'Miami',
  'Shedeur Sanders':'Colorado',
  'Drake Maye':'North Carolina',
  'Jayden Daniels':'LSU',
  'Caleb Williams':'USC',
  'Bo Nix':'Oregon',
  'Trevor Lawrence':'Clemson',
  'Justin Herbert':'Oregon',
  'Lamar Jackson':'Louisville',
  'Patrick Mahomes':'Texas Tech',
  'Josh Allen':'Wyoming',
  'Jalen Hurts':'Alabama/Oklahoma',
  'Joe Burrow':'LSU',
  'Brock Purdy':'Iowa State',
  'Jordan Love':'Utah State',
  'J.J. McCarthy':'Michigan',
  'Tyler Shough':'Louisville',
  'Michael Penix Jr.':'Washington',
  'Bryce Young':'Alabama',
  "Ja'Marr Chase":"LSU",
  'Justin Jefferson':'LSU',
  'CeeDee Lamb':'Oklahoma',
  'Amon-Ra St. Brown':'USC',
  'Stefon Diggs':'Maryland',
  'Davante Adams':'Fresno State',
  'A.J. Brown':'Ole Miss',
  'DK Metcalf':'Ole Miss',
  'DeVonta Smith':'Alabama',
  'Jaxon Smith-Njigba':'Ohio State',
  'Puka Nacua':'BYU',
  'Drake London':'USC',
  'Garrett Wilson':'Ohio State',
  'Chris Olave':'Ohio State',
  'Tee Higgins':'Clemson',
  'Jaylen Waddle':'Alabama',
  'Malik Nabers':'LSU',
  'Tetairoa McMillan':'Arizona',
  'Emeka Egbuka':'Ohio State',
  'Rome Odunze':'Washington',
  'Luther Burden':'Missouri',
  'Brian Thomas Jr.':'LSU',
  'Ladd McConkey':'Georgia',
  'Marvin Harrison Jr.':'Ohio State',
  'George Pickens':'Georgia',
  'Zay Flowers':'Boston College',
  'Rashee Rice':'SMU',
  'Jayden Higgins':'Iowa State',
  'Matthew Golden':'Texas',
  'Tre Harris':'Ole Miss',
  'Elic Ayomanor':'Stanford',
  'Travis Hunter':'Colorado',
  'Jordan Addison':'Pitt/USC',
  'Jayden Reed':'Michigan State',
  "Wan'Dale Robinson":"Kentucky",
  'Quentin Johnston':'TCU',
  'Terry McLaurin':'Ohio State',
  'Courtland Sutton':'SMU',
  'Jakobi Meyers':'NC State',
  'Michael Pittman Jr.':'USC',
  'Cooper Kupp':'Eastern Washington',
  'Keon Coleman':'Florida State',
  'Xavier Worthy':'Texas',
  'Khalil Shakir':'Boise State',
  'Romeo Doubs':'Nevada',
  'Christian Watson':'North Dakota State',
  'Josh Downs':'North Carolina',
  'D.J. Moore':'Maryland',
  'Rashid Shaheed':'Weber State',
  'Parker Washington':'Penn State',
  'Troy Franklin':'Oregon',
  'Jalen McMillan':'Washington',
  'Xavier Legette':'South Carolina',
  'Devaughn Vele':'Utah',
  'Jalen Coker':'Holy Cross',
  'Adonai Mitchell':'Texas',
  'Pat Bryant':'Illinois',
  'Cedric Tillman':'Tennessee',
  'Tez Johnson':'Oregon',
  'Jaylin Noel':'Iowa State',
  'DeMario Douglas':'Liberty',
  'Jack Bech':'TCU',
  'Kyle Williams':'Washington State',
  'Rashod Bateman':'Minnesota',
  'Dontayvion Wicks':'Virginia',
  'Chimere Dike':'Wisconsin',
  'Marvin Mims':'Oklahoma',
  'Jalen Nailor':'Michigan State',
  'Tank Dell':'Houston',
  'Bijan Robinson':'Texas',
  'Jahmyr Gibbs':'Georgia Tech',
  "De'Von Achane":"Texas A&M",
  'Ashton Jeanty':'Boise State',
  'Omarion Hampton':'North Carolina',
  'Quinshon Judkins':'Ole Miss/Ohio State',
  'TreVeyon Henderson':'Ohio State',
  'RJ Harvey':'UCF',
  'Cam Skattebo':'Arizona State',
  'Jonathon Brooks':'Texas',
  'James Cook':'Georgia',
  'Jonathan Taylor':'Wisconsin',
  'Christian McCaffrey':'Stanford',
  'Saquon Barkley':'Penn State',
  'Kyren Williams':'Notre Dame',
  'Travis Etienne':'Clemson',
  'Derrick Henry':'Alabama',
  'Breece Hall':'Iowa State',
  'Kenneth Walker III':'Michigan State',
  'Josh Jacobs':'Alabama',
  'Jaylen Warren':'Oklahoma State',
  'Javonte Williams':'North Carolina',
  'Chase Brown':'Illinois',
  'Tyrone Tracy':'Iowa',
  'Blake Corum':'Michigan',
  'J.K. Dobbins':'Ohio State',
  'Chuba Hubbard':'Oklahoma State',
  'Bhayshul Tuten':'Virginia Tech',
  'Jacory Croskey-Merritt':'Arizona State',
  'Kyle Monangai':'Rutgers',
  'Dylan Sampson':'Tennessee',
  'Jaylen Wright':'Tennessee',
  'Braelon Allen':'Wisconsin',
  'Trey Benson':'Florida State',
  "D'Andre Swift":"Georgia",
  'Rico Dowdle':'South Carolina',
  'Bucky Irving':'Oregon',
  'Rachaad White':'Arizona State',
  'Woody Marks':'USC',
  'Audric Estime':'Notre Dame',
  'MarShawn Lloyd':'USC',
  'Kimani Vidal':'Troy',
  'Keaton Mitchell':'East Carolina',
  'Tank Bigsby':'Auburn',
  'Ollie Gordon':'Oklahoma State',
  'Tyjae Spears':'Tulane',
  'Ray Davis':'Kentucky',
  'Brock Bowers':'Georgia',
  'Sam LaPorta':'Iowa',
  'Kyle Pitts':'Florida',
  'Trey McBride':'Colorado State',
  'George Kittle':'Iowa',
  'Travis Kelce':'Cincinnati',
  'Tyler Warren':'Penn State',
  'Harold Fannin Jr.':'Bowling Green',
  'Colston Loveland':'Michigan',
  'Tucker Kraft':'South Dakota State',
  'Dallas Goedert':'South Dakota State',
  'Mark Andrews':'Oklahoma',
  'T.J. Hockenson':'Iowa',
  'Dalton Kincaid':'Utah',
  'Oronde Gadsden':'Syracuse',
  'Juwan Johnson':'Penn State',
  'Hunter Henry':'Arkansas',
  'Jake Ferguson':'Wisconsin',
  'Dalton Schultz':'Stanford',
  'Pat Freiermuth':'Penn State',
  'Gunnar Helm':'Texas',
  'Mason Taylor':'LSU',
  'Isaiah Likely':'Coastal Carolina',
  'Evan Engram':'Ole Miss',
  'AJ Barner':'Michigan',
  'Cole Kmet':'Notre Dame',
  'Chigoziem Okonkwo':'Vanderbilt',
  'Brenton Strange':'Penn State',
  'Cade Otton':'Washington',
  'Terrance Ferguson':'Oregon',
  'Theo Johnson':'Penn State',
  'Dawson Knox':'Ole Miss',
  'Noah Fant':'Iowa',
  'Charlie Kolar':'Iowa State',
  'Jonnu Smith':'Florida International',
  'Elijah Higgins':'Stanford',
  'Greg Dulcich':'UCLA',
  'David Njoku':'Miami',
  'Colby Parkinson':'Stanford',
  'JaTavion Sanders':'Texas',
  'Ben Sinnott':'Kansas State',
  'Jake Tonges':'Cal',
  'Michael Mayer':'Notre Dame',
  'Zach Ertz':'Stanford'
};


// ── OPPORTUNITY SCORES ────────────────────────────────────────────────────────
// Alpha Score (WR/TE): target share + air yards share + RZ target share
// Workhorse Score (RB): rush volume + target share + RZ carry share + RZ targets
// Scale: 0-100. Elite ~93-97. League avg starter ~65-72. Committee/role ~45-60.
// 100 is reachable, not decorative: Josh Allen scores exactly 100 in 14-team
// superflex on 16 Aug 2026 data. calcDynastyScore clips at Math.min(100, ...) and
// the RB branch is scaled to the same ceiling (15 + 45*1.233 + 30*0.65 + 10 = 100).
// Every user-facing "0-99" was wrong, not the code.
// Data loaded from player-stats.json via loadPlayerStats()

let PLAYER_STATS = {}; // populated by loadPlayerStats()
let QB_ROLES = {};      // pipeline-emitted QB backup flags {name:{role,behind,source}} — model value (availMult)
let QB_ROLES_SCORE = {};   // the Score's own copy: 2025 incumbency, held all season (owner, 2 Oct 2026) — dsOpportunity
let HEADSHOTS = {};    // player name → headshot URL

function calcAlphaScore(name, src) {
  // src: an explicit stats row, used ONLY by opportunitySoFar() for the cards'
  // display line. Every scoring call passes one argument and reads 2025, unchanged.
  const s = src || PLAYER_STATS[name]?.['2025'];
  if (!s || !s.games) return null;
  const games = s.games || 1;

  /* MISSED-GAME CORRECTION — target_share, air_yds_share and rz_targets are all
     measured against FULL-SEASON team totals, so a player who missed games has
     his share mechanically depressed by the fraction of the season he sat out.
     Verified against the live data: implied team targets come out IDENTICAL for
     every teammate regardless of games played (every JAX player = 547, every DAL
     player = 607), which is only possible if the denominator is the full season.

     This mattered because tgtN(35%) + airN(30%) + rzN(25%) = 90% of this score
     scaled with availability, while gamesN(10%) below is the ONLY term that is
     SUPPOSED to. Injured players were docked roughly four times over for one
     absence. Brenton Strange (12 games) read as an 11.0% target share when his
     share across games he actually played was 15.6%.

     The correction TAPERS rather than stopping at a cliff. 10+ games gets the full
     rate (enough of a season to trust the role). Below 10 the player still gets
     credit, but only 40% of the amount beyond the 10-game rate, and never more than
     the 8-game rate (2.12x) no matter how few games he played. A flat cap at 1.70
     under-corrected exactly the group it was meant to help — Tucker Kraft (8 games)
     was short 20% of his earned correction, Garrett Wilson (7 games) short 30% —
     while an uncapped 17/g extrapolated a 4-game sample 4.25x, which is projection,
     not measurement, and rewards a hot start followed by an injury.
     Players who appeared in all 17 games are unaffected by construction. */
  const _earned = 17 / games;
  const _gn = games >= 10 ? _earned
            : Math.min(1.7 + (_earned - 1.7) * 0.4, 17 / 8);
  const tgtS  = (s.target_share  || 0) * _gn;
  const airS  = (s.air_yds_share || 0) * _gn;
  const rzT   = s.rz_targets != null ? s.rz_targets * _gn : s.rz_targets;

  // Ceilings calibrated against 2025 dataset:
  // tgt: Chase .321, JSN .368 → ceil .32 (JSN slightly above = max)
  // air: JSN .504, Jefferson .402 → ceil .46 (realistic elite)
  // rz:  Adams 32, Chase 22 → ceil 24 (Adams is historic outlier)
  const tgtN  = Math.min(1, tgtS  / 0.32);
  const airN  = Math.min(1, airS  / 0.46);
  const rzN   = rzT != null ? Math.min(1, rzT / 24) : tgtN * 0.7;
  const gamesN= Math.min(1, games / 17);

  const raw = tgtN*0.35 + airN*0.30 + rzN*0.25 + gamesN*0.10;

  // Scale: 30 floor, 99 theoretical ceiling
  return Math.round(30 + raw * 69);
}

function calcWorkhorseScore(name, src) {
  // src: see calcAlphaScore. Scoring calls pass one argument and read 2025.
  const s = src || PLAYER_STATS[name]?.['2025'];
  if (!s || !s.games) return null;
  const g     = s.games;
  // rush_share = player_rush_att / team_rush_att (season totals) — diluted by
  // missed games because the team's denominator includes all 17 games. Adjust
  // to per-game equivalent so injury absences don't misrepresent role intensity.
  // target_share is already a games-weighted per-game mean (from nflverse weekly
  // data), so no adjustment needed there.
  /* Both shares are season totals over a FULL-SEASON team denominator, so both
     are diluted by missed games. rush_share was already corrected here; target_share
     was NOT, on the stated belief that it "is already a games-weighted per-game mean
     (from nflverse weekly data)". That belief was wrong — implied team targets are
     identical across teammates regardless of games played, which can only happen with
     a full-season denominator. Both are corrected now, using the same taper as
     calcAlphaScore (full rate at 10+ games; 40% partial credit below, ceilinged at
     the 8-game rate). Keep the two in step — if one changes, change both. */
  const _earnedW = 17 / g;
  const _gn = g >= 10 ? _earnedW
            : Math.min(1.7 + (_earnedW - 1.7) * 0.4, 17 / 8);
  const rushS = Math.min(1, (s.rush_share || 0) * (17 / g));
  const tgtS  = (s.target_share || 0) * _gn;
  const rzC   = s.rz_carries;
  const rzT   = s.rz_targets;

  // Ceilings calibrated against 2025 full-season dataset:
  // rush_share/g: Bijan ~.65, CMC ~.55, Taylor ~.58 → ceil .65
  // tgt_share:    CMC .234, Achane .188 → ceil .24
  // rzC/game:     CMC 75/17≈4.4, Taylor 71/17≈4.2 → ceil 4.41 (=75/17)
  // rzT/game:     CMC 25/17≈1.5, Gibbs 15/17≈0.9 → ceil 1.53 (=26/17)
  const rushN = Math.min(1, rushS / 0.65);
  const tgtN  = Math.min(1, tgtS  / 0.24);
  const rzCpg = rzC != null ? rzC / g : null;
  const rzTpg = rzT != null ? rzT / g : null;
  const rzCN  = rzCpg != null ? Math.min(1, rzCpg / (75/17)) : rushN * 0.6;
  const rzTN  = rzTpg != null ? Math.min(1, rzTpg / (26/17)) : tgtN  * 0.6;

  const raw = rushN*0.50 + tgtN*0.15 + rzCN*0.30 + rzTN*0.05;
  return Math.round(28 + raw * 71);
}

function getOppScore(name, pos) {
  if (pos === 'WR' || pos === 'TE') return calcAlphaScore(name);
  if (pos === 'RB') return calcWorkhorseScore(name);
  return null;
}

/* ── THIS SEASON SO FAR — DISPLAY ONLY (owner, 4 Oct 2026) ─────────────────
   The Alpha / Workhorse the cards show for the season being played, beside the
   2025 number the DELTA Score uses. NOTHING SCORED READS THIS: not the DELTA
   Score, the projection, model value or the freeze. The Score holds in-season
   (§10b); this line lets a reader see a role change as it happens.

   data/season-so-far.json is built by scripts/fetch-season-so-far.py with the
   pipeline's own functions, so each share is defined exactly as the 2025 one.
   The formulas assume a 17-game season, so a part season is put on that basis
   first: games and red-zone counts scale by 17 / team games played; shares are
   already fractions of the team's games so far and pass through. With 17 team
   games the mapping is exact — it reproduced every 2025 score (632 of 632).
   Early weeks swing hard; the line always says how many games it is built on.
   Loaded lazily by the card itself — no boot chain changes, and the freeze
   never sees it. */
let SEASON_SO_FAR = null, SEASON_SO_FAR_STATE = 'idle', SEASON_SO_FAR_P = null;
function ensureSeasonSoFar(){
  if (SEASON_SO_FAR_P) return SEASON_SO_FAR_P;
  SEASON_SO_FAR_STATE = 'loading';
  SEASON_SO_FAR_P = fetch('data/season-so-far.json', { cache: 'no-cache' })
    .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(j => { SEASON_SO_FAR = (j && j.players) ? j : null; SEASON_SO_FAR_STATE = SEASON_SO_FAR ? 'ok' : 'failed'; })
    .catch(() => { SEASON_SO_FAR = null; SEASON_SO_FAR_STATE = 'failed'; });
  return SEASON_SO_FAR_P;
}
function opportunitySoFar(name, pos) {
  const r = SEASON_SO_FAR && SEASON_SO_FAR.players[name];
  if (!r || !r.games || !r.team_games) return null;
  const k = 17 / r.team_games;
  const src = { games: r.games * k, target_share: r.target_share, air_yds_share: r.air_yds_share,
                rush_share: r.rush_share,
                rz_targets: r.rz_targets == null ? null : r.rz_targets * k,
                rz_carries: r.rz_carries == null ? null : r.rz_carries * k };
  const sc = (pos === 'WR' || pos === 'TE') ? calcAlphaScore(name, src)
           : pos === 'RB' ? calcWorkhorseScore(name, src) : null;
  return sc == null ? null : { sc: sc, g: r.games, tg: r.team_games, season: SEASON_SO_FAR.season };
}
/* Sits directly under the card's main (last-season) score, as a boxed side-by-side
   so the two numbers read as a comparison (owner, 4 Oct). The change is in fog, not
   a signal colour: it is a fact about role, not a buy or sell. */
/* SIDE-BY-SIDE TILES (owner, 7 Oct 2026). The card read "2025 score, 2026 score, 2025
   stats", so the season of each number was easy to lose. Now the two scores sit side by
   side as matching tiles, each naming its season, and the usage rows below are labelled
   2025. oppTile draws one tile; oppTiles the pair. */
function oppTile(top, num, color, sub, id) {
  return '<div style="flex:1;min-width:0;box-sizing:border-box;background:var(--ink);border:1px solid var(--line);border-radius:8px;padding:10px 12px">'
    + '<div style="font-size:9.5px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:var(--fog)">' + top + '</div>'
    + '<div' + (id ? ' id="' + id + '"' : '') + ' style="font-size:28px;font-weight:800;line-height:1.1;margin-top:4px;color:' + color + '">' + num + '</div>'
    + '<div style="font-size:10.5px;color:var(--fog);margin-top:3px">' + sub + '</div></div>';
}
function oppSoFarInner(p) {
  const o = opportunitySoFar(p.n, p.pos);
  if (!o) return '';
  const base = getOppScore(p.n, p.pos);
  const d = base != null ? o.sc - base : null;
  const chg = d == null ? '' : (d === 0 ? 'no change' : (d > 0 ? '+' : '\u2212') + Math.abs(d) + ' vs ' + (o.season - 1));
  return oppTile(o.season + ' So Far', o.sc, oppScoreColor(o.sc),
    o.g + ' of ' + o.tg + ' games' + (chg ? ' \u00b7 ' + chg : ''));
}
/* The 2026 tile fills when its file arrives (the card is on the page by then — the fetch
   is never synchronous). No 2026 data: the slot is removed and the 2025 tile runs full width. */
function oppSoFarSlot(p) {
  if (SEASON_SO_FAR_STATE === 'ok') {
    const t = oppSoFarInner(p);
    return t ? '<div id="opp-sofar" style="flex:1;min-width:0;display:flex">' + t + '</div>' : '';
  }
  ensureSeasonSoFar().then(() => {
    const h = document.getElementById('opp-sofar');
    if (!h || h.dataset.n !== p.n) return;
    const t = oppSoFarInner(p);
    if (t) h.innerHTML = t; else h.remove();
  });
  return '<div id="opp-sofar" data-n="' + String(p.n).replace(/"/g, '&quot;') + '" style="flex:1;min-width:0;display:flex"></div>';
}
/* tier: the 2025 grade ("Clear starter"); scC: its colour. */
function oppTiles(p, sc, scC, tier) {
  // A grid, not flex: equal columns regardless of padding; with no 2026 tile, one column fills the row.
  return '<div style="display:grid;grid-auto-flow:column;grid-auto-columns:minmax(0,1fr);gap:8px;margin:2px 0 12px">'
    + oppTile('Last Season \u00b7 2025', sc, scC, tier, 'opp-score-val') + oppSoFarSlot(p) + '</div>';
}

/* ── EFFICIENCY THIS SEASON — DISPLAY ONLY (owner, 4 Oct 2026) ──────────────
   data/efficiency.json, built nightly by scripts/fetch-game-reads.py with the
   same numbers as Live's DELTA Read, filed under DELTA's own names. Each player
   in the measure DELTA uses for his position:
     QB  EPA per dropback · RB  EPA per carry   (last season = DELTA's stored e25)
     WR / TE  yards per route run. Last season uses REAL routes (nflverse participation
              — it reproduces DELTA's hand-entered 2025 YPRR at 0.99); this season's
              routes are estimated from snaps, corrected by each receiver's own ratio of
              real to estimated routes last season, so both sit on the hand table's scale.
   Tiers place a value against last season at the position: Elite (top 10%),
   Top Tier (top quarter), Typical (middle half), Below Typical (bottom quarter).
   Nothing scored reads this. Fed to: the So Far box under the efficiency card,
   the Game Log's Efficiency view, and two optional rankings columns. */
let EFF = null, EFF_STATE = 'idle', EFF_P = null;
function ensureEfficiency(){
  if (EFF_P) return EFF_P;
  EFF_STATE = 'loading';
  EFF_P = fetch('data/efficiency.json', { cache: 'no-cache' })
    .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(j => { EFF = (j && j.players) ? j : null; EFF_STATE = EFF ? 'ok' : 'failed'; })
    .catch(() => { EFF = null; EFF_STATE = 'failed'; });
  return EFF_P;
}
function effRec(name){ return EFF && EFF.players[name] || null; }
const EFF_MEASURE = { QB:'EPA Per Dropback', RB:'EPA Per Carry', WR:'Yards Per Route Run (Est.)', TE:'Yards Per Route Run (Est.)' };
const EFF_UNIT    = { QB:'dropbacks', RB:'carries', WR:'routes', TE:'routes' };
function effFmt(pos, v){
  if (v == null) return '\u2014';
  if (pos === 'WR' || pos === 'TE') return v.toFixed(2);
  const t = Math.abs(v).toFixed(2);
  return (Number(t) === 0 ? '' : (v < 0 ? '\u2212' : '+')) + t;     // never "-0.00"
}
/* floor: 'tier_min' for one game, 'season_min' for a season so far. Too few plays: no word. */
function effTier(pos, v, n, floor){
  const f = floor || 'tier_min';
  const c = EFF && EFF.tiers && EFF.tiers[pos], min = EFF && EFF[f] && EFF[f][pos];
  if (!c || v == null || n < (min || 0)) return '';
  return v >= c[2] ? 'Elite' : v >= c[1] ? 'Top Tier' : v >= c[0] ? 'Typical' : 'Below Typical';
}
/* Where a value would have ranked among last season's regulars at the position, 0-100. */
function effPct(pos, v){
  const d = EFF && EFF.dist && EFF.dist[pos];
  if (!d || v == null) return null;
  if (v <= d[0]) return 0;
  if (v >= d[20]) return 100;
  for (let i = 1; i <= 20; i++) if (v <= d[i]) {
    const lo = d[i-1], hi = d[i], fr = hi > lo ? (v - lo) / (hi - lo) : 0;
    return Math.round((i - 1 + fr) * 5);
  }
  return 100;
}
function effSoFarInner(p){
  const r = effRec(p.n);
  if (!r || r.sofar == null || r.pos !== p.pos) return '';
  const t = effTier(r.pos, r.sofar, r.n, 'season_min'), yr = EFF.season;
  /* ONE SLIM LINE (owner, 7 Oct 2026). A boxed panel with its own long title out-shouted the
     section it sits in, whose heading already names the measure. Now a single row: season and
     sample on the left, the number and tier on the right, sized like the card's other rows. */
  return '<div style="display:flex;justify-content:space-between;align-items:baseline;gap:10px;'
    + 'padding:7px 0;margin:0 0 10px;border-top:1px solid var(--line);border-bottom:1px solid var(--line)">'
    + '<div style="font-size:11px;color:var(--fog);min-width:0"><span style="font-weight:700;color:var(--paper)">' + yr + ' So Far</span>'
    + ' \u00b7 ' + r.games.length + ' games \u00b7 ' + r.n + ' ' + EFF_UNIT[r.pos]
    + ((r.pos === 'WR' || r.pos === 'TE') ? ' (est.)' : '') + '</div>'
    + '<div style="flex-shrink:0;white-space:nowrap;font-size:11px;color:var(--fog)">'
    + (t ? t + ' \u00b7 ' : '') + '<b style="font-size:13px;color:var(--paper)">' + effFmt(r.pos, r.sofar) + '</b></div></div>';
}
function effSoFarSlot(p){
  if (EFF_STATE === 'ok') return '<div id="eff-sofar">' + effSoFarInner(p) + '</div>';
  ensureEfficiency().then(() => {
    const h = document.getElementById('eff-sofar');
    if (h && h.dataset.n === p.n) h.innerHTML = effSoFarInner(p);
  });
  return '<div id="eff-sofar" data-n="' + String(p.n).replace(/"/g, '&quot;') + '"></div>';
}
/* Game Log -> Efficiency: every game this season in DELTA's measure, with its tier,
   against the player's season so far and last season. */
function gameLogEff(p){
  if (EFF_STATE !== 'ok'){
    ensureEfficiency().then(() => { if (_glView === 'eff' && _glPlayer === p) glSetView('eff'); });
    return '<div style="font-size:11px;color:var(--fog);padding:8px 0">' + (EFF_STATE === 'failed' ? 'Efficiency data is not available right now.' : 'Loading\u2026') + '</div>';
  }
  const r = effRec(p.n);
  if (!r || !r.games.length || r.pos !== p.pos) return '<div style="font-size:11px;color:var(--fog);padding:8px 0">No ' + EFF.season + ' games measured yet.</div>';
  const yr = EFF.season, est = '';
  const head = '<div style="display:flex;gap:16px;flex-wrap:wrap;font-size:11px;color:var(--fog);margin:2px 0 8px">'
    + '<span>' + yr + ' So Far <b style="color:var(--paper);font-family:var(--mono,monospace)">' + effFmt(r.pos, r.sofar) + '</b></span>'
    + '<span>' + (yr - 1) + est + ' <b style="color:var(--paper);font-family:var(--mono,monospace)">' + effFmt(r.pos, r.base) + '</b></span></div>';
  const rows = r.games.slice().sort((a, b) => b[0] - a[0]).map(g => {
    const t = effTier(r.pos, g[2], g[3], 'tier_min');
    return '<div style="display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid var(--line)">'
      + '<div style="width:48px;font-size:11px;color:var(--fog)">Wk ' + g[0] + '</div>'
      + '<div style="flex:1;font-size:11.5px;color:var(--paper)">vs ' + g[1]
      + '<span style="color:var(--fog-2);font-size:10.5px"> \u00b7 ' + g[3] + ' ' + EFF_UNIT[r.pos] + '</span></div>'
      + '<div style="text-align:right;min-width:86px"><b style="font-family:var(--mono,monospace);font-size:13px;color:var(--paper)">' + effFmt(r.pos, g[2]) + '</b>'
      + (t ? '<div style="font-size:10px;color:var(--fog)">' + t + '</div>' : '') + '</div></div>';
  }).join('');
  return '<div style="font-size:10.5px;color:var(--fog-2);margin-bottom:2px">' + EFF_MEASURE[r.pos] + '</div>' + head + rows
    + '<div style="font-size:9.5px;color:var(--fog-2);margin-top:6px;line-height:1.5">Tier words place each game against last season at his position. '
    + 'One game is noisy \u2014 look for the same direction over several. A game with too few plays gets no word.</div>';
}

function oppScoreColor(score) {
  // Tokens, not hex — same colours, but resolving through :root is what lets a palette
  // change reach the style attributes these land in. Matches dsColor's treatment.
  if (!score) return 'var(--fog-2)';
  if (score >= 88) return 'var(--emerald)';
  if (score >= 75) return 'var(--sky)';
  if (score >= 60) return 'var(--topaz)';
  return 'var(--coral)';
}

function oppScoreLabel(pos) {
  if (pos === 'WR' || pos === 'TE') return 'ALP';
  if (pos === 'RB') return 'WHS';
  return '';
}

const COMP=[];
// ── DYNASTY SCORE ─────────────────────────────────────────────────────────
// Pure asset score: age + trajectory + scarcity + contract + opportunity
// Independent of current QB/system situation — evaluates long-term dynasty value
const DS_AVG   = {QB:18.0,WR:12.0,RB:11.0,TE:10.0};
const DS_ELITE = {QB:23.0,WR:17.0,RB:15.0,TE:14.0};
const DS_SCAR  = {QB:1.35,TE:1.10,WR:1.00,RB:0.82};
const DS_TRANS = {QB:1.05,WR:1.15,RB:1.10,TE:1.05};
const DS_ROOKIE_CAP = 89;
// FORMAT-AWARE PRODUCTION BASELINES: a position's PPG scales with the scoring format
// (WR PPG ~+21% in Full PPR, TE PPG ~-40% in Standard), so the baseline production is
// graded against must scale the same way — otherwise changing format spuriously inflates
// or craters whole positions. Factors are data-derived (per-position PPG ratio vs the
// half_tep base, 2023-25) and anchored so half_tep = 1.00 (the default is unchanged).
// QB ~unaffected (no reception points). SCORING only; positional/roster scarcity is separate.
const DS_FMT_SCALE = {
  half_tep: {QB:1.00, RB:1.00, WR:1.00, TE:1.00},
  half:     {QB:1.00, RB:1.00, WR:1.00, TE:0.80},
  full_tep: {QB:1.00, RB:1.10, WR:1.21, TE:1.20},
  full:     {QB:1.00, RB:1.10, WR:1.21, TE:1.00},
  std:      {QB:1.00, RB:0.90, WR:0.79, TE:0.61},
};
// ── LEAGUE-SETTINGS SCARCITY ENGINE (replacement-level) ──────────────────────
// Player value = production ABOVE the best freely-available (replacement) player
// at his position. Replacement depth = teams × starters, so deeper leagues and
// superflex push the replacement line down the talent curve (worse replacement),
// raising scarcity. Curve SHAPES are fixed, documented assumptions from positional
// PPG-by-rank structure (2025): TE = steep cliff then flat plateau (weak size
// sensitivity); QB = long tail (strong sensitivity to SF + league size); WR deep;
// RB moderate. Output is a factor anchored to 1.00 at the representative default
// (12-team superflex), so the default config is UNCHANGED and the factor only
// modulates when a knob moves. Position-level (not per-player); judged by DIRECTION
// not precision. NOTE: market values from the source API are already SF-priced, so
// the QB factor <1 in 1-QB strips that baked-in premium back out — see audit notes.
let leagueTeams = 12;          // 8 / 10 / 12 / 14
let qbFmt = 'sf';              // 'sf' (superflex) | '1qb'
let MARKET_SETTINGS = null;    // {"T|Q": {name:{value,...}}} from market-values.json
let MARKET_DEFAULT = '12|sf';  // slice used as the model's 12-SF anchor

// ── Persist league/scoring settings across visits ──
try{
  const saved=JSON.parse(localStorage.getItem('delta_settings')||'{}');
  if([8,10,12,14].includes(saved.teams)) leagueTeams=saved.teams;
  if(['sf','1qb'].includes(saved.qb)) qbFmt=saved.qb;
  if(['std','half','half_tep','full','full_tep'].includes(saved.fmt)) scoringFmt=saved.fmt;
}catch(e){}
function saveLeaguePrefs(){
  try{ localStorage.setItem('delta_settings', JSON.stringify({teams:leagueTeams,qb:qbFmt,fmt:scoringFmt})); }catch(e){}
  try{ if(typeof DSYNC!=='undefined') DSYNC.noteSettings(); }catch(e){}
  // Multi-league: keep the ACTIVE league's stored format in step with the dropdowns,
  // so a hand change means "for this league" and survives a switch away and back.
  try{ if(typeof slpNoteSettings==='function') slpNoteSettings(); }catch(e){}
}
const SCAR_STARTERS = { QB:{ '1qb':1.0, 'sf':1.8 }, RB:2.4, WR:3.0, TE:1.1 };
// Positional value-by-rank curves.  v(r) = (PPG of the rank-r player) / (PPG of the rank-1 player).
// Used ONLY by scarcity() to rescale value between league formats. Never fed by market data.
//
// ALL FOUR derived 2026-07-12 by scripts/derive_scarcity_final.py — ONE documented method:
//   source    nflverse player stats, 2017-2025 (9 seasons)
//   scoring   half_tep, replicated exactly from gamefp() (4pt pass TD, 0.5 PPR, TE 1.0/rec)
//   rank by   PPG, among "real contributors" (QB >=100 att, RB >=50 touches, WR/TE >=25 tgt)
//   NO SMOOTHING — rank-smoothing averages each rank with its neighbours. At shallow breakpoints
//     the windows overlap so heavily that adjacent points share most of the same players and the
//     curve is flattened BY CONSTRUCTION (TE rank1 and rank3 windows overlap 67%: true TE3/TE1
//     is 0.807, smoothing reports 0.945). Noise is cut with MORE SEASONS instead.
//     NOTE: the prior RB curve matches a smoothed derivation almost exactly (smoothed RB6 = 0.842
//     vs committed 0.843), i.e. it carried that distortion. This replaces it.
//   stability Leave-one-season-out spread on every point <= ~0.03.
// Prior values kept inline for rollback.
const SCAR_CURVE = {
  QB: [[1,1.0],[6,0.815],[9,0.759],[12,0.717],[15,0.671],[18,0.642],[22,0.6],[26,0.562],[32,0.488]],  // was [6,0.865][9,0.796][12,0.769][15,0.731][18,0.721][22,0.647][26,0.608][32,0.471] (hand-tuned)
  RB: [[1,1.0],[6,0.721],[12,0.605],[19,0.536],[26,0.475],[34,0.405]],  // was [6,0.843][12,0.686][19,0.614][26,0.579][34,0.508] (2026-06-28, smoothed derivation)
  WR: [[1,1.0],[8,0.726],[16,0.649],[24,0.582],[36,0.506],[48,0.437]],  // was [8,0.705][16,0.588][24,0.537][36,0.473][48,0.362] (hand-tuned)
  TE: [[1,1.0],[3,0.835],[5,0.711],[8,0.628],[11,0.585],[14,0.54],[18,0.482]],  // was [3,0.788][5,0.667][8,0.605][11,0.582][14,0.563][18,0.507] (hand-tuned)
};
function scarCurveVal(pos,rank){
  const c=SCAR_CURVE[pos]; if(!c) return 0.6;
  if(rank<=c[0][0]) return c[0][1];
  for(let i=0;i<c.length-1;i++){
    if(rank<=c[i+1][0]){ const r0=c[i][0],v0=c[i][1],r1=c[i+1][0],v1=c[i+1][1]; return v0+(rank-r0)/(r1-r0)*(v1-v0); }
  }
  return c[c.length-1][1];
}
function scarcity(pos,teams,qb){
  const stOf=(p,f)=> p==='QB' ? SCAR_STARTERS.QB[f] : SCAR_STARTERS[p];
  const gap =1-scarCurveVal(pos,(teams||12)*stOf(pos,qb||'sf'));
  const gapD=1-scarCurveVal(pos,12*stOf(pos,'sf'));   // default: 12-team superflex
  return gapD>0 ? gap/gapD : 1;
}

// ============================================================
// DYNASTY SCORE — season-stable, historical-fact-only composite
// Four axes from the data pipeline (never projections):
//   Age (25) + Production (32) + Opportunity (33) + Contract (10)
// Updates on a season cadence; does NOT react to small in-season samples.
// Reflects what a player HAS demonstrated, not what their situation implies.
// ============================================================
function dsAge(age, pos) {
  // Positional value curve — calibrated to a 2-3 YEAR dynasty window (the
  // horizon most managers actually operate on, and roughly where the market
  // prices). Smooth one-step-per-year decline rather than cliffs: a player is
  // penalized in proportion to how much of the next ~3 productive years they're
  // likely to retain, NOT their theoretical decline to retirement. Onset of
  // decline is position-specific (RB earliest ~26, WR ~28, TE ~29, QB latest
  // ~33). Max 25 pts.
  const curves = {
    QB:[[21,32,25],[33,33,23],[34,34,20],[35,35,16],[36,36,12],[37,37,8],[38,38,5],[39,99,3]],
    WR:[[20,26,25],[27,27,23],[28,28,21],[29,29,18],[30,30,14],[31,31,10],[32,32,7],[33,33,5],[34,99,3]],
    RB:[[20,25,25],[26,26,23],[27,27,21],[28,28,18],[29,29,15],[30,30,11],[31,31,8],[32,32,6],[33,33,4],[34,99,2]],
    TE:[[20,27,25],[28,28,23],[29,29,20],[30,30,17],[31,31,13],[32,32,10],[33,33,7],[34,34,4],[35,99,3]],
  };
  const curve = curves[pos] || curves.WR;
  // Value at an INTEGER age from the bucket table (young→max, old→last segment).
  const valAt = (x) => {
    if (x <= curve[0][0]) return curve[0][2];
    for (const [lo,hi,pts] of curve) if (x>=lo && x<=hi) return pts;
    return curve[curve.length-1][2];
  };
  // Interpolate LINEARLY between integer breakpoints so 27.9 no longer equals
  // 27.0 and then cliffs at 28. At whole ages this returns exactly the old
  // bucket value (frac=0), so integer-age scores are unchanged; only the
  // in-between months move, gliding smoothly across each year boundary.
  const a = Math.floor(age);
  const frac = age - a;
  const lo = valAt(a), hi = valAt(a+1);
  return lo + (hi - lo) * frac;
}

function dsProduction(ppg25, ppg24, ppg23, g25, pos, p, neutral) {
  // Production QUALITY relative to positional baseline, recency-weighted. Max 32 pts.
  //
  // `neutral` — omit LEAGUE scarcity from the calculation (the positional DS_SCAR
  // constant still applies). calcDynastyScore passes true and re-applies scarcity
  // AFTER the 45-point clip; see the note there for why. Callers that want the
  // historical behaviour just omit the argument.
  const _fmtScale = (DS_FMT_SCALE[typeof scoringFmt!=='undefined'?scoringFmt:'half_tep'] || DS_FMT_SCALE.half_tep)[pos] || 1;
  const avg = (DS_AVG[pos]||12) * _fmtScale, elite = (DS_ELITE[pos]||14) * _fmtScale;
  // The bar above is in the league's format, so every PPG graded against it must be too.
  // PPGs recomputed from real stats already are (the loader stores ppgH25/24/23 beside
  // them). A value with no ppgH is a draft-slot baseline or a stored number, which is in
  // half PPR + TE premium — convert it with the same per-position factor (27 Sep 2026).
  // Before this, draft-slot rookies moved uniformly with the format whatever their role:
  // every one down in full PPR (Love 83 -> 76), up in standard (Sadiq 68 -> 83).
  if (p && _fmtScale !== 1) {
    const inFmt = (v, k) => (v > 0 && p['ppgH' + k] == null) ? v * _fmtScale : v;
    ppg25 = inFmt(ppg25, '25'); ppg24 = inFmt(ppg24, '24'); ppg23 = inFmt(ppg23, '23');
  }
  const trans = DS_TRANS[pos]||1.15;
  const scarMult = (DS_SCAR[pos]||1.0) * (neutral ? 1 : scarcity(pos, leagueTeams, qbFmt));

  // No NFL data (rookie) — placeholder scales with draft capital (premium picks get benefit of doubt)
  if (ppg25===0 && ppg24===0 && ppg23===0) return p ? dsRookieProd(p) : 12;

  // Recency-weighted production: most recent completed season weighted most heavily.
  // FULL-SEASON THRESHOLD = 12 games. A player who appeared in <12 of 17 games
  // missed roughly a third+ of the year — an injury-disrupted sample whose lower
  // per-game average partly reflects playing hurt. Weighting that partial year at
  // full recency (60%) wrongly buries proven stars off one injury season (Burrow
  // at 8g, Mike Evans at 8g were landing just over the old 8-game line). For
  // 8-11 games we lean on the prior FULL season instead; <8 is too thin to trust.
  let weighted, wSum;
  if (g25 >= 12) {
    weighted = (ppg25||0)*0.60 + (ppg24||0)*0.30 + (ppg23||0)*0.10;
    wSum = 0.60 + (ppg24>0?0.30:0) + (ppg23>0?0.10:0);
  } else if (g25 === 0 && ppg25 === 0 && ppg24 > 0) {
    // AVAILABILITY PENALTY — missed the ENTIRE most recent season. Unlike the
    // partial-injury branch below, we do NOT erase the missed year from the
    // average: it counts as a real ZERO holding ~40% weight. Being available is
    // itself part of a dynasty asset's value, and a player who produced nothing
    // for a full season (major injury, role loss, or no team) should be dinged
    // for it — many never return to form. The prior body of work still carries
    // the majority weight, so a proven player isn't zeroed out, just honestly
    // discounted (Tank Dell, Joe Mixon, Aiyuk, Watson). If the market believes
    // in the bounce-back, that shows up as a buy in the DELTA-vs-market gap, not
    // by the Score pretending the missed season never happened.
    weighted = 0*0.40 + (ppg24||0)*0.42 + (ppg23||0)*0.18;
    wSum = 0.40 + 0.42 + (ppg23>0?0.18:0);
  } else if (ppg24 > 0) {
    // Injured/partial recent season (1-11 games) — lean on prior full season
    weighted = (ppg24||0)*0.65 + (ppg23||0)*0.25 + (ppg25||0)*0.10;
    wSum = 0.65 + (ppg23>0?0.25:0) + (ppg25>0?0.10:0);
  } else {
    weighted = ppg25 || 0;
    wSum = 1;
  }
  const prod = wSum > 0 ? weighted / wSum : 0;

  // avg → ~18pts, elite → ~28pts, transcendent → 32pts
  let raw = (prod / avg) * 18 * scarMult;
  const best = Math.max(ppg25, ppg24, ppg23);
  if (best >= elite * trans) raw += 4;       // transcendent ceiling bonus
  else if (best >= elite) raw += 2;          // elite ceiling bonus

  return Math.round(Math.min(32, Math.max(2, raw)));
}

// Draft capital → "organizational investment" signal, decaying by NFL experience.
// Rookies: capital is the primary opportunity signal (no usage history yet).
// Yr1-2: blends with demonstrated usage. Yr3+: drops out, pure demonstrated value.
function dsCapitalScore(overallPick) {
  if (overallPick == null) return 0.30; // unknown draft slot — neutral-low
  if (overallPick <= 5)   return 1.00;
  if (overallPick <= 15)  return 0.88;
  if (overallPick <= 32)  return 0.75;
  if (overallPick <= 64)  return 0.55;
  if (overallPick <= 100) return 0.40;
  if (overallPick <= 140) return 0.28;
  if (overallPick <= 180) return 0.18;
  if (overallPick <= 260) return 0.10;
  return 0.05;
}

function dsExpWeight(draftYear) {
  // Years of NFL experience entering 2026 season. Capital influence decays as evidence accrues.
  if (draftYear == null) return 0;
  const yrs = SEASON_YEAR - draftYear;
  if (yrs <= 0) return 1.00;  // incoming rookie
  if (yrs === 1) return 0.55; // after rookie season
  if (yrs === 2) return 0.30; // after 2 seasons
  return 0.0;                 // 3+ seasons — demonstrated usage only
}

function dsDraftInfo(name) {
  let d = null;
  try { d = (typeof DRAFT_PICKS !== 'undefined') ? DRAFT_PICKS[name] : null; } catch(e) {}
  if (d) return { pick: d.p ?? null, year: d.y ?? null };
  // Fallback to current prospect class (2026) — draft capital maintained there.
  // try/catch guards the temporal-dead-zone case on first COMP build (PROSPECTS_2026
  // is declared later in the file; it's available by the post-load rebuild).
  try {
    const pr = PROSPECTS_2026.find(x => x.n === name);
    if (pr && pr.ovr != null) return { pick: pr.ovr, year: 2026 };
  } catch(e) {}
  return { pick: null, year: null };
}

function dsOpportunity(p) {
  // Opportunity = DEMONSTRATED usage from the most recent completed season, Max 33 pts.
  // For players with <=2 yrs experience, draft capital (organizational investment) blends in
  // and decays to zero by year 3 — by then demonstrated usage is the whole story.
  const pos = p.pos||p.p||'WR';
  const isRookie = p.g25===0 && p.ppg25>0;
  const noData = p.ppg25===0 && p.ppg24===0 && p.ppg23===0;
  const noNFL = p.g25===0;
  const { pick, year } = dsDraftInfo(p.n);
  const expW = dsExpWeight(year != null && p._rollover ? year - 1 : year);   // a year more experience at the roll
  // Draft-capital opportunity is CAPPED BELOW what a proven starter can earn (max 19 of 33).
  // PHILOSOPHY: pedigree earns a strong opportunity FLOOR, but the full max is reserved for
  // players who've DEMONSTRATED elite usage. Unproven potential < proven production.
  // (MHJ — elite capital, weak film — must be separable from a pure-capital rookie.)
  //
  // The span was 23 (max 26), which was described as "capped below the proven-elite
  // ceiling" — true only against an elite RUSHING QB (18+13=31). A proven POCKET
  // passer maxes at 18+3=21, so a top-pick rookie who had never taken an NFL snap
  // outscored every proven pocket passer alive on the opportunity axis. Fernando
  // Mendoza (0 games) sat above Joe Burrow on this axis alone.
  // Span 16 puts the rookie ceiling at 19 — deliberately BELOW the 21 pocket-passer
  // floor, because rookies start slower and earn opportunity as they go. Costs
  // proven players nothing: capital only blends in during a player's first two years.
  const capitalOpp = 3 + dsCapitalScore(pick) * 16; // map capital → 3-19 (capped)

  // Base demonstrated opportunity
  let baseOpp;
  if (pos === 'QB') {
    const s25 = PLAYER_STATS[p.n]?.['2025'];
    const rushAtt = s25?.rush_att || 0;
    const rushG = s25?.games || 0;
    // Rushing opportunity bonus keyed to rush attempts PER GAME, not season total.
    // Total-attempts over-credited mere scramblers: Dak (53) and Baker (55) cleared
    // the old 50-att line and got the same bonus as genuine rushing QBs, despite
    // running ~3/g vs 7-8/g for Allen/Daniels. Per-game rate isolates "running is
    // part of his game" from "ran a few bootlegs." Tiers: 7+/g elite dual-threat
    // (Allen, Daniels), 5-7/g real rushing QB (Hurts, Maye, Dart, Lamar, Herbert),
    // 4-5/g moderate mobility (Mahomes, Caleb), <4/g pocket passer/scrambler (no
    // bonus beyond the base — their rushing is incidental and already in their PPG).
    const rushPG = p._qbRushPG != null ? p._qbRushPG : (rushG > 0 ? rushAtt / rushG : 0);
    const rushPts = rushPG >= 7 ? 13 : rushPG >= 5 ? 9 : rushPG >= 4 ? 6 : 3;
    // QB ROLE FLAG (pipeline-emitted, conservative): the flat 18 baseline treats
    // every QB with NFL data as a starter — backups (Fields-behind-Mahomes) were
    // scoring 60s-70s. A flagged backup's seat drops to 9 (floor, not cliff:
    // contingent SF value and rushing spike-weeks are real). Flags exist only
    // when an UNAMBIGUOUS established incumbent sits ahead (depth chart when
    // published, 2025 incumbency otherwise) — ascending QBs (Dart), injured
    // starters (Love), and open competitions are never flagged. QB-only by
    // design: depth ranks are never read for other positions, where snap and
    // target share already measure opportunity. Absent qb_roles data, behavior
    // is unchanged.
    const seat = (QB_ROLES_SCORE[p.n] && QB_ROLES_SCORE[p.n].role === 'backup') ? 9 : 18;
    baseOpp = (noData && !noNFL) ? 13 : ((noNFL ? 14 : seat) + rushPts);
  } else {
    const oppSc = p._opp26 != null ? p._opp26 : getOppScore(p.n, pos);
    baseOpp = (oppSc == null) ? (noNFL ? 14 : 13) : (((oppSc - 30) / 69) * 29 + 4);
  }

  // Blend demonstrated usage with draft-capital signal, weighted by experience
  const blended = expW > 0 ? baseOpp * (1 - expW) + capitalOpp * expW : baseOpp;
  return Math.round(Math.min(33, Math.max(3, blended)));
}

function dsRookieProd(p) {
  // Rookie production placeholder scales with draft capital — premium picks get
  // benefit of the doubt on future production; low-capital fliers do not. Max ~18.
  const { pick } = dsDraftInfo(p.n);
  return Math.round(4 + dsCapitalScore(pick) * 14);
}

function dsCont(p) {
  // Contract / role security from the live nflverse/OTC feed. Max 10 pts.
  // PHILOSOPHY: security is a bonus to be EARNED, not something whose absence is punished.
  // An expiring deal is NEUTRAL (no security bonus), not a red flag — a young elite player
  // awaiting his extension shouldn't be cratered for a fact that isn't a negative.
  // Genuine "old + expiring" risk is handled by the AGE axis, not double-penalized here.
  // Band: 5 (neutral/expiring) → 10 (long-term security). No sub-5 penalties.
  // Threshold: 4+ years = 10/10 — skill-position NFL contracts rarely exceed 4 years,
  // so a 4yr deal genuinely IS maximum security and fully covers DELTA's 2-3yr window.
  const c = CONTRACTS.find(x => x.n===p.n);
  if (!c || !c.end) return 5; // unknown — neutral
  // Base 2025 (last completed season) so yrs counts remaining seasons
  // including the current 2026 season. Thresholds shifted +1 vs old base 2026
  // so all contract scores remain identical — only display changes.
  const yrs = c.end - (SEASON_YEAR - 1) - (p._rollover ? 1 : 0);   // one season fewer at the roll
  return yrs>=5?10:yrs===4?9:yrs===3?7:yrs===2?6:5;
}

// Youth production multiplier — boost only, no penalty for veterans.
// Principle: the same production level achieved at 22 is a stronger forward dynasty
// signal than at 30. A young player clearing elite production thresholds early has
// already beaten the development curve; a veteran doing the same is at his ceiling.
// Multiplier amplifies early production; 28+ gets full credit with no discount.
function dsYouthMult(age) {
  if (age <= 24) return 1.25;
  if (age <= 26) return 1.12;
  if (age <= 28) return 1.04;
  return 1.00;   // 28+ gets full credit, no penalty
}

/* CONFIRMED SEASON-ENDER: THE MISSED SEASON COUNTS NOW (owner, 8 Oct 2026).
   The DELTA Score still never moves on weekly stats. It moves on one verified event:
   a player on data/injury-overrides.json (INJ_OUT) will have this season recorded as
   a full zero, and the offseason roll would apply dsProduction's existing missed-season
   rule (zero at 40% weight) then. This applies that same rule now: seasons shift one
   year with the current season as zero games. PRODUCTION ONLY, deliberately — the
   opportunity axis, age and contract are untouched (the roll's opportunity behaviour
   for a missed season is an open question, backlog). Only players with games in the
   last completed season: someone who already missed it (Polk) has the rule applied
   already, and a rookie with no NFL games stays on the rookie path, as at the roll.
   Measured 8 Oct at 12-team SF: Pearsall 55 -> 48, Higgins 52 -> 44; nobody else. */
function dsProductionNow(p, pos) {
  // The end-of-season projection (dsEndOfSeason) has already rolled the seasons forward,
  // so the season-ender shift below must not be applied a second time.
  if (p._rollover) return dsProduction(p.ppg25||0, p.ppg24||0, p.ppg23||0, p.g25||0, pos, p, true);
  const out = (typeof INJ_OUT !== 'undefined' && INJ_OUT && INJ_OUT[p.n]) && (p.g25 || 0) > 0;
  if (!out) return dsProduction(p.ppg25||0, p.ppg24||0, p.ppg23||0, p.g25||0, pos, p, true);
  const q = Object.assign({}, p, { ppgH25: undefined, ppgH24: p.ppgH25, ppgH23: p.ppgH24 });
  return dsProduction(0, p.ppg25||0, p.ppg24||0, 0, pos, q, true);
}

function calcDynastyScore(p) {
  const pos = p.pos||p.p||'WR';
  /* READS AS "ROOKIE", MEANS "NO 2025 GAMES" — the two are not the same, and this
     catches veterans who missed the whole season. Measured at the 12sf anchor on
     16 Aug 2026: 11 players have g25===0 with prior NFL production (Joe Mixon,
     Brandon Aiyuk, Deshaun Watson, Tank Dell, Will Levis and 6 others). Not one is
     within 38 points of the 89 cap — the highest scores 51 — so the cap binds on
     nobody today and no score in the ledger is affected by this.
     Left alone on purpose. Tightening it to "no NFL experience" is a change to the
     rookie gate, and g25===0 is load-bearing in eight other places in this file with
     four different companion conditions (ppg25>0 for a seeded rookie, ppg25===0 for
     no-data, and so on). That untangling is an offseason job, not a pre-freeze one.
     It cannot bite before the ledger resolves: the 2026 baseline locks on 6 Sep, so
     the season a player would have to miss for this to matter has not started. */
  const noNFL = p.g25===0;
  const age = p.a || 22;
  const scar = scarcity(pos, leagueTeams, qbFmt) || 1;
  const a    = dsAge(age, pos);                                                       // raw max 25
  const prod = dsProductionNow(p, pos);                                               // league-NEUTRAL, raw max 32
  const opp  = dsOpportunity(p);                                                     // raw max 33
  const c    = dsCont(p);                                                            // max 10

  // Axis weights: 15 / 45 / 30 / 10 — shifts emphasis from age and opportunity
  // toward demonstrated production, aligning with the 2-3 year dynasty window.
  // Production scaled with youth multiplier (boost-only): early elite production
  // predicts the next 2-3 seasons more reliably than the same output at 30+.
  const mult  = dsYouthMult(age);
  const aW    = (a / 25)  * 15;

  /* LEAGUE SCARCITY IS APPLIED AFTER THE CLIP — ORDER IS LOAD-BEARING.
     Scarcity used to be multiplied in INSIDE dsProduction, so it was clipped twice
     (at 32 there, at 45 here, the second time after the youth multiplier). For any
     player whose contribution exceeded the ceiling the entire league adjustment was
     discarded. Measured on live data: Brock Bowers scored 85 in 8-team 1QB AND 85
     in 14-team superflex — identical — while unclipped players at his own position
     moved 7-8 points. 33 players were completely league-insensitive, including all
     13 rookies (dsRookieProd never saw scarcity at all).
     Clipping on a league-neutral basis and applying scarcity afterwards means the
     adjustment can never be thrown away. scarcity(pos,12,'sf') === 1.000 exactly,
     so every 12-team-superflex score — the freeze anchor — is unchanged.
     The multipliers themselves are externally validated: 29 of 32 agree with the
     FantasyCalc VOR market factor within 0.06 (data/scarcity-validation.json). */
  const prodW = Math.min(45, (prod / 32) * 45 * mult) * scar;
  const oppW  = (opp / 33) * 30;

  // RB OPPORTUNITY DOWNWEIGHT (backtest-diagnosed): usage/Workhorse axis overlaps
  // production heavily for RBs. Keep 65% of opp axis and reallocate freed weight into
  // production. Scale preserved: RB max = 15 + 45*1.233 + 30*0.65 + 10 = 100.
  let total;
  if (pos === 'RB') {
    total = Math.min(100, aW + prodW * 1.233 + oppW * 0.65 + c);
  } else {
    total = Math.min(100, aW + prodW + oppW + c);
  }
  if (noNFL) total = Math.min(DS_ROOKIE_CAP, total);
  return Math.round(total);
}

/* ── END-OF-SEASON SCORE — DISPLAY ONLY (owner, 12 Oct 2026) ─────────────────
   What his DELTA Score would be at the offseason roll if this season's pace holds.
   The live Score does not move in-season (owner, 9 Oct); this is the projection card
   on the player page ("End Of 2026"), and NOTHING scored reads it: not rankings,
   calls, model value, the scorecard or the freeze.
   Built by running the real calcDynastyScore on rolled-forward inputs:
     production  this season = (games played x PPG so far + games left x his projection)
                 / all games; last season and the one before shift back one slot
     games       played + left on his schedule (0 left once he is on the season-ender list)
     opportunity this season's usage (the Alpha / Workhorse number the card shows) once he
                 has 3+ games; a QB's rushing attempts per game from this season the same way
     contract    one season fewer; experience one season more; age +1
   All PPGs are in the league's own format (marked with ppgH so dsProduction does not
   convert them again). Returns null until the game logs are loaded. */
function dsEndOfSeason(p){
  if (!p || typeof GAMELOGS === 'undefined' || !GAMELOGS) return null;
  const pos = p.pos || p.p || 'WR';
  let G = 0, pts = 0, left = 0, car = 0;
  for (const r of (GAMELOGS[p.n] || [])) {
    if (r.s !== SEASON_YEAR) continue;
    if (r.up) { left++; continue; }
    if (r.dnp) continue;
    G++; pts += gamefp(r, pos, scoringFmt); car += (+r.car || 0);
  }
  /* A confirmed season-ender is recorded at the roll as a FULL ZERO season (the rule
     dsProductionNow already applies today), not as a short season: a 3-game year would
     otherwise be down-weighted as "injury-disrupted" and his Score would jump (Achane
     74 -> 86 in the first build). His opportunity stays on last season's usage, as the
     live Score does (what the roll does to a missed season's opportunity is backlog R9). */
  const out = !!(p.outForSeason || (typeof INJ_OUT !== 'undefined' && INJ_OUT && INJ_OUT[p.n]));
  if (out) { G = 0; pts = 0; left = 0; }
  const rest = (typeof getAdjProj === 'function') ? getAdjProj(p) : (p.proj || 0);
  const games = G + left;
  const ppg = games ? (pts + left * rest) / games : 0;
  let opp26 = null, rushPG = null, oppGames = 0;
  if (out) { /* last season's usage */ }
  else if (pos === 'QB') { if (G >= 3) { rushPG = car / G; oppGames = G; } }
  else if (typeof opportunitySoFar === 'function') {
    const o = opportunitySoFar(p.n, pos);
    if (o && o.g >= 3) { opp26 = o.sc; oppGames = o.g; }
  }
  const q = Object.assign({}, p, {
    a: (p.a || 22) + 1,
    ppg25: ppg, ppgH25: ppg,
    ppg24: p.ppg25 || 0, ppgH24: p.ppgH25,
    ppg23: p.ppg24 || 0, ppgH23: p.ppgH24,
    g25: games, _rollover: true, _opp26: opp26, _qbRushPG: rushPG
  });
  return { score: calcDynastyScore(q), played: G, left: left, ppg: ppg, oppGames: oppGames, out: out,
           oppFrom: (opp26 != null || rushPG != null) ? SEASON_YEAR : SEASON_YEAR - 1 };
}

/* DELTA Score ring (25 Oct 2026, owner; legal compliance plan step 6). Stands where the NFL.com
   headshot used to be: those photos are NFL.com's, licensed for personal, non-commercial use only,
   so DELTA no longer shows them. The ring fills to the Score and takes its colour from dsColor()
   (the owner chose the Score colours over plain teal). It is sized by font-size: `size` px, or let
   the page's CSS set font-size on .dl-ring. The number carries class dl-ring-n for count-ups. */
function dlScoreRing(p, size){
  const s = (p && p.dsScore != null) ? Math.round(p.dsScore) : null;
  const f = s == null ? 0 : Math.max(0, Math.min(100, s)) / 100, C = 2 * Math.PI * 30;
  return '<span class="dl-ring" role="img" aria-label="DELTA Score '+(s == null ? 'not available' : s)+'"'
    + ' style="position:relative;display:inline-block;flex-shrink:0;width:1em;height:1em;line-height:1'+(size ? ';font-size:'+size+'px' : '')+'">'
    + '<svg viewBox="0 0 68 68" width="100%" height="100%" aria-hidden="true" style="position:absolute;inset:0;display:block">'
    + '<circle cx="34" cy="34" r="30" fill="var(--ink-2)" stroke="var(--line)" stroke-width="4"/>'
    + (f ? '<circle cx="34" cy="34" r="30" fill="none" stroke="'+dsColor(s)+'" stroke-width="4" stroke-linecap="round"'
         + ' stroke-dasharray="'+(C*f).toFixed(1)+' '+C.toFixed(1)+'" transform="rotate(-90 34 34)"/>' : '')
    + '</svg><span style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center">'
    + '<b class="dl-ring-n" style="font-family:var(--mono);font-size:.32em;font-weight:700;color:var(--paper)">'+(s == null ? '\u2014' : s)+'</b>'
    + '<small style="font-family:var(--sans,system-ui);font-size:.11em;font-weight:800;letter-spacing:.14em;color:var(--fog);margin-top:.05em">DELTA</small>'
    + '</span></span>';
}

function dsColor(score) {
  // Matches platform color language (oppScoreColor thresholds)
  // Tokens, not hex: every value below is the exact same colour it was, but
  // resolving through :root is what lets a palette fix or an accent theme
  // reach the twelve places this result is dropped into a style attribute.
  if (!score) return 'var(--fog-2)';
  if (score >= 85) return 'var(--emerald)'; // elite
  if (score >= 72) return 'var(--sky)';     // strong
  if (score >= 55) return 'var(--topaz)';   // average
  return 'var(--coral)';                    // weak
}

RAW.forEach(r=>COMP.push(calcProj(r)));
const ASSETS=[...COMP,...PICKS.filter(p=>!p.hidden)];
function tH(t){return t==='up'?'<span style="color:var(--emerald)">▲</span>':t==='down'?'<span style="color:var(--coral)">▼</span>':'<span style="color:var(--fog-2)">—</span>';}
/* Visible marker so a zeroed projection reads as a known absence rather than
   stale data — which was the reason for surfacing this at all. */
function injBadge(n){
  if(INJ_OUT[n]){
    const note=INJ_OUT[n].note?' — '+String(INJ_OUT[n].note).replace(/"/g,'&quot;'):'';
    return '<span class="badge bd" style="margin-right:3px;font-size:9px" title="Out for the season'+note+'">OUT</span>';
  }
  const rec=INJ_STATUS[n];
  const st=rec && rec.status;
  if(!st) return '';
  const lbl=String(st).toUpperCase();

  /* ROSTER DESIGNATIONS ONLY.
     The test a tag has to pass is whether it matches DELTA's time horizon and
     explains itself without a click.

       IR / PUP / NFI / SUS  — multi-week minimums, structural, self-explanatory.
                               The label IS the explanation, so the tag does not
                               invite a question DELTA cannot answer.

       Questionable / Doubtful / Out — DELIBERATELY NOT SHOWN. These describe a
                               single Sunday, churn daily off practice reports,
                               and most Questionable players suit up. At a 2-3
                               year dynasty horizon they are noise, and DELTA is
                               not a news product — Sleeper and the beat writers
                               own that clock and always will. A "Q" that makes
                               someone click through to nothing is worse than no
                               tag at all.

     Season-ending calls still come from data/injury-overrides.json, handled
     above, and carry their own note in the tooltip.

       DNR — reserve/did-not-report or left-squad. Added because it passes the
             same test: structural, open-ended, and a longer-horizon fact than
             any weekly injury tag. The player is not with the team at all.
             Its absence was actively misleading — a player off the roster
             entirely rendered as perfectly healthy. Coral, not amber: this is
             a harder state than "currently unavailable". */
  if(lbl==='DNR')
    return '<span class="badge bd" style="margin-right:3px;font-size:9px" title="Sleeper status: DNR — reserve/did not report. Not with the team.">DNR</span>';
  /* NA — not on the active roster. Exempt list, non-football absence, or a
     designation with no return date. Same test as DNR: structural, open-ended,
     and a longer-horizon fact than any weekly tag. Its absence was the live
     Pearsall failure shape — Josh Jacobs sat on the Commissioner's Exempt List
     through Week 1 rendering as a perfectly healthy RB1 with no tag at all.
     Labelled INACTIVE, not "NA", because the label has to explain itself
     without a click and two letters do not.
     Note the tooltip never names a body part. Sleeper carries one for these
     players and it is often stale — Jacobs reads "Groin" from a camp injury
     that has nothing to do with why he is unavailable. injBadge has never read
     body_part and must not start. */
  if(lbl==='NA')
    return '<span class="badge bd" style="margin-right:3px;font-size:9px" title="Sleeper status: NA — not on the active roster. Not necessarily an injury, and not necessarily out for the season.">INACTIVE</span>';
  if(lbl==='IR'||lbl==='PUP'||lbl==='NFI'||lbl==='SUS')
    return '<span class="badge bw" style="margin-right:3px;font-size:9px" title="Sleeper status: '+lbl+' — currently unavailable. Not necessarily out for the season.">'+lbl+'</span>';
  return '';
}
function sTag(s){const c=s>=70?'bs':s>=55?'bi':s>=40?'bw':'bd';return`<span class="badge ${c}">${s}</span>`;}
function eTag(sc,fl,fr){
  if(sc===1.0&&!fl)return'<span class="badge bn">—</span>';
  const c=sc>=1.15?'bs':sc>=1.05?'bi':sc>=0.95?'bn':sc>=0.90?'bw':'bd';
  const lbl=fr==='vol+YAC neutral'?'neutral ⌊':fl?'floor ⌊':sc>=1.15?'elite':sc>=1.05?'above avg':sc>=0.95?'avg':'below avg';
  return`<span class="badge ${c}">${lbl}</span>`;
}
function rTag(mult,lbl,pos){
  if(!lbl||lbl==='—'||lbl==='-')return'<span class="badge bn">—</span>';
  const c=mult>=1.10?'bs':mult>=1.02?'bi':mult>=0.94?'bn':mult>=0.85?'bw':'bd';
  const indicator=pos==='RB'?'⬛':'◆';
  return`<span class="badge ${c}" title="${lbl}">${indicator} ${lbl}</span>`;
}
function mvAssetBase(p){
  // Verdict model is computed at the 12-SF anchor basis (0.5PPR+TEP, 12-team Superflex):
  // scoring pinned so badges don't flip on format change, AND league size + QB format pinned
  // so the buy/sell tag is a pure per-player signal (Allen vs Penix) rather than a position-wide
  // scarcity shift. With scarcity(pos,12,sf)=1.0 the format scaling cancels against the anchor.
  const savedFmt=scoringFmt, savedTeams=leagueTeams, savedQb=qbFmt;
  scoringFmt='half_tep'; leagueTeams=12; qbFmt='sf';
  const mv=mvAsset(p);
  scoringFmt=savedFmt; leagueTeams=savedTeams; qbFmt=savedQb;
  return mv;
}

// vTag thresholds are absolute again: mvAssetBase() now returns the
// market-calibrated model value (see MV_CENTER above), so the population
// centers on 1.0 by construction and buy/sell reads directly off the ratio.
// Tags remain league-invariant and identical to the band-scaled scheme.
// The ratio every buy/sell call is read from: model value over market, both at the 12-SF
// anchor. Shared with The Read's gap line (3 Oct 2026) — that line used the reader's own
// league basis while the tag used this one, and in PPR formats 19 players showed a Sell
// beside a model value ABOVE market. One function, one basis, no disagreement.
function verdictRatio(p){
  // Denominator is the market at the SAME 12-SF anchor basis the model uses (a manual ktc
  // override wins, since it's the user's stated market value). Format scaling cancels → per-player gap.
  const mkt12=(OV[p.n]&&OV[p.n].ktc!=null)?OV[p.n].ktc:p.k;
  return mvAssetBase(p)/Math.max(mkt12,1);
}
/* Rookie Hold (10 Oct 2026, owner). A player with no NFL season on record (in practice the
   2026 rookies, a few undrafted players and three 2025 picks who never played) has no DELTA
   view: his model value is market x age curve. Ungated, that ratio would read 0 buys,
   41 holds and 37 sells, correlated 0.74 with age -- an artefact, not a judgement. What the
   evidence DOES support is the market's price: seven pre-registered rookie studies found the
   market prices draft slot, early production and the second-year dip about right. So the
   call is Hold, marked as a rookie hold (.bnr) so it never reads as an individual verdict.
   It becomes a normal call once he has a season on record. Same gate as before, so model
   value, centering (line ~3519) and every score are untouched. */
function dlRookieHold(p){ return ((p.g25||0)+(p.g24||0)+(p.g23||0))===0; }
/* Price floor for calls (owner, 22 Oct 2026). A player ranked below 300th by market value at
   the call's own 12-team superflex anchor (p.k) shows a plain Hold: no mark, no copy (owner).
   Down there a player is worth ~250 or less against ~10,000 for a star, nobody trades for him,
   and a few points either way flipped the call (Pickett went sell->buy on 108->122). Measured
   22 Oct: 54 of the 86 players ranked 301+ carried a Buy or Sell. Ranked on the anchor, like
   the call itself, so it does not change with the reader's league settings. Display only:
   model value, the gap and every score are untouched. Flicker at the call lines is accepted
   (owner: "that's the market"). */
const DL_CALL_RANK_FLOOR=300;
let _dlFloorCache={first:null,len:0,cut:null};
function dlCallFloorValue(){
  if(typeof COMP==='undefined'||!COMP||!COMP.length) return null;
  if(_dlFloorCache.first===COMP[0]&&_dlFloorCache.len===COMP.length) return _dlFloorCache.cut;   // COMP is rebuilt with new objects
  const ks=COMP.map(x=>x.k||0).sort((a,b)=>b-a);
  const cut=ks.length>DL_CALL_RANK_FLOOR?ks[DL_CALL_RANK_FLOOR-1]:null;   // the 300th price
  _dlFloorCache={first:COMP[0],len:COMP.length,cut:cut};
  return cut;
}
function dlBelowCallFloor(p){ const cut=dlCallFloorValue(); return cut!=null&&(p.k||0)<cut; }
const DL_ROOKIE_HOLD_TIP='No NFL season on record yet. In every test DELTA has run, the market has priced players like this about right, so DELTA holds until he has a full season on record.';
function vTag(p){
  if(dlRookieHold(p)) return'<span class="badge bn bnr" title="'+DL_ROOKIE_HOLD_TIP+'">hold</span>';
  if(dlBelowCallFloor(p)) return'<span class="badge bn">hold</span>';   // price floor (see DL_CALL_RANK_FLOOR)
  const r=verdictRatio(p);
  // ── One ladder for every position (Aug 2026) ──
  // A "strong" tag is a declarative call urging the user to act, so it has to be
  // rare and has to demand a big gap. 25% is that gap, and it means the same
  // thing at every position — so TE no longer gets its own lower ladder. The old
  // TE bars (1.10/1.00/0.88/0.76) had no stated justification and, after the
  // symmetric centering fix, flagged 18 of 51 TEs as strong buys.
  // Both ends moved together so DELTA is no quicker to condemn than to endorse.
  // Accepted consequence: TEs run ~6% above market as a group, so the position
  // reads somewhat bullish (49% buy-or-better vs 34% elsewhere). That is a
  // centering question, not a band question, and is deliberately not patched here.
  const sb=1.25, b=1.06, h=0.94, s=0.75;
  // ── Thin-sample conviction dampener (Aug 2026 — counts CHANCES, not games) ──
  // DELTA only gets loud when the facts back it up, so a "strong" tag is capped
  // one level on a thin sample: strong buy → buy, strong sell → sell. The player
  // keeps a directional tag — he just can't carry max conviction yet.
  //
  // SUPERSEDES the June 2026 trigger of 12 CAREER GAMES, which was wrong in both
  // directions. It silenced Trey Lance (five seasons, eight games) — that is not
  // a thin sample, that is the answer — while doing nothing for actual rookies
  // who scraped past 12 games.
  //
  // The test is now whether the player has HAD the chance to build a record, not
  // whether he took it. A season is 17 games, so a first-year player cannot reach
  // 20 games however well he plays; he was never given the opportunity to clear
  // the bar. Someone several seasons in has had 34, 51, 85 chances — a low game
  // count there is a verdict, not a gap in the data. It also gives a second-year
  // player about three games of cushion before he can be tagged strongly.
  //
  // Chances = seasons since the draft x 17. Unknown draft year (mostly UDFAs)
  // falls through as experienced, i.e. NOT capped.
  //
  // Accepted gap: a rookie who lost year one to injury loses this cover early in
  // year two despite barely playing. Known season-enders carry a separate manual
  // injury flag. See /areas/delta.md.
  const THIN_CHANCES = 20;
  const GAMES_PER_SEASON = 17;
  const _di = (typeof dsDraftInfo === 'function') ? dsDraftInfo(p.n) : null;
  const _dy = (_di && _di.year != null) ? _di.year : null;
  const chances = (_dy != null)
    ? Math.max(0, (SEASON_YEAR - _dy)) * GAMES_PER_SEASON
    : Infinity;                      // no draft year on file → treat as experienced
  const thin = chances < THIN_CHANCES;
  if(r>=sb) return thin
    ? '<span class="badge bi" title="Strong signal capped — first NFL season (fewer than '+THIN_CHANCES+' games\' worth of chances)">buy</span>'
    : '<span class="badge bs">strong buy</span>';
  if(r>=b) return'<span class="badge bi">buy</span>';
  if(r>=h) return'<span class="badge bn">hold</span>';
  if(r>=s) return'<span class="badge bw">sell</span>';
  return thin
    ? '<span class="badge bw" title="Strong signal capped — first NFL season (fewer than '+THIN_CHANCES+' games\' worth of chances)">sell</span>'
    : '<span class="badge bd">strong sell</span>';
}

// ── FEATURE 5: Scoring Format Adjustment ─────────────────────
// Base format: 0.5 PPR + TE Premium (1.0 bonus for TEs)
// REC_PG stores receptions/game for 2025 season
// Delta vs base for each format:
//   standard:   -0.5×rec (all) and -1.0×rec (TE premium removal)
//   half:       -1.0×rec (TE only, removes premium, keeps 0.5 for others)
//   full_tep:   +0.5×rec (all, adds to existing 0.5)
//   full:        0 for WR/RB, -0.5×rec (TE, removes premium partially)
function getScoringDelta(name,pos,fmt){
  const r=REC_PG[name]||0;
  if(fmt==='half_tep') return 0; // current base
  if(fmt==='half')     return pos==='TE'?-r*0.5:0; // remove 0.5 TE premium
  if(fmt==='full_tep') return r*0.5; // add 0.5 to everyone
  if(fmt==='full')     return pos==='TE'?0:r*0.5; // WR/RB to full; TE base 1.0 already = full
  if(fmt==='std')      return -(r*0.5)+(pos==='TE'?-r*0.5:0); // remove all rec pts
  return 0;
}
function ensureFuturePicks(){
  if(typeof MARKET_SETTINGS==='undefined'||!MARKET_SETTINGS) return;
  const anchor=MARKET_SETTINGS['12|sf']||MARKET_SETTINGS[MARKET_DEFAULT];
  if(!anchor) return;
  const sel=MARKET_SETTINGS[leagueTeams+'|'+qbFmt]||anchor;
  let added=0;
  for(const name in anchor){
    if(!/^20\d\d (1st|2nd|3rd|4th)$/.test(name)) continue;
    if(name.indexOf('2026')===0) continue;
    let pk=PICKS.find(function(p){ return p.n===name; });
    if(!pk){ pk={n:name,k:anchor[name].value,ip:true,fp:true}; PICKS.push(pk); added++; }
    pk.k=anchor[name].value;
    pk.kMkt=(sel[name]&&sel[name].value>0)?sel[name].value:pk.k;
  }
  if(added) console.log('[DELTA] '+added+' generic future-pick assets added from market grid');
}

function applyMarketForSetting(){
  ensureFuturePicks();
  // Re-point each player's format-specific market (kMkt) to the selected
  // league/QB slice, then rebuild COMP so ktcEff/gap/verdict reflect it.
  // No-op for the legacy flat market file (kMkt already mirrors k).
  if(MARKET_SETTINGS){
    const key=leagueTeams+'|'+qbFmt;
    const slice=MARKET_SETTINGS[key]||MARKET_SETTINGS[MARKET_DEFAULT];
    if(slice){
      const nidx=fcNormIndex(slice);
      for(const player of RAW){
        if(!player||!player.n) continue;
        // direct → alias → NORMALIZED (punctuation/suffix-insensitive) → anchor
        let m=slice[player.n]
          || (typeof FC_ALIASES!=='undefined' && FC_ALIASES[player.n] && slice[FC_ALIASES[player.n]])
          || slice[nidx[fcNorm(player.n)]];
        player.kMkt = m ? m.value : player.k;   // unmatched → fall back to 12-SF anchor
      }
    }
  }
  if(typeof COMP!=='undefined' && typeof calcProj==='function'){
    COMP.length=0; RAW.forEach(r=>COMP.push(calcProj(r)));
    if(typeof ASSETS!=='undefined'){ ASSETS.length=0; ASSETS.push(...COMP, ...PICKS.filter(p=>!p.hidden)); }
  }
}

function getAdjProj(p){
  const delta=getScoringDelta(p.n,p.p||p.pos,scoringFmt);
  return Math.max(0,+(p.proj+delta).toFixed(1));
}
/* ── "Preseason · Actual So Far | Rest Of Season" context line (26 Sep 2026; relabelled 3 Oct) ─
   Shared by the rankings pop-up card (index.html) and the player page (player.html).
   Context, not a grade: one player's weeks are noise; the Scorecard tab is the grade.
   All three numbers are in the LEAGUE'S scoring, so they are always comparable:
     Preseason = the frozen 7 Sep projection (data/freeze-2026.json, the ledger's record,
                 half PPR + TE premium) plus the same getScoringDelta() the live number gets
     Now       = getAdjProj(p), exactly the card's own projection chip
     Actual    = this season's played games, each scored by gamefp() in the league's format
   Players outside the frozen 376 get no line — "preseason" means the frozen record. */
let FREEZE_PROJ=null, FREEZE_PROJ_LOADING=null;
function loadFreezeProj(){
  if(FREEZE_PROJ) return Promise.resolve(FREEZE_PROJ);
  if(!FREEZE_PROJ_LOADING) FREEZE_PROJ_LOADING=fetch('./data/freeze-2026.json',{cache:'no-cache'})
    .then(r=>r.ok?r.json():Promise.reject('freeze '+r.status))
    .then(d=>{ const m={}; for(const [n,v] of Object.entries(d.players||{})) if(v&&v.proj!=null) m[n]=v.proj; FREEZE_PROJ=m; return m; })
    .catch(e=>{ FREEZE_PROJ_LOADING=null; throw e; });
  return FREEZE_PROJ_LOADING;
}
/* This season's played games, scored in the league's format: the ONE place "so far"
   points are added up (8 Oct 2026). projContext's Actual So Far, the roster's PPG '26
   and the rankings column all read it, so they cannot disagree. Played = not upcoming,
   not DNP (the locked one-snap rule). qs marks a full start (QB per-start projection). */
function seasonTally(p){
  const pos=p.pos||p.p; let g=0,pts=0,fg=0,fpts=0;
  for(const r of ((GAMELOGS&&GAMELOGS[p.n])||[])) if(r.s===SEASON_YEAR&&!r.up&&!r.dnp){
    const fp=gamefp(r,pos,scoringFmt); g++; pts+=fp; if(r.qs){ fg++; fpts+=fp; } }
  return {g,pts,fg,fpts};
}
/* PPG this season so far, or null before his first game (or while logs load). Display only. */
function ppgSoFar(p){
  if(!GAMELOGS) return null;
  const t=seasonTally(p); return t.g ? t.pts/t.g : null;
}
function projContext(p){
  if(!FREEZE_PROJ||FREEZE_PROJ[p.n]==null) return null;
  const pos=p.pos||p.p;
  const pre=Math.max(0,FREEZE_PROJ[p.n]+getScoringDelta(p.n,pos,scoringFmt));
  const now=getAdjProj(p);
  // A per-start QB's Rest Of Season number is per FULL start (qbPerStart). Relabelled 3 Oct 2026 (owner):
  // the line was one comparison of three numbers; it is a grade (Preseason vs Actual So Far, both every
  // game played — the ledger's yardstick) and a forecast (Rest Of Season). Where a QB's full starts
  // differ from his games played (an injury exit, a bench cameo), Full Starts So Far shows what fed it.
  const perStart = pos==='QB' && QB_PS && QB_PS_LEVEL>0 && GL_HAS_QS;
  if(!GAMELOGS) return {pre,now,act:null,g:null,perStart};         // logs still loading: no Actual yet
  const {g,pts,fg,fpts}=seasonTally(p);
  const showFull = perStart && fg!==g;
  return {pre,now,act:g?pts/g:null,g,perStart,showFull,full:fg?fpts/fg:null,fg};
}
/* projContextHTML: the old one-line version. No page draws it since 26 Oct 2026 — both pages show
   dlProjChartHTML() (design A1, below). Kept for now so a roll-back is a one-line change. */
function projContextHTML(p,linkHtml){
  const c=projContext(p); if(!c) return '';
  const m='font-family:var(--mono)';
  const dot=' <span style="color:var(--fog-2)">\u00b7</span> ', lab=t=>'<span style="color:var(--fog)">'+t+'</span> ';
  const games=k=>' <span style="color:var(--fog)">('+k+(k===1?' game':' games')+')</span>';
  // The grade: the frozen call against every game played (the ledger's yardstick).
  const item=h=>'<span style="white-space:nowrap">'+h+'</span>';   // a label never splits from its number on a phone
  let txt=item(lab('Preseason')+'<span style="'+m+'">'+c.pre.toFixed(1)+'</span>');
  if(c.g!=null) txt+=dot+item(lab('Actual So Far')
    +(c.act!=null?'<span style="'+m+'">'+c.act.toFixed(1)+'</span>'+games(c.g):'<span style="color:var(--fog)">no games yet</span>'));
  // The forecast: points per game from here on (per full start for a QB).
  let fc=item(lab(c.perStart?'Rest Of Season Per Full Start':'Rest Of Season')
    +'<span style="'+m+';color:var(--teal-br);font-weight:700">'+c.now.toFixed(1)+'</span>');
  if(c.showFull) fc+=dot+item(lab('Full Starts So Far')
    +(c.full!=null?'<span style="'+m+'">'+c.full.toFixed(1)+'</span>'+games(c.fg):'<span style="color:var(--fog)">none yet</span>'));
  txt='<span>'+txt+'</span><span>'+fc+'</span>';
  const vals=[c.pre,c.now].concat(c.act!=null?[c.act]:[]);
  const lo=Math.floor(Math.min(...vals)-1), hi=Math.ceil(Math.max(...vals)+1), X=v=>(6+(v-lo)/(hi-lo)*108).toFixed(1);
  const scale='<svg width="120" height="14" viewBox="0 0 120 14" aria-hidden="true" style="flex:none">'
    +'<line x1="6" y1="7" x2="114" y2="7" stroke="var(--line)" stroke-width="2"></line>'
    +(c.act!=null?'<circle cx="'+X(c.act)+'" cy="7" r="4" fill="var(--paper)"></circle>':'')
    +'<circle cx="'+X(c.now)+'" cy="7" r="4.5" fill="var(--teal-br)"></circle>'
    +'<circle cx="'+X(c.pre)+'" cy="7" r="3.6" fill="none" stroke="var(--fog)" stroke-width="1.5"></circle></svg>';
  return '<span style="display:inline-flex;flex-wrap:wrap;align-items:center;gap:6px 10px;font-size:12px">'
    +txt+scale+(linkHtml||'')+'</span>';
}
/* ── PLAYER HEADER, DESIGN A1 (26 Oct 2026, owner) ─────────────────────────────────────────────
   Shared by the player page (player.html buildHeroHTML) and the rankings pop-up card (index.html
   renderDeck), so the two cannot drift. Display only: every number here is one the site already
   showed in the old header. The layout, chosen by the owner from mockups:
     the Score ring, big, with the position rank under it; beside it the name (always one line),
     position / team / age / contract, college / draft, the call with its gap to market, and the
     Owned In line. Below: three tiles (Market, Model, Proj PPG) and the season chart.
   The styles (.dlh-*) live in each page's own <style>; keep player.html and index.html in step.
   The chart needs the frozen preseason file, so pages draw it after loadFreezeProj(). */
/* Projection colour, scaled by position so 12 PPG reads good for a TE and middling for a WR.
   Moved here from index.html (26 Oct 2026) so the player page's tile uses the same bands. */
function projChipColor(v,pos){
  const hi=pos==='QB'?21:pos==='RB'?16:pos==='TE'?11:15;
  const mid=pos==='QB'?17:pos==='RB'?12:pos==='TE'?8:11;
  return v>=hi?'var(--emerald)':v>=mid?'var(--sky)':v>=mid*0.7?'var(--topaz)':'var(--coral)';
}
function dlHdrMetaHTML(p){
  const ct=CONTRACTS.find(c=>c.n===p.n), pos=p.pos||p.p;
  const team=(typeof AL!=='undefined'&&AL[p.t])?AL[p.t]:p.t;
  const opt=ct?fifthYearNote(p,ct):'';
  // "+opt" sits on the contract's own line at the same size (owner: it read like a superscript).
  return '<span class="dlh-pos">'+pos+'</span><span>'+(team||'FA')+'</span><span>Age '+(p.a!=null?p.a.toFixed(1):'—')+'</span>'
    +(ct?'<span>Thru '+ct.end
      +(ct.end<=SEASON_YEAR?' <span style="color:var(--topaz)" title="Walk year: the contract ends after this season">⚠</span>':'')
      +(opt?' <span class="dlh-opt" title="'+opt+'">+opt</span>':'')+'</span>':'');
}
/* One school: the one he came to the NFL from. A transfer's list comes in two shapes:
   - the nightly feed (nflverse player bios), newest first: "Indiana; James Madison; St. Francis PA".
     Checked 26 Oct 2026 against the draft records: the first school was the draft-day school for
     every one of the 117 transfers that could be matched;
   - this file's own COLLEGES table, oldest first: "Alabama/Oklahoma".
   So the first of a ";" list, the last of a "/" list. */
function dlHdrSchool(p){
  const raw=(typeof COLLEGES!=='undefined'&&COLLEGES[p.n])?String(COLLEGES[p.n]).trim():'';
  if(raw.indexOf(';')>=0) return raw.split(';')[0].trim();
  return raw.split('/').pop().trim();
}
function dlHdrBgText(p){
  const dp=DRAFT_PICKS[p.n];
  return [dlHdrSchool(p), dp?dp.y+' Rd'+dp.r+' Pick '+dp.p:''].filter(Boolean).join(' · ');
}
function dlHdrCallHTML(p){
  const vt=(vTag(p).match(/>([a-z ]+)</)||[,''])[1], rookie=dlRookieHold(p);
  const buy=/buy/.test(vt), sell=/sell/.test(vt);
  const clr=buy?'var(--emerald)':/strong sell/.test(vt)?'var(--coral-bri)':sell?'var(--coral)':'var(--paper)';
  const bg=buy?'var(--emerald-tint)':sell?'var(--coral-tint)':'var(--line)';
  // The gap is the call's own ratio (verdictRatio). None under the price floor: there the call is
  // a plain Hold with no copy (owner, 22 Oct).
  let gap='';
  if(rookie) gap='No season on record yet';
  else if(!dlBelowCallFloor(p)){ const pct=Math.round((verdictRatio(p)-1)*100);
    gap=pct===0?'Model level with market':Math.abs(pct)+'% '+(pct>0?'above':'below')+' market'; }
  return '<span class="dlh-call" style="color:'+clr+';background:'+bg+'"'+(rookie?' title="'+DL_ROOKIE_HOLD_TIP+'"':'')+'>'
    +vt+(rookie?' · rookie':'')+'</span>'+(gap?'<span class="dlh-gap">'+gap+'</span>':'');
}
function dlHdrReachHTML(p){
  if(typeof dlLeagueReach!=='function') return '';
  const r=dlLeagueReach(p.n,p.pos||p.p), t=dlLeagueReachText(r);
  return t?'<div class="dlh-reach" title="'+dlLeagueReachTitle(r).replace(/"/g,'&quot;')+'">'+t+'</div>':'';
}
function dlPerStartQB(p){
  return (p.pos||p.p)==='QB' && QB_PS && QB_PS_LEVEL>0 && GL_HAS_QS;   // same test as projContext()
}
function dlHdrTilesHTML(p){
  const mk=p.ktcEff!=null?p.ktcEff:(p.ktc!=null?p.ktc:0), mv=mvAsset(p), adj=getAdjProj(p);
  // Proj PPG repeats the chart's Rest Of Season on purpose (owner): the big number for a quick look.
  return '<div class="dlh-tiles">'
    +'<div><small>Market</small><b>'+Math.round(mk).toLocaleString()+'</b></div>'
    +'<div><small>Model</small><b>'+(mv>=19999?'19,999+':Math.round(mv||0).toLocaleString())+'</b></div>'
    +'<div><small>'+(dlPerStartQB(p)?'Proj / Start':'Proj PPG')+'</small><b style="color:'+projChipColor(adj||0,p.pos||p.p)+'">'
    +(adj!=null?adj.toFixed(1):'—')+'</b></div></div>';
}
/* The season chart (owner, 25-26 Oct 2026): one number line, Preseason / So Far / Rest Of Season.
   - Labels sit in one evenly spaced row above the line, in the dots' left-to-right order, with no
     connecting lines. Each number is its dot's colour. Always three numbers, three labels.
   - So Far is sky at or above Preseason, violet below, judged on the numbers shown.
   - Two numbers that match share one dot carrying both looks: So Far's fill inside Rest Of
     Season's teal ring (the common case), or a grey ring when Preseason is one of the pair. */
function dlProjChartHTML(p){
  const c=projContext(p); if(!c) return '';
  const pts=[{v:c.pre,lab:'Preseason',cls:'o'}];
  if(c.act!=null) pts.push({v:c.act,lab:'So Far',cls:'w',clr:+c.act.toFixed(1)>=+c.pre.toFixed(1)?'var(--sky)':'var(--violet)'});
  pts.push({v:c.now,lab:c.perStart?'Rest / Start':'Rest Of Season',cls:'t',clr:'var(--teal-br)'});
  pts.forEach((x,i)=>{ x.i=i; x.r=x.v.toFixed(1); });
  const vals=pts.map(x=>x.v), lo=Math.floor(Math.min(...vals)-1), hi=Math.ceil(Math.max(...vals)+1);
  pts.forEach(x=>{ x.x=100*(x.v-lo)/(hi-lo); });
  const groups={}; pts.forEach(x=>{ (groups[x.r]=groups[x.r]||[]).push(x); });
  const dots=Object.values(groups).map(g=>{
    const at='left:'+g[0].x.toFixed(1)+'%';
    if(g.length===1){ const x=g[0]; return '<span class="dlh-pt dlh-pt-'+x.cls+'" style="'+at+(x.cls==='w'?';background:'+x.clr:'')+'"></span>'; }
    const o=g.find(x=>x.cls==='o'), w=g.find(x=>x.cls==='w'), t=g.find(x=>x.cls==='t');
    const fill=w?w.clr:'var(--teal-br)', edge=(w&&t)?'var(--teal-br)':'var(--fog)';
    const ring=(o&&w&&t)?'0 0 0 2px var(--fog)':t?'0 0 0 3px var(--teal-tint)':'none';
    return '<span class="dlh-pt dlh-pt-mix" style="'+at+';background:'+fill+';border-color:'+edge+';box-shadow:'+ring+'"></span>';
  }).join('');
  const lbl=x=>'<div class="dlh-lbl"><b'+(x.clr?' style="color:'+x.clr+'"':'')+'>'+x.r+'</b><small>'+x.lab+'</small></div>';
  const order=pts.slice().sort((a,b)=>(+a.r-+b.r)||(a.i-b.i));
  return '<div class="dlh-chart"><div class="dlh-chart-h">'+SEASON_YEAR+' Points Per Game'+(c.perStart?' · Per Full Start From Here':'')+'</div>'
    +'<div class="dlh-lbls" style="grid-template-columns:repeat('+pts.length+',minmax(0,1fr))">'+order.map(lbl).join('')+'</div>'
    +'<div class="dlh-plot"><span class="dlh-axis"></span>'+dots+'</div>'
    +'<div class="dlh-scale"><span>'+lo+'</span><span>'+hi+'</span></div>'
    +(c.g!=null?'<div class="dlh-chart-f">So far: '+c.g+' game'+(c.g===1?'':'s')
      +(c.showFull?' · '+c.fg+' full start'+(c.fg===1?'':'s')+', '+(c.full!=null?c.full.toFixed(1):'—')+' per start':'')+'</div>':'')
    +'</div>';
}
/* One line, largest size that fits (owner: "I hate the look of names broken into two lines").
   Steps down from `max` px until the text fits its box, never below `min`. */
function dlFitOneLine(el,max,min){
  if(!el) return;
  let fs=max; el.style.fontSize=fs+'px';
  while(el.scrollWidth>el.clientWidth+0.5 && fs>min){ fs-=0.5; el.style.fontSize=fs+'px'; }
}
/* Fit everything in a header that must stay on one line: the name, the meta line, the college line,
   and the chart labels (which shrink as a set, to 85% at most, if one outgrows its share of the row).
   Pages call this after drawing, when fonts finish loading, and on resize. */
function dlHdrFit(root,nameMax){
  if(!root) return;
  dlFitOneLine(root.querySelector('.dlh-name'),nameMax||24,14);
  dlFitOneLine(root.querySelector('.dlh-meta'),12.5,10);
  dlFitOneLine(root.querySelector('.dlh-bg'),12,10);
  const row=root.querySelector('.dlh-lbls');
  if(row) for(const sc of [1,0.95,0.9,0.85]){
    row.style.setProperty('--ls',sc);
    if([...row.children].every(el=>el.scrollWidth<=el.clientWidth+0.5)) break;
  }
}
function rescalePickTier(year, rnd, tierName, newTierVal) {
  const tierSlots = {Early:[1,2,3,4], Mid:[5,6,7,8], Late:[9,10,11,12]};
  const slots = tierSlots[tierName];
  if (!slots) return;
  /* The TIER ASSET ITSELF ('2027 Early 3rd Round Pick') is what the trade
     calculator prices when a tiered pick is added, and it was never touched
     here — only the numbered slots were. So even a matching name would have
     left the thing on screen stale. It is the market's own number for that
     tier, so it is set, not scaled. */
  const ord = {1:'1st',2:'2nd',3:'3rd'}[rnd];
  const tierAsset = ord && PICKS.find(p => p.n === year+' '+tierName+' '+ord+' Round Pick');
  if (tierAsset) { tierAsset.k = Math.round(newTierVal); tierAsset.kMkt = Math.round(newTierVal); }
  const slotPicks = PICKS.filter(p => {
    const m = p.n.match(/^(\d{4}) (\d)\.(\d{2})$/);
    return m && m[1]===String(year) && parseInt(m[2])===rnd && slots.includes(parseInt(m[3]));
  });
  if (!slotPicks.length) return;
  const avg = slotPicks.reduce((s,p)=>s+p.k,0) / slotPicks.length;
  const ratio = newTierVal / (avg || newTierVal);
  slotPicks.forEach(p => { p.k = Math.round(p.k * ratio); });
}
// ── NAME ALIASES ──────────────────────────────────────────────────────────
// Add entries here whenever you notice a player isn't getting updated.
// Format: 'FantasyCalc name': 'DELTA name'
// Normalize a player name for fuzzy FC↔DELTA matching: lowercase, drop
// punctuation (periods/apostrophes/hyphens) and common suffixes. This catches
// the whole class of stale-value bugs where FC and DELTA disagree only on
// punctuation — e.g. FC 'Marvin Harrison Jr' vs DELTA 'Marvin Harrison Jr.',
// FC "Tre' Harris" vs DELTA 'Tre Harris', FC 'Ja'Tavion' vs DELTA 'JaTavion'.
function fcNorm(s){
  return String(s||'').toLowerCase()
    .replace(/[.''\u2019\-]/g,'')
    .replace(/\b(jr|sr|ii|iii|iv)\b/g,'')
    .replace(/\s+/g,' ').trim();
}
// Build a normalized index of an FC slice once: {normalizedName: originalKey}.
function fcNormIndex(slice){
  const idx={};
  for(const k in slice){ const n=fcNorm(k); if(!(n in idx)) idx[n]=k; }
  return idx;
}
/* DELTA name → FantasyCalc name. THE KEY IS DELTA'S SPELLING — that is the
   direction both consumers read it (valOf() in loadLiveMarketValues, and the
   kMkt lookup in applyMarketForSetting), and it matches the convention the
   nightly pipeline already uses ('DELTA name -> nflverse display name' in
   fetch-player-stats.py). The header used to say the opposite, and the table was
   written to that wrong header: of 22 entries exactly ONE ever fired.

   WHAT BELONGS HERE: only names normalization cannot bridge — a different first
   name, a nickname, a genuinely different string. Nothing else. fcNorm() already
   strips periods, apostrophes, hyphens and Jr/Sr/II/III/IV from both sides, so
   FC's 'Kenneth Walker' / 'Marvin Harrison Jr' / 'Michael Pittman' / 'Sam LaPorta'
   / 'Brian Thomas' / 'C.J. Stroud' all resolve on their own. Measured against the
   live 12|sf slice on 16 Aug 2026: 361 names hit FC directly, 10 more resolve
   through fcNorm, 1 needs this table. The twenty entries removed here were all
   inert — either no-ops ('CeeDee Lamb': 'CeeDee Lamb') or punctuation variants
   fcNorm already handled. Adding a dead entry is worse than adding none: it reads
   as coverage that does not exist, which is how Gainwell sat mispriced.

   Gainwell is the shape that DOES need an entry: FantasyCalc, nflverse
   load_player_stats and nflverse load_players all say 'Kenny', while DELTA, OTC
   contracts, the game logs, nflverse load_draft_picks and nflverse snap counts all
   say 'Kenneth'. No normalizer bridges Kenneth→Kenny; only a stated alias does. */
const FC_ALIASES = {
  'Chigoziem Okonkwo':     'Chig Okonkwo',
  'Kenneth Gainwell':      'Kenny Gainwell',
};


/* The stats file is the same for every league format; only the PPG recompute
   below depends on the format. A format change re-runs this function for that
   recompute, and used to re-download ~786 KB to do it. The text from the first
   good download is kept and re-parsed instead (a fresh parse, so the result is
   exactly what a re-download gave). A page reload still downloads fresh. */
let PS_TEXT = null;
async function loadPlayerStats() {
  try {
    let txt = PS_TEXT;
    if (txt == null) {
      const res = await dlFetch('./data/player-stats.json',{cache:'no-cache'});
      if (!res.ok) { dlNoteFail('player stats'); return; }
      txt = await res.text();
    }
    const data = JSON.parse(txt);
    if (data?.players) PS_TEXT = txt;
    if (!data?.players) return;

    PLAYER_STATS = data.players;
    // data.headshots (NFL.com photo addresses) is no longer read or written (25 Oct 2026, step 6).
    QB_ROLES = data.qb_roles || {};
    // Model value follows the live depth chart; the DELTA Score holds in-season (owner, 2 Oct 2026).
    // Older data files without the field fall back to qb_roles, which was the same set until then.
    QB_ROLES_SCORE = data.qb_roles_score || data.qb_roles || {};
    QB_PS = data.qb_start_splits || null; QB_PS_LEVEL = data.qb_starter_level || 0;   // points per start (null/0: old QB path)
    if (Object.keys(QB_ROLES).length) console.log('[DELTA] QB backup flags loaded:', Object.keys(QB_ROLES).join(', '));
    // Backfill g24 and g23 (games played in prior seasons) from the pipeline onto
    // RAW player objects. These aren't baked into RAW — the pipeline is the only
    // source. Required for the player page PPG trend games column.
    let gUpd = 0;
    for (const player of RAW) {
      const pdata = data.players[player.n];
      if (!pdata) continue;
      if (pdata['2024'] && pdata['2024'].games > 0) { player.g24 = pdata['2024'].games; gUpd++; }
      if (pdata['2023'] && pdata['2023'].games > 0) { player.g23 = pdata['2023'].games; }
    }
    if (gUpd) console.log('[DELTA] ' + gUpd + ' players updated with prior-season game counts (g24/g23)');
    // Team fields are live data: the pipeline emits `teams` from the nflverse
    // 2026 roster feed, so trades and FA moves (A.J. Brown PHI→NE, Mac Jones
    // NE→SF) flow into RAW nightly instead of waiting on hand edits. Baked
    // RAW.t remains the first-paint fallback and covers players the roster
    // feed can't resolve.
    if (data.injury) {
      INJ_STATUS = data.injury;
      console.log('[DELTA] Injury statuses loaded:', Object.keys(data.injury).length);
    }
    if (data.teams) {
      let moved = 0;
      for (const player of RAW) {
        const t = data.teams[player.n];
        if (t && player.t !== t) {
          console.log('[DELTA] team update:', player.n, player.t, '\u2192', t);
          player.t = t; moved++;
        }
      }
      if (moved) console.log('[DELTA] ' + moved + ' team field(s) updated from roster feed');
    }
    // EPA: the pipeline computes QB/RB EPA-per-play from nflverse play-by-play
    // and emits it as data.epa (keyed by DELTA name). It is merged OVER the hand
    // EPA table so QB/RB efficiency is now data-driven and auto-populates the
    // expanded universe. WR/TE entries in the hand table are intentionally left
    // alone — their efficiency input is hand-curated YPRR (no free routes-run
    // source), so the pipeline never touches receiver rows. ef25 (a secondary
    // RB display metric) is preserved from the hand table when present.
    if (data.epa && typeof EPA !== 'undefined') {
      let epaUpd = 0;
      for (const name in data.epa) {
        const v = data.epa[name];
        const prev = EPA[name] || {};
        EPA[name] = {
          e25: v.e25 != null ? v.e25 : (prev.e25 || 0),
          e24: v.e24 != null ? v.e24 : (prev.e24 || 0),
          e23: v.e23 != null ? v.e23 : (prev.e23 || 0),
          e22: v.e22 != null ? v.e22 : (prev.e22 || 0),
          ef25: prev.ef25 != null ? prev.ef25 : (v.e25 != null ? v.e25 : 0)
        };
        epaUpd++;
      }
      if (epaUpd) console.log('[DELTA] ' + epaUpd + ' QB/RB EPA entries updated from pipeline');
    }
    // Draft capital + college: the pipeline pulls these from nflverse (draft
    // picks dataset + player bios) and emits data.draft {name:{y,r,p}} and
    // data.college {name:'College'}. Merged OVER the hand DRAFT_PICKS/COLLEGES
    // tables so they auto-populate the expanded universe and stop going stale.
    // Hand tables remain the fallback for anyone the feed doesn't resolve
    // (incoming rookies before the draft dataset updates, name-match misses).
    if (data.draft && typeof DRAFT_PICKS !== 'undefined') {
      let n = 0, rejected = 0;
      // current NFL season for the "is this draft year plausible" check
      const CUR_DRAFT_YR = 2026;
      for (const name in data.draft) {
        const v = data.draft[name];
        if (!v || v.p == null) continue;
        // Rookie-collision guard: the draft feed matches on name, and a recent
        // rookie can share a name with a veteran (e.g. a 2026 'Justin Jefferson'
        // pick 149 vs the real 2020 R1 star). A wrong match flips a veteran to
        // "rookie" and discards their demonstrated opportunity. So if the feed
        // says a player was drafted in the last 2 years BUT they have real prior
        // NFL production (2023/2024 games), it's a bad match — keep baked draft.
        const st = (typeof PLAYER_STATS !== 'undefined') ? PLAYER_STATS[name] : null;
        const priorG = st ? (((st['2023']||{}).games||0) + ((st['2024']||{}).games||0)) : 0;
        if (v.y >= CUR_DRAFT_YR - 1 && priorG > 0) { rejected++; continue; }
        // Parent/namesake guard (the other direction): the feed can also match a
        // MUCH older player with the same name (Marvin Harrison Jr. ← the 1996
        // Marvin Harrison). If a curated baked entry exists and the feed's year
        // is 3+ off, the baked entry wins.
        const baked = DRAFT_PICKS[name];
        if (baked && Math.abs((v.y||0) - (baked.y||0)) > 3) { rejected++; continue; }
        // Age guard (10 Oct 2026): a draft year that would make him younger than 19 on
        // draft day is a namesake, whatever the feed says (Chris Brazzell II, 23, was
        // matched to the 1998 Chris Brazzell; no baked entry existed to catch it).
        const rawP = (typeof RAW !== 'undefined') ? RAW.find(function(x){ return x && x.n === name; }) : null;
        if (rawP && rawP.a && v.y && (rawP.a - (CUR_DRAFT_YR - v.y)) < 19) { rejected++; continue; }
        DRAFT_PICKS[name] = { y: v.y, r: v.r, p: v.p }; n++;
      }
      if (n) console.log('[DELTA] ' + n + ' draft-capital entries from pipeline');
      if (rejected) console.log('[DELTA] ' + rejected + ' draft entries rejected (rookie-collision guard)');
    }
    if (data.college && typeof COLLEGES !== 'undefined') {
      let n = 0;
      for (const name in data.college) {
        if (data.college[name]) { COLLEGES[name] = data.college[name]; n++; }
      }
      if (n) console.log('[DELTA] ' + n + ' college entries from pipeline');
    }
    // Age from nflverse bios (birth_date). Merged over baked RAW age — important
    // for the universe-expansion players seeded with a placeholder age, which
    // self-correct to real age on the first pipeline run (age feeds the DELTA
    // Score age axis, so a wrong seed would distort the score until corrected).
    // Names whose baked age is authoritative — pipeline NEVER overwrites,
    // regardless of the seed heuristic. Protects manual DOB fixes from the
    // x.0-is-an-integer trap (Number.isInteger(27.0)===true) and from known
    // nflverse name collisions (a different, younger Justin Jefferson; an
    // older DB D.J. Moore).
    const AGE_LOCK = new Set(['Justin Jefferson', 'D.J. Moore', 'Devaughn Vele']);
    if (data.age) {
      let n = 0, rejected = 0;
      for (const player of RAW) {
        const a = data.age[player.n];
        if (a == null || a <= 0) continue;
        if (AGE_LOCK.has(player.n)) { rejected++; continue; }
        const baked = player.a;
        // The 117 universe-expansion players were seeded with PLACEHOLDER ages —
        // whole integers (24, 25). Real baked ages carry a decimal (28.9). The
        // collision guard must only protect REAL baked ages: for a seed, the
        // pipeline age is strictly better, so accept it even if it diverges a
        // lot (e.g. Tyreek Hill seeded 24 → real 32.3). For a real decimal baked
        // age, a >3yr jump signals a name-collision bad match (e.g. Justin Jefferson
        // baked 26.8 vs a 23yr nflverse player with the same name, or D.J. Moore
        // 28.9 vs an older DB D.J. Moore 39) → keep the trusted baked value.
        // Tightened from >6 to >3 after two confirmed collisions at 3.5yr diff.
        const bakedIsSeed = baked != null && Number.isInteger(baked);
        if (!bakedIsSeed && baked != null && baked > 0 && Math.abs(a - baked) > 3) {
          rejected++;
          continue;
        }
        player.a = a; n++;
      }
      if (n) console.log('[DELTA] ' + n + ' ages updated from pipeline');
      if (rejected) console.log('[DELTA] ' + rejected + ' pipeline ages rejected (collision guard)');
    }
    // RB snap share, receptions/game, target-share delta: all pipeline-derived
    // (snap share from nflverse snap counts; rec/g and ts-delta computed from
    // per-season stats). Merged OVER the hand RB_SNAP / REC_PG / TS_DELTA tables
    // so they auto-populate the expanded universe. Hand tables stay as fallback.
    if (data.rb_snap && typeof RB_SNAP !== 'undefined') {
      let n = 0;
      for (const name in data.rb_snap) {
        const v = data.rb_snap[name];
        if (Array.isArray(v) && v.length) { RB_SNAP[name] = v; n++; }
      }
      if (n) console.log('[DELTA] ' + n + ' RB snap-share entries from pipeline');
    }
    if (data.rec_pg && typeof REC_PG !== 'undefined') {
      let n = 0;
      for (const name in data.rec_pg) {
        if (data.rec_pg[name] != null) { REC_PG[name] = data.rec_pg[name]; n++; }
      }
      if (n) console.log('[DELTA] ' + n + ' rec/g entries from pipeline');
    }
    if (data.ts_delta && typeof TS_DELTA !== 'undefined') {
      let n = 0;
      for (const name in data.ts_delta) {
        if (data.ts_delta[name] != null) { TS_DELTA[name] = data.ts_delta[name]; n++; }
      }
      if (n) console.log('[DELTA] ' + n + ' target-share-delta entries from pipeline');
    }
    let updated = 0;
    for (const player of RAW) {
      if (!player || !player.n) continue;
      const s = PLAYER_STATS[player.n];
      if (!s) continue;
      // Update baked-in PPG from live stats — respects active scoring format
      // Base rec pts per format: half_tep=0.5, half=0.5, full_tep=1.0, full=1.0, std=0
      // TE premium adds 0.5 for half_tep and full_tep
      const fmt = typeof scoringFmt !== 'undefined' ? scoringFmt : 'half_tep';
      const baseRec = (fmt==='full'||fmt==='full_tep') ? 1.0 : fmt==='std' ? 0 : 0.5;
      const tePrem  = (fmt==='half_tep'||fmt==='full_tep') ? 0.5 : 0;
      const recPts  = baseRec + (player.p === 'TE' ? tePrem : 0);
      for (const [yr, key] of [['2025','ppg25'],['2024','ppg24'],['2023','ppg23']]) {
        const row = s[yr];
        if (!row || !row.games) continue;
        // NOTE: g25 is deliberately NOT synced from these rows — the stats file
        // undercounts multi-team (traded) seasons (one row per team stint, only
        // one survives). Game logs are the canonical played-games source under
        // the locked DNP rule; g25 syncs in ensureStartData() instead.
        const ppgAt = (rp) => (
          (row.rec     || 0) * rp +
          (row.rec_yds || 0) * 0.1 +
          (row.rec_td  || 0) * 6 +
          (row.rush_yds|| 0) * 0.1 +
          (row.rush_td || 0) * 6 +
          (row.pass_yds|| 0) * 0.04 +
          (row.pass_td || 0) * 4 -
          (row.pass_int|| 0) * 2
        ) / row.games;
        const ppg = ppgAt(recPts);
        if (ppg > 0) { player[key] = Math.round(ppg * 10) / 10; updated++; }
        // The same season in the projection's basis, half PPR + TE premium (26 Sep 2026).
        // calcProj works only in this basis; getAdjProj() converts to the league's format once.
        const ppgH = ppgAt(0.5 + (player.p === 'TE' ? 0.5 : 0));
        if (ppgH > 0) player[key.replace('ppg', 'ppgH')] = Math.round(ppgH * 10) / 10;
      }
    }
    // Rebuild COMP with fresh PPG and opportunity scores now available
    COMP.length = 0;
    RAW.forEach(r => COMP.push(calcProj(r)));
    ASSETS.length = 0;
    ASSETS.push(...COMP, ...PICKS.filter(p => !p.hidden));
    if (typeof renderRankings === 'function') renderRankings();
    console.log(`[DELTA] Player stats loaded: ${Object.keys(PLAYER_STATS).length} players, ${updated} PPG values updated`);
  } catch(e) {
    dlNoteFail('player stats');
    console.warn('[DELTA] Could not load player stats:', e.message);
  }
}

// ── LOADER ────────────────────────────────────────────────────────────────
async function loadLiveMarketValues() {
  try {
    const res = await dlFetch('./data/market-values.json',{cache:'no-cache'}); // cache-bust: bypass Pages CDN edge cache
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    // Skip if file is the empty placeholder
    if (data.playerCount === 0) {
      console.log('[DELTA] Market values not yet populated — using baked-in values');
      // Report it. This path used to return without touching the badge, which left
      // whatever the previous call had set — so an unpopulated file was indistinguishable
      // from a healthy load. -2 is the "not yet published" sentinel (see dlFreshHtml).
      if (typeof showDataFreshness === 'function') showDataFreshness(data.fetched || new Date().toISOString(), -2);
      return;
    }

    // Supports the per-format grid file {settings:{"T|Q":{...}}, default:"12|sf"}
    // and the legacy flat file {values:{...}}. The default (12-SF) slice is the
    // model's anchor (player.k); the selected-format slice drives player.kMkt.
    // direct → alias → NORMALIZED (punctuation/suffix-insensitive). The
    // normalized fallback fixes stale anchors for names FC spells differently
    // (MHJ 'Marvin Harrison Jr' vs DELTA 'Marvin Harrison Jr.', etc.).
    const _nidxCache = new WeakMap();
    const valOf=(map,name)=>{
      let v = map[name] || (FC_ALIASES[name] && map[FC_ALIASES[name]]);
      if(v) return v;
      let idx=_nidxCache.get(map);
      if(!idx){ idx=fcNormIndex(map); _nidxCache.set(map,idx); }
      const k=idx[fcNorm(name)];
      return k? map[k] : null;
    };

    let anchorSlice;
    if (data.settings) {
      MARKET_SETTINGS = data.settings;
      MARKET_DEFAULT  = data.default || '12|sf';
      anchorSlice     = MARKET_SETTINGS[MARKET_DEFAULT] || MARKET_SETTINGS[Object.keys(MARKET_SETTINGS)[0]];
    } else {
      MARKET_SETTINGS = null;            // legacy flat file
      anchorSlice     = data.values || {};
    }

    /* PICK TIERS, rescaled from the anchor slice. FantasyCalc RENAMED these at
       some point: it sends '2027 3rd (Early)' where it used to send
       '2027 Early 3rd Round Pick'. Only the old spelling was looked up, so from
       the rename onward every lookup missed, nothing was rescaled, and every
       tiered and slotted pick kept the value baked into this file — by Sept 2026
       a 2027 late 3rd read 2,212 against a market price of 987, so picks in the
       trade calculator were worth roughly double what they should have been.
       Both spellings are tried now, and the result is COUNTED: a third rename
       shows up in the console instead of silently freezing prices again. */
    const PICK_ORD = {1:'1st', 2:'2nd', 3:'3rd'};
    let tiersHit = 0; const tiersMissed = [];
    for (const rnd of [1,2,3]) {
      for (const tier of ['Early','Mid','Late']) {
        for (const yr of [2026,2027,2028]) {
          const fc = anchorSlice[yr+' '+PICK_ORD[rnd]+' ('+tier+')']            // current naming
                  || anchorSlice[yr+' '+tier+' '+PICK_ORD[rnd]+' Round Pick'];  // pre-rename naming
          if (fc) { rescalePickTier(yr, rnd, tier, fc.value); tiersHit++; }
          else tiersMissed.push(yr+' '+tier+' '+PICK_ORD[rnd]);
        }
      }
    }
    /* YEARS THE FILE PRICES ONLY AS A ROUND. FantasyCalc tiers just the next
       draft class: 2028 arrives as a plain '2028 1st' with no early/mid/late.
       Left there, every tiered and numbered 2028 pick keeps its baked value,
       which is the same bug one year out — a 2028 early 1st read 4,991 against
       a market pricing the whole round at 2,190. The SHAPE comes from the year
       that does have tiers: early, mid and late sit at a measured ratio to
       their plain round price, and that ratio carries over. Nothing is being
       assumed about 2028 itself beyond one draft class pricing like another. */
    const shape = {};
    for (const rnd of [1,2,3]) {
      for (const tier of ['Early','Mid','Late']) {
        for (const yr of [2026,2027,2028]) {
          const t = anchorSlice[yr+' '+PICK_ORD[rnd]+' ('+tier+')'], g = anchorSlice[yr+' '+PICK_ORD[rnd]];
          if (t && g && g.value > 0) { shape[rnd+tier] = t.value / g.value; break; }
        }
      }
    }
    const derived = [];
    for (const rnd of [1,2,3]) {
      for (const tier of ['Early','Mid','Late']) {
        for (const yr of [2026,2027,2028]) {
          if (anchorSlice[yr+' '+PICK_ORD[rnd]+' ('+tier+')']) continue;   // already priced by tier
          const g = anchorSlice[yr+' '+PICK_ORD[rnd]], r = shape[rnd+tier];
          if (!g || !r) continue;
          rescalePickTier(yr, rnd, tier, g.value * r);
          derived.push(yr+' '+tier+' '+PICK_ORD[rnd]);
        }
      }
    }
    console.log('[DELTA] Pick tiers rescaled: ' + tiersHit + '/27'
      + (derived.length ? ' \u00b7 ' + derived.length + ' derived from the tiered year\'s shape' : '')
      + (tiersMissed.length ? ' \u00b7 not priced in this market file: ' + tiersMissed.join(', ') : ''));
    if (!tiersHit) console.warn('[DELTA] NO pick tier matched the market file \u2014 every pick is showing the '
      + 'value baked into delta-engine.js. Check how picks are named in data/market-values.json.');

    // Anchor: player.k = default (12-SF) market — the base the model rescales from via scarcity()
    let updated = 0, notFound = [];
    for (const player of RAW) {
      if (!player || !player.n) continue;
      const match = valOf(anchorSlice, player.n);
      if (match) {
        player.k = match.value;
        player.fcRank = match.overallRank;
        player.mktStale = false;
        if (match.trend30Day !== undefined) player.fcTrend = match.trend30Day;
        if (match.team && match.team !== player.t) player.fcTeam = match.team;
        updated++;
      } else {
        player.kMkt = player.k;          // keep kMkt defined even if unmatched
        player.mktStale = true;          // not in latest FC fetch — baked value persisting
        notFound.push(player.n);
      }
    }

    console.log(`[DELTA] Live values loaded: ${updated} players updated, ${notFound.length} not matched` +
                (MARKET_SETTINGS ? ` · grid ${Object.keys(MARKET_SETTINGS).length} settings` : ' · legacy flat'));
    if (typeof showDataFreshness === 'function') showDataFreshness(data.fetched, updated, notFound.length);
    /* ALWAYS print the names. This used to be gated on `notFound.length < 20`, which
       suppressed the list at exactly 28 unmatched — so the one entry that mattered was
       invisible. Most unmatched names are legitimate (free agents outside FC's top ~475);
       the list is noise until you need it, and then it is the only place to look. */
    if (notFound.length) console.log('[DELTA] Unmatched players (' + notFound.length + '):', notFound.join(', '));

    /* SURNAME COLLISION DETECTOR — the whole point of the two lines above.
       An unmatched DELTA name whose surname DOES appear in the FC slice is almost
       always a spelling difference, not a genuine absence: DELTA said 'Kenneth
       Gainwell', FantasyCalc said 'Kenny Gainwell', the match failed silently, and he
       carried a baked value 76% above his real price into the freeze. A player FC has
       simply never heard of produces no collision, so this stays quiet in the normal
       case. Every hit here wants either an FC_ALIASES entry or a RAW rename. */
    if (notFound.length) {
      const parts = s => fcNorm(s).split(' ');
      const last  = s => parts(s).pop();
      const first = s => parts(s)[0] || '';
      /* Surname alone is far too loose — it flagged 'Elijah Higgins' against Tee Higgins
         and 'Ty Johnson' against six unrelated Johnsons. A detector that cries wolf gets
         ignored, which is the failure it exists to prevent. So also require the first
         names to be plausibly the same person: one a prefix of the other (Chig/Chigoziem,
         Sam/Samuel, Ken/Kenneth) or sharing three leading letters (Kenneth/Kenny).
         This deliberately will NOT catch a true nickname substitution like Mike/Michael
         or Bob/Robert — nothing short of a nickname table would. The full unmatched list
         printed above is the backstop for those; scan it when a name looks wrong. */
      const related = (a, b) => {
        const x = first(a), y = first(b);
        if (!x || !y) return false;
        if (x === y || x.startsWith(y) || y.startsWith(x)) return true;
        let i = 0; while (i < x.length && i < y.length && x[i] === y[i]) i++;
        return i >= 3;
      };
      const fcBySurname = {};
      for (const k of Object.keys(anchorSlice)) (fcBySurname[last(k)] = fcBySurname[last(k)] || []).push(k);
      const suspects = notFound
        .map(n => ({ n, cands: (fcBySurname[last(n)] || []).filter(c => related(n, c)) }))
        .filter(x => x.cands.length);
      if (suspects.length) {
        console.warn('[DELTA] ' + '!'.repeat(68));
        console.warn('[DELTA] !! POSSIBLE NAME MISMATCH — unmatched here, but FantasyCalc lists a near-identical name.');
        console.warn('[DELTA] !! These keep a BAKED market value and are excluded from the freeze ledger.');
        for (const s of suspects) console.warn(`[DELTA] !!   DELTA "${s.n}"  ←→  FC ${s.cands.map(c => '"' + c + '"').join(', ')}`);
        console.warn('[DELTA] !! Fix with an FC_ALIASES entry (DELTA name → FC name) or a RAW rename.');
        console.warn('[DELTA] ' + '!'.repeat(68));
      }
    }

    // Point kMkt at the currently-selected format and rebuild COMP/ASSETS/render.
    // (Legacy flat file → kMkt mirrors k, preserving prior behaviour.)
    if (!MARKET_SETTINGS) { RAW.forEach(p=>{ if(p) p.kMkt = p.k; }); }
    applyMarketForSetting();
    if (typeof renderRankings === 'function') renderRankings();
    if (typeof renderProj === 'function') renderProj();

  } catch (err) {
    // Show error in badge so we can debug
    console.warn('[DELTA] Could not load live market values:', err.message);
    dlNoteFail('market values');
    if (typeof showDataFreshness === 'function') showDataFreshness(new Date().toISOString(), -1);
  }
}

// ── FRESHNESS INDICATOR ───────────────────────────────────────────────────
/* Players whose built-in copy (DL_CONTRACTS_BACKUP) differs from the table: the copy is out of
   date. Shown on the ?dev=1 Engine Audit panel; the nightly fails on it too
   (scripts/build-contracts-backup.js --check). Feeds no number. */
let DL_CONTRACT_BACKUP_DIFF = [];
function dlContractsDiff(a, b){
  const key = (r) => r ? [r.team, r.end, r.kind, r.aav, r.total,
    r.option == null ? null : (typeof r.option === 'string' ? r.option : r.option.status)].join('|') : '';
  return [...new Set([...Object.keys(a || {}), ...Object.keys(b || {})])]
    .filter((n) => key(a[n]) !== key(b[n])).sort();
}
/* Contracts: DELTA's own table, data/delta-contracts.json (25 Oct 2026; see CONTRACTS). Replaces
   the OverTheCap feed and its hand corrections (the +1 rule, CONTRACT_OVERRIDES, CONTRACT_VOID):
   the table is built from the signing reports, so every end year in it is already the owner's.
   On any failure the built-in copy filled at load stays in use, and the load notice says so. */
async function loadPlayerContracts() {
  try {
    const res = await dlFetch('./data/delta-contracts.json',{cache:'no-cache'});
    if (!res.ok) { dlNoteFail('contracts'); return; }        // built-in copy stays
    const data = await res.json();
    const rows = data && data.players;
    // A short or empty table is a broken file, not a league with no contracts.
    if (!rows || Object.keys(rows).length < 350) { dlNoteFail('contracts'); return; }
    DL_CONTRACT_BACKUP_DIFF = dlContractsDiff(DL_CONTRACTS_BACKUP, rows);
    dlContractsApply(rows);
    DL_CONTRACTS_SOURCE = 'table';
    console.log(`[DELTA] Contracts: ${CONTRACTS.length} from DELTA's table` +
                (DL_CONTRACT_BACKUP_DIFF.length ? ` (built-in copy differs for ${DL_CONTRACT_BACKUP_DIFF.length})` : ''));
    COMP.length = 0;
    RAW.forEach(r => COMP.push(calcProj(r)));
    ASSETS.length = 0;
    ASSETS.push(...COMP, ...PICKS.filter(p => !p.hidden));
    if (typeof renderRankings === 'function') renderRankings();
  } catch(e) {
    dlNoteFail('contracts');
    console.warn('[DELTA] Could not load contracts; using the built-in copy:', e.message);
  }
}

// Ripple effects — single data-backed source for BOTH the projection multiplier
// (RP) and the displayed reasons (RIPPLE). Generated by the ripple pipeline and
// reviewed via PR before landing in data/ripple.json. Mirrors the other loaders:
// fetch → rebuild → recompute projections → re-render.
/* ── Injury state ─────────────────────────────────────────────────────────────
   TWO SEPARATE THINGS, deliberately not merged (docs/ACCURACY-LEDGER.md s.6):

     INJ_STATUS  — Sleeper injury_status, refreshed nightly. DISPLAY ONLY.
                   Never touches a projection. "IR" means out NOW, not out for
                   the season: NFL rules permit return from injured reserve and
                   designated-to-return is routine, so automating IR -> 0 would
                   print false zeros on players who come back.

     INJ_OUT     — hand-maintained season-enders from data/injury-overrides.json.
                   THIS is what zeroes a projection, and only this. */
/* Hand-maintained Week-1 starters. Same shape and same failure posture as the injury
   loader above: absent is normal, a bad file disables the rule rather than corrupting
   projections, and every name is logged so a typo is visible rather than silent. */
async function loadQBStarters() {
  try {
    const res = await dlFetch('./data/qb-starters.json');
    if (!res.ok) { QB_STARTERS = {}; return; }       // absent is normal — rule just won't fire
    const raw = await res.json();
    const out = {};
    for (const [name, e] of Object.entries(raw || {})) {
      if (name.startsWith('_') || !e || typeof e !== 'object') continue;
      if (!e.starter) continue;                      // only an explicit true acts
      out[name] = { team: e.team || null, since: e.since || null, note: e.note || '' };
    }
    QB_STARTERS = out;
    const n = Object.keys(out).length;
    if (n) console.log('[DELTA] Week-1 QB starters applied:', n, Object.keys(out).join(', '));
    if (RAW && RAW.length && typeof calcProj === 'function') {
      COMP.length = 0;
      RAW.forEach(r => COMP.push(calcProj(r)));
      ASSETS.length = 0;
      ASSETS.push(...COMP, ...PICKS.filter(p => !p.hidden));
      if (typeof renderRankings === 'function') renderRankings();
    }
  } catch (e) {
    dlNoteFail('QB starters');
    console.warn('[DELTA] Could not load QB starters (rule inactive):', e.message);
    QB_STARTERS = {};
  }
}

async function loadInjuryOverrides() {
  try {
    const res = await dlFetch('./data/injury-overrides.json');
    if (!res.ok) { INJ_OUT = {}; return; }          // absent is normal
    const raw = await res.json();
    const out = {};
    for (const [name, e] of Object.entries(raw || {})) {
      if (name.startsWith('_') || !e || typeof e !== 'object') continue;
      if (!e.out_for_season) continue;              // only season-enders act
      out[name] = { note: e.note || '', since: e.since || null };
    }
    INJ_OUT = out;
    const n = Object.keys(out).length;
    if (n) console.log('[DELTA] Season-ending injuries applied:', n, Object.keys(out).join(', '));
    if (RAW && RAW.length && typeof calcProj === 'function') {
      COMP.length = 0;
      RAW.forEach(r => COMP.push(calcProj(r)));
      ASSETS.length = 0;
      ASSETS.push(...COMP, ...PICKS.filter(p => !p.hidden));
      if (typeof renderRankings === 'function') renderRankings();
    }
  } catch (e) {
    dlNoteFail('injury overrides');
    console.warn('[DELTA] Could not load injury overrides (none applied):', e.message);
    INJ_OUT = {};
  }
}

async function loadRipples() {
  try {
    const res = await dlFetch('./data/ripple.json',{cache:'no-cache'});
    if (!res.ok) throw new Error('ripple '+res.status);
    const data = await res.json();
    const arr = Array.isArray(data) ? data : (data.ripples || []);
    RIPPLE = arr;                                  // display array
    RP = {};                                       // math multipliers, derived from the SAME entries
    for (const r of arr) {
      if (!r || !r.n || r.delta == null) continue;
      RP[r.n] = 1 + (parseFloat(r.delta) || 0) / 100;   // '+12%' -> 1.12, '-40%' -> 0.60
    }
    console.log('[DELTA] Ripples loaded:', arr.length, 'entries');
    if (RAW && RAW.length && typeof calcProj === 'function') {
      COMP.length = 0;
      RAW.forEach(r => COMP.push(calcProj(r)));
      ASSETS.length = 0;
      ASSETS.push(...COMP, ...PICKS.filter(p => !p.hidden));
      if (typeof renderRankings === 'function') renderRankings();
    }
  } catch(e) {
    dlNoteFail('ripple effects');
    console.warn('[DELTA] Could not load ripples (none applied):', e.message);
  }
}

// ════════════════════════════════════════════════════════════
// SCARCITY ENGINE AUDIT — external validation against FantasyCalc
// ------------------------------------------------------------------
// FantasyCalc is a YARDSTICK ONLY here: it NEVER enters any DELTA score or
// ranking. We compare DELTA's own scarcity(pos,teams,qb) — the single source of
// truth, computed LIVE below — against the market's observed value-by-rank,
// using the SAME replacement-level (VOR) formula and the SAME 12-team-SF anchor
// (= 1.00). The only thing differing between the two factors is the curve shape,
// which is exactly what we're validating. Judged by DIRECTION, not magnitude fit.
// Data baked offline by scripts/fetch-scarcity-validation.js (no live API calls).
// ════════════════════════════════════════════════════════════
// Engine Audit is an internal validation/regression tool, not a public feature.
// It is gated behind a ?dev flag: visit ...github.io/fantasy-delta/?dev=1 to use it.
// Public visitors never see the tab and never fetch its data.
const DELTA_DEV = new URLSearchParams(location.search).has('dev');
// Separate flag from ?dev on purpose: a college preview link handed to a league-mate
// must not also reveal the Engine Audit tab.
const DELTA_CFB = new URLSearchParams(location.search).has('college');

// ─────────────────────────────────────────────────────────────────────────────
// Shared player card HTML builders — used by both index.html (popup) and
// player.html (full page). Return HTML strings; touch no DOM directly.
// ─────────────────────────────────────────────────────────────────────────────

function contractStatus(c){
  if(c.end===SEASON_YEAR)return{label:'Walk Year',cls:'bd',icon:'⚠'};
  const yrsLeft=c.end-(SEASON_YEAR-1); // inclusive of the current season
  if(yrsLeft>=5)return{label:'Locked Up',cls:'bs',icon:'■'};
  if(yrsLeft<=2)return{label:'Expiring',cls:'bw',icon:'◷'};
  return{label:'Stable',cls:'bi',icon:'✓'};
}

function dynastySignal(c){
  if(c.end===SEASON_YEAR)return'<span style="color:var(--coral);font-size:10px">Sell before walk year · Contract leverage gone</span>';
  const yrsLeft=c.end-(SEASON_YEAR-1); // inclusive of the current season
  if(yrsLeft>=5&&c.aav>=20000000)return'<span style="color:var(--emerald);font-size:10px">Elite commitment — long-term hold</span>';
  if(yrsLeft>=3)return'<span style="color:var(--sky);font-size:10px">Stable — '+yrsLeft+' years of role security</span>';
  if(yrsLeft<=2)return'<span style="color:var(--topaz);font-size:10px">Contract leverage ends · '+yrsLeft+' yrs left</span>';
  return'<span style="color:var(--fog);font-size:10px">'+(c.note||'')+'</span>';
}

function buildDSBreakdownHTML(p){
  const ds=p.dsScore;
  if(ds==null) return '';
  const pos=p.pos||p.p||'WR';
  const noNFL=p.g25===0;
  const age=p.a||22;
  const aPts=dsAge(age,pos);
  // MUST mirror calcDynastyScore exactly, including the league-neutral prod and the
  // post-clip scarcity multiply. If that changes, change it here in the same commit
  // or the displayed bars stop summing to the displayed score.
  const scar=scarcity(pos, leagueTeams, qbFmt) || 1;
  const prodPts=dsProduction(p.ppg25||0,p.ppg24||0,p.ppg23||0,p.g25||0,pos,p,true);
  const oppPts=dsOpportunity(p);
  const conPts=dsCont(p);
  const col=dsColor(ds);
  // Scale to effective weighted values (mirrors calcDynastyScore)
  const mult=dsYouthMult(age);
  const aW=Math.round((aPts/25)*15*10)/10;
  const prodW=Math.round(Math.min(45,(prodPts/32)*45*mult)*scar*10)/10;
  const oppW=Math.round((oppPts/33)*30*10)/10;
  const hasNFLProd=(p.ppg25||0)>0||(p.ppg24||0)>0||(p.ppg23||0)>0;
  const multLbl=(mult>1.00 && hasNFLProd)?' ×'+mult.toFixed(2):'';
  const multTipContent=(mult>1.00 && hasNFLProd)
    ?'Earlier production is a stronger dynasty signal — the same output at age '+Math.floor(age)+' predicts more value over the 2–3yr window than at 30+.'
     +'<br><span style="color:var(--fog-2)">≤24: ×1.25 &nbsp;·&nbsp; ≤26: ×1.12 &nbsp;·&nbsp; ≤28: ×1.04 &nbsp;·&nbsp; 28+: no adjustment</span>'
    :'';
  // Each axis gets its own color based on that axis's individual score ratio
  const axisClr=(val,max)=>{const r=val/max;return r>=0.8?'var(--emerald)':r>=0.6?'var(--sky)':r>=0.4?'var(--topaz)':'var(--coral)';};
  const bar=(label,val,max,tip)=>{
    const pct=Math.round((val/max)*100);
    const c=axisClr(val,max);
    // ⓘ button navigates: span → label span → header div → bar container → last child (tooltip)
    const iBtn=tip
      ?' <span onclick="var t=this.parentNode.parentNode.parentNode.lastElementChild;t.style.display=t.style.display===\'block\'?\'none\':\'block\'" '
       +'style="cursor:pointer;color:var(--fog-2);font-size:8px;border:1px solid var(--line);border-radius:50%;padding:0 2.5px;vertical-align:middle;line-height:1.4">ⓘ</span>'
      :'';
    return'<div style="margin-bottom:6px">'
      +'<div style="display:flex;justify-content:space-between;font-size:9px;color:var(--fog);margin-bottom:2px">'
      +'<span>'+label+iBtn+'</span><span style="color:'+c+';font-weight:600">'+val+'/'+max+'</span></div>'
      +'<div style="height:5px;background:var(--panel);border-radius:3px;overflow:hidden">'
      +'<div style="height:100%;width:'+pct+'%;background:'+c+';border-radius:3px"></div></div>'
      +(tip?'<div style="display:none;font-size:9px;color:var(--fog);margin-top:4px;padding:5px 7px;background:var(--ink);border-radius:4px;border:1px solid var(--line);line-height:1.5">'+tip+'</div>':'')
      +'</div>';
  };
  return'<div class="dd-section" style="background:linear-gradient(135deg,var(--ink-2),var(--ink-2));border:1px solid var(--line);border-radius:10px;padding:14px;margin-bottom:10px">'
    +'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">'
    +'<div style="display:flex;align-items:baseline;gap:7px">'
    +'<span style="font-family:Georgia,serif;font-size:20px;color:'+col+'">Δ</span>'
    +'<span style="font-size:13px;font-weight:600;color:var(--paper);letter-spacing:.02em">DELTA Score</span>'
    +(noNFL?'<span style="font-size:9px;color:var(--fog);margin-left:2px">rookie · capped</span>':'')
    +'</div>'
    /* The big number moved to the Score ring at the top of the card (owner, 25 Oct 2026). */
    +'</div>'
    +'<div style="font-size:9px;color:var(--fog-2);margin-bottom:8px;letter-spacing:.04em">PROVEN VALUE · demonstrated production, age &amp; draft capital — no speculation</div>'
    +bar('Age',aW,15)+bar('Production'+multLbl,prodW,45,multTipContent)+bar('Opportunity',oppW,30)+bar('Contract',conPts,10)
    +'</div>';
}

// ── SCHEME / SYSTEM CONTEXT ─────────────────────────────────────────────────
// Shared explainer for the Offensive System Score: what the number means, the
// exact projection impact (mirrors calcProj's d_sys/d_oc tables, incl. the
// proven-producer softening), and OC-change context. Single source for the
// popup and the full player card so the two can never disagree.
function isNFLRookie(p){
  // no NFL production yet (seeded rookie projection) or drafted this cycle
  const d=(typeof DRAFT_PICKS!=='undefined')&&DRAFT_PICKS[p.n];
  return ((p.g25||0)===0&&(p.ppg25||0)>0)||(d&&d.y===2026);
}
// First-round rookie deals carry a team-option 5th year. We display guaranteed
// years as-is (the option isn't exercised until it is), but surface that it
// exists so a Bowers doesn't read as "2 years and done".
/* Fifth-year option still to be decided (owner, 25 Oct 2026): read from the contracts table, not
   guessed from the draft round, so an option already declined or picked up never shows. No date:
   teams can decide any time in the window. A picked-up option is already in the end year. */
function fifthYearNote(p,ct){
  return ct&&ct.opt==='available'?'Fifth-Year Option Available':'';
}
function explainSystem(p){
  if(p.sys==null) return null;
  const pos=p.pos||p.p||'WR', isQB=pos==='QB';
  if(isNFLRookie(p)){
    // A rookie has no prior scheme — there is nothing for a coordinator change
    // to disrupt, so no continuity penalty exists or is shown.
    const tier=p.sys>=70?'a strong offensive environment':p.sys>=55?'a league-average environment'
              :p.sys>=40?'a below-average environment':'a poor offensive environment';
    const dS=isQB?(p.sys>=70?.01:p.sys>=55?0:p.sys>=40?-.03:-.07)
                 :(p.sys>=70?.04:p.sys>=55?.01:p.sys>=40?-.04:-.10);
    const styR=styleFactors(p.n,pos,p.t);
    return {sys:p.sys,tier,proven:false,softened:false,dSys:dS,dOc:0,net:dS+styR.total,och:false,oc:'',rookie:true,style:styR};
  }
  const e={s:p.sys, c:(gs(p.t)||{}).c ?? 0.95};
  const provenThreshold = pos==='WR'?13.0:pos==='TE'?12.0:pos==='RB'?15.0:22.0;
  const provenPPG25 = pos==='WR'?15.0:pos==='TE'?13.0:pos==='RB'?16.0:24.0;
  const proven = (p.base||0)>=provenThreshold || (p.ppg25||0)>=provenPPG25;
  const adjCont = proven && e.c<0.70 ? e.c+(0.70-e.c)*0.60 : e.c;
  const adjSys  = proven && e.s<55 ? Math.min(e.s+10,55) : e.s;
  const dSys=isQB?(adjSys>=70?.01:adjSys>=55?0:adjSys>=40?-.03:-.07)
                 :(adjSys>=70?.04:adjSys>=55?.01:adjSys>=40?-.04:-.10);
  const ocFranchise=typeof COMP_EXEMPT!=='undefined'&&COMP_EXEMPT.has(p.n);
  const dOc=isQB?(adjCont>=.95?.01:adjCont>=.70?0:adjCont>=.50?-.04:adjCont>=.30?-.07:-.11)
      :pos==='RB'?(adjCont>=.95?.01:adjCont>=.70?.01:adjCont>=.50?-.02:adjCont>=.30?-.03:-.05)
      :ocFranchise?(adjCont>=.95?.03:adjCont>=.70?.01:adjCont>=.50?-.02:adjCont>=.30?-.04:-.06)
                  :(adjCont>=.95?.03:adjCont>=.70?.01:adjCont>=.50?-.04:adjCont>=.30?-.08:-.12);
  const tier=p.sys>=70?'a strong offensive environment':p.sys>=55?'a league-average environment'
            :p.sys>=40?'a below-average environment':'a poor offensive environment';
  const sty=styleFactors(p.n,pos,p.t);
  return {sys:p.sys,tier,proven,softened:proven&&(e.s<55||e.c<0.70),dSys,dOc,net:dSys+dOc+sty.total,och:!!p.och,oc:p.oc||'',style:sty};
}
function buildSchemeHTML(p){
  // PLAYCALLER TENDENCIES — descriptive only, NO projection values.
  // Reads the CURRENT (2026) playcaller's own 4-year charted fingerprint, following him
  // across teams. First-time playcallers have no charted history -> honest blank, because
  // an unproven coordinator has no established tendencies to show.
  var team = p.t || p.team;
  var fp = (typeof PC_FINGERPRINT!=='undefined') ? PC_FINGERPRINT[team] : null;
  if(!fp){
    var oc0 = (typeof SYS!=='undefined' && SYS[team]) ? SYS[team].oc : '';
    var vet = (typeof VET_NO_FTN!=='undefined') ? VET_NO_FTN[team] : null;
    var msg;
    if(vet){
      msg = '<b>'+vet+'</b> last called plays before our charting data begins (2022), so there\'s no '
          + 'recent book to profile. Tendencies will populate once the offense has games on tape under him.';
    } else {
      msg = (oc0?'<b>'+oc0+'</b> is':'The playcaller is')
          + ' calling plays for the first time — no established book yet. '
          + 'Tendencies will populate once the offense has games on tape.';
    }
    return '<div>'
      +'<div style="font-size:11px;color:var(--paper);font-weight:700;margin-bottom:4px">Playcaller Tendencies</div>'
      +'<div style="font-size:10px;color:var(--fog);line-height:1.5">'+msg+'</div></div>';
  }
  var d = fp.d, coach = fp.pc, color = 'var(--teal-br)';

  // ---- radar: 6 axes ----
  var AX = [['Motion','moti'],['Play-action','pa_p'],['PROE','proe'],
            ['12-pers','te2'],['Two-back','two_'],['Pace','play']];
  var n = AX.length, cx = 150, cy = 158, R = 92;
  function xy(i, r){ var a = -Math.PI/2 + 2*Math.PI*i/n; return [cx + r*Math.cos(a), cy + r*Math.sin(a)]; }
  var rings = '', spokes = '', poly = '', dots = '', labels = '';
  [33,66,100].forEach(function(g){ rings += '<circle cx="'+cx+'" cy="'+cy+'" r="'+(R*g/100)+'" fill="none" style="stroke:var(--line)"/>'; });
  var pts = [];
  for(var i=0;i<n;i++){
    var lab = AX[i][0], cell = d[AX[i][1]], pc = cell?cell.p:0;
    var e = xy(i, R); spokes += '<line x1="'+cx+'" y1="'+cy+'" x2="'+e[0].toFixed(0)+'" y2="'+e[1].toFixed(0)+'" style="stroke:var(--line)"/>';
    var v = xy(i, R*pc/100); pts.push(v[0].toFixed(1)+','+v[1].toFixed(1));
    dots += '<circle cx="'+v[0].toFixed(1)+'" cy="'+v[1].toFixed(1)+'" r="2.5" style="fill:'+color+'"/>';
    var gap = (i===0)?24:15, lp = xy(i, R+gap);
    var anc = Math.abs(lp[0]-cx)<15?'middle':(lp[0]>cx?'start':'end');
    labels += '<text x="'+lp[0].toFixed(0)+'" y="'+lp[1].toFixed(0)+'" font-size="9" text-anchor="'+anc+'" style="fill:var(--fog);font-family:var(--sans,sans-serif)">'+lab+'</text>';
  }
  poly = '<polygon points="'+pts.join(' ')+'" fill-opacity="0.18" stroke-width="2" style="fill:'+color+';stroke:'+color+'"/>';
  var radar = '<svg viewBox="0 0 300 300" style="width:100%;max-width:300px;display:block;margin:0 auto">'
    +'<text x="150" y="18" font-size="12.5" font-weight="700" text-anchor="middle" style="fill:var(--paper);font-family:var(--sans,sans-serif)">Playcaller Tendencies</text>'
    +'<text x="150" y="33" font-size="10.5" font-weight="600" text-anchor="middle" style="fill:'+color+';font-family:var(--sans,sans-serif)">'+coach+'</text>'
    +rings+spokes+poly+dots+labels+'</svg>';

  // ---- bars: all 8 ----
  var BARS = [
    ['Pre-snap motion','moti','How often a man is moving at the snap — used to read coverage and create leverage'],
    ['Play-action','pa_p','Share of dropbacks with a fake handoff to freeze the defense'],
    ['Pass rate over expected (PROE)','proe','Positive = passes more than a typical team would in the same spots'],
    ['12-personnel (2-TE)','te2','How often two tight ends are on the field — heavier looks that squeeze the WR3'],
    ['Two-back sets','two_','How often two running backs share the field — a run-game / play-action tell'],
    ['Pace (plays/game)','play','Total offensive snaps per game — higher = faster, more volume for everyone'],
    ['11-personnel pass lean','pass','Overall pass rate — how pass-heavy the offense is'],
    ['Air yards (aDOT)','adot','Average depth of target — how far downfield the ball travels on throws']
  ];
  function bar(label, cell, hint){
    if(!cell) return '';
    var pc = cell.p, v = cell.v, clr = pc>=67?'var(--teal-br)':pc>=34?'var(--sky)':'var(--fog-2)';
    var tier = pc>=80?'elite':pc>=60?'high':pc>=40?'average':pc>=20?'low':'rare';
    return '<div style="margin:8px 0">'
      +'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:3px">'
      +'<span style="font-size:10px;color:var(--fog)">'+label+'</span>'
      +'<span style="font-size:10px;color:'+clr+';font-family:var(--mono,monospace);font-weight:600">'+v+'<span style="color:var(--fog-2);font-weight:400"> · '+tier+'</span></span></div>'
      +'<div style="height:4px;border-radius:3px;background:var(--line)"><div style="height:100%;width:'+pc+'%;background:'+clr+';border-radius:3px"></div></div>'
      +(hint?'<div style="font-size:8.5px;color:var(--fog-2);margin-top:2px">'+hint+'</div>':'')+'</div>';
  }
  var bars = BARS.map(function(b){ return bar(b[0], d[b[1]], b[2]); }).join('');

  return '<div>'+radar
    +'<div style="margin-top:6px">'+bars+'</div>'
    +'<div style="font-size:8.5px;color:var(--fog-2);text-align:center;margin-top:8px">'
    + fp.yrs + '-year fingerprint · ' + coach + ' · ranked vs league · descriptive, not a projection input</div>'
    +'</div>';
}
// receptions/game with a game-log fallback so RBs outside the pipeline's
// coverage still get a format-sensitivity readout
function recPgOf(p){
  const r=REC_PG[p.n]||0; if(r>0) return r;
  const arr=(typeof GAMELOGS!=='undefined')&&GAMELOGS&&GAMELOGS[p.n];
  if(!Array.isArray(arr)||!arr.length) return 0;
  const latest=Math.max(...arr.map(g=>g.s||0));
  const gs=arr.filter(g=>g&&g.s===latest&&g.rec!=null);
  if(gs.length>=6) return gs.reduce((s,g)=>s+(g.rec||0),0)/gs.length;
  return 0;
}

function buildReadHTML(p){
  // Numbers only since 3 Oct 2026 (owner). The authored paragraph (reads.json, retired 8 Oct; written
  // July) and the rotating template sentences are gone: the first went stale by Week 1, the
  // second read machine-written and added advice the model never computed. What remains is
  // the call, one line stating the gap the call is read from, and the three rank bars.
  // The gap uses verdictRatio() — the tag's own basis — so the line cannot contradict it.
  const mvv=mvAsset(p), mk=p.ktcEff||0, ds=p.dsScore;
  if(!mk||ds==null) return '';
  const verdict=(vTag(p).match(/>([a-z ]+)</)||[,''])[1];
  const pos=p.pos||p.p||'';
  const peers=COMP.filter(x=>(x.pos||x.p)===pos);
  const rankMv=peers.slice().sort((a,b)=>mvAsset(b)-mvAsset(a)).findIndex(x=>x.n===p.n)+1;
  const rankDs=peers.slice().sort((a,b)=>b.dsScore-a.dsScore).findIndex(x=>x.n===p.n)+1;
  const rankMk=peers.slice().sort((a,b)=>(b.ktcEff||0)-(a.ktcEff||0)).findIndex(x=>x.n===p.n)+1;
  const proof=ds>=72?'elite':ds>=62?'strong':ds>=52?'solid':ds>=42?'middling':'thin';
  const proofClr=ds>=72?'var(--emerald)':ds>=62?'var(--emerald)':ds>=52?'var(--sky)':ds>=42?'var(--topaz)':'var(--coral)';
  let read,clr;
  if(dlRookieHold(p)){
    read='Rookie Hold \u00b7 No Season On Record Yet';
    clr='var(--fog)';
  } else {
    const pct=Math.round((verdictRatio(p)-1)*100);
    read=pct===0?'Model Value Level With Market Price'
      :'Model Value '+Math.abs(pct)+'% '+(pct>0?'Above':'Below')+' Market Price';
    clr=/buy/.test(verdict)?'var(--emerald)':/sell/.test(verdict)?'var(--coral)':'var(--paper)';
  }
  const N=peers.length||1;
  const barFor=(rank,c,lbl,sub)=>{
    const w=Math.max(4,Math.round((1-(rank-1)/N)*100));
    return'<div style="margin-bottom:5px">'
      +'<div style="display:flex;justify-content:space-between;font-size:9px;margin-bottom:2px">'
      +'<span style="color:var(--fog)">'+lbl+'</span>'
      +'<span style="color:'+c+';font-weight:700">'+pos+rank+'<span style="color:var(--fog-2);font-weight:400"> · '+sub+'</span></span></div>'
      +'<div style="height:5px;background:var(--panel);border-radius:3px;overflow:hidden">'
      +'<div style="height:100%;width:'+w+'%;background:'+c+';border-radius:3px"></div></div></div>';
  };
  return'<div class="dd-section" style="border:1px solid var(--line);border-radius:10px;padding:13px 15px;margin-bottom:10px;background:linear-gradient(135deg,var(--ink-2),var(--ink-2))">'
    +'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'
    +'<span class="dd-section-label" style="margin-bottom:0">The Read</span>'
    +'<span style="font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.05em;color:'+clr+'">'+verdict+'</span></div>'
    +'<div style="font-size:12px;color:var(--paper);line-height:1.55;margin-bottom:11px">'+read+'</div>'
    +barFor(rankDs,proofClr,'DELTA SCORE (Δ'+ds+')',proof)
    +barFor(rankMv,'var(--violet)','MODEL VALUE',(mvv>=19999?'19,999+':mvv.toLocaleString()))
    +barFor(rankMk,'var(--sky)','MARKET PRICE',mk.toLocaleString())
    +'</div>';
}

/* ── SHARE IMAGES: shared drawing kit (23 Oct 2026) ──────────────────────────────
   Used by the Trade Calc, Compare (index.html) and the player page (player.html). Browser
   only, and only on a tap: nothing here runs at load, so the Node tools that load this
   file never touch it. Colours are read from :root at draw time (zero hex here); the
   brand mark is the page's own SVG, drawn as an image. Photos are deliberately left out:
   headshots come from other sites, and drawing one would block the picture from saving. */
function dlImgTok(n){ return getComputedStyle(document.documentElement).getPropertyValue('--'+n).trim(); }
function dlImgColors(){
  const t=dlImgTok;
  return {ink:t('ink'),panel:t('panel'),line:t('line'),paper:t('paper'),fog:t('fog'),fog2:t('fog-2'),url:t('cp-1'),
    emerald:t('emerald'),coral:t('coral'),sky:t('sky'),violet:t('violet'),topaz:t('topaz'),lead:t('cp-lead'),leadBd:t('cp-lead-bd')};
}
function dlImgFonts(){ return {sans:dlImgTok('sans'),mono:dlImgTok('mono'),geo:dlImgTok('geo')}; }
function dlImgFit(g,t,max){ t=String(t); if(g.measureText(t).width<=max) return t;
  while(t.length>1&&g.measureText(t+'…').width>max) t=t.slice(0,-1); return t+'…'; }
function dlImgRound(g,x,y,w,h,r){ g.beginPath(); g.moveTo(x+r,y); g.arcTo(x+w,y,x+w,y+h,r); g.arcTo(x+w,y+h,x,y+h,r); g.arcTo(x,y+h,x,y,r); g.arcTo(x,y,x+w,y,r); g.closePath(); }
function dlImgSpace(g,px){ if('letterSpacing' in g) g.letterSpacing=px+'px'; }
function dlImgDate(d){ return d.getDate()+' '+['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][d.getMonth()]+' '+d.getFullYear(); }
function dlImgFmtLine(){
  const f={half_tep:'Half PPR + TE Premium',half:'Half PPR',std:'Standard',full:'Full PPR',full_tep:'Full PPR + TE Premium'}[scoringFmt]||scoringFmt;
  return leagueTeams+'-Team '+(qbFmt==='sf'?'Superflex':'1QB')+' · '+f;
}
/* The solid brand mark from whichever page this is (index: svg.dl-mark; player page: the
   nav logo). Its gradient is fixed by BRAND.md, so drawing the page's own copy is exact. */
function dlImgMark(){
  const svg=[...document.querySelectorAll('svg[viewBox="0 0 128 128"]')].find(s=>s.querySelector('linearGradient')&&s.querySelector('path[fill^="url("]'));
  if(!svg) return Promise.resolve(null);
  // Comments go: player.html's mark carries one mentioning "--teal-br", and a double dash
  // inside a comment is invalid XML, so the image silently failed to load.
  let s=new XMLSerializer().serializeToString(svg).replace(/<!--[\s\S]*?-->/g,'');
  s=s.replace(/^<svg[^>]*>/,'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">');
  return new Promise(r=>{ const im=new Image(); im.onload=()=>r(im); im.onerror=()=>r(null);
    im.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(s); });
}
/* Canvas of width W painted ink, with the DELTA header drawn. Returns the y below it.
   sub replaces the 'Valued <today>' line (the Mock Draft names its board date instead). */
async function dlImgStart(g,W,P,C,F,kind,sub){
  try{ await document.fonts.ready; }catch(e){}
  g.fillStyle=C.ink; g.fillRect(0,0,W,g.canvas.height); g.textBaseline='middle';
  const mark=await dlImgMark(); if(mark) g.drawImage(mark,P-6,P-6,84,84);
  g.textAlign='left'; g.fillStyle=C.paper; g.font='700 40px '+F.geo; dlImgSpace(g,9); g.fillText('DELTA',P+92,P+36); dlImgSpace(g,0);
  g.textAlign='right'; g.fillStyle=C.fog; g.font='700 24px '+F.mono; dlImgSpace(g,3); g.fillText(kind,W-P,P+22); dlImgSpace(g,0);
  g.fillStyle=C.fog2; g.font='500 22px '+F.mono; g.fillText(sub||('Valued '+dlImgDate(new Date())),W-P,P+56);
  return P+96;
}
function dlImgFooter(g,W,P,C,F,y){
  g.fillStyle=C.line; g.fillRect(P,y,W-2*P,2);
  g.textAlign='left'; g.fillStyle=C.fog2; g.font='600 22px '+F.sans; g.fillText(dlImgFmtLine(),P,y+44);
  g.textAlign='right'; g.fillStyle=C.url; g.font='700 24px '+F.sans; g.fillText('fantasydelta.com',W-P,y+44);
}
const DL_IMG_FOOT=90;
/* The call as plain words + its signal colour, read from vTag so it can never differ. */
function dlImgCall(p,C){
  const hold=typeof dlRookieHold==='function'&&dlRookieHold(p);
  const m=(vTag(p)||'').match(/>([a-z ]+)<\/span>/); const t=hold?'rookie hold':(m?m[1]:'');
  const col=/buy/.test(t)?C.emerald:/sell/.test(t)?C.coral:C.fog;
  return {t:t.replace(/\b[a-z]/g,c=>c.toUpperCase()),col};
}
function dlImgColorOf(v,C){ // a token string like 'var(--sky)' → colour
  const m=String(v).match(/var\(--([a-z0-9-]+)\)/); return m?dlImgTok(m[1]):v;
}
/* Phone: share sheet with the picture alone. Computer: download it. */
async function dlImgShare(cvPromise,fileName,btn){
  const label=btn?btn.textContent:'';
  const say=(t)=>{ if(btn){ btn.textContent=t; setTimeout(()=>{btn.textContent=label;},2200); } };
  if(btn){ btn.disabled=true; btn.textContent='Making Image…'; }
  try{
    const cv=await cvPromise();
    const blob=await new Promise(r=>cv.toBlob(r,'image/png'));
    if(!blob) throw new Error('no image');
    const file=new File([blob],fileName,{type:'image/png'});
    if(btn){ btn.disabled=false; btn.textContent=label; }
    if(navigator.canShare&&navigator.canShare({files:[file]})){
      try{ await navigator.share({files:[file]}); }catch(e){}
      return;
    }
    const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=fileName;
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(()=>URL.revokeObjectURL(a.href),4000);
    say('Image Saved');
  }catch(e){ if(btn) btn.disabled=false; say('Couldn’t Make Image'); }
}
/* The four DELTA Score parts, same arithmetic as buildDSBreakdownHTML (the card's bars). */
function dlScoreParts(p){
  const pos=p.pos||p.p||'WR', age=p.a||22;
  const scar=scarcity(pos,leagueTeams,qbFmt)||1, mult=dsYouthMult(age);
  return {prod:Math.min(45,(dsProduction(p.ppg25||0,p.ppg24||0,p.ppg23||0,p.g25||0,pos,p,true)/32)*45*mult)*scar,
    opp:(dsOpportunity(p)/33)*30, age:(dsAge(age,pos)/25)*15, con:dsCont(p)};
}
function dlPosRank(p){
  const pos=p.pos||p.p; const list=COMP.filter(x=>(x.pos||x.p)===pos).sort((a,b)=>(b.dsScore||0)-(a.dsScore||0));
  const i=list.indexOf(p); return i<0?null:i+1;
}
/* Start Profile bar: miss / hit / elite. The last segment runs to the end of the bar, because
   the three rounded percentages can add up to 99 and leave a sliver of track showing. */
function dlImgStartBar(g,x,y,w,h,s,C){
  g.save(); dlImgRound(g,x,y,w,h,h/2); g.clip();
  g.fillStyle=C.line; g.fillRect(x,y,w,h);
  const segs=[[s.missPct,C.coral],[s.hitOnlyPct,C.sky],[s.elitePct,C.emerald]].filter(z=>z[0]>0);
  let cx=x; segs.forEach(([pc,c],i)=>{ const sw=i===segs.length-1?x+w-cx:w*pc/100; g.fillStyle=c; g.fillRect(cx,y,sw,h); cx+=sw; });
  g.restore();
}
/* Link-preview picture: 1200 x 630, the shape chat apps show for a pasted link. Only things
   that rarely change in-season (Score, rank, call, Score parts; no prices, no date), so a
   preview stays true for weeks and crawlers' caches do little harm. */
async function dlImgPlayerOG(p){
  const C=dlImgColors(), F=dlImgFonts(), W=1200, H=630, P=60;
  const cv=document.createElement('canvas'); cv.width=W; cv.height=H; const g=cv.getContext('2d');
  try{ await document.fonts.ready; }catch(e){}
  g.fillStyle=C.ink; g.fillRect(0,0,W,H); g.textBaseline='middle';
  const pos=p.pos||p.p, call=dlImgCall(p,C), rk=dlPosRank(p), parts=dlScoreParts(p);
  // header
  const mark=await dlImgMark(); if(mark) g.drawImage(mark,P-4,P-10,64,64);
  g.textAlign='left'; g.fillStyle=C.paper; g.font='700 30px '+F.geo; dlImgSpace(g,7); g.fillText('DELTA',P+70,P+22); dlImgSpace(g,0);
  g.textAlign='right'; g.fillStyle=C.url; g.font='700 24px '+F.sans; g.fillText('fantasydelta.com',W-P,P+22);
  // name block
  g.textAlign='left'; g.fillStyle=C.paper; g.font='800 64px '+F.sans; g.fillText(dlImgFit(g,p.n,W-2*P),P,P+122);
  g.fillStyle=C.fog; g.font='600 28px '+F.sans;
  g.fillText([pos,p.t&&p.t!=='FA'?p.t:'Free agent','Age '+Math.floor(p.a||0)].join(' · '),P,P+178);
  // left panel: score
  const py=P+222, ph=H-py-P, lw=440;
  dlImgRound(g,P,py,lw,ph,22); g.fillStyle=C.panel; g.fill(); g.strokeStyle=C.line; g.lineWidth=2; g.stroke();
  // number + label in the top part, call | rank in a strip along the bottom
  const cx=P+lw/2, stripY=py+ph-104;
  g.textAlign='center'; g.fillStyle=dlImgColorOf(dsColor(p.dsScore),C); g.font='800 120px '+F.mono;
  g.fillText(p.dsScore!=null?p.dsScore:'\u2014',cx,py+(stripY-py)/2-10);
  g.fillStyle=C.fog2; g.font='700 17px '+F.sans; dlImgSpace(g,3); g.fillText('DELTA SCORE',cx,stripY-20); dlImgSpace(g,0);
  g.fillStyle=C.line; g.fillRect(P+24,stripY,lw-48,2); g.fillRect(cx-1,stripY+18,2,68);
  const fitSize=(t,max,start,min,wt,fam)=>{ let s=start; for(;s>min;s-=2){ g.font=wt+' '+s+'px '+fam; if(g.measureText(t).width<=max) break; } return s; };
  const half=lw/2-28;
  fitSize(call.t||'\u2014',half,34,18,'800',F.sans); g.fillStyle=call.col; g.fillText(call.t||'\u2014',P+lw/4,stripY+44);
  g.fillStyle=C.fog2; g.font='700 15px '+F.sans; dlImgSpace(g,2); g.fillText('CALL',P+lw/4,stripY+80); dlImgSpace(g,0);
  g.fillStyle=C.paper; g.font='700 32px '+F.mono; g.fillText(rk?pos+rk:'\u2014',P+lw*3/4,stripY+44);
  g.fillStyle=C.fog2; g.font='700 15px '+F.sans; dlImgSpace(g,2); g.fillText('AT POSITION',P+lw*3/4,stripY+80); dlImgSpace(g,0);
  // right: parts
  const rx=P+lw+48, rw=W-P-rx; let y=py+6;
  [['prod','Production',45],['opp','Opportunity',30],['age','Age',15],['con','Contract',10]].forEach(([k,lab,max])=>{
    const v=parts[k];
    g.textAlign='left'; g.fillStyle=C.fog; g.font='700 24px '+F.sans; g.fillText(lab,rx,y+16);
    g.textAlign='right'; g.fillStyle=C.paper; g.font='700 24px '+F.mono; g.fillText((k==='con'?Math.round(v):v.toFixed(1))+' / '+max,rx+rw,y+16);
    dlImgRound(g,rx,y+38,rw,14,7); g.fillStyle=C.line; g.fill();
    const fw=Math.max(0,Math.min(1,v/max))*rw; if(fw>0){ dlImgRound(g,rx,y+38,Math.max(fw,14),14,7); g.fillStyle=C.url; g.fill(); }
    y+=(ph-12)/4;
  });
  return cv;
}
