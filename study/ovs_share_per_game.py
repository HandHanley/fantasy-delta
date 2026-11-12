#!/usr/bin/env python3
"""
DELTA — OWN VALUE SCALE: ROSTER SHARE PER GAME. Implements docs/DECISION-roster-share-per-game.md.

Decided by rule (no availability penalty); this measures the cost and decides nothing. The preseason value's roster
share used his season TOTAL points, so weeks he missed hurt lowered it.
  v1 (first measurement, superseded): points per game x his club's games. It also rescaled healthy backups who simply
     didn't play (Hoyer, Howell, Barkley with one game), which is a bonus for not playing, not injury neutrality.
  v2 (the rule): points per AVAILABLE game x (available weeks + weeks out hurt): only weeks hurt are filled in, at his
     rate; healthy weeks he didn't play stay zeros. Same available/hurt definitions as the adopted in-season value.

    python ovs_share_per_game.py --nflverse D --rosters D --week1 FILE --weekly D --wrost D --inj D [--v1]
"""
import argparse, json, os
import numpy as np
import pandas as pd
import comps_value_study as C
import comps_draft_drop as DD
import ovs_era as E
import ovs_offseason as O
import own_value_scale as V
import injury_weeks as J

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
MISSED = 10                                     # "missed time": <= 10 games in the snapshot season (as ovs_no_games.py)
EXPECT_ADOPTED_RMSE = 50.53434058613906         # ovs_no_games.py re-run 12 Nov on this data folder (preseason.rmse_without);
                                                # the 8 Nov results file reads 50.536348 (data refresh, 0.004%)


def season_games(t):
    return 16 if t <= 2020 else 17


HURT, AVAIL = {}, {}                            # filled by main for v2: {(gsis_id, season): weeks}
MODE = 'v2'


def features_per_game(S, st, dp, R):
    """ovs_offseason.features with one change: his own season-t points are rescaled (v1 or v2, see the docstring)."""
    team = {(int(s), g): t for s, g, t in zip(R.season, R.gsis_id, R.team)}
    pts = {(k, int(y)): (float(p), ps, float(g)) for k, y, p, ps, g in zip(st.player_id, st.season, st.P, st.position, st.games)}
    grp = {}
    for (s, k), c in team.items():
        p_ = pts.get((k, s - 1))
        if p_: grp[(s, c, p_[1])] = grp.get((s, c, p_[1]), 0.0) + p_[0]
    d = dp.copy(); d['team'] = d.team.replace(O.CANON)
    cap = d[d.pick <= 64].groupby(['season', 'team', 'position']).size().to_dict()
    share, capital, noteam, scaled = [], [], 0, 0
    for k, t, ps, kd in zip(S.key.values, S.t.values, S.pos.values, S.kind.values):
        if kd != 'V': share.append(np.nan); capital.append(np.nan); continue
        c = team.get((int(t) + 1, k))
        if c is None:
            noteam += 1; share.append(0.0); capital.append(0.0); continue
        mine, mps, mg = pts.get((k, int(t)), (0.0, ps, 0.0))
        g = grp.get((int(t) + 1, c, ps), 0.0)
        if mine > 0 and mps != ps: g += mine                                     # counted under another position
        if mg >= 1:
            if MODE == 'v1':
                full = mine / mg * max(mg, season_games(int(t)))                 # never below what he actually scored
            else:
                av = max(AVAIL.get((k, int(t)), 0), mg)                           # available weeks (>= games played)
                full = mine + mine / av * HURT.get((k, int(t)), 0) * (season_games(int(t)) > 0)
            if full > mine + 1e-9: scaled += 1                                   # float-safe count
            if mps == ps or mine > 0: g = g - mine + full                        # his own points in the group, rescaled
            mine = full
        share.append(mine / g if g > 0 else 1.0)
        capital.append(float(cap.get((int(t) + 1, c, ps), 0)))
    return np.array(share), np.array(capital), noteam, scaled


def match(S, T):
    pc = O.neighbours_off(S, T)
    look = {int(r): nn for r, nn in zip(pc['test'], pc['nn'][30])}
    assert set(look) == set(int(r) for r in T)
    nn_, W_ = [], []
    for r in T:
        nn = look[int(r)]
        assert (S.t.values[nn] <= S.t.values[r] - E.HORIZON).all() and S.key.values[r] not in set(S.key.values[nn])
        w = 0.5 ** ((S.t.values[r] - S.t.values[nn]) / V.HALF_LIFE); nn_.append(nn); W_.append(w / w.sum())
    return nn_, W_


def main():
    ap = argparse.ArgumentParser()
    for k in ('nflverse', 'rosters', 'week1', 'weekly', 'wrost', 'inj'): ap.add_argument('--' + k, required=True)
    ap.add_argument('--v1', action='store_true', help='the superseded all-games rescale')
    a = ap.parse_args()
    global MODE
    MODE = 'v1' if a.v1 else 'v2'
    HURT.update(J.injured_weeks(a.weekly, a.wrost, a.inj, 22)); AVAIL.update(J.available_weeks(a.weekly, a.wrost, a.inj, 22))
    st, S, pre, nn2, W2, nn3, W3, counts = O.setup(a.nflverse, a.rosters, a.week1)   # S carries today's share/capital
    C.W_V['games'] = 0.0                                                                # adopted: games out (8 Nov)
    T = pre['test']; y = S.FV.values.astype(float); yt = y[T]
    nn_o, W_o = match(S, T); po = E.preds(nn_o, W_o, y)
    assert abs(C.rmse(po, yt) - EXPECT_ADOPTED_RMSE) < 1e-6, ('adopted value not reproduced', C.rmse(po, yt))
    # equivalence: the new function with no scaling (season_games -> 0) gives today's share exactly
    dp = pd.read_csv(os.path.join(a.nflverse, 'draft_picks.csv'), low_memory=False)
    R = O.first_game_rosters(a.week1)
    global season_games
    _sg = season_games; season_games = lambda t: 0
    s0, c0, _, sc0 = features_per_game(S, st, dp, R)
    season_games = _sg
    v = S.kind.values == 'V'
    assert sc0 == 0 and np.allclose(s0[v], S.share.values[v]) and np.allclose(c0[v], S.capital.values[v]), 'equivalence failed'
    S2 = S.copy()
    S2['share'], S2['capital'], noteam, scaled = features_per_game(S, st, dp, R)
    assert np.allclose(S2.capital.values[v], S.capital.values[v])
    nn_n, W_n = match(S2, T); pn = E.preds(nn_n, W_n, y)
    vet = S.kind.values[T] == 'V'
    assert all(np.array_equal(a_, b_) for a_, b_, k in zip(nn_o, nn_n, vet) if not k), 'rookie matches changed'
    cl = S.key.values[T]; pos = S.pos.values[T]
    lift, p = C.perm_test(yt, pn, po, cl, E.N_PERM)
    missed = vet & (S.games.values[T] <= MISSED)
    moved = v[T] & ~np.isclose(S2.share.values[T], S.share.values[T])
    res = {'decision_doc': 'docs/DECISION-roster-share-per-game.md', 'mode': MODE, 'rows': int(len(T)),
           'veteran_rows_share_raised_all_seasons': int(scaled),
           'test_rows_share_changed': int(moved.sum()),
           'rmse_today': C.rmse(po, yt), 'rmse_per_game': C.rmse(pn, yt), 'change': float(lift), 'p_better': float(p),
           'by_position': {q: float(1 - C.rmse(pn[pos == q], yt[pos == q]) / C.rmse(po[pos == q], yt[pos == q])) for q in C.POS},
           'trades': E.q2(S, pre, pn, po, yt)}
    for lab, m in (('missed_time', missed), ('did_not_miss', vet & ~missed), ('share_changed', moved)):
        res[lab] = {'rows': int(m.sum()), 'produced_over_value_today': float(yt[m].sum() / po[m].sum()),
                    'produced_over_value_per_game': float(yt[m].sum() / pn[m].sum()),
                    'rmse_change': float(1 - C.rmse(pn[m], yt[m]) / C.rmse(po[m], yt[m]))}
    # examples: biggest share increases among test rows
    d = pd.DataFrame({'name': S.name.values[T], 't': S.t.values[T], 'pos': pos, 'games': S.games.values[T],
                      'share_today': S.share.values[T], 'share_new': S2.share.values[T], 'value_today': po, 'value_new': pn})
    d = d[moved].assign(up=lambda x: x.share_new - x.share_today).sort_values('up', ascending=False).head(12)
    res['examples'] = d.round(3).to_dict('records')
    name = 'ovs_share_per_game_results_v1_all_games.json' if MODE == 'v1' else 'ovs_share_per_game_results.json'
    json.dump(res, open(os.path.join(OUT, name), 'w'), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == '__main__':
    main()
