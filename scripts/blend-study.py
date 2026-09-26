#!/usr/bin/env python3
"""
DELTA In-Season Blend Study — scripts/blend-study.py
Pre-registration: docs/PREREG-in-season-blend.md (read it first; this script implements it).

    python3 scripts/blend-study.py --count   # eligibility counts only. Computes NO errors.
    python3 scripts/blend-study.py --run     # the study. Refuses unless the pre-registration
                                             # is committed to git and unmodified.

Question: at the end of Week N (3, 6, 9, 12), which better predicts a player's points per
game over the REST of that regular season?
  A  preseason only  — scripts/backtest.js's core: 60/30/10 over the three prior seasons,
                       each shrunk by min(1, games/8), >=8 prior games to project.
  B  blend           — w x (PPG so far) + (1-w) x A,  w = G/(G+K).
  D  blend + penalty — B x (1 + 0.5 x d_volatility), the engine's Rule 4 exactly as calcProj
                       applies it, from Miss%/Elite% over the last 34 played games.
  C  rolling games   — exploratory, reported only: A counts as K pretend games, real games
                       this season weighted 0.5^(age/H), newest first.

One definition of a played game everywhere — the live DNP rule from fetch-game-logs.py:
>=1 offensive snap OR any recorded production. (backtest.js counts "has a stats row"; mixing
the two would bias A and hand B a free win.) Players are keyed by nflverse player_id, never by
name: two Josh Johnsons and two Ryan Griffins exist in this data.

Data: nflverse weekly player stats + snap counts, 2015-2025, regular season, downloaded from
nflverse-data GitHub releases into data-cache/ (not committed).
"""
import argparse, hashlib, json, math, os, subprocess, sys, urllib.request
from pathlib import Path
import numpy as np
import pandas as pd

ROOT      = Path(__file__).resolve().parent.parent
CACHE     = ROOT / 'data-cache' / 'blend-study'
PREREG    = 'docs/PREREG-in-season-blend.md'
REL       = 'https://github.com/nflverse/nflverse-data/releases/download'
YEARS     = list(range(2015, 2026))
TRAIN     = [2018, 2019, 2020, 2021, 2022]
HELDOUT   = [2023, 2024, 2025]
CHECKS    = [3, 6, 9, 12]
K_GRID    = [4, 6, 8, 10, 12, 16, 20, 24, 32]
H_GRID    = [4, 8, 16]
SKILL     = ['QB', 'RB', 'WR', 'TE']
MIN_PRIOR = 8     # backtest.js: >=8 prior-season games to project
MIN_AFTER = 4     # pre-registered: >=4 games played after the checkpoint
SHUFFLES  = 2000
SEED      = 20260926
# Start Profile usable-starter lines, half_tep (data/start-profile-thresholds.json)
LINES     = json.load(open(ROOT / 'data' / 'start-profile-thresholds.json'))['lines']

# ── data ──────────────────────────────────────────────────────────────────
def fetch(url, dest):
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f'[BLEND] downloading {url}')
        urllib.request.urlretrieve(url, dest)
    return dest

def num(df, *cols):
    out = pd.Series(0.0, index=df.index)
    for c in cols:
        if c in df.columns:
            out = out + df[c].fillna(0).astype(float)
    return out

def load_games():
    """One row per (player_id, season, week) the player PLAYED, regular season, skill positions."""
    stats = pd.concat([pd.read_parquet(fetch(f'{REL}/stats_player/stats_player_week_{y}.parquet',
                                             CACHE / f'w{y}.parquet')) for y in YEARS], ignore_index=True)
    stats = stats[stats['season_type'] == 'REG'].copy()
    g = pd.DataFrame({
        'pid': stats['player_id'].astype(str), 'name': stats['player_display_name'],
        'season': stats['season'].astype(int), 'week': stats['week'].astype(int),
        'pos': stats['position'],
        'py': num(stats, 'passing_yards'), 'pt': num(stats, 'passing_tds'),
        'pi': num(stats, 'passing_interceptions'),
        'ry': num(stats, 'rushing_yards'), 'rt': num(stats, 'rushing_tds'),
        'rec': num(stats, 'receptions'), 'rey': num(stats, 'receiving_yards'),
        'ret': num(stats, 'receiving_tds'),
        'fl': num(stats, 'sack_fumbles_lost', 'rushing_fumbles_lost', 'receiving_fumbles_lost'),
        'tp': num(stats, 'passing_2pt_conversions', 'rushing_2pt_conversions', 'receiving_2pt_conversions'),
        'rtd': num(stats, 'special_teams_tds'),
        'vol': num(stats, 'attempts', 'completions', 'carries', 'targets'),
    })
    prod_cols = ['py', 'pt', 'pi', 'ry', 'rt', 'rec', 'rey', 'ret', 'fl', 'tp', 'rtd', 'vol']
    g['prod'] = (g[prod_cols].abs().sum(axis=1) > 0)

    # snaps, joined by ID (pfr -> gsis via the nflverse players table), never by name
    players = pd.read_parquet(fetch(f'{REL}/players/players.parquet', CACHE / 'players.parquet'),
                              columns=['gsis_id', 'pfr_id', 'position'])
    both = players.dropna(subset=['pfr_id', 'gsis_id'])            # pair IDs row by row
    pfr2gsis = dict(zip(both['pfr_id'], both['gsis_id'].astype(str)))
    snaps = pd.concat([pd.read_parquet(fetch(f'{REL}/snap_counts/snap_counts_{y}.parquet',
                                             CACHE / f's{y}.parquet')) for y in YEARS], ignore_index=True)
    snaps = snaps[(snaps['game_type'] == 'REG') & (snaps['offense_snaps'].fillna(0) >= 1)]
    sn = pd.DataFrame({'pid': snaps['pfr_player_id'].map(pfr2gsis), 'season': snaps['season'].astype(int),
                       'week': snaps['week'].astype(int)}).dropna().drop_duplicates()
    sn['snap'] = True
    unmapped = snaps['pfr_player_id'].map(pfr2gsis).isna().sum()

    g = g.merge(sn, on=['pid', 'season', 'week'], how='outer')
    g['snap'] = g['snap'].fillna(False).astype(bool)
    g['prod'] = g['prod'].fillna(False).astype(bool)
    for c in prod_cols:
        g[c] = g[c].fillna(0.0)
    g = g[g['snap'] | g['prod']].copy()        # live DNP rule: >=1 snap OR any production
    # position: the player's most common listed position that season; snap-only weeks inherit it
    ps = g.dropna(subset=['pos']).groupby(['pid', 'season'])['pos'].agg(lambda s: s.mode().iat[0])
    g['spos'] = [ps.get((p, s)) for p, s in zip(g['pid'], g['season'])]
    fallback = dict(zip(players['gsis_id'].astype(str), players['position']))
    g['spos'] = g['spos'].fillna(g['pid'].map(fallback))
    g = g[g['spos'].isin(SKILL)].copy()
    g['name'] = g.groupby('pid')['name'].transform(lambda s: s.dropna().iat[-1] if s.notna().any() else '')
    g = g.sort_values(['pid', 'season', 'week']).reset_index(drop=True)
    info = {'played_games': len(g), 'snap_only_games': int((g['snap'] & ~g['prod']).sum()),
            'snap_rows_unmapped_to_id': int(unmapped)}
    return g, info

def bt_pts(df, pos):
    """backtest.js ppg() scoring (half-PPR, TE +1.0/rec): the outcome and A/B/C units."""
    rp = 1.0 if pos == 'TE' else 0.5
    return (df['ry'] * .1 + df['rt'] * 6 + df['rey'] * .1 + df['ret'] * 6 + df['rec'] * rp
            + df['py'] * .04 + df['pt'] * 4 + df['pi'] * -2).to_numpy()

def sp_pts(df, pos):
    """delta-engine.js gamefp() at half_tep: the Start Profile's game scoring (D's penalty)."""
    rp = 1.0 if pos == 'TE' else (0.0 if pos == 'QB' else 0.5)
    return (df['py'] * .04 + df['pt'] * 4 + df['pi'] * -2 + df['ry'] * .1 + df['rt'] * 6
            + df['rec'] * rp + df['rey'] * .1 + df['ret'] * 6 + df['fl'] * -2 + df['tp'] * 2
            + df['rtd'] * 6).to_numpy()

def d_volatility(sp_hist, pos):
    """calcProj Rule 4, verbatim thresholds; percentages rounded as computeStartProfile does."""
    games = sp_hist[-34:]
    n = len(games)
    if n < 20:
        return 0.0
    hit, elite = LINES[f'{pos}|half_tep']
    e = int((games >= elite).sum()); m = int((games < hit).sum())
    miss = math.floor(100 * m / n + 0.5); elp = math.floor(100 * e / n + 0.5)   # = JS Math.round
    d = 0.0
    if miss > 65: d = -0.09
    elif miss > 55: d = -0.06
    elif miss > 45: d = -0.03
    elif miss > 40: d = -0.01
    if elp > 30: d = min(0.0, d + 0.03)
    elif elp > 20: d = min(0.0, d + 0.01)
    return d

# ── one row per (player-season, checkpoint) ───────────────────────────────
def build_rows(g):
    rows = []
    for pid, pg in g.groupby('pid', sort=False):
        seasons = {s: sg for s, sg in pg.groupby('season')}
        for Y in TRAIN + HELDOUT:
            if Y not in seasons:
                continue
            pos = seasons[Y]['spos'].mode().iat[0]
            # A — backtest.js core over Y-1..Y-3, games by the live rule
            numr = den = 0.0; prior_g = 0
            for k, bw in zip((1, 2, 3), (0.6, 0.3, 0.1)):
                sg = seasons.get(Y - k)
                if sg is None or len(sg) == 0:
                    continue
                n = len(sg); v = bt_pts(sg, pos).sum() / n
                w = bw * min(1.0, n / 8)
                numr += w * v; den += w; prior_g += n
            if den == 0 or prior_g < MIN_PRIOR:
                continue
            pre = numr / den
            cur = seasons[Y]
            cur_bt = bt_pts(cur, pos); cur_wk = cur['week'].to_numpy()
            hist = pg[pg['season'] < Y]
            hist_sp = sp_pts(hist, pos) if len(hist) else np.array([])
            cur_sp = sp_pts(cur, pos)
            for N in CHECKS:
                before = cur_wk <= N; after = cur_wk > N
                G = int(before.sum()); A_n = int(after.sum())
                if G < 1 or A_n < MIN_AFTER:
                    continue
                rows.append({
                    'pid': pid, 'name': cur['name'].iat[0], 'season': Y, 'pos': pos, 'N': N,
                    'pre': pre, 'G': G, 'sofar': cur_bt[before].sum() / G,
                    'recent': cur_bt[before][::-1].tolist(),              # newest first, for C
                    'dvol': d_volatility(np.concatenate([hist_sp, cur_sp[before]]), pos),
                    'actual': cur_bt[after].sum() / A_n, 'n_after': A_n,
                })
    return pd.DataFrame(rows)

# ── contenders ────────────────────────────────────────────────────────────
def pred_B(r, K): return (r['G'] / (r['G'] + K)) * r['sofar'] + (K / (r['G'] + K)) * r['pre']
def pred_D(r, K): return pred_B(r, K) * (1 + 0.5 * r['dvol'])
def pred_C(r, K, H):
    w = np.array([0.5 ** (i / H) for i in range(len(r['recent']))])
    return (K * r['pre'] + (w * np.array(r['recent'])).sum()) / (K + w.sum())

def pooled_rmse(err, df):
    """Mean of the four per-checkpoint RMSEs (each checkpoint weighted equally)."""
    return float(np.mean([math.sqrt(np.mean(err[df['N'].to_numpy() == N] ** 2)) for N in CHECKS]))

def errors(df, kind, K=None, H=None):
    if kind == 'A': p = df['pre'].to_numpy()
    elif kind == 'B': p = np.array([pred_B(r, K) for r in df.to_dict('records')])
    elif kind == 'D': p = np.array([pred_D(r, K) for r in df.to_dict('records')])
    else: p = np.array([pred_C(r, K, H) for r in df.to_dict('records')])
    return p - df['actual'].to_numpy()

def cv_pick(train, kind):
    """Leave-one-training-season-out CV. Returns (final K or (K,H), out-of-fold pooled RMSE)."""
    grid = [(k, h) for k in K_GRID for h in H_GRID] if kind == 'C' else [(k, None) for k in K_GRID]
    def score(df, kh): return pooled_rmse(errors(df, kind, *kh), df)
    oof = []
    for s in TRAIN:
        fit, hold = train[train['season'] != s], train[train['season'] == s]
        best = min(grid, key=lambda kh: score(fit, kh))
        oof.append(score(hold, best))
    final = min(grid, key=lambda kh: score(train, kh))
    return final, float(np.mean(oof))

# ── guards ────────────────────────────────────────────────────────────────
def require_locked_prereg():
    try:
        subprocess.run(['git', 'ls-files', '--error-unmatch', PREREG], cwd=ROOT, check=True,
                       capture_output=True)
    except subprocess.CalledProcessError:
        sys.exit(f'[BLEND] REFUSED: {PREREG} is not committed. Commit it first — that is the lock.')
    if subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', PREREG], cwd=ROOT).returncode != 0:
        sys.exit(f'[BLEND] REFUSED: {PREREG} has uncommitted edits. Commit or discard them.')
    sha = subprocess.run(['git', 'log', '-1', '--format=%H %cI', '--', PREREG], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip()
    body = (ROOT / PREREG).read_bytes()
    return {'prereg_commit': sha, 'prereg_sha256': hashlib.sha256(body).hexdigest()[:16]}

# ── main ──────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--count', action='store_true', help='eligibility counts only; no errors')
    mode.add_argument('--run', action='store_true', help='the study (needs the committed pre-registration)')
    a = ap.parse_args()
    lock = require_locked_prereg() if a.run else None

    g, info = load_games()
    df = build_rows(g)
    print(f"[BLEND] played games {info['played_games']:,} · of which snap-only (0 production) "
          f"{info['snap_only_games']:,} · snap rows with no ID match {info['snap_rows_unmapped_to_id']:,}")
    tab = df.groupby(['season', 'N']).size().unstack('N').reindex(TRAIN + HELDOUT)
    print('[BLEND] graded player-checkpoints (rows: season, columns: after week N)')
    print(tab.to_string())
    print(f"[BLEND] training rows {int((df['season'].isin(TRAIN)).sum()):,} · held-out rows "
          f"{int((df['season'].isin(HELDOUT)).sum()):,} · held-out player-seasons "
          f"{df[df['season'].isin(HELDOUT)][['pid','season']].drop_duplicates().shape[0]:,}")
    print(f"[BLEND] rows where the step penalty is active (>=20 games, d<0): "
          f"{int((df['dvol'] < 0).sum()):,} of {len(df):,}")
    if a.count:
        print('[BLEND] --count: no errors computed.')
        return

    train, test = df[df['season'].isin(TRAIN)], df[df['season'].isin(HELDOUT)]
    picks = {k: cv_pick(train, k) for k in ('B', 'D', 'C')}
    cand = 'B' if picks['B'][1] <= picks['D'][1] else 'D'
    print(f"[BLEND] training CV: B K={picks['B'][0][0]} oof {picks['B'][1]:.4f} · "
          f"D K={picks['D'][0][0]} oof {picks['D'][1]:.4f} · C K,H={picks['C'][0]} oof {picks['C'][1]:.4f}")
    print(f'[BLEND] candidate chosen on training: {cand}   (held-out numbers cannot change this)')

    eA = errors(test, 'A')
    out = {'lock': lock, 'info': info, 'picks': {k: [list(v[0]), v[1]] for k, v in picks.items()},
           'candidate': cand, 'heldout': {}}
    for k in ('B', 'D', 'C'):
        e = errors(test, k, *picks[k][0])
        out['heldout'][k] = {'rmse': pooled_rmse(e, test), 'lift': 1 - pooled_rmse(e, test) / pooled_rmse(eA, test)}
    out['heldout']['A'] = {'rmse': pooled_rmse(eA, test)}
    eC = errors(test, cand, *picks[cand][0])
    lift = 1 - pooled_rmse(eC, test) / pooled_rmse(eA, test)

    # permutation: swap A/candidate errors per PLAYER-SEASON (all its checkpoints together)
    rng = np.random.default_rng(SEED)
    keys = (test['pid'] + '|' + test['season'].astype(str)).to_numpy()
    uniq, inv = np.unique(keys, return_inverse=True)
    ge = 0
    for _ in range(SHUFFLES):
        flip = rng.random(len(uniq)) < 0.5
        f = flip[inv]
        a_, c_ = np.where(f, eC, eA), np.where(f, eA, eC)
        if 1 - pooled_rmse(c_, test) / pooled_rmse(a_, test) >= lift:
            ge += 1
    p = (ge + 1) / (SHUFFLES + 1)
    per_season = {int(s): 1 - pooled_rmse(eC[test['season'].to_numpy() == s], test[test['season'] == s])
                  / pooled_rmse(eA[test['season'].to_numpy() == s], test[test['season'] == s]) for s in HELDOUT}
    per_pos = {}
    for ps in SKILL:
        m = test['pos'].to_numpy() == ps
        if m.sum():
            per_pos[ps] = 1 - pooled_rmse(eC[m], test[m]) / pooled_rmse(eA[m], test[m])
    per_check = {N: 1 - math.sqrt(np.mean(eC[test['N'].to_numpy() == N] ** 2))
                 / math.sqrt(np.mean(eA[test['N'].to_numpy() == N] ** 2)) for N in CHECKS}
    gates = {'size_>=2%': lift >= 0.02, 'p<0.05': p < 0.05,
             'every_heldout_season': all(v > 0 for v in per_season.values()),
             'no_position_worse_than_-1%': all(v >= -0.01 for v in per_pos.values())}
    rel = test['pre'].to_numpy() >= 8.0          # reported only, never gated (pre-registered §6)
    relevant = {k: 1 - pooled_rmse(errors(test[rel], k, *picks[k][0]), test[rel])
                / pooled_rmse(errors(test[rel], 'A'), test[rel]) for k in ('B', 'D', 'C')}
    out['relevant_8ppg_lift_reported_only'] = relevant
    out.update({'lift': lift, 'p': p, 'per_season': per_season, 'per_position': per_pos,
                'per_checkpoint': per_check, 'gates': gates, 'SHIP': all(gates.values())})
    print(json.dumps(out, indent=2, default=float))
    (ROOT / 'data-cache' / 'blend-study-result.json').write_text(json.dumps(out, indent=2, default=float))

if __name__ == '__main__':
    main()
