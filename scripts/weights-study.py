#!/usr/bin/env python3
"""
DELTA Past-Season Weights Study — scripts/weights-study.py
Pre-registration: docs/PREREG-season-weights.md

    python3 scripts/weights-study.py --count   # eligibility only; computes NO errors
    python3 scripts/weights-study.py --run     # refuses unless the pre-registration is committed

Question: how should the projection's starting number weight a player's last three
seasons, and how should it treat short seasons?

  E  today's engine (calcProj "RULE 1", copied exactly — verified 315/315 against the live
     engine's own base on 26 Sep; the 24 others are later adjustments this study leaves alone):
       last season 3 if 10+ games, 1.5 if 8-9, 0.75 if 4-7, else 0; the season before 2 if he
       scored at all; three seasons back 1 if he scored at all; fallback last || before || 8.0
  Grid: weights {3/2/1, 6/3/1, 5/3/2, 4/2/1, 7/2/1, 1/1/1} x short-season rule
        {"steps": today's rule above, applied only to last season;
         "smooth": every season scaled by min(1, games / 8)} — 12 combinations, E is one.
The best of the other 11, chosen on training seasons only, is the candidate; it faces E once on
the held-out seasons. Shared machinery (games, scoring, IDs) comes from scripts/blend-study.py.
"""
import argparse, importlib.util, json, math, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
_s = importlib.util.spec_from_file_location('bs1', ROOT / 'scripts' / 'blend-study.py')
bs = importlib.util.module_from_spec(_s); _s.loader.exec_module(bs)

PREREG    = 'docs/PREREG-season-weights.md'
TRAIN, HELDOUT = [2018, 2019, 2020, 2021, 2022], [2023, 2024, 2025]
WEIGHTS   = [(3, 2, 1), (6, 3, 1), (5, 3, 2), (4, 2, 1), (7, 2, 1), (1, 1, 1)]
SHRINKS   = ['steps', 'smooth']
ENGINE    = ((3, 2, 1), 'steps')
MIN_PRIOR, MIN_NOW, MIN_POS_N = 8, 6, 30
SEED, SHUFFLES = 20260926, 2000

def base(row, w, shrink):
    g, v = row['g'], row['v']                       # games, PPG for last season, before, three back
    num = den = 0.0
    for k in range(3):
        if not (v[k] > 0): continue
        if shrink == 'steps':
            if k == 0: wk = w[0] * (1 if g[0] >= 10 else 0.5 if g[0] >= 8 else 0.25 if g[0] >= 4 else 0)
            else: wk = w[k]
        else:
            wk = w[k] * min(1.0, g[k] / 8)
        if wk > 0: num += v[k] * wk; den += wk
    return num / den if den > 0 else (v[0] or v[1] or 8.0)
# steps: engine's 3/1.5/0.75 are 3 x (1, 0.5, 0.25) — the same fractions for any weight triple

def build_rows(g):
    rows = []
    for pid, pg in g.groupby('pid', sort=False):
        seasons = {s: sg for s, sg in pg.groupby('season')}
        for Y in TRAIN + HELDOUT:
            cur = seasons.get(Y)
            if cur is None or len(cur) < MIN_NOW: continue
            pos = cur['spos'].mode().iat[0]
            gs, vs = [], []
            for k in (1, 2, 3):
                sg = seasons.get(Y - k)
                n = 0 if sg is None else len(sg)
                gs.append(n); vs.append(bs.bt_pts(sg, pos).sum() / n if n else 0.0)
            if sum(gs) < MIN_PRIOR: continue
            rows.append({'pid': pid, 'season': Y, 'pos': pos, 'g': gs, 'v': vs,
                         'actual': bs.bt_pts(cur, pos).sum() / len(cur)})
    return pd.DataFrame(rows)

def preds(df, combo): return np.array([base(r, *combo) for r in df.to_dict('records')])
def rmse(e): return float(np.sqrt(np.mean(e ** 2)))

def main():
    ap = argparse.ArgumentParser(); m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument('--count', action='store_true'); m.add_argument('--run', action='store_true')
    a = ap.parse_args()
    lock = None
    if a.run: bs.PREREG = PREREG; lock = bs.require_locked_prereg()
    g, _ = bs.load_games()
    df = build_rows(g)
    print('[WEIGHTS] graded player-seasons by season:', df.groupby('season').size().to_dict())
    h = df[df['season'].isin(HELDOUT)]
    print(f"[WEIGHTS] training {int(df['season'].isin(TRAIN).sum())} · held out {len(h)} · held-out by position "
          f"{h['pos'].value_counts().to_dict()} · distinct held-out players {h['pid'].nunique()}")
    if a.count: print('[WEIGHTS] --count: no errors computed.'); return

    tr, te = df[df['season'].isin(TRAIN)], df[df['season'].isin(HELDOUT)]
    combos = [(w, s) for w in WEIGHTS for s in SHRINKS]
    def cv(combo):                                   # leave-one-training-season-out (no fitted parameters,
        return float(np.mean([rmse(preds(tr[tr['season'] == s], combo) - tr[tr['season'] == s]['actual'].to_numpy())
                              for s in TRAIN]))       # so this is the mean per-season training error)
    cvs = {f'{w[0]}/{w[1]}/{w[2]} {s}': cv((w, s)) for w, s in combos}
    others = [c for c in combos if c != ENGINE]
    cand = min(others, key=cv)
    eng_cv, cand_cv = cv(ENGINE), cv(cand)
    label = lambda c: f'{c[0][0]}/{c[0][1]}/{c[0][2]} {c[1]}'
    print(f'[WEIGHTS] training error by combination: ' + ', '.join(f'{k} {v:.4f}' for k, v in sorted(cvs.items(), key=lambda kv: kv[1])))
    print(f'[WEIGHTS] candidate chosen on training: {label(cand)} ({cand_cv:.4f}) vs engine {eng_cv:.4f}')

    y = te['actual'].to_numpy()
    eE, eC = preds(te, ENGINE) - y, preds(te, cand) - y
    lift = 1 - rmse(eC) / rmse(eE)
    rng = np.random.default_rng(SEED)                 # paired swap of E and candidate errors, per PLAYER
    uniq, inv = np.unique(te['pid'].to_numpy(), return_inverse=True); ge = 0
    for _ in range(SHUFFLES):
        f = (rng.random(len(uniq)) < 0.5)[inv]
        if 1 - rmse(np.where(f, eE, eC)) / rmse(np.where(f, eC, eE)) >= lift: ge += 1
    p = (ge + 1) / (SHUFFLES + 1)
    s_arr, p_arr = te['season'].to_numpy(), te['pos'].to_numpy()
    per_season = {int(s): 1 - rmse(eC[s_arr == s]) / rmse(eE[s_arr == s]) for s in HELDOUT}
    per_pos = {ps: 1 - rmse(eC[p_arr == ps]) / rmse(eE[p_arr == ps]) for ps in bs.SKILL if (p_arr == ps).any()}
    pos_n = {ps: int((p_arr == ps).sum()) for ps in bs.SKILL}
    gates = {'size_>=2%': lift >= 0.02, 'p<0.05': p < 0.05,
             'every_heldout_season': all(v > 0 for v in per_season.values()),
             'no_position_worse_than_-1%_(n>=30)': all(v >= -0.01 for k, v in per_pos.items() if pos_n[k] >= MIN_POS_N)}
    out = {'lock': lock, 'candidate': label(cand), 'training_cv': cvs,
           'heldout': {'engine_rmse': rmse(eE), 'candidate_rmse': rmse(eC), 'lift': lift, 'p': p,
                       'engine_mae': float(np.mean(np.abs(eE))), 'candidate_mae': float(np.mean(np.abs(eC)))},
           'per_season': per_season, 'per_position': per_pos, 'position_n': pos_n,
           'reported_only_all_12_heldout_rmse': {label(c): rmse(preds(te, c) - y) for c in combos},
           'gates': gates, 'SHIP': all(gates.values())}
    print(json.dumps(out, indent=2, default=float))
    (ROOT / 'data-cache' / 'weights-study-result.json').write_text(json.dumps(out, indent=2, default=float))

if __name__ == '__main__':
    main()
