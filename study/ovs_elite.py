#!/usr/bin/env python3
"""
DELTA — OWN VALUE SCALE: DO WE SHORTCHANGE THE ELITE? (a measured size). docs/PREREG-ovs-elite.md.

Veteran preseason test rows 2013-2022. Within each position and season, rank by the adopted preseason value:
elite = ranks 1-3, next tier = ranks 4-24. Elite ratio = (sum FV3 / sum value, elite) / (same, next tier).
Q1 decides on TEs, Q2 on all positions pooled (row-weighted). Ranges: players resampled. Lean: outcome-to-value
ratios shuffled within position and season among ranks 1-24.

    python ovs_elite.py --nflverse D --rosters D --week1 FILE (--crash | --run [--dry])
"""
import argparse, json, os
import numpy as np, pandas as pd
import comps_value_study as C
import ovs_era as E
import ovs_offseason as O
import ovs_second_contract as SC
from ovs_contract_security import Boot, shrink

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, 'out')
POS = ('QB', 'RB', 'WR', 'TE')
TOP, TIER_END = 3, 24
N_BOOT, SEED, GUARD, BUFFER, LEAN_RUNS = 2000, 2026, -0.005, 2, 200


def ranks(v, pos, t):
    """Rank 1 = highest value within position and season."""
    r = np.zeros(len(v), int)
    for key in set(zip(pos, t)):
        m = np.where((pos == key[0]) & (t == key[1]))[0]
        r[m[np.argsort(-v[m], kind='stable')]] = np.arange(1, len(m) + 1)
    return r


def elite_ratio(B, y, v, pos, rk, top=TOP):
    """Per position (elite ratio, elite rows weight); pooled = row-weighted mean. Arrays over bootstraps."""
    out, num, den = {}, 0, 0
    for p in POS:
        e = (pos == p) & (rk <= top); n = (pos == p) & (rk > top) & (rk <= TIER_END)
        if e.sum() == 0: continue
        re = B.sums(y, e) / np.maximum(B.sums(v, e), 1e-9); rn = B.sums(y, n) / np.maximum(B.sums(v, n), 1e-9)
        out[p] = re / np.maximum(rn, 1e-9)
        w = B.sums(np.ones(len(y)), e); num = num + w * out[p]; den = den + w
    out['pooled'] = num / np.maximum(den, 1e-9)
    return out


def null_world(y, v, pos, t, rk, rng):
    """§2: outcome-to-value ratios shuffled within position and season among ranks 1-24; others unchanged."""
    ys = y.copy()
    for key in set(zip(pos, t)):
        m = np.where((pos == key[0]) & (t == key[1]) & (rk <= TIER_END))[0]
        r = y[m] / v[m]; ys[m] = v[m] * r[rng.permutation(len(m))]
    return ys


def summary(x, null=1.0):
    est, b = float(x[0]), x[1:]
    lo95, hi95 = np.quantile(b, [.025, .975]); lo90, hi90 = np.quantile(b, [.05, .95])
    return {'estimate': est, 'range_90': [float(lo90), float(hi90)], 'range_95': [float(lo95), float(hi95)],
            'se': float(b.std(ddof=1)), 'excludes_null_95': bool(lo95 > null or hi95 < null)}


def lean(pid, y, v, pos, t, rk, rng, top=TOP, n=LEAN_RUNS):
    B0 = Boot(pid, 0, rng); acc = {}
    for _ in range(n):
        for k, x in elite_ratio(B0, null_world(y, v, pos, t, rk, rng), v, pos, rk, top).items():
            acc.setdefault(k, []).append(float(x[0]) - 1.0)
    return {k: float(np.mean(x)) for k, x in acc.items()}


def measure(pid, y, v, pos, t, rk, rng, top=TOP, n_boot=N_BOOT):
    """Bootstrap summaries, then the lean subtracted from each estimate and both ends of its ranges."""
    B = Boot(pid, n_boot, rng)
    res = {k: summary(x) for k, x in elite_ratio(B, y, v, pos, rk, top).items()}
    for k, l in lean(pid, y, v, pos, t, rk, rng, top).items():
        d = res[k]; d['lean'] = l; d['estimate'] -= l
        d['range_90'] = [x - l for x in d['range_90']]; d['range_95'] = [x - l for x in d['range_95']]
        d['excludes_null_95'] = bool(d['range_95'][0] > 1 or d['range_95'][1] < 1)
    return res


def no_harm(y, v, pos, t, rk, which):
    """Each season's elite rows take the ratio learned without that season and the two either side (raw, unshrunk).
    Typical miss on ranks 1-24 of the positions in `which`, vs the base."""
    new = v.copy(); scope = np.isin(pos, which) & (rk <= TIER_END)
    for s in np.unique(t):
        learn = np.abs(t - s) > BUFFER
        for p in which:
            src = POS if len(which) > 1 else (p,)                                # pooled layer learns from all positions
            num = den = 0
            for q in src:
                e = learn & (pos == q) & (rk <= TOP); n = learn & (pos == q) & (rk > TOP) & (rk <= TIER_END)
                r = (y[e].sum() / v[e].sum()) / (y[n].sum() / v[n].sum()); num += e.sum() * r; den += e.sum()
            sel = (t == s) & (pos == p) & (rk <= TOP); new[sel] = v[sel] * num / den
    return float(1 - C.rmse(new[scope], y[scope]) / C.rmse(v[scope], y[scope]))


def staying_power(st):
    """Reported: top-3 finishers by season points; top 3 again next season, and in >= 2 of the next three."""
    pts = st.groupby(['player_id', 'season', 'position']).P.sum().reset_index()
    pts['rk'] = pts.groupby(['season', 'position']).P.rank(ascending=False, method='first')
    top = set(zip(pts[pts.rk <= 3].player_id, pts[pts.rk <= 3].season))
    out = {}
    for p in POS:
        g = pts[(pts.position == p) & (pts.rk <= 3) & pts.season.between(*E.TEST)]
        nxt = [(k, s + 1) in top for k, s in zip(g.player_id, g.season)]
        two = [sum((k, s + i) in top for i in (1, 2, 3)) >= 2 for k, s in zip(g.player_id, g.season)]
        out[p] = {'top3_finishes': int(len(g)), 'top3_next_season': float(np.mean(nxt)), 'top3_in_2_of_next_3': float(np.mean(two))}
    return out


def main():
    ap = argparse.ArgumentParser()
    for k in ('nflverse', 'rosters', 'week1'): ap.add_argument('--' + k, required=True)
    g = ap.add_mutually_exclusive_group(required=True); g.add_argument('--crash', action='store_true'); g.add_argument('--run', action='store_true')
    ap.add_argument('--dry', action='store_true'); ap.add_argument('--runs', type=int, default=200)
    a = ap.parse_args()
    st, S, pre, *_ = O.setup(a.nflverse, a.rosters, a.week1)
    test = np.asarray(pre['test'], int)
    M = test[(S.kind.values[test] == 'V') & S.complete.values[test].astype(bool)]
    rows, nn_, W_ = SC.base_value(S, M)
    y_all = S.FV.values.astype(float)
    rng = np.random.default_rng(SEED)
    if a.dry:                                                              # every outcome shuffled within position and season
        r7 = np.random.default_rng(7)
        for _, ix in pd.DataFrame({'p': S.pos.values, 't': S.t.values}).groupby(['p', 't']).groups.items():
            ix = np.asarray(ix); y_all[ix] = y_all[r7.permutation(ix)]
    v = E.preds(nn_, W_, y_all); y = y_all[rows]
    pid, pos, t = S.key.values[rows], S.pos.values[rows], S.t.values[rows].astype(int)
    rk = ranks(v, pos, t)
    info = {'test_rows': int(len(M)), 'valued_rows': int(len(rows)),
            'elite_rows': {p: int(((pos == p) & (rk <= TOP)).sum()) for p in POS},
            'tier_rows': {p: int(((pos == p) & (rk > TOP) & (rk <= TIER_END)).sum()) for p in POS}}
    print(json.dumps(info), flush=True)
    if a.crash:
        res = dict(info, runs=a.runs)
        for b in (0.0, 0.25, 0.15):
            hit = {'TE': 0, 'pooled': 0}; est = {'TE': [], 'pooled': []}
            for _ in range(a.runs):
                ys = null_world(y, v, pos, t, rk, rng); ys = np.where(rk <= TOP, ys * (1 + b), ys)
                r = measure(pid, ys, v, pos, t, rk, rng, n_boot=1000)
                for k in hit: hit[k] += r[k]['excludes_null_95']; est[k].append(r[k]['estimate'])
            res[f'planted_{b}'] = {k: {'excluded_one': int(hit[k]), 'mean_estimate': float(np.mean(est[k]))} for k in hit}
            print(b, res[f'planted_{b}'], flush=True)
        pl = res['planted_0.25']
        res['pass'] = {k: bool(res['planted_0.0'][k]['excluded_one'] <= 15 and pl[k]['excluded_one'] >= 0.8 * a.runs
                               and abs(pl[k]['mean_estimate'] - 1.25) <= 0.05) for k in ('TE', 'pooled')}
        json.dump(res, open(os.path.join(OUT, 'ovs_elite_crash.json'), 'w'), indent=1)
        print('crash pass', res['pass']); return
    res = dict(info, decided=measure(pid, y, v, pos, t, rk, rng))
    d = res['decided']
    res['no_harm'] = {'TE': no_harm(y, v, pos, t, rk, ('TE',)), 'pooled': no_harm(y, v, pos, t, rk, POS)}
    use = {k: d[k]['excludes_null_95'] and res['no_harm'][k] >= GUARD for k in ('TE', 'pooled')}
    res['layer'] = {k: (1 + shrink(d[k]['estimate'] - 1, d[k]['se']) if use[k] else None) for k in ('TE', 'pooled')}
    res['reported'] = {'top1': measure(pid, y, v, pos, t, rk, rng, top=1, n_boot=1000),
                       'top5': measure(pid, y, v, pos, t, rk, rng, top=5, n_boot=1000),
                       'staying_power': staying_power(st),
                       'te_elite_rows': [{'name': S.name.values[r], 'season': int(S.t.values[r]), 'rank': int(k),
                                          'value': round(float(vv), 1), 'delivered': round(float(yy), 1)}
                                         for r, k, vv, yy in zip(rows, rk, v, y) if S.pos.values[r] == 'TE' and k <= TOP]}
    json.dump(res, open(os.path.join(OUT, 'ovs_elite_' + ('dry' if a.dry else 'results') + '.json'), 'w'), indent=1, default=float)
    print(json.dumps({k: res[k] for k in ('no_harm', 'layer')}, default=float))
    for k in POS + ('pooled',):
        x = d[k]; print(k, round(x['estimate'], 3), [round(z, 3) for z in x['range_95']], x['excludes_null_95'])


if __name__ == '__main__':
    main()
