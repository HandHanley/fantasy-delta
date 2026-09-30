#!/usr/bin/env python3
"""
DELTA Rookie Trajectory — scripts/trajectory-study.py
Pre-registration: docs/PREREG-rookie-trajectory.md

    python3 scripts/trajectory-study.py --count   # counts only; reads NO year-two stats
    python3 scripts/trajectory-study.py --run     # refuses unless the pre-registration is committed

Does a rookie's SECOND-HALF scoring predict his second season better than his full-season average?
  today      year-2 starting number = rookie full-season PPG (with one season, the engine's weights cancel)
  candidate  lam x second-half PPG + (1 - lam) x full-season PPG
             second half = the later half of the games he played (the extra game goes to the first half)
  lam chosen once on classes 1999-2016 (grid 0.0-1.0 by 0.1; ties to the smaller); lam = 0 is today.
Graded once on classes 2017-2024. Drafted QB/RB/WR/TE, 8+ rookie games, 4+ games in year two.
Games = games with a recorded stat (no snap counts before 2012 — one rule for every era); scoring the
blend study's half PPR + TE premium. Old-era loader imported unchanged from scripts/rookie-volume-study.py.
"""
import argparse, importlib.util, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
_s = importlib.util.spec_from_file_location('rv', ROOT / 'scripts' / 'rookie-volume-study.py')
rv = importlib.util.module_from_spec(_s); _s.loader.exec_module(rv); bs = rv.bs

PREREG = 'docs/PREREG-rookie-trajectory.md'
TRAIN, TEST = list(range(1999, 2017)), list(range(2017, 2025))
LAMS = [round(0.1 * i, 1) for i in range(11)]
MIN_G1, MIN_G2 = 8, 4
MIN_CLASSES_BETTER, MIN_POS_N, SEED, SHUFFLES = 6, 30, 20260930, 2000

def build(read_outcomes):
    years = range(1999, 2026 if read_outcomes else 2025)
    g = rv.games(years)
    dp = pd.read_parquet(bs.CACHE / 'draft_picks.parquet')
    dp = dp[dp['season'].isin(TRAIN + TEST) & dp['position'].isin(bs.SKILL)].dropna(subset=['gsis_id'])
    cls = dict(zip(dp['gsis_id'].astype(str), dp['season'].astype(int)))
    rows = []
    for pid, pg in g[g['pid'].isin(cls)].groupby('pid'):
        y = cls[pid]; r = pg[pg['season'] == y].sort_values('week')
        if len(r) < MIN_G1: continue
        pos = r['pos'].mode().iat[0]
        if pos not in bs.SKILL: continue
        pts = np.asarray(bs.bt_pts(r, pos), dtype=float); h = len(pts) // 2
        row = {'pid': pid, 'cls': y, 'pos': pos, 'g': len(pts), 'full': pts.mean(), 'late': pts[h:].mean()}
        if read_outcomes:
            r2 = pg[pg['season'] == y + 1]
            row['y2'] = float(np.asarray(bs.bt_pts(r2, pos), dtype=float).mean()) if len(r2) >= MIN_G2 else np.nan
        rows.append(row)
    return pd.DataFrame(rows)

def pred(d, lam): return lam * d['late'].to_numpy() + (1 - lam) * d['full'].to_numpy()
def rmse(e): return float(np.sqrt(np.mean(e ** 2)))

def main():
    ap = argparse.ArgumentParser(); m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument('--count', action='store_true'); m.add_argument('--run', action='store_true')
    a = ap.parse_args()
    lock = None
    if a.run: bs.PREREG = PREREG; lock = bs.require_locked_prereg()
    d = build(read_outcomes=a.run)
    print(f"[TRAJ] drafted rookies with {MIN_G1}+ games: {len(d)} · training 1999-2016 {int(d['cls'].isin(TRAIN).sum())} · "
          f"test 2017-2024 {int(d['cls'].isin(TEST).sum())} · by position {d['pos'].value_counts().to_dict()}")
    if a.count: print('[TRAJ] --count: no year-two stats read.'); return

    excluded = int(d['y2'].isna().sum()); d = d.dropna(subset=['y2']).reset_index(drop=True)
    tr, te = d[d['cls'].isin(TRAIN)], d[d['cls'].isin(TEST)]
    err = {lam: float(np.mean([rmse(pred(tr[tr['cls'] == c], lam) - tr[tr['cls'] == c]['y2'].to_numpy()) for c in TRAIN if (tr['cls'] == c).any()])) for lam in LAMS}
    lam = min(LAMS, key=lambda l: (err[l], l))
    out = {'lock': lock, 'excluded_under_4_games_in_year_2': excluded, 'n_train': int(len(tr)), 'n_test': int(len(te)),
           'training_error_by_lambda': err, 'lambda_chosen': lam}
    if lam == 0.0:
        out.update({'SHIP': False, 'note': 'lam = 0 chosen on training: second-half scoring adds nothing.'})
        print(json.dumps(out, indent=2, default=float)); return
    y = te['y2'].to_numpy(); e0, e1 = pred(te, 0.0) - y, pred(te, lam) - y
    lift = 1 - rmse(e1) / rmse(e0)
    rng = np.random.default_rng(SEED); ge = 0
    for _ in range(SHUFFLES):
        f = rng.random(len(te)) < 0.5
        if 1 - rmse(np.where(f, e0, e1)) / rmse(np.where(f, e1, e0)) >= lift: ge += 1
    p = (ge + 1) / (SHUFFLES + 1)
    c, ps = te['cls'].to_numpy(), te['pos'].to_numpy()
    per_class = {int(k): 1 - rmse(e1[c == k]) / rmse(e0[c == k]) for k in TEST if (c == k).any()}
    per_pos = {q: 1 - rmse(e1[ps == q]) / rmse(e0[ps == q]) for q in bs.SKILL if (ps == q).any()}
    pos_n = {q: int((ps == q).sum()) for q in bs.SKILL}
    gates = {'size_>=2%': lift >= 0.02, 'p<0.05': p < 0.05,
             f'better_in_{MIN_CLASSES_BETTER}_of_8_classes': sum(v > 0 for v in per_class.values()) >= MIN_CLASSES_BETTER,
             'no_position_worse_than_-1%_(n>=30)': all(v >= -0.01 for k, v in per_pos.items() if pos_n[k] >= MIN_POS_N)}
    out.update({'test': {'today_rmse': rmse(e0), 'candidate_rmse': rmse(e1), 'lift': lift, 'p': p,
                         'today_mae': float(np.mean(np.abs(e0))), 'candidate_mae': float(np.mean(np.abs(e1)))},
                'per_class': per_class, 'per_position': per_pos, 'position_n': pos_n, 'gates': gates, 'SHIP': all(gates.values()),
                'reported_second_half_only_rmse': rmse(pred(te, 1.0) - y)})
    print(json.dumps(out, indent=2, default=float))
    (ROOT / 'data-cache' / 'trajectory-result.json').write_text(json.dumps(out, indent=2, default=float))

if __name__ == '__main__':
    main()
