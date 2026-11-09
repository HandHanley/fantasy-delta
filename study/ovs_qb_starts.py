#!/usr/bin/env python3
"""
DELTA — OWN VALUE SCALE: QB GAMES BY THE START PROFILE RULE. Implements docs/PREREG-ovs-available-ppg.md §8 (measured).

Week 9, 2013-2022. B = points per available game with §7 (first-year QBs count only games played). S = the same, with
QB games and cameos by qb_games.py; a first-year QB with no game yet takes his incoming-rookie value (preseason frame
Sb, kind R0) and is left out of every pool.

    python ovs_qb_starts.py --nflverse D --rosters D --weekly D --wrost D --inj D --sched FILE --snaps D
"""
import argparse, json, os
import numpy as np
import comps_value_study as C
import ovs_in_season as I
import injury_weeks as J
import ovs_available_ppg as AP
import qb_games as QG

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
WEEK = 9


def qb_frame(W, games, cameos):
    """Weekly frame with QB cameo weeks emptied and QB starts without a stat counted as games."""
    W2 = W.copy()
    key = list(zip(W2.player_id, W2.season.astype(int), W2.week.astype(int)))
    cam = np.array([k in cameos for k in key]); gm = np.array([k in games for k in key])
    W2.loc[cam, 'P'] = 0.0; W2.loc[cam, 'g'] = 0; W2.loc[gm, 'g'] = 1
    return W2, int(cam.sum()), int((gm & (W.g.values == 0)).sum())


def build_S(Sin, W, st, L_full, L_upto, a, sched, snaps, players):
    games, cameos = QG.qb_weeks(a.weekly, sched, snaps, players, 22)
    qb_season = {(k, int(y)) for k, y, p in zip(st.player_id, st.season, st.position) if p == 'QB'}   # §8 note A
    games = {x for x in games if (x[0], x[1]) in qb_season}; cameos = {x for x in cameos if (x[0], x[1]) in qb_season}
    W2, n_cam, n_add = qb_frame(W, games, cameos)
    A_up = J.available_weeks(a.weekly, a.wrost, a.inj, WEEK, drop=cameos, add=games)
    A_fu = J.available_weeks(a.weekly, a.wrost, a.inj, 22, drop=cameos, add=games)
    prod, _ = AP.prod_available(Sin, W2, WEEK, L_full, L_upto, st, A_fu, A_up, rookie_qb_sits=True)
    S = Sin.copy(); S['prod'] = prod
    none = (S.kind.values == 'V') & np.isnan(prod)
    S.loc[none, 'kind'] = 'X'                                           # incoming-rookie value; out of every pool
    return S, none, {'cameo_rows_emptied': n_cam, 'starts_without_stat_added': n_add}


def main():
    ap = argparse.ArgumentParser()
    for k in ('nflverse', 'rosters', 'weekly', 'wrost', 'inj', 'sched', 'snaps'): ap.add_argument('--' + k, required=True)
    a = ap.parse_args()
    st, W, Sin, Sb, skipped = I.build(a.nflverse, a.rosters, a.weekly, WEEK)
    L_full, L_upto = I.levels(W)
    rows = Sin.index[(Sin.t >= I.TEST[0]) & (Sin.t <= I.TEST[1])].values
    yi = np.nan_to_num(Sin.FV.values.astype(float)); yt = yi[rows]
    players = os.path.join(a.nflverse, 'players.csv')
    A_up = J.available_weeks(a.weekly, a.wrost, a.inj, WEEK); A_fu = J.available_weeks(a.weekly, a.wrost, a.inj, 22)
    pB_, _ = AP.prod_available(Sin, W, WEEK, L_full, L_upto, st, A_fu, A_up, rookie_qb_sits=True)
    SB = Sin.copy(); SB['prod'] = pB_
    SS, none, parts = build_S(Sin, W, st, L_full, L_upto, a, a.sched, a.snaps, players)
    changed = ~np.isclose(SB['prod'].values, SS['prod'].values, equal_nan=True)
    assert not (changed & (Sin.pos.values != 'QB')).any(), 'a non-QB row changed'
    assert (Sin.pos.values[none] == 'QB').all() and Sin.rookie_Y.values[none].all()
    C.W_V['games'] = 0.0
    ti, nn, w = I.match(SB, rows); pB = AP.paired(rows, ti, nn, w, yi)
    xr = rows[none[rows]]; vr = rows[~none[rows]]
    ti, nn, w = I.match(SS, vr); pS = np.zeros(len(rows)); ix = {int(r): j for j, r in enumerate(rows)}
    pv = AP.paired(vr, ti, nn, w, yi)
    for r, v in zip(vr, pv): pS[ix[int(r)]] = v
    if len(xr):
        tb, nnb, wb = I.match(Sb, xr); px = AP.paired(xr, tb, nnb, wb, yi)
        assert (Sb.kind.values[xr] == 'R0').all()
        for r, v in zip(xr, px): pS[ix[int(r)]] = v
    q = Sin.pos.values[rows] == 'QB'; rq = q & Sin.rookie_Y.values[rows]

    def part(m):
        return {'rows': int(m.sum()), 'rmse_rule': C.rmse(pS[m], yt[m]), 'rmse_before': C.rmse(pB[m], yt[m]),
                'change': float(1 - C.rmse(pS[m], yt[m]) / C.rmse(pB[m], yt[m])),
                'produced_over_rule': float(yt[m].sum() / pS[m].sum()), 'produced_over_before': float(yt[m].sum() / pB[m].sum())}
    res = {'amendment': 'docs/PREREG-ovs-available-ppg.md §8', 'rows': int(len(rows)), 'data': parts,
           'qb_rows_production_changed_all_seasons': int(changed.sum()), 'rows_valued_as_incoming_rookie_all_seasons': int(none.sum()),
           'rows_valued_as_incoming_rookie_test': int(len(xr)),
           'all_rows': part(np.ones(len(rows), bool)), 'qb_rows': part(q), 'first_year_qb_rows': part(rq),
           'trades': I.trades(Sin, rows, pS, pB, yt)}
    json.dump(res, open(os.path.join(OUT, 'ovs_qb_starts_results.json'), 'w'), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == '__main__':
    main()
