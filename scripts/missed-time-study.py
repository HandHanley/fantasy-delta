#!/usr/bin/env python3
"""
DELTA Missed-Time Penalty Sizes — scripts/missed-time-study.py
Pre-registration: docs/PREREG-missed-time.md

    python3 scripts/missed-time-study.py --count   # eligibility only; computes NO errors
    python3 scripts/missed-time-study.py --run     # refuses unless the pre-registration is committed

Owner rule (handoff §2, 26 Sep 2026): missed time counts. Only the SIZE of each penalty is on trial;
a fitted size is capped at x1.00 (it may shrink to "no penalty", never become a bonus).

Groups, by games played in the season before the one being predicted (the engine's g25):
  S1  sat out that season, played the one before     current x0.66  (x0.75 stale discount, then -12%)
  S2  sat out that season AND the one before it      current x0.615 (x0.75, then -18%)
  P1  played 1-3 games                               current x0.92  (-8%)
  P2  played 4-7 games                               current x0.96  (-4%)
The starting number is the engine's own rule (3/2/1 steps), imported from scripts/weights-study.py so
the two studies cannot drift.
EVALUATION: leave-one-season-out over all eight seasons 2018-2025 — each season is predicted with sizes
fitted on the other seven, never on itself — because a single 2023-25 hold-out has only 125 cases.
S2 has too few cases (6) to size alone: it keeps today's extra penalty relative to S1 (0.615 / 0.66). The -12/-18/-8/-4 sit inside calcProj's delta clamp in the live engine;
this study applies them as plain multipliers (disclosed in the pre-registration).
"""
import argparse, importlib.util, json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
def _load(n, f):
    s = importlib.util.spec_from_file_location(n, ROOT / 'scripts' / f); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
ws = _load('ws', 'weights-study.py'); bs = ws.bs

PREREG = 'docs/PREREG-missed-time.md'
SEASONS = ws.TRAIN + ws.HELDOUT      # 2018-2025, each held out in turn
MIN_SEASONS_BETTER = 6               # of 8
CURRENT = {'S1': 0.75 * (1 - 0.12), 'S2': 0.75 * (1 - 0.18), 'P1': 0.92, 'P2': 0.96}
MIN_POS_N, SEED, SHUFFLES = 30, 20260927, 2000

def group(r):
    g = r['g']
    if g[0] == 0: return 'S1' if g[1] > 0 else ('S2' if g[2] > 0 else None)
    if 1 <= g[0] <= 3: return 'P1'
    if 4 <= g[0] <= 7: return 'P2'
    return None

def build(g):
    df = ws.build_rows(g)                           # same eligibility as the weights study: 8+ prior games, 6+ now
    df['grp'] = [group(r) for r in df.to_dict('records')]
    df['base'] = [ws.base(r, *ws.ENGINE) for r in df.to_dict('records')]
    return df[df['grp'].notna()].reset_index(drop=True)

def rmse(e): return float(np.sqrt(np.mean(e ** 2)))

def main():
    ap = argparse.ArgumentParser(); m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument('--count', action='store_true'); m.add_argument('--run', action='store_true')
    a = ap.parse_args()
    lock = None
    if a.run: bs.PREREG = PREREG; lock = bs.require_locked_prereg()
    g, _ = bs.load_games()
    df = build(g)
    t = df.groupby(['season', 'grp']).size().unstack('grp').fillna(0).astype(int)
    print('[MISSED] graded player-seasons (came back and played 6+ games):'); print(t.to_string())
    print(f"[MISSED] all seasons {len(df)} · by group {df['grp'].value_counts().to_dict()} · by position "
          f"{df['pos'].value_counts().to_dict()} · distinct players {df['pid'].nunique()}")
    if a.count: print('[MISSED] --count: no errors computed.'); return

    def fit(d):
        out, raw = {}, {}
        for k in ('S1', 'P1', 'P2'):
            dk = d[d['grp'] == k]
            m_ = float((dk['base'] * dk['actual']).sum() / (dk['base'] ** 2).sum()) if len(dk) else CURRENT[k]
            raw[k] = m_; out[k] = min(1.0, m_)
        out['S2'] = out['S1'] * CURRENT['S2'] / CURRENT['S1']; raw['S2'] = raw['S1'] * CURRENT['S2'] / CURRENT['S1']
        return out, raw
    te = df.copy(); fitted_by_season = {}
    mB = np.zeros(len(te))
    for s_ in SEASONS:                                # each season predicted with sizes fitted on the other seven
        f_, _ = fit(df[df['season'] != s_]); fitted_by_season[s_] = f_
        mk = (te['season'] == s_).to_numpy()
        mB[mk] = [f_[k] for k in te.loc[mk, 'grp']]
    fitted_all, raw_all = fit(df)                     # reported: the sizes that would ship, fitted on all eight
    print('[MISSED] current sizes', {k: round(v, 3) for k, v in CURRENT.items()})
    print('[MISSED] sizes fitted on all eight seasons (capped at 1.00)', {k: round(v, 3) for k, v in fitted_all.items()},
          '| uncapped', {k: round(v, 3) for k, v in raw_all.items()})

    y, b, grp = te['actual'].to_numpy(), te['base'].to_numpy(), te['grp'].to_numpy()
    eA = b * np.array([CURRENT[k] for k in grp]) - y
    eB = b * mB - y
    lift = 1 - rmse(eB) / rmse(eA)
    rng = np.random.default_rng(SEED)
    uniq, inv = np.unique(te['pid'].to_numpy(), return_inverse=True); ge = 0
    for _ in range(SHUFFLES):
        f = (rng.random(len(uniq)) < 0.5)[inv]
        if 1 - rmse(np.where(f, eA, eB)) / rmse(np.where(f, eB, eA)) >= lift: ge += 1
    p = (ge + 1) / (SHUFFLES + 1)
    s_arr, p_arr = te['season'].to_numpy(), te['pos'].to_numpy()
    sub = lambda mk: 1 - rmse(eB[mk]) / rmse(eA[mk]) if mk.any() else None
    per_season = {int(s): sub(s_arr == s) for s in SEASONS}
    per_pos = {ps: sub(p_arr == ps) for ps in bs.SKILL}
    pos_n = {ps: int((p_arr == ps).sum()) for ps in bs.SKILL}
    per_group = {k: {'n': int((grp == k).sum()), 'lift': sub(grp == k),
                     'current_rmse': rmse(eA[grp == k]) if (grp == k).any() else None,
                     'fitted_rmse': rmse(eB[grp == k]) if (grp == k).any() else None} for k in CURRENT}
    gates = {'size_>=2%': lift >= 0.02, 'p<0.05': p < 0.05,
             f'better_in_{MIN_SEASONS_BETTER}_of_8_seasons': sum(1 for v in per_season.values() if v is not None and v > 0) >= MIN_SEASONS_BETTER,
             'no_position_worse_than_-1%_(n>=30)': all(v >= -0.01 for k, v in per_pos.items() if v is not None and pos_n[k] >= MIN_POS_N)}
    out = {'lock': lock, 'current': CURRENT, 'ship_sizes_fitted_all_seasons': fitted_all, 'uncapped_reported_only': raw_all,
           'fitted_by_held_out_season': fitted_by_season,
           'heldout': {'n': int(len(te)), 'current_rmse': rmse(eA), 'fitted_rmse': rmse(eB), 'lift': lift, 'p': p,
                       'current_mae': float(np.mean(np.abs(eA))), 'fitted_mae': float(np.mean(np.abs(eB)))},
           'per_season': per_season, 'per_position': per_pos, 'position_n': pos_n, 'per_group_reported_only': per_group,
           'gates': gates, 'SHIP': all(gates.values())}
    print(json.dumps(out, indent=2, default=float))
    (ROOT / 'data-cache' / 'missed-time-result.json').write_text(json.dumps(out, indent=2, default=float))

if __name__ == '__main__':
    main()
