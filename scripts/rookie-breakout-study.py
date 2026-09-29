#!/usr/bin/env python3
"""
DELTA Rookie Breakouts: Which Ones Hold Up? — scripts/rookie-breakout-study.py
Pre-registration: docs/PREREG-rookie-breakout.md

    python3 scripts/rookie-breakout-study.py --count   # breakouts from ROOKIE-YEAR stats only; no outcomes
    python3 scripts/rookie-breakout-study.py --run     # refuses unless the pre-registration is committed

Unseen evidence on purpose: Study 1 (prices, classes 2020-24) showed its 57 breakouts' outcomes. This
study uses PRODUCTION, not price, and ten classes (2015-2024).
  Breakout  = drafted rookie, 8+ games, rookie-year PPG in the top 12 QB / 24 RB / 24 WR / 12 TE of
              all players at his position with 8+ games that season.
  Outcome   = log(year-2 PPG / rookie PPG), year 2 with 4+ games (fewer: excluded and counted).
  Traits    = TD SHARE (share of rookie points from touchdowns)      — primary, predicted to fade more
              VOLUME (targets + carries per game; QBs add pass attempts) — primary, predicted to hold more
              RUNNING BACK (vs every other position)                  — secondary, hinted by Study 1's list
              DAY-ONE-OR-TWO PICK (rounds 1-2 vs later)               — secondary, hinted by Study 1's list
Games, scoring (half PPR + TE premium) and IDs from scripts/blend-study.py; targets and carries from
scripts/usage-study.py; draft picks from scripts/blend-study-rookies.py — all imported unchanged.
"""
import argparse, importlib.util, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
def _load(n, f):
    s = importlib.util.spec_from_file_location(n, ROOT / 'scripts' / f); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
us = _load('us', 'usage-study.py'); rk = us.rk; bs = us.bs

PREREG = 'docs/PREREG-rookie-breakout.md'
CLASSES = list(range(2015, 2025))
TOP = {'QB': 12, 'RB': 24, 'WR': 24, 'TE': 12}
MIN_G1, MIN_G2 = 8, 4
SEED, BOOT = 20260929, 2000

def load(g):
    g = us.load_usage(g)
    att = []
    for y in bs.YEARS:
        w = pd.read_parquet(bs.CACHE / f'w{y}.parquet', columns=['player_id', 'season', 'week', 'season_type', 'attempts'])
        att.append(w[w['season_type'] == 'REG'])
    a = pd.concat(att); a = pd.DataFrame({'pid': a['player_id'].astype(str), 'season': a['season'].astype(int),
                                          'week': a['week'].astype(int), 'att': a['attempts'].fillna(0).astype(float)})
    g = g.merge(a, on=['pid', 'season', 'week'], how='left'); g['att'] = g['att'].fillna(0.0)
    return g

def season_table(g):
    rows = []
    for (pid, y), sg in g.groupby(['pid', 'season']):
        pos = sg['spos'].mode().iat[0]
        if pos not in TOP: continue
        pts = bs.bt_pts(sg, pos); n = len(sg); tot = pts.sum()
        td = (sg['rt'] * 6 + sg['ret'] * 6 + sg['pt'] * 4).sum()
        vol = (sg['tgt'].sum() + sg['car'].sum() + (sg['att'].sum() if pos == 'QB' else 0)) / n
        rows.append({'pid': pid, 'season': y, 'pos': pos, 'g': n, 'ppg': tot / n,
                     'td_share': (td / tot) if tot > 0 else np.nan, 'vol': vol})
    return pd.DataFrame(rows)

def build(g, read_future):
    st = season_table(load(g)); draft = rk.load_draft()
    dp = pd.read_parquet(bs.CACHE / 'draft_picks.parquet').dropna(subset=['gsis_id'])
    rnd = dict(zip(dp['gsis_id'].astype(str), dp['round']))
    q = st[st['g'] >= MIN_G1].copy()
    q['rank'] = q.groupby(['season', 'pos'])['ppg'].rank(ascending=False, method='first')
    q = q[q['rank'] <= q['pos'].map(TOP)]
    brk = q[q.apply(lambda r: r['pid'] in draft and draft[r['pid']][0] == r['season'] and r['season'] in CLASSES, axis=1)].copy()
    brk['rb'] = (brk['pos'] == 'RB').astype(float)
    brk['early_pick'] = brk['pid'].map(lambda p: 1.0 if rnd.get(p, 9) <= 2 else 0.0)
    if read_future:
        y2 = st.set_index(['pid', 'season'])
        def outcome(r):
            k = (r['pid'], r['season'] + 1)
            if k not in y2.index or y2.at[k, 'g'] < MIN_G2 or y2.at[k, 'ppg'] <= 0: return np.nan
            return float(np.log(y2.at[k, 'ppg'] / r['ppg']))
        brk['out'] = brk.apply(outcome, axis=1)
    return brk

def z_within_pos(d, col):
    return d.groupby('pos')[col].transform(lambda s: (s - s.mean()) / (s.std(ddof=0) or 1))

def main():
    ap = argparse.ArgumentParser(); m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument('--count', action='store_true'); m.add_argument('--run', action='store_true')
    a = ap.parse_args()
    lock = None
    if a.run: bs.PREREG = PREREG; lock = bs.require_locked_prereg()
    g, _ = bs.load_games()
    brk = build(g, read_future=a.run)
    print(f"[BREAKOUT] rookie breakouts 2015-2024: {len(brk)} · by class {brk['season'].value_counts().sort_index().to_dict()} · "
          f"by position {brk['pos'].value_counts().to_dict()} · rounds 1-2: {int(brk['early_pick'].sum())}")
    if a.count: print('[BREAKOUT] --count: no year-2 stats read, no outcomes computed.'); return

    d = brk.dropna(subset=['out', 'td_share']).copy()
    excluded = int(len(brk) - len(d))
    d['z_td'] = z_within_pos(d, 'td_share'); d['z_vol'] = z_within_pos(d, 'vol')
    rng = np.random.default_rng(SEED); idx_all = np.arange(len(d))
    def slope(dd, col): return float(np.polyfit(dd[col].to_numpy(), dd['out'].to_numpy(), 1)[0])
    def gapb(dd, col): return float(dd.loc[dd[col] == 1, 'out'].mean() - dd.loc[dd[col] == 0, 'out'].mean())
    tests = {'td_share': ('slope', 'z_td', -1), 'volume': ('slope', 'z_vol', +1),
             'running_back': ('gap', 'rb', -1), 'early_pick': ('gap', 'early_pick', +1)}
    res = {}
    for name, (kind, col, sign) in tests.items():
        est = slope(d, col) if kind == 'slope' else gapb(d, col); boots = []
        for _ in range(BOOT):
            dd = d.iloc[rng.choice(idx_all, len(d), replace=True)]
            try: boots.append(slope(dd, col) if kind == 'slope' else gapb(dd, col))
            except Exception: pass
        lo, hi = np.nanpercentile(boots, [2.5, 97.5])
        confirmed = (hi < 0) if sign < 0 else (lo > 0)
        res[name] = {'estimate_log': est, 'range_95_log': [float(lo), float(hi)], 'predicted_direction': 'fade' if sign < 0 else 'hold',
                     'CONFIRMED': bool(confirmed), 'tier': 'primary' if name in ('td_share', 'volume') else 'secondary (hinted by Study 1)'}
    pct = lambda x: float(np.exp(x) - 1)
    out = {'lock': lock, 'n_breakouts': int(len(brk)), 'n_graded': int(len(d)), 'excluded_under_4_games_in_year_2': excluded,
           'average_year2_change': pct(d['out'].mean()), 'share_that_fell': float((d['out'] < 0).mean()),
           'by_position_average_change': {p: pct(v) for p, v in d.groupby('pos')['out'].mean().items()},
           'traits': res}
    print(json.dumps(out, indent=2, default=float))
    (ROOT / 'data-cache' / 'rookie-breakout-result.json').write_text(json.dumps(out, indent=2, default=float))

if __name__ == '__main__':
    main()
