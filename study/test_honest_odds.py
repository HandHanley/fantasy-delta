#!/usr/bin/env python3
"""
CRASH TESTS for honest_odds_study.py — docs/PREREG-honest-odds.md §6.

On the FRESH set (t = 2021, 2022), using the As-is odds and synthetic outcomes only (no real outcome is
compared with any odds here):
  1. HONEST WORLD     outcomes drawn from As-is's own comparables. The A6 rule must call it honest
                      in >= 80% of 200 runs (how often the check wrongly cries foul).
  2. DISHONEST WORLD  the 1 Nov gaps planted: veterans' odds really 0.835 of what's said, rookies'
                      1.118. The rule must call As-is dishonest in >= 80% of 200 runs, else two fresh
                      seasons are too few.
  3. LEAKS            asserted inside the study code (pools <= t-3, nobody in his own pool).

Usage: python test_honest_odds.py --nflverse DIR --rosters DIR [--runs 200]
"""
import argparse, json, os, time
import numpy as np
import honest_odds_study as O

VET_SCALE, ROOKIE_SCALE = 20.2 / 24.2, 23.7 / 21.2


def dishonest_draw(rng, P, E, CW, CNT, R, is_vet):
    s = np.where(is_vet, VET_SCALE, ROOKIE_SCALE)
    yp = (rng.random(len(P)) < np.clip(P * s, 0, 1)).astype(float)
    c = O.draw_counts(rng, CW, CNT, R)
    ye = np.where(is_vet, rng.binomial(c.astype(int), VET_SCALE), 0.0)
    # rookies: add starter seasons among the empty ones so the expected count scales by ROOKIE_SCALE
    room = np.maximum(0, O.H - c)
    q = np.clip((ROOKIE_SCALE - 1) * E / np.maximum(room, 1e-9), 0, 1)
    ye = np.where(is_vet, ye, c + rng.binomial(room.astype(int), np.where(room > 0, q, 0)))
    return yp, ye


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nflverse', required=True); ap.add_argument('--rosters', required=True)
    ap.add_argument('--runs', type=int, default=200)
    ap.add_argument('--out', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out',
                                                 'honest_odds_crash.json'))
    a = ap.parse_args()
    t0 = time.time()
    S, N, cnt = O.setup(a.nflverse, a.rosters)
    pre = O.comps(S, O.FRESH)
    masks = O.masks_for(S, pre)
    parts = O.version_parts(S, N, pre, 'As-is')
    P, E = O.predictions(S, parts)
    sims, edges = O.sim_limits(S, parts, P, E, masks)
    CW, CNT, R = O.pad(S, parts)
    is_vet = S.kind.values[pre['test']] == 'V'
    rng = np.random.default_rng(42)
    honest_ok, caught = 0, 0
    fails = {}
    for _ in range(a.runs):
        yp = (rng.random(len(P)) < P).astype(float); ye = O.draw_counts(rng, CW, CNT, R)
        ok, ch = O.judge(P, E, yp, ye, masks, sims, edges)
        honest_ok += ok
        for k, v in ch.items():
            if not v['honest']: fails[k] = fails.get(k, 0) + 1
    caught_by = {}
    for _ in range(a.runs):
        yp, ye = dishonest_draw(rng, P, E, CW, CNT, R, is_vet)
        ok, ch = O.judge(P, E, yp, ye, masks, sims, edges)
        caught += (not ok)
        if not ch['overall P3']['honest']: caught_by['overall P3'] = caught_by.get('overall P3', 0) + 1
        if not ch['overall E3']['honest']: caught_by['overall E3'] = caught_by.get('overall E3', 0) + 1
    out = {'fresh_rows': int(len(P)), 'runs': a.runs,
           'honest_world_judged_honest': honest_ok / a.runs, 'honest_world_false_alarms_by_check': fails,
           'dishonest_world_caught': caught / a.runs, 'dishonest_caught_by_overall_check': caught_by,
           'powered': bool(honest_ok / a.runs >= 0.80 and caught / a.runs >= 0.80)}
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(out, open(a.out, 'w'), indent=1)
    print(json.dumps(out, indent=1), round(time.time() - t0), 's')


if __name__ == '__main__':
    main()
