#!/usr/bin/env python3
"""
DELTA — OWN VALUE SCALE: CONTRACT-BUMP POWER CHECK (made-up contracts; no contract data). docs/POWER-contract-bump.md.

Question: with every veteran from 2013-2022 labelled by contract years left, how big a real bump could the usual test
(>= 2% better on veteran rows, paired permutation p < 0.05) detect? Contracts are simulated per player: a deal length,
counting down a year per season and renewing. Groups at each snapshot: expiring (0 left after the coming season),
one more year, two or more. A bump b is planted on outcomes: expiring x (1 - b), one more x 1, two or more x (1 + b).
The method is the second-contract study's: scale each veteran's adopted preseason value by his group's ratio of outcome
to value over seasons whose results are in (t' <= t - 3).

    python ovs_contract_power.py --nflverse D --rosters D --week1 FILE [--sims 40]
"""
import argparse, json, os
import numpy as np, pandas as pd
import comps_value_study as C
import ovs_era as E
import ovs_offseason as O
import ovs_second_contract as SC

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
BUMPS = (0.03, 0.05, 0.075, 0.10, 0.15, 0.20)
FIRST_LEFT = ([0, 1, 2, 3, 4], [0.3, 0.25, 0.2, 0.15, 0.1])          # years left when a player is first seen
NEW_DEAL = ([1, 2, 3, 4, 5], [0.25, 0.2, 0.25, 0.2, 0.1])            # length of each new deal


def simulate_labels(S, rng):
    lab = np.full(len(S), -1)
    df = pd.DataFrame({'k': S.key.values, 't': S.t.values.astype(int)}).reset_index()
    for _, g in df.sort_values('t').groupby('k'):
        left, prev = None, None
        for i, t in zip(g['index'].values, g.t.values):
            if left is None: left = rng.choice(*FIRST_LEFT[:1], p=FIRST_LEFT[1])
            else:
                left -= (t - prev)
                while left < 0: left += rng.choice(NEW_DEAL[0], p=NEW_DEAL[1])
            lab[i] = min(left, 2); prev = t
    return lab                                                            # 0 expiring, 1 one more, 2 two or more


def main():
    ap = argparse.ArgumentParser()
    for k in ('nflverse', 'rosters', 'week1'): ap.add_argument('--' + k, required=True)
    ap.add_argument('--sims', type=int, default=40)
    ap.add_argument('--precision', action='store_true')
    ap.add_argument('--bumps', default='')
    a = ap.parse_args()
    st, S, pre, nn2, W2, nn3, W3, counts = O.setup(a.nflverse, a.rosters, a.week1)
    T = pre['test']; y = S.FV.values.astype(float)
    vet = S.kind.values == 'V'
    H = np.array([r for r in np.where(vet)[0] if E.HORIZON + C.SNAP_FIRST <= S.t.values[r] <= E.TEST[1] - E.HORIZON
                  and S.complete.values[r]], int)
    allrows = np.array(sorted(set(T.tolist()) | set(H.tolist())), int)
    allrows, nn_, W_ = SC.base_value(S, allrows)                          # adopted preseason value (games out)
    ix = {int(r): j for j, r in enumerate(allrows)}
    H = np.array([r for r in H if int(r) in ix], int)
    Tj = np.array([ix[int(r)] for r in T]); Hj = np.array([ix[int(r)] for r in H])
    mask = vet[T]; tT = S.t.values[T]; tH = S.t.values[H]
    rng = np.random.default_rng(2026); res = {'decided_rows': int(mask.sum()), 'history_rows': int(len(H)), 'sims': a.sims}
    for b in ([float(x) for x in a.bumps.split(',')] if a.bumps else BUMPS) if a.bumps != 'none' else ():
        mult = np.array([1 - b, 1.0, 1 + b]); passed = 0; lifts = []
        for s in range(a.sims):
            lab = simulate_labels(S, rng)
            ys = y * np.where(lab >= 0, mult[np.clip(lab, 0, 2)], 1.0)
            pa = E.preds(nn_, W_, ys); base = pa[Tj]; hb = pa[Hj]; hy = ys[H]; hl = lab[H]
            new = base.copy()
            for t in np.unique(tT[mask]):
                for g in (0, 1, 2):
                    m = (tH <= t - E.HORIZON) & (hl == g)
                    if m.sum() < SC.N_MIN or hb[m].sum() <= 0: continue
                    sel = mask & (tT == t) & (lab[T] == g)
                    new[sel] = base[sel] * hy[m].sum() / hb[m].sum()
            r = SC.q(S, T, new, base, ys[T], mask, 1000); passed += r['pass']; lifts.append(r['lift'])
        res[f'bump_{b}'] = {'passed': int(passed), 'power': passed / a.sims, 'median_lift': float(np.median(lifts))}
        print(b, res[f'bump_{b}'], flush=True)
    if a.precision:                                                       # how well all history pins the bump down
        prec = {}
        for b in (0.0, 0.05, 0.10):
            mult = np.array([1 - b, 1.0, 1 + b]); est = []
            for s in range(a.sims):
                lab = simulate_labels(S, rng)
                ys = y * np.where(lab >= 0, mult[np.clip(lab, 0, 2)], 1.0)
                pa = E.preds(nn_, W_, ys); hb = pa[Hj]; hy = ys[H]; hl = lab[H]
                r = [hy[hl == g].sum() / hb[hl == g].sum() for g in (0, 2)]
                est.append((r[1] - r[0]) / 2)                             # estimated bump, half the gap between the ends
            prec[str(b)] = {'mean_estimate': float(np.mean(est)), 'range_90': [float(np.quantile(est, 0.05)), float(np.quantile(est, 0.95))]}
            print('precision', b, prec[str(b)], flush=True)
        res['precision'] = prec
    json.dump(res, open(os.path.join(OUT, 'ovs_contract_power.json'), 'w'), indent=1, default=float)


if __name__ == '__main__':
    main()
