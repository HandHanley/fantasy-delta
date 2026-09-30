#!/usr/bin/env python3
"""
DELTA Role-Entry Odds — scripts/role-entry-study.py
Pre-registration: docs/PREREG-role-entry.md

    python3 scripts/role-entry-study.py --count   # counts and coverage only; computes NO outcomes
    python3 scripts/role-entry-study.py --run     # refuses unless the pre-registration is committed

Every drafted QB/RB/WR/TE of 2015-2023 — busts included. HIT = at least one starter-level season in his
first three: top 12 QB / 24 RB / 24 WR / 12 TE in PPG among players with 8+ games that season (the
breakout studies' definition; half PPR + TE premium). Never played = no hit.
PART A — the odds. Per position, logit P(hit) = a + b x ln(pick), each class predicted from the other
         eight. Honest enough to show if the average calibration error across ten equal-size bins is no
         worse than a PERFECTLY honest model would show by chance on this many players: outcomes are
         simulated 2,000 times from the model's own odds, and the real error must sit at or below the 95th
         percentile. (A fixed 5-point limit failed perfectly honest noise in the crash test — with ~70
         players a bin, chance alone moves a bin about 4-5 points.) Reported: Brier score vs a position-only base rate; undrafted
         rookies' base rates.
PART B — does anything sharpen the odds beyond draft slot? Each adds ONE pooled term to Part A:
         B1 AGE at the start of the rookie season (7 Sep, the engine's rule), within position
         B2 ATHLETICISM: speed score (weight x 200 / forty^4), within position — RB/WR/TE with a forty,
            baseline refitted on the same players
         Reported only: dDOM (classes 2021-2023; too few to test).
Games, scoring, IDs: scripts/blend-study.py. College dDOM: scripts/college-signal-study.py (imported).
"""
import argparse, importlib.util, json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parent.parent
def _load(n, f):
    s = importlib.util.spec_from_file_location(n, ROOT / 'scripts' / f); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
cs = _load('cs', 'college-signal-study.py'); bs = cs.bs

PREREG = 'docs/PREREG-role-entry.md'
CLASSES = list(range(2015, 2024))
TOP = {'QB': 12, 'RB': 24, 'WR': 24, 'TE': 12}
CAL_SIMS = 2000
MIN_CLASSES_BETTER, MIN_POS_N, P_BAR, SEED, SHUFFLES = 6, 30, 0.025, 20260929, 2000

def starter_seasons(g):
    rows = []
    for (pid, y), sg in g.groupby(['pid', 'season']):
        pos = sg['spos'].mode().iat[0]
        if pos not in TOP or len(sg) < 8: continue
        rows.append((pid, y, pos, bs.bt_pts(sg, pos).sum() / len(sg)))
    t = pd.DataFrame(rows, columns=['pid', 'season', 'pos', 'ppg'])
    t['rank'] = t.groupby(['season', 'pos'])['ppg'].rank(ascending=False, method='first')
    return set(map(tuple, t[t['rank'] <= t['pos'].map(TOP)][['pid', 'season']].values))

def build(read_outcomes):
    dp = pd.read_parquet(bs.CACHE / 'draft_picks.parquet')
    dp = dp[dp['season'].isin(CLASSES) & dp['position'].isin(bs.SKILL)].dropna(subset=['gsis_id', 'pick']).copy()
    pl = pd.read_parquet(bs.CACHE / 'players.parquet', columns=['gsis_id', 'birth_date', 'rookie_season', 'draft_round', 'position'])
    bd = dict(zip(pl['gsis_id'].astype(str), pd.to_datetime(pl['birth_date'], errors='coerce')))
    cb = pd.read_parquet(bs.CACHE / 'combine.parquet')
    cb = cb.dropna(subset=['pfr_id']).drop_duplicates('pfr_id').set_index('pfr_id')
    df = pd.DataFrame({'pid': dp['gsis_id'].astype(str), 'cls': dp['season'].astype(int), 'pos': dp['position'],
                       'pick': dp['pick'].astype(float), 'pfr': dp['pfr_player_id'], 'name': dp['pfr_player_name']})
    df['age'] = [(pd.Timestamp(c, 9, 7) - bd.get(p)).days / 365.25 if pd.notna(bd.get(p)) else np.nan for p, c in zip(df['pid'], df['cls'])]
    fw = [(cb.at[f, 'forty'], cb.at[f, 'wt']) if f in cb.index else (np.nan, np.nan) for f in df['pfr']]
    df['forty'] = [a for a, _ in fw]; df['wt'] = [b for _, b in fw]
    df['speed'] = np.where(df['forty'].notna() & df['wt'].notna(), df['wt'] * 200 / df['forty'] ** 4, np.nan)
    und = pl[pl['draft_round'].isna() & pl['rookie_season'].isin(CLASSES) & pl['position'].isin(bs.SKILL)].dropna(subset=['gsis_id'])
    ud = pd.DataFrame({'pid': und['gsis_id'].astype(str), 'cls': und['rookie_season'].astype(int), 'pos': und['position']})
    if read_outcomes:
        g, _ = bs.load_games(); hits = starter_seasons(g)
        hit = lambda p, c: int(any((p, y) in hits for y in (c, c + 1, c + 2)))
        df['hit'] = [hit(p, c) for p, c in zip(df['pid'], df['cls'])]; ud['hit'] = [hit(p, c) for p, c in zip(ud['pid'], ud['cls'])]
    return df, ud

def fit_logit(X, y):
    def nll(w):
        z = X @ w; return float(np.sum(np.logaddexp(0, z) - y * z)) + 1e-4 * float(w @ w)
    return minimize(nll, np.zeros(X.shape[1]), method='BFGS').x

def design(d, extra=None):
    cols = []
    for p in bs.SKILL:
        m = (d['pos'] == p).to_numpy().astype(float); cols += [m, m * np.log(d['pick'].to_numpy())]
    if extra is not None: cols.append(d[extra].to_numpy())
    return np.column_stack(cols)

def loco(d, extra=None):
    pr = np.zeros(len(d))
    for c in CLASSES:
        tr, mk = d[d['cls'] != c], (d['cls'] == c).to_numpy()
        if not mk.any(): continue
        w = fit_logit(design(tr, extra), tr['hit'].to_numpy()); pr[mk] = 1 / (1 + np.exp(-design(d[mk], extra) @ w))
    return pr

def brier(p, y): return float(np.mean((p - y) ** 2))

def calibration(p, y, bins=10):
    q = np.quantile(p, np.linspace(0, 1, bins + 1)); idx = np.clip(np.searchsorted(q, p, side='right') - 1, 0, bins - 1)
    rows = [(float(p[idx == b].mean()), float(y[idx == b].mean()), int((idx == b).sum())) for b in range(bins) if (idx == b).any()]
    return float(sum(abs(a - o) * n for a, o, n in rows) / len(p)), rows

def zpos(d, col): return d.groupby('pos')[col].transform(lambda s: (s - s.mean()) / (s.std(ddof=0) or 1))

def addon(d, extra):
    d = d.copy(); d['z'] = zpos(d, extra)
    y = d['hit'].to_numpy(); p0 = loco(d); p1 = loco(d, 'z')
    e0, e1 = (p0 - y) ** 2, (p1 - y) ** 2; lift = 1 - e1.mean() / e0.mean()
    rng = np.random.default_rng(SEED); ge = 0
    for _ in range(SHUFFLES):
        f = rng.random(len(d)) < 0.5
        if 1 - np.where(f, e0, e1).mean() / np.where(f, e1, e0).mean() >= lift: ge += 1
    pv = (ge + 1) / (SHUFFLES + 1)
    c, ps = d['cls'].to_numpy(), d['pos'].to_numpy()
    per_class = {int(k): 1 - e1[c == k].mean() / e0[c == k].mean() for k in CLASSES if (c == k).any()}
    per_pos = {q: 1 - e1[ps == q].mean() / e0[ps == q].mean() for q in bs.SKILL if (ps == q).any()}
    pos_n = {q: int((ps == q).sum()) for q in bs.SKILL}
    w = fit_logit(design(d, 'z'), y)
    gates = {'size_>=2%_(Brier)': lift >= 0.02, f'p<{P_BAR}': pv < P_BAR,
             f'better_in_{MIN_CLASSES_BETTER}_of_9_classes': sum(v > 0 for v in per_class.values()) >= MIN_CLASSES_BETTER,
             'no_position_worse_than_-1%_(n>=30)': all(v >= -0.01 for k, v in per_pos.items() if pos_n[k] >= MIN_POS_N)}
    return {'n': int(len(d)), 'hits': int(y.sum()), 'brier_draft_only': float(e0.mean()), 'brier_with_term': float(e1.mean()),
            'lift': lift, 'p': pv, 'term_coefficient_all_classes': float(w[-1]), 'per_class': per_class,
            'per_position': per_pos, 'position_n': pos_n, 'gates': gates, 'CONFIRMED': all(gates.values())}

def main():
    ap = argparse.ArgumentParser(); m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument('--count', action='store_true'); m.add_argument('--run', action='store_true')
    a = ap.parse_args()
    lock = None
    if a.run: bs.PREREG = PREREG; lock = bs.require_locked_prereg()
    df, ud = build(read_outcomes=a.run)
    ath = df[df['pos'].isin(['RB', 'WR', 'TE']) & df['speed'].notna()]
    print(f"[ROLE] drafted 2015-2023: {len(df)} · by position {df['pos'].value_counts().to_dict()} · with age {int(df['age'].notna().sum())} · "
          f"RB/WR/TE with a speed score {len(ath)} of {int(df['pos'].isin(['RB','WR','TE']).sum())} · undrafted rookies {len(ud)}")
    if a.count: print('[ROLE] --count: no outcomes computed.'); return

    y = df['hit'].to_numpy(); pA = loco(df)
    base = np.array([df[(df['cls'] != c) & (df['pos'] == p)]['hit'].mean() for c, p in zip(df['cls'], df['pos'])])
    cal, rows = calibration(pA, y)
    sim_rng = np.random.default_rng(SEED)
    sims = [calibration(pA, (sim_rng.random(len(pA)) < pA).astype(float))[0] for _ in range(CAL_SIMS)]
    cal_limit = float(np.percentile(sims, 95))
    wA = fit_logit(design(df), y)
    curve = {p: {'a': float(wA[2 * i]), 'b': float(wA[2 * i + 1])} for i, p in enumerate(bs.SKILL)}
    def odds(p, pick): c = curve[p]; return float(1 / (1 + np.exp(-(c['a'] + c['b'] * np.log(pick)))))
    table = {p: {k: round(odds(p, k), 3) for k in (5, 20, 45, 80, 120, 180, 240)} for p in bs.SKILL}
    partA = {'n': int(len(df)), 'hits': int(y.sum()), 'hit_rate_by_position': df.groupby('pos')['hit'].mean().to_dict(),
             'brier_curve_loco': brier(pA, y), 'brier_position_only_loco': brier(base, y),
             'calibration_error': cal, 'calibration_limit_95th_pct_of_honest_model': cal_limit,
             'calibration_bins_(predicted,actual,n)': rows,
             'HONEST_ENOUGH_TO_SHOW': cal <= cal_limit, 'curve_all_classes': curve, 'odds_at_picks': table,
             'undrafted_hit_rate_by_position': ud.groupby('pos')['hit'].agg(['mean', 'count']).to_dict('index')}
    partB = {'B1_age': addon(df.dropna(subset=['age']), 'age'),
             'B2_athleticism_RB_WR_TE': addon(ath, 'speed')}
    col = cs.college(); import re
    dd = df[df['cls'] >= 2021].copy(); dd['k'] = dd['name'].map(cs.norm)
    dm = {}
    for i, r in dd.iterrows():
        c = col[(col['k'] == r['k']) & (col['s'] <= r['cls'] - 1)]
        if (c['pos'] == r['pos']).any(): c = c[c['pos'] == r['pos']]
        if len(c): dm[i] = float(c.sort_values('s').iloc[-1]['ddom'])
    dd = dd.loc[list(dm)]; dd['ddom'] = pd.Series(dm)
    out = {'lock': lock, 'PART_A_odds': partA, 'PART_B_addons': partB}
    try: out['reported_only_dDOM_2021_2023'] = {k: v for k, v in addon(dd, 'ddom').items() if k not in ('gates', 'CONFIRMED')}
    except Exception as e: out['reported_only_dDOM_2021_2023'] = f'not computable: {e}'
    print(json.dumps(out, indent=2, default=float))
    (ROOT / 'data-cache' / 'role-entry-result.json').write_text(json.dumps(out, indent=2, default=float))

if __name__ == '__main__':
    main()
