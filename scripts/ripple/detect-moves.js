// DELTA Sleeper roster-diff detector (isolation WIP)
// Compares the current Sleeper /players/nfl snapshot to the previously stored
// snapshot and emits skill-position team-change events. Live pull runs in CI;
// the diff logic is plain and testable on sample snapshots.
const SKILL=new Set(['RB','WR','TE']);  // QB excluded

// snapshots: { player_id: { full_name, position, team } }  (trimmed Sleeper shape)
function detectMoves(prev, curr){
  const moves=[]; const ids=new Set([...Object.keys(prev),...Object.keys(curr)]);
  for(const id of ids){
    const p=prev[id], c=curr[id];
    const pos=(c&&c.position)||(p&&p.position);
    if(!SKILL.has(pos)) continue;
    const from=p?p.team:null, to=c?c.team:null;
    if(from===to) continue;                       // no change (incl. both null)
    const name=(c&&c.full_name)||(p&&p.full_name);
    if(from && to){ moves.push({type:'departure',name,pos,from,to}); moves.push({type:'arrival',name,pos,from,to}); }
    else if(to)   moves.push({type:'arrival',name,pos,from:null,to}); // entered league / activated
    else          moves.push({type:'departure',name,pos,from,to:null}); // cut / retired / unsigned
  }
  return moves;
}

// Group raw events into per-(team,pos) generator-shaped moves: each affected
// team+position gets its departures and arrivals collected.
function groupByTeam(moves){
  const g={}; // `${team}|${pos}` -> {team,pos,departures:[],arrivals:[]}
  for(const m of moves){
    if(m.type==='departure' && m.from){ const k=`${m.from}|${m.pos}`; (g[k]||={team:m.from,pos:m.pos,departures:[],arrivals:[]}).departures.push(m.name); }
    if(m.type==='arrival'   && m.to){   const k=`${m.to}|${m.pos}`;   (g[k]||={team:m.to,  pos:m.pos,departures:[],arrivals:[]}).arrivals.push(m.name); }
  }
  return Object.values(g);
}
module.exports={detectMoves,groupByTeam};

// ---- synthetic test modeled on the real Eagles offseason ----
if(require.main===module){
  const prev={
    p1:{full_name:'A.J. Brown',position:'WR',team:'PHI'},
    p2:{full_name:'Jahan Dotson',position:'WR',team:'PHI'},
    p3:{full_name:'DeVonta Smith',position:'WR',team:'PHI'},
    p4:{full_name:'Derrick Henry',position:'RB',team:'BAL'},
    p5:{full_name:'Some Kicker',position:'K',team:'PHI'},      // non-skill, must be ignored
  };
  const curr={
    p1:{full_name:'A.J. Brown',position:'WR',team:'NE'},        // PHI -> NE (trade)
    p2:{full_name:'Jahan Dotson',position:'WR',team:'ATL'},     // PHI -> ATL
    p3:{full_name:'DeVonta Smith',position:'WR',team:'PHI'},    // unchanged
    p4:{full_name:'Derrick Henry',position:'RB',team:'BAL'},    // unchanged
    p5:{full_name:'Some Kicker',position:'K',team:'PHI'},
    p6:{full_name:'Makai Lemon',position:'WR',team:'PHI'},      // new arrival (rookie)
  };
  const moves=detectMoves(prev,curr);
  console.log('Raw move events:'); moves.forEach(m=>console.log('  ',JSON.stringify(m)));
  console.log('\nGrouped per team+pos (generator input shape):');
  groupByTeam(moves).forEach(g=>console.log('  ',JSON.stringify(g)));
}
