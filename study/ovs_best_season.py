#!/usr/bin/env python3
"""
DELTA — OWN VALUE SCALE: BEST SEASON IN MATCHING. Implements docs/PREREG-ovs-best-season.md; where they disagree, the
pre-registration wins.

Week 9, adopted in-season value (ovs_qb_starts.build_S, no games number). Adds one veteran matching feature:
  peak = max(his production number, his best earlier full season)
a season = points per game / that season's starter level at his position (the era rule), seasons with 8+ games
(if none, any season with a game). Weight picked from {1.0, 1.5, 3.0} on t = 2006-2012; tested on 2013-2022.

    python ovs_best_season.py --nflverse D --rosters D --weekly D --wrost D --inj D --sched FILE --snaps D --counts
    python ovs_best_season.py ... --crash [--runs 200]      # before lock
    python ovs_best_season.py ... --run                     # once, after lock
"""
import argparse, json, os, pickle
import numpy as np
import pandas as pd
import comps_value_study as C
import comps_draft_drop as DD
import own_value_scale as V
import ovs_in_season as I
import ovs_qb_starts as QS

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
WEEK = 9
FIT = (2006, 2012)
TEST = (2013, 2022)
GRID = (1.0, 1.5, 3.0)
PLANT_W = 1.5
MIN_GAMES = 8
LIFT_BAR, ALPHA, TRADE_GUARD = 0.02, 0.05, -1.0
CACHE = '/tmp/ovs_best_season_frame.pkl'
EXPECT_TEST_RMSE_TODAY = 48.461133390000334     # ovs_qb_starts.py all_rows.rmse_rule on this data folder (12 Nov)


def peaks(S, W, st, L_full):
    """Best earlier full season (era-adjusted points per game) for every row; NaN if he has none."""
    full = W.groupby(['player_id', 'season']).agg(P=('P', 'sum'), G=('g', 'sum')).reset_index()
    spos = st.set_index(['player_id', 'season']).position.to_dict()
    full['pos'] = [spos.get((k, int(y))) for k, y in zip(full.player_id, full.season)]
    full = full[full.pos.notna() & (full.G >= 1)].copy()
    full['rel'] = [(p / g) / L_full[(int(y), ps)] if (int(y), ps) in L_full else np.nan
                   for p, g, y, ps in zip(full.P, full.G, full.season, full.pos)]
    full = full[full.rel.notna()]
    by = {k: (g.season.values, g.G.values, g.rel.values) for k, g in full.groupby('player_id')}
    out = np.full(len(S), np.nan)
    for i, (k, t) in enumerate(zip(S.key.values, S.t.values)):
        if k not in by: continue
        yr, G, rel = by[k]; m = yr < t
        if not m.any(): continue
        m8 = m & (G >= MIN_GAMES)
        out[i] = rel[m8].max() if m8.any() else rel[m].max()
    return out


def neighbours_peak(S, rows, w_peak):
    """comps_draft_drop.neighbours, mode A, with 'peak' added to veteran matching at weight w_peak."""
    keys = S.key.values; tt = S.t.values; pos = S.pos.values; kind = S.kind.values
    out_rows, out_nn = [], []
    for t in sorted(set(tt[rows])):
        pmax = t - C.POOL_LAG
        pool_all = S.index[(S.t >= C.SNAP_FIRST) & (S.t <= pmax)].values
        rows_t = rows[tt[rows] == t]
        for p in C.POS:
            for kd in ('V', 'R0'):
                trow = rows_t[(pos[rows_t] == p) & (kind[rows_t] == kd)]
                if not len(trow): continue
                prow = pool_all[(pos[pool_all] == p) & (kind[pool_all] == kd)]
                if kd == 'V':
                    feats = ['prod', 'age', 'draft', 'cy', 'games', 'peak']
                    Wb = DD.vet_weights('A', S.loc[trow, 'G'].values.astype(float), S.cy.values[trow])
                    Wm = np.column_stack([Wb, np.full(len(trow), w_peak)])
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


def recency(S, ti, nn):
    out = {}
    for r, n in zip(ti, nn):
        assert (S.t.values[n] <= S.t.values[r] - I.LAG).all() and S.key.values[r] not in set(S.key.values[n])
        assert S.complete.values[n].all()
        w = 0.5 ** ((S.t.values[r] - S.t.values[n]) / V.HALF_LIFE); out[int(r)] = (n, w / w.sum())
    return out


def frame(a):
    if os.path.exists(CACHE):
        return pickle.load(open(CACHE, 'rb'))
    C.HORIZON = I.HORIZON
    st, W, Sin, Sb, skipped = I.build(a.nflverse, a.rosters, a.weekly, WEEK)
    L_full, L_upto = I.levels(W)
    players = os.path.join(a.nflverse, 'players.csv')
    SS, none, parts = QS.build_S(Sin, W, st, L_full, L_upto, a, a.sched, a.snaps, players)
    C.W_V['games'] = 0.0; C.POOL_LAG, C.SNAP_FIRST = I.LAG, I.FIRST_Y
    best_before = peaks(SS, W, st, L_full)
    v = SS.kind.values == 'V'
    SS['peak'] = np.where(v, np.fmax(SS['prod'].values, best_before), np.nan)   # no earlier season: his production
    assert not np.isnan(SS.peak.values[v]).any()
    rows = Sin.index[(Sin.t >= FIT[0]) & (Sin.t <= TEST[1])].values
    assert Sin.complete.values[rows].all()
    xr = rows[none[rows]]; vr = rows[~none[rows]]
    # equivalence: weight 0 reproduces today's matches exactly
    ti, nn, _ = I.match(SS, vr); today = {int(r): n for r, n in zip(ti, nn)}
    z = neighbours_peak(SS, vr, 0.0)
    assert set(int(r) for r in z['test']) == set(today) and all(np.array_equal(today[int(r)], n) for r, n in zip(z['test'], z['nn'][30])), 'weight 0 does not reproduce today'
    nn_today = recency(SS, z['test'], z['nn'][30])
    assert (Sb.kind.values[xr] == 'R0').all()
    tb, nb, _ = I.match(Sb, xr); x_today = recency(Sb, tb, nb)          # first-year QB, no game: unchanged by the rule
    nn_today.update(x_today)
    by_w = {}
    for wp in GRID:
        g = neighbours_peak(SS, vr, wp); d = recency(SS, g['test'], g['nn'][30]); d.update(x_today); by_w[wp] = d
        assert set(d) == set(int(r) for r in rows)
    F = {'Sin': Sin, 'rows': rows, 'none': none, 'today': nn_today, 'by_w': by_w,
         'peak': SS.peak.values, 'best_before': best_before, 'prod': SS['prod'].values, 'parts': parts}
    pickle.dump(F, open(CACHE, 'wb'))
    return F


def pr(D, rows, y):
    return I.preds([D[int(r)][0] for r in rows], [D[int(r)][1] for r in rows], y)


def rmse(p, y):
    return float(np.sqrt(np.mean((p - y) ** 2)))


def setup(a):
    F = frame(a)
    S, rows = F['Sin'], F['rows']
    y = np.nan_to_num(S.FV.values.astype(float))
    t = S.t.values[rows]
    fit = (t >= FIT[0]) & (t <= FIT[1]); test = (t >= TEST[0]) & (t <= TEST[1])
    pt = pr(F['today'], rows, y)
    assert abs(rmse(pt[test], y[rows][test]) - EXPECT_TEST_RMSE_TODAY) < 1e-6, ('today not reproduced', rmse(pt[test], y[rows][test]))
    return F, S, rows, y, fit, test


def decide(F, S, rows, y, fit, test, n_perm, with_trades):
    pt = pr(F['today'], rows, y); yr = y[rows]
    pw = {w: pr(F['by_w'][w], rows, y) for w in GRID}
    fit_sc = {w: rmse(pw[w][fit], yr[fit]) for w in GRID}
    wbest = min(fit_sc, key=fit_sc.get); pn = pw[wbest]
    lift, p = C.perm_test(yr[test], pn[test], pt[test], S.key.values[rows][test], n_perm)
    r = {'weight': wbest, 'fit_rmse_by_weight': fit_sc, 'fit_rmse_today': rmse(pt[fit], yr[fit]),
         'rmse_new': rmse(pn[test], yr[test]), 'rmse_today': rmse(pt[test], yr[test]), 'lift': float(lift), 'p': float(p)}
    ok = lift >= LIFT_BAR and p < ALPHA
    if with_trades:
        tr = I.trades(S, rows[test], pn[test], pt[test], yr[test]); r['trades'] = tr
        ok = ok and tr['diff'] >= TRADE_GUARD / 100
    r['pass'] = bool(ok)
    return r, pn, pt, pw


def counts(a):
    F, S, rows, y, fit, test = setup(a)
    v = S.kind.values[rows] == 'V'; bb = F['best_before'][rows]; pk = F['peak'][rows]; pd_ = F['prod'][rows]
    changed = {w: int(sum(not np.array_equal(F['by_w'][w][int(r)][0], F['today'][int(r)][0]) for r in rows[test])) for w in GRID}
    return {'rows_fit': int(fit.sum()), 'rows_test': int(test.sum()),
            'valued_rows_with_no_earlier_season': int((v & np.isnan(bb)).sum()),
            'valued_rows_where_peak_is_this_production': int((v & (pk == pd_)).sum()),
            'peak_quantiles_valued_rows': {q: float(np.nanquantile(pk[v], q)) for q in (0.1, 0.5, 0.9, 0.99)},
            'test_rows_whose_matches_change_by_weight': changed, 'data': F['parts']}


def crash(a, runs, noise_runs=20):
    F, S, rows, y, fit, test = setup(a)
    res = {}; rng = np.random.default_rng(7)
    grp = pd.DataFrame({'p': S.pos.values, 't': S.t.values}).groupby(['p', 't']).groups
    npass = 0; ws = []
    for i in range(noise_runs):
        yn = y.copy()
        for g in grp.values():
            g = np.array(list(g)); yn[g] = y[rng.permutation(g)]
        r, *_ = decide(F, S, rows, yn, fit, test, 1000, False); npass += r['pass']; ws.append(r['weight'])
    res['noise'] = {'runs': noise_runs, 'passed': int(npass), 'ok': npass <= 1, 'weight_picked': ws}
    print('noise', res['noise'], flush=True)
    pt = pr(F['today'], rows, y); pp = pr(F['by_w'][PLANT_W], rows, y); yr = y[rows]
    truth0 = pt + 0.75 * (pp - pt); resid = yr - pt; pos = S.pos.values[rows]
    rng = np.random.default_rng(75); ok = 0; lifts = []; ws = []
    for i in range(runs):
        e = resid.copy()
        for ps in C.POS:
            m = np.where(pos == ps)[0]; e[m] = resid[rng.permutation(m)]
        truth = np.maximum(0.0, truth0 + e)
        # the planted world replaces the test rows' outcomes only; pool outcomes stay real (as the in-season crash)
        pt_, pw_ = pt, {w: pr(F['by_w'][w], rows, y) for w in GRID}
        fit_sc = {w: rmse(pw_[w][fit], truth[fit]) for w in GRID}; wb = min(fit_sc, key=fit_sc.get)
        lift, p = C.perm_test(truth[test], pw_[wb][test], pt_[test], S.key.values[rows][test], 1000)
        ok += (lift >= LIFT_BAR and p < ALPHA); lifts.append(float(lift)); ws.append(wb)
    res['planted_0.75_at_1.5'] = {'runs': runs, 'passed': int(ok), 'share': ok / runs, 'ok': ok / runs >= 0.80,
                                  'median_lift': float(np.median(lifts)), 'weight_picked': {str(w): ws.count(w) for w in GRID}}
    print('planted', res['planted_0.75_at_1.5'], flush=True)
    return res


def run(a):
    F, S, rows, y, fit, test = setup(a)
    r, pn, pt, pw = decide(F, S, rows, y, fit, test, I.N_PERM, True)
    yr = y[rows]; pos = S.pos.values[rows]
    res = {'prereg': 'docs/PREREG-ovs-best-season.md', 'week': WEEK, 'decides': r,
           'every_weight_on_test': {str(w): {'rmse': rmse(pw[w][test], yr[test]), 'lift': float(1 - rmse(pw[w][test], yr[test]) / rmse(pt[test], yr[test]))} for w in GRID},
           'by_position': {q: {'rows': int((test & (pos == q)).sum()), 'lift': float(1 - rmse(pn[test & (pos == q)], yr[test & (pos == q)]) / rmse(pt[test & (pos == q)], yr[test & (pos == q)]))} for q in C.POS}}
    vet = ~S.rookie_Y.values[rows].astype(bool) & (S.kind.values[rows] == 'V')
    pk, pdn = F['peak'][rows], F['prod'][rows]
    drop = 1 - pdn / pk
    groups = {'all_veterans': vet, 'former_stars_now_20pct_off': vet & (pk >= 1.1) & (drop >= 0.2),
              'former_star_wrs_now_20pct_off': vet & (pk >= 1.1) & (drop >= 0.2) & (pos == 'WR'),
              'stars_near_their_best': vet & (pk >= 1.1) & (drop < 0.2)}
    res['groups_produced_over_value'] = {g: {'rows': int((m & test).sum()), 'today': float(yr[m & test].sum() / pt[m & test].sum()),
                                             'new': float(yr[m & test].sum() / pn[m & test].sum()),
                                             'lift': float(1 - rmse(pn[m & test], yr[m & test]) / rmse(pt[m & test], yr[m & test]))} for g, m in groups.items()}
    res['decision'] = f'add best season at weight {r["weight"]}' if r['pass'] else 'no change'
    return res


def main():
    ap = argparse.ArgumentParser()
    for k in ('nflverse', 'rosters', 'weekly', 'wrost', 'inj', 'sched', 'snaps'): ap.add_argument('--' + k, required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--counts', action='store_true'); g.add_argument('--crash', action='store_true'); g.add_argument('--run', action='store_true')
    ap.add_argument('--runs', type=int, default=200)
    a = ap.parse_args()
    if a.counts:
        res = counts(a); name = 'ovs_best_season_counts.json'
    elif a.crash:
        res = crash(a, a.runs); name = 'ovs_best_season_crash.json'
        print('crash tests:', 'PASS' if res['noise']['ok'] and res['planted_0.75_at_1.5']['ok'] else 'FAIL')
    else:
        res = run(a); name = 'ovs_best_season_results.json'
    json.dump(res, open(os.path.join(OUT, name), 'w'), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == '__main__':
    main()
