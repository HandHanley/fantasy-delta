#!/usr/bin/env python3
"""
DELTA Rookie Baseline v2 — scripts/rookie-baseline-study.py
Pre-registration: docs/PREREG-rookie-baseline-v2.md

    python3 scripts/rookie-baseline-study.py --count   # counts only; computes NO errors
    python3 scripts/rookie-baseline-study.py --run     # refuses unless the pre-registration is committed

Outcome for both parts: rookie points per game over the games he played in his rookie season (the
rookie table's own definition; half PPR + TE premium). Classes 2015-2025; each class predicted from the
other ten (leave one class out).
PART A — drafted rookies
  today      the ROOKIE_PPG METHOD: median by position x five draft tiers (1-10, 11-32, 33-64, 65-105,
             106+), rows forced non-increasing — refitted on the other ten classes. The engine's literal
             constants cannot be the comparison: they were fitted on ALL of 2015-2025 (every class here)
             and their builder is not in the repo (the recipe gives 725 rookie seasons, not the 718 the
             engine comment cites, and reproduces 3 of 20 cells). Their in-sample error is reported only.
  candidate  a smooth MEDIAN curve per position:  PPG = a + b x ln(pick), fitted by least absolute
             deviations (b <= 0), floored at 0 — medians like the table, so the ONLY difference is
             smoothness. (A least-squares curve "won" on pure noise in the crash test: fantasy points are
             right-skewed, so any average beats any median on RMSE. Fixed before locking.)
  PRIMARY MEASURE: average miss (MAE — the ledger's headline, and what a median targets); the typical miss
             (RMSE) must not get worse.
  reported   the five tiers using AVERAGES vs MEDIANS — the separate "average or median?" question
PART B — undrafted rookies (no draft round; first NFL season = that year; played a game)
  today      the engine's fallback: a literal 8.0 x the "sat out two seasons" multiplier 0.672 = 5.376
             (its core; later engine adjustments cannot be rebuilt for past seasons)
  candidate  the MEDIAN rookie PPG of past undrafted rookies at his position
Games, scoring, IDs from scripts/blend-study.py; draft picks and the table recipe from
scripts/blend-study-rookies.py — imported unchanged.
"""
import argparse, importlib.util, json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import linprog

ROOT = Path(__file__).resolve().parent.parent
_s = importlib.util.spec_from_file_location('rk', ROOT / 'scripts' / 'blend-study-rookies.py')
rk = importlib.util.module_from_spec(_s); _s.loader.exec_module(rk); bs = rk.bs

PREREG = 'docs/PREREG-rookie-baseline-v2.md'
CLASSES = list(range(2015, 2026))
UDFA_TODAY = 8.0 * 0.672
MIN_CLASSES_BETTER, MIN_POS_N, SEED, SHUFFLES = 8, 30, 20260929, 2000

def build(read_outcomes):
    g, _ = bs.load_games(); draft = rk.load_draft()
    rs = rk.rookie_seasons(g, draft)
    rs = rs[rs['season'].isin(CLASSES)].copy(); rs['pick'] = rs['pid'].map(lambda p: draft[p][1])
    pl = pd.read_parquet(bs.CACHE / 'players.parquet', columns=['gsis_id', 'rookie_season', 'draft_round'])
    und = pl[pl['draft_round'].isna() & pl['rookie_season'].isin(CLASSES)].dropna(subset=['gsis_id'])
    first = dict(zip(und['gsis_id'].astype(str), und['rookie_season'].astype(int)))
    rows = []
    for pid, pg in g[g['pid'].isin(first)].groupby('pid'):
        y = first[pid]; r = pg[pg['season'] == y]
        if len(r) == 0 or pid in draft: continue
        pos = r['spos'].mode().iat[0]
        rows.append({'pid': pid, 'season': y, 'pos': pos, 'ppg': bs.bt_pts(r, pos).sum() / len(r)})
    ud = pd.DataFrame(rows)
    if not read_outcomes: rs = rs.drop(columns=['ppg']); ud = ud.drop(columns=['ppg'])
    return rs, ud

def rmse(e): return float(np.sqrt(np.mean(e ** 2)))
def mae(e): return float(np.mean(np.abs(e)))

def lad(x, y):
    """Median (least-absolute-deviation) line y = a + b x with b <= 0, solved exactly as a linear program."""
    n = len(x); c = np.r_[0, 0, np.ones(2 * n)]
    A = np.c_[np.ones(n), x, np.eye(n), -np.eye(n)]
    r = linprog(c, A_eq=A, b_eq=y, bounds=[(None, None), (None, 0)] + [(0, None)] * (2 * n), method='highs')
    return float(r.x[0]), float(r.x[1])

def compare(df, e0, e1, key):
    lift = 1 - mae(e1) / mae(e0)
    rng = np.random.default_rng(SEED); ge = 0
    for _ in range(SHUFFLES):
        f = rng.random(len(df)) < 0.5
        if 1 - mae(np.where(f, e0, e1)) / mae(np.where(f, e1, e0)) >= lift: ge += 1
    p = (ge + 1) / (SHUFFLES + 1)
    c, ps = df[key].to_numpy(), df['pos'].to_numpy()
    per_class = {int(y): 1 - mae(e1[c == y]) / mae(e0[c == y]) for y in CLASSES if (c == y).any()}
    per_pos = {q: 1 - mae(e1[ps == q]) / mae(e0[ps == q]) for q in bs.SKILL if (ps == q).any()}
    pos_n = {q: int((ps == q).sum()) for q in bs.SKILL}
    gates = {'size_>=2%_(MAE)': lift >= 0.02, 'p<0.05': p < 0.05, 'RMSE_not_worse': rmse(e1) <= rmse(e0),
             f'better_in_{MIN_CLASSES_BETTER}_of_11_classes': sum(v > 0 for v in per_class.values()) >= MIN_CLASSES_BETTER,
             'no_position_worse_than_-1%_(n>=30)': all(v >= -0.01 for k, v in per_pos.items() if pos_n[k] >= MIN_POS_N)}
    return {'n': int(len(df)), 'today_rmse': rmse(e0), 'candidate_rmse': rmse(e1), 'lift': lift, 'p': p,
            'today_mae': float(np.mean(np.abs(e0))), 'candidate_mae': float(np.mean(np.abs(e1))),
            'per_class': per_class, 'per_position': per_pos, 'position_n': pos_n, 'gates': gates, 'SHIP': all(gates.values())}

def main():
    ap = argparse.ArgumentParser(); m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument('--count', action='store_true'); m.add_argument('--run', action='store_true')
    a = ap.parse_args()
    lock = None
    if a.run: bs.PREREG = PREREG; lock = bs.require_locked_prereg()
    rs, ud = build(read_outcomes=a.run)
    print(f"[BASELINE] drafted rookie seasons: {len(rs)} · by class {rs['season'].value_counts().sort_index().to_dict()} · by position {rs['pos'].value_counts().to_dict()}")
    print(f"[BASELINE] undrafted rookie seasons: {len(ud)} · by class {ud['season'].value_counts().sort_index().to_dict()} · by position {ud['pos'].value_counts().to_dict()}")
    if a.count: print('[BASELINE] --count: no errors computed.'); return

    # PART A
    tab_pred = np.zeros(len(rs)); curve_pred = np.zeros(len(rs)); mean_pred = np.zeros(len(rs)); curves = {}
    for y in CLASSES:
        mk = (rs['season'] == y).to_numpy(); tr = rs[rs['season'] != y]
        tab = rk.fit_table(tr.assign(season=0), [0])
        tab_pred[mk] = [tab[p][t] for p, t in zip(rs.loc[mk, 'pos'], rs.loc[mk, 'tier'])]
        means = tr.groupby(['pos', 'tier'])['ppg'].mean().to_dict()
        mean_pred[mk] = [means.get((p, t), np.nan) for p, t in zip(rs.loc[mk, 'pos'], rs.loc[mk, 'tier'])]
        for p in bs.SKILL:
            tp = tr[tr['pos'] == p]; a0, b = lad(np.log(tp['pick'].to_numpy(float)), tp['ppg'].to_numpy(float)); curves.setdefault(y, {})[p] = (a0, b)
            sel = mk & (rs['pos'] == p).to_numpy()
            curve_pred[sel] = np.maximum(0, a0 + b * np.log(rs.loc[sel, 'pick']))
    y_ = rs['ppg'].to_numpy()
    partA = compare(rs, tab_pred - y_, curve_pred - y_, 'season')
    ok = ~np.isnan(mean_pred)
    partA['reported_average_vs_median_buckets'] = {'averages': {'mae': mae((mean_pred - y_)[ok]), 'rmse': rmse((mean_pred - y_)[ok])},
                                                   'medians': {'mae': mae((tab_pred - y_)[ok]), 'rmse': rmse((tab_pred - y_)[ok])}}
    import re
    src = (ROOT / 'delta-engine.js').read_text(); blk = src[src.index('const ROOKIE_PPG'):src.index('};', src.index('const ROOKIE_PPG'))]
    eng = {q: [float(x) for x in re.findall(r'[\d.]+', blk.split(q + ':')[1].split(']')[0])] for q in bs.SKILL}
    lit = np.array([eng[q][t] for q, t in zip(rs['pos'], rs['tier'])])
    partA['reported_engine_literal_constants_IN_SAMPLE'] = {'mae': mae(lit - y_), 'rmse': rmse(lit - y_)}
    partA['curve_all_classes'] = {p: dict(zip(('a', 'b'), lad(np.log(rs[rs['pos'] == p]['pick'].to_numpy(float)), rs[rs['pos'] == p]['ppg'].to_numpy(float)))) for p in bs.SKILL}
    # PART B
    ud_pred = np.zeros(len(ud))
    for y in CLASSES:
        mk = (ud['season'] == y).to_numpy(); tr = ud[ud['season'] != y]; mu = tr.groupby('pos')['ppg'].median().to_dict()
        ud_pred[mk] = [mu.get(p, UDFA_TODAY) for p in ud.loc[mk, 'pos']]
    yu = ud['ppg'].to_numpy()
    partB = compare(ud, np.full(len(ud), UDFA_TODAY) - yu, ud_pred - yu, 'season')
    partB['undrafted_baseline_all_classes'] = {'mean': ud.groupby('pos')['ppg'].mean().to_dict(), 'median': ud.groupby('pos')['ppg'].median().to_dict()}
    out = {'lock': lock, 'PART_A_drafted': partA, 'PART_B_undrafted': partB}
    print(json.dumps(out, indent=2, default=float))
    (ROOT / 'data-cache' / 'rookie-baseline-result.json').write_text(json.dumps(out, indent=2, default=float))

if __name__ == '__main__':
    main()
