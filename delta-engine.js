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
// Data is lazy-loaded on first player-card open (~1.1MB), not on startup.
// ════════════════════════════════════════════════════════════
let GAMELOGS=null, STARTLINES=null, GAMELOGS_MAX=null, START_DATA_STATE='idle';
async function ensureStartData(){
  if(START_DATA_STATE==='loaded'||START_DATA_STATE==='loading') return START_DATA_STATE;
  START_DATA_STATE='loading';
  try{
    const [gl,th]=await Promise.all([
      fetch('./data/game-logs.json?t='+Date.now()).then(r=>r.ok?r.json():Promise.reject('logs '+r.status)),
      fetch('./data/start-profile-thresholds.json?t='+Date.now()).then(r=>r.ok?r.json():Promise.reject('thresh '+r.status)),
    ]);
    GAMELOGS=gl.games||{}; STARTLINES=th.lines||{};
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
      let synced=0;
      for(const p of RAW){
        const logs=GAMELOGS[p.n];
        if(!logs||!logs.length) continue;
        const wk=new Set();
        for(const g of logs){ if(g.s===2025) wk.add(g.w); }
        if(wk.size>0&&p.g25!==wk.size){ p.g25=wk.size; synced++; }
      }
      if(synced) console.log('[DELTA] g25 synced from game logs for '+synced+' players');
    }
  }catch(e){ console.warn('[DELTA] Start Profile data load failed:',e); START_DATA_STATE='error'; }
  return START_DATA_STATE;
}
function gamefp(g,pos,fmt){
  const baseRec = pos==='TE'?1.0 : (pos==='QB'?0:0.5);          // half_tep base per rec: 0.5 PPR + 0.5 TE premium
  const recAbs = baseRec + (pos==='QB'?0:fmtRecPts(pos,fmt));
  return g.py*0.04 + g.pt*4 + g.pi*-2 + g.ry*0.1 + g.rt*6
       + g.rec*recAbs + g.rey*0.1 + g.ret*6 + g.fl*-2 + g.tp*2 + g.rtd*6;
}
function computeStartProfile(name,pos){
  if(!GAMELOGS||!STARTLINES||!GAMELOGS[name]) return null;
  const line=STARTLINES[pos+'|'+scoringFmt];   // league-invariant: game quality depends on position + scoring only
  if(!line) return null;
  const [hit,elite]=line, minS=GAMELOGS_MAX-1;
  const games=GAMELOGS[name].filter(g=>g.s>=minS);
  if(!games.length) return null;
  let m=0,ho=0,e=0;
  for(const g of games){ const fp=gamefp(g,pos,scoringFmt); if(fp>=elite)e++; else if(fp>=hit)ho++; else m++; }
  const n=games.length;
  return {n, miss:m, hitOnly:ho, elite:e,
          missPct:Math.round(100*m/n), hitOnlyPct:Math.round(100*ho/n), elitePct:Math.round(100*e/n),
          hitPct:Math.round(100*(ho+e)/n),   // cumulative: a Hit includes Elite (Serviceable and up)
          lo:minS, hi:GAMELOGS_MAX, hitLine:hit, eliteLine:elite};
}
function glOf(p){
  if(!p) return null;
  const sp=computeStartProfile(p.n, p.pos||p.p||'WR');
  return sp ? {miss:sp.missPct, hit:sp.hitPct, elite:sp.elitePct, g:sp.n} : null;
}
function startProfileHTML(p){
  const pos=p.pos||p.p||'WR';
  const sp=computeStartProfile(p.n,pos);
  if(!sp) return '<div class="dd-section"><div class="dd-section-label">Start Profile</div>'
    +'<div style="font-size:11px;color:#718096">No recent game data for this player/format.</div></div>';
  const seg=(pct,col)=> pct>0?'<div style="width:'+pct+'%;background:'+col+'"></div>':'';
  const cell=(lbl,pct,cnt,col)=>'<div style="text-align:center;flex:1">'
    +'<div style="font-size:18px;font-weight:800;color:'+col+';line-height:1">'+pct+'%</div>'
    +'<div style="font-size:9px;color:#718096;letter-spacing:.05em;margin-top:2px">'+lbl+'</div>'
    +'<div style="font-size:9px;color:#4a5568">'+cnt+' g</div></div>';
  return '<div class="dd-section"><div class="dd-section-label">Start Profile</div>'
    +'<div style="display:flex;height:8px;border-radius:4px;overflow:hidden;background:#1a202c;margin-bottom:9px">'
    + seg(sp.missPct,'#fc8181')+seg(sp.hitOnlyPct,'#93c5fd')+seg(sp.elitePct,'#6ee7b7')+'</div>'
    +'<div style="display:flex;gap:4px">'
    + cell('MISS',sp.missPct,sp.miss,'#fc8181')+cell('HIT',sp.hitPct,sp.hitOnly+sp.elite,'#93c5fd')+cell('ELITE',sp.elitePct,sp.elite,'#6ee7b7')
    +'</div>'
    +'<div style="font-size:9px;color:#4a5568;text-align:center;margin-top:8px">'
    + sp.n+' starts · '+sp.lo+'\u2013'+String(sp.hi).slice(2)+' · hit \u2265'+sp.hitLine+' · elite \u2265'+sp.eliteLine+' pts</div></div>';
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
  CAR:{s:62,c:.75,oc:'Canales',ch:false},CHI:{s:71,c:.75,oc:'B.Johnson',ch:false},
  CIN:{s:78,c:1.0,oc:'Taylor',ch:false},CLE:{s:46,c:.20,oc:'Monken',ch:true},
  DAL:{s:65,c:.75,oc:'Schotty',ch:false},DEN:{s:72,c:1.0,oc:'Payton',ch:false},
  DET:{s:66,c:.75,oc:'Petzing',ch:false},GB:{s:67,c:1.0,oc:'LaFleur',ch:false},
  HOU:{s:64,c:.75,oc:'Caley',ch:false},IND:{s:63,c:1.0,oc:'Steichen',ch:false},
  JAC:{s:60,c:.75,oc:'Coen',ch:false},KC:{s:72,c:1.0,oc:'Reid',ch:false},
  LV:{s:51,c:.20,oc:'Janocko',ch:true},LAC:{s:62,c:.20,oc:'McDaniel',ch:true},
  LAR:{s:74,c:1.0,oc:'McVay',ch:false},MIA:{s:40,c:.20,oc:'Slowik',ch:true},
  MIN:{s:72,c:1.0,oc:"O'Connell",ch:false},NE:{s:55,c:.75,oc:'McDaniels',ch:false},
  NO:{s:61,c:.75,oc:'Moore',ch:false},NYG:{s:50,c:.20,oc:'Nagy',ch:true},
  NYJ:{s:44,c:.20,oc:'Reich',ch:true},PHI:{s:49,c:.20,oc:'Mannion',ch:true},
  PIT:{s:55,c:.20,oc:'Angelichio',ch:true},SF:{s:73,c:1.0,oc:'Shanahan',ch:false},
  SEA:{s:55,c:.20,oc:'Fleury',ch:true},TB:{s:55,c:.20,oc:'Robinson',ch:true},
  TEN:{s:58,c:.35,oc:'Daboll',ch:true},WAS:{s:55,c:.35,oc:'Blough',ch:true},
  FA:{s:50,c:.20,oc:'Unknown',ch:true}
};
const AL={NEP:'NE',NOS:'NO',LVR:'LV',GBP:'GB',TBB:'TB',KCC:'KC',SFO:'SF',OAK:'LV',RFA:'FA',LA:'LAR',JAX:'JAC',WSH:'WAS',ARZ:'ARI'};
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
  if(d.e25!==0&&(d.e24!==0||d.e23!==0)){
    const prev=d.e24!==0?d.e24:d.e23;const diff=d.e25-prev;
    if(pos==='QB'){if(diff>.05)tr='up';else if(diff<-.05)tr='down';}
    else{if(diff>.20)tr='up';else if(diff<-.20)tr='down';}
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
function sm(s){return s>=70?1.12:s>=55?1.03:s>=40?.92:.78;}
function cm(c){return c>=.95?1.00:c>=.70?.96:c>=.50?.88:c>=.30?.80:.72;}
function ci(c){return c>=.95?.10:c>=.70?.15:c>=.50?.22:.32;}
const RP={
  'Jaylen Waddle':1.18,'Courtland Sutton':1.08,'RJ Harvey':1.10,"De'Von Achane":1.05,
  'Bhayshul Tuten':1.15,'Travis Etienne':1.08,'Ricky Pearsall':1.12,'Mike Evans':1.15,
  'Mason Rudolph':.80,'DK Metcalf':.82,'Michael Pittman Jr.':.85,'Jaylen Warren':.90,
  'Rico Dowdle':.92,'Kenneth Walker III':1.08,'Rashee Rice':1.05,'Shedeur Sanders':1.05,
  'Harold Fannin Jr.':1.05,'Quinshon Judkins':.95,'Trey McBride':.92,
  'Marvin Harrison Jr.':.88,'Tua Tagovailoa':.70,'Kyle Pitts':.92,
  'Colston Loveland':1.08,'Mason Taylor':.85,'Breece Hall':.90,'Garrett Wilson':.88,
  'Jaxson Dart':1.05,'Cam Skattebo':1.08,'Justin Jefferson':1.08,
  'Jordan Addison':1.06,'T.J. Hockenson':1.05,'Kyren Williams':1.05,
  'Puka Nacua':1.05,'Zach Charbonnet':.90,'Brandon Aiyuk':0.0,
};

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
function getEff(pl){
  const o=OV[pl.n]||{};
  const team=o.team||pl.t;
  const td=gs(team);
  return{team,s:o.s!==undefined?o.s:td.s,c:o.c!==undefined?o.c:td.c,
    oc:td.oc,ch:td.ch,inj:o.inj!==undefined?o.inj:1.0,
    ktc:o.ktc!==undefined?o.ktc:pl.k,notes:o.notes||'',hasOv:Object.keys(o).length>0};
}

const RAW=[
  // QBs — note: no superflex multiplier; market value already prices it in
  {n:'Josh Allen',t:'BUF',p:'QB',a:29.8,k:9997,ppg25:22.0,ppg24:22.7,ppg23:24.2,g25:17},
  {n:'Drake Maye',t:'NE',p:'QB',a:23.6,k:9318,ppg25:21.1,ppg24:14.4,ppg23:0,g25:17},
  {n:'Jayden Daniels',t:'WAS',p:'QB',a:25.2,k:7668,ppg25:16.7,ppg24:21.5,ppg23:0,g25:7},
  {n:'Caleb Williams',t:'CHI',p:'QB',a:24.3,k:7694,ppg25:19.0,ppg24:15.3,ppg23:0,g25:17},
  {n:'Lamar Jackson',t:'BAL',p:'QB',a:29.2,k:7635,ppg25:17.1,ppg24:25.6,ppg23:21.1,g25:13},
  {n:'Patrick Mahomes',t:'KC',p:'QB',a:30.5,k:6744,ppg25:21.1,ppg24:18.3,ppg23:18.4,g25:14},
  {n:'Jalen Hurts',t:'PHI',p:'QB',a:27.6,k:6338,ppg25:19.1,ppg24:21.3,ppg23:21.9,g25:16},
  {n:'Justin Herbert',t:'LAC',p:'QB',a:28.0,k:6883,ppg25:18.7,ppg24:17.0,ppg23:18.5,g25:16},
  {n:'Bo Nix',t:'DEN',p:'QB',a:26.1,k:6207,ppg25:18.6,ppg24:19.3,ppg23:0,g25:17},
  {n:'Trevor Lawrence',t:'JAC',p:'QB',a:26.4,k:6192,ppg25:20.6,ppg24:15.2,ppg23:17.3,g25:17},
  {n:'Jared Goff',t:'DET',p:'QB',a:31.4,k:4604,ppg25:17.9,ppg24:19.7,ppg23:17.7,g25:17},
  {n:'Dak Prescott',t:'DAL',p:'QB',a:32.6,k:5059,ppg25:19.0,ppg24:15.6,ppg23:20.7,g25:17},
  {n:'Brock Purdy',t:'SF',p:'QB',a:26.2,k:5934,ppg25:20.8,ppg24:18.6,ppg23:19.2,g25:9},
  {n:'Jordan Love',t:'GB',p:'QB',a:27.4,k:5644,ppg25:16.1,ppg24:16.3,ppg23:19.4,g25:15},
  {n:'Baker Mayfield',t:'TB',p:'QB',a:30.9,k:4818,ppg25:16.6,ppg24:22.5,ppg23:16.7,g25:17},
  {n:'Sam Darnold',t:'SEA',p:'QB',a:28.8,k:4824,ppg25:14.7,ppg24:18.8,ppg23:0,g25:17},
  {n:'C.J. Stroud',t:'HOU',p:'QB',a:24.4,k:4830,ppg25:15.5,ppg24:13.7,ppg23:18.7,g25:14},
  {n:'Jaxson Dart',t:'NYG',p:'QB',a:22.8,k:6619,ppg25:17.6,ppg24:0,ppg23:0,g25:14},
  {n:'Cam Ward',t:'TEN',p:'QB',a:23.8,k:5071,ppg25:11.4,ppg24:0,ppg23:0,g25:17},
  {n:'Bryce Young',t:'CAR',p:'QB',a:24.6,k:4481,ppg25:14.3,ppg24:14.6,ppg23:10.4,g25:16},
  {n:'Matthew Stafford',t:'LAR',p:'QB',a:38.1,k:3620,ppg25:21.1,ppg24:13.9,ppg23:17.0,g25:17},
  {n:'Kyler Murray',t:'MIN',p:'QB',a:28.6,k:4385,ppg25:16.2,ppg24:18.1,ppg23:18.9,g25:5},
  {n:'Joe Burrow',t:'CIN',p:'QB',a:29.3,k:7299,ppg25:17.4,ppg24:22.5,ppg23:15.3,g25:8},
  {n:'Tua Tagovailoa',t:'ATL',p:'QB',a:28.0,k:2726,ppg25:12.5,ppg24:17.1,ppg23:16.7,g25:14},
  {n:'Geno Smith',t:'NYJ',p:'QB',a:35.0,k:1200,ppg25:12.7,ppg24:16.5,ppg23:15.7,g25:15},
  {n:'J.J. McCarthy',t:'MIN',p:'QB',a:23.2,k:2880,ppg25:13.7,ppg24:0,ppg23:0,g25:10},
  {n:'Daniel Jones',t:'IND',p:'QB',a:28.8,k:4143,ppg25:18.0,ppg24:14.2,ppg23:0,g25:13},
  {n:'Tyler Shough',t:'NO',p:'QB',a:26.5,k:4683,ppg25:14.9,ppg24:0,ppg23:0,g25:11},
  {n:'Michael Penix Jr.',t:'ATL',p:'QB',a:25.9,k:3153,ppg25:13.7,ppg24:9.4,ppg23:0,g25:9},
  {n:'Shedeur Sanders',t:'CLE',p:'QB',a:24.1,k:2747,ppg25:11.9,ppg24:0,ppg23:0,g25:8},
  {n:'Mason Rudolph',t:'PIT',p:'QB',a:30.0,k:535,ppg25:3.4,ppg24:13.1,ppg23:9.9,g25:5},
  {n:'Aaron Rodgers',t:'PIT',p:'QB',a:42.3,k:800,ppg25:14.2,ppg24:0,ppg23:18.5,g25:10},
  {n:'Malik Willis',t:'MIA',p:'QB',a:26.8,k:4142,ppg25:12.8,ppg24:7.4,ppg23:0,g25:4},
  {n:'Jacoby Brissett',t:'ARI',p:'QB',a:34.4,k:800,ppg25:16.8,ppg24:6.6,ppg23:0,g25:14},
  // RBs
  {n:'Bijan Robinson',t:'ATL',p:'RB',a:24.1,k:9995,ppg25:19.5,ppg24:18.3,ppg23:19.5,g25:17},
  {n:'Jahmyr Gibbs',t:'DET',p:'RB',a:24.0,k:9695,ppg25:19.3,ppg24:19.8,ppg23:0,g25:17},
  {n:'James Cook',t:'BUF',p:'RB',a:26.5,k:6123,ppg25:16.8,ppg24:15.7,ppg23:12.4,g25:17},
  {n:'Jonathan Taylor',t:'IND',p:'RB',a:27.2,k:6020,ppg25:20.0,ppg24:16.8,ppg23:20.0,g25:17},
  {n:'Derrick Henry',t:'BAL',p:'RB',a:32.2,k:3752,ppg25:16.0,ppg24:19.2,ppg23:13.7,g25:17},
  {n:'Kyren Williams',t:'LAR',p:'RB',a:25.6,k:4837,ppg25:14.4,ppg24:15.9,ppg23:19.9,g25:17},
  {n:'Saquon Barkley',t:'PHI',p:'RB',a:29.1,k:4882,ppg25:13.4,ppg24:21.2,ppg23:14.5,g25:16},
  {n:'Christian McCaffrey',t:'SF',p:'RB',a:29.8,k:5083,ppg25:21.5,ppg24:10.1,ppg23:22.4,g25:17},
  {n:'Chase Brown',t:'CIN',p:'RB',a:25.0,k:3800,ppg25:14.6,ppg24:14.3,ppg23:3.9,g25:17},
  {n:'Travis Etienne',t:'NO',p:'RB',a:27.1,k:4687,ppg25:13.9,ppg24:7.4,ppg23:14.9,g25:17},
  {n:'Javonte Williams',t:'DAL',p:'RB',a:25.9,k:4615,ppg25:14.1,ppg24:7.8,ppg23:9.7,g25:16},
  {n:'Josh Jacobs',t:'GB',p:'RB',a:28.1,k:4551,ppg25:14.6,ppg24:16.2,ppg23:12.5,g25:15},
  {n:'Ashton Jeanty',t:'LV',p:'RB',a:22.3,k:7440,ppg25:12.8,ppg24:0,ppg23:0,g25:17},
  {n:"D'Andre Swift",t:'CHI',p:'RB',a:27.2,k:3544,ppg25:13.2,ppg24:11.4,ppg23:11.2,g25:16},
  {n:'Jaylen Warren',t:'PIT',p:'RB',a:27.4,k:3266,ppg25:12.3,ppg24:7.0,ppg23:9.8,g25:16},
  {n:'Rico Dowdle',t:'PIT',p:'RB',a:27.8,k:3340,ppg25:11.6,ppg24:11.1,ppg23:5.2,g25:17},
  {n:'Breece Hall',t:'NYJ',p:'RB',a:24.8,k:5372,ppg25:11.9,ppg24:13.3,ppg23:14.9,g25:16},
  {n:'TreVeyon Henderson',t:'NE',p:'RB',a:23.4,k:5525,ppg25:11.1,ppg24:0,ppg23:0,g25:17},
  {n:'Kenneth Gainwell',t:'TB',p:'RB',a:27.0,k:2923,ppg25:10.9,ppg24:3.2,ppg23:5.2,g25:17},
  {n:'RJ Harvey',t:'DEN',p:'RB',a:25.1,k:3853,ppg25:10.8,ppg24:0,ppg23:0,g25:17},
  {n:'Kenneth Walker III',t:'KC',p:'RB',a:25.4,k:5783,ppg25:10.4,ppg24:14.4,ppg23:12.3,g25:17},
  {n:'Zach Charbonnet',t:'SEA',p:'RB',a:25.2,k:3771,ppg25:10.7,ppg24:9.8,ppg23:5.6,g25:16},
  {n:'Tony Pollard',t:'TEN',p:'RB',a:28.9,k:2620,ppg25:10.0,ppg24:11.3,ppg23:11.5,g25:17},
  {n:'Rhamondre Stevenson',t:'NE',p:'RB',a:28.1,k:2980,ppg25:11.6,ppg24:10.6,ppg23:10.6,g25:14},
  {n:'Quinshon Judkins',t:'CLE',p:'RB',a:22.4,k:5414,ppg25:11.2,ppg24:0,ppg23:0,g25:14},
  {n:'David Montgomery',t:'HOU',p:'RB',a:28.8,k:3504,ppg25:9.1,ppg24:14.6,ppg23:14.2,g25:17},
  {n:'Woody Marks',t:'HOU',p:'RB',a:25.2,k:2811,ppg25:8.7,ppg24:0,ppg23:0,g25:16},
  {n:'Kyle Monangai',t:'CHI',p:'RB',a:23.8,k:3602,ppg25:8.1,ppg24:0,ppg23:0,g25:17},
  {n:'Kareem Hunt',t:'FA',p:'RB',a:30.0,k:668,ppg25:8.0,ppg24:11.1,ppg23:7.4,g25:17},
  {n:'Jacory Croskey-Merritt',t:'WAS',p:'RB',a:24.9,k:2868,ppg25:8.0,ppg24:0,ppg23:0,g25:17},
  {n:'Bucky Irving',t:'TB',p:'RB',a:23.6,k:5148,ppg25:12.4,ppg24:13.0,ppg23:0,g25:10},
  {n:'Rachaad White',t:'WAS',p:'RB',a:27.2,k:2723,ppg25:7.2,ppg24:10.9,ppg23:13.9,g25:17},
  {n:'Jordan Mason',t:'MIN',p:'RB',a:26.8,k:2718,ppg25:7.6,ppg24:9.1,ppg23:2.7,g25:16},
  {n:'Omarion Hampton',t:'LAC',p:'RB',a:23.0,k:6718,ppg25:13.3,ppg24:0,ppg23:0,g25:9},
  {n:'Blake Corum',t:'LAR',p:'RB',a:25.3,k:3320,ppg25:7.0,ppg24:2.0,ppg23:0,g25:17},
  {n:'Cam Skattebo',t:'NYG',p:'RB',a:24.1,k:4553,ppg25:14.5,ppg24:0,ppg23:0,g25:8},
  {n:'J.K. Dobbins',t:'DEN',p:'RB',a:27.2,k:3043,ppg25:11.0,ppg24:13.5,ppg23:0,g25:10},
  {n:'Chuba Hubbard',t:'CAR',p:'RB',a:26.8,k:3337,ppg25:7.4,ppg24:14.7,ppg23:9.6,g25:15},
  {n:'Bhayshul Tuten',t:'JAC',p:'RB',a:23.1,k:4007,ppg25:5.6,ppg24:0,ppg23:0,g25:15},
  {n:'Aaron Jones',t:'MIN',p:'RB',a:31.3,k:2045,ppg25:8.7,ppg24:12.7,ppg23:10.9,g25:12},
  {n:'Tyjae Spears',t:'TEN',p:'RB',a:25.4,k:2673,ppg25:6.9,ppg24:8.2,ppg23:7.5,g25:13},
  {n:'Alvin Kamara',t:'NO',p:'RB',a:30.6,k:2156,ppg25:7.7,ppg24:16.5,ppg23:15.0,g25:11},
  {n:"De'Von Achane",t:'MIA',p:'RB',a:24.0,k:8155,ppg25:12.8,ppg24:18.7,ppg23:0,g25:14},
  {n:'Ollie Gordon',t:'MIA',p:'RB',a:22.2,k:2603,ppg25:3.0,ppg24:0,ppg23:0,g25:16},
  {n:'Isaac Guerendo',t:'SF',p:'RB',a:25.7,k:1689,ppg25:0,ppg24:5.4,ppg23:0,g25:0},
  {n:'Trey Benson',t:'ARI',p:'RB',a:23.6,k:2755,ppg25:5.8,ppg24:3.4,ppg23:0,g25:4},
  {n:'Dylan Sampson',t:'CLE',p:'RB',a:22.8,k:2700,ppg25:4.7,ppg24:0,ppg23:0,g25:15},
  {n:'Jaylen Wright',t:'MIA',p:'RB',a:23.3,k:2324,ppg25:4.2,ppg24:1.7,ppg23:0,g25:11},
  {n:'Braelon Allen',t:'NYJ',p:'RB',a:22.2,k:2796,ppg25:3.6,ppg24:4.5,ppg23:0,g25:4},
  {n:'James Conner',t:'ARI',p:'RB',a:30.2,k:1800,ppg25:7.3,ppg24:14.4,ppg23:14.5,g25:4},
  {n:'Isiah Pacheco',t:'DET',p:'RB',a:27.3,k:3050,ppg25:6.0,ppg24:7.3,ppg23:13.7,g25:13},
  
  
  {n:'Jonathon Brooks',t:'CAR',p:'RB',a:22.1,k:4100,ppg25:5.2,ppg24:0,ppg23:0,g25:8},
    {n:'Tank Bigsby',t:'JAC',p:'RB',a:23.8,k:2900,ppg25:8.1,ppg24:6.2,ppg23:0,g25:15},
      {n:'Alexander Mattison',t:'FA',p:'RB',a:26.7,k:708,ppg25:4.8,ppg24:7.2,ppg23:13.4,g25:10},
  {n:'Audric Estime',t:'DEN',p:'RB',a:22.8,k:1382,ppg25:6.3,ppg24:0,ppg23:0,g25:14},
  {n:'MarShawn Lloyd',t:'GB',p:'RB',a:24.2,k:2100,ppg25:5.8,ppg24:0,ppg23:0,g25:12},
  {n:'Kimani Vidal',t:'LAC',p:'RB',a:23.5,k:1900,ppg25:5.2,ppg24:2.1,ppg23:0,g25:11},
  // WRs
  {n:'Puka Nacua',t:'LAR',p:'WR',a:24.8,k:9394,ppg25:19.4,ppg24:15.2,ppg23:14.5,g25:16},
  {n:'Jaxon Smith-Njigba',t:'SEA',p:'WR',a:24.1,k:9675,ppg25:17.7,ppg24:11.9,ppg23:7.0,g25:17},
  {n:'Amon-Ra St. Brown',t:'DET',p:'WR',a:26.4,k:7658,ppg25:15.6,ppg24:15.2,ppg23:17.0,g25:17},
  {n:'George Pickens',t:'DAL',p:'WR',a:25.0,k:6137,ppg25:14.4,ppg24:9.6,ppg23:10.4,g25:17},
  {n:'Chris Olave',t:'NO',p:'WR',a:25.7,k:5644,ppg25:13.7,ppg24:7.6,ppg23:11.7,g25:16},
  {n:'Zay Flowers',t:'BAL',p:'WR',a:25.5,k:4652,ppg25:11.8,ppg24:10.1,ppg23:10.5,g25:17},
  {n:'Davante Adams',t:'LAR',p:'WR',a:33.2,k:3556,ppg25:13.8,ppg24:14.2,ppg23:12.6,g25:14},
  {n:'Nico Collins',t:'HOU',p:'WR',a:27.0,k:5797,ppg25:12.7,ppg24:14.7,ppg23:14.7,g25:15},
  {n:'Jameson Williams',t:'DET',p:'WR',a:25.0,k:4723,ppg25:11.0,ppg24:12.2,ppg23:5.7,g25:17},
  {n:'Courtland Sutton',t:'DEN',p:'WR',a:30.4,k:3208,ppg25:10.7,ppg24:11.8,ppg23:10.0,g25:17},
  {n:'Tee Higgins',t:'CIN',p:'WR',a:27.2,k:4931,ppg25:12.1,ppg24:15.5,ppg23:9.7,g25:15},
  {n:'A.J. Brown',t:'PHI',p:'WR',a:28.7,k:4816,ppg25:12.1,ppg24:14.1,ppg23:13.9,g25:15},
  {n:'Tetairoa McMillan',t:'CAR',p:'WR',a:23.0,k:6668,ppg25:10.4,ppg24:0,ppg23:0,g25:17},
  {n:"Wan'Dale Robinson",t:'TEN',p:'WR',a:25.2,k:3716,ppg25:10.7,ppg24:8.0,ppg23:6.9,g25:16},
  {n:'Drake London',t:'ATL',p:'WR',a:24.6,k:6891,ppg25:14.0,ppg24:13.6,ppg23:8.7,g25:12},
  {n:'Emeka Egbuka',t:'TB',p:'WR',a:23.4,k:6092,ppg25:9.7,ppg24:0,ppg23:0,g25:17},
  {n:"Ja'Marr Chase",t:'CIN',p:'WR',a:26.0,k:9200,ppg25:15.7,ppg24:20.0,ppg23:18.1,g25:17},
  {n:'CeeDee Lamb',t:'DAL',p:'WR',a:26.9,k:7414,ppg25:11.7,ppg24:14.2,ppg23:19.7,g25:14},
  {n:'DeVonta Smith',t:'PHI',p:'WR',a:27.3,k:4859,ppg25:9.6,ppg24:12.7,ppg23:11.7,g25:17},
  {n:'Michael Pittman Jr.',t:'PIT',p:'WR',a:28.4,k:3562,ppg25:9.6,ppg24:8.2,ppg23:12.2,g25:17},
  {n:'Jaylen Waddle',t:'DEN',p:'WR',a:27.3,k:4917,ppg25:10.1,ppg24:7.5,ppg23:11.6,g25:16},
  {n:'Alec Pierce',t:'IND',p:'WR',a:25.9,k:4429,ppg25:10.7,ppg24:8.9,ppg23:4.7,g25:15},
  {n:'Justin Jefferson',t:'MIN',p:'WR',a:26.8,k:7697,ppg25:9.4,ppg24:15.6,ppg23:16.8,g25:17},
  {n:'DK Metcalf',t:'PIT',p:'WR',a:28.3,k:3709,ppg25:10.5,ppg24:10.5,ppg23:12.0,g25:15},
  {n:'Parker Washington',t:'JAC',p:'WR',a:24.0,k:3580,ppg25:9.7,ppg24:4.8,ppg23:3.5,g25:16},
  {n:'Ladd McConkey',t:'LAC',p:'WR',a:24.4,k:5349,ppg25:9.2,ppg24:12.5,ppg23:0,g25:16},
  {n:"D.J. Moore",t:'BUF',p:'WR',a:28.9,k:3942,ppg25:8.5,ppg24:11.1,ppg23:14.0,g25:17},
  {n:'Troy Franklin',t:'DEN',p:'WR',a:23.5,k:2500,ppg25:8.5,ppg24:3.3,ppg23:0,g25:17},
  {n:'Jakobi Meyers',t:'JAC',p:'WR',a:29.4,k:3332,ppg25:8.6,ppg24:11.6,ppg23:11.4,g25:16},
  {n:'Romeo Doubs',t:'NE',p:'WR',a:25.9,k:3701,ppg25:8.6,ppg24:8.4,ppg23:8.5,g25:16},
  {n:'Quentin Johnston',t:'LAC',p:'WR',a:24.5,k:3324,ppg25:10.4,ppg24:9.8,ppg23:4.4,g25:14},
  {n:'Khalil Shakir',t:'BUF',p:'WR',a:26.1,k:3056,ppg25:8.2,ppg24:9.6,ppg23:5.5,g25:16},
  {n:'Rome Odunze',t:'CHI',p:'WR',a:23.5,k:4800,ppg25:10.3,ppg24:6.9,ppg23:0,g25:12},
  {n:'Rashee Rice',t:'KC',p:'WR',a:25.9,k:4831,ppg25:15.5,ppg24:13.2,ppg23:10.8,g25:8},
  {n:'Christian Watson',t:'GB',p:'WR',a:26.8,k:3697,ppg25:11.5,ppg24:6.1,ppg23:9.7,g25:10},
  {n:'Brian Thomas Jr.',t:'JAC',p:'WR',a:23.4,k:4943,ppg25:8.2,ppg24:14.1,ppg23:0,g25:14},
  {n:'Jordan Addison',t:'MIN',p:'WR',a:24.1,k:3953,ppg25:8.2,ppg24:12.1,ppg23:11.0,g25:14},
  {n:'Luther Burden',t:'CHI',p:'WR',a:22.3,k:5376,ppg25:7.0,ppg24:0,ppg23:0,g25:15},
  {n:'Elic Ayomanor',t:'TEN',p:'WR',a:22.8,k:2822,ppg25:6.0,ppg24:0,ppg23:0,g25:16},
  {n:'Terry McLaurin',t:'WAS',p:'WR',a:30.5,k:3384,ppg25:9.5,ppg24:13.3,ppg23:10.0,g25:10},
  {n:'Tre Harris',t:'LAC',p:'WR',a:24.0,k:2809,ppg25:3.2,ppg24:0,ppg23:0,g25:17},
  {n:'Jayden Higgins',t:'HOU',p:'WR',a:23.2,k:3546,ppg25:6.4,ppg24:0,ppg23:0,g25:17},
  {n:'Matthew Golden',t:'GB',p:'WR',a:22.6,k:3544,ppg25:4.0,ppg24:0,ppg23:0,g25:14},
  {n:'Ricky Pearsall',t:'SF',p:'WR',a:25.5,k:3640,ppg25:7.1,ppg24:7.1,ppg23:0,g25:10},
  {n:'Mike Evans',t:'SF',p:'WR',a:32.6,k:3340,ppg25:8.7,ppg24:14.5,ppg23:14.3,g25:8},
  {n:'Marvin Harrison Jr.',t:'ARI',p:'WR',a:23.6,k:4995,ppg25:8.9,ppg24:9.7,ppg23:0,g25:12},
  {n:'Garrett Wilson',t:'NYJ',p:'WR',a:25.6,k:5852,ppg25:11.6,ppg24:11.8,ppg23:9.7,g25:7},
  {n:'Xavier Worthy',t:'KC',p:'WR',a:22.9,k:3373,ppg25:6.4,ppg24:9.3,ppg23:0,g25:14},
  {n:'Keon Coleman',t:'BUF',p:'WR',a:22.5,k:2900,ppg25:6.4,ppg24:7.5,ppg23:0,g25:13},
  {n:'Josh Downs',t:'IND',p:'WR',a:24.6,k:3339,ppg25:6.7,ppg24:10.5,ppg23:7.2,g25:16},
  {n:'Travis Hunter',t:'JAC',p:'WR',a:22.8,k:3701,ppg25:7.1,ppg24:0,ppg23:0,g25:7},
  {n:'Brandon Aiyuk',t:'FA',p:'WR',a:28.0,k:2609,ppg25:0,ppg24:7.5,ppg23:13.1,g25:0},
  {n:'Jalen Coker',t:'CAR',p:'WR',a:24.4,k:3085,ppg25:6.7,ppg24:7.0,ppg23:0,g25:11},
  {n:'Malik Nabers',t:'NYG',p:'WR',a:22.6,k:7790,ppg25:12.0,ppg24:14.6,ppg23:0,g25:4},
  {n:'Deebo Samuel',t:'FA',p:'WR',a:29.4,k:2800,ppg25:9.5,ppg24:8.5,ppg23:14.2,g25:16},
  {n:'Jauan Jennings',t:'FA',p:'WR',a:29.0,k:2700,ppg25:9.7,ppg24:11.5,ppg23:3.2,g25:15},
  {n:'Stefon Diggs',t:'FA',p:'WR',a:32.0,k:1800,ppg25:9.9,ppg24:12.3,ppg23:13.0,g25:17},
  
  {n:'Jayden Reed',t:'GB',p:'WR',a:25.3,k:4200,ppg25:10.4,ppg24:12.8,ppg23:9.6,g25:16},
  {n:'Calvin Ridley',t:'TEN',p:'WR',a:30.7,k:3200,ppg25:5.5,ppg24:7.2,ppg23:13.8,g25:7},
  {n:'Rashid Shaheed',t:'SEA',p:'WR',a:27.4,k:3100,ppg25:9.4,ppg24:6.8,ppg23:10.2,g25:17},
    {n:'Darnell Mooney',t:'ATL',p:'WR',a:27.8,k:2800,ppg25:8.6,ppg24:9.2,ppg23:6.4,g25:16},
    {n:'Rashod Bateman',t:'BAL',p:'WR',a:25.8,k:2900,ppg25:9.8,ppg24:8.6,ppg23:6.2,g25:14},
    {n:'Jalen McMillan',t:'TB',p:'WR',a:23.1,k:3200,ppg25:7.8,ppg24:0,ppg23:0,g25:14},
  {n:'Isaac TeSlaa',t:'DET',p:'WR',a:23.8,k:2800,ppg25:6.4,ppg24:0,ppg23:0,g25:15},
  {n:'Xavier Legette',t:'CAR',p:'WR',a:24.2,k:3100,ppg25:7.2,ppg24:5.8,ppg23:0,g25:16},
  {n:'Devaughn Vele',t:'DEN',p:'WR',a:25.1,k:2600,ppg25:7.6,ppg24:4.2,ppg23:0,g25:14},
  {n:'Chimere Dike',t:'TEN',p:'WR',a:23.4,k:2400,ppg25:5.8,ppg24:0,ppg23:0,g25:13},
      {n:'Jalen Nailor',t:'LV',p:'WR',a:26.8,k:2900,ppg25:9.6,ppg24:7.8,ppg23:4.2,g25:15},
  {n:'Marvin Mims',t:'DEN',p:'WR',a:23.8,k:2700,ppg25:6.8,ppg24:6.2,ppg23:3.4,g25:14},
  {n:'K.J. Osborn',t:'FA',p:'WR',a:28.4,k:150,ppg25:6.2,ppg24:5.4,ppg23:8.6,g25:12},
  {n:'Dontayvion Wicks',t:'GB',p:'WR',a:24.4,k:2600,ppg25:7.4,ppg24:5.8,ppg23:4.2,g25:15},
  // TEs
  {n:'Trey McBride',t:'ARI',p:'TE',a:26.3,k:8387,ppg25:18.6,ppg24:15.6,ppg23:10.7,g25:17},
  {n:'Brock Bowers',t:'LV',p:'TE',a:23.3,k:8549,ppg25:14.7,ppg24:15.5,ppg23:0,g25:12},
  {n:'George Kittle',t:'SF',p:'TE',a:32.4,k:3743,ppg25:14.7,ppg24:15.8,ppg23:12.7,g25:11},
  {n:'Sam LaPorta',t:'DET',p:'TE',a:25.2,k:5083,ppg25:11.9,ppg24:10.9,ppg23:14.1,g25:9},
  {n:'Kyle Pitts',t:'ATL',p:'TE',a:25.4,k:5070,ppg25:12.4,ppg24:7.7,ppg23:8.1,g25:17},
  {n:'Travis Kelce',t:'KC',p:'TE',a:36.4,k:2834,ppg25:11.4,ppg24:12.2,ppg23:14.6,g25:17},
  {n:'Tyler Warren',t:'IND',p:'TE',a:23.8,k:6393,ppg25:11.1,ppg24:0,ppg23:0,g25:17},
  {n:'Harold Fannin Jr.',t:'CLE',p:'TE',a:21.7,k:5491,ppg25:11.7,ppg24:0,ppg23:0,g25:16},
  {n:'Dallas Goedert',t:'PHI',p:'TE',a:31.2,k:3028,ppg25:12.3,ppg24:10.4,ppg23:9.7,g25:15},
  {n:'Juwan Johnson',t:'NO',p:'TE',a:29.5,k:2790,ppg25:10.6,ppg24:7.2,ppg23:7.5,g25:17},
  {n:'Hunter Henry',t:'NE',p:'TE',a:31.3,k:2760,ppg25:10.5,ppg24:9.1,ppg23:8.6,g25:17},
  {n:'Dalton Schultz',t:'HOU',p:'TE',a:29.7,k:2721,ppg25:10.5,ppg24:7.0,ppg23:10.0,g25:17},
  {n:'Colston Loveland',t:'CHI',p:'TE',a:21.9,k:6715,ppg25:10.3,ppg24:0,ppg23:0,g25:16},
  {n:'AJ Barner',t:'SEA',p:'TE',a:23.9,k:3266,ppg25:8.7,ppg24:4.6,ppg23:0,g25:17},
  {n:'Oronde Gadsden',t:'LAC',p:'TE',a:22.7,k:4427,ppg25:8.8,ppg24:0,ppg23:0,g25:15},
  {n:'Mark Andrews',t:'BAL',p:'TE',a:30.5,k:3162,ppg25:7.7,ppg24:11.1,ppg23:13.5,g25:17},
  {n:'Theo Johnson',t:'NYG',p:'TE',a:25.0,k:2834,ppg25:8.5,ppg24:5.7,ppg23:0,g25:15},
  {n:'Dalton Kincaid',t:'BUF',p:'TE',a:26.4,k:3784,ppg25:10.5,ppg24:7.8,ppg23:9.4,g25:12},
  {n:'Chigoziem Okonkwo',t:'WAS',p:'TE',a:26.5,k:3123,ppg25:7.3,ppg24:6.7,ppg23:6.7,g25:17},
  {n:'Cade Otton',t:'TB',p:'TE',a:26.9,k:2913,ppg25:7.6,ppg24:10.0,ppg23:6.9,g25:16},
  {n:'Brenton Strange',t:'JAC',p:'TE',a:25.2,k:3556,ppg25:9.8,ppg24:5.4,ppg23:0,g25:12},
  {n:'Tucker Kraft',t:'GB',p:'TE',a:25.4,k:5441,ppg25:14.7,ppg24:9.6,ppg23:4.6,g25:8},
  {n:'Pat Freiermuth',t:'PIT',p:'TE',a:27.4,k:2609,ppg25:6.7,ppg24:9.9,ppg23:6.4,g25:17},
  {n:'T.J. Hockenson',t:'MIN',p:'TE',a:28.7,k:3179,ppg25:7.5,ppg24:8.7,ppg23:14.6,g25:15},
  {n:'Evan Engram',t:'DEN',p:'TE',a:31.5,k:2218,ppg25:6.4,ppg24:9.9,ppg23:13.5,g25:16},
  {n:'Gunnar Helm',t:'TEN',p:'TE',a:23.5,k:2919,ppg25:5.7,ppg24:0,ppg23:0,g25:16},
  {n:'Mason Taylor',t:'NYJ',p:'TE',a:21.9,k:3335,ppg25:6.8,ppg24:0,ppg23:0,g25:13},
  {n:'Isaiah Likely',t:'NYG',p:'TE',a:25.9,k:4049,ppg25:4.4,ppg24:7.7,ppg23:5.9,g25:14},
  {n:'Cole Kmet',t:'CHI',p:'TE',a:26.6,k:3800,ppg25:8.4,ppg24:8.8,ppg23:6.4,g25:16},
  {n:'Jake Ferguson',t:'DAL',p:'TE',a:26.2,k:4200,ppg25:9.2,ppg24:9.4,ppg23:10.8,g25:17},
  {n:'Dawson Knox',t:'BUF',p:'TE',a:30.2,k:2400,ppg25:7.8,ppg24:6.4,ppg23:8.2,g25:14},
  {n:'Noah Fant',t:'NO',p:'TE',a:27.4,k:2200,ppg25:6.8,ppg24:8.2,ppg23:7.6,g25:15},
  {n:'Jonnu Smith',t:'ATL',p:'TE',a:30.0,k:1800,ppg25:7.4,ppg24:9.6,ppg23:6.2,g25:14},
  {n:'Charlie Kolar',t:'LAC',p:'TE',a:27.4,k:934,ppg25:7.2,ppg24:5.8,ppg23:3.4,g25:16},
  {n:'Elijah Higgins',t:'ARI',p:'TE',a:24.8,k:1110,ppg25:5.6,ppg24:4.2,ppg23:0,g25:15},
    // Batch 4-7 — WRs
  {n:'Jalen Tolbert',t:'DAL',p:'WR',a:26.3,k:1800,ppg25:5.6,ppg24:13.5,ppg23:8.6,g25:13},
  {n:'Christian Kirk',t:'FA',p:'WR',a:28.8,k:1200,ppg25:5.8,ppg24:11.0,ppg23:9.1,g25:14},
  {n:'Jack Bech',t:'LV',p:'WR',a:23.5,k:2400,ppg25:5.2,ppg24:0,ppg23:0,g25:12},
  {n:'Jerry Jeudy',t:'CLE',p:'WR',a:26.9,k:2100,ppg25:9.6,ppg24:11.5,ppg23:12.6,g25:18},
  {n:'Cooper Kupp',t:'SEA',p:'WR',a:33.1,k:2800,ppg25:10.2,ppg24:11.8,ppg23:11.2,g25:17},
  {n:'Tez Johnson',t:'TB',p:'WR',a:23.3,k:2200,ppg25:9.3,ppg24:0,ppg23:0,g25:17},
  {n:'Chris Godwin',t:'FA',p:'WR',a:30.4,k:1800,ppg25:12.5,ppg24:16.1,ppg23:9.9,g25:10},
  {n:'Cedric Tillman',t:'CLE',p:'WR',a:24.4,k:1900,ppg25:5.2,ppg24:11.9,ppg23:5.5,g25:14},
  {n:'Pat Bryant',t:'DEN',p:'WR',a:23.2,k:2600,ppg25:7.8,ppg24:0,ppg23:0,g25:15},
  {n:'Tre Tucker',t:'LV',p:'WR',a:25.6,k:1600,ppg25:11.9,ppg24:11.5,ppg23:7.2,g25:18},
  {n:'Kyle Williams',t:'NE',p:'WR',a:23.4,k:2100,ppg25:5.2,ppg24:0,ppg23:0,g25:17},
  {n:'Tank Dell',t:'HOU',p:'WR',a:24.1,k:2900,ppg25:0,ppg24:14.7,ppg23:14.2,g25:0},
  {n:'DeMario Douglas',t:'NE',p:'WR',a:25.4,k:1900,ppg25:8.4,ppg24:12.6,ppg23:10.6,g25:18},
  {n:'Adonai Mitchell',t:'IND',p:'WR',a:23.4,k:3200,ppg25:8.1,ppg24:4.9,ppg23:0,g25:17},
  {n:'Jaylin Noel',t:'IND',p:'WR',a:22.8,k:1800,ppg25:6.5,ppg24:0,ppg23:0,g25:17},
  {n:'Malik Washington',t:'MIA',p:'WR',a:24.6,k:1600,ppg25:9.7,ppg24:5.9,ppg23:0,g25:18},
  {n:'Kayshon Boutte',t:'NE',p:'WR',a:23.8,k:1400,ppg25:12.7,ppg24:12.4,ppg23:0,g25:15},
  {n:'Michael Wilson',t:'ARI',p:'WR',a:25.8,k:2000,ppg25:10.7,ppg24:11.2,ppg23:13.0,g25:18},
  {n:'Darius Slayton',t:'NYG',p:'WR',a:28.6,k:1400,ppg25:10.2,ppg24:10.1,ppg23:13.4,g25:15},
  {n:'Marquise Brown',t:'FA',p:'WR',a:28.8,k:1500,ppg25:11.8,ppg24:6.8,ppg23:13.1,g25:17},
  // Batch 4-7 — RBs
  {n:'Tyrone Tracy',t:'NYG',p:'RB',a:24.8,k:3400,ppg25:9.5,ppg24:9.6,ppg23:0,g25:16},
  {n:'Brian Robinson',t:'WAS',p:'RB',a:27.0,k:2200,ppg25:6.9,ppg24:10.7,ppg23:12.0,g25:17},
  {n:'George Holani',t:'LV',p:'RB',a:25.2,k:1800,ppg25:6.6,ppg24:0,ppg23:0,g25:6},
  {n:'Keaton Mitchell',t:'CLE',p:'RB',a:24.2,k:2400,ppg25:7.3,ppg24:4.2,ppg23:16.4,g25:14},
  {n:'Chris Rodriguez',t:'JAC',p:'RB',a:25.4,k:2100,ppg25:12.9,ppg24:8.9,ppg23:9.1,g25:14},
  {n:'Sean Tucker',t:'TB',p:'RB',a:25.3,k:1900,ppg25:13.5,ppg24:10.7,ppg23:2.1,g25:13},
  {n:'Ray Davis',t:'BUF',p:'RB',a:24.6,k:1800,ppg25:6.6,ppg24:12.0,ppg23:0,g25:18},
  {n:'Tyler Allgeier',t:'ARI',p:'RB',a:25.4,k:1600,ppg25:12.9,ppg24:11.1,ppg23:14.3,g25:18},
  // Batch 4-7 — TEs
  {n:'Greg Dulcich',t:'FA',p:'TE',a:26.4,k:1200,ppg25:10.2,ppg24:1.1,ppg23:2.3,g25:11},
  {n:'David Njoku',t:'FA',p:'TE',a:28.8,k:3200,ppg25:12.4,ppg24:13.5,ppg23:12.6,g25:12},
  {n:'Colby Parkinson',t:'LAR',p:'TE',a:26.8,k:1800,ppg25:8.6,ppg24:6.0,ppg23:6.1,g25:15},
  {n:'Terrance Ferguson',t:'LAR',p:'TE',a:23.8,k:1900,ppg25:7.8,ppg24:0,ppg23:0,g25:13},
  {n:'Jake Tonges',t:'SF',p:'TE',a:26.8,k:2000,ppg25:9.9,ppg24:0,ppg23:0,g25:17},
  {n:'Michael Mayer',t:'LV',p:'TE',a:24.2,k:1800,ppg25:9.8,ppg24:6.1,ppg23:9.6,g25:14},
  {n:'JaTavion Sanders',t:'CAR',p:'TE',a:23.8,k:1600,ppg25:6.8,ppg24:8.2,ppg23:0,g25:13},
  {n:'Ben Sinnott',t:'WAS',p:'TE',a:25.0,k:2300,ppg25:3.3,ppg24:1.9,ppg23:0,g25:17},
  {n:'Zach Ertz',t:'WAS',p:'TE',a:35.8,k:1400,ppg25:16.6,ppg24:10.4,ppg23:10.1,g25:13},
  // Batch 4-7 — QBs
  {n:'Mac Jones',t:'NE',p:'QB',a:27.8,k:800,ppg25:0,ppg24:8.2,ppg23:11.4,g25:0},
  {n:'Joe Flacco',t:'CIN',p:'QB',a:41.8,k:500,ppg25:0,ppg24:0,ppg23:14.2,g25:0},
  {n:'Justin Fields',t:'KC',p:'QB',a:26.8,k:3400,ppg25:15.4,ppg24:19.2,ppg23:0,g25:9},
  {n:'Kirk Cousins',t:'LV',p:'QB',a:37.9,k:800,ppg25:0,ppg24:25.6,ppg23:0,g25:0},
  // 2026 Rookies — post-draft Round 1
  {n:'Fernando Mendoza',t:'LV',p:'QB',a:23,k:8800,ppg25:0.0,ppg24:0,ppg23:0,g25:0},
  {n:'Jeremiyah Love',t:'ARI',p:'RB',a:22,k:9300,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Carnell Tate',t:'TEN',p:'WR',a:21,k:7800,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jordyn Tyson',t:'NO',p:'WR',a:23,k:7600,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Ty Simpson',t:'LAR',p:'QB',a:23,k:4200,ppg25:0.0,ppg24:0,ppg23:0,g25:0},
  {n:'Kenyon Sadiq',t:'NYJ',p:'TE',a:21,k:6800,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Makai Lemon',t:'PHI',p:'WR',a:22,k:7400,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'KC Concepcion',t:'CLE',p:'WR',a:22,k:6200,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Omar Cooper',t:'NYJ',p:'WR',a:22,k:5800,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jadarian Price',t:'SEA',p:'RB',a:22,k:6000,ppg25:0,ppg24:0,ppg23:0,g25:0},
  // 2026 Rookies — Day 2 & 3 picks
  {n:"De'Zhaun Stribling",t:'SF',p:'WR',a:24,k:4200,ppg25:7.2,ppg24:0,ppg23:0,g25:0},
  {n:'Denzel Boston',t:'CLE',p:'WR',a:23,k:4800,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Germie Bernard',t:'PIT',p:'WR',a:23,k:3800,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Eli Stowers',t:'PHI',p:'TE',a:24,k:6200,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Marlin Klein',t:'HOU',p:'TE',a:24,k:1200,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Max Klare',t:'LAR',p:'TE',a:23,k:2200,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Carson Beck',t:'ARI',p:'QB',a:24,k:1200,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Sam Roush',t:'CHI',p:'TE',a:24,k:800,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Antonio Williams',t:'WAS',p:'WR',a:23,k:4600,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Oscar Delp',t:'NO',p:'TE',a:23,k:1000,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Malachi Fields',t:'NYG',p:'WR',a:23,k:2000,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Zachariah Branch',t:'ATL',p:'WR',a:22,k:3200,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:"Ja'Kobi Lane",t:'BAL',p:'WR',a:23,k:3600,ppg25:6.4,ppg24:0,ppg23:0,g25:0},
  {n:'Chris Brazzell II',t:'CAR',p:'WR',a:23,k:1400,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Ted Hurst',t:'TB',p:'WR',a:24,k:1800,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Drew Allar',t:'PIT',p:'QB',a:24,k:2000,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Will Kacmarek',t:'MIA',p:'TE',a:24,k:1000,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Chris Bell',t:'MIA',p:'WR',a:23,k:3600,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Eli Raridon',t:'NE',p:'TE',a:24,k:1800,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Caleb Douglas',t:'MIA',p:'WR',a:23,k:1800,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Zavion Thomas',t:'CHI',p:'WR',a:23,k:1400,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Kaelon Black',t:'SF',p:'RB',a:23,k:2000,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Barion Brown',t:'NO',p:'WR',a:23,k:633,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Cyrus Allen',t:'KC',p:'WR',a:24,k:2000,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Reggie Virgil',t:'ARI',p:'WR',a:24,k:150,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Kendrick Law',t:'DET',p:'WR',a:23,k:150,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Kaden Wetjen',t:'PIT',p:'WR',a:24,k:150,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Colbie Young',t:'CIN',p:'WR',a:24,k:150,ppg25:0,ppg24:0,ppg23:0,g25:0},
  // Missing rookies — added from draft results
  {n:'Nicholas Singleton',t:'TEN',p:'RB',a:23,k:2400,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Emmett Johnson',t:'KC',p:'RB',a:24,k:1800,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jonah Coleman',t:'DEN',p:'RB',a:24,k:2200,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Mike Washington Jr.',t:'LV',p:'RB',a:24,k:2400,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Adam Randall',t:'BAL',p:'RB',a:22,k:1600,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Kaytron Allen',t:'WAS',p:'RB',a:23,k:1000,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Demond Claiborne',t:'MIN',p:'RB',a:23,k:1000,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Deion Burks',t:'IND',p:'WR',a:23,k:1400,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Garrett Nussmeier',t:'KC',p:'QB',a:23,k:800,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Cade Klubnik',t:'NYJ',p:'QB',a:23,k:1600,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Taylen Green',t:'CLE',p:'QB',a:25,k:800,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Bryce Lance',t:'NO',p:'WR',a:24,k:1200,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Elijah Sarratt',t:'BAL',p:'WR',a:24,k:1200,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Skyler Bell',t:'BUF',p:'WR',a:24,k:1800,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Brenen Thompson',t:'LAC',p:'WR',a:24,k:2000,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Justin Joly',t:'DEN',p:'TE',a:24,k:2000,ppg25:0,ppg24:0,ppg23:0,g25:0},
  // === UNIVERSE EXPANSION (FantasyCalc full list) — seeded; pipeline populates stats/age ===
  {n:'Deshaun Watson',t:'CLE',p:'QB',a:25,k:1280,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Anthony Richardson',t:'IND',p:'QB',a:25,k:1099,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jalen Milroe',t:'SEA',p:'QB',a:25,k:511,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Will Howard',t:'PIT',p:'QB',a:25,k:429,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Cole Payton',t:'PHI',p:'QB',a:25,k:328,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Marcus Mariota',t:'WAS',p:'QB',a:25,k:317,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Riley Leonard',t:'IND',p:'QB',a:25,k:310,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Quinn Ewers',t:'MIA',p:'QB',a:25,k:295,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jameis Winston',t:'NYG',p:'QB',a:25,k:276,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Joe Milton',t:'DAL',p:'QB',a:25,k:240,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Dillon Gabriel',t:'CLE',p:'QB',a:25,k:130,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Gardner Minshew',t:'ARI',p:'QB',a:25,k:118,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Kenny Pickett',t:'CAR',p:'QB',a:25,k:115,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Tyler Huntley',t:'BAL',p:'QB',a:25,k:112,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Will Levis',t:'TEN',p:'QB',a:25,k:110,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Tyson Bagent',t:'CHI',p:'QB',a:25,k:101,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Trey Lance',t:'LAC',p:'QB',a:25,k:79,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Tyrod Taylor',t:'GB',p:'QB',a:25,k:64,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Davis Mills',t:'HOU',p:'QB',a:25,k:56,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Tanner McKee',t:'PHI',p:'QB',a:25,k:51,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Kaleb Johnson',t:'PIT',p:'RB',a:24,k:1150,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jordan James',t:'SF',p:'RB',a:24,k:850,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Eli Heidenreich',t:'PIT',p:'RB',a:24,k:782,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jaydon Blue',t:'DAL',p:'RB',a:24,k:690,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:"J'Mari Taylor",t:'JAC',p:'RB',a:24,k:639,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Seth McGowan',t:'IND',p:'RB',a:24,k:632,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'DJ Giddens',t:'IND',p:'RB',a:24,k:541,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jam Miller',t:'NE',p:'RB',a:24,k:532,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Emanuel Wilson',t:'SEA',p:'RB',a:24,k:511,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Devin Neal',t:'NO',p:'RB',a:24,k:448,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'LeQuint Allen',t:'JAC',p:'RB',a:24,k:396,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Trevor Etienne',t:'CAR',p:'RB',a:24,k:395,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Tahj Brooks',t:'CIN',p:'RB',a:24,k:337,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Chris Brooks',t:'GB',p:'RB',a:24,k:325,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Robert Henry',t:'WAS',p:'RB',a:24,k:313,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Isaiah Davis',t:'NYJ',p:'RB',a:24,k:312,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Roman Hemby',t:'LV',p:'RB',a:24,k:301,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Brashard Smith',t:'KC',p:'RB',a:24,k:299,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Najee Harris',t:'None',p:'RB',a:24,k:290,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Joe Mixon',t:'None',p:'RB',a:24,k:260,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Malik Davis',t:'DAL',p:'RB',a:24,k:177,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Kendre Miller',t:'NO',p:'RB',a:24,k:173,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jarquez Hunter',t:'LAR',p:'RB',a:24,k:168,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Justice Hill',t:'BAL',p:'RB',a:24,k:146,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Emari Demercado',t:'KC',p:'RB',a:24,k:141,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Ty Johnson',t:'BUF',p:'RB',a:24,k:123,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Devin Singletary',t:'NYG',p:'RB',a:24,k:112,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jerome Ford',t:'WAS',p:'RB',a:24,k:110,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Will Shipley',t:'PHI',p:'RB',a:24,k:100,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Phil Mafah',t:'DAL',p:'RB',a:24,k:80,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Damien Martinez',t:'GB',p:'RB',a:24,k:74,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Samaje Perine',t:'CIN',p:'RB',a:24,k:57,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Michael Carter',t:'TEN',p:'RB',a:24,k:53,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Zonovan Knight',t:'ARI',p:'RB',a:24,k:48,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Roschon Johnson',t:'CHI',p:'RB',a:24,k:43,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Kenny McIntosh',t:'SEA',p:'RB',a:24,k:36,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Nick Chubb',t:'None',p:'RB',a:24,k:34,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Austin Ekeler',t:'None',p:'RB',a:24,k:24,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Raheim Sanders',t:'CLE',p:'RB',a:24,k:16,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Michael Trigg',t:'DAL',p:'TE',a:24,k:790,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Elijah Arroyo',t:'SEA',p:'TE',a:24,k:689,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jack Endries',t:'CIN',p:'TE',a:24,k:625,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Matt Hibner',t:'BAL',p:'TE',a:24,k:491,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Tanner Koziol',t:'JAC',p:'TE',a:24,k:457,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'John Michael Gyllenborg',t:'KC',p:'TE',a:24,k:270,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Darnell Washington',t:'PIT',p:'TE',a:24,k:251,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jaren Kanak',t:'TEN',p:'TE',a:24,k:229,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Mike Gesicki',t:'CIN',p:'TE',a:24,k:216,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Nate Boerkircher',t:'JAC',p:'TE',a:24,k:197,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Luke Musgrave',t:'GB',p:'TE',a:24,k:122,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Joe Royer',t:'CLE',p:'TE',a:24,k:113,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Noah Gray',t:'KC',p:'TE',a:24,k:111,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Tyler Higbee',t:'LAR',p:'TE',a:24,k:104,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Erick All',t:'CIN',p:'TE',a:24,k:36,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Tory Horton',t:'SEA',p:'WR',a:24,k:1120,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Tyreek Hill',t:'None',p:'WR',a:24,k:916,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Kevin Coleman',t:'MIA',p:'WR',a:24,k:853,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Ryan Flournoy',t:'DAL',p:'WR',a:24,k:719,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'CJ Daniels',t:'LAR',p:'WR',a:24,k:587,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:"Dont'e Thornton",t:'LV',p:'WR',a:24,k:453,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Isaiah Bond',t:'CLE',p:'WR',a:24,k:441,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jalen Royals',t:'KC',p:'WR',a:24,k:420,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Josh Cameron',t:'JAC',p:'WR',a:24,k:357,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jeff Caldwell',t:'KC',p:'WR',a:24,k:257,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jaylin Lane',t:'WAS',p:'WR',a:24,k:257,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jahan Dotson',t:'ATL',p:'WR',a:24,k:223,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Tyquan Thornton',t:'KC',p:'WR',a:24,k:215,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Malik Benson',t:'LV',p:'WR',a:24,k:199,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Savion Williams',t:'GB',p:'WR',a:24,k:181,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Odell Beckham',t:'None',p:'WR',a:24,k:175,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Andrei Iosivas',t:'CIN',p:'WR',a:24,k:162,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Calvin Austin',t:'NYG',p:'WR',a:24,k:142,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'KeAndre Lambert-Smith',t:'LAC',p:'WR',a:24,k:134,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'John Metchie',t:'CAR',p:'WR',a:24,k:126,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Luke McCaffrey',t:'WAS',p:'WR',a:24,k:125,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Noah Thomas',t:'CIN',p:'WR',a:24,k:122,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Keenan Allen',t:'None',p:'WR',a:24,k:118,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Treylon Burks',t:'WAS',p:'WR',a:24,k:105,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jahdae Walker',t:'CHI',p:'WR',a:24,k:104,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:"Ja'Lynn Polk",t:'NO',p:'WR',a:24,k:99,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'KaVontae Turpin',t:'DAL',p:'WR',a:24,k:94,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Xavier Hutchinson',t:'HOU',p:'WR',a:24,k:92,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Kendrick Bourne',t:'ARI',p:'WR',a:24,k:91,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Roman Wilson',t:'PIT',p:'WR',a:24,k:90,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Mack Hollins',t:'NE',p:'WR',a:24,k:85,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Tai Felton',t:'MIN',p:'WR',a:24,k:64,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jimmy Horn',t:'CAR',p:'WR',a:24,k:61,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Konata Mumpfield',t:'LAR',p:'WR',a:24,k:58,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Arian Smith',t:'NYJ',p:'WR',a:24,k:47,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jordan Whittington',t:'LAR',p:'WR',a:24,k:46,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Xavier Restrepo',t:'TEN',p:'WR',a:24,k:42,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Joshua Palmer',t:'BUF',p:'WR',a:24,k:30,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Kameron Johnson',t:'TB',p:'WR',a:24,k:28,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Tutu Atwell',t:'MIA',p:'WR',a:24,k:27,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Olamide Zaccheaus',t:'ATL',p:'WR',a:24,k:17,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Jacob Cowing',t:'SF',p:'WR',a:24,k:11,ppg25:0,ppg24:0,ppg23:0,g25:0},
  {n:'Efton Chism',t:'NE',p:'WR',a:24,k:8,ppg25:0,ppg24:0,ppg23:0,g25:0},
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

const DC={
  ARI:{QB:['Jacoby Brissett'],RB:['Trey Benson'],WR:['Marvin Harrison Jr.'],TE:['Trey McBride']},
  ATL:{QB:['Michael Penix Jr.','Tua Tagovailoa'],RB:['Bijan Robinson'],WR:['Drake London'],TE:['Kyle Pitts']},
  BAL:{QB:['Lamar Jackson'],RB:['Derrick Henry'],WR:['Zay Flowers'],TE:['Mark Andrews']},
  BUF:{QB:['Josh Allen'],RB:['James Cook'],WR:["D.J. Moore",'Khalil Shakir'],TE:['Dalton Kincaid']},
  CAR:{QB:['Bryce Young'],RB:['Chuba Hubbard'],WR:['Tetairoa McMillan','Jalen Coker'],TE:[]},
  CHI:{QB:['Caleb Williams'],RB:["D'Andre Swift",'Kyle Monangai'],WR:['Rome Odunze','Luther Burden'],TE:['Colston Loveland']},
  CIN:{QB:['Joe Burrow'],RB:['Chase Brown'],WR:["Ja'Marr Chase",'Tee Higgins'],TE:[]},
  CLE:{QB:['Shedeur Sanders'],RB:['Quinshon Judkins','Dylan Sampson'],WR:[],TE:['Harold Fannin Jr.']},
  DAL:{QB:['Dak Prescott'],RB:['Javonte Williams'],WR:['CeeDee Lamb','George Pickens'],TE:['Jake Ferguson']},
  DEN:{QB:['Bo Nix'],RB:['J.K. Dobbins','RJ Harvey'],WR:['Courtland Sutton','Jaylen Waddle'],TE:['Evan Engram']},
  DET:{QB:['Jared Goff'],RB:['Jahmyr Gibbs'],WR:['Amon-Ra St. Brown','Jameson Williams'],TE:['Sam LaPorta']},
  GB:{QB:['Jordan Love'],RB:['Josh Jacobs'],WR:['Christian Watson','Matthew Golden'],TE:['Tucker Kraft']},
  HOU:{QB:['C.J. Stroud'],RB:['David Montgomery','Woody Marks'],WR:['Nico Collins','Jayden Higgins'],TE:['Dalton Schultz']},
  IND:{QB:['Daniel Jones'],RB:['Jonathan Taylor'],WR:['Alec Pierce','Josh Downs'],TE:['Tyler Warren']},
  JAC:{QB:['Trevor Lawrence'],RB:['Bhayshul Tuten'],WR:['Brian Thomas Jr.','Jakobi Meyers','Parker Washington'],TE:['Brenton Strange']},
  KC:{QB:['Patrick Mahomes'],RB:['Kenneth Walker III'],WR:['Rashee Rice','Xavier Worthy'],TE:['Travis Kelce']},
  LV:{QB:['Kirk Cousins'],RB:['Ashton Jeanty'],WR:[],TE:['Brock Bowers']},
  LAC:{QB:['Justin Herbert'],RB:['Omarion Hampton'],WR:['Ladd McConkey','Quentin Johnston','Tre Harris'],TE:['Oronde Gadsden']},
  LAR:{QB:['Matthew Stafford'],RB:['Kyren Williams','Blake Corum'],WR:['Puka Nacua','Davante Adams'],TE:[]},
  MIA:{QB:['Malik Willis'],RB:["De'Von Achane",'Jaylen Wright','Ollie Gordon'],WR:[],TE:[]},
  MIN:{QB:['Kyler Murray','J.J. McCarthy'],RB:['Aaron Jones','Jordan Mason'],WR:['Justin Jefferson','Jordan Addison'],TE:['T.J. Hockenson']},
  NE:{QB:['Drake Maye'],RB:['Rhamondre Stevenson','TreVeyon Henderson'],WR:['Romeo Doubs'],TE:['Hunter Henry']},
  NO:{QB:['Tyler Shough'],RB:['Travis Etienne','Alvin Kamara'],WR:['Chris Olave'],TE:['Juwan Johnson']},
  NYG:{QB:['Jaxson Dart'],RB:['Cam Skattebo'],WR:['Malik Nabers'],TE:['Isaiah Likely']},
  NYJ:{QB:['Geno Smith'],RB:['Breece Hall','Braelon Allen'],WR:['Garrett Wilson'],TE:['Mason Taylor']},
  PHI:{QB:['Jalen Hurts'],RB:['Saquon Barkley'],WR:['A.J. Brown','DeVonta Smith'],TE:['Dallas Goedert']},
  PIT:{QB:['Mason Rudolph'],RB:['Jaylen Warren','Rico Dowdle'],WR:['DK Metcalf','Michael Pittman Jr.'],TE:['Pat Freiermuth']},
  SF:{QB:['Brock Purdy'],RB:['Christian McCaffrey','Isaac Guerendo'],WR:['Mike Evans','Ricky Pearsall'],TE:['George Kittle']},
  SEA:{QB:['Sam Darnold'],RB:['Zach Charbonnet'],WR:['Jaxon Smith-Njigba'],TE:['AJ Barner']},
  TB:{QB:['Baker Mayfield'],RB:['Bucky Irving','Kenneth Gainwell'],WR:['Emeka Egbuka'],TE:['Cade Otton']},
  TEN:{QB:['Cam Ward'],RB:['Tony Pollard','Tyjae Spears'],WR:["Wan'Dale Robinson",'Elic Ayomanor'],TE:['Gunnar Helm']},
  WAS:{QB:['Jayden Daniels'],RB:['Jacory Croskey-Merritt','Rachaad White'],WR:['Terry McLaurin'],TE:['Chigoziem Okonkwo']},
};

const RIPPLE=[
  {n:'DK Metcalf',d:'up',reason:'Rodgers arrives — upgrade over Rudolph, still limited upside at 28',delta:'+5%'},
  {n:'Jaylen Waddle',d:'up',reason:'MIA→DEN Payton system',delta:'+18%'},
  {n:'Bhayshul Tuten',d:'up',reason:'Etienne gone, JAC RB1',delta:'+15%'},
  {n:'Travis Etienne',d:'up',reason:'JAC→NO Moore system, role TBD',delta:'+8%'},
  {n:'Mike Evans',d:'up',reason:'SF WR1 — Aiyuk DNR, Shanahan offense',delta:'+15%'},
  {n:'Ricky Pearsall',d:'down',reason:'SF — Evans arrives as WR1, then Rd2 WR drafted. Pearsall falls to WR3',delta:'-18%'},
  {n:'Kenneth Walker III',d:'up',reason:'KC RB1 — Reid/Mahomes system, elite opportunity',delta:'+8%'},
  {n:'Shedeur Sanders',d:'up',reason:'Named CLE QB1',delta:'+5%'},
  {n:'Harold Fannin Jr.',d:'up',reason:'Clear CLE TE1',delta:'+5%'},
  {n:'Colston Loveland',d:'up',reason:'CHI TE1, Caleb Williams system',delta:'+8%'},
  {n:'Justin Jefferson',d:'up',reason:'MIN — Kyler Murray arrives as QB1, elite weapons upgraded to top-5 dynasty situation',delta:'+12%'},
  {n:'Jordan Addison',d:'up',reason:'MIN — Kyler Murray arrival transforms WR2 role. Addison in prime with elite QB',delta:'+10%'},
  {n:'Javonte Williams',d:'up',reason:'68% snap share in 2025, true DAL bellcow',delta:'+12%'},
  {n:'Kenneth Gainwell',d:'up',reason:'50% snap share as TB RB1',delta:'+10%'},
  {n:'Davante Adams',d:'up',reason:'LAR WR — YPRR 1.98 in 2025, age curve undersold him. Rams offense',delta:'+8%'},
  {n:'Parker Washington',d:'up',reason:'YPRR 2.10 in 2025, steep ascending arc',delta:'+15%'},
  {n:'George Pickens',d:'down',reason:'DAL — franchise tagged 2026, long-term deal unknown. Contract uncertainty is real dynasty risk',delta:'-8%'},
  {n:'CeeDee Lamb',d:'down',reason:'DAL — Pickens as WR2 compresses targets slightly',delta:'-6%'},
  {n:'Jeremiyah Love',d:'up',reason:'ARI #3 — RB1 immediately. Conner re-signed as committee back only',delta:'+28%'},
  {n:'James Conner',d:'down',reason:'ARI — Love drafted #3, Conner now committee back not cut',delta:'-40%'},
  {n:'Trey McBride',d:'up',reason:'ARI — Love draws box safeties, opens middle for McBride',delta:'+10%'},
  {n:'Carnell Tate',d:'up',reason:'TEN #4 — immediate WR1 with Cam Ward at QB',delta:'+28%'},
  {n:'Calvin Ridley',d:'down',reason:'TEN — loses WR1 role to Tate immediately',delta:'-30%'},
  {n:'Cam Ward',d:'up',reason:'TEN — Tate gives Ward an elite WR1 target immediately',delta:'+12%'},
  {n:'Jordyn Tyson',d:'up',reason:'NO #8 — Kellen Moore HC, Tyler Shough showed promise in 2025',delta:'+18%'},
  {n:'Chris Olave',d:'down',reason:'NO — Tyson drafted WR heir, Olave loses target share',delta:'-18%'},
  {n:'Tyler Shough',d:'up',reason:'NO — Tyson gives Shough an explosive WR1 to target',delta:'+15%'},
  {n:'Kenyon Sadiq',d:'up',reason:'NYJ #16 — immediate TE1, no competition. Geno Smith limits upside',delta:'+14%'},
  {n:'Mason Taylor',d:'down',reason:'NYJ — Sadiq takes over TE1 immediately',delta:'-65%'},
  {n:'Tyler Conklin',d:'down',reason:'NYJ — Sadiq drafted, Conklin is cut candidate',delta:'-80%'},
  {n:'Makai Lemon',d:'up',reason:'PHI #20 — Hurts offense. AJ Brown still on roster, WR3 for now',delta:'+10%'},
  {n:'DeVonta Smith',d:'down',reason:'PHI — Lemon added, Brown trade likely June 1. Three-way split coming',delta:'-8%'},
  {n:'KC Concepcion',d:'up',reason:'CLE #24 — WR1 path in thin Browns room',delta:'+15%'},
  {n:'Jerry Jeudy',d:'down',reason:'CLE — demoted to WR2 behind Concepcion, then Boston also added. Three rookie WRs crowding room',delta:'-30%'},
  {n:'Omar Cooper',d:'up',reason:'NYJ #30 — WR2 behind Wilson. Geno Smith limits ceiling',delta:'+10%'},
  {n:'Garrett Wilson',d:'down',reason:'NYJ — Cooper drafted WR2, Wilson remains WR1 but shares',delta:'-8%'},
  {n:'Geno Smith',d:'up',reason:'NYJ — Sadiq + Cooper give Geno two first-round skill players',delta:'+8%'},
  {n:'Jadarian Price',d:'up',reason:'SEA #32 — strong OL, run-heavy scheme. Walker injury history opens door',delta:'+18%'},
  {n:'Zach Charbonnet',d:'down',reason:'SEA — Price arrival further reduces role',delta:'-20%'},
  {n:'Fernando Mendoza',d:'up',reason:'LV #1 — franchise QB. Cousins starts 2026, Mendoza takes over mid-year or 2027',delta:'+25%'},
  {n:'Kirk Cousins',d:'down',reason:'LV — Mendoza #1 overall, Cousins pure bridge with zero dynasty value',delta:'-95%'},
  {n:'Ty Simpson',d:'up',reason:'LAR #13 — SF+ dynasty value long-term. Stafford starts 2026, Simpson is 2028 play',delta:'+10%'},
  {n:'Puka Nacua',d:'down',reason:'LAR — Simpson era eventually coming, Stafford lame duck',delta:'-20%'},
  {n:'Cooper Kupp',d:'down',reason:'SEA WR2 behind JSN — aging, high cap hit, uncertain 2027',delta:'-40%'},
  {n:'Eli Stowers',d:'up',reason:'PHI #54 — TE2 behind Goedert (31). Heir apparent with Hurts throwing',delta:'+22%'},
  {n:'Germie Bernard',d:'up',reason:'PIT #47 — WR3 behind Metcalf + Pittman. Rodgers signed 1yr deal as bridge QB',delta:'+8%'},
  {n:'Denzel Boston',d:'up',reason:'CLE #39 — WR2/3 behind Concepcion. Two rookie WRs competing with Jeudy',delta:'+10%'},
  {n:'Antonio Williams',d:'up',reason:'WAS #71 — Jayden Daniels elite QB, WR2 behind McLaurin',delta:'+18%'},
  {n:'Jayden Daniels',d:'up',reason:'WAS — Williams gives Daniels a WR2 threat opposite McLaurin, small efficiency boost',delta:'+10%'},
  {n:'Terry McLaurin',d:'down',reason:'WAS — Williams drafted WR2, mild target share compression',delta:'-6%'},
  {n:'Zachariah Branch',d:'up',reason:'ATL #79 — WR2 behind London. Penix Jr likely starter, Tua competing in camp',delta:'+10%'},
  {n:'Drake London',d:'up',reason:'ATL — Branch adds another weapon, Penix Jr/Tua competition. Net neutral to slight positive',delta:'+4%'},
  {n:'Tua Tagovailoa',d:'up',reason:'ATL — competing with Penix Jr for starter role. Value contingent on camp outcome',delta:'+6%'},
  {n:'Max Klare',d:'up',reason:'LAR #61 — Rd2 TE in Stafford era pass-heavy system',delta:'+8%'},
  {n:'Drew Allar',d:'up',reason:'PIT #76 — QB competition with Howard, possible long-term franchise QB',delta:'+8%'},
  {n:'Ted Hurst',d:'up',reason:'TB #84 — Baker Mayfield solid QB, open WR depth chart',delta:'+8%'},
  {n:'Eli Raridon',d:'up',reason:'NE #95 — starter-level TE opportunity in thin NE roster',delta:'+6%'},
  {n:'Caleb Douglas',d:'up',reason:'MIA #75 — ample opportunity with thin WR room. Malik Willis at QB limits ceiling',delta:'+8%'},
  {n:'Chris Bell',d:'up',reason:'MIA #94 — same opportunity as Douglas, open WR room to prove himself',delta:'+8%'},
  {n:'Malik Willis',d:'up',reason:'MIA — Bell + Douglas + Kacmarek drafted. Best offensive weapons Willis has had',delta:'+10%'},
  {n:'Kaelon Black',d:'up',reason:'SF #90 — elite OL system but McCaffrey is still the feature back. Backup role only',delta:'+5%'},
  {n:'Zavion Thomas',d:'up',reason:'CHI #89 — DJ Moore returns as WR1, Thomas projects WR2 with upside',delta:'+6%'},
  {n:'Colby Parkinson',d:'down',reason:'LAR — Klare drafted Rd2 #61, impacts Parkinson target share as TE1',delta:'-12%'},
  {n:'Darius Slayton',d:'down',reason:'NYG — Fields drafted Rd3 WR2 behind Nabers, Slayton falls to WR3',delta:'-15%'},
  {n:'Tyjae Spears',d:'down',reason:'TEN — Singleton drafted Rd5 #165, Spears loses carries in backfield',delta:'-18%'},
  {n:'Tony Pollard',d:'down',reason:'TEN — Singleton drafted, Pollard also loses share in three-way backfield',delta:'-12%'},
  {n:'Jaleel McLaughlin',d:'down',reason:'DEN — Coleman drafted Rd4 #109, McLaughlin loses RB depth role',delta:'-20%'},
  {n:'Dallas Goedert',d:'down',reason:'PHI — Stowers drafted Rd2 #54 as heir apparent, Goedert long-term dynasty value hurt',delta:'-15%'},
  {n:'Olamide Zaccheaus',d:'down',reason:'WAS — Williams takes WR2 role opposite McLaurin, Zaccheaus loses target share',delta:'-20%'}
];

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
  const mc=d.miss<=35?'#6ee7b7':d.miss<=50?'#fcd34d':'#fca5a5';
  const hc=d.hit>=65?'#6ee7b7':d.hit>=50?'#7dd3fc':'#718096';
  const ec=d.elite>=25?'#6ee7b7':d.elite>=15?'#7dd3fc':'#718096';
  return`<span style="font-size:9px;display:inline-flex;gap:3px;margin-left:4px">` +
    `<span style="background:#1a202c;border:1px solid #2d3748;border-radius:3px;padding:1px 4px;color:${mc}">M${d.miss}%</span>` +
    `<span style="background:#1a202c;border:1px solid #2d3748;border-radius:3px;padding:1px 4px;color:${hc}">H${d.hit}%</span>` +
    `<span style="background:#1a202c;border:1px solid #2d3748;border-radius:3px;padding:1px 4px;color:${ec}">E${d.elite}%</span>` +
    `</span>`;
}

// ============================================================
// ADDITIVE DELTA PROJECTION FORMULA (v5.6 fix)
// proj = base * age_curve * (1 + capped_delta)
// Each factor contributes a small delta — no multiplicative stacking
// Total delta capped at ±0.20 for projections, ±0.25 for model value
// Model value hard-capped at 9,999 to match market value ceiling
// ============================================================
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
  return d_sys+d_oc+d_role+d_col+d_epa+d_rip+d_qbq+d_ts;
}

function calcProj(pl){
  const e=getEff(pl);
  const age=parseFloat(pl.a)||26;
  const agM=am(pl.p,Math.floor(age));
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

  // Stale-production discount: if player has no 2025 games, prior data
  // is unconfirmed — reduce base to reflect health/role uncertainty
  if(g25===0 && pl.ppg25===0){
    base *= 0.75; // stale discount — production not confirmed this season
  }
  // Rookie override: if ppg25 is set as a forward projection (g25=0, ppg25>0),
  // skip all delta/efficiency adjustments — projection already accounts for situation.
  // Apply only the age curve multiplier since that's position-universal.
  if(g25===0 && pl.ppg25>0){
    const rookieProj = pl.ppg25 * agM;
    const e2=getEff(pl);
    const mv2=mvAsset({...pl,proj:rookieProj,p:pl.p});
    const ciV2=ci(e2.c);
    const rookieResult={...pl,pos:pl.p,t:e2.team,base:pl.ppg25,proj:rookieProj,
      floor:rookieProj*(1-ciV2),ceil:rookieProj*(1+ciV2),mv:mv2,
      gap:mv2-e2.ktc,s:e2.s,c:e2.c,oc:e2.oc,ch:e2.ch,inj:1.0,
      ktcEff:e2.ktc,notes:'',hasOv:true,
      epaSc:1.0,epaFl:false,epaFr:null,epaTr:'flat',
      role:0,roleLabel:'—',sys:50,oppSc:null};
    // Projected rookies (drafted, ppg25 set as a forward projection, no NFL
    // games yet) still get a DELTA Score — every player on the platform has one.
    // calcDynastyScore handles g25:0 correctly: it scores age + the projected
    // production + draft-capital-driven opportunity + contract, capped at the
    // rookie ceiling (DS_ROOKIE_CAP). Without this, projected rookies fell
    // through scoreless while rookies who logged any 2025 snap got a score —
    // an inconsistency (e.g. #33 pick Stribling blank, later picks scored).
    rookieResult.dsScore=calcDynastyScore(rookieResult);
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
  const gl = glOf(pl);
  if(gl && gl.g >= 20){
    if(gl.miss > 65) d_volatility = -0.09;
    else if(gl.miss > 55) d_volatility = -0.06;
    else if(gl.miss > 45) d_volatility = -0.03;
    else if(gl.miss > 40) d_volatility = -0.01;
    if(gl.elite > 30) d_volatility = Math.min(0, d_volatility + 0.03);
    else if(gl.elite > 20) d_volatility = Math.min(0, d_volatility + 0.01);
  }

  // ── RULE 5: INJURY / TIME-DECAY MODIFIER ─────────────────────
  let d_decay = 0;
  if(g25===0 && pl.ppg24===0){
    d_decay = -0.18; // no recent data at all
  } else if(g25===0){
    d_decay = -0.12; // missed all of 2025
  } else if(g25>0 && g25<4){
    d_decay = -0.08;
  } else if(g25>0 && g25<8){
    d_decay = -0.04;
  }
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
  let proj=base*agM*(1+delta)*e.inj;

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
  const mv=mvAsset({...pl,proj,p:pl.p});

  const oppSc=getOppScore(pl.n,pl.p);
  // ktcEff/gap compare against the MARKET in the SELECTED format (pl.kMkt).
  // e.ktc stays the 12-SF anchor the model rescales from via scarcity(); a manual
  // ktc override (OV) is an explicit market value and takes precedence.
  const kMkt=(OV[pl.n]&&OV[pl.n].ktc!==undefined)?e.ktc:(pl.kMkt!=null?pl.kMkt:e.ktc);
  const result={...pl,pos:pl.p,t:e.team,base,proj,floor:proj*(1-ciV),ceil:proj*(1+ciV),mv,
    gap:mv-kMkt,sys:e.s,oc:e.oc,och:e.ch,ci:ciV,inj:e.inj,
    ktcEff:kMkt,notes:e.notes,hasOv:e.hasOv,role:roleData.mult,roleLabel:roleData.label,
    epaSc:epa.sc,epaRaw:epa.raw,epaFl:epa.fl,epaFr:epa.fr,epaTr:epa.tr,
    ef25:epa.ef25,ef24:epa.ef24,e25:epa.e25,e24:epa.e24,e23:epa.e23,e22:epa.e22,oppSc};
  result.dsScore=calcDynastyScore(result);
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
// Option B calibration (June 2026): correct the one-directional penalty bias
// ONLY where it exists — players whose RAW value is below market. A raw value
// already at/above market earned it despite the penalties, so it is NOT scaled
// up (a flat multiplier used to stack conviction, e.g. Walker 6.8k→8.0k). raw
// and mkt are both anchor-basis (pl.k or an OV override).
function applyCenter(raw, mkt){
  if(MV_CENTER===1) return raw;            // pass 1 / no center yet
  if(raw>=mkt && mkt>0) return raw;        // already above market — no bias to correct
  return raw/MV_CENTER;
}
function computeMvCenter(){
  // Call ONLY while MV_CENTER===1 (raw basis) — mvAssetBase must return raw here.
  const rs=[];
  if(typeof COMP!=='undefined'){
    for(const p of COMP){
      if(((p.g25||0)+(p.g24||0)+(p.g23||0))===0) continue;  // same gate as vTag's "no data"
      const mkt=(OV[p.n]&&OV[p.n].ktc!=null)?OV[p.n].ktc:p.k;
      rs.push(mvAssetBase(p)/Math.max(mkt,1));
    }
  }
  if(!rs.length) return 1;
  rs.sort(function(a,b){return a-b;});
  let c=rs[Math.floor(rs.length/2)];
  if(c<0.6||c>1.3){
    console.warn('[DELTA] model-value population center out of range ('+c.toFixed(3)+') — falling back to 1.0 (raw); check market/stats data');
    c=1;
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
    const expiresIn=ctEntry.end-2026;
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
  if(g25h<14&&ppg24h===0&&(pl.a||30)>22) d_inj_hist-=0.03;
  if(g25h<14&&ppg23h===0&&ppg24h===0&&(pl.a||30)>23) d_inj_hist-=0.02;
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
  return Math.min(19999,Math.round(e.ktc*agM*(1+mvDelta)*e.inj));
}

const CONTRACTS=[
  // NEW ORLEANS SAINTS
  {n:'Travis Etienne',pos:'RB',team:'NO',aav:12000000,total:48000000,end:2029,note:'Signed as RB1 through 2029'},
  {n:'Alvin Kamara',pos:'RB',team:'NO',aav:12250000,total:24500000,end:2026,note:'Final contract — walk year 2026'},
  {n:'Chris Olave',pos:'WR',team:'NO',aav:4817969,total:19271874,end:2026,note:'Cheap deal expiring — extension or FA looms'},
  {n:'Juwan Johnson',pos:'TE',team:'NO',aav:10250000,total:30750000,end:2027,note:'Locked in as TE1 through 2027'},

  // NEW YORK GIANTS
  {n:'Malik Nabers',pos:'WR',team:'NYG',aav:7301938,total:29207750,end:2028,note:'Locked in as WR1 through 2028'},
  {n:'Jaxson Dart',pos:'QB',team:'NYG',aav:4244482,total:16977927,end:2029,note:'Franchise QB of the future'},
  {n:'Isaiah Likely',pos:'TE',team:'NYG',aav:13333333,total:40000000,end:2028,note:'Major investment — clear TE1 role'},
  {n:'Cam Skattebo',pos:'RB',team:'NYG',aav:1318260,total:5273040,end:2028,note:'Cheap rookie deal, developing RB1'},
  {n:'Theo Johnson',pos:'TE',team:'NYG',aav:1212859,total:4851436,end:2027,note:'Backup TE on affordable deal'},
  // NEW YORK JETS
  {n:'Garrett Wilson',pos:'WR',team:'NYJ',aav:32500000,total:130000000,end:2030,note:'Elite WR1 locked up long term'},
  {n:'Breece Hall',pos:'RB',team:'NYJ',aav:15250000,total:45750000,end:2028,note:'3yr/$45.75M signed May 2026 — $29M guaranteed'},
  {n:'Mason Taylor',pos:'TE',team:'NYJ',aav:2616547,total:10466187,end:2028,note:'Young TE1 locked in through 2028'},
  {n:'Braelon Allen',pos:'RB',team:'NYJ',aav:1137177,total:4548708,end:2027,note:'Cheap ascending RB on rookie deal'},
  {n:'Geno Smith',pos:'QB',team:'NYJ',aav:3300000,total:3300000,end:2026,note:'1yr stop-gap — NYJ will move on'},
  // PHILADELPHIA EAGLES
  {n:'Jalen Hurts',pos:'QB',team:'PHI',aav:51000000,total:255000000,end:2028,note:'Franchise locked through 2028'},
  {n:'A.J. Brown',pos:'WR',team:'PHI',aav:32000000,total:96000000,end:2029,note:'Elite WR1 locked up long term'},
  {n:'DeVonta Smith',pos:'WR',team:'PHI',aav:25000000,total:75000000,end:2028,note:'Locked in as WR2 through 2028'},
  {n:'Saquon Barkley',pos:'RB',team:'PHI',aav:20600000,total:41200000,end:2028,note:'2 years left — sell window opening'},
  {n:'Dallas Goedert',pos:'TE',team:'PHI',aav:7000000,total:7000000,end:2026,note:'Walk year — PHI may extend or move on'},
  {n:'Will Shipley',pos:'RB',team:'PHI',aav:1184241,total:4736964,end:2027,note:'Cheap handcuff/developing back'},
  {n:'Ricky Pearsall',pos:'WR',team:'SF',aav:3134600,total:12538398,end:2028,note:'SF committed through 2028 — ascending'},
  // PITTSBURGH STEELERS
  {n:'DK Metcalf',pos:'WR',team:'PIT',aav:33000000,total:132000000,end:2029,note:'Elite WR1 locked through 2029'},
  {n:'Michael Pittman Jr.',pos:'WR',team:'PIT',aav:17500000,total:35000000,end:2029,note:'2yr deal but through 2029'},
  {n:'Pat Freiermuth',pos:'TE',team:'PIT',aav:12100000,total:48400000,end:2028,note:'Locked in as TE1 through 2028'},
  {n:'Rico Dowdle',pos:'RB',team:'PIT',aav:6125000,total:12250000,end:2027,note:'2yr deal — RB1 committed short term'},
  {n:'Jaylen Warren',pos:'RB',team:'PIT',aav:5952000,total:11904000,end:2027,note:'2yr deal alongside Dowdle'},
  {n:'Mason Rudolph',pos:'QB',team:'PIT',aav:3750000,total:7500000,end:2026,note:'Ends 2026 — PIT will upgrade at QB'},
  // HOUSTON TEXANS
  {n:'Nico Collins',pos:'WR',team:'HOU',aav:24250000,total:72750000,end:2027,note:'HOU WR1 locked through 2027'},
  {n:'C.J. Stroud',pos:'QB',team:'HOU',aav:9069811,total:36279243,end:2027,note:'Franchise QB through 2027 — extension likely'},
    {n:'Jayden Higgins',pos:'WR',team:'HOU',aav:2925206,total:11700824,end:2028,note:'Locked rookie deal through 2028'},
  {n:'Dalton Schultz',pos:'TE',team:'HOU',aav:12600000,total:12600000,end:2027,note:'Expiring 2027 — walk year coming'},
  {n:'Tank Dell',pos:'WR',team:'HOU',aav:1422276,total:5689104,end:2026,note:'Walk year — extension or FA looms'},
  {n:'Woody Marks',pos:'RB',team:'HOU',aav:1300942,total:5203768,end:2028,note:'Cheap RB on 4yr rookie deal'},
  // ARIZONA CARDINALS
  {n:'Trey McBride',pos:'TE',team:'ARI',aav:19000000,total:76000000,end:2029,note:'Elite TE1 locked through 2029 — long-term buy'},
  {n:'Marvin Harrison Jr.',pos:'WR',team:'ARI',aav:8843686,total:35374742,end:2028,note:'Locked as WR1 through 2028'},
  {n:'Trey Benson',pos:'RB',team:'ARI',aav:1514902,total:6059606,end:2027,note:'Cheap rookie deal through 2027'},
  {n:'James Conner',pos:'RB',team:'ARI',aav:3000000,total:3000000,end:2026,note:'Walk year — final contract at ARI'},
  // CAROLINA PANTHERS
  {n:'Bryce Young',pos:'QB',team:'CAR',aav:9488768,total:37955071,end:2027,note:'CAR franchise QB locked through 2027'},
  {n:'Chuba Hubbard',pos:'RB',team:'CAR',aav:8300000,total:33200000,end:2028,note:'Locked through 2028 — role declining per target data'},
  {n:'Tetairoa McMillan',pos:'WR',team:'CAR',aav:6982598,total:27930390,end:2028,note:'Locked WR1 through 2028 — ascending rookie'},
  {n:'Jonathon Brooks',pos:'RB',team:'CAR',aav:2104271,total:8417082,end:2027,note:'Cheap rookie deal — monitor health'},
  {n:'Xavier Legette',pos:'WR',team:'CAR',aav:3089294,total:12357176,end:2028,note:'Locked WR2 through 2028'},
  {n:'Jalen Coker',pos:'WR',team:'CAR',aav:1075000,total:1075000,end:2026,note:'Walk year — cheap rookie deal expiring 2026'},
  // WASHINGTON COMMANDERS
  {n:'Terry McLaurin',pos:'WR',team:'WAS',aav:32333333,total:97000000,end:2028,note:'Elite WR1 locked through 2028'},
  {n:'Jayden Daniels',pos:'QB',team:'WAS',aav:9436663,total:37746650,end:2028,note:'Franchise QB locked — ascending'},
  {n:'Chigoziem Okonkwo',pos:'TE',team:'WAS',aav:9000000,total:27000000,end:2028,note:'WAS TE1 locked through 2028'},
  {n:'Jacory Croskey-Merritt',pos:'RB',team:'WAS',aav:1076357,total:4305428,end:2028,note:'Cheap ascending RB on rookie deal'},
  // TENNESSEE TITANS
  {n:'Calvin Ridley',pos:'WR',team:'TEN',aav:23000000,total:92000000,end:2027,note:'WR1 locked through 2027'},
  {n:"Wan'Dale Robinson",pos:'WR',team:'TEN',aav:17500000,total:70000000,end:2029,note:'Locked WR2 through 2029 — great value'},
  {n:'Cam Ward',pos:'QB',team:'TEN',aav:12209905,total:48839618,end:2029,note:'Franchise rookie QB locked through 2029'},
  {n:'Tony Pollard',pos:'RB',team:'TEN',aav:7250000,total:21750000,end:2026,note:'Walk year — confirmed final season in TEN'},
  {n:'Tyjae Spears',pos:'RB',team:'TEN',aav:1372654,total:5490616,end:2026,note:'Expiring 2026 — cheap handcuff'},
  {n:'Gunnar Helm',pos:'TE',team:'TEN',aav:1293227,total:5172908,end:2028,note:'Locked TE1 through 2028 on rookie deal'},
  {n:'Elic Ayomanor',pos:'WR',team:'TEN',aav:1216454,total:4865816,end:2028,note:'Cheap ascending WR on rookie deal'},
  // BUFFALO BILLS
  {n:'Josh Allen',pos:'QB',team:'BUF',aav:55000000,total:330000000,end:2030,note:'Generational deal — locked through 2030'},
  {n:'D.J. Moore',pos:'WR',team:'BUF',aav:27500000,total:110000000,end:2029,note:'Elite WR1 locked through 2029'},
  {n:'Khalil Shakir',pos:'WR',team:'BUF',aav:13264500,total:53058000,end:2029,note:'Locked WR2 through 2029 — ascending'},
  {n:'James Cook',pos:'RB',team:'BUF',aav:11500000,total:46000000,end:2029,note:'4yr/$46M locked through 2029 — role secure'},
  {n:'Keon Coleman',pos:'WR',team:'BUF',aav:2518565,total:10074258,end:2027,note:'Cheap rookie deal through 2027'},
  {n:'Dalton Kincaid',pos:'TE',team:'BUF',aav:3356756,total:13427023,end:2027,note:'Through 2027 — competing for role'},
  // BALTIMORE RAVENS
  {n:'Lamar Jackson',pos:'QB',team:'BAL',aav:52000000,total:260000000,end:2027,note:'Generational deal locked through 2027'},
  {n:'Mark Andrews',pos:'TE',team:'BAL',aav:13089000,total:39267000,end:2028,note:'Locked through 2028 — 3yr deal'},
  {n:'Zay Flowers',pos:'WR',team:'BAL',aav:3509109,total:14036434,end:2027,note:'Cheap deal through 2027 — extension coming given ascending role'},
  {n:'Derrick Henry',pos:'RB',team:'BAL',aav:15000000,total:30000000,end:2027,note:'2yr deal — sell window opening'},
  {n:'Rashod Bateman',pos:'WR',team:'BAL',aav:12250000,total:36750000,end:2029,note:'Locked BAL WR2 through 2029'},
  // ATLANTA FALCONS
  {n:'Tua Tagovailoa',pos:'QB',team:'ATL',aav:53100000,total:212400000,end:2028,note:'Franchise QB locked through 2028'},
  {n:'Bijan Robinson',pos:'RB',team:'ATL',aav:5489634,total:21958535,end:2027,note:'Locked through 2027 — cheap deal, RB1 secure'},
  {n:'Drake London',pos:'WR',team:'ATL',aav:5383617,total:21534468,end:2026,note:'WALK YEAR 2026 — ATL must extend or lose WR1'},
  {n:'Kyle Pitts',pos:'TE',team:'ATL',aav:15045000,total:15045000,end:2026,note:'WALK YEAR 2026 — extension or departure imminent'},
  // TAMPA BAY BUCCANEERS
  {n:'Baker Mayfield',pos:'QB',team:'TB',aav:33333333,total:100000000,end:2026,note:'WALK YEAR 2026 — TB must extend or move on'},
  {n:'Kenneth Gainwell',pos:'RB',team:'TB',aav:7000000,total:14000000,end:2027,note:'2yr/$14M — committed RB role confirmed'},
  {n:'Emeka Egbuka',pos:'WR',team:'TB',aav:4543183,total:18172730,end:2029,note:'Locked WR through 2029 — ascending'},
  {n:'Bucky Irving',pos:'RB',team:'TB',aav:1187888,total:4751552,end:2027,note:'Cheap ascending RB through 2027'},
  {n:'Cade Otton',pos:'TE',team:'TB',aav:10000000,total:30000000,end:2028,note:'Locked TE1 through 2028'},
  // SEATTLE SEAHAWKS
  {n:'Cooper Kupp',pos:'WR',team:'SEA',aav:15000000,total:45000000,end:2027,note:'3yr/$45M — SEA WR2 behind JSN, uncertain beyond 2026'},
  {n:'Jaxon Smith-Njigba',pos:'WR',team:'SEA',aav:42150000,total:168600000,end:2031,note:'Franchise deal — locked through 2031, buy at any cost'},
  {n:'Sam Darnold',pos:'QB',team:'SEA',aav:33500000,total:100500000,end:2027,note:'3yr committed starter through 2027'},
  {n:'Rashid Shaheed',pos:'WR',team:'SEA',aav:17000000,total:51000000,end:2028,note:'Locked WR2 through 2028'},
  {n:'Zach Charbonnet',pos:'RB',team:'SEA',aav:1719020,total:6876079,end:2026,note:'Expiring 2026 — SEA RB situation murky'},
  {n:'George Kittle',pos:'TE',team:'SF',aav:19100000,total:76400000,end:2029,note:'Elite TE1 locked up through 2029'},
  {n:'Christian McCaffrey',pos:'RB',team:'SF',aav:19000000,total:38000000,end:2027,note:'Only 2 years left — sell window opening'},
  {n:'Mike Evans',pos:'WR',team:'SF',aav:14133333,total:42400000,end:2028,note:'3yr deal — committed as SF WR2'},
  // DALLAS COWBOYS
  {n:'Dak Prescott',pos:'QB',team:'DAL',aav:60000000,total:240000000,end:2028,note:'Locked through 2028'},
  {n:'CeeDee Lamb',pos:'WR',team:'DAL',aav:34000000,total:136000000,end:2029,note:'Elite WR1 locked through 2029'},
  {n:'Jake Ferguson',pos:'TE',team:'DAL',aav:12500000,total:50000000,end:2029,note:'DAL TE1 locked through 2029'},
  {n:'George Pickens',pos:'WR',team:'DAL',aav:27298000,total:27298000,end:2026,note:'WALK YEAR 2026 — DAL must extend WR2'},
  {n:'Javonte Williams',pos:'RB',team:'DAL',aav:8000000,total:24000000,end:2028,note:'3yr/$24M locked — role security confirmed'},
  // DENVER BRONCOS
    {n:'Jaylen Waddle',pos:'WR',team:'DEN',aav:28250000,total:84750000,end:2028,note:'Locked WR2 through 2028 — big investment'},
  {n:'Bo Nix',pos:'QB',team:'DEN',aav:4653292,total:18613166,end:2028,note:'Franchise QB locked through 2028'},
  {n:'RJ Harvey',pos:'RB',team:'DEN',aav:1839920,total:7359680,end:2028,note:'Cheap ascending RB locked through 2028'},
  {n:'Troy Franklin',pos:'WR',team:'DEN',aav:1218709,total:4874836,end:2027,note:'Cheap WR on rookie deal through 2027'},
  {n:'Evan Engram',pos:'TE',team:'DEN',aav:11500000,total:23000000,end:2026,note:'Walk year — expiring 2026'},
  {n:'J.K. Dobbins',pos:'RB',team:'DEN',aav:8000000,total:16000000,end:2027,note:'2yr deal — RB1 committed short term'},
  // GREEN BAY PACKERS
  {n:'Jordan Love',pos:'QB',team:'GB',aav:55000000,total:220000000,end:2028,note:'Franchise QB locked through 2028'},
  {n:'Josh Jacobs',pos:'RB',team:'GB',aav:12000000,total:48000000,end:2027,note:'Locked RB1 through 2027'},
      {n:'Tucker Kraft',pos:'TE',team:'GB',aav:1384484,total:5537934,end:2026,note:'Expiring 2026 — extension expected'},
  {n:'Jayden Reed',pos:'WR',team:'GB',aav:1795195,total:7180778,end:2026,note:'Expiring 2026 — extension coming'},
  // LOS ANGELES CHARGERS
  {n:'Justin Herbert',pos:'QB',team:'LAC',aav:52500000,total:262500000,end:2029,note:'Franchise locked through 2029'},
  {n:'Omarion Hampton',pos:'RB',team:'LAC',aav:4443616,total:17774464,end:2029,note:'Cheap ascending RB locked through 2029'},
  {n:'Quentin Johnston',pos:'WR',team:'LAC',aav:3547195,total:14188778,end:2027,note:'Locked WR through 2027'},
  {n:'Ladd McConkey',pos:'WR',team:'LAC',aav:2498797,total:9995186,end:2027,note:'Cheap ascending WR through 2027'},
    // LOS ANGELES RAMS
  {n:'Matthew Stafford',pos:'QB',team:'LAR',aav:42000000,total:84000000,end:2026,note:'Walk year — LAR QB murky after 2026'},
  {n:'Davante Adams',pos:'WR',team:'LAR',aav:22000000,total:44000000,end:2026,note:'WALK YEAR 2026 — final deal'},
  {n:'Kyren Williams',pos:'RB',team:'LAR',aav:11000000,total:33000000,end:2028,note:'3yr/$33M locked through 2028'},
  {n:'Puka Nacua',pos:'WR',team:'LAR',aav:1021244,total:4084977,end:2026,note:'Expiring 2026 — extension critical'},
  {n:'Blake Corum',pos:'RB',team:'LAR',aav:1440941,total:5763762,end:2027,note:'Cheap RB on rookie deal'},
  // MIAMI DOLPHINS
  {n:'Malik Willis',pos:'QB',team:'MIA',aav:22500000,total:67500000,end:2028,note:'3yr committed starter through 2028'},
  {n:'Jaylen Wright',pos:'RB',team:'MIA',aav:1195005,total:4780020,end:2027,note:'Cheap ascending RB through 2027'},
  {n:'Ollie Gordon',pos:'RB',team:'MIA',aav:1118166,total:4472664,end:2028,note:'Cheap RB on rookie deal'},
  // DETROIT LIONS
  {n:'Jared Goff',pos:'QB',team:'DET',aav:53000000,total:212000000,end:2028,note:'Franchise QB locked through 2028'},
  {n:'Amon-Ra St. Brown',pos:'WR',team:'DET',aav:30002500,total:120010000,end:2028,note:'Elite WR1 locked through 2028'},
    {n:'Jahmyr Gibbs',pos:'RB',team:'DET',aav:4461283,total:17845130,end:2027,note:'Cheap RB1 on rookie deal — buy before extension'},
    {n:'Isaac TeSlaa',pos:'WR',team:'DET',aav:1666113,total:6664452,end:2028,note:'Cheap ascending WR locked through 2028'},
  // LAS VEGAS RAIDERS
  {n:'Ashton Jeanty',pos:'RB',team:'LV',aav:8973953,total:35895812,end:2029,note:'Locked RB1 through 2029 — franchise piece'},
  {n:'Brock Bowers',pos:'TE',team:'LV',aav:4534696,total:18138784,end:2028,note:'Cheap TE1 on rookie deal — extension imminent'},
  {n:'Jalen Nailor',pos:'WR',team:'LV',aav:11676667,total:35030000,end:2028,note:'LV WR1 locked through 2028'},
  // CLEVELAND BROWNS
  {n:'Quinshon Judkins',pos:'RB',team:'CLE',aav:2850534,total:11402136,end:2028,note:'Cheap ascending RB locked through 2028'},
  {n:'Harold Fannin Jr.',pos:'TE',team:'CLE',aav:1685722,total:6742886,end:2028,note:'Cheap TE1 on rookie deal through 2028'},
  {n:'Shedeur Sanders',pos:'QB',team:'CLE',aav:1161845,total:4647380,end:2028,note:'Cheap franchise QB on rookie deal'},
  {n:'Dylan Sampson',pos:'RB',team:'CLE',aav:1282641,total:5130564,end:2028,note:'Cheap ascending RB through 2028'},
  // KANSAS CITY CHIEFS
  {n:'Patrick Mahomes',pos:'QB',team:'KC',aav:45000000,total:450000000,end:2031,note:'Generational deal — locked through 2031'},
  {n:'Kenneth Walker III',pos:'RB',team:'KC',aav:14350000,total:43050000,end:2028,note:'3yr/$43M — major RB1 investment'},
  {n:"De'Von Achane",pos:'RB',team:'MIA',aav:16000000,total:64000000,end:2029,note:'4yr/$64M signed May 2026'},
  {n:'Aaron Rodgers',pos:'QB',team:'PIT',aav:4000000,total:4000000,end:2026,note:'1yr bridge deal at 42'},
  {n:'Travis Kelce',pos:'TE',team:'KC',aav:12000000,total:12000000,end:2028,note:'Walk year but likely extends — monitor'},
  {n:'Xavier Worthy',pos:'WR',team:'KC',aav:3447566,total:13790264,end:2028,note:'Cheap ascending WR through 2028'},
  {n:'Rashee Rice',pos:'WR',team:'KC',aav:1623802,total:6495208,end:2026,note:'Expiring 2026 — extension coming given ascending role'},
  // MINNESOTA VIKINGS
  {n:'Justin Jefferson',pos:'WR',team:'MIN',aav:35000000,total:140000000,end:2028,note:'Elite WR1 locked through 2028'},
  {n:'Kyler Murray',pos:'QB',team:'MIN',aav:1300000,total:1300000,end:2026,note:'1yr bridge deal — expected QB1 starter in 2026'},
  {n:'T.J. Hockenson',pos:'TE',team:'MIN',aav:16500000,total:66000000,end:2026,note:'WALK YEAR 2026 — confirms Fading signal'},
  {n:'J.J. McCarthy',pos:'QB',team:'MIN',aav:5463699,total:21854796,end:2028,note:'Franchise QB locked through 2028'},
  {n:'Jordan Addison',pos:'WR',team:'MIN',aav:3432935,total:13731739,end:2027,note:'Cheap WR locked through 2027'},
  {n:'Aaron Jones',pos:'RB',team:'MIN',aav:5560000,total:5560000,end:2026,note:'WALK YEAR 2026 — final contract at MIN'},
  {n:'Jordan Mason',pos:'RB',team:'MIN',aav:5250000,total:10500000,end:2026,note:'Expiring 2026 — short runway'},
  // CINCINNATI BENGALS
  {n:'Joe Burrow',pos:'QB',team:'CIN',aav:55000000,total:275000000,end:2029,note:'Franchise locked through 2029'},
  {n:"Ja'Marr Chase",pos:'WR',team:'CIN',aav:40250000,total:161000000,end:2029,note:'Elite WR1 locked through 2029'},
  {n:'Tee Higgins',pos:'WR',team:'CIN',aav:28750000,total:115000000,end:2028,note:'Locked WR2 through 2028'},
  {n:'Chase Brown',pos:'RB',team:'CIN',aav:1031539,total:4126156,end:2026,note:'Expiring 2026 — CIN RB1 extension needed'},
  // JACKSONVILLE JAGUARS
  {n:'Trevor Lawrence',pos:'QB',team:'JAC',aav:55000000,total:275000000,end:2030,note:'Franchise locked through 2030'},
  {n:'Jakobi Meyers',pos:'WR',team:'JAC',aav:20000000,total:60000000,end:2028,note:'Locked WR1 through 2028'},
  {n:'Travis Hunter',pos:'WR',team:'JAC',aav:11662282,total:46649126,end:2028,note:'Locked WR2 through 2028 — ascending rookie'},
  {n:'Brian Thomas Jr.',pos:'WR',team:'JAC',aav:3664995,total:14659978,end:2028,note:'Cheap WR locked through 2028'},
  {n:'Bhayshul Tuten',pos:'RB',team:'JAC',aav:1319132,total:5276528,end:2028,note:'Cheap ascending RB through 2028'},
  {n:'Parker Washington',pos:'WR',team:'JAC',aav:1008066,total:4032264,end:2026,note:'Expiring 2026 — extension needed'},
  {n:'Brenton Strange',pos:'TE',team:'JAC',aav:1528583,total:6114333,end:2026,note:'Expiring 2026'},
  // CHICAGO BEARS
  {n:'Caleb Williams',pos:'QB',team:'CHI',aav:9871515,total:39486058,end:2028,note:'Franchise QB locked through 2028'},
  {n:'Colston Loveland',pos:'TE',team:'CHI',aav:6659002,total:26636008,end:2029,note:'Locked TE1 through 2029 — ascending'},
  {n:"D'Andre Swift",pos:'RB',team:'CHI',aav:8000000,total:24000000,end:2026,note:'WALK YEAR 2026 — CHI RB1 expiring'},
  {n:'Rome Odunze',pos:'WR',team:'CHI',aav:5681125,total:22724500,end:2028,note:'Locked WR through 2028 — ascending'},
  {n:'Luther Burden',pos:'WR',team:'CHI',aav:2741008,total:10964030,end:2028,note:'Cheap ascending WR locked through 2028'},
  {n:'Cole Kmet',pos:'TE',team:'CHI',aav:12500000,total:50000000,end:2027,note:'Locked TE through 2027'},
  // NEW ENGLAND PATRIOTS
  {n:'Romeo Doubs',pos:'WR',team:'NE',aav:17000000,total:68000000,end:2029,note:'Locked NE WR1 through 2029 — major investment'},
  {n:'Drake Maye',pos:'QB',team:'NE',aav:9159941,total:36639764,end:2028,note:'Franchise QB locked through 2028'},
  {n:'Rhamondre Stevenson',pos:'RB',team:'NE',aav:9000000,total:36000000,end:2028,note:'Locked RB1 through 2028'},
  {n:'Hunter Henry',pos:'TE',team:'NE',aav:9000000,total:27000000,end:2026,note:'Walk year — NE TE1 expiring 2026'},
  {n:'TreVeyon Henderson',pos:'RB',team:'NE',aav:2785809,total:11143234,end:2028,note:'Cheap ascending RB locked through 2028'},
  {n:'Jonathan Taylor',pos:'RB',team:'IND',aav:14000000,total:42000000,end:2026,note:'WALK YEAR 2026 — IND must extend or sell'},
  {n:'Tyler Warren',pos:'TE',team:'IND',aav:5240163,total:20960650,end:2029,note:'Locked TE1 through 2029 — IND committed'},
  {n:'Josh Downs',pos:'WR',team:'IND',aav:1380115,total:5520459,end:2026,note:'Expiring 2026 — extension likely'},
  // Batch — contracts from screenshots
  {n:'AJ Barner',pos:'TE',team:'SEA',aav:1193777,total:4775108,end:2027,note:'Cheap rookie deal through 2027 — ascending SEA TE1'},
  {n:'Kyle Monangai',pos:'RB',team:'CHI',aav:1082035,total:4328140,end:2028,note:'Cheap rookie deal through 2028 — CHI ascending RB'},
  {n:'Matthew Golden',pos:'WR',team:'GB',aav:4393835,total:17575338,end:2029,note:'Fully guaranteed rookie deal through 2029 — locked up'},
  {n:'David Montgomery',pos:'RB',team:'HOU',aav:8250000,total:16500000,end:2027,note:'2yr/$16.5M — HOU RB1 committed through 2027'},
  {n:'Tyrone Tracy',pos:'RB',team:'NYG',aav:1076588,total:4306352,end:2027,note:'Cheap rookie deal through 2027 — NYG ascending RB'},
  {n:'Jameson Williams',pos:'WR',team:'DET',aav:26666667,total:80000000,end:2029,note:'Major extension — locked through 2029 as DET WR2'},
  {n:'Oronde Gadsden',pos:'TE',team:'LAC',aav:1143509,total:4574036,end:2028,note:'Cheap rookie deal through 2028 — ascending LAC TE1'},
  {n:'Brock Purdy',pos:'QB',team:'SF',aav:53000000,total:265000000,end:2030,note:'Franchise QB locked through 2030'},
  {n:'Tyler Shough',pos:'QB',team:'NO',aav:2701180,total:10804721,end:2028,note:'Cheap rookie QB deal through 2028 — fully guaranteed'},
  {n:'Courtland Sutton',pos:'WR',team:'DEN',aav:23000000,total:92000000,end:2029,note:'Locked through 2029 — potential out after 2026 worth monitoring'},
  {n:'Daniel Jones',pos:'QB',team:'IND',aav:44000000,total:88000000,end:2027,note:'2yr/$88M transition tag extension — IND QB1'},
  {n:'Alec Pierce',pos:'WR',team:'IND',aav:28500000,total:114000000,end:2029,note:'Major extension — IND WR1 locked through 2029'},
  {n:'Christian Watson',pos:'WR',team:'GB',aav:11000000,total:11000000,end:2026,note:'WALK YEAR 2026 — 1yr incentive-laden deal, GB must re-sign'},
  // 2026 Draft Rounds 4-7
  {n:'Brenen Thompson',pos:'WR',team:'LAC',aav:980000,total:3920000,end:2029,note:'Rd4 #105 — LAC speed WR, 4.26 40'},
  {n:'Jonah Coleman',pos:'RB',team:'DEN',aav:960000,total:3840000,end:2029,note:'Rd4 #109 — DEN RB, Payton system'},
  {n:'Cade Klubnik',pos:'QB',team:'NYJ',aav:955000,total:3820000,end:2029,note:'Rd4 #110 — NYJ backup QB, developmental'},
  {n:'Elijah Sarratt',pos:'WR',team:'BAL',aav:935000,total:3740000,end:2029,note:'Rd4 #115 — BAL depth WR'},
  {n:'Kaden Wetjen',pos:'WR',team:'PIT',aav:920000,total:3680000,end:2029,note:'Rd4 #121 — PIT kick returner/depth WR'},
  {n:'Mike Washington Jr.',pos:'RB',team:'LV',aav:915000,total:3660000,end:2029,note:'Rd4 #122 — LV RB, Mendoza era backup'},
  {n:'Skyler Bell',pos:'WR',team:'BUF',aav:910000,total:3640000,end:2029,note:'Rd4 #125 — BUF depth WR, Bills offense'},
  {n:'Matthew Hibner',pos:'TE',team:'BAL',aav:900000,total:3600000,end:2029,note:'Rd4 #133 — BAL blocking TE'},
  {n:'Bryce Lance',pos:'WR',team:'NO',aav:890000,total:3560000,end:2029,note:'Rd4 #136 — NO depth WR, FCS background'},
  {n:'Colbie Young',pos:'WR',team:'CIN',aav:880000,total:3520000,end:2029,note:'Rd4 #140 — CIN depth WR'},
  {n:'Reggie Virgil',pos:'WR',team:'ARI',aav:870000,total:3480000,end:2029,note:'Rd5 #143 — ARI depth WR, one-year wonder concern'},
  {n:'Justin Joly',pos:'TE',team:'DEN',aav:855000,total:3420000,end:2029,note:'Rd5 #152 — DEN most proven TE producer in class'},
  {n:'Emmett Johnson',pos:'RB',team:'KC',aav:840000,total:3360000,end:2029,note:'Rd5 #161 — KC RB, Mahomes system'},
  {n:'Nicholas Singleton',pos:'RB',team:'TEN',aav:835000,total:3340000,end:2029,note:'Rd5 #165 — TEN RB behind Ward/Tate offense'},
  {n:'Kendrick Law',pos:'WR',team:'DET',aav:825000,total:3300000,end:2029,note:'Rd5 #168 — DET offense elite but thin production profile'},
  {n:'Adam Randall',pos:'RB',team:'BAL',aav:820000,total:3280000,end:2029,note:'Rd5 #174 — BAL RB, converted WR athlete'},
  {n:'Kevin Coleman Jr.',pos:'WR',team:'MIA',aav:815000,total:3260000,end:2029,note:'Rd5 #177 — MIA WR, Willis at QB limits ceiling'},
  {n:'Cole Payton',pos:'QB',team:'PHI',aav:810000,total:3240000,end:2029,note:'Rd5 #178 — PHI backup QB, FCS background'},
  {n:'Cyrus Allen',pos:'WR',team:'KC',aav:805000,total:3220000,end:2029,note:'Rd5 #176 — KC WR, Mahomes creates opportunity'},
  {n:'Taylen Green',pos:'QB',team:'CLE',aav:795000,total:3180000,end:2029,note:'Rd6 #182 — CLE backup QB'},
  {n:'Kaytron Allen',pos:'RB',team:'WAS',aav:785000,total:3140000,end:2029,note:'Rd6 #187 — WAS depth RB'},
  {n:'Barion Brown',pos:'WR',team:'NO',aav:780000,total:3120000,end:2029,note:'Rd6 #190 — NO depth WR, Olave+Tyson limit ceiling'},
  {n:'Demond Claiborne',pos:'RB',team:'MIN',aav:775000,total:3100000,end:2029,note:'Rd6 #198 — MIN depth RB'},
  {n:'Deion Burks',pos:'WR',team:'IND',aav:760000,total:3040000,end:2029,note:'Rd7 #254 — IND WR, slid from projected Rd3'},
  {n:'Garrett Nussmeier',pos:'QB',team:'KC',aav:755000,total:3020000,end:2029,note:'Rd7 #249 — KC backup QB behind Mahomes'},
  {n:'Seth McGowan',pos:'RB',team:'IND',aav:750000,total:3000000,end:2029,note:'Rd7 #237 — IND depth RB'},
  {n:'Caleb Douglas',pos:'WR',team:'MIA',aav:1390000,total:5560000,end:2029,note:'Rd3 #75 — 4yr rookie deal. MIA WR — Malik Willis at QB (Tua moved to ATL). Low-volume situation hurts dynasty ceiling significantly'},
  {n:'Zavion Thomas',pos:'WR',team:'CHI',aav:1310000,total:5240000,end:2029,note:'Rd3 #89 — 4yr rookie deal. CHI WR — DJ Moore returns WR1, Thomas WR2'},
  {n:'Kaelon Black',pos:'RB',team:'SF',aav:1305000,total:5220000,end:2029,note:'Rd3 #90 — 4yr rookie deal. SF RB — strong OL system but crowded room'},
  // 2026 Day 2 Rookies
  {n:"De'Zhaun Stribling",pos:'WR',team:'SF',aav:1800000,total:7200000,end:2029,note:'Rd2 #33 — 4yr rookie deal. SF WR — Deebo/Aiyuk departed, real target share available'},
  {n:'Denzel Boston',pos:'WR',team:'CLE',aav:2200000,total:8800000,end:2029,note:'Rd2 #39 — 4yr rookie deal. CLE WR2 behind Concepcion. QB situation (Sanders) limits ceiling'},
  {n:'Germie Bernard',pos:'WR',team:'PIT',aav:1900000,total:7600000,end:2029,note:'Rd2 #47 — 4yr rookie deal. PIT WR3 behind DK Metcalf + Pittman. QB unresolved (Howard/Allar/Rodgers). Ceiling compressed vs expected'},
  {n:'Eli Stowers',pos:'TE',team:'PHI',aav:1700000,total:6800000,end:2029,note:'Rd2 #54 — 4yr rookie deal. PHI TE2 behind Goedert (31, injury history). Heir apparent — Hurts is elite QB. Best long-term TE dynasty situation in class'},
  {n:'Marlin Klein',pos:'TE',team:'HOU',aav:1600000,total:6400000,end:2029,note:'Rd2 #59 — 4yr rookie deal. Blocking TE — Stroud is elite QB but limited dynasty upside'},
  {n:'Max Klare',pos:'TE',team:'LAR',aav:1550000,total:6200000,end:2029,note:'Rd2 #61 — 4yr rookie deal. LAR TE behind Stafford short-term, Simpson era eventually'},
  {n:'Carson Beck',pos:'QB',team:'ARI',aav:1500000,total:6000000,end:2029,note:'Rd3 #65 — 4yr rookie deal. ARI backup behind Love. Long-term Brady/Love pairing'},
  {n:'Sam Roush',pos:'TE',team:'CHI',aav:1450000,total:5800000,end:2029,note:'Rd3 #69 — 4yr rookie deal. CHI blocking TE — limited dynasty receiving upside'},
  {n:'Antonio Williams',pos:'WR',team:'WAS',aav:1420000,total:5680000,end:2029,note:'Rd3 #71 — 4yr rookie deal. WAS WR2 behind McLaurin with Jayden Daniels throwing'},
  {n:'Oscar Delp',pos:'TE',team:'NO',aav:1400000,total:5600000,end:2029,note:'Rd3 #73 — 4yr rookie deal. Blocking-first TE in NO. Shough/Moore system'},
  {n:'Malachi Fields',pos:'WR',team:'NYG',aav:1390000,total:5560000,end:2029,note:'Rd3 #74 — 4yr rookie deal. NYG WR room thin but QB situation uncertain'},
  {n:'Zachariah Branch',pos:'WR',team:'ATL',aav:1380000,total:5520000,end:2029,note:'Rd3 #79 — 4yr rookie deal. ATL WR behind Drake London — Kirk/Pitts offense'},
  {n:"Ja'Kobi Lane",pos:'WR',team:'BAL',aav:1370000,total:5480000,end:2029,note:'Rd3 #80 — 4yr rookie deal. BAL WR — Lamar Jackson is elite, crowded WR room'},
  {n:'Chris Brazzell II',pos:'WR',team:'CAR',aav:1360000,total:5440000,end:2029,note:'Rd3 #83 — 4yr rookie deal. CAR WR — thin room but weak offense overall'},
  {n:'Ted Hurst',pos:'WR',team:'TB',aav:1355000,total:5420000,end:2029,note:'Rd3 #84 — 4yr rookie deal. TB WR — Baker Mayfield gives solid QB situation'},
  {n:'Drew Allar',pos:'QB',team:'PIT',aav:1350000,total:5400000,end:2029,note:'Rd3 #76 — 4yr rookie deal. PIT QB competition with Howard and possible Rodgers. Long-term franchise QB'},
  {n:'Will Kacmarek',pos:'TE',team:'MIA',aav:1320000,total:5280000,end:2029,note:'Rd3 #87 — 4yr rookie deal. Blocking TE in MIA — minimal dynasty receiving upside'},
  {n:'Chris Bell',pos:'WR',team:'MIA',aav:1300000,total:5200000,end:2029,note:'Rd3 #94 — 4yr rookie deal. MIA WR3 — Tua + Douglas competing for targets'},
  {n:'Eli Raridon',pos:'TE',team:'NE',aav:1290000,total:5160000,end:2029,note:'Rd3 #95 — 4yr rookie deal. NE TE — thin NE roster but unclear QB situation'},
  // 2026 Rookies — standard 4yr rookie deals
  {n:'Fernando Mendoza',pos:'QB',team:'LV',aav:9500000,total:38000000,end:2029,note:'#1 overall — 4yr through 2029. Cousins bridge 2026, Mendoza starter 2027+'},
  {n:'Jeremiyah Love',pos:'RB',team:'ARI',aav:8200000,total:32800000,end:2029,note:'#3 overall — 4yr through 2029. Cardinals RB1 immediately. Conner in committee'},
  {n:'Carnell Tate',pos:'WR',team:'TEN',aav:7900000,total:31600000,end:2029,note:'#4 overall — 4yr through 2029. Titans WR1 with Cam Ward at QB'},
  {n:'Jordyn Tyson',pos:'WR',team:'NO',aav:6800000,total:27200000,end:2029,note:'#8 overall — 4yr through 2029. Saints WR with Shough/Moore HC'},
  {n:'Ty Simpson',pos:'QB',team:'LAR',aav:5400000,total:21600000,end:2029,note:'#13 overall — 4yr through 2029. Buried behind Stafford until 2027+'},
  {n:'Kenyon Sadiq',pos:'TE',team:'NYJ',aav:4800000,total:19200000,end:2029,note:'#16 overall — 4yr through 2029. Jets TE1 immediately with Geno Smith'},
  {n:'Makai Lemon',pos:'WR',team:'PHI',aav:4200000,total:16800000,end:2029,note:'#20 overall — 4yr through 2029. Eagles WR3 until AJ Brown trade clears'},
  {n:'KC Concepcion',pos:'WR',team:'CLE',aav:3800000,total:15200000,end:2029,note:'#24 overall — 4yr through 2029. Browns WR1 path, QB situation concern'},
  {n:'Omar Cooper',pos:'WR',team:'NYJ',aav:3200000,total:12800000,end:2029,note:'#30 overall — 4yr through 2029. Jets WR2 behind Garrett Wilson'},
  {n:'Jadarian Price',pos:'RB',team:'SEA',aav:3100000,total:12400000,end:2029,note:'#32 overall — 4yr through 2029. Seahawks RB, strong OL, Walker competition'},

];

// Scouting reports now live in data/scout-reports.json (regenerate when model/thresholds change)
let SCOUT={};
let SCOUT_LOADED=false, SCOUT_LOADING=null;
function ensureScoutData(){
  if(SCOUT_LOADED) return Promise.resolve();
  if(SCOUT_LOADING) return SCOUT_LOADING;
  SCOUT_LOADING=fetch('./data/scout-reports.json?t='+Date.now())
    .then(r=>r.ok?r.json():Promise.reject('scout '+r.status))
    .then(d=>{SCOUT=d.reports||d; SCOUT_LOADED=true; console.log('[DELTA] Scout reports loaded:',Object.keys(SCOUT).length);})
    .catch(e=>{console.warn('[DELTA] Scout reports unavailable:',e); SCOUT_LOADED=true;});
  return SCOUT_LOADING;
}

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
// Scale: 0-99. Elite ~93-97. League avg starter ~65-72. Committee/role ~45-60.
// Data loaded from player-stats.json via loadPlayerStats()

let PLAYER_STATS = {}; // populated by loadPlayerStats()
let QB_ROLES = {};      // pipeline-emitted QB backup flags {name:{role,behind,source}} — see dsOpportunity
let HEADSHOTS = {};    // player name → headshot URL

function calcAlphaScore(name) {
  const s = PLAYER_STATS[name]?.['2025'];
  if (!s || !s.games) return null;
  const tgtS  = s.target_share  || 0;
  const airS  = s.air_yds_share || 0;
  const rzT   = s.rz_targets;
  const games = s.games || 1;

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

function calcWorkhorseScore(name) {
  const s = PLAYER_STATS[name]?.['2025'];
  if (!s || !s.games) return null;
  const rushS = s.rush_share   || 0;  // carries ÷ team carries — mirrors target_share
  const tgtS  = s.target_share || 0;
  const rzC   = s.rz_carries;
  const rzT   = s.rz_targets;

  // Ceilings calibrated against 2025 dataset:
  // rush_share: Bijan ~.65 (bellcow/run-heavy), CMC ~.55, Taylor ~.58 → ceil .65
  // tgt_share:  CMC .234, Achane .188 → ceil .24
  // rzC:        CMC 75, Taylor 71 → ceil 75
  // rzT:        CMC 25, Gibbs 15 → ceil 26
  const rushN = Math.min(1, rushS / 0.65);
  const tgtN  = Math.min(1, tgtS  / 0.24);
  const rzCN  = rzC != null ? Math.min(1, rzC / 75) : rushN * 0.6;
  const rzTN  = rzT != null ? Math.min(1, rzT / 26) : tgtN  * 0.6;

  const raw = rushN*0.40 + tgtN*0.30 + rzCN*0.20 + rzTN*0.10;

  // Scale: 28 floor, 99 theoretical ceiling
  return Math.round(28 + raw * 71);
}

function getOppScore(name, pos) {
  if (pos === 'WR' || pos === 'TE') return calcAlphaScore(name);
  if (pos === 'RB') return calcWorkhorseScore(name);
  return null;
}

function oppScoreColor(score) {
  if (!score) return '#4a5568';
  if (score >= 88) return '#6ee7b7';
  if (score >= 75) return '#7dd3fc';
  if (score >= 60) return '#fcd34d';
  return '#fc8181';
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
}
const SCAR_STARTERS = { QB:{ '1qb':1.0, 'sf':1.8 }, RB:2.4, WR:3.0, TE:1.1 };
const SCAR_CURVE = {
  QB: [[1,1.0],[6,0.865],[9,0.796],[12,0.769],[15,0.731],[18,0.721],[22,0.647],[26,0.608],[32,0.471]],
  RB: [[1,1.0],[6,0.798],[12,0.666],[19,0.573],[26,0.511],[34,0.387]],
  WR: [[1,1.0],[8,0.705],[16,0.588],[24,0.537],[36,0.473],[48,0.362]],
  TE: [[1,1.0],[3,0.788],[5,0.667],[8,0.605],[11,0.582],[14,0.563],[18,0.507]],
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
  const a = Math.floor(age);
  const curves = {
    QB:[[21,32,25],[33,33,23],[34,34,20],[35,35,16],[36,36,12],[37,37,8],[38,38,5],[39,99,3]],
    WR:[[20,26,25],[27,27,23],[28,28,21],[29,29,18],[30,30,14],[31,31,10],[32,32,7],[33,33,5],[34,99,3]],
    RB:[[20,25,25],[26,26,23],[27,27,21],[28,28,18],[29,29,15],[30,30,11],[31,31,8],[32,32,6],[33,33,4],[34,99,2]],
    TE:[[20,27,25],[28,28,23],[29,29,20],[30,30,17],[31,31,13],[32,32,10],[33,33,7],[34,34,4],[35,99,3]],
  };
  for (const [lo,hi,pts] of (curves[pos]||curves.WR)) {
    if (a>=lo && a<=hi) return pts;
  }
  return 2;
}

function dsProduction(ppg25, ppg24, ppg23, g25, pos, p) {
  // Production QUALITY relative to positional baseline, recency-weighted. Max 32 pts.
  const _fmtScale = (DS_FMT_SCALE[typeof scoringFmt!=='undefined'?scoringFmt:'half_tep'] || DS_FMT_SCALE.half_tep)[pos] || 1;
  const avg = (DS_AVG[pos]||12) * _fmtScale, elite = (DS_ELITE[pos]||14) * _fmtScale;
  const trans = DS_TRANS[pos]||1.15, scarMult = (DS_SCAR[pos]||1.0) * scarcity(pos, leagueTeams, qbFmt);

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
  const yrs = 2026 - draftYear;
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
  const expW = dsExpWeight(year);
  // Draft-capital opportunity is CAPPED below the proven-elite ceiling (max ~26 of 33).
  // PHILOSOPHY: pedigree earns a strong opportunity FLOOR, but the full max is reserved for
  // players who've DEMONSTRATED elite usage. Unproven potential < proven production.
  // (MHJ — elite capital, weak film — must be separable from a pure-capital rookie.)
  const capitalOpp = 3 + dsCapitalScore(pick) * 23; // map capital → 3-26 (capped)

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
    const rushPG = rushG > 0 ? rushAtt / rushG : 0;
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
    const seat = (QB_ROLES[p.n] && QB_ROLES[p.n].role === 'backup') ? 9 : 18;
    baseOpp = (noData && !noNFL) ? 13 : ((noNFL ? 14 : seat) + rushPts);
  } else {
    const oppSc = getOppScore(p.n, pos);
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
  const c = CONTRACTS.find(x => x.n===p.n);
  if (!c || !c.end) return 5; // unknown — neutral
  const yrs = c.end - 2026;
  return yrs>=5?10:yrs===4?9:yrs===3?8:yrs===2?7:yrs===1?6:5;
}

function calcDynastyScore(p) {
  const pos = p.pos||p.p||'WR';
  const noNFL = p.g25===0;  // rookie or no NFL data — cap applies (unproven)
  const a = dsAge(p.a||22, pos);                                                // max 25
  const prod = dsProduction(p.ppg25||0, p.ppg24||0, p.ppg23||0, p.g25||0, pos, p); // max 32
  const opp = dsOpportunity(p);                                                 // max 33
  const c = dsCont(p);                                                          // max 10
  // RB OPPORTUNITY DOWNWEIGHT (backtest-diagnosed): for running backs the usage/Workhorse
  // axis overlaps production heavily — redundancy held across volume, receiving, trajectory,
  // and efficiency tests — so the two axes were double-counting the same demonstrated fact.
  // Keep 65% of the usage axis and reallocate the freed weight (33*0.35 = 11.55 pts) into
  // production (the direct measure), preserving the 0-100 scale (RB max = 25 + 32*1.361 +
  // 33*0.65 + 10 = 100). REPRESENTATION fix to stop double-counting, NOT a predictive tune.
  // The 0.65 strength is a reasoned starting point on limited data; revisit as seasons accrue.
  let total;
  if (pos === 'RB') {
    total = Math.min(100, a + prod * 1.361 + opp * 0.65 + c);
  } else {
    total = Math.min(100, a + prod + opp + c);
  }
  if (noNFL) total = Math.min(DS_ROOKIE_CAP, total);
  return Math.round(total);
}

function dsColor(score) {
  // Matches platform color language (oppScoreColor thresholds)
  if (!score) return '#4a5568';
  if (score >= 85) return '#6ee7b7'; // teal — elite
  if (score >= 72) return '#7dd3fc'; // blue — strong
  if (score >= 55) return '#fcd34d'; // yellow — average
  return '#fc8181';                  // red — weak
}

RAW.forEach(r=>COMP.push(calcProj(r)));
const ASSETS=[...COMP,...PICKS.filter(p=>!p.hidden)];
function bc(s){return s>=70?'#6ee7b7':s>=55?'#7dd3fc':s>=40?'#fcd34d':'#fca5a5';}
function tH(t){return t==='up'?'<span style="color:#6ee7b7">▲</span>':t==='down'?'<span style="color:#fca5a5">▼</span>':'<span style="color:#4a5568">—</span>';}
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
function vTag(p){
  // No games across all tracked seasons = no signal
  // Selling a no-data player is bad advice regardless of model gap
  const totalG=(p.g25||0)+(p.g24||0)+(p.g23||0);
  if(totalG===0) return'<span class="badge bn" title="No NFL data yet">no data</span>';
  // Denominator is the market at the SAME 12-SF anchor basis the model uses (a manual ktc
  // override wins, since it's the user's stated market value). Format scaling cancels → per-player gap.
  const mkt12=(OV[p.n]&&OV[p.n].ktc!=null)?OV[p.n].ktc:p.k;
  const r=mvAssetBase(p)/Math.max(mkt12,1);
  const pos=p.p||p.pos||'';
  // TEs use tighter thresholds — market value already prices in TE scarcity
  const sb=pos==='TE'?1.10:1.15, b=pos==='TE'?1.00:1.06,
        h=pos==='TE'?0.88:0.94, s=pos==='TE'?0.76:0.82;
  // ── Thin-sample conviction dampener (June 2026) ──
  // DELTA only gets loud when the facts back it up. A "strong" tag on a tiny
  // sample (a hot 7-game rookie run) overclaims — those stretches fizzle and the
  // dynasty market overreacts. Below 12 CAREER games, conviction is capped one
  // level: strong buy → buy, strong sell → sell. The player keeps a directional
  // tag (a short elite stretch is still signal, à la Skattebo) — he just can't
  // carry max conviction until he's shown it across enough games.
  //
  // CAREER games come from PLAYER_STATS (real per-season game counts), NOT the
  // RAW record — RAW only carries g25, so g25+g24+g23 wrongly counted every
  // player as if their career started in 2025 (e.g. veteran James Conner read as
  // 3 career games and got dampened; he has 32). Falls back to RAW totals only
  // if stats are unavailable.
  const THIN_GAMES = 12;
  let careerG = 0;
  const _st = (typeof PLAYER_STATS !== 'undefined') ? PLAYER_STATS[p.n] : null;
  if(_st){
    careerG = ((_st['2023']&&_st['2023'].games)||0)
            + ((_st['2024']&&_st['2024'].games)||0)
            + ((_st['2025']&&_st['2025'].games)||0);
  }
  if(!careerG) careerG = totalG;   // fallback: RAW totals (rare — stats missing)
  const thin = careerG < THIN_GAMES;
  if(r>=sb) return thin
    ? '<span class="badge bi" title="Strong signal capped — only '+careerG+' career games (thin sample)">buy</span>'
    : '<span class="badge bs">strong buy</span>';
  if(r>=b) return'<span class="badge bi">buy</span>';
  if(r>=h) return'<span class="badge bn">hold</span>';
  if(r>=s) return'<span class="badge bw">sell</span>';
  return thin
    ? '<span class="badge bw" title="Strong signal capped — only '+careerG+' career games (thin sample)">sell</span>'
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
function rescalePickTier(year, rnd, tierName, newTierVal) {
  const tierSlots = {Early:[1,2,3,4], Mid:[5,6,7,8], Late:[9,10,11,12]};
  const slots = tierSlots[tierName];
  if (!slots) return;
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
const FC_ALIASES = {
  // FC name → DELTA name (when FC uses different format)
  'CeeDee Lamb':           'CeeDee Lamb',
  'Cee Dee Lamb':          'CeeDee Lamb',
  'DK Metcalf':            'D.K. Metcalf',
  'AJ Brown':              'A.J. Brown',
  'Deebo Samuel Sr.':      'Deebo Samuel',
  "De'Von Achane":         "De'Von Achane",
  'Devon Achane':          "De'Von Achane",
  'Travis Etienne Jr.':    'Travis Etienne',
  'Michael Pittman':       'Michael Pittman Jr.',
  'Ken Walker III':        'Kenneth Walker III',
  // Jr./Sr. variations
  'Marvin Harrison':       'Marvin Harrison Jr.',
  'Michael Penix':         'Michael Penix Jr.',
  'Harold Fannin':         'Harold Fannin Jr.',
  'Chigoziem Okonkwo':     'Chig Okonkwo',
  'Brian Thomas':          'Brian Thomas Jr.',
  // Initials without dots
  'CJ Stroud':             'C.J. Stroud',
  'JJ McCarthy':           'J.J. McCarthy',
  'JK Dobbins':            'J.K. Dobbins',
  'TJ Hockenson':          'T.J. Hockenson',
  'KJ Osborn':             'K.J. Osborn',
  // Other common variants
  'Samuel LaPorta':        'Sam LaPorta',
  'Javonte Williams':      'Javonte Williams',
};


async function loadPlayerStats() {
  try {
    const res = await fetch('./data/player-stats.json?t='+Date.now());
    if (!res.ok) return;
    const data = await res.json();
    if (!data?.players) return;

    PLAYER_STATS = data.players;
    if (data.headshots) HEADSHOTS = data.headshots;
    QB_ROLES = data.qb_roles || {};
    if (Object.keys(QB_ROLES).length) console.log('[DELTA] QB backup flags loaded:', Object.keys(QB_ROLES).join(', '));
    // Team fields are live data: the pipeline emits `teams` from the nflverse
    // 2026 roster feed, so trades and FA moves (A.J. Brown PHI→NE, Mac Jones
    // NE→SF) flow into RAW nightly instead of waiting on hand edits. Baked
    // RAW.t remains the first-paint fallback and covers players the roster
    // feed can't resolve.
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
    if (data.age) {
      let n = 0, rejected = 0;
      for (const player of RAW) {
        const a = data.age[player.n];
        if (a == null || a <= 0) continue;
        const baked = player.a;
        // The 117 universe-expansion players were seeded with PLACEHOLDER ages —
        // whole integers (24, 25). Real baked ages carry a decimal (28.9). The
        // collision guard must only protect REAL baked ages: for a seed, the
        // pipeline age is strictly better, so accept it even if it diverges a
        // lot (e.g. Tyreek Hill seeded 24 → real 32.3). For a real decimal baked
        // age, a >6yr jump signals a name-collision bad match (e.g. WR D.J. Moore
        // 28.9 vs an older DB D.J. Moore 39) → keep the trusted baked value.
        const bakedIsSeed = baked != null && Number.isInteger(baked);
        if (!bakedIsSeed && baked != null && baked > 0 && Math.abs(a - baked) > 6) {
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
        const ppg = (
          (row.rec     || 0) * recPts +
          (row.rec_yds || 0) * 0.1 +
          (row.rec_td  || 0) * 6 +
          (row.rush_yds|| 0) * 0.1 +
          (row.rush_td || 0) * 6 +
          (row.pass_yds|| 0) * 0.04 +
          (row.pass_td || 0) * 4 -
          (row.pass_int|| 0) * 2
        ) / row.games;
        if (ppg > 0) { player[key] = Math.round(ppg * 10) / 10; updated++; }
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
    console.warn('[DELTA] Could not load player stats:', e.message);
  }
}

// ── LOADER ────────────────────────────────────────────────────────────────
async function loadLiveMarketValues() {
  try {
    const res = await fetch('./data/market-values.json?t=' + Date.now()); // cache-bust: bypass Pages CDN edge cache
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    // Skip if file is the empty placeholder
    if (data.playerCount === 0) {
      console.log('[DELTA] Market values not yet populated — using baked-in values');
      return;
    }

    // Supports the per-format grid file {settings:{"T|Q":{...}}, default:"12|sf"}
    // and the legacy flat file {values:{...}}. The default (12-SF) slice is the
    // model's anchor (player.k); the selected-format slice drives player.kMkt.
    const tierMap = {
      'Early 1st Round Pick':{rnd:1,tier:'Early'},'Mid 1st Round Pick':{rnd:1,tier:'Mid'},
      'Late 1st Round Pick':{rnd:1,tier:'Late'},'Early 2nd Round Pick':{rnd:2,tier:'Early'},
      'Mid 2nd Round Pick':{rnd:2,tier:'Mid'},'Late 2nd Round Pick':{rnd:2,tier:'Late'},
      'Early 3rd Round Pick':{rnd:3,tier:'Early'},'Mid 3rd Round Pick':{rnd:3,tier:'Mid'},
      'Late 3rd Round Pick':{rnd:3,tier:'Late'},
    };
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

    // Pick tiers: rescale once from the anchor (default) slice — picks are not yet per-format
    for (const [n,m] of Object.entries(tierMap)) {
      for (const yr of [2026,2027,2028]) {
        const fc = anchorSlice[yr+' '+n];
        if (fc) rescalePickTier(yr, m.rnd, m.tier, fc.value);
      }
    }

    // Anchor: player.k = default (12-SF) market — the base the model rescales from via scarcity()
    let updated = 0, notFound = [];
    for (const player of RAW) {
      if (!player || !player.n) continue;
      const match = valOf(anchorSlice, player.n);
      if (match) {
        player.k = match.value;
        player.fcRank = match.overallRank;
        if (match.trend30Day !== undefined) player.fcTrend = match.trend30Day;
        if (match.team && match.team !== player.t) player.fcTeam = match.team;
        updated++;
      } else {
        player.kMkt = player.k;          // keep kMkt defined even if unmatched
        notFound.push(player.n);
      }
    }

    console.log(`[DELTA] Live values loaded: ${updated} players updated, ${notFound.length} not matched` +
                (MARKET_SETTINGS ? ` · grid ${Object.keys(MARKET_SETTINGS).length} settings` : ' · legacy flat'));
    showDataFreshness(data.fetched, updated);
    if (notFound.length > 0 && notFound.length < 20) {
      console.log('[DELTA] Unmatched players:', notFound.join(', '));
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
    showDataFreshness(new Date().toISOString(), -1);
  }
}

// ── FRESHNESS INDICATOR ───────────────────────────────────────────────────
async function loadPlayerContracts() {
  try {
    const res = await fetch('./data/player-contracts.json?t='+Date.now());
    if (!res.ok) return; // non-fatal
    const data = await res.json();
    if (!data?.contracts) return;

    let updated = 0;
    for (const player of RAW) {
      if (!player || !player.n) continue;
      const c = data.contracts[player.n];
      if (!c) continue;

      // Update contract in CONTRACTS array
      const existing = CONTRACTS.find(x => x.n === player.n);
      if (existing) {
        existing.end     = c.end_year;
        // player-contracts.json stores values in millions — convert to dollars
        existing.aav     = Math.round((c.aav   || 0) * 1000000);
        existing.total   = Math.round((c.total || 0) * 1000000);
        existing.years   = c.years;
      }
      updated++;
    }

    if (updated > 0) {
      console.log(`[DELTA] Contracts loaded: ${updated} updated`);
      // Rebuild COMP with fresh contract data
      COMP.length = 0;
      RAW.forEach(r => COMP.push(calcProj(r)));
      ASSETS.length = 0;
      ASSETS.push(...COMP, ...PICKS.filter(p => !p.hidden));
      if (typeof renderRankings === 'function') renderRankings();
    }
  } catch(e) {
    console.warn('[DELTA] Could not load contracts:', e.message);
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
