// DELTA Ripple Generator — core module (isolation WIP)
const COEF={RB:0.76,WR:1.51,TE:1.74}, INTCPT={RB:-0.22,WR:-0.51,TE:0.02};
const ROOKIE={
  RB:[[5,23.9],[12,18.2],[32,17.0],[64,11.6],[100,8.0],[999,4.5]],
  WR:[[5,7.1],[12,6.9],[32,5.5],[64,3.7],[100,2.9],[999,1.7]],
  TE:[[5,6.5],[12,5.1],[32,5.8],[64,2.8],[100,1.9],[999,1.8]],
};
const CEIL={RB:22.2,WR:10.1,TE:8.4}, SAFETY_CAP=0.50, GATE=3.0;
const rookiePrior=(pos,pick)=>{for(const[m,o]of ROOKIE[pos])if(pick<=m)return o;return 0;};
const clamp=(x,lo,hi)=>Math.max(lo,Math.min(hi,x));
const FLOOR=0.5;  // a rostered player can't be squeezed below ~replacement level
// gain bounded by headroom-to-ceiling; loss bounded by cedeable-to-floor (symmetric, diminishing)
const absorb=(cur,raw,ceil)=>{const h=Math.max(0,ceil-cur);return (h<=0||raw<=0)?0:h*(1-Math.exp(-raw/h));};
const cede=(cur,raw)=>{const c=Math.max(0,cur-FLOOR);return (c<=0||raw<=0)?0:c*(1-Math.exp(-raw/c));};

function generateRipple(move){
  const {pos}=move, coef=COEF[pos], ceil=CEIL[pos];
  const vacated=move.departures.reduce((s,d)=>s+d.opp_pg,0);
  const arrivals=move.arrivals.map(a=>({...a,proj_opp:a.rookie?rookiePrior(pos,a.pick):a.prior_opp_pg}));
  const claimed=arrivals.reduce((s,a)=>s+a.proj_opp,0);
  const residual=vacated-claimed;
  const gated=move.incumbents.filter(i=>i.opp_pg>=GATE);
  const filtered=move.incumbents.filter(i=>i.opp_pg<GATE).map(i=>i.name);
  // SIGNIFICANCE GATE — if the net opportunity actually changing hands is tiny,
  // the move is a non-factor (e.g. a depth player joining): no incumbent ripples.
  const negligible = Math.abs(residual) < 3.0;
  const ripples=[];
  for(const a of arrivals)
    ripples.push({n:a.name,role:'arrival',proj_opp_pg:+a.proj_opp.toFixed(1),
      proj_ppg:+(INTCPT[pos]+coef*a.proj_opp).toFixed(1),
      reason:`${a.rookie?`rookie (pick ${a.pick})`:'vet, prior '+a.prior_opp_pg+' opp/g'} → ${a.proj_opp.toFixed(1)} opp/g into ${move.team} ${pos}`});
  const rawShare=gated.length?residual/gated.length:0; let absorbedTotal=0;
  if(!negligible) for(const inc of gated){
    const realized=residual>=0?absorb(inc.opp_pg,rawShare,ceil):-cede(inc.opp_pg,Math.abs(rawShare));
    absorbedTotal+=Math.max(0,realized);
    const pct=inc.baseline_ppg>0?clamp(coef*realized/inc.baseline_ppg,-SAFETY_CAP,SAFETY_CAP):0;
    const deps=move.departures.map(d=>d.name).join(' + ');
    const arrs=arrivals.map(a=>a.name).join(' + ');
    const reason = realized>=0
      ? `absorbs ~${realized.toFixed(1)} opp/g${deps?` (${deps} out`:''}${arrs?`, ${arrs} in)`:deps?')':''}`
      : `cedes ~${Math.abs(realized).toFixed(1)} opp/g${arrs?` (${arrs} in`:''}${deps?`, ${deps} out)`:arrs?')':''}`;
    ripples.push({n:inc.name,role:'incumbent',d:pct>=0?'up':'down',delta:`${pct>=0?'+':''}${(pct*100).toFixed(0)}%`,
      reason, realized_opp:+realized.toFixed(1),new_opp_pg:+(inc.opp_pg+realized).toFixed(1)});
  }
  const leaked=Math.max(0,residual-absorbedTotal);
  const flag=negligible?`negligible — only ${Math.abs(residual).toFixed(1)} opp/g net change, no incumbent ripple`
            :(residual>3&&gated.length>1)?'multiple relevant incumbents — human picks ascender'
            :(residual>3&&gated.length===0)?'vacancy but NO rotation incumbent gated in — human-confirm (likely a backup ascends or addition needed)'
            :(leaked>3)?`${leaked.toFixed(1)} opp/g unabsorbed — verify current roster for additions`
            :(claimed>vacated*1.1)?'arrivals exceed vacancy — incumbents squeezed':'ok';
  return {team:move.team,pos,vacated:+vacated.toFixed(1),claimed:+claimed.toFixed(1),residual:+residual.toFixed(1),
          absorbed:+absorbedTotal.toFixed(1),leaked:+leaked.toFixed(1),gated_out:filtered,flag,ripples};
}
module.exports={generateRipple,COEF,CEIL,rookiePrior};
