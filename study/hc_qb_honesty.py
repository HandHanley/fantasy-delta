#!/usr/bin/env python3
"""
DELTA — HISTORICAL COMPS: ARE THE QB ODDS HONEST UNDER THE START RULE? Implements docs/PREREG-hc-qb-starts.md.

    python hc_qb_honesty.py NFLVERSE ROSTERS WEEKLY SCHEDULE SNAPS
"""
import sys, os, glob, json
import numpy as np, pandas as pd
import comps_value_study as C, honest_odds_study as O, comps_draft_drop as DD, qb_games as QG

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
YEARS = tuple(range(2013, 2023)); MIN_GAMES = 4; FEW = 4


def overrides(st, nflverse, wk, sched, snaps):
    games, _ = QG.qb_weeks(wk, sched, snaps, os.path.join(nflverse, 'players.csv'), 22)
    W = pd.concat([pd.read_csv(f, low_memory=False, usecols=['player_id', 'season', 'week', 'season_type',
                                                             'fantasy_points', 'fantasy_points_ppr'])
                   for f in sorted(glob.glob(os.path.join(wk, 'stats_player_week_*.csv')))], ignore_index=True)
    W = W[W.season_type == 'REG']
    W['P'] = (W.fantasy_points.fillna(0) + W.fantasy_points_ppr.fillna(0)) / 2
    keep = np.array([(k, int(y), int(w)) in games for k, y, w in zip(W.player_id, W.season, W.week)])
    gp = W[keep].groupby(['player_id', 'season']).P.agg(['sum', 'size'])
    tot, cnt = gp['sum'].to_dict(), gp['size'].to_dict()
    qb = st[st.position == 'QB']
    rule = {(k, int(y)): (float(tot.get((k, y), 0.0)), int(cnt.get((k, y), 0))) for k, y in zip(qb.player_id, qb.season)}
    minimum = {k: (v if v[1] >= MIN_GAMES else (0.0, 0)) for k, v in rule.items()}
    return rule, minimum


def grade(S, N, label, few_keys):
    rows = S.index[(S.t.isin(YEARS)) & (S.kind == 'V') & (S.pos == 'QB')].values
    pre = DD.neighbours(S, rows, 'A', pool_max_t=None)
    for r, nn in zip(pre['test'], pre['nn'][30]):
        assert (S.t.values[nn] <= S.t.values[r] - 3).all() and S.key.values[r] not in set(S.key.values[nn])
    parts = O.version_parts(S, N, pre, 'Fix 2')
    P, E = O.predictions(S, parts)
    T = pre['test']; yP = S.any_start.values[T].astype(float); yE = S.n_start.values[T].astype(float)
    few = np.array([(S.key.values[r], int(S.t.values[r])) in few_keys for r in T])
    masks = {'overall': np.ones(len(T), bool), 'few': few}
    sims, edges = O.sim_limits(S, parts, P, E, masks)
    checks, ok = {}, {}
    for g, mk in masks.items():
        ok[g] = True
        for m, pred, obs in (('P3', P, yP), ('E3', E, yE)):
            err, _ = C.calib_error(pred[mk], obs[mk], edges[(g, m)])
            lim = float(np.percentile(sims[(g, m)], 95.0))
            checks[f'{g} {m}'] = {'n': int(mk.sum()), 'error': float(err), 'limit': lim, 'honest': bool(err <= lim)}
            ok[g] &= err <= lim
    ns = S.n_start.values
    two = np.array([(w * (ns[nn] >= 2)).sum() for nn, w, _ in parts]); one = np.array([(w * (ns[nn] == 1)).sum() for nn, w, _ in parts])
    said = {g: {'two_plus_said': float(two[mk].mean()), 'two_plus_happened': float((yE[mk] >= 2).mean()),
                'one_said': float(one[mk].mean()), 'one_happened': float((yE[mk] == 1).mean()),
                'none_said': float((1 - two - one)[mk].mean()), 'none_happened': float((yE[mk] == 0).mean())} for g, mk in masks.items()}
    return {'version': label, 'rows': int(len(T)), 'few_rows': int(few.sum()), 'honest_all': bool(ok['overall']),
            'honest_few': bool(ok['few']), 'brier_all': O.brier(P, yP), 'brier_few': O.brier(P[few], yP[few]),
            'checks': checks, 'said_vs_happened': said}


def main():
    nflverse, rosters, wk, sched, snaps = sys.argv[1:6]
    C.HORIZON, C.POOL_LAG = 3, 3
    st, dp, pl = C.load(nflverse, rosters)
    g = st[st.games >= 1].groupby(['season', 'position']).size(); N = {(int(s), p): int(n) for (s, p), n in g.items()}
    rule, minimum = overrides(st, nflverse, wk, sched, snaps)
    few_keys = {k for k, v in rule.items() if v[1] <= FEW}
    res = {'prereg': 'docs/PREREG-hc-qb-starts.md', 'versions': {}}
    for label, ov in (('Today', None), ('Start rule', rule), ('Start rule + 4 minimum', minimum)):
        S, _ = C.build(st, dp, pl, snap_last=max(YEARS), prod_override=ov)
        S = S.reset_index(drop=True)
        res['versions'][label] = grade(S, N, label, few_keys)
        v = res['versions'][label]
        print(label, {k: v[k] for k in ('rows', 'few_rows', 'honest_all', 'honest_few', 'brier_all', 'brier_few')}, flush=True)
    honest = [k for k in ('Start rule', 'Start rule + 4 minimum') if res['versions'][k]['honest_all'] and res['versions'][k]['honest_few']]
    res['decision'] = min(honest, key=lambda k: res['versions'][k]['brier_all']) if honest else 'keep today (back to Steve)'
    json.dump(res, open(os.path.join(OUT, 'hc_qb_honesty_results.json'), 'w'), indent=1, default=float)
    print('DECISION:', res['decision'])


if __name__ == '__main__':
    main()
