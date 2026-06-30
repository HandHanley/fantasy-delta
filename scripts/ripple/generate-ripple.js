// DELTA Ripple Generator — core module (isolation WIP)
const COEF={RB:0.76,WR:1.51,TE:1.74}, INTCPT={RB:-0.22,WR:-0.51,TE:0.02};
const ROOKIE={
  RB:[[5,23.9],[12,18.2],[32,17.0],[64,11.6],[100,8.0],[999,4.5]],
  WR:[[5,7.1],[12,6.9],[32,5.5],[64,3.7],[100,2.9],[999,1.7]],
  TE:[[5,6.5],[12,5.1],[32,5.8],[64,2.8],[100,1.9],[999,1.8]],
};
const SAFETY_CAP=0.50, GATE=3.0, ARRIVAL_GATE=5.0;
// Measured across 8 seasons (2018-2025), controlling for regression-to-the-mean:
// per-incumbent opportunity change per 1 opp/g of vacated (absorption) and of
// arriving (displacement) talent. Absorption ≈ 0 — incumbents do NOT inherit a
// departed teammate's work; it goes to replacements. Displacement is small but
// consistently negative. Δopp_incumbent = VAC_COEF·vacated + ARR_COEF·arrival.
// (full-sample OLS, N=844/536/509, R²≈0.12 — opportunity shifts are mostly
// idiosyncratic, so honest ripples are small.)
const VAC_COEF={WR:0.005,RB:0.018,TE:0.042};
const ARR_COEF={WR:-0.048,RB:-0.073,TE:-0.086};
const NEG_PCT=0.02;   // below ±2% it's noise, not a ripple
const MIN_BASE=8.0;   // floor the %-denominator at a flex workload so a deep
                      // player's near-zero projection can't blow a tiny opp
                      // change up into a huge percentage
const MIN_PPG=0.25;   // and drop any projected change under ~0.25 PPG as immaterial
const rookiePrior=(pos,pick)=>{for(const[m,o]of ROOKIE[pos])if(pick<=m)return o;return 0;};
const clamp=(x,lo,hi)=>Math.max(lo,Math.min(hi,x));

function generateRipple(move){
  const {pos}=move;
  if(!COEF[pos]) return {team:move.team,pos,vacated:0,arrival:0,flag:'position not modeled (QB excluded)',ripples:[]};
  const coef=COEF[pos];
  // which moves are big enough to count: departures at rotation level, arrivals
  // at flex-starter level (a depth arrival rides the bench, doesn't displace).
  const sigDep=move.departures.filter(d=>d.opp_pg>=GATE);
  const arrivals=move.arrivals.map(a=>({...a,proj_opp:a.rookie?rookiePrior(pos,a.pick):a.prior_opp_pg}))
                              .filter(a=>a.proj_opp>=ARRIVAL_GATE);
  const vacated=sigDep.reduce((s,d)=>s+d.opp_pg,0);
  const arrival=arrivals.reduce((s,a)=>s+a.proj_opp,0);
  const gated=move.incumbents.filter(i=>i.opp_pg>=GATE);
  const filtered=move.incumbents.filter(i=>i.opp_pg<GATE).map(i=>i.name);
  const ripples=[];
  // informational only (NOT emitted as ripples): who's projected to claim the
  // vacated work. Their own DELTA projection carries it, not a ripple.
  for(const a of arrivals)
    ripples.push({n:a.name,role:'arrival',proj_opp_pg:+a.proj_opp.toFixed(1),
      proj_ppg:+(INTCPT[pos]+coef*a.proj_opp).toFixed(1),
      reason:`${a.rookie?`rookie (pick ${a.pick})`:'vet, prior '+a.prior_opp_pg+' opp/g'} → ${a.proj_opp.toFixed(1)} opp/g into ${move.team} ${pos}`});
  // the measured opportunity change applies per gated incumbent (team-level
  // vacated/arrival predicts each incumbent's shift; regression-to-mean is a
  // baseline effect DELTA already handles, so it is NOT applied here).
  const dOpp = VAC_COEF[pos]*vacated + ARR_COEF[pos]*arrival;
  const deps=sigDep.map(d=>d.name).join(' + ');
  const arrs=arrivals.map(a=>a.name).join(' + ');
  let emitted=0;
  for(const inc of gated){
    const dPpg=coef*dOpp;
    if(Math.abs(dPpg)<MIN_PPG) continue;                // immaterial absolute change
    const pct=clamp(dPpg/Math.max(inc.baseline_ppg,MIN_BASE),-SAFETY_CAP,SAFETY_CAP);
    if(Math.abs(pct)<NEG_PCT) continue;                 // below noise floor — no ripple
    emitted++;
    const up=dOpp>=0;
    const reason = up
      ? `slight bump from ~${vacated.toFixed(1)} opp/g vacated${deps?` (${deps} out)`:''}`
      : `cedes ~${Math.abs(dOpp).toFixed(1)} opp/g to arrivals${arrs?` (${arrs} in${deps?`, ${deps} out`:''})`:''}`;
    ripples.push({n:inc.name,role:'incumbent',d:up?'up':'down',delta:`${pct>=0?'+':''}${(pct*100).toFixed(0)}%`,
      reason, d_opp:+dOpp.toFixed(2), new_opp_pg:+(inc.opp_pg+dOpp).toFixed(1)});
  }
  const flag = (!gated.length && (vacated>=GATE||arrival>=ARRIVAL_GATE))
                 ? 'no rotation incumbent — absorber is an addition/rookie (own projection handles it)'
             : (!emitted) ? 'effects below ±2% — no material ripple'
             : 'ok';
  return {team:move.team,pos,vacated:+vacated.toFixed(1),arrival:+arrival.toFixed(1),
          d_opp:+dOpp.toFixed(2),gated_out:filtered,flag,ripples};
}
module.exports={generateRipple,COEF,rookiePrior};
