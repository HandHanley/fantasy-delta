#!/usr/bin/env python3
"""
DELTA — HONEST ODDS FOLLOW-UP: LEAGUE SIZE FOR VETERANS ONLY (Fix 3)

Implements docs/PREREG-honest-odds-v3.md, reusing honest_odds_study.py (locked 356f183) unchanged.
Test set: never-graded three-year odds for t = 2009-2012.

    python honest_odds_v3.py --nflverse DIR --rosters DIR --size-check [--runs 200]
    python honest_odds_v3.py --nflverse DIR --rosters DIR                 # real run (once, after lock)
"""
import argparse, json, os, time
import numpy as np
import comps_value_study as C
import honest_odds_study as O

YEARS = (2009, 2010, 2011, 2012)
VET_LEAN = 17.1 / 19.8


def parts_fix3(S, N, pre):
    p2 = O.version_parts(S, N, pre, 'Fix 2')
    p1 = O.version_parts(S, N, pre, 'Fix 1')
    kind = S.kind.values[pre['test']]
    out = []
    for (nn, w, _), (_, _, r1), k in zip(p2, p1, kind):
        out.append((nn, w, r1 if k == 'V' else np.ones(len(nn))))
    return out


def prepare(S, N):
    pre = O.comps(S, YEARS)
    masks = O.masks_for(S, pre)
    V = {}
    for name, parts in (('Fix 2', O.version_parts(S, N, pre, 'Fix 2')), ('Fix 3', parts_fix3(S, N, pre))):
        P, E = O.predictions(S, parts)
        sims, edges = O.sim_limits(S, parts, P, E, masks)
        V[name] = dict(parts=parts, P=P, E=E, sims=sims, edges=edges, pad=O.pad(S, parts))
    return pre, masks, V


def decide(pre, masks, V, yP, yE, clusters, n_perm=C.N_PERM, seed=7):
    h3, ch3 = O.judge(V['Fix 3']['P'], V['Fix 3']['E'], yP, yE, masks, V['Fix 3']['sims'], V['Fix 3']['edges'])
    h2, ch2 = O.judge(V['Fix 2']['P'], V['Fix 2']['E'], yP, yE, masks, V['Fix 2']['sims'], V['Fix 2']['edges'])
    lift, p = C.perm_test(yP, V['Fix 3']['P'], V['Fix 2']['P'], clusters, n_perm, seed)
    return {'fix3_honest': h3, 'fix2_honest': h2, 'brier_fix2': O.brier(V['Fix 2']['P'], yP),
            'brier_fix3': O.brier(V['Fix 3']['P'], yP), 'lift': lift, 'p': p,
            'switch': bool(h3 and lift > 0 and p < 0.05), 'checks_fix2': ch2, 'checks_fix3': ch3}


def draw(rng, v, vet_scale=None, is_vet=None):
    P = v['P'] if vet_scale is None else np.where(is_vet, v['P'] * vet_scale, v['P'])
    yP = (rng.random(len(P)) < P).astype(float)
    CW, CNT, R = v['pad']
    c = O.draw_counts(rng, CW, CNT, R)
    yE = c if vet_scale is None else np.where(is_vet, rng.binomial(c.astype(int), vet_scale), c).astype(float)
    return yP, yE


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nflverse', required=True); ap.add_argument('--rosters', required=True)
    ap.add_argument('--size-check', action='store_true'); ap.add_argument('--runs', type=int, default=200)
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    t0 = time.time()
    S, N, _ = O.setup(a.nflverse, a.rosters)
    pre, masks, V = prepare(S, N)
    T = pre['test']; cl = S.key.values[T]; is_vet = S.kind.values[T] == 'V'
    head = {'rows': int(len(T)), 'veterans': int(is_vet.sum()), 'rookies': int((~is_vet).sum()),
            'players': int(len(set(cl))),
            'mean_P_vets': {k: float(V[k]['P'][is_vet].mean()) for k in V}}
    if a.size_check:
        rng = np.random.default_rng(99)
        w1 = [decide(pre, masks, V, *draw(rng, V['Fix 3']), cl, 2000, i)['switch'] for i in range(a.runs)]
        w2 = [decide(pre, masks, V, *draw(rng, V['Fix 2']), cl, 2000, i) for i in range(a.runs)]
        w3 = [O.judge(V['Fix 2']['P'], V['Fix 2']['E'], *draw(rng, V['Fix 2'], VET_LEAN, is_vet), masks,
                      V['Fix 2']['sims'], V['Fix 2']['edges'])[0] for _ in range(a.runs)]
        out = dict(head, runs=a.runs,
                   world1_switch_rate=float(np.mean(w1)),
                   world2_false_switch_rate=float(np.mean([d['switch'] for d in w2])),
                   world2_fix2_judged_honest=float(np.mean([d['fix2_honest'] for d in w2])),
                   world3_lean_caught=float(1 - np.mean(w3)),
                   note='size-check permutation tests use 2,000 shuffles for speed; the real run uses 10,000')
        out['QA_powered'] = out['world1_switch_rate'] >= 0.80
        out['QB_powered'] = out['world3_lean_caught'] >= 0.80
        path = a.out or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out', 'honest_odds_v3_size.json')
    else:
        # Q-A was underpowered in the size check (amendment A2): ONLY the Fix 2 re-check (Q-B) runs.
        yP = S.any_start.values[T].astype(float); yE = S.n_start.values[T].astype(float)
        v = V['Fix 2']
        honest, checks = O.judge(v['P'], v['E'], yP, yE, masks, v['sims'], v['edges'])
        d = {'QB_fix2_honest': honest, 'checks_fix2': checks, 'brier_fix2': O.brier(v['P'], yP)}
        out = dict(head, result=d,
                   said_vs_happened={'Fix 2': {g: {'said': float(v['P'][m].mean()), 'happened': float(yP[m].mean())}
                                               for g, m in (('V', is_vet), ('R0', ~is_vet))}})
        path = a.out or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out', 'honest_odds_v3_results.json')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(out, open(path, 'w'), indent=1, default=float)
    print(json.dumps({k: v for k, v in out.items() if k != 'result'}, indent=1, default=float))
    if 'result' in out:
        r = out['result']; print({'QB_fix2_honest': r['QB_fix2_honest'], 'brier_fix2': r['brier_fix2']}, out['said_vs_happened'])
    print(round(time.time() - t0), 's')


if __name__ == '__main__':
    main()
