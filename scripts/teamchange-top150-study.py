#!/usr/bin/env python3
"""
DELTA Team Changes Among Fantasy-Relevant Players — scripts/teamchange-top150-study.py
Pre-registration: docs/PREREG-team-change-top150.md

    python3 scripts/teamchange-top150-study.py --count   # counts only; computes NO outcomes
    python3 scripts/teamchange-top150-study.py --run     # refuses unless the pre-registration is committed

Owner's hypothesis (27 Sep 2026): the young-mover drop is driven by fringe players and busts; among
players who matter in fantasy lineups, moving young should not hurt.
"Top 150" = each season's 150 highest PRESEASON starting numbers across all positions (no hindsight).
Everything else is imported unchanged from the locked scripts/teamchange-age-study.py (which imports
scripts/teamchange-study.py): teams, eligibility, starting number, age, the multiplier fit.
"""
import argparse, importlib.util, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
_s = importlib.util.spec_from_file_location('ag', ROOT / 'scripts' / 'teamchange-age-study.py')
ag = importlib.util.module_from_spec(_s); _s.loader.exec_module(ag); tc = ag.tc; bs = ag.bs

PREREG = 'docs/PREREG-team-change-top150.md'
TOP = 150
ENGINE_GAP_TOP150 = 0.843 / 0.928 - 1      # live engine 27 Sep 2026, top 150 veterans, recorded before the run
SEED, BOOT = 20260927, 2000

def build(g):
    df = ag.build(g)
    df['rk'] = df.groupby('season')['p0'].rank(ascending=False, method='first')
    return df[df['rk'] <= TOP].copy()

def main():
    ap = argparse.ArgumentParser(); m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument('--count', action='store_true'); m.add_argument('--run', action='store_true')
    a = ap.parse_args()
    lock = None
    if a.run: bs.PREREG = PREREG; lock = bs.require_locked_prereg()
    g, _ = bs.load_games()
    df = build(g)
    print(f"[TOP150] {len(df)} player-seasons · changed {int(df['changed'].sum())} · stayed {int((~df['changed']).sum())}")
    for lo, hi, l in ag.BANDS:
        d = df[df['band'] == l]; print(f"[TOP150]   {l:13s} changed {int(d['changed'].sum()):3d} · stayed {int((~d['changed']).sum()):4d}")
    if a.count: print('[TOP150] --count: no outcomes computed.'); return

    young = df[df['age'] < 27]
    est = {'gap_all_top150': ag.gap(df), 'gap_young_top150': ag.gap(young), 'gap_29plus_top150': ag.gap(df[df['age'] >= 29])}
    rng = np.random.default_rng(SEED); pids = df['pid'].unique(); by = {p: d for p, d in df.groupby('pid')}
    boots = {k: [] for k in est}; bb = {l: [] for _, _, l in ag.BANDS}
    for _ in range(BOOT):
        d = pd.concat([by[p] for p in rng.choice(pids, len(pids), replace=True)], ignore_index=True)
        boots['gap_all_top150'].append(ag.gap(d)); boots['gap_young_top150'].append(ag.gap(d[d['age'] < 27]))
        boots['gap_29plus_top150'].append(ag.gap(d[d['age'] >= 29]))
        for _, _, l in ag.BANDS: bb[l].append(ag.gap(d[d['band'] == l]))
    ci = {k: [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))] for k, v in boots.items()}
    lo, hi = ci['gap_all_top150']
    q1 = ('ABOUT RIGHT for top-150 players — the engine\'s gap is inside the range' if lo <= ENGINE_GAP_TOP150 <= hi else
          'ENGINE TOO SOFT on top-150 team-changers' if hi < ENGINE_GAP_TOP150 else 'ENGINE TOO HARSH on top-150 team-changers')
    q2 = ci['gap_young_top150'][1] >= 0
    out = {'lock': lock, 'n': int(len(df)), 'n_changed': int(df['changed'].sum()), 'estimates': est, 'range_95': ci,
           'engine_gap_top150_recorded': ENGINE_GAP_TOP150, 'Q1_VERDICT': q1,
           'Q2_young_relevant_movers_not_clearly_worse': bool(q2),
           'Q2_VERDICT': ('SUPPORTED — among top-150 players, young changers are not clearly worse than young stayers' if q2
                          else 'NOT SUPPORTED — even top-150 young changers are clearly worse than young stayers'),
           'by_band_reported_only': {l: {'n_changed': int(df[(df['band'] == l) & df['changed']].shape[0]), 'gap': ag.gap(df[df['band'] == l]),
                                         'range_95': [float(np.nanpercentile(bb[l], 2.5)), float(np.nanpercentile(bb[l], 97.5))]} for _, _, l in ag.BANDS},
           'by_position_reported_only': {ps: {'n_changed': int(df[(df['pos'] == ps) & df['changed']].shape[0]), 'gap': ag.gap(df[df['pos'] == ps])} for ps in bs.SKILL}}
    print(json.dumps(out, indent=2, default=float))
    (ROOT / 'data-cache' / 'teamchange-top150-result.json').write_text(json.dumps(out, indent=2, default=float))

if __name__ == '__main__':
    main()
