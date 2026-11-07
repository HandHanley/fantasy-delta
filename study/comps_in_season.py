#!/usr/bin/env python3
"""Historical Comps during the season — pre-registered in docs/PREREG-in-season-comps.md.

A player as of the end of week W of season Y, matched against past players at the same week W of their own season
(pool seasons <= Y - 4). Outcome: starter seasons in Y+1..Y+3 (window A, owner 7 Nov 2026). Two versions on the
SAME rows:
  in-season : this season so far counts as the newest season in the 3/2/1 points per game; games = games so far;
              this season's rookies are veterans in year 1 (production, games, age, draft slot)
  baseline  : this season ignored: 3/2/1 over the last three full seasons; games = last season's games;
              this season's rookies matched as at the draft (draft slot + age)
Age and year in the league are the same in both (they are time, not this season's play).
Everything else as locked: Version A matching (no draft slot from year 2), 30 matches, Fix 2 weights (half-life 8).

Usage:
  python3 comps_in_season.py --nflverse D --rosters D --weekly D --crash      # crash tests (before lock)
  python3 comps_in_season.py --nflverse D --rosters D --weekly D --run        # the one real run (after lock)
"""
import argparse, glob, json, os
import numpy as np, pandas as pd
import comps_value_study as C, honest_odds_study as O, comps_draft_drop as DD

WEEKS = (5, 9, 13)
FRESH = (2021, 2022)
OLD = (2009, 2010, 2011, 2012)
ALL = tuple(range(2005, 2023))
FIRST_Y = 2002                # needs Y-3 = 1999, the first weekly season
LAG = 4                       # pool season <= Y - 4: its Y+1..Y+3 window is complete when Y's is
BRIER_GUARD = 1.01
N_PERM = 10000
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')


# ═════════════════════════════════════════════════════════════════════════════
# DATA
# ═════════════════════════════════════════════════════════════════════════════
def load(nflverse, rosters, weekly_dir):
    st, dp, pl = C.load(nflverse, rosters)                     # season file: positions (A11/A12), outcomes
    cols = ['player_id', 'season', 'week', 'season_type', 'fantasy_points', 'fantasy_points_ppr',
            'receptions', 'attempts', 'carries', 'targets']
    W = pd.concat([pd.read_csv(f, usecols=cols, low_memory=False)
                   for f in sorted(glob.glob(os.path.join(weekly_dir, 'stats_player_week_*.csv')))])
    W = W[W.season_type == 'REG'].copy()
    W = W.join(st.set_index(['player_id', 'season']).position, on=['player_id', 'season'], how='inner')
    W['P'] = (W.fantasy_points.fillna(0) + W.fantasy_points_ppr.fillna(0)) / 2 \
        + np.where(W.position == 'TE', 0.5 * W.receptions.fillna(0), 0.0)
    # a game = a week with at least one pass, carry, target or catch (matches the season file's games 96.8%)
    W['g'] = (W[['attempts', 'carries', 'targets', 'receptions']].fillna(0).sum(axis=1) > 0).astype(int)
    W.loc[W.g == 0, 'P'] = 0.0
    return st, dp, pl, W


def points_check(st, W):
    """Pre-lock amendment A1: report, and stop only if the weekly file disagrees widely with the season file."""
    agg = W.groupby(['player_id', 'season']).agg(Pw=('P', 'sum'), Gw=('g', 'sum')).reset_index()
    m = st.merge(agg, on=['player_id', 'season'], how='left').fillna({'Pw': 0, 'Gw': 0})
    off5 = float(((m.P - m.Pw).abs() > 5).mean()); offg = float(((m.games - m.Gw).abs() > 1).mean())
    out = {'player_seasons': int(len(m)), 'points_off_by_more_than_5': off5, 'games_off_by_more_than_1': offg}
    assert off5 <= 0.05 and offg <= 0.05, f'weekly vs season file disagree too often: {out}'
    return out


def snapshots(st, dp, pl, W, week, seasons):
    """Two frames with identical rows: (in-season, baseline). Outcomes from the season file."""
    # season totals and through-week-W totals, from the weekly file (features use one source throughout)
    full = W.groupby(['player_id', 'season']).agg(P=('P', 'sum'), G=('g', 'sum'))
    upto = W[W.week <= week].groupby(['player_id', 'season']).agg(P=('P', 'sum'), G=('g', 'sum'))
    FP, FG = full.P.to_dict(), full.G.to_dict()
    UP, UG = upto.P.to_dict(), upto.G.to_dict()
    played = W[W.g == 1].groupby('player_id').season.agg(set).to_dict()

    # outcome lines: the season file, exactly as the other studies
    start, pts = {}, {(r.player_id, r.season): r.P for r in st.itertuples()}
    for (yr, ps), g in st.groupby(['season', 'position']):
        p = np.sort(g.P.values)[::-1]
        start[(yr, ps)] = p[C.STARTER_N[ps] - 1] if len(p) >= C.STARTER_N[ps] else 0.0
    last_data = int(st.season.max())
    spos = st.set_index(['player_id', 'season']).position.to_dict()

    dq = dp[dp.gsis_id.notna()].sort_values(['season', 'pick']).drop_duplicates('gsis_id')
    draft = {r.gsis_id: (int(r.season), int(r.pick), r.age) for r in dq.itertuples()}
    plx = pl.set_index('gsis_id')
    birth = plx.birth_date.dropna().to_dict()
    pl_draft = {g: (int(r.draft_year), int(r.draft_pick)) for g, r in plx.iterrows()
                if pd.notna(r.draft_year) and pd.notna(r.draft_pick)}
    pl_rookie = plx.rookie_season.dropna().astype(int).to_dict()
    names = st.drop_duplicates('player_id', keep='last').set_index('player_id').player_display_name.to_dict()

    def ppg(terms):
        num = den = 0.0
        for w, (pid, yr, P_, G_) in terms:
            if G_ >= 1: num += w * P_ / G_; den += w
        return num / den if den else np.nan

    rin, rb, skipped = [], [], {}
    for Y in seasons:
        keys = {k for (k, y) in UG if y == Y and UG[(k, y)] >= 1} | {k for (k, y) in FG if y == Y - 1 and FG[(k, y)] >= 1}
        for pid in keys:
            gY = UG.get((pid, Y), 0)
            pos = spos.get((pid, Y)) or spos.get((pid, Y - 1))
            if pos is None: skipped['no position'] = skipped.get('no position', 0) + 1; continue
            dinfo = draft.get(pid) or ((pl_draft[pid][0], pl_draft[pid][1], np.nan) if pid in pl_draft else None)
            undrafted = not (dinfo and dinfo[0] <= Y)
            pick = C.UNDRAFTED_PICK if undrafted else dinfo[1]
            if pid in birth: age = C.age_on(birth[pid], Y)
            elif dinfo and pd.notna(dinfo[2]): age = float(dinfo[2]) + (Y - dinfo[0])
            else: skipped['no age'] = skipped.get('no age', 0) + 1; continue
            seasons_played = {s for s in played.get(pid, set()) if s < Y} | ({Y} if gY >= 1 else set())
            cands = [min(seasons_played)]
            if dinfo and dinfo[0] <= Y: cands.append(dinfo[0])
            if pid in pl_rookie and pl_rookie[pid] <= Y: cands.append(pl_rookie[pid])
            cy = Y - min(cands) + 1
            G_before = sum(FG.get((pid, s), 0) for s in range(1999, Y))
            rookie_Y = not any(s < Y for s in seasons_played)
            prev = [(w, (pid, Y - k, FP.get((pid, Y - k), 0.0), FG.get((pid, Y - k), 0))) for w, k in ((3, 1), (2, 2), (1, 3))]
            prod_b = ppg(prev)
            if gY >= 1:
                prod_in = ppg([(3, (pid, Y, UP[(pid, Y)], gY)),
                               (2, (pid, Y - 1, FP.get((pid, Y - 1), 0.0), FG.get((pid, Y - 1), 0))),
                               (1, (pid, Y - 2, FP.get((pid, Y - 2), 0.0), FG.get((pid, Y - 2), 0)))])
            else:
                prod_in = prod_b
            if not rookie_Y and np.isnan(prod_b):
                skipped['no game in Y-1..Y-3'] = skipped.get('no game in Y-1..Y-3', 0) + 1; continue
            ns, comp = 0, True
            for k in (1, 2, 3):
                yr = Y + k
                if yr > last_data: comp = False; continue
                p = pts.get((pid, yr), 0.0)
                ns += int(p >= start[(yr, pos)] and p > 0)
            common = dict(key=pid, name=names.get(pid, pid), t=Y, pos=pos, age=age, cy=cy, pick=pick,
                          draft=np.log(min(pick, C.UNDRAFTED_PICK)), undrafted=undrafted, n_start=ns,
                          any_start=int(ns > 0), complete=comp, FV=np.nan, rookie_Y=rookie_Y)
            rin.append(dict(common, kind='V', prod=prod_in, games=float(gY), G=float(G_before + gY)))
            if rookie_Y:
                rb.append(dict(common, kind='R0', prod=np.nan, games=np.nan, G=np.nan))
            else:
                rb.append(dict(common, kind='V', prod=prod_b, games=float(FG.get((pid, Y - 1), 0)), G=float(G_before)))
    Sin = pd.DataFrame(rin).reset_index(drop=True); Sb = pd.DataFrame(rb).reset_index(drop=True)
    assert (Sin.key.values == Sb.key.values).all() and (Sin.t.values == Sb.t.values).all()
    return Sin, Sb, skipped


# ═════════════════════════════════════════════════════════════════════════════
# MATCHING, ODDS, JUDGING
# ═════════════════════════════════════════════════════════════════════════════
def odds(S, test_years):
    C.POOL_LAG, C.SNAP_FIRST = LAG, FIRST_Y
    rows = S.index[S.t.isin(test_years)].values
    pre = DD.neighbours(S, rows, 'A', pool_max_t=None)
    for r, nn in zip(pre['test'], pre['nn'][30]):                   # leak check
        assert (S.t.values[nn] <= S.t.values[r] - LAG).all(), 'pool leak'
        assert S.key.values[r] not in set(S.key.values[nn]), 'self in pool'
    parts = O.version_parts(S, None, pre, 'Fix 2')
    P, E = O.predictions(S, parts)
    return pre, parts, P, E


def perm_better(loss_in, loss_b, clusters, n=None, seed=11):
    """One-sided: is the in-season loss lower? Sign flips by player (a player's rows move together)."""
    n = N_PERM if n is None else n
    d = loss_in - loss_b
    u, inv = np.unique(clusters, return_inverse=True)
    obs = d.mean()
    rng = np.random.default_rng(seed)
    cnt = 0
    for _ in range(n):
        s = rng.choice([-1.0, 1.0], len(u))[inv]
        cnt += (d * s).mean() <= obs
    return float((cnt + 1) / (n + 1))


def evaluate(Sin, Sb, years, n_sim=O.N_SIM, judge_it=True):
    pi, parts_i, Pi, Ei = odds(Sin, years)
    pb, parts_b, Pb, Eb = odds(Sb, years)
    common = np.intersect1d(pi['test'], pb['test'])        # rows both versions could score
    ki = np.searchsorted(pi['test'], common) if (np.diff(pi['test']) > 0).all() else None
    mi = {r: i for i, r in enumerate(pi['test'])}; mb = {r: i for i, r in enumerate(pb['test'])}
    ii = np.array([mi[r] for r in common]); ib = np.array([mb[r] for r in common])
    y = Sin.any_start.values[common].astype(float); yE = Sin.n_start.values[common].astype(float)
    Pi_, Pb_ = Pi[ii], Pb[ib]
    li, lb = (Pi_ - y) ** 2, (Pb_ - y) ** 2
    res = {'n': int(len(common)), 'players': int(len(set(Sin.key.values[common]))),
           'brier_in': float(li.mean()), 'brier_base': float(lb.mean()),
           'p_better': perm_better(li, lb, Sin.key.values[common]),
           'said_vs_happened': {'in_season': float(Pi_.mean()), 'baseline': float(Pb_.mean()), 'happened': float(y.mean())}}
    res['guard_ok'] = bool(res['brier_in'] <= BRIER_GUARD * res['brier_base'])
    if judge_it:
        sub = {'test': common, 'nn': {30: [parts_i[i][0] for i in ii]}}
        parts = [parts_i[i] for i in ii]
        masks = O.masks_for(Sin, sub)
        sims, edges = O.sim_limits(Sin, parts, Pi_, Ei[ii], masks, n_sim)
        res['honest'], res['checks'] = O.judge(Pi_, Ei[ii], y, yE, masks, sims, edges)
        res['passes'] = bool(res['honest'] and res['guard_ok'])
    return res


# ═════════════════════════════════════════════════════════════════════════════
# CRASH TESTS (before lock): outcomes replaced, so no real result is seen
# ═════════════════════════════════════════════════════════════════════════════
def with_outcomes(S, ns):
    S = S.copy(); S['n_start'] = ns.astype(int); S['any_start'] = (ns > 0).astype(int); return S


def crash(Sin, Sb, runs=20, noise_runs=100, noise_perm=2000):
    rng = np.random.default_rng(3)
    out = {'noise': [], 'planted': []}
    # noise: outcomes shuffled within position and season (both frames get the same outcomes)
    # pre-lock amendment A3: 100 noise runs, not 20 (20 can't measure a 5% rate: 2 of 20 by chance is common)
    global N_PERM
    keep, N_PERM = N_PERM, noise_perm
    for k in range(noise_runs):
        ns = Sin.n_start.values.copy()
        for _, idx in Sin.groupby(['pos', 't']).indices.items():
            ns[idx] = ns[rng.permutation(idx)]
        r = evaluate(with_outcomes(Sin, ns), with_outcomes(Sb, ns), FRESH, judge_it=False)
        out['noise'].append(bool(r['brier_in'] < r['brier_base'] and r['p_better'] < 0.05))
    N_PERM = keep
    # planted: truth driven by this season's production, at the strength season-end production has on
    # pool-only seasons (<= 2016, never a test row). Strength fitted on baseline features, so no in-season
    # outcome relation is looked at.
    pool = (Sb.kind.values == 'V') & (Sb.t.values <= 2016)
    z = lambda x, m: (x - np.nanmean(x[m])) / np.nanstd(x[m])
    zb = z(Sb['prod'].values.astype(float), pool)
    yb = Sb.any_start.values.astype(float)
    a, b = fit_logit(zb[pool], yb[pool])
    zi = z(Sin['prod'].values.astype(float), Sin.t.values <= 2016)
    p_true = 1 / (1 + np.exp(-(a + b * np.nan_to_num(zi))))
    frac2 = float(((Sb.n_start.values >= 2).sum()) / max(1, (Sb.n_start.values >= 1).sum()))
    for k in range(runs):
        hit = rng.random(len(p_true)) < p_true
        ns = np.where(hit, 1 + rng.binomial(2, frac2 / 2, len(hit)), 0)
        r = evaluate(with_outcomes(Sin, ns), with_outcomes(Sb, ns), FRESH, judge_it=False)
        out['planted'].append(bool(r['brier_in'] < r['brier_base'] and r['p_better'] < 0.05))
    out['planted_strength'] = {'a': a, 'b': b}
    out['noise_false_alarms'] = int(sum(out['noise'])); out['planted_caught'] = int(sum(out['planted']))
    out['noise_ok'] = out['noise_false_alarms'] <= 5          # <= 5% of 100
    out['planted_ok'] = out['planted_caught'] >= 16           # >= 80% of 20
    return out


def fit_logit(x, y, it=50):
    a = b = 0.0
    for _ in range(it):                                       # Newton steps, two parameters
        p = 1 / (1 + np.exp(-(a + b * x)))
        w = p * (1 - p); g = np.array([(y - p).sum(), ((y - p) * x).sum()])
        H = np.array([[w.sum(), (w * x).sum()], [(w * x).sum(), (w * x * x).sum()]])
        a, b = np.array([a, b]) + np.linalg.solve(H, g)
    return float(a), float(b)


# ═════════════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nflverse', required=True); ap.add_argument('--rosters', required=True)
    ap.add_argument('--weekly', required=True)
    g = ap.add_mutually_exclusive_group(required=True); g.add_argument('--crash', action='store_true'); g.add_argument('--run', action='store_true')
    a = ap.parse_args()
    st, dp, pl, W = load(a.nflverse, a.rosters, a.weekly)
    res = {'prereg': 'docs/PREREG-in-season-comps.md', 'points_check': points_check(st, W)}
    os.makedirs(OUT, exist_ok=True)
    if a.crash:
        Sin, Sb, sk = snapshots(st, dp, pl, W, 9, range(FIRST_Y, max(FRESH) + 1))
        res['rows'] = int(len(Sin)); res['skipped'] = sk
        res['crash_week_9'] = crash(Sin, Sb)
        json.dump(res, open(os.path.join(OUT, 'comps_in_season_crash.json'), 'w'), indent=1)
        print(json.dumps({k: v for k, v in res['crash_week_9'].items() if k not in ('noise', 'planted')}, indent=1))
        return
    res['weeks'] = {}
    for w in WEEKS:
        Sin, Sb, sk = snapshots(st, dp, pl, W, w, range(FIRST_Y, max(FRESH) + 1))
        r = {'rows': int(len(Sin)), 'skipped': sk, 'fresh_2021_22': evaluate(Sin, Sb, FRESH),
             'reported_2009_12': evaluate(Sin, Sb, OLD), 'reported_2005_22': evaluate(Sin, Sb, ALL, judge_it=False)}
        res['weeks'][str(w)] = r
        print(w, {k: r['fresh_2021_22'][k] for k in ('n', 'brier_in', 'brier_base', 'p_better', 'honest', 'guard_ok', 'passes')})
    res['decision'] = 'in-season from week 5' if all(res['weeks'][str(w)]['fresh_2021_22']['passes'] for w in WEEKS) \
        else 'keep season-end matching all year'
    json.dump(res, open(os.path.join(OUT, 'comps_in_season_results.json'), 'w'), indent=1, default=str)
    print('DECISION:', res['decision'])


if __name__ == '__main__':
    main()
