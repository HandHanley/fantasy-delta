#!/usr/bin/env python3
"""
DELTA — OWN VALUE SCALE WITH OFFSEASON CHANGES. Implements docs/PREREG-ovs-offseason.md.

Starts from the adopted offseason value (ovs_era.py: era-adjusted matching, three seasons ahead) and adds two facts
about each veteran's situation for the coming season, known by its first weeks:
  share    his points last season / last season's points of everyone at his position on his club (his first listing in
           weeks 1-5 of the season; him included). A big signing lowers it; a departure raises it. A player on no roster: 0.
  capital  his first-game team's round 1-2 draft picks at his position that spring (0, 1, 2...).
Veteran matching adds them (weights 1.5 and 1.0); everything else unchanged. Rookies unchanged.

    python ovs_offseason.py --nflverse D --rosters D --week1 FILE --counts-only | --crash | --run
"""
import argparse, json, os
import numpy as np
import pandas as pd
import comps_value_study as C
import comps_draft_drop as DD
import own_value_scale as V
import ovs_era as E

W_NEW = {'share': 1.5, 'capital': 1.0}
ON_TEAM = {'ACT', 'RES', 'INA', 'SUS', 'PUP', 'NON', 'EXE', 'RSN', 'RSR', 'NWT'}   # on the club, not cut/FA/practice squad
CANON = {'ARZ': 'ARI', 'BLT': 'BAL', 'CLV': 'CLE', 'HST': 'HOU', 'SL': 'STL', 'GNB': 'GB', 'KAN': 'KC', 'NOR': 'NO',
         'NWE': 'NE', 'SDG': 'SD', 'SFO': 'SF', 'TAM': 'TB', 'LAR': 'LA', 'LVR': 'LV'}
LIFT_BAR, ALPHA, ALL_GUARD, TRADE_GUARD = 0.02, 0.05, -0.005, -1.0
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')


def first_game_rosters(path):
    R = pd.read_csv(path, low_memory=False)
    R['team'] = R.team.replace(CANON)
    # a player's club = his first listing, on the club (not cut or practice squad), in the season's first five weeks.
    # Five so a player serving a four-game suspension still has his club (early files omit him until he returns: Jimmy
    # Smith 2003 first appears in week 5); no later, so most mid-season signings the market couldn't know stay out.
    first = R.groupby(['season', 'team']).week.transform('min')       # each club's first game (2017: Irma)
    R = R[(R.week <= first + 4) & R.status.isin(ON_TEAM) & R.gsis_id.notna()]
    return R.sort_values(['season', 'week']).drop_duplicates(['season', 'gsis_id'])


def features(S, st, dp, R):
    """share and capital for every veteran row (key, t): situation entering season t+1."""
    team = {(int(s), g): t for s, g, t in zip(R.season, R.gsis_id, R.team)}
    pts = {(k, int(y)): (float(p), ps) for k, y, p, ps in zip(st.player_id, st.season, st.P, st.position)}
    # group points: season-t points of players at position p on club c's first-game roster of t+1
    grp = {}
    for (s, k), c in team.items():                   # keyed (season, player)
        p_ = pts.get((k, s - 1))
        if p_: grp[(s, c, p_[1])] = grp.get((s, c, p_[1]), 0.0) + p_[0]
    d = dp.copy(); d['team'] = d.team.replace(CANON)
    cap = d[d.pick <= 64].groupby(['season', 'team', 'position']).size().to_dict()
    share, capital, noteam = [], [], 0
    for k, t, ps, kd in zip(S.key.values, S.t.values, S.pos.values, S.kind.values):
        if kd != 'V': share.append(np.nan); capital.append(np.nan); continue
        c = team.get((int(t) + 1, k))
        if c is None:
            noteam += 1; share.append(0.0); capital.append(0.0); continue
        mine = pts.get((k, int(t)), (0.0, ps))[0]
        g = grp.get((int(t) + 1, c, ps), 0.0)
        if mine > 0 and pts.get((k, int(t)), (0, None))[1] != ps: g += mine     # counted under another position
        share.append(mine / g if g > 0 else 1.0)
        capital.append(float(cap.get((int(t) + 1, c, ps), 0)))
    return np.array(share), np.array(capital), noteam


def neighbours_off(S, rows, pool_max_t=None):
    """comps_draft_drop.neighbours, mode A, with share and capital added to veteran matching."""
    keys = S.key.values; tt = S.t.values; pos = S.pos.values; kind = S.kind.values
    out_rows, out_nn = [], []
    for t in sorted(set(tt[rows])):
        pmax = t - C.POOL_LAG if pool_max_t is None else pool_max_t
        pool_all = S.index[(S.t >= C.SNAP_FIRST) & (S.t <= pmax)].values
        rows_t = rows[tt[rows] == t]
        for p in C.POS:
            for kd in ('V', 'R0'):
                trow = rows_t[(pos[rows_t] == p) & (kind[rows_t] == kd)]
                if not len(trow): continue
                prow = pool_all[(pos[pool_all] == p) & (kind[pool_all] == kd)]
                if kd == 'V':
                    feats = ['prod', 'age', 'draft', 'cy', 'games', 'share', 'capital']
                    Wb = DD.vet_weights('A', S.loc[trow, 'G'].values.astype(float), S.cy.values[trow])
                    Wm = np.column_stack([Wb, np.full(len(trow), W_NEW['share']), np.full(len(trow), W_NEW['capital'])])
                else:
                    feats = ['draft', 'age']; Wm = np.tile([C.W_R0['draft'], C.W_R0['age']], (len(trow), 1))
                P = S.loc[prow, feats].values.astype(float)
                mu, sd = P.mean(0), P.std(0); sd[sd == 0] = 1.0
                Pz = (P - mu) / sd; Tz = (S.loc[trow, feats].values.astype(float) - mu) / sd
                d2 = (((Tz[:, None, :] - Pz[None, :, :]) ** 2) * Wm[:, None, :]).sum(2)
                for i, r in enumerate(trow):
                    same = keys[prow] == keys[r]
                    dd = d2[i].copy(); dd[same] = np.inf
                    n_avail = int((~same).sum())
                    if n_avail < C.K_MIN: continue
                    out_rows.append(r); out_nn.append(prow[np.argsort(dd, kind='stable')[:min(30, n_avail)]])
    return {'test': np.array(out_rows, dtype=int), 'nn': {30: out_nn}}


def setup(nflverse, rosters, week1):
    st, S, S2, pre, nnA, W, nn2, W2, counts = E.setup(nflverse, rosters)        # adopted value: S2 / nn2 / W2
    dp = pd.read_csv(os.path.join(nflverse, 'draft_picks.csv'), low_memory=False)
    R = first_game_rosters(week1)
    S3 = S2.copy()
    S3['share'], S3['capital'], noteam = features(S3, st, dp, R)
    T = pre['test']
    pc = neighbours_off(S3, T)
    lookup = {int(r): nn for r, nn in zip(pc['test'], pc['nn'][30])}
    assert set(lookup) == set(int(r) for r in T), 'offseason rows differ'
    nn3, W3 = [], []
    for r in T:
        nn = lookup[int(r)]
        assert (S3.t.values[nn] <= S3.t.values[r] - E.HORIZON).all() and S3.key.values[r] not in set(S3.key.values[nn])
        w = 0.5 ** ((S3.t.values[r] - S3.t.values[nn]) / V.HALF_LIFE); nn3.append(nn); W3.append(w / w.sum())
    rk = S3.kind.values[T] == 'R0'
    assert all(np.array_equal(a, b) for a, b, k in zip(nn2, nn3, rk) if k), 'rookie matches changed'
    v = S3.kind.values == 'V'
    counts.update({'veteran_rows': int(v.sum()), 'no_first_game_roster': int(noteam),
                   'share_median_by_pos': {p: round(float(np.median(S3.share.values[v & (S3.pos.values == p)])), 3) for p in C.POS},
                   'capital_rows_with_pick': int((S3.capital.values[v] > 0).sum())})
    return st, S3, pre, nn2, W2, nn3, W3, counts


def q(S, pre, p_new, p_old, yt, n_perm=E.N_PERM):
    T = pre['test']; cl = S.key.values[T]
    rb = (S.kind.values[T] == 'V') & (S.pos.values[T] == 'RB')
    lift, p = C.perm_test(yt[rb], p_new[rb], p_old[rb], cl[rb], n_perm)
    lift_all = 1 - C.rmse(p_new, yt) / C.rmse(p_old, yt)
    return {'rb_rows': int(rb.sum()), 'rb_lift': float(lift), 'rb_p': float(p), 'all_lift': float(lift_all), 'lift': float(lift),
            'pass': bool(lift >= LIFT_BAR and p < ALPHA and lift_all >= ALL_GUARD)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nflverse', required=True); ap.add_argument('--rosters', required=True); ap.add_argument('--week1', required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--counts-only', action='store_true'); g.add_argument('--crash', action='store_true'); g.add_argument('--run', action='store_true')
    ap.add_argument('--runs', type=int, default=200)
    a = ap.parse_args()
    st, S, pre, nn2, W2, nn3, W3, counts = setup(a.nflverse, a.rosters, a.week1)
    print(json.dumps(counts, indent=1, default=float))
    if a.counts_only: return
    y = S.FV.values.astype(float); T = pre['test']
    if a.crash:
        E.q1 = lambda S_, pre_, pn, po, yt, n_perm=1000: q(S_, pre_, pn, po, yt, n_perm)      # same worlds, this rule
        res = E.crash(S, S, pre, nn2, W2, nn3, W3, y, a.runs); res['counts'] = counts
        json.dump(res, open(os.path.join(OUT, 'ovs_offseason_crash.json'), 'w'), indent=1, default=float)
        print('crash tests:', 'PASS' if res['noise']['ok'] and res['planted_0.75']['ok'] else 'FAIL'); return
    po, pn = E.preds(nn2, W2, y), E.preds(nn3, W3, y); yt = y[T]
    res = {'prereg': 'docs/PREREG-ovs-offseason.md', 'counts': counts, 'Q': q(S, pre, pn, po, yt), 'trades': E.q2(S, pre, pn, po, yt)}
    res['by_position'] = {p: float(1 - C.rmse(pn[S.pos.values[T] == p], yt[S.pos.values[T] == p]) / C.rmse(po[S.pos.values[T] == p], yt[S.pos.values[T] == p])) for p in C.POS}
    res['decision'] = 'adopt offseason features' if res['Q']['pass'] and res['trades']['guard_ok'] else 'keep the adopted value'
    json.dump(res, open(os.path.join(OUT, 'ovs_offseason_results.json'), 'w'), indent=1, default=float)
    print(json.dumps({k: res[k] for k in ('Q', 'trades', 'by_position', 'decision')}, indent=1, default=float))


if __name__ == '__main__':
    main()
