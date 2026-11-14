# Proposed replacement planted test: each player "becomes" one of his own 30 matches, drawn by match weight.
# Cap-is-right world: that match's outcome is capped at the player's third-best match. Uses no test row's own outcome.
import sys, types, json, numpy as np
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import ovs_one_match as M
N='/home/claude/nfl'
a=types.SimpleNamespace(nflverse=f'{N}/nflv',rosters=f'{N}/rosters',weekly=f'{N}/weekly',wrost=f'{N}/wrost',inj=f'{N}/inj',sched=f'{N}/sched/games.csv',snaps=f'{N}/snaps')
G=M.frame(a); y=G['y']; F=G['F']; d=G['on_draft']
today, cap = M.values(G,y), M.values(G,y,M.CAP_AT)
NN=[F['nnB'][i] if d[i] else F['nnI'][i] for i in range(len(d))]; WW=[F['wB'][i] if d[i] else F['wI'][i] for i in range(len(d))]
def world(rng, capped):
    out=np.empty(len(NN))
    for i,(n,w) in enumerate(zip(NN,WW)):
        o=y[n]
        if capped: o=np.minimum(o, np.sort(o)[-M.CAP_AT])
        out[i]=o[rng.choice(len(o), p=w/w.sum())]
    return out
res={}
for name,capped,runs in ():
    rng=np.random.default_rng(75 if capped else 76); ok=0; lifts=[]
    for _ in range(runs):
        r=M.decide(G,today,cap,world(rng,capped),n_perm=1000); ok+=r['pass']; lifts.append(r['lift'])
    res[name]={'runs':runs,'passed':ok,'share':ok/runs,'median_lift':float(np.median(lifts))}
    print(name,res[name],flush=True)
json.dump(res,open('/home/claude/fantasy-delta/study/out/ovs_one_match_crash_draw.json','w'),indent=1)

# Proposed option: decide on the rows the cap actually moves (value down 20%+), with an all-rows guard
moved = (today > 0) & ((today - cap) / np.where(today > 0, today, 1) >= 0.20)
print('rows moved 20%+ (test):', int((moved & G['test']).sum()), 'of', int(G['test'].sum()))
G2 = dict(G); G2['test'] = G['test'] & moved
out={}
for name,capped,runs in (('cap_is_right',True,200),('today_is_right',False,50)):
    rng=np.random.default_rng(75 if capped else 76); ok=0; lifts=[]; allw=[]
    for _ in range(runs):
        tr=world(rng,capped); r=M.decide(G2,today,cap,tr,n_perm=1000); ok+=r['pass']; lifts.append(r['lift'])
        m=G['test']; allw.append(1-M.rmse(cap[m],tr[m])/M.rmse(today[m],tr[m]))
    out[name]={'runs':runs,'passed':ok,'share':ok/runs,'median_lift_moved_rows':float(np.median(lifts)),'median_lift_all_rows':float(np.median(allw))}
    print(name,out[name],flush=True)
json.dump(out,open('/home/claude/fantasy-delta/study/out/ovs_one_match_crash_draw_moved.json','w'),indent=1)
