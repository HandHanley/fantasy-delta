#!/usr/bin/env python3
"""
DELTA — CONTRACT SECURITY: DOES A CONTRACT YEAR AT THE END OF A MULTI-YEAR DEAL COST LESS THAN ONE ON A ONE-YEAR DEAL?
Implements docs/PREREG-contract-length.md; where they disagree, the pre-registration wins.

Same rows, base value, outcome, opportunity and resampling as ovs_contract_security.py (its §1-§2). The contract-year
group (0) is split by the length of the deal in force at kickoff: ONE-YEAR (the deal covered one season: one-year
veteran deals, tags, tenders, exercised options, practice-squad deals) vs MULTI-YEAR (it covered two or more seasons).

    python ovs_contract_length.py --nflverse D --rosters D --week1 FILE --schedules FILE (--labels | --crash | --run)
"""
import argparse, json, os
import numpy as np, pandas as pd
import comps_value_study as C
import ovs_era as E
import ovs_offseason as O
import ovs_second_contract as SC
import ovs_contract_security as CS

OUT = CS.OUT
N_BOOT, SEED, GUARD, LEAN_RUNS = 2000, 2026, -0.005, 200
CURRENT = {1: 0.9547539143952655, 2: 1.0781335965973162}      # the adopted layer's other two groups, unchanged


def deal_years(c):
    y = c.get('years')
    if y not in (None, ''): return int(y)
    return int(c['end']) - int(c['first']) + 1


def split_labels(S, M, L, schedules, nflverse):
    """For contract-year rows: 'one' (deal covered 1 season) or 'multi' (2+). Contracts only."""
    P = json.load(open(CS.HIST))['players']
    dp = pd.read_csv(os.path.join(nflverse, 'draft_picks.csv'), low_memory=False).dropna(subset=['gsis_id'])
    dp = dp.sort_values(['season', 'pick']).drop_duplicates('gsis_id'); dyear = {g: int(s) for g, s in zip(dp.gsis_id, dp.season)}
    G = pd.read_csv(schedules, low_memory=False); G = G[G.game_type == 'REG']; kick = G.groupby('season').gameday.min().to_dict()
    out = []
    for r, grp, ts in zip(M, L.group.values, L.team_signed.values):
        if not ts or grp != 0: out.append(None); continue
        pid, n = S.key.values[r], int(S.t.values[r]) + 1
        c = CS.status(pid, n, kick[n], P, dyear)
        out.append('multi' if deal_years(c) >= 2 else 'one')
    return np.array(out, dtype=object)


def rel(B, y, v, mask_g, mask_all):
    return (B.sums(y, mask_g) / np.maximum(B.sums(v, mask_g), 1e-9)) / (B.sums(y, mask_all) / B.sums(v, mask_all))


def rel_pos(B, y, v, mask_g, pos):
    """Opportunity ratio per position (units differ), combined by row counts, as CS.ratios with pos."""
    num = 0; den = 0
    for p in np.unique(pos):
        mp = pos == p; w = B.sums(np.ones(len(y)), mp & mask_g)
        num = num + w * rel(B, y, v, mp & mask_g, mp); den = den + w
    return num / np.maximum(den, 1e-9)


def measure(pid, pos, y, v, o, ohat, sub, rng, n_boot=N_BOOT, opp=True):
    """sub: 'one' / 'multi' / 'g1' / 'g2' per decided row."""
    B = CS.Boot(pid, n_boot, rng); allm = np.ones(len(y), bool)
    r = {g: rel(B, y, v, sub == g, allm) for g in ('one', 'multi', 'g1', 'g2')}
    res = {'points': {g: CS.summary(r[g]) for g in r}, 'points_gap': CS.summary(r['multi'] - r['one'])}
    if opp:
        ro = {g: rel_pos(B, o, ohat, sub == g, pos) for g in ('one', 'multi')}
        res['opportunity'] = {g: CS.summary(ro[g]) for g in ro}; res['opportunity_gap'] = CS.summary(ro['multi'] - ro['one'])
    return res


def shuffle_cy(sub, pos, t, rng):
    """One-year / multi-year labels shuffled among contract-year rows of the same position and season."""
    s2 = sub.copy()
    for key in set(zip(pos, t)):
        m = np.where((pos == key[0]) & (t == key[1]) & np.isin(sub, ['one', 'multi']))[0]
        s2[m] = sub[rng.permutation(m)]
    return s2


def lean(pid, pos, t, y, v, o, ohat, sub, rng, n=LEAN_RUNS):
    B0 = CS.Boot(pid, 0, rng); allm = np.ones(len(y), bool); pg = []; og = []
    for _ in range(n):
        s2 = shuffle_cy(sub, pos, t, rng)
        pg.append(float((rel(B0, y, v, s2 == 'multi', allm) - rel(B0, y, v, s2 == 'one', allm))[0]))
        if o is not None:
            og.append(float((rel_pos(B0, o, ohat, s2 == 'multi', pos) - rel_pos(B0, o, ohat, s2 == 'one', pos))[0]))
    return float(np.mean(pg)), (float(np.mean(og)) if og else None)


def correct(s, l):
    s = dict(s); s['lean'] = l; s['estimate'] -= l
    s['range_95'] = [x - l for x in s['range_95']]; s['range_90'] = [x - l for x in s['range_90']]
    s['excludes_zero_95'] = bool(s['range_95'][0] > 0 or s['range_95'][1] < 0)
    return s


def no_harm(t, y, v, sub):
    """Leave-season-out (and the two either side) raw ratios: the 4-group split vs today's 3 groups. Lift >= -0.5%."""
    def fit(groups_of):
        new = v.copy()
        for s in np.unique(t):
            learn = np.abs(t - s) > CS.BUFFER; tot = y[learn].sum() / v[learn].sum()
            for g in np.unique(groups_of):
                m = learn & (groups_of == g)
                if m.sum() == 0: continue
                sel = (t == s) & (groups_of == g)
                new[sel] = v[sel] * (y[m].sum() / v[m].sum()) / tot
        return new
    three = np.where(np.isin(sub, ['one', 'multi']), 'g0', sub)
    a, b = fit(three), fit(sub)
    return float(1 - C.rmse(b, y) / C.rmse(a, y))


def main():
    ap = argparse.ArgumentParser()
    for k in ('nflverse', 'rosters', 'week1', 'schedules'): ap.add_argument('--' + k, required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--labels', action='store_true'); g.add_argument('--crash', action='store_true'); g.add_argument('--run', action='store_true')
    ap.add_argument('--runs', type=int, default=200)
    a = ap.parse_args()
    st, S, pre, nn2, W2, nn3, W3, counts = O.setup(a.nflverse, a.rosters, a.week1)
    Rv = pd.read_csv(CS.ROWS); Rv = Rv[Rv.relevant & (Rv.season >= E.TEST[0]) & (Rv.season <= E.TEST[1])]
    keep = set(zip(Rv.gsis_id, Rv.season.astype(int)))
    M = np.array([i for i in range(len(S)) if S.kind.values[i] == 'V' and S.complete.values[i]
                  and (S.key.values[i], int(S.t.values[i])) in keep], int)
    L = CS.labels(S, M, a.schedules, a.week1, a.nflverse)
    old = pd.read_csv(os.path.join(OUT, 'contract_security_labels.csv'))             # must match the adopted study's labels
    assert len(old) == len(L) and (old.group.astype(str).values == L.group.astype(str).values).all()
    split = split_labels(S, M, L, a.schedules, a.nflverse)
    dec = L.team_signed.values & L.group.isin(CS.GROUPS).values
    sub = np.where(L.group.values == 1, 'g1', np.where(L.group.values == 2, 'g2', split)).astype(object)[dec]
    pos = S.pos.values[M][dec]
    info = {'decided_rows': int(dec.sum()), 'by_subgroup': pd.Series(sub).value_counts().to_dict(),
            'contract_year_by_position': pd.crosstab(pos[np.isin(sub, ['one', 'multi'])], sub[np.isin(sub, ['one', 'multi'])]).to_dict()}
    print(json.dumps(info, indent=1, default=int), flush=True)
    if a.labels:
        json.dump(info, open(os.path.join(OUT, 'ovs_contract_length_counts.json'), 'w'), indent=1, default=int); return
    rows = M[dec]
    rows_v, nn_, W_ = SC.base_value(S, rows); assert len(rows_v) == len(rows)
    y = S.FV.values.astype(float); v = E.preds(nn_, W_, y); yd = y[rows]
    pid = S.key.values[rows]; t = S.t.values[rows].astype(int)
    rng = np.random.default_rng(SEED)
    if a.crash:
        res = {'decided_rows': int(len(rows)), 'runs': a.runs}
        for gap in (0.0, 0.25, 0.15):
            hit = 0; est = []
            for _ in range(a.runs):
                sh = shuffle_cy(sub, pos, t, rng)                                    # removes any real link
                ys = yd * np.where(sh == 'one', 1 - gap / 2, np.where(sh == 'multi', 1 + gap / 2, 1.0))
                r = measure(pid, pos, ys, v, None, None, sh, rng, n_boot=1000, opp=False)['points_gap']
                l, _ = lean(pid, pos, t, ys, v, None, None, sh, rng, n=50)
                r = correct(r, l); hit += r['excludes_zero_95']; est.append(r['estimate'])
            res[f'planted_{gap}'] = {'excluded_zero': int(hit), 'mean_estimate': float(np.mean(est))}
            print(gap, res[f'planted_{gap}'], flush=True)
        res['pass'] = bool(res['planted_0.0']['excluded_zero'] <= 15 and res['planted_0.25']['excluded_zero'] >= 0.8 * a.runs)
        json.dump(res, open(os.path.join(OUT, 'ovs_contract_length_crash.json'), 'w'), indent=1)
        print('crash pass', res['pass']); return
    car, tgt, starts = CS.opportunity(a.nflverse, a.schedules)
    o_all = CS.opp_vector(S, car, tgt, starts); od = o_all[rows]; ohat = E.preds(nn_, W_, o_all)
    m = measure(pid, pos, yd, v, od, ohat, sub, rng)
    lp, lo = lean(pid, pos, t, yd, v, od, ohat, sub, rng)
    m['points_gap'] = correct(m['points_gap'], lp); m['opportunity_gap'] = correct(m['opportunity_gap'], lo)
    harm = no_harm(t, yd, v, sub)
    use = m['points_gap']['excludes_zero_95'] and np.sign(m['opportunity_gap']['estimate']) == np.sign(m['points_gap']['estimate']) and harm >= GUARD
    layer = None
    if use:
        layer = {'contract_year_one_year_deal': 1 + CS.shrink(m['points']['one']['estimate'] - 1, m['points']['one']['se']),
                 'contract_year_multi_year_deal': 1 + CS.shrink(m['points']['multi']['estimate'] - 1, m['points']['multi']['se']),
                 'one_year_left': CURRENT[1], 'two_plus_left': CURRENT[2]}
    res = {'prereg': 'docs/PREREG-contract-length.md', 'info': info, 'measured': m, 'no_harm_lift': harm,
           'split_used': bool(use), 'layer': layer}
    by = {}
    for p in np.unique(pos):
        mp = pos == p
        if np.isin(sub[mp], ['multi']).sum() >= 5:
            by[p] = measure(pid[mp], pos[mp], yd[mp], v[mp], od[mp], ohat[mp], sub[mp], rng, n_boot=1000)['points_gap']
    res['reported_by_position'] = by
    json.dump(res, open(os.path.join(OUT, 'ovs_contract_length_results.json'), 'w'), indent=1, default=float)
    print(json.dumps({k: res[k] for k in ('no_harm_lift', 'split_used', 'layer')}, indent=1, default=float))
    print(json.dumps({'points': {g: m['points'][g]['estimate'] for g in m['points']}, 'points_gap': m['points_gap'], 'opportunity_gap': m['opportunity_gap']}, indent=1, default=float))


if __name__ == '__main__':
    main()
