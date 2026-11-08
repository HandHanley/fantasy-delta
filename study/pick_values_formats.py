#!/usr/bin/env python3
"""
DELTA — ROOKIE PICK VALUES BY LEAGUE FORMAT. Implements docs/PREREG-pick-values-formats.md; where they disagree, the
pre-registration (with its section 9 amendments) wins. Same estimator as pick_values.py, rebuilt per format.

    python pick_values_formats.py --nflverse DIR --rosters DIR                       # all 36 formats (once, after lock)
    python pick_values_formats.py --nflverse DIR --rosters DIR --only 12,SF,0.5,0.5  # one format
"""
import argparse, itertools, json, os, time
import numpy as np
import comps_value_study as C
import pick_values as P

TEAMS = (10, 12, 14)
QBS = ('1QB', 'SF')
PPR = (0.0, 0.5, 1.0)
TEP = (0.0, 0.5)
DELTA_FMT = (12, 'SF', 0.5, 0.5)
LOCKED_R = 1.392101615371152          # docs/PREREG-pick-values.md §12, DELTA's format
BINS = [(1, 4), (5, 8), (9, 12), (13, 24), (25, 36)]
_ORIG_LOAD, _ORIG_REPL = C.load, dict(C.REPL_N)


def lines(teams, qb):
    return {'QB': (2 if qb == 'SF' else 1) * teams, 'RB': round(2.5 * teams), 'WR': round(3.5 * teams),
            'TE': round(14 / 12 * teams)}


def name(f):
    t, q, p, e = f
    return f"{t}-team {'Superflex' if q == 'SF' else '1QB'} {({0.0: 'Standard', 0.5: 'Half PPR', 1.0: 'Full PPR'})[p]}" \
           + (' TE Premium' if e else '')


def apply(f):
    """Point every builder at this format: scoring in the stats table, replacement lines in the snapshot builder."""
    t, q, ppr, tep = f
    def load(*a, **k):
        st, dp, pl = _ORIG_LOAD(*a, **k)
        P_new = st.fantasy_points.fillna(0) + ppr * st.receptions + np.where(st.position == 'TE', tep * st.receptions, 0.0)
        if f == DELTA_FMT:
            assert np.allclose(P_new, st.P), 'DELTA format must reproduce the locked points exactly'
        st['P'] = P_new
        return st, dp, pl
    C.load = load
    C.REPL_N = lines(t, q)
    if f == DELTA_FMT:
        assert C.REPL_N == _ORIG_REPL, (C.REPL_N, _ORIG_REPL)


def by_pick(teams, slot_val):
    """League pick label -> value, for three rounds. Slots past 36 take the slots 25-36 value (convention, §3)."""
    out = {}
    for r in (1, 2, 3):
        for p in range(1, teams + 1):
            s = (r - 1) * teams + p
            out[f'{r}.{p:02d}'] = slot_val[min(next((i for i, (a, b) in enumerate(BINS) if a <= s <= b), 4), 4)]
    return out


def run(f, nflverse, rosters, n_boot=P.BOOT):
    apply(f)
    st, S, picks, vet, counts = P.setup(nflverse, rosters)
    M = P.Matcher(vet)
    yp, yv = picks['y'], vet['y']
    est = P.estimate(picks, vet, M, yp, yv, detail=True)
    if f == DELTA_FMT:
        assert abs(est['R'] - LOCKED_R) < 1e-9, est['R']
    ci = P.bootstrap(picks, vet, M, yp, yv, n_boot=n_boot)
    fair = ci['includes_1']; mult = 1.0 if fair else est['R']
    top = P.ruler_top(S)
    G = P.groups(picks); w1 = np.ones(len(yp))
    slot = picks['slot']
    raw = [float(yp[(slot >= a) & (slot <= b)].mean()) for a, b in BINS]
    sv = [round(10000 * mult * x / top) for x in raw]
    first = {t: round(np.mean([sv[min(next(i for i, (a, b) in enumerate(BINS) if a <= s <= b), 4)]
                               for s in range(1, t + 1)])) for t in TEAMS}
    return {'format': name(f), 'key': list(f), 'lines': C.REPL_N, 'R': est['R'], 'range': [ci['lo'], ci['hi']],
            'decision': 'fair' if fair else 'tilted', 'multiplier': mult,
            'picks_scored': int(est['keep'].sum()),
            'R_QB_picks': P.sub_R(yp, est['m'], est['keep'], w1, G['QB']), 'R_QB_range': ci['groups']['QB'],
            'R_other_picks': P.sub_R(yp, est['m'], est['keep'], w1, G['RB/WR/TE']),
            'R_other_range': ci['groups']['RB/WR/TE'],
            'ruler_top_fv5': top, 'slot_bins': {f'{a}-{b}': v for (a, b), v in zip(BINS, sv)},
            'slot_bins_year_out': {f'{a}-{b}': round(P.YEAR_OUT * v) for (a, b), v in zip(BINS, sv)},
            'first_slot_unknown': first[f[0]], 'by_pick': by_pick(f[0], sv)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nflverse', required=True); ap.add_argument('--rosters', required=True)
    ap.add_argument('--only', default=None, help='teams,qb,ppr,tep')
    a = ap.parse_args()
    if a.only:
        t, q, p, e = a.only.split(','); fmts = [(int(t), q, float(p), float(e))]
    else:
        fmts = [DELTA_FMT] + [f for f in itertools.product(TEAMS, QBS, PPR, TEP) if f != DELTA_FMT]
    out, t0 = [], time.time()
    for f in fmts:
        r = run(f, a.nflverse, a.rosters)
        out.append(r)
        print(f"{r['format']:<40} R {r['R']:.2f} [{r['range'][0]:.2f}-{r['range'][1]:.2f}] {r['decision']:<6} "
              f"bins {list(r['slot_bins'].values())}  QB {r['R_QB_picks']:.2f} rest {r['R_other_picks']:.2f}  "
              f"{time.time() - t0:.0f}s", flush=True)
    if not a.only:
        dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out', 'pick_values_formats_results.json')
        json.dump({'prereg': 'docs/PREREG-pick-values-formats.md', 'formats': out}, open(dst, 'w'), indent=1,
                  default=float)


if __name__ == '__main__':
    main()
