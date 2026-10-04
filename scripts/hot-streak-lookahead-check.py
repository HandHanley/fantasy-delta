#!/usr/bin/env python3
"""
Hot Streak Study — look-ahead check. Written 4 Oct 2026 AFTER the locked run; NOT pre-registered.
The locked pool rule dropped any player with a streak at ANY point that season, including streaks that
happened AFTER the comparison date — so the pool leaned toward players who did nothing later. This reruns
the locked script with that ONE line changed, three ways, and prints all three. See PREREG-hot-streak.md.
    python3 scripts/hot-streak-lookahead-check.py
"""
import importlib.util, numpy as np, pandas as pd
s=importlib.util.spec_from_file_location('hs','scripts/hot-streak-study.py'); hs=importlib.util.module_from_spec(s); s.loader.exec_module(hs)
hs.ensure_repo(); C=hs.commits(); wd=hs.week_dates(); xw=hs.crosswalk(); attr=hs.attributes(); g=hs.weekly()
E_,streaked,_,_=hs.events(g,C,wd,xw); H=hs.horizon_commits(C)
S=hs.find_streaks(g)                                    # every streak, any price
end={(r.season,r.pid): wd[(r.season,r.w3)][1] for r in S.itertuples()}
snapdate={h:d for d,h in C}
def price_at(h,fps,va):
    s_=hs.snapshot(h); return np.array([float(s_.at[f,'value_2qb']) if f in s_.index else 0.0 for f in fps])
src=open('scripts/hot-streak-study.py').read()
orig_filter="            pool = pool[[(y, fp2pid.get(f)) not in streaked for f in pool.index]]\n"
assert src.count(orig_filter)==1
def run(label, new_filter):
    code=src.replace(orig_filter,new_filter)
    ns={'__file__': 'scripts/hot-streak-study.py', '__name__': 'diag'}; exec(compile(code,'hs_diag','exec'),ns)
    for k in ('_snap',): ns[k]=hs._snap
    ns['__name__']='diag'
    ns['end']=end; ns['snapdate']=snapdate; ns['E_fps']=set(E_['fp'])
    r=ns['grade'](ns['build_frames'](E_,streaked,xw,H,price_at,attr),np.random.default_rng(hs.SEED))
    for hz,x in r.items():
        print(f"  {label:<44} {hs.HORIZONS[hz]:<26} gap {hs.pct(x['gap']):>7}  range {hs.pct(x['lo'])} to {hs.pct(x['hi'])}  halves {hs.pct(x['halves'][0])}/{hs.pct(x['halves'][1])}  {x['verdict']}")
print('[DIAG] after the locked run — not pre-registered')
run('LOCKED (excludes any streak, any time)', orig_filter)
run('FIXED (excludes only streaks already over)',
    "            pool = pool[[not ((y, fp2pid.get(f)) in end and end[(y, fp2pid.get(f))] < snapdate[snap_h]) for f in pool.index]]\n")
run('EVERYONE (excludes only the streak players)',
    "            pool = pool[[f not in E_fps for f in pool.index]]\n")
