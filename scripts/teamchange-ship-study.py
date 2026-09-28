#!/usr/bin/env python3
"""
DELTA Team-Change Adjustment — Ship Test — scripts/teamchange-ship-study.py
Pre-registration: docs/PREREG-team-change-ship.md

    python3 scripts/teamchange-ship-study.py --count   # counts only; computes NO outcomes
    python3 scripts/teamchange-ship-study.py --run     # refuses unless the pre-registration is committed

Does knowing a player CHANGED TEAMS improve his preseason forecast, beyond treating him like a player
who stayed? The trap avoided: the plain starting number runs high for everyone, so "shrink movers"
would beat "don't" even if moving meant nothing. So BOTH sides are calibrated on training stayers:
  baseline   movers forecast like stayers:     start x m_S          (m_S fitted on 2018-2022 stayers)
  candidate  movers get their own correction:  start x m_S x r      (r = m_C / m_S, fitted on 2018-2022)
graded once on 2023-2025 movers. Teams, eligibility, the starting number and the fit are imported
unchanged from the locked scripts/teamchange-study.py.

SHIPPED SIZE (if it passes): DELTA already treats movers about 7% more cautiously through its
directional team adjustments (recorded 27 Sep: x0.823 vs x0.886). The new piece closes only the
difference:  extra = min(1, r_all / (0.823 / 0.886)),  r_all fitted on all eight seasons.
"""
import argparse, importlib.util, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
_s = importlib.util.spec_from_file_location('tc', ROOT / 'scripts' / 'teamchange-study.py')
tc = importlib.util.module_from_spec(_s); _s.loader.exec_module(tc); bs = tc.bs

PREREG = 'docs/PREREG-team-change-ship.md'
TRAIN, HELDOUT = [2018, 2019, 2020, 2021, 2022], [2023, 2024, 2025]
ENGINE_RATIO = 0.823 / 0.886                     # engine's existing extra caution, recorded 27 Sep
MIN_POS_N, SEED, SHUFFLES = 30, 20260927, 2000

def rmse(e): return float(np.sqrt(np.mean(e ** 2)))

def main():
    ap = argparse.ArgumentParser(); m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument('--count', action='store_true'); m.add_argument('--run', action='store_true')
    a = ap.parse_args()
    lock = None
    if a.run: bs.PREREG = PREREG; lock = bs.require_locked_prereg()
    g, _ = bs.load_games()
    df = tc.build(g)
    tr, te = df[df['season'].isin(TRAIN)], df[df['season'].isin(HELDOUT)]
    print(f"[SHIP] training movers {int(tr['changed'].sum())} · stayers {int((~tr['changed']).sum())} | "
          f"held-out movers {int(te['changed'].sum())} · by position {te[te['changed']]['pos'].value_counts().to_dict()}")
    if a.count: print('[SHIP] --count: no outcomes computed.'); return

    mS, mC = tc.mult(tr[~tr['changed']]), tc.mult(tr[tr['changed']]); r = mC / mS
    mv = te[te['changed']]; y = mv['actual'].to_numpy(); p0 = mv['p0'].to_numpy()
    eA, eB = p0 * mS - y, p0 * mS * r - y
    lift = 1 - rmse(eB) / rmse(eA)
    rng = np.random.default_rng(SEED)
    uniq, inv = np.unique(mv['pid'].to_numpy(), return_inverse=True); ge = 0
    for _ in range(SHUFFLES):
        f = (rng.random(len(uniq)) < 0.5)[inv]
        if 1 - rmse(np.where(f, eA, eB)) / rmse(np.where(f, eB, eA)) >= lift: ge += 1
    p = (ge + 1) / (SHUFFLES + 1)
    s_arr, p_arr = mv['season'].to_numpy(), mv['pos'].to_numpy()
    sub = lambda mk: 1 - rmse(eB[mk]) / rmse(eA[mk]) if mk.any() else None
    per_season = {int(s): sub(s_arr == s) for s in HELDOUT}
    per_pos = {ps: sub(p_arr == ps) for ps in bs.SKILL}; pos_n = {ps: int((p_arr == ps).sum()) for ps in bs.SKILL}
    gates = {'size_>=2%': lift >= 0.02, 'p<0.05': p < 0.05,
             'every_heldout_season': all(v is not None and v > 0 for v in per_season.values()),
             'no_position_worse_than_-1%_(n>=30)': all(v >= -0.01 for k, v in per_pos.items() if v is not None and pos_n[k] >= MIN_POS_N)}
    r_all = tc.mult(df[df['changed']]) / tc.mult(df[~df['changed']])
    extra = min(1.0, r_all / ENGINE_RATIO)
    out = {'lock': lock, 'training': {'m_stayers': mS, 'm_movers': mC, 'r': r},
           'heldout_movers': {'n': int(len(mv)), 'baseline_rmse': rmse(eA), 'candidate_rmse': rmse(eB), 'lift': lift, 'p': p,
                              'baseline_mae': float(np.mean(np.abs(eA))), 'candidate_mae': float(np.mean(np.abs(eB)))},
           'per_season': per_season, 'per_position': per_pos, 'position_n': pos_n, 'gates': gates, 'SHIP': all(gates.values()),
           'ship_size': {'r_all_eight_seasons': r_all, 'engine_ratio_recorded': ENGINE_RATIO, 'extra_multiplier': extra}}
    print(json.dumps(out, indent=2, default=float))
    (ROOT / 'data-cache' / 'teamchange-ship-result.json').write_text(json.dumps(out, indent=2, default=float))

if __name__ == '__main__':
    main()
