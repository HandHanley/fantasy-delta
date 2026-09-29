#!/usr/bin/env python3
"""
DELTA Rookie Volume Test On Fresh Classes — scripts/rookie-volume-study.py
Pre-registration: docs/PREREG-rookie-volume.md

    python3 scripts/rookie-volume-study.py --count   # breakouts from ROOKIE-YEAR stats only; no outcomes
    python3 scripts/rookie-volume-study.py --run     # refuses unless the pre-registration is committed

Study 2 (docs/PREREG-rookie-breakout.md, 2015-2024) found, against its prediction, that breakout
rookies with heavier volume fell MORE in year two (-8% per step up). A pattern found that way needs
fresh data. This tests exactly that direction on the 1999-2002 and 2009-2014 classes — never used by
any DELTA study (2003-2008 have no target data, so volume cannot be measured fairly).
Same breakout definition, volume measure and outcome as Study 2. Differences, disclosed: no snap counts
before 2012, so a game counts when a stat was recorded; players link by nflverse ID where the draft
file carries one.
"""
import argparse, importlib.util, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
_s = importlib.util.spec_from_file_location('bs1', ROOT / 'scripts' / 'blend-study.py')
bs = importlib.util.module_from_spec(_s); _s.loader.exec_module(bs)

PREREG = 'docs/PREREG-rookie-volume.md'
CLASSES = [1999, 2000, 2001, 2002, 2009, 2010, 2011, 2012, 2013, 2014]
TOP = {'QB': 12, 'RB': 24, 'WR': 24, 'TE': 12}
MIN_G1, MIN_G2 = 8, 4
SEED, BOOT = 20260929, 2000

def games(years):
    fr = []
    for y in years:
        w = pd.read_parquet(bs.fetch(f'{bs.REL}/stats_player/stats_player_week_{y}.parquet', bs.CACHE / f'w{y}.parquet'))
        w = w[w['season_type'] == 'REG']
        fr.append(pd.DataFrame({
            'pid': w['player_id'].astype(str), 'season': w['season'].astype(int), 'week': w['week'].astype(int), 'pos': w['position'],
            'py': bs.num(w, 'passing_yards'), 'pt': bs.num(w, 'passing_tds'), 'pi': bs.num(w, 'passing_interceptions'),
            'ry': bs.num(w, 'rushing_yards'), 'rt': bs.num(w, 'rushing_tds'), 'rec': bs.num(w, 'receptions'),
            'rey': bs.num(w, 'receiving_yards'), 'ret': bs.num(w, 'receiving_tds'),
            'tgt': bs.num(w, 'targets'), 'car': bs.num(w, 'carries'), 'att': bs.num(w, 'attempts')}))
    g = pd.concat(fr, ignore_index=True)
    prod = g[['py', 'pt', 'pi', 'ry', 'rt', 'rec', 'rey', 'ret', 'tgt', 'car', 'att']].abs().sum(axis=1) > 0
    return g[prod].copy()                                   # a game counts when a stat was recorded

def season_table(g):
    rows = []
    for (pid, y), sg in g.groupby(['pid', 'season']):
        pos = sg['pos'].mode().iat[0] if sg['pos'].notna().any() else None
        if pos not in TOP: continue
        pts = bs.bt_pts(sg, pos); n = len(sg); tot = pts.sum()
        td = (sg['rt'] * 6 + sg['ret'] * 6 + sg['pt'] * 4).sum()
        vol = (sg['tgt'].sum() + sg['car'].sum() + (sg['att'].sum() if pos == 'QB' else 0)) / n
        rows.append({'pid': pid, 'season': y, 'pos': pos, 'g': n, 'ppg': tot / n,
                     'td_share': (td / tot) if tot > 0 else np.nan, 'vol': vol})
    return pd.DataFrame(rows)

def build(read_future):
    years = sorted(set(CLASSES) | ({c + 1 for c in CLASSES} if read_future else set()))
    st = season_table(games(years))
    dp = pd.read_parquet(bs.fetch(f'{bs.REL}/draft_picks/draft_picks.parquet', bs.CACHE / 'draft_picks.parquet')).dropna(subset=['gsis_id'])
    dyear = dict(zip(dp['gsis_id'].astype(str), dp['season'].astype(int)))
    q = st[(st['g'] >= MIN_G1) & st['season'].isin(CLASSES)].copy()
    q['rank'] = q.groupby(['season', 'pos'])['ppg'].rank(ascending=False, method='first')
    q = q[q['rank'] <= q['pos'].map(TOP)]
    brk = q[q.apply(lambda r: dyear.get(r['pid']) == r['season'], axis=1)].copy()
    if read_future:
        y2 = st.set_index(['pid', 'season'])
        def outcome(r):
            k = (r['pid'], r['season'] + 1)
            if k not in y2.index or y2.at[k, 'g'] < MIN_G2 or y2.at[k, 'ppg'] <= 0: return np.nan
            return float(np.log(y2.at[k, 'ppg'] / r['ppg']))
        brk['out'] = brk.apply(outcome, axis=1)
    return brk

def main():
    ap = argparse.ArgumentParser(); m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument('--count', action='store_true'); m.add_argument('--run', action='store_true')
    a = ap.parse_args()
    lock = None
    if a.run: bs.PREREG = PREREG; lock = bs.require_locked_prereg()
    brk = build(read_future=a.run)
    print(f"[VOLUME] rookie breakouts: {len(brk)} · by class {brk['season'].value_counts().sort_index().to_dict()} · "
          f"by position {brk['pos'].value_counts().to_dict()}")
    if a.count: print('[VOLUME] --count: no year-2 stats read, no outcomes computed.'); return

    d = brk.dropna(subset=['out']).copy()
    d['z_vol'] = d.groupby('pos')['vol'].transform(lambda s: (s - s.mean()) / (s.std(ddof=0) or 1))
    d['z_td'] = d.groupby('pos')['td_share'].transform(lambda s: (s - s.mean()) / (s.std(ddof=0) or 1))
    slope = lambda dd, c: float(np.polyfit(dd[c].to_numpy(), dd['out'].to_numpy(), 1)[0])
    rng = np.random.default_rng(SEED); res = {}
    for name, col in (('volume', 'z_vol'), ('td_share_reported_only', 'z_td')):
        dd0 = d.dropna(subset=[col]); est = slope(dd0, col); boots = []
        for _ in range(BOOT):
            dd = dd0.iloc[rng.integers(0, len(dd0), len(dd0))]
            boots.append(slope(dd, col))
        lo, hi = np.percentile(boots, [2.5, 97.5]); res[name] = {'estimate_log': est, 'range_95_log': [float(lo), float(hi)]}
    confirmed = res['volume']['range_95_log'][1] < 0
    pct = lambda x: float(np.exp(x) - 1)
    out = {'lock': lock, 'n_breakouts': int(len(brk)), 'n_graded': int(len(d)), 'excluded_under_4_games_in_year_2': int(len(brk) - len(d)),
           'average_year2_change': pct(d['out'].mean()), 'share_that_fell': float((d['out'] < 0).mean()),
           'by_position_average_change': {p: pct(v) for p, v in d.groupby('pos')['out'].mean().items()},
           'volume': res['volume'], 'td_share_reported_only': res['td_share_reported_only'],
           'VERDICT': ('CONFIRMED — high-volume breakout rookies fade more in year two, on fresh classes' if confirmed else
                       'NOT CONFIRMED — Study 2\'s volume pattern does not replicate on fresh classes')}
    print(json.dumps(out, indent=2, default=float))
    (ROOT / 'data-cache' / 'rookie-volume-result.json').write_text(json.dumps(out, indent=2, default=float))

if __name__ == '__main__':
    main()
