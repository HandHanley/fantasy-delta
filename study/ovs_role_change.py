#!/usr/bin/env python3
"""
DELTA — NEW VALUE: A PLAYER WHOSE ROLE GREW IS JUDGED ON HIS NEW ROLE. Implements docs/PREREG-ovs-role-change.md; where
they disagree, the pre-registration wins.

Flag (usage only): RB/WR/TE, 4+ games this season (to week 9) and last season, this season's share of team carries +
targets inside the starter line at his position (top 34 RB / 48 WR / 14 TE among players with 4+ games), last season's
share under two-thirds of this season's, season 2010+. Flagged rows use this season's production only in matching.

    python ovs_role_change.py --mode crash|run --nflverse D --rosters D --weekly D --wrost D --inj D --sched FILE --snaps D
"""
import argparse, json, os, pickle
import numpy as np
import pandas as pd
import comps_value_study as C
import ovs_in_season as I
import ovs_available_ppg as AP
import ovs_qb_starts as QS
import ovs_small_samples as SSm
import ovs_one_match as M

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
CACHE = '/tmp/ovs_role_change_frame.pkl'
LINE = {'RB': 34, 'WR': 48, 'TE': 14}
MIN_G, RATIO, FIRST_Y = 4, 2 / 3, 2010
BAR, ALPHA, GUARD, N_PERM = 0.02, 0.05, 0.005, 10000


def season_share(weekly_dir, yr, upto=None):
    f = os.path.join(weekly_dir, f'stats_player_week_{yr}.csv')
    w = pd.read_csv(f, usecols=['player_id', 'position', 'week', 'season_type', 'team', 'carries', 'targets'], low_memory=False)
    w = w[w.season_type == 'REG'].copy()
    w[['carries', 'targets']] = w[['carries', 'targets']].fillna(0)
    w['opp'] = w.carries + w.targets
    w = w.join(w.groupby(['team', 'week']).opp.sum().rename('team_opp'), on=['team', 'week'])
    if upto is not None: w = w[w.week <= upto]
    g = w.groupby('player_id').agg(opp=('opp', 'sum'), team_opp=('team_opp', 'sum'), games=('week', 'nunique'),
                                   pos=('position', 'last'))
    g['share'] = np.where(g.team_opp > 0, g.opp / g.team_opp.where(g.team_opp > 0, 1), 0.0)
    return g


def role_flags(weekly_dir, week, years):
    """{(player_id, season): True} for flagged player-seasons (section 1)."""
    out = set(); detail = {}
    for Y in years:
        if Y < FIRST_Y: continue
        cur, prev = season_share(weekly_dir, Y, week), season_share(weekly_dir, Y - 1)
        el = cur[(cur.games >= MIN_G) & cur.pos.isin(list(LINE))].copy()
        el['prank'] = el.groupby('pos').share.rank(ascending=False, method='first')
        el = el[el.prank <= el.pos.map(LINE)]
        el = el.join(prev[['share', 'games']], rsuffix='_prev', how='inner')
        el = el[(el.games_prev >= MIN_G) & (el.share_prev < RATIO * el.share)]
        for pid, r in el.iterrows():
            out.add((pid, Y)); detail[(pid, Y)] = (float(r.share), float(r.share_prev), r.pos)
    return out, detail


def make_wrapper(orig, flags, counter):
    def prod_role(Sin, W, week, L_full, L_upto, st, A_full, A_upto, rookie_qb_sits=False):
        v, lifted = orig(Sin, W, week, L_full, L_upto, st, A_full, A_upto, rookie_qb_sits=rookie_qb_sits)
        v = v.copy()
        upto = W[W.week <= week].groupby(['player_id', 'season']).agg(P=('P', 'sum'), G=('g', 'sum'))
        UP, UG = upto.P.to_dict(), upto.G.to_dict()
        spos = st.set_index(['player_id', 'season']).position.to_dict()
        n = 0
        for i, (k, Y, pos, kin) in enumerate(zip(Sin.key.values, Sin.t.values, Sin.pos.values, Sin.kind.values)):
            if kin != 'V' or (k, int(Y)) not in flags: continue
            aY = max(A_upto.get((k, Y), 0), UG.get((k, Y), 0))
            if aY < 1: continue
            v[i] = (UP.get((k, Y), 0.0) / aY) / L_upto[(Y, spos.get((k, Y), pos), week)]
            n += 1
        counter['changed'] = n
        return v, lifted
    return prod_role


def frame(a, G):
    if os.path.exists(CACHE):
        return pickle.load(open(CACHE, 'rb'))
    C.HORIZON = I.HORIZON
    st, W, Sin, Sb, skipped = I.build(a.nflverse, a.rosters, a.weekly, SSm.WEEK)
    assert np.array_equal(Sin.key.values, G['S'].key.values) and np.array_equal(Sin.t.values, G['S'].t.values)
    L_full, L_upto = I.levels(W)
    players = os.path.join(a.nflverse, 'players.csv')
    flags, detail = role_flags(a.weekly, SSm.WEEK, range(int(Sin.t.min()), int(Sin.t.max()) + 1))
    orig = AP.prod_available
    cnt = {}
    AP.prod_available = make_wrapper(orig, set(), cnt)          # check: no flags reproduces today's production
    try:
        SS0, none0, _ = QS.build_S(Sin, W, st, L_full, L_upto, a, a.sched, a.snaps, players)
        AP.prod_available = make_wrapper(orig, flags, cnt)
        SS, none, _ = QS.build_S(Sin, W, st, L_full, L_upto, a, a.sched, a.snaps, players)
    finally:
        AP.prod_available = orig
    assert np.array_equal(none, none0)
    p0, p1 = SS0['prod'].values.astype(float), SS['prod'].values.astype(float)
    fl = np.array([(k, int(t)) in flags and kd == 'V' for k, t, kd in zip(Sin.key.values, Sin.t.values, SS0.kind.values)])
    same = np.isclose(p0, p1, equal_nan=True)
    assert same[~fl].all(), int((~same[~fl]).sum())
    C.W_V['games'] = 0.0
    rows = G['rows']
    vr = rows[~none[rows]]
    # reproduction check on a sample: today's matches from the unflagged frame
    rng = np.random.default_rng(1); samp = rng.choice(vr, 300, replace=False)
    ti, nn, w = I.match(SS0, samp)
    pos = {int(r): j for j, r in enumerate(rows)}
    for r, a_, b_ in zip(ti, nn, w):
        assert np.array_equal(a_, G['F']['nnI'][pos[int(r)]]) and np.allclose(b_, G['F']['wI'][pos[int(r)]]), int(r)
    ti, nn, w = I.match(SS, vr)
    nnI = list(G['F']['nnI']); wI = list(G['F']['wI'])
    for r, a_, b_ in zip(ti, nn, w): nnI[pos[int(r)]] = a_; wI[pos[int(r)]] = b_
    flag_rows = fl[rows]
    R = {'nnI': nnI, 'wI': wI, 'flag_rows': flag_rows, 'changed_prod_rows': int(cnt['changed']), 'flags': flags,
         'detail': {f'{k}|{t}': v for (k, t), v in detail.items()}}
    pickle.dump(R, open(CACHE, 'wb'))
    return R


def values_with(G, nnI, wI, y):
    F = G['F']
    pin = np.array([(w * y[n]).sum() for n, w in zip(nnI, wI)])
    pb = np.array([(w * y[n]).sum() for n, w in zip(F['nnB'], F['wB'])])
    return np.where(G['on_draft'], pb, pin)


def decide(G, mask, today, new, truth, n_perm=N_PERM):
    mv = G['test'] & mask; m = G['test']
    r0, r1 = M.rmse(today[mv], truth[mv]), M.rmse(new[mv], truth[mv])
    lift, p = C.perm_test(truth[mv], new[mv], today[mv], G['keys'][mv], n_perm)
    a0, a1 = M.rmse(today[m], truth[m]), M.rmse(new[m], truth[m])
    return {'flagged_rows': int(mv.sum()), 'rmse_today': r0, 'rmse_rule': r1, 'lift': float(lift), 'p': float(p),
            'all_rows': int(m.sum()), 'all_rmse_today': a0, 'all_rmse_rule': a1, 'all_rows_worse_by': float(a1 / a0 - 1),
            'pass': bool(lift >= BAR and p < ALPHA and a1 / a0 - 1 <= GUARD)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=('crash', 'run'), required=True)
    for k in ('nflverse', 'rosters', 'weekly', 'wrost', 'inj', 'sched', 'snaps'): ap.add_argument('--' + k, required=True)
    a = ap.parse_args()
    G = M.frame(a); G['F'] = SSm.frame(a)
    R = frame(a, G)
    y, rows = G['y'], G['rows']; yr = y[rows]
    mask = R['flag_rows'] & ~G['on_draft']
    today, new = M.values(G, y), values_with(G, R['nnI'], R['wI'], y)
    F = G['F']
    t = G['t']
    info = {'flagged_test_rows': int((mask & G['test']).sum()), 'flagged_all_frame_rows': int(mask.sum()),
            'by_season': {int(s): int((mask & (t == s)).sum()) for s in range(2010, 2023)},
            'by_position': {p: int((mask & G['test'] & (G['pos'] == p)).sum()) for p in LINE},
            'test_rows_value_moved': int((G['test'] & ~np.isclose(today, new)).sum()),
            'changed_prod_rows_in_frame': R['changed_prod_rows']}
    print(info, flush=True)
    if a.mode == 'crash':
        res = {'info': info}
        grp = pd.DataFrame({'p': G['S'].pos.values, 't': G['S'].t.values}).groupby(['p', 't']).groups
        rng = np.random.default_rng(7); ok = 0; lifts = []
        for i in range(20):
            yn = y.copy()
            for g in grp.values():
                g = np.array(list(g)); yn[g] = y[rng.permutation(g)]
            r = decide(G, mask, M.values(G, yn), values_with(G, R['nnI'], R['wI'], yn), yn[rows], n_perm=1000)
            ok += r['pass']; lifts.append(r['lift'])
        res['noise'] = {'runs': 20, 'passed': int(ok), 'ok': ok <= 1, 'median_lift': float(np.median(lifts))}
        print(res['noise'], flush=True)
        d = G['on_draft']
        def world(rng, nnI, wI):
            out = np.empty(len(rows))
            for i in range(len(rows)):
                n, w = (F['nnB'][i], F['wB'][i]) if d[i] else (nnI[i], wI[i])
                out[i] = y[n][rng.choice(len(n), p=w / w.sum())]
            return out
        for name, (nI, wI_), runs, seed in (('rule_is_right', (R['nnI'], R['wI']), 200, 75), ('today_is_right', (F['nnI'], F['wI']), 50, 76)):
            rng = np.random.default_rng(seed); ok = 0; lifts = []
            for _ in range(runs):
                r = decide(G, mask, today, new, world(rng, nI, wI_), n_perm=1000); ok += r['pass']; lifts.append(r['lift'])
            res[name] = {'runs': runs, 'passed': int(ok), 'share': ok / runs, 'median_lift': float(np.median(lifts))}
            print(name, res[name], flush=True)
        res['planted_ok'] = res['rule_is_right']['share'] >= 0.80
    else:
        res = {'prereg': 'docs/PREREG-ovs-role-change.md', 'info': info, 'decides': decide(G, mask, today, new, yr)}
        mv = mask & G['test']
        res['reported'] = {
            'by_position': {p: {'rows': int((mv & (G['pos'] == p)).sum()),
                                'rmse_today': M.rmse(today[mv & (G['pos'] == p)], yr[mv & (G['pos'] == p)]),
                                'rmse_rule': M.rmse(new[mv & (G['pos'] == p)], yr[mv & (G['pos'] == p)])} for p in LINE},
            'produced_over_value_flagged': {'today': float(yr[mv].sum() / today[mv].sum()), 'rule': float(yr[mv].sum() / new[mv].sum())},
            'mean_value_flagged': {'today': float(today[mv].mean()), 'rule': float(new[mv].mean()), 'produced': float(yr[mv].mean())},
            'spearman_all': {'today': float(pd.Series(today[G['test']]).corr(pd.Series(yr[G['test']]), method='spearman')),
                             'rule': float(pd.Series(new[G['test']]).corr(pd.Series(yr[G['test']]), method='spearman'))}}
    json.dump(res, open(os.path.join(OUT, f'ovs_role_change_{a.mode}.json'), 'w'), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == '__main__':
    main()
