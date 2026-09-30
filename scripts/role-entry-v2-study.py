#!/usr/bin/env python3
"""
DELTA Role-Entry Odds v2 — scripts/role-entry-v2-study.py
Pre-registration: docs/PREREG-role-entry-v2.md

    python3 scripts/role-entry-v2-study.py --count   # counts only; computes NO outcomes
    python3 scripts/role-entry-v2-study.py --run     # refuses unless the pre-registration is committed

The first odds curve (docs/PREREG-role-entry.md) was too confident at the top (rated 77%, hit 65%; a
top-5 RB "100%"). The fix, fixed now: a CAPPED curve — per position  P = c x logistic(a + b x ln(pick)),
with one pooled ceiling c < 1 (no draft slot guarantees a fantasy starter).
VALIDATED ON UNSEEN CLASSES 2000-2014 (never used by any DELTA study): each class predicted from the
other fourteen of its own era, so the test is of the METHOD, not of one era's numbers.
Drafted players with no nflverse ID count as misses: an ID is issued when a player records stats, and
those missing are never-played picks (e.g. Giovanni Carmazzi, Maurice Clarett, Eric Crouch, Kenny Irons).
Old-era games count when a stat was recorded (no snap counts before 2012). Hit = a starter-level season
in the first three (top 12 QB / 24 RB / 24 WR / 12 TE by PPG, 8+ games) — as the first study.
Imports, unchanged: scripts/role-entry-study.py (modern data, fit, calibration) and
scripts/rookie-volume-study.py (the old-era game loader).
"""
import argparse, importlib.util, json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parent.parent
def _load(n, f):
    s = importlib.util.spec_from_file_location(n, ROOT / 'scripts' / f); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
re1 = _load('re1', 'role-entry-study.py'); rv = _load('rv', 'rookie-volume-study.py'); bs = re1.bs

PREREG = 'docs/PREREG-role-entry-v2.md'
OLD, NEW = list(range(2000, 2015)), list(range(2015, 2024))
TOP = re1.TOP
SEED, SIMS = 20260929, 2000
PICKS = (5, 20, 45, 80, 120, 180, 240)

def old_hits():
    g = rv.games(range(2000, 2017))
    rows = []
    for (pid, y), sg in g.groupby(['pid', 'season']):
        pos = sg['pos'].mode().iat[0] if sg['pos'].notna().any() else None
        if pos not in TOP or len(sg) < 8: continue
        rows.append((pid, y, pos, bs.bt_pts(sg, pos).sum() / len(sg)))
    t = pd.DataFrame(rows, columns=['pid', 'season', 'pos', 'ppg'])
    t['rank'] = t.groupby(['season', 'pos'])['ppg'].rank(ascending=False, method='first')
    return set(map(tuple, t[t['rank'] <= t['pos'].map(TOP)][['pid', 'season']].values))

def build_old(read_outcomes):
    dp = pd.read_parquet(bs.CACHE / 'draft_picks.parquet')
    dp = dp[dp['season'].isin(OLD) & dp['position'].isin(bs.SKILL)].dropna(subset=['pick']).copy()
    df = pd.DataFrame({'pid': dp['gsis_id'].astype(object).where(dp['gsis_id'].notna(), None), 'cls': dp['season'].astype(int),
                       'pos': dp['position'], 'pick': dp['pick'].astype(float)})
    if read_outcomes:
        hits = old_hits()
        df['hit'] = [int(p is not None and any((str(p), y) in hits for y in (c, c + 1, c + 2))) for p, c in zip(df['pid'], df['cls'])]
    return df

def capped_fit(d):
    X = re1.design(d); y = d['hit'].to_numpy(float)
    def nll(w):
        cap = 1 / (1 + np.exp(-w[-1])); p = np.clip(cap / (1 + np.exp(-(X @ w[:-1]))), 1e-9, 1 - 1e-9)
        return float(-np.sum(y * np.log(p) + (1 - y) * np.log(1 - p))) + 1e-4 * float(w[:-1] @ w[:-1])
    return minimize(nll, np.r_[np.zeros(X.shape[1]), 2.0], method='BFGS').x

def capped_pred(w, d):
    return (1 / (1 + np.exp(-w[-1]))) / (1 + np.exp(-(re1.design(d) @ w[:-1])))

def loco(d, classes, capped=True):
    pr = np.zeros(len(d))
    for c in classes:
        tr, mk = d[d['cls'] != c], (d['cls'] == c).to_numpy()
        if not mk.any(): continue
        if capped: pr[mk] = capped_pred(capped_fit(tr), d[mk])
        else:
            w = re1.fit_logit(re1.design(tr), tr['hit'].to_numpy()); pr[mk] = 1 / (1 + np.exp(-re1.design(d[mk]) @ w))
    return pr

def honest(p, y):
    cal, rows = re1.calibration(p, y); rng = np.random.default_rng(SEED)
    lim = float(np.percentile([re1.calibration(p, (rng.random(len(p)) < p).astype(float))[0] for _ in range(SIMS)], 95))
    return {'calibration_error': cal, 'honest_model_limit': lim, 'HONEST': cal <= lim, 'bins_(predicted,actual,n)': rows,
            'brier': float(np.mean((p - y) ** 2))}

def odds_table(w):
    out = {}
    for p in bs.SKILL:
        d = pd.DataFrame({'pos': [p] * len(PICKS), 'pick': [float(k) for k in PICKS]})
        out[p] = {k: round(float(v), 3) for k, v in zip(PICKS, capped_pred(w, d))}
    return out

def main():
    ap = argparse.ArgumentParser(); m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument('--count', action='store_true'); m.add_argument('--run', action='store_true')
    a = ap.parse_args()
    lock = None
    if a.run: bs.PREREG = PREREG; lock = bs.require_locked_prereg()
    old = build_old(read_outcomes=a.run)
    print(f"[ODDS2] drafted 2000-2014: {len(old)} · no nflverse ID (counted as misses): {int(old['pid'].isna().sum())} · "
          f"by position {old['pos'].value_counts().to_dict()}")
    if a.count: print('[ODDS2] --count: no outcomes computed.'); return

    yo = old['hit'].to_numpy(float)
    primary = honest(loco(old, OLD), yo)
    new, _ = re1.build(read_outcomes=True); yn = new['hit'].to_numpy(float)
    modern = honest(loco(new, NEW), yn)
    w_old, w_new = capped_fit(old), capped_fit(new)
    cross = honest(capped_pred(w_old, new), yn)
    out = {'lock': lock,
           'PRIMARY_capped_method_on_unseen_2000_2014': primary,
           'REQUIRED_capped_method_on_2015_2023': modern,
           'SHIP_ODDS_DISPLAY': bool(primary['HONEST'] and modern['HONEST']),
           'reported_old_plain_curve_on_2000_2014': honest(loco(old, OLD, capped=False), yo),
           'reported_hit_rates': {'2000_2014': old.groupby('pos')['hit'].mean().to_dict(), '2015_2023': new.groupby('pos')['hit'].mean().to_dict()},
           'reported_era_comparison_odds': {'fitted_2000_2014': odds_table(w_old), 'fitted_2015_2023': odds_table(w_new),
                                            'ceiling': {'2000_2014': float(1 / (1 + np.exp(-w_old[-1]))), '2015_2023': float(1 / (1 + np.exp(-w_new[-1])))}},
           'reported_cross_era_old_fit_applied_to_2015_2023': cross,
           'ship_curve_2015_2023': {'weights': [float(x) for x in w_new], 'positions_order': bs.SKILL}}
    print(json.dumps(out, indent=2, default=float))
    (ROOT / 'data-cache' / 'role-entry-v2-result.json').write_text(json.dumps(out, indent=2, default=float))

if __name__ == '__main__':
    main()
