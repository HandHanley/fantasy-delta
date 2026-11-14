#!/usr/bin/env python3
"""
DELTA — NEW VALUE: A DEAD-WEIGHT SEASON COSTS A ROSTER SPOT. Implements docs/DECISION-roster-spot-cost.md; where they
disagree, the document wins.

FV_rc = sum over t+1..t+3 of 0.9^(k-1) x [max(0, points - line) - c x dead], dead = played 1+ games and under the line.
c = the starter points per season that the players ranked 301st-336th by today's value (12 teams x 28) went on to
produce, seasons 2006-2012. Safety check: rank correlation with today's FV on 2013-2022 no more than 0.01 lower.

    python ovs_roster_cost.py --nflverse D --rosters D --weekly D --wrost D --inj D --sched FILE --snaps D
"""
import argparse, json, os
import numpy as np
import pandas as pd
import comps_value_study as C
import comps_in_season as CI
import ovs_small_samples as SSm
import ovs_one_match as M

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
ROSTER_LAST, ROSTER_FROM = 336, 301        # 12 teams x 28; the bottom 36 (three per team)
HORIZON, DISC = 3, 0.9
SEASON_SUM = 1 + 0.9 + 0.81
GUARD = 0.01
FULL_LINES = C.REPL_N_FULL_ADOPTED          # the weekly build's lines (full PPR)


def season_tables(st, P, lines):
    pts = {(r.player_id, int(r.season)): float(p) for r, p in zip(st.itertuples(), P)}
    gms = {(r.player_id, int(r.season)): int(r.games) for r in st.itertuples()}
    line = {}
    tmp = st.assign(_P=P)
    for (yr, ps), g in tmp.groupby(['season', 'position']):
        p = np.sort(g._P.values)[::-1]; line[(int(yr), ps)] = p[lines[ps] - 1] if len(p) >= lines[ps] else 0.0
    return pts, gms, line


def fv_rc(keys, ts, poss, pts, gms, line, c, last=2025):
    out = np.full(len(keys), np.nan)
    for i, (k, t, ps) in enumerate(zip(keys, ts, poss)):
        if t + HORIZON > last: continue
        v = 0.0
        for j in range(1, HORIZON + 1):
            p, g, L = pts.get((k, t + j), 0.0), gms.get((k, t + j), 0), line[(t + j, ps)]
            v += DISC ** (j - 1) * (max(0.0, p - L) - (c if (g >= 1 and p < L) else 0.0))
        out[i] = v
    return out


def spear(a, b):
    return float(pd.Series(a).corr(pd.Series(b), method='spearman'))


def main():
    ap = argparse.ArgumentParser()
    for k in ('nflverse', 'rosters', 'weekly', 'wrost', 'inj', 'sched', 'snaps'): ap.add_argument('--' + k, required=True)
    a = ap.parse_args()
    G = M.frame(a)
    S, rows, y = G['S'], G['rows'], G['y']
    st, dp, pl, W = CI.load(a.nflverse, a.rosters, a.weekly)
    pts, gms, line = season_tables(st, st.P.values, C.REPL_N)
    K, T, PS = S.key.values, S.t.values, S.pos.values
    # the frame's own FV must reproduce exactly with c = 0 (study scoring, the frame's lines)
    f0 = fv_rc(K[rows], T[rows], PS[rows], pts, gms, line, 0.0)
    assert np.allclose(f0, S.FV.values[rows]), float(np.nanmax(np.abs(f0 - S.FV.values[rows])))

    # c: rows ranked 301st-336th by today's live value, each season 2006-2012
    today = M.values(G, y)
    t = T[rows]; fit = (t >= SSm.FIT[0]) & (t <= SSm.FIT[1])
    last = np.zeros(len(rows), bool)
    for tt in range(SSm.FIT[0], SSm.FIT[1] + 1):
        idx = np.where(t == tt)[0]
        assert len(idx) >= ROSTER_LAST, (tt, len(idx))
        order = idx[np.argsort(-today[idx], kind='stable')]
        last[order[ROSTER_FROM - 1:ROSTER_LAST]] = True
    assert (last & fit).sum() == 36 * 7
    yr = y[rows]
    c = float(yr[last].mean() / SEASON_SUM)
    # the same players rescored in the weekly build's scoring (full PPR, its lines)
    ptsF, gmsF, lineF = season_tables(st, st.fantasy_points_ppr.fillna(0).values, FULL_LINES)
    fF = fv_rc(K[rows][last], T[rows][last], PS[rows][last], ptsF, gmsF, lineF, 0.0)
    c_display = float(np.mean(fF) / SEASON_SUM)
    print('c (study scoring)', c, ' c_display (full PPR)', c_display, flush=True)

    # values on FV_rc: the same matches and weights, the new outcome
    y_rc = np.nan_to_num(fv_rc(K, T, PS, pts, gms, line, c))
    new = M.values(G, y_rc)
    m = G['test']
    sp_today, sp_new = spear(today[m], yr[m]), spear(new[m], yr[m])
    yrc = y_rc[rows]
    res = {'decision_doc': 'docs/DECISION-roster-spot-cost.md', 'week': SSm.WEEK, 'roster_spots': [ROSTER_FROM, ROSTER_LAST],
           'c': c, 'c_display': c_display, 'c_rows': int(last.sum()),
           'c_rows_share_with_any_starter_points': float((yr[last] > 0).mean()),
           'safety': {'rows': int(m.sum()), 'spearman_fv_today': sp_today, 'spearman_fv_new': sp_new,
                      'drop': sp_today - sp_new, 'allowed_drop': GUARD, 'pass': bool(sp_today - sp_new <= GUARD)},
           'reported': {
               'spearman_fv_rc': {'today': spear(today[m], yrc[m]), 'new': spear(new[m], yrc[m])},
               'rmse_fv': {'today': M.rmse(today[m], yr[m]), 'new': M.rmse(new[m], yr[m])},
               'rmse_fv_rc': {'today': M.rmse(today[m], yrc[m]), 'new': M.rmse(new[m], yrc[m])},
               'share_of_test_rows_charged_at_least_once': float(((yrc[m] < yr[m] - 1e-9)).mean())}}
    late = m & G['rook'] & G['on_draft'] & (G['pick'] > 100)
    res['reported']['late_round_rookies_on_draft_value'] = {'rows': int(late.sum()), 'mean_value_today': float(today[late].mean()),
                                                            'mean_value_new': float(new[late].mean()),
                                                            'mean_fv': float(yr[late].mean()), 'mean_fv_rc': float(yrc[late].mean())}
    json.dump(res, open(os.path.join(OUT, 'ovs_roster_cost_results.json'), 'w'), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == '__main__':
    main()
