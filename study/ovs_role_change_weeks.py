#!/usr/bin/env python3
"""
DELTA — ROLE CHANGE, AMENDMENT A1: weeks 5, 9 and 13 pooled (docs/PREREG-ovs-role-change.md §5A).

    python ovs_role_change_weeks.py --mode build --week W ...   # builds and caches one week's frames
    python ovs_role_change_weeks.py --mode crash|run ...        # pooled decision over the cached weeks
"""
import argparse, json, os, pickle
import numpy as np
import pandas as pd
import comps_value_study as C
import ovs_small_samples as SSm
import ovs_qb_starts as QS
import ovs_one_match as M
import ovs_role_change as RC
import rookie_snaps as RS

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
WEEKS = (5, 9, 13)


def set_week(w):
    SSm.WEEK = w; QS.WEEK = w
    SSm.CACHE = '/tmp/ovs_small_samples_frame.pkl' if w == 9 else f'/tmp/ovs_small_samples_frame_w{w}.pkl'
    RC.CACHE = '/tmp/ovs_role_change_frame.pkl' if w == 9 else f'/tmp/ovs_role_change_frame_w{w}.pkl'


def frame_g(a, w):
    """M.frame for week w. Week 9 runs SSm.setup's reproduction assertion; other weeks have no adopted figure."""
    set_week(w)
    if w == 9:
        return M.frame(a)
    F = SSm.frame(a)
    S, rows = F['Sin'], F['rows']
    y = np.nan_to_num(S.FV.values.astype(float))
    t = S.t.values[rows]
    test = (t >= SSm.TEST[0]) & (t <= SSm.TEST[1])
    n = F['n'][rows]
    rook = S.rookie_Y.values[rows].astype(bool); qb = S.pos.values[rows] == 'QB'
    inc_today = rook & np.where(qb, F['none'][rows], n == 0)
    snaps = RS.offense_snaps(a.snaps, os.path.join(a.nflverse, 'players.csv'), w)
    keys = S.key.values[rows]
    under = np.array([RS.under(snaps, k, tt) for k, tt in zip(keys, t)])
    return dict(F=F, S=S, rows=rows, y=y, test=test, on_draft=rook & (inc_today | under), keys=keys,
                pos=S.pos.values[rows], t=t, rook=rook, pick=np.exp(S.draft.values[rows]))


def week_parts(a, w):
    G = frame_g(a, w)
    R = RC.frame(a, G)
    y = G['y']
    return dict(today=M.values(G, y), new=RC.values_with(G, R['nnI'], R['wI'], y), G=G, R=R,
                mask=R['flag_rows'] & ~G['on_draft'])


def pooled(parts, y_override=None):
    cat = lambda f: np.concatenate([f(p) for p in parts])
    if y_override is None:
        today, new = cat(lambda p: p['today']), cat(lambda p: p['new'])
    else:
        today = cat(lambda p: M.values(p['G'], y_override))
        new = cat(lambda p: RC.values_with(p['G'], p['R']['nnI'], p['R']['wI'], y_override))
    return today, new


def decide(parts, today, new, truth, n_perm=RC.N_PERM):
    cat = lambda f: np.concatenate([f(p) for p in parts])
    test, mask, keys = cat(lambda p: p['G']['test']), cat(lambda p: p['mask']), cat(lambda p: p['G']['keys'])
    mv = test & mask
    lift, pv = C.perm_test(truth[mv], new[mv], today[mv], keys[mv], n_perm)
    a0, a1 = M.rmse(today[test], truth[test]), M.rmse(new[test], truth[test])
    return {'flagged_rows': int(mv.sum()), 'rmse_today': M.rmse(today[mv], truth[mv]), 'rmse_rule': M.rmse(new[mv], truth[mv]),
            'lift': float(lift), 'p': float(pv), 'all_rows': int(test.sum()), 'all_rmse_today': a0, 'all_rmse_rule': a1,
            'all_rows_worse_by': float(a1 / a0 - 1), 'pass': bool(lift >= RC.BAR and pv < RC.ALPHA and a1 / a0 - 1 <= RC.GUARD)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=('build', 'crash', 'run'), required=True)
    ap.add_argument('--week', type=int)
    for k in ('nflverse', 'rosters', 'weekly', 'wrost', 'inj', 'sched', 'snaps'): ap.add_argument('--' + k, required=True)
    a = ap.parse_args()
    if a.mode == 'build':
        p = week_parts(a, a.week)
        print('week', a.week, 'flagged test rows', int((p['mask'] & p['G']['test']).sum()), 'frame flagged', int(p['mask'].sum()))
        return
    parts = [week_parts(a, w) for w in WEEKS]
    y = parts[0]['G']['y']
    for p in parts: assert np.array_equal(p['G']['y'], y)
    truth = np.concatenate([y[p['G']['rows']] for p in parts])
    info = {f'week_{w}': {'flagged_test_rows': int((p['mask'] & p['G']['test']).sum()),
                          'by_position': {q: int((p['mask'] & p['G']['test'] & (p['G']['pos'] == q)).sum()) for q in RC.LINE}}
            for w, p in zip(WEEKS, parts)}
    print(info, flush=True)
    today, new = pooled(parts)
    if a.mode == 'crash':
        res = {'info': info}
        S = parts[0]['G']['S']
        grp = pd.DataFrame({'p': S.pos.values, 't': S.t.values}).groupby(['p', 't']).groups
        rng = np.random.default_rng(7); ok = 0; lifts = []
        for i in range(20):
            yn = y.copy()
            for g in grp.values():
                g = np.array(list(g)); yn[g] = y[rng.permutation(g)]
            tn, nn_ = pooled(parts, yn)
            r = decide(parts, tn, nn_, np.concatenate([yn[p['G']['rows']] for p in parts]), n_perm=1000)
            ok += r['pass']; lifts.append(r['lift'])
        res['noise'] = {'runs': 20, 'passed': int(ok), 'ok': ok <= 1, 'median_lift': float(np.median(lifts))}
        print(res['noise'], flush=True)

        def world(rng, use_rule):
            out = []
            for p in parts:
                F, R, d = p['G']['F'], p['R'], p['G']['on_draft']
                nI, wI = (R['nnI'], R['wI']) if use_rule else (F['nnI'], F['wI'])
                o = np.empty(len(d))
                for i in range(len(d)):
                    n, w = (F['nnB'][i], F['wB'][i]) if d[i] else (nI[i], wI[i])
                    o[i] = y[n][rng.choice(len(n), p=w / w.sum())]
                out.append(o)
            return np.concatenate(out)
        for name, use_rule, runs, seed in (('rule_is_right', True, 200, 75), ('today_is_right', False, 50, 76)):
            rng = np.random.default_rng(seed); ok = 0; lifts = []
            for _ in range(runs):
                r = decide(parts, today, new, world(rng, use_rule), n_perm=1000); ok += r['pass']; lifts.append(r['lift'])
            res[name] = {'runs': runs, 'passed': int(ok), 'share': ok / runs, 'median_lift': float(np.median(lifts))}
            print(name, res[name], flush=True)
        res['planted_ok'] = res['rule_is_right']['share'] >= 0.80
    else:
        res = {'prereg': 'docs/PREREG-ovs-role-change.md §5A', 'info': info, 'decides': decide(parts, today, new, truth)}
        by_week = {}
        off = 0
        for w, p in zip(WEEKS, parts):
            k = len(p['G']['rows']); sl = slice(off, off + k); off += k
            mv = p['mask'] & p['G']['test']
            by_week[w] = {'rows': int(mv.sum()), 'rmse_today': M.rmse(today[sl][mv], truth[sl][mv]), 'rmse_rule': M.rmse(new[sl][mv], truth[sl][mv])}
        res['reported'] = {'by_week': by_week}
        cat = lambda f: np.concatenate([f(p) for p in parts])
        mv = cat(lambda p: p['mask'] & p['G']['test']); pos = cat(lambda p: p['G']['pos'])
        res['reported']['by_position'] = {q: {'rows': int((mv & (pos == q)).sum()), 'rmse_today': M.rmse(today[mv & (pos == q)], truth[mv & (pos == q)]),
                                              'rmse_rule': M.rmse(new[mv & (pos == q)], truth[mv & (pos == q)])} for q in RC.LINE}
        res['reported']['produced_over_value_flagged'] = {'today': float(truth[mv].sum() / today[mv].sum()), 'rule': float(truth[mv].sum() / new[mv].sum())}
    json.dump(res, open(os.path.join(OUT, f'ovs_role_change_weeks_{a.mode}.json'), 'w'), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == '__main__':
    main()
