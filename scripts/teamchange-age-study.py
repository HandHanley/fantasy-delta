#!/usr/bin/env python3
"""
DELTA Team Changes Through An Age Lens — scripts/teamchange-age-study.py
Pre-registration: docs/PREREG-team-change-age.md

    python3 scripts/teamchange-age-study.py --count   # counts only; computes NO outcomes
    python3 scripts/teamchange-age-study.py --run     # refuses unless the pre-registration is committed

Owner's hypothesis (27 Sep 2026): the team-change penalty is an AGE effect — young players who move
can do as well or better; older players who move lose production. Each age group compares changers
with STAYERS OF THE SAME AGE (older players decline whether they move or not).

Everything about teams, eligibility and the starting number is imported unchanged from the locked
scripts/teamchange-study.py. Age = years on 7 September of the season (the engine's AGE_AS_OF rule),
from nflverse birth dates.
"""
import argparse, importlib.util, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
_s = importlib.util.spec_from_file_location('tc', ROOT / 'scripts' / 'teamchange-study.py')
tc = importlib.util.module_from_spec(_s); _s.loader.exec_module(tc); bs = tc.bs

PREREG = 'docs/PREREG-team-change-age.md'
BANDS = [(0, 27, '26 and under'), (27, 29, '27-28'), (29, 31, '29-30'), (31, 99, '31+')]
SEED, BOOT = 20260927, 2000

def build(g):
    df = tc.build(g)
    pl = pd.read_parquet(bs.fetch(f'{bs.REL}/players/players.parquet', bs.CACHE / 'players.parquet'), columns=['gsis_id', 'birth_date'])
    bd = dict(zip(pl['gsis_id'].astype(str), pd.to_datetime(pl['birth_date'], errors='coerce')))
    df['age'] = [(pd.Timestamp(y, 9, 7) - bd.get(p)).days / 365.25 if pd.notna(bd.get(p)) else np.nan
                 for p, y in zip(df['pid'], df['season'])]
    df = df.dropna(subset=['age']).copy()
    df['band'] = [next(l for lo, hi, l in BANDS if lo <= a < hi) for a in df['age']]
    return df

def gap(d):
    c, s = d[d['changed']], d[~d['changed']]
    if not len(c) or not len(s): return np.nan
    return tc.mult(c) / tc.mult(s) - 1

def main():
    ap = argparse.ArgumentParser(); m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument('--count', action='store_true'); m.add_argument('--run', action='store_true')
    a = ap.parse_args()
    lock = None
    if a.run: bs.PREREG = PREREG; lock = bs.require_locked_prereg()
    g, _ = bs.load_games()
    df = build(g)
    for lo, hi, l in BANDS:
        d = df[df['band'] == l]
        print(f"[AGE] {l:13s} changed {int(d['changed'].sum()):4d} · stayed {int((~d['changed']).sum()):4d}")
    if a.count: print('[AGE] --count: no outcomes computed.'); return

    young, old = df[df['age'] < 27], df[df['age'] >= 29]
    est = {'gap_26_and_under': gap(young), 'gap_29_plus': gap(old)}
    est['difference_29plus_minus_26under'] = est['gap_29_plus'] - est['gap_26_and_under']
    rng = np.random.default_rng(SEED); pids = df['pid'].unique(); by = {p: d for p, d in df.groupby('pid')}
    boots = {k: [] for k in est}; bands_boot = {l: [] for _, _, l in BANDS}
    for _ in range(BOOT):
        d = pd.concat([by[p] for p in rng.choice(pids, len(pids), replace=True)], ignore_index=True)
        y_, o_ = gap(d[d['age'] < 27]), gap(d[d['age'] >= 29])
        boots['gap_26_and_under'].append(y_); boots['gap_29_plus'].append(o_); boots['difference_29plus_minus_26under'].append(o_ - y_)
        for _, _, l in BANDS: bands_boot[l].append(gap(d[d['band'] == l]))
    ci = {k: [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))] for k, v in boots.items()}
    h1 = ci['difference_29plus_minus_26under'][1] < 0                      # older changers clearly worse
    h2 = ci['gap_26_and_under'][0] <= 0 <= ci['gap_26_and_under'][1] or ci['gap_26_and_under'][0] > 0   # young not clearly worse
    verdict = ('SUPPORTED — age drives it: older changers lose production; young changers are not worse than young stayers' if h1 and h2 else
               'PARTLY — older changers are clearly worse, but young changers also lose some' if h1 else
               'NOT SUPPORTED — the team-change gap does not clearly grow with age')
    per_band = {l: {'n_changed': int(df[(df['band'] == l) & df['changed']].shape[0]), 'gap': gap(df[df['band'] == l]),
                    'range_95': [float(np.nanpercentile(bands_boot[l], 2.5)), float(np.nanpercentile(bands_boot[l], 97.5))]}
                for _, _, l in BANDS}
    per_pos = {}
    for ps in bs.SKILL:
        d = df[df['pos'] == ps]
        per_pos[ps] = {'26_and_under': gap(d[d['age'] < 27]), '29_plus': gap(d[d['age'] >= 29]),
                       'n_changed_young': int(d[(d['age'] < 27) & d['changed']].shape[0]), 'n_changed_old': int(d[(d['age'] >= 29) & d['changed']].shape[0])}
    out = {'lock': lock, 'estimates': est, 'range_95': ci, 'H1_older_clearly_worse': bool(h1), 'H2_young_not_clearly_worse': bool(h2),
           'VERDICT': verdict, 'by_band_reported_only': per_band, 'by_position_reported_only': per_pos}
    print(json.dumps(out, indent=2, default=float))
    (ROOT / 'data-cache' / 'teamchange-age-result.json').write_text(json.dumps(out, indent=2, default=float))

if __name__ == '__main__':
    main()
