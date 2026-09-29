#!/usr/bin/env python3
"""
DELTA Pedigree Gap — scripts/pedigree-study.py
Pre-registration: docs/PREREG-pedigree-gap.md

    python3 scripts/pedigree-study.py --count   # group sizes from rookie-year stats + draft only; no outcomes
    python3 scripts/pedigree-study.py --run     # refuses unless the pre-registration is committed

After one season, does the market weigh draft pedigree right? Decision point: the last price before the
player's SECOND season. Outcome: his price change from there to the end of his THIRD regular season —
a window no DELTA study has used — compared with rookies of the SAME STARTING PRICE: the change is
measured against a line fitted on all other rookies (change vs starting price), because on random prices
higher starting prices fall and lower ones rise, which a plain group-vs-rest gap mistakes for mispricing
(caught by the crash test before locking).
  THE NAME      rounds 1-2, rookie PPG in the bottom half of his class's drafted rookies at his position
  THE PRODUCER  rounds 3+,  rookie PPG in the top third of his class's drafted rookies at his position
Classes 2020-2023. Prices, dates and the ID join from scripts/market-form-study.py; games (live DNP rule),
scoring and IDs from scripts/blend-study.py; draft from scripts/blend-study-rookies.py — imported unchanged.
"""
import argparse, importlib.util, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
def _load(n, f):
    s = importlib.util.spec_from_file_location(n, ROOT / 'scripts' / f); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
mf = _load('mf', 'market-form-study.py'); rk = mf.rk; bs = mf.bs

PREREG = 'docs/PREREG-pedigree-gap.md'
CLASSES = [2020, 2021, 2022, 2023]
SEED, BOOT = 20260929, 2000

def snapshots(prices):
    dates = sorted(prices['scrape_date'].unique())
    g = pd.read_csv(bs.CACHE / 'games.csv', usecols=['season', 'game_type', 'week', 'gameday']); g = g[g['game_type'] == 'REG']
    out = {}
    for y in CLASSES:
        w1 = g[(g['season'] == y + 1) & (g['week'] == 1)]['gameday'].min()
        lw = int(g[g['season'] == y + 2]['week'].max()); e = g[(g['season'] == y + 2) & (g['week'] == lw)]['gameday'].max()
        out[y] = {'decision': [d for d in dates if f'{y+1}-08-01' <= d < w1][-1],
                  'outcome': next(d for d in dates if d > e and (pd.Timestamp(d) - pd.Timestamp(e)).days <= 10)}
    return out

def build(read_future):
    games, _ = bs.load_games(); draft = rk.load_draft()
    dp = pd.read_parquet(bs.CACHE / 'draft_picks.parquet').dropna(subset=['gsis_id'])
    rnd = dict(zip(dp['gsis_id'].astype(str), dp['round']))
    prices = mf.load_prices(); snaps = snapshots(prices)
    by = {d: s.dropna(subset=['pid']).drop_duplicates('pid').set_index('pid') for d, s in prices.groupby('scrape_date')}
    rows = []
    for y in CLASSES:
        dec = by[snaps[y]['decision']]; out_s = by[snaps[y]['outcome']] if read_future else None
        for p, (s, _) in draft.items():
            if s != y or p not in dec.index: continue
            pos = dec.at[p, 'pos']
            gy = games[(games['pid'] == p) & (games['season'] == y)]
            ppg = float(bs.bt_pts(gy, pos).sum() / len(gy)) if len(gy) else 0.0
            r = {'pid': p, 'cls': y, 'pos': pos, 'name': dec.at[p, 'player'], 'round': rnd.get(p, 9), 'ppg': ppg,
                 'v_dec': float(dec.at[p, 'value_2qb'])}
            if read_future: r['v_out'] = float(out_s.at[p, 'value_2qb']) if p in out_s.index else 0.0
            rows.append(r)
    df = pd.DataFrame(rows)
    df['pct'] = df.groupby(['cls', 'pos'])['ppg'].rank(pct=True, method='average')
    df['name_grp'] = (df['round'] <= 2) & (df['pct'] <= 0.5)
    df['producer'] = (df['round'] >= 3) & (df['pct'] > 2 / 3)
    return df, snaps

def main():
    ap = argparse.ArgumentParser(); m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument('--count', action='store_true'); m.add_argument('--run', action='store_true')
    a = ap.parse_args()
    lock = None
    if a.run: bs.PREREG = PREREG; lock = bs.require_locked_prereg()
    df, snaps = build(read_future=a.run)
    for y in CLASSES: print(f"[PEDIGREE] {y}: decision {snaps[y]['decision']} · outcome {snaps[y]['outcome']}")
    print(f"[PEDIGREE] rookies priced at the decision point: {len(df)} · THE NAME {int(df['name_grp'].sum())} · "
          f"THE PRODUCER {int(df['producer'].sum())} · by class {df['cls'].value_counts().sort_index().to_dict()}")
    if a.count: print('[PEDIGREE] --count: no year-3 prices read, no outcomes computed.'); return

    f = np.asarray(mf.L(df['v_out']) - mf.L(df['v_dec']), dtype=float)
    rng = np.random.default_rng(SEED); res = {}
    for grp in ('name_grp', 'producer'):
        g_ = df[grp].to_numpy(); x = np.asarray(mf.L(df['v_dec']), dtype=float)
        def effect(gg, ff, xx):                               # group's average gap to the price-matched line
            b, a0 = np.polyfit(xx[~gg], ff[~gg], 1)
            return float((ff[gg] - (a0 + b * xx[gg])).mean())
        est = effect(g_, f, x); boots = []
        for _ in range(BOOT):
            i = rng.integers(0, len(df), len(df)); gg, ff, xx = g_[i], f[i], x[i]
            if gg.any() and (~gg).sum() > 2: boots.append(effect(gg, ff, xx))
        lo, hi = np.percentile(boots, [2.5, 97.5])
        verdict = ('MARKET OVERPRICES — a sell signal' if hi < 0 else 'MARKET UNDERPRICES — a buy signal' if lo > 0 else 'PRICED ABOUT RIGHT')
        pct = lambda x: float(np.exp(x) - 1)
        res['THE NAME' if grp == 'name_grp' else 'THE PRODUCER'] = {
            'tier': 'PRIMARY' if grp == 'name_grp' else 'REPORTED ONLY (22 of 38 overlap Study 1 breakouts whose year-2 prices were seen)',
            'n': int(g_.sum()), 'group_change': pct(f[g_].mean()), 'rest_change': pct(f[~g_].mean()),
            'difference_log': est, 'range_95_log': [float(lo), float(hi)], 'VERDICT': verdict,
            'members': sorted(((df['name'].iat[i], int(df['cls'].iat[i]), round(pct(f[i]), 2)) for i in np.where(g_)[0]), key=lambda t: t[2])}
    out = {'lock': lock, 'n_rookies': int(len(df)), 'groups': res}
    print(json.dumps(out, indent=2, default=float))
    (ROOT / 'data-cache' / 'pedigree-result.json').write_text(json.dumps(out, indent=2, default=float))

if __name__ == '__main__':
    main()
