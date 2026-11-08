#!/usr/bin/env python3
"""
DELTA — A SUPERFLEX ROOKIE-DRAFT ORDER FROM SCARCITY MATH. Implements docs/PREREG-superflex-pick-order.md; where they
disagree, the pre-registration (with its section 10 amendments) wins.

QB boost = QB veterans' five-season value under superflex lines / under 1QB lines (seasons finished before the class).
Expected value = 1QB slot range's average (other classes) x boost for QBs. Re-sort -> superflex slots -> pick values
with the usual fairness fix. Reality check: rank agreement with DynastyProcess superflex rookie rankings, 2020-2023.

    python pick_values_sf.py --nflverse DIR --rosters DIR --crash      # crash tests + order sanity (before lock)
    python pick_values_sf.py --nflverse DIR --rosters DIR --confirm    # reality check + 18 formats (once, after lock)
"""
import argparse, itertools, json, os, time
from pathlib import Path
import importlib.util
import numpy as np
import pandas as pd
import comps_value_study as C
import own_value_scale as V
import pick_values as P
import pick_values_formats as F

ROOT = Path(__file__).resolve().parent.parent
BOARD_CLASSES = list(range(2014, 2024))
BINS = F.BINS
DELTA_FMT = F.DELTA_FMT
SF_FORMATS = [DELTA_FMT] + [f for f in itertools.product(F.TEAMS, ('SF',), F.PPR, F.TEP) if f != DELTA_FMT]
CRASH_FORMATS = [DELTA_FMT, (10, 'SF', 0.0, 0.0)]
FIT = [2020, 2021]                 # amendment A1: the boost's size is fitted to real superflex order here
HOLDOUT = [2022, 2023]             # ... and checked here, never seen by the fit
GRID = np.round(np.arange(1.0, 4.001, 0.05), 2)


def bin_of(s):
    return next((i for i, (a, b) in enumerate(BINS) if a <= s <= b), len(BINS) - 1)


# ── the full board (FFC's rookie file, not cut at 36) ───────────────────────────────────────────────
def board():
    spec = importlib.util.spec_from_file_location('ff', ROOT / 'scripts' / 'future-first-study.py')
    ff = importlib.util.module_from_spec(spec); spec.loader.exec_module(ff)
    dp, und, ids = ff.draft_tables()
    rows = []
    for y in BOARD_CLASSES:                       # ffc_slots' own matching, line for line, without the 36 cut
        R = json.load(open(ff.FIX / f'ffc-rookie-adp-{y}.json'))['response']
        for p in sorted(R['players'], key=lambda p: p['adp']):
            if p['position'] not in ff.SKILL: continue
            k = ff.norm(p['name']); want = ff.POS_EXCEPT.get((y, k), p['position'])
            m = dp[(dp.season == y) & (dp.key == k) & (dp.position == want)]
            if len(m) == 0:
                m = und[(und.season == y) & (und.key == k) & (und.position == p['position'])]
            if len(m) != 1: continue
            rows.append(dict(cls=y, name=p['name'], pos=p['position'], gsis=m['gsis_id'].iat[0], adp=p['adp']))
    B = pd.DataFrame(rows)
    B['slot1'] = B.groupby('cls')['adp'].rank(method='first').astype(int)
    ref, _ = ff.ffc_slots(dp, und)                # must agree with the locked slots for the top 36
    top = B[B.slot1 <= 36].merge(ref, left_on=['cls', 'gsis'], right_on=['cls', 'gsis'])
    assert len(top) == len(ref) == (B.slot1 <= 36).sum() and (top.slot1 == top.slot).all(), 'board != ffc_slots'
    return B.reset_index(drop=True), ff, dp, ids


# ── one format's build: snapshots, veterans, board outcomes ────────────────────────────────────────
def build(f, nflverse, rosters, B):
    F.apply(f)
    st, S, pre, nnA, W, counts = V.setup(nflverse, rosters)
    y = S.FV.values.astype(float)
    pr = V.predictions(S, pre, nnA, W, y)
    T = pre['test']; isv = S.kind.values[T] == 'V'
    vet = {'t': S.t.values[T][isv], 'ovs': pr['OVS'][isv], 'y': y[T][isv], 'key': S.key.values[T][isv],
           'pos': S.pos.values[T][isv], 'row': T[isv]}
    r0 = S[S.kind == 'R0']; r0 = {(k, int(t)): i for i, k, t in zip(r0.index, r0.key, r0.t)}
    yb, line = np.full(len(B), np.nan), B.pos.values.copy()
    for j, r in enumerate(B.itertuples()):
        if r.cls > 2021: continue                  # window not closed; order only
        i = r0.get((r.gsis, r.cls - 1))
        if i is not None:
            assert S.complete.values[i]; yb[j] = S.FV.values[i]; line[j] = S.pos.values[i]
        else:
            yb[j] = P.fv5_from_stats(st, r.gsis, r.pos, r.cls)
    qv = S[(S.kind == 'V') & (S.pos == 'QB') & S.complete]
    qb = {(k, int(t)): float(v) for k, t, v in zip(qv.key, qv.t, qv.FV)}
    return {'S': S, 'vet': vet, 'yb': yb, 'line': line, 'qb': qb, 'lines': dict(C.REPL_N)}


def boosts(sf, one):
    out = {}
    common = sorted(set(sf['qb']) & set(one['qb']))
    for c in BOARD_CLASSES:
        ks = [k for k in common if k[1] <= c - 6]
        out[c] = sum(sf['qb'][k] for k in ks) / sum(one['qb'][k] for k in ks)
    return out


def sf_order(B, y1, boost):
    """Superflex slot for every board row (NaN past 36). Reads other classes' 1QB-line outcomes only."""
    graded = (B.cls <= 2021).values & (B.slot1 <= 36).values
    b1 = np.array([bin_of(s) for s in B.slot1])
    sf = np.full(len(B), np.nan); E = np.zeros(len(B))
    for c in BOARD_CLASSES:
        oth = graded & (B.cls.values != c)
        base = np.array([y1[oth & (b1 == k)].mean() for k in range(len(BINS))])
        ix = np.where(B.cls.values == c)[0]
        E[ix] = base[b1[ix]] * np.where(B.pos.values[ix] == 'QB', boost[c], 1.0)
        order = ix[np.lexsort((B.slot1.values[ix], -E[ix]))]
        sf[order] = np.arange(1, len(order) + 1)
    sf[sf > 36] = np.nan
    return sf, E


def picks_from(B, sf_slot, ysf, line):
    m = (B.cls.values <= 2021) & ~np.isnan(sf_slot)
    s = sf_slot[m].astype(int)
    return {'cls': B.cls.values[m], 'tier': np.array([bin_of(x) for x in s]), 'slot': s, 'pos': line[m],
            'y': ysf[m], 'name': B.name.values[m], 'key': B.gsis.values[m]}


def one_qb(f):
    return (f[0], '1QB', f[2], f[3])


def make(f, nflverse, rosters, B, b_fit):
    one = build(one_qb(f), nflverse, rosters, B)
    sf = build(f, nflverse, rosters, B)          # applied last: C.REPL_N / C.load now point at the SF format
    scar = boosts(sf, one)                       # the scarcity-math boost: reported, no longer used (A1)
    bst = {c: b_fit for c in BOARD_CLASSES}
    slot, E = sf_order(B, one['yb'], bst)
    # leak check: scramble every class's own 1QB outcomes in turn; its order must not move
    rng = np.random.default_rng(5)
    for c in range(2014, 2022):
        y2 = one['yb'].copy(); mk = (B.cls.values == c) & ~np.isnan(y2)
        y2[mk] = rng.permutation(y2[mk]) * 2 + 10
        s2, _ = sf_order(B, y2, bst)
        mc = B.cls.values == c
        assert np.array_equal(np.nan_to_num(s2[mc], nan=-1), np.nan_to_num(slot[mc], nan=-1)), c
    pk = picks_from(B, slot, sf['yb'], sf['line'])
    return one, sf, scar, slot, pk


def sanity(B, slot, bst, b_fit=None):
    qb = (B.pos.values == 'QB') & (B.cls.values <= 2021)
    inn = qb & ~np.isnan(slot)
    return {'boost_min': min(bst.values()), 'boost_max': max(bst.values()),
            'boost': {int(k): round(v, 3) for k, v in bst.items()},
            'qbs_on_board_2014_2021': int(qb.sum()), 'qbs_in_sf_top36': int(inn.sum()),
            'qbs_in_1qb_top36': int((qb & (B.slot1.values <= 36)).sum()),
            'mean_qb_move_up': float((B.slot1.values[inn] - slot[inn]).mean()),
            'fitted_boost': b_fit,
            'ok': bool(min(bst.values()) > 1 and (B.slot1.values[inn] - slot[inn]).mean() > 0)}


def spearman(a, b):
    return float(pd.Series(a).rank().corr(pd.Series(b).rank()))


def reality(B, slot, D, classes):
    out, ours, base = {}, [], []
    for c in classes:
        d = D[D.cls == c].set_index('gsis').slot
        mc = (B.cls.values == c) & ~np.isnan(slot)
        g = B.gsis.values[mc]; both = np.array([x in d.index for x in g])
        s_ours, s_1qb = slot[mc][both], B.slot1.values[mc][both]
        s_dp = d.loc[g[both]].values
        r_o, r_1 = spearman(s_ours, s_dp), spearman(s_1qb, s_dp)
        q = (B.pos.values[mc][both] == 'QB')
        top2 = lambda s: float(np.sort(s[q])[:2].mean()) if q.sum() >= 2 else None
        out[c] = {'rookies_in_both': int(both.sum()), 'corr_ours': r_o, 'corr_1qb': r_1,
                  'top2_qb_slot': {'ours': top2(s_ours), '1qb': top2(s_1qb.astype(float)), 'dynastyprocess': top2(s_dp.astype(float))}}
        ours.append(r_o); base.append(r_1)
    wins = sum(o > b for o, b in zip(ours, base))
    return {'by_class': out, 'mean_ours': float(np.mean(ours)), 'mean_1qb': float(np.mean(base)), 'classes_won': wins,
            'pass': bool(np.mean(ours) > np.mean(base) and wins == len(classes))}


def fit_boost(B, y1, D):
    """One QB boost for every class: the grid value whose order best matches real superflex rankings, FIT classes only."""
    sc = []
    for b in GRID:
        s, _ = sf_order(B, y1, {c: b for c in BOARD_CLASSES})
        sc.append(reality(B, s, D, FIT)['mean_ours'])
    sc = np.array(sc); best = float(GRID[int(np.argmax(sc))])   # ties -> the smaller boost (first)
    return best, {float(b): round(float(v), 4) for b, v in zip(GRID, sc)}


def values(f, sf, pk, n_boot=P.BOOT):
    vet = sf['vet']; M = P.Matcher(vet); yp, yv = pk['y'], vet['y']
    est = P.estimate(pk, vet, M, yp, yv, detail=True)
    ci = P.bootstrap(pk, vet, M, yp, yv, n_boot=n_boot)
    top = P.ruler_top(sf['S']); mult = est['R']
    G = P.groups(pk); w1 = np.ones(len(yp))
    raw = [float(yp[(pk['slot'] >= a) & (pk['slot'] <= b)].mean()) for a, b in BINS]
    sv = [round(10000 * mult * x / top) for x in raw]
    first = round(np.mean([sv[bin_of(s)] for s in range(1, f[0] + 1)]))
    return {'format': F.name(f), 'key': list(f), 'lines': sf['lines'], 'R': est['R'], 'range': [ci['lo'], ci['hi']],
            'range_includes_1': ci['includes_1'], 'picks_scored': int(est['keep'].sum()),
            'qb_picks': int((pk['pos'] == 'QB').sum()),
            'R_QB_picks': P.sub_R(yp, est['m'], est['keep'], w1, G['QB']), 'R_QB_range': ci['groups']['QB'],
            'R_other_picks': P.sub_R(yp, est['m'], est['keep'], w1, G['RB/WR/TE']),
            'slot_bins': {f'{a}-{b}': v for (a, b), v in zip(BINS, sv)},
            'slot_bins_year_out': {f'{a}-{b}': round(P.YEAR_OUT * v) for (a, b), v in zip(BINS, sv)},
            'first_slot_unknown': first, 'by_pick': F.by_pick(f[0], sv)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nflverse', required=True); ap.add_argument('--rosters', required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--fit', action='store_true'); g.add_argument('--crash', action='store_true')
    g.add_argument('--confirm', action='store_true')
    ap.add_argument('--runs', type=int, default=100); ap.add_argument('--boot', type=int, default=1000)
    a = ap.parse_args()
    B, ff, dp, ids = board()
    D = ff.dp_superflex_slots(ids, dp)
    here = os.path.dirname(os.path.abspath(__file__)); t0 = time.time()
    fit_path = os.path.join(here, 'out', 'pick_values_sf_fit.json')
    one = build(one_qb(DELTA_FMT), a.nflverse, a.rosters, B)
    b_fit, curve = fit_boost(B, one['yb'], D)
    if a.fit:
        slot, _ = sf_order(B, one['yb'], {c: b_fit for c in BOARD_CLASSES})
        m = B.cls.values == 2018
        o = np.argsort(np.nan_to_num(slot[m], nan=99))[:16]
        ex = [[int(slot[m][k]), B.name.values[m][k], B.pos.values[m][k], int(B.slot1.values[m][k])] for k in o]
        json.dump({'fit_classes': FIT, 'boost': b_fit, 'curve': curve, 'example_2018': ex}, open(fit_path, 'w'), indent=1)
        print('fitted boost', b_fit); print('curve', curve); print('2018:', ex)
        return
    assert json.load(open(fit_path))['boost'] == b_fit, 'fit changed since it was recorded'
    if a.crash:
        import test_pick_values_formats as TF
        out = {'board_rows': int(len(B)), 'boost': b_fit}
        for j, f in enumerate(CRASH_FORMATS):
            one_, sf, scar, slot, pk = make(f, a.nflverse, a.rosters, B, b_fit)
            r = {'sanity': sanity(B, slot, scar, b_fit), 'picks': int(len(pk['y'])), 'qb_picks': int((pk['pos'] == 'QB').sum())}
            r.update(TF.worlds(pk, sf['vet'], P.Matcher(sf['vet']), a.runs, a.boot, tag=10 + j))
            out[F.name(f)] = r
            print(F.name(f), r, f'{time.time() - t0:.0f}s', flush=True)
        json.dump(out, open(os.path.join(here, 'out', 'pick_values_sf_crash.json'), 'w'), indent=1, default=float)
        ok = all(v['sanity']['ok'] for k, v in out.items() if isinstance(v, dict))
        print('order sanity:', 'PASS' if ok else 'FAIL')
        return
    res = {'prereg': 'docs/PREREG-superflex-pick-order.md', 'boost': b_fit, 'formats': []}
    for f in SF_FORMATS:
        one_, sf, scar, slot, pk = make(f, a.nflverse, a.rosters, B, b_fit)
        if f == DELTA_FMT:
            res['reality_check_holdout'] = reality(B, slot, D, HOLDOUT)
            print('reality check', json.dumps(res['reality_check_holdout'], default=float), flush=True)
        r = values(f, sf, pk) | {'sanity': sanity(B, slot, scar, b_fit)}
        res['formats'].append(r)
        print(f"{r['format']:<40} R {r['R']:.2f} [{r['range'][0]:.2f}-{r['range'][1]:.2f}] bins {list(r['slot_bins'].values())} "
              f"QB {r['R_QB_picks']:.2f} (n {r['qb_picks']}) rest {r['R_other_picks']:.2f}  {time.time() - t0:.0f}s", flush=True)
    json.dump(res, open(os.path.join(here, 'out', 'pick_values_sf_results.json'), 'w'), indent=1, default=float)


if __name__ == '__main__':
    main()
