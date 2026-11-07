#!/usr/bin/env python3
"""In-season Historical Comps with a lean correction — pre-registered in docs/PREREG-in-season-comps-v2.md.

Same rows, matching and weights as comps_in_season.py (locked d03efe3). New: a time-safe correction for the odds'
known high lean. For a test row in season Y, the factor
    k = (starter seasons that happened) / (starter seasons the odds expected)
is measured on earlier in-season rows (seasons 2006 .. Y-4, whose three-year windows had closed by week W of Y),
separately for this season's rookies (year 1) and everyone else (year 2+). Each of the row's comparables then counts
its starter seasons thinned by r = min(1, k): the odds can be pulled down, never pushed up. Nothing else changes.
Honesty is judged on 2013-2020 (never judged for in-season odds). 2021-22 and 2009-12 reported only.

Usage: python3 comps_in_season_v2.py --nflverse D --rosters D --weekly D (--crash | --run)
"""
import argparse, json, os
import numpy as np
import comps_in_season as A, honest_odds_study as O

WEEKS = (5, 9, 13)
TEST = tuple(range(2013, 2021))
REPORT = {'reported_2021_22': (2021, 2022), 'reported_2009_12': (2009, 2010, 2011, 2012)}
K_FROM = 2006                         # first season with a pool (2002 .. t-4)
OUT = A.OUT


def matches(Sin, Sb, years):
    """Comparables for every row we may need (k sources and tests), both versions. Outcome-free."""
    pi, parts_i, _, _ = A.odds(Sin, years)
    pb, parts_b, _, _ = A.odds(Sb, years)
    common = np.intersect1d(pi['test'], pb['test'])
    mi = {r: i for i, r in enumerate(pi['test'])}; mb = {r: i for i, r in enumerate(pb['test'])}
    return common, {r: parts_i[mi[r]] for r in common}, {r: parts_b[mb[r]] for r in common}


def base_odds(S, M):
    """Unadjusted odds from the comparables in M and the outcomes in S."""
    common, parts, parts_b = M
    _, E = O.predictions(S, [parts[r] for r in common])
    Pb, _ = O.predictions(S, [parts_b[r] for r in common])
    return common, parts, dict(zip(common, E)), dict(zip(common, Pb))


def factors(S, rows, E, test_years):
    """k per (test season, group): only rows from seasons K_FROM .. Y-4. Groups: year 1, year 2+."""
    t = S.t.values; cy = S.cy.values; ns = S.n_start.values
    k = {}
    for Y in test_years:
        for grp, m in (('year1', lambda c: c == 1), ('year2plus', lambda c: c >= 2)):
            src = [r for r in rows if K_FROM <= t[r] <= Y - 4 and m(cy[r])]
            assert all(t[r] <= Y - 4 for r in src), 'k leak'
            exp = sum(E[r] for r in src); hap = float(ns[src].sum())
            k[(Y, grp)] = {'k': hap / exp if exp > 0 else 1.0, 'rows': len(src)}
    return k


def adjusted(S, rows, parts, k):
    t = S.t.values; cy = S.cy.values
    out = []
    for r in rows:
        nn, w, _ = parts[r]
        kk = k[(int(t[r]), 'year1' if cy[r] == 1 else 'year2plus')]['k']
        out.append((nn, w, np.full(len(nn), min(1.0, kk))))
    return out


def predictions_thinned(S, parts):
    """Each comparable's starter seasons kept with chance r each (binomial thinning), so
    chance of at least one = 1 - (1 - r)^count and expected count = r x count. (O.predictions thins the
    at-least-one flag itself, which over-corrects players with two or three starter seasons: caught by the
    lean-world crash test before lock, amendment A1.)"""
    cnt = S.n_start.values.astype(float)
    P = np.array([(w * (1 - (1 - r) ** cnt[nn])).sum() for nn, w, r in parts])
    E = np.array([(w * cnt[nn] * r).sum() for nn, w, r in parts])
    return np.minimum(P, 1.0), E


def judge_years(Sin, M, years, n_sim=O.N_SIM, outcomes=None):
    if outcomes is not None:
        Sin = A.with_outcomes(Sin, outcomes)
    common, parts, E, Pb = base_odds(Sin, M)
    k = factors(Sin, common, E, years)
    test = np.array([r for r in common if Sin.t.values[r] in years])
    padj = adjusted(Sin, test, parts, k)
    P, Eadj = predictions_thinned(Sin, padj)
    y = Sin.any_start.values[test].astype(float); yE = Sin.n_start.values[test].astype(float)
    masks = O.masks_for(Sin, {'test': test})
    sims, edges = O.sim_limits(Sin, padj, P, Eadj, masks, n_sim)
    honest, checks = O.judge(P, Eadj, y, yE, masks, sims, edges)
    pb = np.array([Pb[r] for r in test])
    li, lb = (P - y) ** 2, (pb - y) ** 2
    res = {'n': int(len(test)), 'players': int(len(set(Sin.key.values[test]))), 'honest': bool(honest),
           'brier_in_adj': float(li.mean()), 'brier_base': float(lb.mean()),
           'guard_ok': bool(li.mean() <= A.BRIER_GUARD * lb.mean()),
           'p_better': A.perm_better(li, lb, Sin.key.values[test]),
           'said_vs_happened': {'in_season_adj': float(P.mean()), 'baseline': float(pb.mean()), 'happened': float(y.mean())},
           'k': {f'{Y} {g}': v for (Y, g), v in k.items()}, 'checks': checks}
    res['passes'] = bool(res['honest'] and res['guard_ok'])
    return res


# ═════════════════════════════════════════════════════════════════════════════
# CRASH TESTS (before lock; synthetic outcomes only)
# ═════════════════════════════════════════════════════════════════════════════
def synth(Sin, common, parts, scale, rng):
    """Outcomes drawn from each row's own comparables, starter seasons thinned by `scale` (1 = the odds are honest
    as they stand; 0.84 = the odds run high by the size seen on 7 Nov). Rows outside `common` keep real outcomes,
    but they are never a test row or a k source."""
    ns = Sin.n_start.values.copy().astype(int)
    # oldest first, each row drawn from its comparables' (already drawn) outcomes: every row's odds then run
    # high by exactly 1/scale against its own truth, the way a real lean would look
    for r in sorted(common, key=lambda r: Sin.t.values[r]):
        nn, w, _ = parts[r]
        j = rng.choice(len(nn), p=w / w.sum())
        ns[r] = rng.binomial(ns[nn[j]], scale)
    return ns


def crash(Sin, Sb, runs=20, n_sim=500):
    rng = np.random.default_rng(7)
    M = matches(Sin, Sb, tuple(range(K_FROM, max(TEST) + 1)))
    common, parts, _ = M
    out = {}
    # A2: 40 runs per world (20 can't separate an 80% pass rate from the A6 rule's own ~85%)
    for name, scale in (('honest_world', 1.0), ('lean_world', 0.84)):
        passes, ks = 0, []
        for _ in range(2 * runs):
            ns = synth(Sin, common, parts, scale, rng)
            r = judge_years(Sin, M, TEST, n_sim=n_sim, outcomes=ns)
            passes += r['honest']; ks.append(r['k'][f'{TEST[-1]} year2plus']['k'])
        out[name] = {'honest_passes': int(passes), 'runs': 2 * runs, 'k_2020_year2plus_mean': float(np.mean(ks))}
    # an uncorrected forecaster in the lean world must be caught: same draw, k forced to 1
    fails = 0
    for _ in range(runs):
        ns = synth(Sin, common, parts, 0.84, rng)
        S2 = A.with_outcomes(Sin, ns)
        test = np.array([r for r in common if S2.t.values[r] in TEST])
        P, Ee = O.predictions(S2, [parts[r] for r in test])
        masks = O.masks_for(S2, {'test': test})
        sims, edges = O.sim_limits(S2, [parts[r] for r in test], P, Ee, masks, n_sim)
        h, _ = O.judge(P, Ee, S2.any_start.values[test].astype(float), S2.n_start.values[test].astype(float), masks, sims, edges)
        fails += not h
    out['uncorrected_in_lean_world_caught'] = int(fails)
    out['ok'] = bool(out['honest_world']['honest_passes'] >= 32 and out['lean_world']['honest_passes'] >= 32 and fails >= 16)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nflverse', required=True); ap.add_argument('--rosters', required=True); ap.add_argument('--weekly', required=True)
    g = ap.add_mutually_exclusive_group(required=True); g.add_argument('--crash', action='store_true'); g.add_argument('--run', action='store_true')
    a = ap.parse_args()
    st, dp, pl, W = A.load(a.nflverse, a.rosters, a.weekly)
    res = {'prereg': 'docs/PREREG-in-season-comps-v2.md', 'points_check': A.points_check(st, W)}
    if a.crash:
        Sin, Sb, _ = A.snapshots(st, dp, pl, W, 9, range(A.FIRST_Y, max(TEST) + 1))
        res['crash_week_9'] = crash(Sin, Sb)
        json.dump(res, open(os.path.join(OUT, 'comps_in_season_v2_crash.json'), 'w'), indent=1)
        print(json.dumps(res['crash_week_9'], indent=1)); return
    res['weeks'] = {}
    for w in WEEKS:
        Sin, Sb, sk = A.snapshots(st, dp, pl, W, w, range(A.FIRST_Y, 2023))
        M = matches(Sin, Sb, tuple(range(K_FROM, 2023)))
        r = {'test_2013_20': judge_years(Sin, M, TEST)}
        for lab, yrs in REPORT.items():
            r[lab] = judge_years(Sin, M, yrs)
        res['weeks'][str(w)] = r
        f = r['test_2013_20']
        print(w, {k: f[k] for k in ('n', 'brier_in_adj', 'brier_base', 'p_better', 'honest', 'guard_ok', 'passes')}, f['said_vs_happened'])
    res['decision'] = 'in-season (corrected) from week 5' if all(res['weeks'][str(w)]['test_2013_20']['passes'] for w in WEEKS) \
        else 'keep season-end matching all year'
    json.dump(res, open(os.path.join(OUT, 'comps_in_season_v2_results.json'), 'w'), indent=1, default=str)
    print('DECISION:', res['decision'])


if __name__ == '__main__':
    main()
