#!/usr/bin/env python3
"""
DELTA — OWN VALUE SCALE WITH THIS SEASON'S GAMES. Implements docs/PREREG-ovs-in-season.md; where they disagree, the
pre-registration (with its amendments) wins.

A player at the end of week W of season Y, two ways on identical rows (comps_in_season.snapshots, unchanged):
  in-season  this season so far is the newest season in the 3/2/1 production; games = games so far
  baseline   this season ignored (what the value does mid-season today)
Production is era-adjusted in both (docs/PREREG-ovs-era.md, passed 8 Nov): each season's points per game / that
season's starter level at his position; for season Y, the starter level through week W.
Outcome FV3 over Y+1..Y+3 (12-team superflex lines, the season file). Pool: same week W, seasons <= Y-4, from 2002.

    python ovs_in_season.py --nflverse D --rosters D --weekly D --counts-only
    python ovs_in_season.py --nflverse D --rosters D --weekly D --crash [--runs 200]   # before lock
    python ovs_in_season.py --nflverse D --rosters D --weekly D --run                  # once, after lock
"""
import argparse, json, math, os, time
import numpy as np
import pandas as pd
import comps_value_study as C
import comps_draft_drop as DD
import comps_in_season as CI
import own_value_scale as V

WEEKS = (5, 9, 13)
TEST = (2013, 2022)
LAG = 4                        # week W of Y: a pool season's Y'+1..Y'+3 must be finished by Y-1
FIRST_Y = 2002
HORIZON = 3
LIFT_BAR = 0.02
ALPHA = 0.05 / 3               # three weeks decide
TRADE_GUARD = -1.0
N_PERM = 10_000
CRASH_WEEK = 9
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')


# ── era levels from the weekly file (one source for every feature) ───────────────────────────────
def levels(W):
    """(season, pos) full-season and (season, pos, week) through-week starter levels: average points per game of the
    top 24 QB/RB/WR or 12 TE, among players with 8+ games (full) or at least half the weeks so far (through week W)."""
    full = W.groupby(['player_id', 'season', 'position']).agg(P=('P', 'sum'), G=('g', 'sum')).reset_index()
    def top(g, need):
        g = g[g.G >= need]; return float((g.P / g.G).nlargest(C.STARTER_N[g.position.iat[0]]).mean())
    L_full = {(int(y), p): top(g, 8) for (y, p), g in full.groupby(['season', 'position'])}
    L_upto = {}
    for wk in WEEKS + (CRASH_WEEK,):
        u = W[W.week <= wk].groupby(['player_id', 'season', 'position']).agg(P=('P', 'sum'), G=('g', 'sum')).reset_index()
        for (y, p), g in u.groupby(['season', 'position']):
            L_upto[(int(y), p, wk)] = top(g, math.ceil(wk / 2))
    return L_full, L_upto


def era_adjust(Sin, Sb, W, week, L_full, L_upto, st):
    """Replace both versions' production with the era-adjusted 3/2/1 (same seasons and games as the raw feature)."""
    full = W.groupby(['player_id', 'season']).agg(P=('P', 'sum'), G=('g', 'sum'))
    upto = W[W.week <= week].groupby(['player_id', 'season']).agg(P=('P', 'sum'), G=('g', 'sum'))
    FP, FG, UP, UG = full.P.to_dict(), full.G.to_dict(), upto.P.to_dict(), upto.G.to_dict()
    spos = st.set_index(['player_id', 'season']).position.to_dict()
    def term(pid, yr, P_, G_, row_pos, lvl):
        return (P_ / G_) / lvl if G_ >= 1 else None
    def ppg(terms):
        num = den = 0.0
        for w, v in terms:
            if v is not None: num += w * v; den += w
        return num / den if den else np.nan
    pin, pb = [], []
    for k, Y, pos, kin, kb in zip(Sin.key.values, Sin.t.values, Sin.pos.values, Sin.kind.values, Sb.kind.values):
        ps = lambda yr: spos.get((k, yr), pos)
        def full_term(yr):
            G_ = FG.get((k, yr), 0)
            return term(k, yr, FP.get((k, yr), 0.0), G_, pos, L_full[(yr, ps(yr))]) if G_ >= 1 else None
        b = ppg([(3, full_term(Y - 1)), (2, full_term(Y - 2)), (1, full_term(Y - 3))])
        gY = UG.get((k, Y), 0)
        if gY >= 1:
            cur = (UP[(k, Y)] / gY) / L_upto[(Y, ps(Y), week)]
            i = ppg([(3, cur), (2, full_term(Y - 1)), (1, full_term(Y - 2))])
        else:
            i = b
        pin.append(i); pb.append(b)
    Sin = Sin.copy(); Sb = Sb.copy()
    Sin['prod'] = np.where(Sin.kind.values == 'V', pin, np.nan)
    Sb['prod'] = np.where(Sb.kind.values == 'V', pb, np.nan)
    assert (np.isnan(Sin['prod'].values) == np.isnan(Sin['prod'].where(Sin.kind == 'V').values)).all()
    return Sin, Sb


def outcomes(S, st, last=2025):
    """FV3 over t+1..t+3 from the season file, on the row's position line (as C.build)."""
    pts = {(r.player_id, int(r.season)): float(r.P) for r in st.itertuples()}
    repl = {}
    for (yr, ps), g in st.groupby(['season', 'position']):
        p = np.sort(g.P.values)[::-1]; repl[(int(yr), ps)] = p[C.REPL_N[ps] - 1] if len(p) >= C.REPL_N[ps] else 0.0
    fv, comp = [], []
    for k, t, ps in zip(S.key.values, S.t.values, S.pos.values):
        if t + HORIZON > last: fv.append(np.nan); comp.append(False); continue
        fv.append(sum(C.DISCOUNT ** (j - 1) * max(0.0, pts.get((k, t + j), 0.0) - repl[(t + j, ps)]) for j in range(1, HORIZON + 1)))
        comp.append(True)
    S = S.copy(); S['FV'] = fv; S['complete'] = comp
    return S


def build(nflverse, rosters, weekly, week, extra=()):
    st, dp, pl, W = CI.load(nflverse, rosters, weekly)
    seasons = list(range(FIRST_Y, TEST[1] + 1)) + list(extra)
    Sin, Sb, skipped = CI.snapshots(st, dp, pl, W, week, seasons)
    L_full, L_upto = levels(W)
    Sin, Sb = era_adjust(Sin, Sb, W, week, L_full, L_upto, st)
    Sin, Sb = outcomes(Sin, st), outcomes(Sb, st)
    return st, W, Sin, Sb, skipped


def match(S, rows):
    C.POOL_LAG, C.SNAP_FIRST = LAG, FIRST_Y
    pa = DD.neighbours(S, rows, 'A', pool_max_t=None)
    Wt = []
    for r, nn in zip(pa['test'], pa['nn'][30]):
        assert (S.t.values[nn] <= S.t.values[r] - LAG).all(), 'pool leak'
        assert S.key.values[r] not in set(S.key.values[nn]), 'self in pool'
        assert S.complete.values[nn].all(), 'a match without a finished window'
        w = 0.5 ** ((S.t.values[r] - S.t.values[nn]) / V.HALF_LIFE); Wt.append(w / w.sum())
    return pa['test'], pa['nn'][30], Wt


def preds(nn, Wt, y):
    return np.array([(w * y[n]).sum() for n, w in zip(nn, Wt)])


def setup_week(nflverse, rosters, weekly, week):
    st, W, Sin, Sb, skipped = build(nflverse, rosters, weekly, week)
    rows = Sin.index[(Sin.t >= TEST[0]) & (Sin.t <= TEST[1])].values
    ti, nni, wi = match(Sin, rows)
    tb, nnb, wb = match(Sb, rows)
    common = np.intersect1d(ti, tb)
    # neighbours() returns rows grouped by position and kind, not in input order: pair through a lookup (handoff note)
    pos_i = {int(r): j for j, r in enumerate(ti)}; pos_b = {int(r): j for j, r in enumerate(tb)}
    ii = np.array([pos_i[int(r)] for r in common]); ib = np.array([pos_b[int(r)] for r in common])
    assert np.array_equal(ti[ii], common) and np.array_equal(tb[ib], common)
    assert np.array_equal(Sin.key.values[common], Sb.key.values[common])
    nni = [nni[i] for i in ii]; wi = [wi[i] for i in ii]; nnb = [nnb[i] for i in ib]; wb = [wb[i] for i in ib]
    counts = {'week': week, 'rows_scored': int(len(common)), 'players': int(len(set(Sin.key.values[common]))),
              'rookies_this_season': int(Sin.rookie_Y.values[common].sum()), 'skipped': skipped}
    return st, Sin, Sb, common, nni, wi, nnb, wb, counts


def q(S, rows, p_new, p_old, yt, n_perm=N_PERM):
    cl = S.key.values[rows]
    lift, p = C.perm_test(yt, p_new, p_old, cl, n_perm)
    return {'rmse_in_season': C.rmse(p_new, yt), 'rmse_baseline': C.rmse(p_old, yt), 'lift': float(lift), 'p': float(p),
            'pass': bool(lift >= LIFT_BAR and p < ALPHA)}


def trades(S, rows, p_new, p_old, yt):
    V.TEST = TEST
    pre = {'test': rows}
    A, B, K = V.build_trades(S, pre, p_new, p_old)
    r = V.q2(S, pre, p_new, p_old, yt, A, B, K, n_perm=N_PERM, seed=13)
    return {'n_trades': r['n_trades'], 'acc_in_season': r['acc_ovs'], 'acc_baseline': r['acc_b2'], 'diff': r['diff'],
            'p': r['p'], 'guard_ok': bool(r['diff'] >= TRADE_GUARD / 100)}


def crash(nflverse, rosters, weekly, runs, noise_runs=20):
    st, Sin, Sb, rows, nni, wi, nnb, wb, counts = setup_week(nflverse, rosters, weekly, CRASH_WEEK)
    y = Sin.FV.values.astype(float); assert np.allclose(np.nan_to_num(y), np.nan_to_num(Sb.FV.values.astype(float)))
    yz = np.nan_to_num(y)
    res = {'counts': counts}; rng = np.random.default_rng(7)
    grp = pd.DataFrame({'p': Sin.pos.values, 't': Sin.t.values}).groupby(['p', 't']).groups
    npass = 0
    for i in range(noise_runs):
        yn = yz.copy()
        for g in grp.values():
            g = np.array(list(g)); yn[g] = yz[rng.permutation(g)]
        npass += q(Sin, rows, preds(nni, wi, yn), preds(nnb, wb, yn), yn[rows], n_perm=1000)['pass']
    res['noise'] = {'runs': noise_runs, 'passed': int(npass), 'ok': npass <= 1}
    print('noise', res['noise'], flush=True)
    pi_, pb_ = preds(nni, wi, yz), preds(nnb, wb, yz)
    resid = yz[rows] - pb_; pos = Sin.pos.values[rows]
    for w, n, key in ((0.75, runs, 'planted_0.75'), (0.6, max(20, runs // 4), 'planted_0.6')):
        rng = np.random.default_rng(int(w * 100)); ok = 0; lifts = []
        for i in range(n):
            e = resid.copy()
            for ps in C.POS:
                m = np.where(pos == ps)[0]; e[m] = resid[rng.permutation(m)]
            truth = np.maximum(0.0, pb_ + w * (pi_ - pb_) + e)
            r = q(Sin, rows, pi_, pb_, truth, n_perm=1000); ok += r['pass']; lifts.append(r['lift'])
        res[key] = {'runs': n, 'passed': int(ok), 'share': ok / n, 'median_lift': float(np.median(lifts))}
        if w == 0.75: res[key]['ok'] = ok / n >= 0.80
        print(key, res[key], flush=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nflverse', required=True); ap.add_argument('--rosters', required=True); ap.add_argument('--weekly', required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--counts-only', action='store_true'); g.add_argument('--crash', action='store_true')
    g.add_argument('--run', action='store_true')
    ap.add_argument('--runs', type=int, default=200)
    a = ap.parse_args()
    C.HORIZON = HORIZON
    if a.counts_only:
        print(json.dumps(setup_week(a.nflverse, a.rosters, a.weekly, CRASH_WEEK)[-1], indent=1, default=int)); return
    if a.crash:
        res = crash(a.nflverse, a.rosters, a.weekly, a.runs)
        json.dump(res, open(os.path.join(OUT, 'ovs_in_season_crash.json'), 'w'), indent=1, default=float)
        print('crash tests:', 'PASS' if res['noise']['ok'] and res['planted_0.75']['ok'] else 'FAIL'); return
    res = {'prereg': 'docs/PREREG-ovs-in-season.md', 'weeks': {}}
    for wk in WEEKS:
        st, Sin, Sb, rows, nni, wi, nnb, wb, counts = setup_week(a.nflverse, a.rosters, a.weekly, wk)
        y = np.nan_to_num(Sin.FV.values.astype(float)); yt = y[rows]
        pi_, pb_ = preds(nni, wi, y), preds(nnb, wb, y)
        r = {'counts': counts, 'Q': q(Sin, rows, pi_, pb_, yt), 'trades': trades(Sin, rows, pi_, pb_, yt), 'by_position': {}}
        for ps in C.POS:
            m = Sin.pos.values[rows] == ps
            r['by_position'][ps] = {'rows': int(m.sum()), 'lift': float(1 - C.rmse(pi_[m], yt[m]) / C.rmse(pb_[m], yt[m]))}
        rk = Sin.rookie_Y.values[rows].astype(bool)
        r['rookies_this_season'] = {'rows': int(rk.sum()), 'lift': float(1 - C.rmse(pi_[rk], yt[rk]) / C.rmse(pb_[rk], yt[rk]))}
        r['pass'] = bool(r['Q']['pass'] and r['trades']['guard_ok'])
        res['weeks'][wk] = r
        print(wk, json.dumps({k: r[k] for k in ('Q', 'trades', 'pass')}, default=float), flush=True)
    passed = [wk for wk in WEEKS if res['weeks'][wk]['pass']]
    res['decision'] = f'count this season from week {passed[0]}' if passed else 'stay on full seasons'
    json.dump(res, open(os.path.join(OUT, 'ovs_in_season_results.json'), 'w'), indent=1, default=float)
    print(res['decision'])


if __name__ == '__main__':
    main()
