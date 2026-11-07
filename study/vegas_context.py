#!/usr/bin/env python3
"""
DELTA — VEGAS TEAM CONTEXT IN THE OWN VALUE SCALE. Implements docs/PREREG-vegas-team-context.md; where they
disagree, the pre-registration (with its amendments) wins.

Candidate = OVS x (team implied-points ratio) ** beta, beta fitted per position on earlier seasons only.
Baseline  = OVS exactly as locked (own_value_scale.py, 63c80df).
Q1: RMSE on FV5, lift >= 2%, p < 0.025.  Q2: trade calls, +2.0 points, p < 0.025.
Lines: nflverse/nfldata games.csv (closing spread and total). Credit nflverse. No market data of any kind.

    python vegas_context.py --nflverse D --rosters D --games F --weekly D --wrosters D --crash
    python vegas_context.py --nflverse D --rosters D --games F --weekly D --wrosters D --run
"""
import argparse, glob, json, os
import numpy as np
import pandas as pd
import comps_value_study as C
import comps_draft_drop as DD
import own_value_scale as V

FIT_FROM = 2006                     # first season with an OVS prediction (pool 2001 .. t-5)
BETAS = np.round(np.arange(0, 3.0001, 0.01), 2)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
DRAFT_CODE = {'GNB': 'GB', 'KAN': 'KC', 'LAR': 'LA', 'LVR': 'LV', 'NOR': 'NO', 'NWE': 'NE', 'SDG': 'LAC',
              'SFO': 'SF', 'TAM': 'TB'}


def code_in(team, season):
    """A franchise's code in a given season of the games file (relocations)."""
    t = DRAFT_CODE.get(team, team)
    if t in ('LV', 'OAK'): return 'OAK' if season < 2020 else 'LV'
    if t in ('LAC', 'SD'): return 'SD' if season < 2017 else 'LAC'
    if t in ('LA', 'STL'): return 'STL' if season < 2016 else 'LA'
    return t


# ── the lines ────────────────────────────────────────────────────────────────────────────────────
def implied(games_csv):
    g = pd.read_csv(games_csv)
    g = g[(g.game_type == 'REG') & g.spread_line.notna() & g.total_line.notna()]
    h = pd.DataFrame({'season': g.season, 'week': g.week, 'team': g.home_team,
                      'pts': g.total_line / 2 + g.spread_line / 2})
    a = pd.DataFrame({'season': g.season, 'week': g.week, 'team': g.away_team,
                      'pts': g.total_line / 2 - g.spread_line / 2})
    return pd.concat([h, a], ignore_index=True)


def ratios(S, imp, weekly_dir, wros_dir, dp):
    """Version A (season t, his season-t team) and Version B (week 1 of t+1, his week-1 team). 1.0 if unknown."""
    seas = imp.groupby(['season', 'team']).pts.mean()
    lg = seas.groupby('season').mean()
    rA_team = (seas / lg.reindex(seas.index.get_level_values(0)).values).to_dict()
    w1 = imp[imp.week == 1]
    w1_lg = w1.groupby('season').pts.mean()
    rB_team = {(r.season, r.team): r.pts / w1_lg[r.season] for r in w1.itertuples()}

    cols = ['player_id', 'season', 'week', 'season_type', 'team', 'attempts', 'carries', 'targets', 'receptions']
    W = pd.concat([pd.read_csv(f, usecols=cols, low_memory=False)
                   for f in sorted(glob.glob(os.path.join(weekly_dir, 'stats_player_week_*.csv')))])
    W = W[(W.season_type == 'REG') & (W[['attempts', 'carries', 'targets', 'receptions']].fillna(0).sum(axis=1) > 0)]
    cnt = W[W.team.notna()].groupby(['player_id', 'season', 'team']).size().reset_index(name='n')
    cnt = cnt.sort_values(['player_id', 'season', 'n', 'team'], ascending=[True, True, False, True])
    main_team = cnt.drop_duplicates(['player_id', 'season']).set_index(['player_id', 'season']).team.to_dict()
    dq = dp[dp.gsis_id.notna()].sort_values(['season', 'pick']).drop_duplicates('gsis_id')
    dteam = {r.gsis_id: (int(r.season), r.team) for r in dq.itertuples()}
    wk1 = {}
    for f in sorted(glob.glob(os.path.join(wros_dir, 'rw_*.csv'))):
        d = pd.read_csv(f, usecols=['season', 'week', 'game_type', 'team', 'gsis_id'], low_memory=False)
        d = d[(d.week == 1) & (d.game_type == 'REG') & d.gsis_id.notna()]
        for r in d.itertuples(): wk1[(r.gsis_id, int(r.season))] = r.team

    rA, rB, tA, tB, miss = [], [], [], [], {'A': 0, 'B': 0}
    for r in S.itertuples():
        t = int(r.t)
        if r.kind == 'R0':
            ds = dteam.get(r.key)
            team = code_in(ds[1], t) if ds else None
        else:
            team = main_team.get((r.key, t))
        a = rA_team.get((t, team)) if team else None
        if a is None: miss['A'] += 1; a = 1.0
        nt = wk1.get((r.key, t + 1))
        nt = code_in(nt, t + 1) if nt else None
        b = rB_team.get((t + 1, nt)) if nt else None
        if b is None: miss['B'] += 1; b = 1.0
        rA.append(a); rB.append(b); tA.append(team); tB.append(nt)
    return np.array(rA), np.array(rB), np.array(tA, dtype=object), np.array(tB, dtype=object), miss


# ── OVS for every row from 2006 (fit rows and test rows) ───────────────────────────────────────
def ovs_all(S, y):
    rows = S.index[(S.t >= FIT_FROM) & (S.t <= V.TEST[1])].values
    pa = DD.neighbours(S, rows, 'A')
    out = {}
    for r, nn in zip(pa['test'], pa['nn'][30]):
        assert (S.t.values[nn] <= S.t.values[r] - 5).all() and S.key.values[r] not in set(S.key.values[nn])
        w = 0.5 ** ((S.t.values[r] - S.t.values[nn]) / V.HALF_LIFE); w = w / w.sum()
        out[int(r)] = (nn, w)
    return out


def fv1(S, st):
    repl = {}
    for (yr, pos), g in st.groupby(['season', 'position']):
        p = np.sort(g.P.values)[::-1]
        repl[(yr, pos)] = p[C.REPL_N[pos] - 1] if len(p) >= C.REPL_N[pos] else 0.0
    pts = {(r.player_id, r.season): r.P for r in st.itertuples()}
    return np.array([max(0.0, pts.get((k, int(t) + 1), 0.0) - repl.get((int(t) + 1, p), 0.0)) if k else 0.0
                     for k, t, p in zip(S.key.values, S.t.values, S.pos.values)])


def fit_betas(S, rows_fit, pred, y, ratio):
    """beta per (test season, position) on rows from FIT_FROM .. t-5 only; least squares in value."""
    t = S.t.values; pos = S.pos.values
    B = {}
    for T in range(V.TEST[0], V.TEST[1] + 1):
        for p in C.POS:
            m = np.array([FIT_FROM <= t[r] <= T - 5 and pos[r] == p for r in rows_fit])
            rr = rows_fit[m]
            assert (t[rr] <= T - 5).all(), 'beta leak'
            o, yy, q = pred[rr], y[rr], ratio[rr]
            sse = [((yy - o * q ** b) ** 2).sum() for b in BETAS]
            B[(T, p)] = float(BETAS[int(np.argmin(sse))])
    return B


def candidate(S, test, pred, ratio, B):
    return np.array([pred[r] * ratio[r] ** B[(int(S.t.values[r]), S.pos.values[r])] for r in test])


def evaluate(S, pre, A_rows_pred, y, ratio, n_perm, label):
    """A_rows_pred: OVS prediction for every row index (array, NaN where none)."""
    T = pre['test']
    rows_fit = np.array([r for r in np.where(~np.isnan(A_rows_pred))[0]])
    B = fit_betas(S, rows_fit, A_rows_pred, y, ratio)
    p_ovs = A_rows_pred[T]
    p_c = candidate(S, T, A_rows_pred, ratio, B)
    yt = y[T]
    A, Bt, K = V.build_trades(S, pre, p_c, p_ovs)
    q1 = V.q1(S, pre, p_c, p_ovs, yt, n_perm=n_perm)
    q2 = V.q2(S, pre, p_c, p_ovs, yt, A, Bt, K, n_perm=n_perm)
    return {'label': label, 'Q1': q1, 'Q2': q2, 'beta': {f'{t} {p}': b for (t, p), b in B.items()},
            'pass_both': bool(q1['pass'] and q2['pass'])}, (p_c, p_ovs, A, Bt, K)


def setup_all(a):
    st, S, pre, nnA, W, counts = V.setup(a.nflverse, a.rosters)
    y = S.FV.values.astype(float)
    O = ovs_all(S, y)
    pred = np.full(len(S), np.nan)
    for r, (nn, w) in O.items(): pred[r] = (w * y[nn]).sum()
    locked = V.predictions(S, pre, nnA, W, y)['OVS']
    assert np.allclose(pred[pre['test']], locked), 'OVS differs from the locked OVS'      # leak check 3
    _, dp, _ = C.load(a.nflverse, a.rosters)
    imp = implied(a.games)
    rA, rB, tA, tB, miss = ratios(S, imp, a.weekly, a.wrosters, dp)
    return st, S, pre, y, O, pred, rA, rB, tA, tB, miss, counts


# ── crash tests (before lock) ───────────────────────────────────────────────────────────────────
def crash(S, pre, y, O, pred, rA, runs_noise=20, runs_planted=200, perm=1000):
    rng = np.random.default_rng(7)
    out = {'noise': [], 'planted_1.0': [], 'planted_0.5': []}
    t = S.t.values
    # noise: each season's team ratios handed to random teams (here: shuffled among that season's rows by team)
    for _ in range(runs_noise):
        rN = rA.copy()
        for T in np.unique(t):
            idx = np.where(t == T)[0]
            vals = np.unique(rA[idx]); perm_map = dict(zip(vals, rng.permutation(vals)))
            rN[idx] = [perm_map[v] for v in rA[idx]]
        r, _ = evaluate(S, pre, pred, y, rN, perm, 'noise')
        out['noise'].append(bool(r['Q1']['pass'] or r['Q2']['pass']))
    # planted: outcomes (rows from 2006) = OVS x ratio**b0 + leftover error around OVS, shuffled within position
    rows = np.where(~np.isnan(pred))[0]
    resid = y[rows] - pred[rows]; pos = S.pos.values[rows]
    for b0, key, n in ((1.0, 'planted_1.0', runs_planted), (0.5, 'planted_0.5', 50)):
        for _ in range(n):
            e = resid.copy()
            for p in C.POS:
                m = pos == p; e[m] = rng.permutation(e[m])
            ys = y.copy(); ys[rows] = np.maximum(0.0, pred[rows] * rA[rows] ** b0 + e)
            # OVS is held at its real predictions (A1): the test is whether the beta fit and the two questions can
            # find a planted team effect in the outcomes.
            r, _ = evaluate(S, pre, pred, ys, rA, perm, key)
            out[key].append(bool(r['pass_both']))
            out.setdefault(key + '_detail', []).append([r['Q1']['lift'], r['Q2']['diff'], np.median(list(r['beta'].values()))])
    res = {'noise_false_passes': int(sum(out['noise'])), 'noise_runs': runs_noise,
           'planted_1.0_passes': int(sum(out['planted_1.0'])), 'planted_1.0_runs': runs_planted,
           'planted_0.5_passes': int(sum(out['planted_0.5'])), 'planted_0.5_runs': 50, 'perm': perm}
    for k in ('planted_1.0', 'planted_0.5'):
        d = np.array(out[k + '_detail']); res[k + '_median'] = {'Q1_lift': float(np.median(d[:, 0])),
                                                               'Q2_diff': float(np.median(d[:, 1])), 'beta': float(np.median(d[:, 2]))}
    res['ok'] = bool(res['noise_false_passes'] <= 1 and res['planted_1.0_passes'] >= 0.8 * runs_planted)
    return res


def main():
    ap = argparse.ArgumentParser()
    for k in ('nflverse', 'rosters', 'games', 'weekly', 'wrosters'): ap.add_argument('--' + k, required=True)
    g = ap.add_mutually_exclusive_group(required=True); g.add_argument('--crash', action='store_true'); g.add_argument('--run', action='store_true')
    ap.add_argument('--planted-runs', type=int, default=200)
    a = ap.parse_args()
    st, S, pre, y, O, pred, rA, rB, tA, tB, miss, counts = setup_all(a)
    T = pre['test']
    counts.update({'ratio_missing_A': miss['A'], 'ratio_missing_B': miss['B'],
                   'test_missing_A': int(sum(1 for r in T if tA[r] is None)),
                   'test_missing_B': int(sum(1 for r in T if tB[r] is None))})
    os.makedirs(OUT, exist_ok=True)
    if a.crash:
        res = {'prereg': 'docs/PREREG-vegas-team-context.md', 'counts': counts,
               'crash': crash(S, pre, y, O, pred, rA, runs_planted=a.planted_runs)}
        json.dump(res, open(os.path.join(OUT, 'vegas_context_crash.json'), 'w'), indent=1, default=float)
        print(json.dumps(res, indent=1, default=float)); return
    res = {'prereg': 'docs/PREREG-vegas-team-context.md', 'counts': counts}
    resA, (pc, po, A, Bt, K) = evaluate(S, pre, pred, y, rA, V.N_PERM, 'Version A (deciding)')
    res['A'] = resA
    res['decision'] = 'Version A joins OVS' if resA['pass_both'] else 'OVS stays as it is'
    # reported only
    res['B_reported'], _ = evaluate(S, pre, pred, y, rB, V.N_PERM, 'Version B (reported)')
    f1 = fv1(S, st)
    p1 = np.full(len(S), np.nan)
    for r, (nn, w) in O.items(): p1[r] = (w * f1[nn]).sum()
    res['FV1_reported'] = {}
    for lab, rr in (('A', rA), ('B', rB)):
        rf = np.where(~np.isnan(p1))[0]
        Bf = fit_betas(S, rf, p1, f1, rr)
        c1 = candidate(S, T, p1, rr, Bf)
        lift, p = C.perm_test(f1[T], c1, p1[T], S.key.values[T], V.N_PERM)
        res['FV1_reported'][lab] = {'rmse_cand': C.rmse(c1, f1[T]), 'rmse_ovs': C.rmse(p1[T], f1[T]),
                                    'lift': float(lift), 'p': float(p)}
    yt = y[T]; pos = S.pos.values[T]
    res['by_position_A'] = {p: {'rmse_cand': C.rmse(pc[pos == p], yt[pos == p]), 'rmse_ovs': C.rmse(po[pos == p], yt[pos == p]),
                                'n': int((pos == p).sum())} for p in C.POS}
    moved = np.array([tA[r] is not None and tB[r] is not None and tA[r] != tB[r] for r in T])
    res['team_changers_A'] = {'n': int(moved.sum()), 'rmse_cand': C.rmse(pc[moved], yt[moved]), 'rmse_ovs': C.rmse(po[moved], yt[moved])}
    json.dump(res, open(os.path.join(OUT, 'vegas_context_results.json'), 'w'), indent=1, default=float)
    print(json.dumps({'A': {k: resA[k] for k in ('Q1', 'Q2', 'pass_both')}, 'decision': res['decision'],
                      'B': {k: res['B_reported'][k] for k in ('Q1', 'Q2')}, 'FV1': res['FV1_reported']}, indent=1, default=float))


if __name__ == '__main__':
    main()
