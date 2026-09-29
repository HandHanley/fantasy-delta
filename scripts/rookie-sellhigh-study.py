#!/usr/bin/env python3
"""
DELTA Rookie Sell-High Test — scripts/rookie-sellhigh-study.py
Pre-registration: docs/PREREG-rookie-sellhigh.md

    python3 scripts/rookie-sellhigh-study.py --count   # classes and breakout counts from PRICE only; no outcomes
    python3 scripts/rookie-sellhigh-study.py --run     # refuses unless the pre-registration is committed

Question (owner, 28 Sep 2026): when a rookie's value spikes during his rookie year, does it fall back?
  Breakout = top 20% of his class by price rise from before Week 1 to the sell point, AND in the
  top 150 players by market value at the sell point (all positions; fantasy-relevant — added before
  any outcome was read, after near-zero risers like Jaren Hall 3 -> 108 qualified on rise alone).
  Price only — exactly what a manager could see when deciding to sell.
  Outcome  = his price change from the sell point to the end of his SECOND regular season,
             compared with the other rookies in his class.
Primary sell point: end of the rookie regular season. Reported: after Week 8, next preseason.
Classes 2020-2024 (the 2025 class has no year-2 end yet). Prices: DynastyProcess value_2qb (superflex),
L(v) = log(v + 100); loading, dates and the nflverse ID join imported from scripts/market-form-study.py
(verified 3,370/3,370 prices, 729/729 links). Draft classes from scripts/blend-study-rookies.py.
"""
import argparse, importlib.util, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
def _load(n, f):
    s = importlib.util.spec_from_file_location(n, ROOT / 'scripts' / f); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
mf = _load('mf', 'market-form-study.py'); rk = mf.rk; bs = mf.bs

PREREG = 'docs/PREREG-rookie-sellhigh.md'
CLASSES = [2020, 2021, 2022, 2023, 2024]
BREAKOUT_SHARE = 0.20
TOP_VALUE = 150
MAX_LAG = 31          # days after the target date; class 2020's season-end snapshot is 28 days late (archive gap)
SEED, BOOT = 20260928, 2000

def snapshots(prices):
    dates = sorted(prices['scrape_date'].unique())
    g = pd.read_csv(bs.CACHE / 'games.csv', usecols=['season', 'game_type', 'week', 'gameday']); g = g[g['game_type'] == 'REG']
    wk = lambda y, w, f: g[(g['season'] == y) & (g['week'] == w)]['gameday'].agg(f)
    last = lambda y: int(g[g['season'] == y]['week'].max())
    after = lambda d0: next((d for d in dates if d > d0 and (pd.Timestamp(d) - pd.Timestamp(d0)).days <= MAX_LAG), None)
    before = lambda y: ([d for d in dates if f'{y}-08-01' <= d < wk(y, 1, 'min')] or [None])[-1]
    return {y: {'pre': before(y), 'w8': after(wk(y, 8, 'max')), 'end': after(wk(y, last(y), 'max')),
                'next_pre': before(y + 1), 'y2_end': after(wk(y + 1, last(y + 1), 'max'))} for y in CLASSES}

def build(read_future):
    prices = mf.load_prices(); draft = rk.load_draft()
    by = {d: s.dropna(subset=['pid']).drop_duplicates('pid').set_index('pid') for d, s in prices.groupby('scrape_date')}
    rank_at = {d: s['value_2qb'].rank(ascending=False, method='first') for d, s in by.items()}   # all skill players
    snaps = snapshots(prices); rows = []
    for y in CLASSES:
        sn = snaps[y]; pids = [p for p, (s, _) in draft.items() if s == y]
        for p in pids:
            if p not in by[sn['pre']].index: continue
            row = {'pid': p, 'cls': y, 'pos': by[sn['pre']].at[p, 'pos'], 'name': by[sn['pre']].at[p, 'player'],
                   'v_pre': float(by[sn['pre']].at[p, 'value_2qb'])}
            for k in ('w8', 'end', 'next_pre'):
                row['v_' + k] = float(by[sn[k]].at[p, 'value_2qb']) if p in by[sn[k]].index else 0.0
                row['rank_' + k] = float(rank_at[sn[k]].get(p, 9999))
            if read_future:
                row['v_y2_end'] = float(by[sn['y2_end']].at[p, 'value_2qb']) if p in by[sn['y2_end']].index else 0.0
            rows.append(row)
    df = pd.DataFrame(rows)
    for k in ('w8', 'end', 'next_pre'):
        df['rise_' + k] = mf.L(df['v_' + k]) - mf.L(df['v_pre'])
        df['brk_' + k] = (df.groupby('cls')['rise_' + k].rank(ascending=False, pct=True, method='first') <= BREAKOUT_SHARE) \
                         & (df['rank_' + k] <= TOP_VALUE)
    return df, snaps

def main():
    ap = argparse.ArgumentParser(); m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument('--count', action='store_true'); m.add_argument('--run', action='store_true')
    a = ap.parse_args()
    lock = None
    if a.run: bs.PREREG = PREREG; lock = bs.require_locked_prereg()
    df, snaps = build(read_future=a.run)
    for y in CLASSES: print(f"[SELLHIGH] {y}: " + ' · '.join(f"{k} {v}" for k, v in snaps[y].items()))
    print(f"[SELLHIGH] rookies priced before Week 1: {len(df)} · by class {df['cls'].value_counts().sort_index().to_dict()}")
    print(f"[SELLHIGH] breakouts (top 20% by rise AND top {TOP_VALUE} by value): after W8 {int(df['brk_w8'].sum())} · "
          f"season end {int(df['brk_end'].sum())} · next preseason {int(df['brk_next_pre'].sum())}")
    if a.count: print('[SELLHIGH] --count: no year-2 prices read, no outcomes computed.'); return

    out = {'lock': lock, 'sell_points': {}}
    rng = np.random.default_rng(SEED)
    for k in ('end', 'w8', 'next_pre'):
        f = np.asarray(mf.L(df['v_y2_end']) - mf.L(df['v_' + k]), dtype=float); b = df['brk_' + k].to_numpy()
        diff = float(f[b].mean() - f[~b].mean())
        boots = []
        for _ in range(BOOT):
            idx = rng.integers(0, len(df), len(df)); bb, ff = b[idx], f[idx]
            if bb.any() and (~bb).any(): boots.append(ff[bb].mean() - ff[~bb].mean())
        lo, hi = np.percentile(boots, [2.5, 97.5])
        slope = float(np.polyfit(df['rise_' + k].to_numpy(), f, 1)[0])
        pct = lambda x: float(np.exp(x) - 1)
        rec = {'n_breakouts': int(b.sum()), 'breakout_mean_change': pct(f[b].mean()), 'others_mean_change': pct(f[~b].mean()),
               'difference_log': diff, 'difference_range_95_log': [float(lo), float(hi)],
               'share_of_breakouts_that_lost_value': float((f[b] < 0).mean()), 'slope_future_on_rise': slope,
               'breakouts': sorted(((df['name'].iat[i], int(df['cls'].iat[i]), round(pct(f[i]), 3)) for i in np.where(b)[0]), key=lambda t: t[2])}
        out['sell_points'][k] = rec
    e = out['sell_points']['end']
    rel = e['difference_range_95_log'][1] < 0; absl = e['breakout_mean_change'] < 0
    out['VERDICT'] = ('SUPPORTED — breakout rookies lose value after their rookie year, and lose it relative to other rookies' if rel and absl else
                      'RELATIVE ONLY — breakouts grow slower than other rookies but do not lose value on average' if rel else
                      'NOT SUPPORTED — breakouts do not clearly give back value relative to other rookies')
    print(json.dumps(out, indent=2, default=float))
    (ROOT / 'data-cache' / 'rookie-sellhigh-result.json').write_text(json.dumps(out, indent=2, default=float))

if __name__ == '__main__':
    main()
