#!/usr/bin/env python3
"""
DELTA — OWN VALUE SCALE WITH EXPECTED POINTS FROM USAGE. Implements docs/PREREG-ovs-xfp.md; where they disagree, the
pre-registration (with its amendments) wins.

Starts from the adopted Own Value Scale (era-adjusted, this season counted: docs/PREREG-ovs-era.md,
docs/PREREG-ovs-in-season.md) and changes one thing: matching weighs half actual production and half EXPECTED
production (what his carries, targets and field position usually score; ffverse/ffopportunity, from nflverse
play-by-play), each 3/2/1 weighted and era-adjusted the same way. Production weight 3.0 -> 1.5 actual + 1.5 expected.

    python ovs_xfp.py --nflverse D --rosters D --weekly D --ep D --counts-only
    python ovs_xfp.py ... --crash [--runs 200]    # before lock
    python ovs_xfp.py ... --run                   # once, after lock
"""
import argparse, glob, json, math, os
import numpy as np
import pandas as pd
import comps_value_study as C
import comps_draft_drop as DD
import own_value_scale as V
import ovs_in_season as I

WEEKS = (9, 18)                 # 9 = in-season value, 18 = end of the regular season (the offseason value)
TEST = (2015, 2022)
FIRST_Y = 2008                  # expected points start in 2006; a row needs seasons Y-2..Y
W_SPLIT = (1.5, 1.5)            # actual, expected (was 3.0 actual)
LIFT_BAR = 0.02
ALPHA = 0.05 / 2
TRADE_GUARD = -1.0
N_PERM = 10_000
CRASH_WEEK = 9
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')


def load_ep(ep_dir, W):
    """Expected points per player-season (full and through each week), half PPR + TE premium, regular-season weeks
    he played (the weekly file's games)."""
    E = pd.concat([pd.read_csv(f, low_memory=False, usecols=['season', 'week', 'player_id', 'total_fantasy_points_exp',
                                                             'receptions_exp'])
                   for f in sorted(glob.glob(os.path.join(ep_dir, 'ep_weekly_*.csv')))])
    g = W[W.g == 1][['player_id', 'season', 'week', 'position']]
    E = E.merge(g, on=['player_id', 'season', 'week'], how='inner')           # regular season, a game played
    E['xP'] = E.total_fantasy_points_exp.fillna(0) - 0.5 * E.receptions_exp.fillna(0) \
        + np.where(E.position == 'TE', 0.5 * E.receptions_exp.fillna(0), 0.0)  # full PPR -> half PPR + TE premium
    cover = len(E) / len(g[g.season >= 2006])
    return E, cover


def xprod(Sin, E, W, week, L_full, L_upto, st):
    """Era-adjusted 3/2/1 expected production for the in-season rows (seasons Y so far, Y-1, Y-2), same games."""
    full = W.groupby(['player_id', 'season']).g.sum().to_dict()
    upto = W[W.week <= week].groupby(['player_id', 'season']).g.sum().to_dict()
    xf = E.groupby(['player_id', 'season']).xP.sum().to_dict()
    xu = E[E.week <= week].groupby(['player_id', 'season']).xP.sum().to_dict()
    spos = st.set_index(['player_id', 'season']).position.to_dict()
    out = []
    for k, Y, pos in zip(Sin.key.values, Sin.t.values, Sin.pos.values):
        ps = lambda yr: spos.get((k, yr), pos)
        num = den = 0.0
        for w, yr, cur in ((3, Y, True), (2, Y - 1, False), (1, Y - 2, False)):
            G_ = upto.get((k, yr), 0) if cur else full.get((k, yr), 0)
            if G_ < 1: continue
            x = (xu if cur else xf).get((k, yr))
            if x is None: num = np.nan; break
            lvl = L_upto[(yr, ps(yr), week)] if cur else L_full[(yr, ps(yr))]
            num += w * (x / G_) / lvl; den += w
        out.append(num / den if den and not np.isnan(num) else np.nan)
    return np.array(out)


def neighbours_xfp(S, rows, pool_max_t=None):
    """comps_draft_drop.neighbours, mode A, with one more veteran feature: production weight split actual/expected."""
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
                    feats = ['prod', 'age', 'draft', 'cy', 'games', 'xprod']
                    Wb = DD.vet_weights('A', S.loc[trow, 'G'].values.astype(float), S.cy.values[trow])
                    Wm = np.column_stack([Wb[:, 0] * W_SPLIT[0] / 3.0, Wb[:, 1:], Wb[:, 0] * W_SPLIT[1] / 3.0])
                    assert np.allclose(Wb[:, 0], C.W_V['prod'])
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
                    nn = prow[np.argsort(dd, kind='stable')[:min(30, n_avail)]]
                    out_rows.append(r); out_nn.append(nn)
    return {'test': np.array(out_rows, dtype=int), 'nn': {30: out_nn}}


def setup_week(a, week, extra=(), loader=None):
    C.HORIZON = I.HORIZON
    if loader: C.load = loader
    I.WEEKS = tuple(sorted(set(I.WEEKS) | set(WEEKS)))   # starter levels for weeks 9 and 18 too
    st, W, Sin, Sb, skipped = I.build(a.nflverse, a.rosters, a.weekly, week, extra=extra)
    E, cover = load_ep(a.ep, W)
    L_full, L_upto = I.levels(W)
    Sin = Sin.copy()
    Sin['xprod'] = np.where(Sin.kind.values == 'V', xprod(Sin, E, W, week, L_full, L_upto, st), np.nan)
    keep = (Sin.t >= FIRST_Y) & ((Sin.kind != 'V') | Sin.xprod.notna())
    dropped = int(((Sin.t >= FIRST_Y) & ~keep).sum())
    S = Sin[keep].reset_index(drop=True)
    C.POOL_LAG, C.SNAP_FIRST = I.LAG, FIRST_Y
    return st, S, {'week': week, 'ep_coverage_of_games': round(cover, 4), 'rows_dropped_no_ep': dropped, 'skipped': skipped}


def match_both(S, rows):
    pa = DD.neighbours(S, rows, 'A'); pb = neighbours_xfp(S, rows)
    out = []
    for p in (pa, pb):
        for r, nn in zip(p['test'], p['nn'][30]):
            assert (S.t.values[nn] <= S.t.values[r] - I.LAG).all(), 'pool leak'
            assert (S.t.values[nn] >= FIRST_Y).all() and S.complete.values[nn].all()
            assert S.key.values[r] not in set(S.key.values[nn]), 'self in pool'
        out.append({int(r): (nn, (lambda w: w / w.sum())(0.5 ** ((S.t.values[r] - S.t.values[nn]) / V.HALF_LIFE)))
                    for r, nn in zip(p['test'], p['nn'][30])})
    common = np.array(sorted(set(out[0]) & set(out[1])))
    return common, [out[0][r] for r in common], [out[1][r] for r in common]


def preds(M, y):
    return np.array([(w * y[nn]).sum() for nn, w in M])


def crash(a, runs, noise_runs=20):
    st, S, counts = setup_week(a, CRASH_WEEK)
    rows = S.index[(S.t >= TEST[0]) & (S.t <= TEST[1])].values
    rows, Mb, Mx = match_both(S, rows)
    y = np.nan_to_num(S.FV.values.astype(float))
    res = {'counts': counts | {'rows_scored': int(len(rows)), 'players': int(len(set(S.key.values[rows])))}}
    rng = np.random.default_rng(7)
    grp = pd.DataFrame({'p': S.pos.values, 't': S.t.values}).groupby(['p', 't']).groups
    npass = 0
    for i in range(noise_runs):
        yn = y.copy()
        for g in grp.values():
            g = np.array(list(g)); yn[g] = y[rng.permutation(g)]
        r = I.q(S, rows, preds(Mx, yn), preds(Mb, yn), yn[rows], n_perm=1000)
        npass += r['lift'] >= LIFT_BAR and r['p'] < ALPHA
    res['noise'] = {'runs': noise_runs, 'passed': int(npass), 'ok': npass <= 1}
    print('noise', res['noise'], flush=True)
    px, pb = preds(Mx, y), preds(Mb, y)
    resid = y[rows] - pb; pos = S.pos.values[rows]
    for w, n, key in ((0.75, runs, 'planted_0.75'), (0.6, max(20, runs // 4), 'planted_0.6')):
        rng = np.random.default_rng(int(w * 100)); ok = 0; lifts = []
        for i in range(n):
            e = resid.copy()
            for ps in C.POS:
                m = np.where(pos == ps)[0]; e[m] = resid[rng.permutation(m)]
            truth = np.maximum(0.0, pb + w * (px - pb) + e)
            r = I.q(S, rows, px, pb, truth, n_perm=1000); ok += r['lift'] >= LIFT_BAR and r['p'] < ALPHA; lifts.append(r['lift'])
        res[key] = {'runs': n, 'passed': int(ok), 'share': ok / n, 'median_lift': float(np.median(lifts))}
        if w == 0.75: res[key]['ok'] = ok / n >= 0.80
        print(key, res[key], flush=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    for k in ('nflverse', 'rosters', 'weekly', 'ep'): ap.add_argument('--' + k, required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--counts-only', action='store_true'); g.add_argument('--crash', action='store_true')
    g.add_argument('--run', action='store_true')
    ap.add_argument('--runs', type=int, default=200)
    a = ap.parse_args()
    if a.counts_only:
        st, S, counts = setup_week(a, CRASH_WEEK)
        rows = S.index[(S.t >= TEST[0]) & (S.t <= TEST[1])].values
        rows, Mb, Mx = match_both(S, rows)
        print(json.dumps(counts | {'rows_scored': int(len(rows)), 'players': int(len(set(S.key.values[rows])))}, indent=1, default=int))
        return
    if a.crash:
        res = crash(a, a.runs)
        json.dump(res, open(os.path.join(OUT, 'ovs_xfp_crash.json'), 'w'), indent=1, default=float)
        print('crash tests:', 'PASS' if res['noise']['ok'] and res['planted_0.75']['ok'] else 'FAIL'); return
    res = {'prereg': 'docs/PREREG-ovs-xfp.md', 'weeks': {}}
    for wk in WEEKS:
        st, S, counts = setup_week(a, wk)
        rows = S.index[(S.t >= TEST[0]) & (S.t <= TEST[1])].values
        rows, Mb, Mx = match_both(S, rows)
        y = np.nan_to_num(S.FV.values.astype(float)); yt = y[rows]
        px, pb = preds(Mx, y), preds(Mb, y)
        qq = I.q(S, rows, px, pb, yt); qq['pass'] = bool(qq['lift'] >= LIFT_BAR and qq['p'] < ALPHA)
        I.TEST = TEST
        tr = I.trades(S, rows, px, pb, yt)
        r = {'counts': counts | {'rows_scored': int(len(rows))}, 'Q': qq, 'trades': tr, 'by_position': {}}
        for ps in C.POS:
            m = S.pos.values[rows] == ps
            r['by_position'][ps] = {'rows': int(m.sum()), 'lift': float(1 - C.rmse(px[m], yt[m]) / C.rmse(pb[m], yt[m]))}
        r['pass'] = bool(qq['pass'] and tr['guard_ok'])
        res['weeks'][wk] = r
        print(wk, json.dumps({k: r[k] for k in ('Q', 'trades', 'by_position', 'pass')}, default=float), flush=True)
    res['decision'] = {'in_season (week 9 decides, weeks 5+)': res['weeks'][9]['pass'],
                       'offseason (week 18 decides)': res['weeks'][18]['pass']}
    json.dump(res, open(os.path.join(OUT, 'ovs_xfp_results.json'), 'w'), indent=1, default=float)
    print(res['decision'])


if __name__ == '__main__':
    main()
