#!/usr/bin/env python3
"""
DELTA In-Season Blend, Part 2 — Rookies And Thin-History Players
scripts/blend-study-rookies.py · pre-registration: docs/PREREG-in-season-blend-rookies.md

    python3 scripts/blend-study-rookies.py --count   # eligibility counts only; computes NO errors
    python3 scripts/blend-study-rookies.py --run     # refuses unless the pre-registration is committed

Part 1 (scripts/blend-study.py, PASSED 26 Sep) covered players with >=8 played games in the three
prior seasons. This covers the two groups it excluded, each gated on its own:

  R  ROOKIES  drafted players in their draft season. Prior = median rookie-season PPG by position
              x draft-capital tier (the ROOKIE_PPG recipe), rebuilt WITHOUT the season being
              graded: held-out seasons use a table fit on 2015-2022; each training season uses a
              table fit on 2015-2022 minus that season.
  T  THIN     everyone else with 1-7 played games in the three prior seasons. Prior = the Part 1
              preseason formula (backtest.js core) without its 8-game floor.

Contenders per group: A = prior only; B = w x (PPG so far) + (1-w) x prior, w = G/(G+K).
Shared machinery (games, scoring, IDs, checkpoints) is imported from scripts/blend-study.py so
the two studies cannot drift apart.
"""
import argparse, hashlib, importlib.util, json, math, subprocess, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location('bs1', ROOT / 'scripts' / 'blend-study.py')
bs = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(bs)

PREREG   = 'docs/PREREG-in-season-blend-rookies.md'
TABLE_FIT = list(range(2015, 2023))          # rookie table fit seasons (2015-2022)
K_GRID   = [2, 3, 4, 6, 8, 10, 12, 16, 20, 24, 32]
MIN_POS_N = 30                               # position gate applies where held-out player-seasons >= 30
ENGINE_TABLE = {                             # delta-engine.js ROOKIE_PPG, shipped (fit 2015-2025) — reported only
    'QB': [15.20, 12.91, 12.91, 8.00, 5.44], 'RB': [15.22, 12.73, 10.79, 6.00, 3.18],
    'TE': [10.32, 8.59, 4.93, 3.12, 3.12],  'WR': [9.39, 7.09, 6.16, 3.69, 1.74]}

def tier(pick):   # delta-engine.js rookieTier()
    return 0 if pick <= 10 else 1 if pick <= 32 else 2 if pick <= 64 else 3 if pick <= 105 else 4

def load_draft():
    dp = pd.read_parquet(bs.fetch(f'{bs.REL}/draft_picks/draft_picks.parquet', bs.CACHE / 'draft_picks.parquet'))
    dp = dp.dropna(subset=['gsis_id', 'pick'])
    return {str(g): (int(s), int(p)) for g, s, p in zip(dp['gsis_id'], dp['season'], dp['pick'])}

def rookie_seasons(g, draft):
    """Full rookie-season PPG for every drafted player: rows (pid, season, pos, tier, ppg)."""
    out = []
    for pid, pg in g.groupby('pid', sort=False):
        if pid not in draft: continue
        y, pk = draft[pid]
        r = pg[pg['season'] == y]
        if len(r) == 0: continue
        pos = r['spos'].mode().iat[0]
        out.append((pid, y, pos, tier(pk), bs.bt_pts(r, pos).sum() / len(r)))
    return pd.DataFrame(out, columns=['pid', 'season', 'pos', 'tier', 'ppg'])

def fit_table(rs, seasons):
    """ROOKIE_PPG recipe: median by position x tier, rows forced non-increasing as capital falls."""
    sub = rs[rs['season'].isin(seasons)]
    t = {}
    for pos in bs.SKILL:
        med = [sub[(sub['pos'] == pos) & (sub['tier'] == k)]['ppg'].median() for k in range(5)]
        for k in range(1, 5):
            if not np.isnan(med[k - 1]) and (np.isnan(med[k]) or med[k] > med[k - 1]):
                med[k] = med[k - 1]
        t[pos] = med
    return t

def build_rows(g, draft):
    rs = rookie_seasons(g, draft)
    tables = {Y: fit_table(rs, [s for s in TABLE_FIT if s != Y]) for Y in bs.TRAIN}
    held_table = fit_table(rs, TABLE_FIT)
    rows = []
    for pid, pg in g.groupby('pid', sort=False):
        seasons = {s: sg for s, sg in pg.groupby('season')}
        for Y in bs.TRAIN + bs.HELDOUT:
            if Y not in seasons: continue
            cur = seasons[Y]; pos = cur['spos'].mode().iat[0]
            prior_g = sum(len(seasons.get(Y - k, [])) for k in (1, 2, 3))
            if pid in draft and draft[pid][0] == Y:                       # R — rookie
                tab = held_table if Y in bs.HELDOUT else tables[Y]
                pre = tab[pos][tier(draft[pid][1])]
                eng = ENGINE_TABLE[pos][tier(draft[pid][1])]
                group = 'R'
            elif 1 <= prior_g <= 7:                                        # T — thin history
                numr = den = 0.0
                for k, bw in zip((1, 2, 3), (0.6, 0.3, 0.1)):
                    sg = seasons.get(Y - k)
                    if sg is None or len(sg) == 0: continue
                    n = len(sg); numr += bw * min(1.0, n / 8) * bs.bt_pts(sg, pos).sum() / n
                    den += bw * min(1.0, n / 8)
                pre = numr / den; eng = None; group = 'T'
            else:
                continue
            if pre is None or np.isnan(pre): continue
            bt = bs.bt_pts(cur, pos); wk = cur['week'].to_numpy()
            for N in bs.CHECKS:
                b, a = wk <= N, wk > N
                G, An = int(b.sum()), int(a.sum())
                if G < 1 or An < bs.MIN_AFTER: continue
                rows.append({'group': group, 'pid': pid, 'name': cur['name'].iat[0], 'season': Y,
                             'pos': pos, 'N': N, 'pre': pre, 'eng': eng, 'G': G,
                             'sofar': bt[b].sum() / G, 'actual': bt[a].sum() / An})
    return pd.DataFrame(rows), {'rookie_seasons_2015_2022': int(rs['season'].isin(TABLE_FIT).sum()),
                                'held_table': {k: [round(x, 2) for x in v] for k, v in held_table.items()}}

def err(df, K=None, prior='pre'):
    p = df[prior].to_numpy()
    if K is not None:
        w = df['G'].to_numpy() / (df['G'].to_numpy() + K)
        p = w * df['sofar'].to_numpy() + (1 - w) * p
    return p - df['actual'].to_numpy()

def cv_pick(train):
    oof = []
    for s in bs.TRAIN:
        fit, hold = train[train['season'] != s], train[train['season'] == s]
        if len(hold) == 0: continue
        k = min(K_GRID, key=lambda k: bs.pooled_rmse(err(fit, k), fit))
        oof.append(bs.pooled_rmse(err(hold, k), hold))
    return min(K_GRID, key=lambda k: bs.pooled_rmse(err(train, k), train)), float(np.mean(oof))

def gate_group(df, name):
    train, test = df[df['season'].isin(bs.TRAIN)], df[df['season'].isin(bs.HELDOUT)]
    K, oof = cv_pick(train)
    eA, eB = err(test), err(test, K)
    rA, rB = bs.pooled_rmse(eA, test), bs.pooled_rmse(eB, test)
    lift = 1 - rB / rA
    rng = np.random.default_rng(bs.SEED)
    keys = (test['pid'] + '|' + test['season'].astype(str)).to_numpy()
    uniq, inv = np.unique(keys, return_inverse=True)
    ge = 0
    for _ in range(bs.SHUFFLES):
        f = (rng.random(len(uniq)) < 0.5)[inv]
        if 1 - bs.pooled_rmse(np.where(f, eA, eB), test) / bs.pooled_rmse(np.where(f, eB, eA), test) >= lift:
            ge += 1
    p = (ge + 1) / (bs.SHUFFLES + 1)
    s_arr = test['season'].to_numpy()
    per_season = {int(s): 1 - bs.pooled_rmse(eB[s_arr == s], test[s_arr == s]) / bs.pooled_rmse(eA[s_arr == s], test[s_arr == s])
                  for s in bs.HELDOUT if (s_arr == s).any()}
    per_pos, pos_n = {}, {}
    for ps in bs.SKILL:
        m = test['pos'].to_numpy() == ps
        n = test[m][['pid', 'season']].drop_duplicates().shape[0]
        if m.sum():
            pos_n[ps] = n
            per_pos[ps] = 1 - bs.pooled_rmse(eB[m], test[m]) / bs.pooled_rmse(eA[m], test[m])
    per_check = {N: 1 - math.sqrt(np.mean(eB[test['N'].to_numpy() == N] ** 2))
                 / math.sqrt(np.mean(eA[test['N'].to_numpy() == N] ** 2)) for N in bs.CHECKS}
    gates = {'size_>=2%': lift >= 0.02, 'p<0.05': p < 0.05,
             'every_heldout_season': all(v > 0 for v in per_season.values()),
             'no_position_worse_than_-1%_(n>=30)': all(v >= -0.01 for ps, v in per_pos.items() if pos_n[ps] >= MIN_POS_N)}
    out = {'K': K, 'train_oof_rmse': oof, 'heldout_rmse_prior': rA, 'heldout_rmse_blend': rB, 'lift': lift,
           'p': p, 'per_season': per_season, 'per_position': per_pos, 'position_player_seasons': pos_n,
           'per_checkpoint': per_check, 'gates': gates, 'SHIP': all(gates.values())}
    if name == 'R':   # reported only: the shipped engine table as the prior (it includes 2023-25 rookies)
        eE, eEB = err(test, prior='eng'), err(test, K, prior='eng')
        out['reported_only_engine_table'] = {'rmse_prior': bs.pooled_rmse(eE, test), 'rmse_blend': bs.pooled_rmse(eEB, test)}
    return out

def main():
    ap = argparse.ArgumentParser(); m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument('--count', action='store_true'); m.add_argument('--run', action='store_true')
    a = ap.parse_args()
    lock = None
    if a.run:
        bs.PREREG = PREREG
        lock = bs.require_locked_prereg()
    g, info = bs.load_games()
    df, tinfo = build_rows(g, load_draft())
    print(f"[ROOKIE] rookie seasons 2015-2022 behind the held-out table: {tinfo['rookie_seasons_2015_2022']}")
    print(f"[ROOKIE] held-out prior table (fit 2015-2022): {tinfo['held_table']}")
    for grp in ('R', 'T'):
        d = df[df['group'] == grp]
        print(f"[ROOKIE] group {grp}: graded player-checkpoints (rows: season, columns: after week N)")
        print(d.groupby(['season', 'N']).size().unstack('N').reindex(bs.TRAIN + bs.HELDOUT).fillna(0).astype(int).to_string())
        h = d[d['season'].isin(bs.HELDOUT)]
        print(f"[ROOKIE] group {grp}: held-out rows {len(h)}, player-seasons {h[['pid','season']].drop_duplicates().shape[0]}, "
              f"by position {h[['pid','season','pos']].drop_duplicates()['pos'].value_counts().to_dict()}")
    if a.count:
        print('[ROOKIE] --count: no errors computed.'); return
    out = {'lock': lock, 'info': info, 'table': tinfo, 'R': gate_group(df[df['group'] == 'R'], 'R'),
           'T': gate_group(df[df['group'] == 'T'], 'T')}
    print(json.dumps(out, indent=2, default=float))
    (ROOT / 'data-cache' / 'blend-study-rookies-result.json').write_text(json.dumps(out, indent=2, default=float))

if __name__ == '__main__':
    main()
