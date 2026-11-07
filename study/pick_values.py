#!/usr/bin/env python3
"""
DELTA — ROOKIE PICKS ON THE OWN VALUE SCALE. Implements docs/PREREG-pick-values.md; where they disagree, the
pre-registration (with its section 11 amendments) wins.

A pick's value = average FV5 of the players taken in its tier of the FFC rookie draft, other classes only (leave one
class out). Fairness against veterans: R = (FV5 the picks produced) / (average FV5 of veterans whose Own Value Scale
value was within +-10% of the pick's value, same offseason). 95% range from 4,000 resamples; range excludes 1.0 ->
multiply every pick by R. No market data of any kind is read. Data: nflverse, Fantasy Football Calculator (credit both).

    python pick_values.py --nflverse DIR --rosters DIR --counts-only
    python pick_values.py --nflverse DIR --rosters DIR                  # confirmatory (once, after lock)
"""
import argparse, importlib.util, json, os
from pathlib import Path
import numpy as np
import pandas as pd
import comps_value_study as C
import comps_draft_drop as DD
import own_value_scale as V

ROOT = Path(__file__).resolve().parent.parent
CLASSES = list(range(2014, 2022))
TIERS = ['Early 1st', 'Mid 1st', 'Late 1st', '2nd', '3rd']
WINDOWS = (0.10, 0.20)
MIN_VETS = 10
BOOT = 4000
SEED = 20261107
YEAR_OUT = 0.9


# ── data ─────────────────────────────────────────────────────────────────────────────────────────
def load_slots():
    """Rookie-draft slots, built by scripts/future-first-study.py's own code, unchanged."""
    spec = importlib.util.spec_from_file_location('ff', ROOT / 'scripts' / 'future-first-study.py')
    ff = importlib.util.module_from_spec(spec); spec.loader.exec_module(ff)
    dp, und, _ = ff.draft_tables()
    S, dropped = ff.ffc_slots(dp, und)
    assert len(S) == 351 and len(dropped) == 7, (len(S), len(dropped))
    assert list(ff.TIERS) == TIERS
    return S[S.cls.isin(CLASSES)].reset_index(drop=True), dropped


def fv5_from_stats(st, key, pos, cls):
    """FV5 for a player with no incoming-rookie snapshot (undrafted): seasons cls..cls+4, as C.build does."""
    fv = 0.0
    for k in range(5):
        yr = cls + k
        p = np.sort(st[(st.season == yr) & (st.position == pos)].P.values)[::-1]
        repl = p[C.REPL_N[pos] - 1] if len(p) >= C.REPL_N[pos] else 0.0
        pts = st[(st.player_id == key) & (st.season == yr)].P
        fv += C.DISCOUNT ** k * max(0.0, (float(pts.iat[0]) if len(pts) else 0.0) - repl)
    return fv


def setup(nflverse, rosters):
    """Picks (outcomes) and veterans (OVS predictions from pool outcomes only, and outcomes)."""
    st, S, pre, nnA, W, counts = V.setup(nflverse, rosters)
    y = S.FV.values.astype(float)
    pr = V.predictions(S, pre, nnA, W, y)
    T = pre['test']
    isv = S.kind.values[T] == 'V'
    vet = {'t': S.t.values[T][isv], 'ovs': pr['OVS'][isv], 'y': y[T][isv], 'key': S.key.values[T][isv],
           'pos': S.pos.values[T][isv], 'row': T[isv]}
    slots, dropped = load_slots()
    r0 = S[S.kind == 'R0']
    r0 = {(k, int(t)): i for i, k, t in zip(r0.index, r0.key, r0.t)}
    yp, pos_line, src = [], [], []
    for r in slots.itertuples():
        i = r0.get((r.gsis, r.cls - 1))
        if i is not None:
            yp.append(float(S.FV.values[i])); pos_line.append(S.pos.values[i]); src.append('R0')
            assert S.complete.values[i]
            if r.pos == S.pos.values[i]:       # same line both ways: the R0 outcome must equal a fresh computation
                assert abs(fv5_from_stats(st, r.gsis, r.pos, r.cls) - yp[-1]) < 1e-6, r.name
        else:
            yp.append(fv5_from_stats(st, r.gsis, r.pos, r.cls)); pos_line.append(r.pos); src.append('stats')
    picks = {'cls': slots.cls.values, 'tier': np.array([TIERS.index(x) for x in slots.tier]),
             'slot': slots.slot.values, 'pos': np.array(pos_line), 'y': np.array(yp),
             'name': slots.name.values, 'key': slots.gsis.values}
    counts.update({'picks': int(len(slots)), 'picks_by_tier': slots.tier.value_counts().to_dict(),
                   'picks_outcome_source': pd.Series(src).value_counts().to_dict(),
                   'veteran_rows': int(isv.sum()), 'veteran_players': int(len(set(vet['key']))),
                   'veteran_rows_by_season': {int(k): int(v) for k, v in zip(*np.unique(vet['t'], return_counts=True))},
                   'slots_dropped_by_ffc_code': len(dropped)})
    return st, S, picks, vet, counts


# ── the estimator ────────────────────────────────────────────────────────────────────────────────
class Matcher:
    """Veterans per offseason, sorted by OVS once. Matching reads OVS only (predictions), never an outcome."""
    def __init__(self, vet):
        self.by_t = {}
        for t in np.unique(vet['t']):
            idx = np.where(vet['t'] == t)[0]
            idx = idx[np.argsort(vet['ovs'][idx], kind='stable')]
            self.by_t[int(t)] = (idx, vet['ovs'][idx])

    def windows(self, t, v):
        """[lo, hi) positions into the season's sorted list, for each window width."""
        idx, o = self.by_t[t]
        return [(np.searchsorted(o, v * (1 - w), 'left'), np.searchsorted(o, v * (1 + w), 'right')) for w in WINDOWS]


def tier_values(picks, y, w):
    """tv[c][k] = weighted mean outcome of tier k over the OTHER classes (leave one class out)."""
    tv = {}
    for c in CLASSES:
        m = picks['cls'] != c
        tv[c] = np.array([(w[m & (picks['tier'] == k)] * y[m & (picks['tier'] == k)]).sum()
                          / w[m & (picks['tier'] == k)].sum() for k in range(len(TIERS))])
    return tv


def estimate(picks, vet, M, y_pick, y_vet, w_pick=None, w_vet=None, detail=False):
    n = len(y_pick)
    w_pick = np.ones(n) if w_pick is None else w_pick
    w_vet = np.ones(len(y_vet)) if w_vet is None else w_vet
    tv = tier_values(picks, y_pick, w_pick)
    v = np.array([tv[c][k] for c, k in zip(picks['cls'], picks['tier'])])
    m = np.full(n, np.nan); width = np.full(n, np.nan); nv = np.zeros(n)
    cum = {}
    for t, (idx, _) in M.by_t.items():
        cw = np.concatenate([[0.0], np.cumsum(w_vet[idx])])
        cy = np.concatenate([[0.0], np.cumsum(w_vet[idx] * y_vet[idx])])
        cum[t] = (cw, cy)
    for i in range(n):
        t = int(picks['cls'][i]) - 1
        cw, cy = cum[t]
        for (lo, hi), wd in zip(M.windows(t, v[i]), WINDOWS):
            cnt = cw[hi] - cw[lo]
            if cnt >= MIN_VETS:
                m[i] = (cy[hi] - cy[lo]) / cnt; width[i] = wd; nv[i] = cnt
                break
    keep = ~np.isnan(m)
    R = (w_pick[keep] * y_pick[keep]).sum() / (w_pick[keep] * m[keep]).sum()
    if not detail:
        return R, keep, m, w_pick
    return {'R': float(R), 'v': v, 'm': m, 'keep': keep, 'width': width, 'n_vets': nv, 'tv': tv}


def sub_R(y_pick, m, keep, w, mask):
    k = keep & mask
    return float((w[k] * y_pick[k]).sum() / (w[k] * m[k]).sum()) if k.any() else None


def groups(picks):
    g = {t: picks['tier'] == i for i, t in enumerate(TIERS)}
    g['QB'] = picks['pos'] == 'QB'; g['RB/WR/TE'] = picks['pos'] != 'QB'
    g['classes 2014-2017'] = picks['cls'] <= 2017; g['classes 2018-2021'] = picks['cls'] >= 2018
    return g


def bootstrap(picks, vet, M, y_pick, y_vet, n_boot=BOOT, seed=SEED, with_groups=True):
    """Picks resampled within each class; veterans resampled by player (all of his seasons together)."""
    rng = np.random.default_rng(seed)
    by_cls = {c: np.where(picks['cls'] == c)[0] for c in CLASSES}
    cl, inv = np.unique(vet['key'], return_inverse=True)
    G = groups(picks) if with_groups else {}
    Rs, sub = np.empty(n_boot), {k: [] for k in G}
    for b in range(n_boot):
        wp = np.zeros(len(y_pick))
        for c, ix in by_cls.items():
            np.add.at(wp, rng.choice(ix, len(ix)), 1.0)
        wc = np.bincount(rng.integers(0, len(cl), len(cl)), minlength=len(cl)).astype(float)
        R, keep, m, w = estimate(picks, vet, M, y_pick, y_vet, wp, wc[inv])
        Rs[b] = R
        for k, mk in G.items():
            sub[k].append(sub_R(y_pick, m, keep, w, mk))
    lo, hi = np.percentile(Rs, [2.5, 97.5])
    out = {'lo': float(lo), 'hi': float(hi), 'includes_1': bool(lo <= 1.0 <= hi)}
    if with_groups:
        out['groups'] = {k: [float(x) for x in np.percentile([z for z in s if z is not None], [2.5, 97.5])]
                         for k, s in sub.items()}
    return out


# ── reported only ────────────────────────────────────────────────────────────────────────────────
def ruler_top(S):
    """The ruler's 10,000: the top 2025 OVS value (same computation as own_value_scale.current)."""
    rows = S.index[S.t == 2025].values
    pa = DD.neighbours(S, rows, 'A', pool_max_t=2020)
    y = S.FV.values.astype(float); top = 0.0
    for r, nn in zip(pa['test'], pa['nn'][30]):
        w = 0.5 ** ((2025 - S.t.values[nn]) / V.HALF_LIFE); w /= w.sum()
        top = max(top, float((w * y[nn]).sum()))
    return top


def ruler(picks, y, top, R_fix=1.0, n_boot=BOOT, seed=SEED):
    """Tier values from all eight classes on the 0-10,000 ruler, with resampled ranges."""
    rng = np.random.default_rng(seed + 1)
    by_cls = {c: np.where(picks['cls'] == c)[0] for c in CLASSES}
    def vals(w):
        t = [float((w * y)[picks['tier'] == k].sum() / w[picks['tier'] == k].sum()) for k in range(len(TIERS))]
        s1 = picks['slot'] == 1
        return t + [float((w * y)[s1].sum() / w[s1].sum())]
    base = vals(np.ones(len(y)))
    bs = []
    for _ in range(n_boot):
        wp = np.zeros(len(y))
        for c, ix in by_cls.items():
            np.add.at(wp, rng.choice(ix, len(ix)), 1.0)
        bs.append(vals(wp))
    bs = np.array(bs)
    sc = lambda x: round(10000 * R_fix * x / top)
    names = TIERS + ['1.01 alone']
    out = {}
    for j, nm in enumerate(names):
        lo, hi = np.percentile(bs[:, j], [2.5, 97.5])
        n = int((picks['slot'] == 1).sum()) if nm == '1.01 alone' else int((picks['tier'] == j).sum())
        out[nm] = {'picks': n, 'fv5': round(base[j], 1), 'value': sc(base[j]), 'range': [sc(lo), sc(hi)]}
    first = np.mean(base[:3])
    out['conventions'] = {'1st, slot unknown': sc(first), '1st, slot unknown, a year out': sc(YEAR_OUT * first)}
    for j, nm in enumerate(TIERS):
        out['conventions'][f'{nm}, a year out'] = sc(YEAR_OUT * base[j])
    return out


def riskiness(picks, vet, M, y_pick, y_vet, est):
    """Share of one-for-one pairs (a pick vs one of its matched veterans) in which the pick produced more."""
    share = []
    for i in np.where(est['keep'])[0]:
        t = int(picks['cls'][i]) - 1
        idx, _ = M.by_t[t]
        lo, hi = M.windows(t, est['v'][i])[WINDOWS.index(est['width'][i])]
        yv = y_vet[idx[lo:hi]]
        share.append(((yv < y_pick[i]).sum() + 0.5 * (yv == y_pick[i]).sum()) / len(yv))
    share = np.array(share)
    zero = float((y_pick[est['keep']] == 0).mean())
    return {'pick_beat_equal_veteran': float(share.mean()), 'picks_scoring_zero_fv5': zero}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nflverse', required=True); ap.add_argument('--rosters', required=True)
    ap.add_argument('--counts-only', action='store_true')
    a = ap.parse_args()
    st, S, picks, vet, counts = setup(a.nflverse, a.rosters)
    M = Matcher(vet)
    print(json.dumps(counts, indent=1, default=int))
    if a.counts_only:
        return
    yp, yv = picks['y'], vet['y']
    est = estimate(picks, vet, M, yp, yv, detail=True)
    ci = bootstrap(picks, vet, M, yp, yv)
    G = groups(picks); w1 = np.ones(len(yp))
    fair = ci['includes_1']
    R_fix = 1.0 if fair else est['R']
    top = ruler_top(S)
    res = {'prereg': 'docs/PREREG-pick-values.md', 'counts': counts,
           'R': est['R'], 'range': [ci['lo'], ci['hi']], 'decision': 'fair: tier values unchanged' if fair
           else f'tilted: every pick multiplied by R = {est["R"]:.3f}',
           'picks_scored': int(est['keep'].sum()), 'picks_dropped_too_few_vets': int((~est['keep']).sum()),
           'window_used': {'10%': int((est['width'] == 0.10).sum()), '20%': int((est['width'] == 0.20).sum())},
           'median_matched_veterans': float(np.median(est['n_vets'][est['keep']])),
           'by_group': {k: {'n': int((est['keep'] & mk).sum()), 'R': sub_R(yp, est['m'], est['keep'], w1, mk),
                            'range': ci['groups'][k]} for k, mk in G.items()},
           'riskiness': riskiness(picks, vet, M, yp, yv, est),
           'ruler_top_fv5': top, 'ruler': ruler(picks, yp, top, R_fix),
           'tier_values_loco_fv5': {int(c): [round(float(x), 1) for x in tv] for c, tv in est['tv'].items()}}
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out', 'pick_values_results.json')
    json.dump(res, open(out, 'w'), indent=1, default=float)
    print(json.dumps({k: res[k] for k in ('R', 'range', 'decision', 'picks_scored', 'by_group', 'riskiness', 'ruler')},
                     indent=1, default=float))


if __name__ == '__main__':
    main()
