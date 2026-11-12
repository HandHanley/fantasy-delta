#!/usr/bin/env python3
"""
DELTA — OWN VALUE SCALE: ROOKIES MATCH ROOKIES. Implements docs/PREREG-ovs-rookies-match-rookies.md; where they
disagree, the pre-registration wins.

Weeks 5, 9, 13 and 17 pooled (amendment A1), adopted in-season value (ovs_qb_starts.build_S, no games number). A rookie
row (no NFL game in an earlier season) is matched only to rookie rows. Decides on rookie rows valued from this season's
games, t = 2013-2022, all four weeks together; a player's rows are shuffled together in the permutation test.

    python ovs_rookies_match.py --nflverse D --rosters D --weekly D --wrost D --inj D --sched FILE --snaps D --counts
    python ovs_rookies_match.py ... --crash [--runs 200]      # before lock
    python ovs_rookies_match.py ... --run                     # once, after lock
"""
import argparse, json, os, pickle
import numpy as np
import pandas as pd
import comps_value_study as C
import ovs_in_season as I
import ovs_qb_starts as QS

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
WEEK = 9                                         # frame() builds this week; set by frames()
WEEKS = (5, 9, 13, 17)
LIFT_BAR, ALPHA, TRADE_GUARD = 0.02, 0.05, -1.0
CACHE = '/tmp/ovs_rookies_match_frame.pkl'      # week 9; other weeks add _w{week}
EXPECT_TEST_RMSE_TODAY = 48.461133390000334     # ovs_qb_starts.py all_rows.rmse_rule on this data folder (12 Nov)


def restrict(S, keep):
    """Copy of S where valued rows outside `keep` leave every pool (kind 'Z' is in no pool)."""
    S2 = S.copy()
    out = (S2.kind.values == 'V') & ~keep
    S2.loc[out, 'kind'] = 'Z'
    return S2


def by_row(ti, nn, w):
    return {int(r): (a, b) for r, a, b in zip(ti, nn, w)}


def frame(a):
    if os.path.exists(CACHE):
        return pickle.load(open(CACHE, 'rb'))
    C.HORIZON = I.HORIZON
    st, W, Sin, Sb, skipped = I.build(a.nflverse, a.rosters, a.weekly, WEEK)
    L_full, L_upto = I.levels(W)
    players = os.path.join(a.nflverse, 'players.csv')
    SS, none, parts = QS.build_S(Sin, W, st, L_full, L_upto, a, a.sched, a.snaps, players)
    C.W_V['games'] = 0.0
    rows = Sin.index[(Sin.t >= I.TEST[0]) & (Sin.t <= I.TEST[1])].values
    xr = rows[none[rows]]; vr = rows[~none[rows]]
    today = by_row(*I.match(SS, vr))
    assert (Sb.kind.values[xr] == 'R0').all()
    today.update(by_row(*I.match(Sb, xr)))                              # first-year QB, no game: incoming-rookie value
    assert set(today) == set(int(r) for r in rows)
    rook = SS.rookie_Y.values.astype(bool)
    dec = vr[rook[vr]]                                                  # rookie rows valued from this season's games
    assert (SS.kind.values[dec] == 'V').all()
    SR = restrict(SS, rook)
    SM = restrict(SS, rook | (SS.cy.values == 2))
    only = by_row(*I.match(SR, dec)); mid = by_row(*I.match(SM, dec))
    assert set(only) == set(mid) == set(int(r) for r in dec), 'a rookie row lost its matches'
    for r in dec:
        assert SS.rookie_Y.values[only[int(r)][0]].all()
        assert (SS.rookie_Y.values[mid[int(r)][0]] | (SS.cy.values[mid[int(r)][0]] == 2)).all()
    pool = {}
    t0 = int(Sin.t.values[dec].min())
    for p in C.POS:
        m = (SS.t.values <= t0 - I.LAG) & (SS.pos.values == p) & (SS.kind.values == 'V')
        pool[p] = {'rookie_rows': int((m & rook).sum()), 'all_rows': int(m.sum())}
    F = {'Sin': Sin, 'rows': rows, 'dec': dec, 'none': none, 'today': today, 'only': only, 'mid': mid,
         'pool_first_test_season': {'season': t0, 'by_position': pool}, 'parts': parts}
    pickle.dump(F, open(CACHE, 'wb'))
    return F


def pr(D, rows, y):
    return I.preds([D[int(r)][0] for r in rows], [D[int(r)][1] for r in rows], y)


def rmse(p, y):
    return float(np.sqrt(np.mean((p - y) ** 2)))


def frames(a):
    """One frame per week. Week 17 needs a through-week starter level, so it joins ovs_in_season.WEEKS for levels()."""
    if 17 not in I.WEEKS:
        I.WEEKS = tuple(I.WEEKS) + (17,)
    global WEEK, CACHE
    base = '/tmp/ovs_rookies_match_frame'
    out = {}
    for wk in WEEKS:
        WEEK = QS.WEEK = wk
        CACHE = f'{base}.pkl' if wk == 9 else f'{base}_w{wk}.pkl'
        out[wk] = frame(a)
    WEEK = QS.WEEK = 9; CACHE = f'{base}.pkl'
    return out


def stacked(FS, ymaps=None):
    """Deciding rookie rows from every week, stacked. ymaps: {week: outcome array} (default: each frame's real FV)."""
    P = {k: [] for k in ('today', 'only', 'mid', 'y', 'key', 'pos', 't', 'week')}
    for wk in WEEKS:
        F = FS[wk]; S, dec = F['Sin'], F['dec']
        y = ymaps[wk] if ymaps else np.nan_to_num(S.FV.values.astype(float))
        for k in ('today', 'only', 'mid'): P[k].append(pr(F[k], dec, y))
        P['y'].append(y[dec]); P['key'].append(S.key.values[dec]); P['pos'].append(S.pos.values[dec])
        P['t'].append(S.t.values[dec]); P['week'].append(np.full(len(dec), wk))
    return {k: np.concatenate(v) for k, v in P.items()}


def setup(a):
    FS = frames(a)
    F = FS[9]; S, rows = F['Sin'], F['rows']
    y = np.nan_to_num(S.FV.values.astype(float))
    assert abs(rmse(pr(F['today'], rows, y), y[rows]) - EXPECT_TEST_RMSE_TODAY) < 1e-6, 'week 9 today not reproduced'
    # one outcome per player-season, the same in every week's frame
    fv = {}
    for wk in WEEKS:
        Sw = FS[wk]['Sin']; done = Sw.complete.values
        for k, t, v in zip(Sw.key.values[done], Sw.t.values[done], Sw.FV.values[done]):
            assert fv.setdefault((k, int(t)), v) == v, ('FV differs between weeks', k, t)
    return FS, fv


def test(key, p_new, p_old, yd, n_perm):
    lift, p = C.perm_test(yd, p_new, p_old, key, n_perm)
    return {'rmse_new': rmse(p_new, yd), 'rmse_today': rmse(p_old, yd), 'lift': float(lift), 'p': float(p),
            'pass': bool(lift >= LIFT_BAR and p < ALPHA)}


def counts(a):
    FS, fv = setup(a)
    D = stacked(FS)
    return {'deciding_rows': int(len(D['y'])), 'players': int(len(set(D['key']))),
            'player_seasons': int(len(set(zip(D['key'], D['t'])))),
            'by_week': {int(w): int((D['week'] == w).sum()) for w in WEEKS},
            'by_position': pd.Series(D['pos']).value_counts().to_dict(),
            'pool_first_test_season': {int(w): FS[w]['pool_first_test_season'] for w in WEEKS},
            'week9_today_rmse_all_rows_reproduced': EXPECT_TEST_RMSE_TODAY}


def crash(a, runs, noise_runs=20):
    FS, fv = setup(a)
    res = {}; rng = np.random.default_rng(7)
    # noise: one shuffle of outcomes among player-seasons within (position, season), applied to every week alike
    ps = pd.DataFrame([(k, t) for (k, t) in fv], columns=['k', 't'])
    pos_of = {}
    for wk in WEEKS:
        Sw = FS[wk]['Sin']
        for k, t, p in zip(Sw.key.values, Sw.t.values, Sw.pos.values): pos_of.setdefault((k, int(t)), p)
    ps['p'] = [pos_of[(k, t)] for k, t in zip(ps.k, ps.t)]
    npass = 0
    for i in range(noise_runs):
        new = {}
        for _, g in ps.groupby(['p', 't']):
            src = list(zip(g.k, g.t)); perm = rng.permutation(len(src))
            for j, kt in enumerate(src): new[kt] = fv[src[perm[j]]]
        ym = {}
        for wk in WEEKS:
            Sw = FS[wk]['Sin']
            ym[wk] = np.array([np.nan_to_num(float(new.get((k, int(t)), 0.0))) if c else 0.0
                               for k, t, c in zip(Sw.key.values, Sw.t.values, Sw.complete.values)])
        D = stacked(FS, ym)
        npass += test(D['key'], D['only'], D['today'], D['y'], 1000)['pass']
    res['noise'] = {'runs': noise_runs, 'passed': int(npass), 'ok': npass <= 1}
    print('noise', res['noise'], flush=True)
    # planted: one true outcome per player-season = its rows' average of today + 0.75 x (rookies-only - today), plus a
    # real miss (outcome - its rows' average today) from another player-season at the same position
    D = stacked(FS)
    df = pd.DataFrame({'k': D['key'], 't': D['t'], 'pos': D['pos'], 'po': D['today'], 'pn': D['only'], 'y': D['y']})
    df['plant'] = df.po + 0.75 * (df.pn - df.po)
    G = df.groupby(['k', 't']).agg(pos=('pos', 'first'), plant=('plant', 'mean'), po=('po', 'mean'), y=('y', 'first')).reset_index()
    G['r'] = G.y - G.po
    gi = {kt: j for j, kt in enumerate(zip(G.k, G.t))}
    row_g = np.array([gi[kt] for kt in zip(df.k, df.t)])
    rng = np.random.default_rng(75); ok = 0; lifts = []
    for i in range(runs):
        e = G.r.values.copy()
        for p in C.POS:
            m = np.where(G.pos.values == p)[0]; e[m] = G.r.values[rng.permutation(m)]
        truth = np.maximum(0.0, G.plant.values + e)[row_g]
        r = test(D['key'], D['only'], D['today'], truth, 1000); ok += r['pass']; lifts.append(r['lift'])
    res['planted_0.75'] = {'runs': runs, 'passed': int(ok), 'share': ok / runs, 'ok': ok / runs >= 0.80,
                           'median_lift': float(np.median(lifts))}
    print('planted', res['planted_0.75'], flush=True)
    return res


def run(a):
    FS, fv = setup(a)
    D = stacked(FS)
    po, pn, pm, yd = D['today'], D['only'], D['mid'], D['y']
    r = test(D['key'], pn, po, yd, I.N_PERM)
    trades = {}
    for wk in WEEKS:                                            # all test rows of the week: rookies changed, others as today
        F = FS[wk]; S, rows, dec = F['Sin'], F['rows'], F['dec']
        y = np.nan_to_num(S.FV.values.astype(float))
        pt = pr(F['today'], rows, y); pnew = pt.copy(); ix = {int(x): j for j, x in enumerate(rows)}
        for x, v in zip(dec, pr(F['only'], dec, y)): pnew[ix[int(x)]] = v
        trades[wk] = I.trades(S, rows, pnew, pt, y[rows])
    nt = sum(trades[w]['n_trades'] for w in WEEKS)
    tdiff = sum(trades[w]['diff'] * trades[w]['n_trades'] for w in WEEKS) / nt
    r['trades_by_week'] = trades; r['trades_diff_pooled'] = float(tdiff)
    r['pass'] = bool(r['pass'] and tdiff >= TRADE_GUARD / 100)
    wk_, pos = D['week'], D['pos']
    lift = lambda a_, m: float(1 - rmse(a_[m], yd[m]) / rmse(po[m], yd[m]))
    res = {'prereg': 'docs/PREREG-ovs-rookies-match-rookies.md (A1: weeks 5, 9, 13, 17 pooled)', 'deciding_rows': int(len(yd)),
           'players': int(len(set(D['key']))), 'decides': r,
           'middle_rookies_plus_second_year': {'rmse': rmse(pm, yd), 'lift_vs_today': lift(pm, np.ones(len(yd), bool)),
                                               'produced_over_value': float(yd.sum() / pm.sum())},
           'by_week': {int(w): {'rows': int((wk_ == w).sum()), 'lift': lift(pn, wk_ == w), 'lift_middle': lift(pm, wk_ == w),
                                'produced_over_value_today': float(yd[wk_ == w].sum() / po[wk_ == w].sum()),
                                'produced_over_value_rookies_only': float(yd[wk_ == w].sum() / pn[wk_ == w].sum())} for w in WEEKS},
           'by_position': {q: {'rows': int((pos == q).sum()), 'lift': lift(pn, pos == q), 'lift_middle': lift(pm, pos == q)} for q in C.POS},
           'produced_over_value': {'today': float(yd.sum() / po.sum()), 'rookies_only': float(yd.sum() / pn.sum())}}
    res['decision'] = 'rookies match rookies' if r['pass'] else 'no change'
    return res


def main():
    ap = argparse.ArgumentParser()
    for k in ('nflverse', 'rosters', 'weekly', 'wrost', 'inj', 'sched', 'snaps'): ap.add_argument('--' + k, required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--counts', action='store_true'); g.add_argument('--crash', action='store_true'); g.add_argument('--run', action='store_true')
    ap.add_argument('--runs', type=int, default=200)
    a = ap.parse_args()
    if a.counts:
        res = counts(a); name = 'ovs_rookies_match_counts.json'
    elif a.crash:
        res = crash(a, a.runs); name = 'ovs_rookies_match_crash.json'
        print('crash tests:', 'PASS' if res['noise']['ok'] and res['planted_0.75']['ok'] else 'FAIL')
    else:
        res = run(a); name = 'ovs_rookies_match_results.json'
    json.dump(res, open(os.path.join(OUT, name), 'w'), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == '__main__':
    main()
