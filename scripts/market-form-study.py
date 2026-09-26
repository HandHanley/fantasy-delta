#!/usr/bin/env python3
"""
DELTA Market-Form Study — does DELTA's in-season re-rating predict where the market goes?
scripts/market-form-study.py · pre-registration: docs/PREREG-market-form.md

    python3 scripts/market-form-study.py --count   # eligibility only; reads NO future prices
    python3 scripts/market-form-study.py --run     # refuses unless the pre-registration is committed

At the first DynastyProcess snapshot after Week 4 and after Week 8 of each season 2020-2025:
  r_D  DELTA's move   = log(blended projection + 1) - log(preseason projection + 1)
  r_M  market's move  = L(price at checkpoint) - L(price before Week 1)
  f    what happens   = L(price before the NEXT season's Week 1) - L(price at checkpoint)
  L(v) = log(v + 100); a player missing from the next snapshot counts as price 0.
Baseline (market only):  f ~ r_M + L(v_cp) + age + age^2 + position + checkpoint
Candidate:               baseline + r_D
Fit on 2020-2022, graded once on 2023-2025.

Prices: DynastyProcess `files/values.csv` git history, `value_2qb` (superflex, DELTA's anchor),
dated by scrape_date. Players join to nflverse by ID through DynastyProcess's own crosswalk
(`files/db_playerids.csv`: fantasypros_id -> gsis_id), never by name.
DELTA numbers reuse scripts/blend-study.py and scripts/blend-study-rookies.py unchanged.
"""
import argparse, importlib.util, io, json, math, subprocess, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
def _load(name, file):
    s = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / file)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
rk = _load('bsr', 'blend-study-rookies.py')
bs = rk.bs                                   # Part 1 machinery, via Part 2 (one copy)

PREREG   = 'docs/PREREG-market-form.md'
DP_GIT   = 'https://github.com/dynastyprocess/data.git'
DP_DIR   = bs.CACHE / 'dynastyprocess-data'
SEASONS  = [2020, 2021, 2022, 2023, 2024, 2025]
TRAIN, HELDOUT = [2020, 2021, 2022], [2023, 2024, 2025]
CHECKS   = [4, 8]
MAX_LAG  = 10          # days: a snapshot further than this from its target date is not used
OFFSET   = 100.0       # L(v) = log(v + 100)
K_BY_GROUP = {'vet': 4, 'thin': 2, 'rookie': 3}   # live engine 2026-09-26c
MIN_POS_N = 30
SEED, SHUFFLES = 20260926, 2000

# ── prices ────────────────────────────────────────────────────────────────
def load_prices():
    cache = bs.CACHE / 'dp_values.parquet'
    if not DP_DIR.exists():
        subprocess.run(['git', 'clone', '-q', '--filter=blob:none', '--no-checkout', DP_GIT, str(DP_DIR)], check=True)
    if not cache.exists():
        log = subprocess.run(['git', 'log', '--format=%H', '--since=2020-08-01', '--', 'files/values.csv'],
                             cwd=DP_DIR, capture_output=True, text=True, check=True).stdout.split()
        frames = []
        for h in reversed(log):                                    # oldest first; later commits win
            raw = subprocess.run(['git', 'show', f'{h}:files/values.csv'], cwd=DP_DIR,
                                 capture_output=True, check=True).stdout
            v = pd.read_csv(io.BytesIO(raw), dtype={'fp_id': str})
            frames.append(v[['player', 'pos', 'age', 'fp_id', 'value_2qb', 'scrape_date']])
        p = pd.concat(frames, ignore_index=True)
        p = p.drop_duplicates(['scrape_date', 'fp_id'], keep='last')
        p.to_parquet(cache)
    p = pd.read_parquet(cache)
    p = p[p['pos'].isin(bs.SKILL)].copy()
    ids = pd.read_csv(io.BytesIO(subprocess.run(['git', 'show', 'HEAD:files/db_playerids.csv'], cwd=DP_DIR,
                      capture_output=True, check=True).stdout), dtype=str, usecols=['fantasypros_id', 'gsis_id'])
    ids = ids.dropna().drop_duplicates('fantasypros_id')
    p['pid'] = p['fp_id'].map(dict(zip(ids['fantasypros_id'], ids['gsis_id'])))
    return p

def week_bounds():
    g = pd.read_csv(bs.fetch('https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv',
                             bs.CACHE / 'games.csv'), usecols=['season', 'game_type', 'week', 'gameday'])
    g = g[g['game_type'] == 'REG']
    return lambda y, w, f: g[(g['season'] == y) & (g['week'] == w)]['gameday'].agg(f)

def pick_snapshots(prices, wb):
    """Per season: last snapshot before Week 1 (>= 1 Aug); first snapshot after Week N's last game."""
    dates = sorted(prices['scrape_date'].unique()); snaps = {}
    D = lambda s: pd.Timestamp(s)
    for y in SEASONS + [SEASONS[-1] + 1]:
        w1 = wb(y, 1, 'min')
        pre = [d for d in dates if f'{y}-08-01' <= d < w1]
        if pre and (D(w1) - D(pre[-1])).days <= MAX_LAG: snaps[(y, 'pre')] = pre[-1]
        if y in SEASONS:
            for N in CHECKS:
                end = wb(y, N, 'max'); aft = [d for d in dates if d > end]
                if aft and (D(aft[0]) - D(end)).days <= MAX_LAG: snaps[(y, N)] = aft[0]
    return snaps

# ── DELTA's read at each checkpoint ───────────────────────────────────────
def delta_reads(g, draft):
    rs = rk.rookie_seasons(g, draft)
    tables = {Y: rk.fit_table(rs, [s for s in rk.TABLE_FIT if s != Y]) for Y in SEASONS}
    held = rk.fit_table(rs, rk.TABLE_FIT)
    out = []
    for pid, pg in g.groupby('pid', sort=False):
        seasons = {s: sg for s, sg in pg.groupby('season')}
        for Y in SEASONS:
            if Y not in seasons: continue
            cur = seasons[Y]; pos = cur['spos'].mode().iat[0]
            prior_g = sum(len(seasons.get(Y - k, [])) for k in (1, 2, 3))
            if pid in draft and draft[pid][0] == Y:
                tab = held if Y in HELDOUT else tables[Y]
                pre, grp = tab[pos][rk.tier(draft[pid][1])], 'rookie'
            elif prior_g >= 1:
                numr = den = 0.0
                for k, bw in zip((1, 2, 3), (0.6, 0.3, 0.1)):
                    sg = seasons.get(Y - k)
                    if sg is None or len(sg) == 0: continue
                    n = len(sg); w = bw * min(1.0, n / 8)
                    numr += w * bs.bt_pts(sg, pos).sum() / n; den += w
                pre, grp = numr / den, ('vet' if prior_g >= 8 else 'thin')
            else:
                continue
            if pre is None or np.isnan(pre): continue
            pts = bs.bt_pts(cur, pos); wk = cur['week'].to_numpy()
            nxt = seasons.get(Y + 1)
            nxt_ppg = (bs.bt_pts(nxt, pos).sum() / len(nxt)) if nxt is not None and len(nxt) >= 4 else None
            for N in CHECKS:
                b = wk <= N; G = int(b.sum())
                if G < 1: continue
                K = K_BY_GROUP[grp]; w = G / (G + K)
                blend = w * pts[b].sum() / G + (1 - w) * pre
                out.append({'pid': pid, 'season': Y, 'N': N, 'pos': pos, 'group': grp, 'G': G,
                            'pre_proj': pre, 'blend': blend,
                            'r_D': math.log(max(blend, 0) + 1) - math.log(max(pre, 0) + 1),
                            'next_ppg': nxt_ppg})
    return pd.DataFrame(out)

def L(v): return np.log(np.asarray(v, dtype=float) + OFFSET)

def build(read_future):
    g, info = bs.load_games()
    draft = rk.load_draft()
    prices = load_prices(); snaps = pick_snapshots(prices, week_bounds())
    reads = delta_reads(g, draft)
    by = {d: s.dropna(subset=['pid']).drop_duplicates('pid').set_index('pid') for d, s in prices.groupby('scrape_date')}
    rows = []
    for r in reads.to_dict('records'):
        Y, N = r['season'], r['N']
        if (Y, 'pre') not in snaps or (Y, N) not in snaps: continue
        s0, s1 = by[snaps[(Y, 'pre')]], by[snaps[(Y, N)]]
        if r['pid'] not in s0.index or r['pid'] not in s1.index: continue
        v0, v1 = float(s0.at[r['pid'], 'value_2qb']), float(s1.at[r['pid'], 'value_2qb'])
        if not (v0 > 0 and v1 > 0): continue
        row = dict(r, v_pre=v0, v_cp=v1, age=float(s1.at[r['pid'], 'age']),
                   r_M=float(L(v1) - L(v0)), Lv=float(L(v1)))
        if read_future:                       # only --run ever touches the next season's prices
            sn = by.get(snaps.get((Y + 1, 'pre')))
            vn = float(sn.at[r['pid'], 'value_2qb']) if sn is not None and r['pid'] in sn.index else 0.0
            row['f'] = float(L(vn) - L(v1))
        rows.append(row)
    df = pd.DataFrame(rows).dropna(subset=['age'])
    return df, snaps, info

# ── model ─────────────────────────────────────────────────────────────────
def design(df, with_rD):
    X = [np.ones(len(df)), df['r_M'], df['Lv'], df['age'], df['age'] ** 2,
         (df['pos'] == 'RB').astype(float), (df['pos'] == 'WR').astype(float), (df['pos'] == 'TE').astype(float),
         (df['N'] == 8).astype(float)]
    if with_rD: X.append(df['r_D'])
    return np.column_stack([np.asarray(x, dtype=float) for x in X])

def fit(df, with_rD):
    beta, *_ = np.linalg.lstsq(design(df, with_rD), df['f'].to_numpy(), rcond=None); return beta

def rmse_by_check(df, pred):
    e = pred - df['f'].to_numpy(); n = df['N'].to_numpy()
    return float(np.mean([math.sqrt(np.mean(e[n == N] ** 2)) for N in CHECKS]))

def main():
    ap = argparse.ArgumentParser(); m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument('--count', action='store_true'); m.add_argument('--run', action='store_true')
    a = ap.parse_args()
    lock = None
    if a.run:
        bs.PREREG = PREREG; lock = bs.require_locked_prereg()
    df, snaps, info = build(read_future=a.run)
    print('[FORM] snapshots used:')
    for y in SEASONS:
        print(f"   {y}: before W1 {snaps.get((y,'pre'))} · after W4 {snaps.get((y,4))} · after W8 {snaps.get((y,8))} · "
              f"next season {snaps.get((y+1,'pre'))}")
    t = df.groupby(['season', 'N']).size().unstack('N')
    print('[FORM] graded player-checkpoints'); print(t.to_string())
    h = df[df['season'].isin(HELDOUT)]
    print(f"[FORM] training rows {int(df['season'].isin(TRAIN).sum())} · held-out rows {len(h)} · held-out player-seasons "
          f"{h[['pid','season']].drop_duplicates().shape[0]} · by position "
          f"{h[['pid','season','pos']].drop_duplicates()['pos'].value_counts().to_dict()} · by group "
          f"{h[['pid','season','group']].drop_duplicates()['group'].value_counts().to_dict()}")
    if a.count:
        print('[FORM] --count: no future prices read, no errors computed.'); return

    tr, te = df[df['season'].isin(TRAIN)], df[df['season'].isin(HELDOUT)]
    b0, b1 = fit(tr, False), fit(tr, True)
    X0, X1 = design(te, False), design(te, True)
    r0, r1 = rmse_by_check(te, X0 @ b0), rmse_by_check(te, X1 @ b1)
    lift = 1 - r1 / r0
    # permutation: shuffle r_D within (season, checkpoint, position) on the held-out rows, fitted betas fixed
    rng = np.random.default_rng(SEED); ge = 0
    strata = (te['season'].astype(str) + te['N'].astype(str) + te['pos']).to_numpy()
    rD = te['r_D'].to_numpy(); idx = {s: np.where(strata == s)[0] for s in np.unique(strata)}
    for _ in range(SHUFFLES):
        sh = rD.copy()
        for ii in idx.values(): sh[ii] = rng.permutation(rD[ii])
        X = X1.copy(); X[:, -1] = sh
        if 1 - rmse_by_check(te, X @ b1) / r0 >= lift: ge += 1
    p = (ge + 1) / (SHUFFLES + 1)
    def sub_lift(mask):
        d = te[mask]; return 1 - rmse_by_check(d, design(d, True) @ b1) / rmse_by_check(d, design(d, False) @ b0)
    per_season = {int(s): sub_lift(te['season'].to_numpy() == s) for s in HELDOUT}
    per_pos, pos_n = {}, {}
    for ps in bs.SKILL:
        mk = te['pos'].to_numpy() == ps
        pos_n[ps] = te[mk][['pid', 'season']].drop_duplicates().shape[0]
        per_pos[ps] = sub_lift(mk)
    gates = {'size_>=2%': lift >= 0.02, 'p<0.05': p < 0.05, 'beta_rD_positive': b1[-1] > 0,
             'every_heldout_season': all(v > 0 for v in per_season.values()),
             'no_position_worse_than_-1%_(n>=30)': all(v >= -0.01 for k, v in per_pos.items() if pos_n[k] >= MIN_POS_N)}
    # reported only
    res = te['f'].to_numpy() - X0 @ b0
    partial = float(np.corrcoef(res, te['r_D'].to_numpy() - X0 @ np.linalg.lstsq(X0, te['r_D'].to_numpy(), rcond=None)[0])[0, 1])
    per_group = {gname: sub_lift(te['group'].to_numpy() == gname) for gname in K_BY_GROUP if (te['group'] == gname).any()}
    sec = te.dropna(subset=['next_ppg'])
    sec_note = None
    if len(sec) > 50:
        Xs0 = np.column_stack([np.ones(len(sec)), sec['Lv'], sec['r_M'], sec['age'], sec['age']**2])
        Xs1 = np.column_stack([Xs0, sec['r_D']])
        y = sec['next_ppg'].to_numpy()
        e0 = y - Xs0 @ np.linalg.lstsq(Xs0, y, rcond=None)[0]; e1 = y - Xs1 @ np.linalg.lstsq(Xs1, y, rcond=None)[0]
        sec_note = {'n': int(len(sec)), 'in_sample_rmse_market_only': float(np.sqrt(np.mean(e0**2))),
                    'in_sample_rmse_plus_rD': float(np.sqrt(np.mean(e1**2)))}
    out = {'lock': lock, 'n_train': int(len(tr)), 'n_heldout': int(len(te)),
           'beta_rD': float(b1[-1]), 'heldout_rmse_market_only': r0, 'heldout_rmse_plus_delta': r1,
           'lift': lift, 'p': p, 'per_season': per_season, 'per_position': per_pos,
           'position_player_seasons': pos_n, 'gates': gates, 'SHIP': all(gates.values()),
           'reported_only': {'partial_correlation': partial, 'per_group_lift': per_group,
                             'next_season_ppg_secondary': sec_note}}
    print(json.dumps(out, indent=2, default=float))
    (ROOT / 'data-cache' / 'market-form-result.json').write_text(json.dumps(out, indent=2, default=float))

if __name__ == '__main__':
    main()
