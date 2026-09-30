#!/usr/bin/env python3
"""
DELTA College Signal Beyond Draft Slot — scripts/college-signal-study.py
Pre-registration: docs/PREREG-college-signal.md

    python3 scripts/college-signal-study.py --count   # links and counts only; computes NO outcomes
    python3 scripts/college-signal-study.py --run     # refuses unless the pre-registration is committed

Does a rookie's final-college-season production predict his NFL rookie points per game BEYOND his
draft slot?
  Baseline  DELTA's rookie table: median rookie PPG by position x draft tier (scripts/blend-study-rookies.py
            recipe), fitted on every rookie season 2015-2025 EXCEPT the class being predicted.
  dDOM      baseline x (1 + b x (dDOM percentile / 100 - 0.5)) — b fitted on the other four classes.
  Raw       the same, with the percentile of the RAW metric (no competition adjustment)  — the sub-test.
dDOM is DELTA's live code, run from index.html by scripts/ddom-dump.js (469/469 identical to the published
college index). Classes 2021-2025 (college data starts in 2020). Rookie PPG = the rookie table's own
definition: points per game over the games he played in his rookie season.
"""
import argparse, importlib.util, json, re, subprocess
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
_s = importlib.util.spec_from_file_location('rk', ROOT / 'scripts' / 'blend-study-rookies.py')
rk = importlib.util.module_from_spec(_s); _s.loader.exec_module(rk); bs = rk.bs

PREREG = 'docs/PREREG-college-signal.md'
CLASSES = [2021, 2022, 2023, 2024, 2025]
MIN_CLASSES_BETTER, MIN_POS_N, SEED, SHUFFLES, BOOT = 4, 30, 20260929, 2000, 2000
norm = lambda s: re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', re.sub(r"[^a-z ]", '', str(s).lower().replace('.', ''))).replace(' ', '')

def college():
    out = subprocess.run(['node', str(ROOT / 'scripts' / 'ddom-dump.js')] + [str(y) for y in range(2020, 2025)],
                         capture_output=True, text=True, check=True).stdout
    d = pd.DataFrame(json.loads(out)); d['k'] = d['n'].map(norm); return d

def build(read_outcomes):
    col = college()
    dp = pd.read_parquet(bs.CACHE / 'draft_picks.parquet')
    dp = dp[dp['season'].isin(CLASSES) & dp['position'].isin(bs.SKILL)].dropna(subset=['gsis_id'])
    rows, unlinked = [], 0
    for _, r in dp.iterrows():
        c = col[(col['k'] == norm(r['pfr_player_name'])) & (col['s'] <= r['season'] - 1)]
        if (c['pos'] == r['position']).any(): c = c[c['pos'] == r['position']]
        if not len(c): unlinked += 1; continue
        f = c.sort_values('s').iloc[-1]                                    # final qualified college season
        rows.append({'pid': str(r['gsis_id']), 'cls': int(r['season']), 'name': r['pfr_player_name'], 'round': int(r['round']),
                     'ddom': float(f['ddom']), 'raw': float(f['raw']), 'col_season': int(f['s'])})
    df = pd.DataFrame(rows)
    g, _ = bs.load_games(); draft = rk.load_draft()
    rs = rk.rookie_seasons(g, draft)                                       # every rookie season 2015-2025
    tabs = {y: rk.fit_table(rs, [s for s in range(2015, 2026) if s != y]) for y in CLASSES}
    rsi = rs.set_index('pid')
    df = df[df['pid'].isin(rsi.index)].copy()                              # played at least one rookie game
    df['pos'] = df['pid'].map(rsi['pos']); df['tier'] = df['pid'].map(rsi['tier'])
    df['prior'] = [tabs[c][p][t] for c, p, t in zip(df['cls'], df['pos'], df['tier'])]
    if read_outcomes: df['actual'] = df['pid'].map(rsi['ppg'])
    return df, unlinked, len(dp)

def fit_b(d, col):
    x = d['prior'].to_numpy() * (d[col].to_numpy() / 100 - 0.5); y = d['actual'].to_numpy() - d['prior'].to_numpy()
    return float((x * y).sum() / (x * x).sum())

def rmse(e): return float(np.sqrt(np.mean(e ** 2)))

def main():
    ap = argparse.ArgumentParser(); m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument('--count', action='store_true'); m.add_argument('--run', action='store_true')
    a = ap.parse_args()
    lock = None
    if a.run: bs.PREREG = PREREG; lock = bs.require_locked_prereg()
    df, unlinked, total = build(read_outcomes=a.run)
    print(f"[COLLEGE] drafted skill players 2021-25: {total} · no qualified final college season: {unlinked} · "
          f"linked and played a rookie game: {len(df)} · by class {df['cls'].value_counts().sort_index().to_dict()} · "
          f"by position {df['pos'].value_counts().to_dict()}")
    if a.count: print('[COLLEGE] --count: no outcomes computed.'); return

    pred = {'base': df['prior'].to_numpy().copy(), 'ddom': np.zeros(len(df)), 'raw': np.zeros(len(df))}; bs_ = {}
    for c in CLASSES:                                                      # leave one class out
        tr, mk = df[df['cls'] != c], (df['cls'] == c).to_numpy()
        for col in ('ddom', 'raw'):
            b = fit_b(tr, col); bs_.setdefault(col, {})[c] = b
            pred[col][mk] = df.loc[mk, 'prior'].to_numpy() * (1 + b * (df.loc[mk, col].to_numpy() / 100 - 0.5))
    y = df['actual'].to_numpy(); E = {k: v - y for k, v in pred.items()}
    lift = 1 - rmse(E['ddom']) / rmse(E['base'])
    rng = np.random.default_rng(SEED); ge = 0
    for _ in range(SHUFFLES):
        f = rng.random(len(df)) < 0.5
        if 1 - rmse(np.where(f, E['base'], E['ddom'])) / rmse(np.where(f, E['ddom'], E['base'])) >= lift: ge += 1
    p = (ge + 1) / (SHUFFLES + 1)
    c_arr, p_arr = df['cls'].to_numpy(), df['pos'].to_numpy()
    sub = lambda mk: 1 - rmse(E['ddom'][mk]) / rmse(E['base'][mk])
    per_class = {int(c): sub(c_arr == c) for c in CLASSES}
    per_pos = {ps: sub(p_arr == ps) for ps in bs.SKILL if (p_arr == ps).any()}; pos_n = {ps: int((p_arr == ps).sum()) for ps in bs.SKILL}
    gates = {'size_>=2%': lift >= 0.02, 'p<0.05': p < 0.05,
             f'better_in_{MIN_CLASSES_BETTER}_of_5_classes': sum(v > 0 for v in per_class.values()) >= MIN_CLASSES_BETTER,
             'no_position_worse_than_-1%_(n>=30)': all(v >= -0.01 for k, v in per_pos.items() if pos_n[k] >= MIN_POS_N)}
    diffs = []                                                             # sub-test: raw error minus dDOM error
    for _ in range(BOOT):
        i = rng.integers(0, len(df), len(df)); diffs.append(rmse(E['raw'][i]) - rmse(E['ddom'][i]))
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    subtest = ('dDOM BEATS the raw dominator' if lo > 0 else 'the RAW dominator beats dDOM' if hi < 0 else 'NO CLEAR DIFFERENCE between dDOM and the raw dominator')
    out = {'lock': lock, 'n': int(len(df)), 'fitted_b': bs_, 'b_all_classes': {c: fit_b(df, c) for c in ('ddom', 'raw')},
           'rmse': {k: rmse(v) for k, v in E.items()}, 'mae': {k: float(np.mean(np.abs(v))) for k, v in E.items()},
           'primary_ddom_vs_draft_slot': {'lift': lift, 'p': p, 'per_class': per_class, 'per_position': per_pos, 'position_n': pos_n,
                                          'gates': gates, 'SHIP': all(gates.values())},
           'raw_vs_draft_slot_lift_reported': 1 - rmse(E['raw']) / rmse(E['base']),
           'subtest_ddom_vs_raw': {'raw_minus_ddom_rmse': rmse(E['raw']) - rmse(E['ddom']), 'range_95': [float(lo), float(hi)], 'VERDICT': subtest}}
    print(json.dumps(out, indent=2, default=float))
    (ROOT / 'data-cache' / 'college-signal-result.json').write_text(json.dumps(out, indent=2, default=float))

if __name__ == '__main__':
    main()
