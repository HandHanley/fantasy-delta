#!/usr/bin/env python3
"""
DELTA Usage Blend Study — scripts/usage-study.py
Pre-registration: docs/PREREG-usage-blend.md

    python3 scripts/usage-study.py --count   # eligibility only; computes NO errors
    python3 scripts/usage-study.py --run     # refuses unless the pre-registration is committed

Question: early in a season, does USAGE (targets and carries) predict a player's rest-of-season
points per game better than his points so far alone?

  Live blend (today, K by history: 4 / 2 thin / 3 rookie):
      w x (PPG so far) + (1 - w) x preseason,                    w = G / (G + K)
  Usage blend (the contender, one weight v):
      w x [ (1 - v) x PPG so far + v x xFP so far ] + (1 - w) x preseason
  xFP = what an average target and carry at his position were worth over the THREE PREVIOUS seasons
        (league-wide, half PPR + TE premium), times his targets and carries, per game.
  v = 0 is exactly today's blend. v is chosen once on training seasons (grid 0.0-1.0 by 0.1).

RB / WR / TE only (targets and carries do not describe how a QB scores). Checkpoints after Weeks
2, 3, 4 and 6. Shared machinery: scripts/blend-study.py (games, scoring, IDs) and
scripts/blend-study-rookies.py (rookie table and its no-leak fitting rules), imported unchanged.
"""
import argparse, importlib.util, json, math, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
def _load(n, f):
    s = importlib.util.spec_from_file_location(n, ROOT / 'scripts' / f); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
rk = _load('rk', 'blend-study-rookies.py'); bs = rk.bs

PREREG   = 'docs/PREREG-usage-blend.md'
POS      = ['RB', 'WR', 'TE']
CHECKS   = [2, 3, 4, 6]
TRAIN, HELDOUT = bs.TRAIN, bs.HELDOUT
V_GRID   = [round(0.1 * i, 1) for i in range(11)]
K        = {'vet': 4, 'thin': 2, 'rookie': 3}              # live engine 2026-09-26c onward
MIN_AFTER, MIN_POS_N, SEED, SHUFFLES = 4, 30, 20260927, 2000

def load_usage(g):
    """Attach targets and carries to every played game (snap-only games have 0 of both)."""
    rows = []
    for y in bs.YEARS:
        w = pd.read_parquet(bs.fetch(f'{bs.REL}/stats_player/stats_player_week_{y}.parquet', bs.CACHE / f'w{y}.parquet'),
                            columns=['player_id', 'season', 'week', 'season_type', 'targets', 'carries'])
        rows.append(w[w['season_type'] == 'REG'])
    u = pd.concat(rows, ignore_index=True)
    u = pd.DataFrame({'pid': u['player_id'].astype(str), 'season': u['season'].astype(int), 'week': u['week'].astype(int),
                      'tgt': u['targets'].fillna(0).astype(float), 'car': u['carries'].fillna(0).astype(float)})
    g = g.merge(u, on=['pid', 'season', 'week'], how='left')
    g['tgt'] = g['tgt'].fillna(0.0); g['car'] = g['car'].fillna(0.0)
    return g

def opp_values(g):
    """Per season Y and position: average points per target and per carry over Y-3..Y-1, league-wide."""
    vals = {}
    for Y in TRAIN + HELDOUT:
        for pos in POS:
            d = g[(g['season'].between(Y - 3, Y - 1)) & (g['spos'] == pos)]
            rp = 1.0 if pos == 'TE' else 0.5
            rec_pts = (d['rec'] * rp + d['rey'] * 0.1 + d['ret'] * 6).sum()
            rush_pts = (d['ry'] * 0.1 + d['rt'] * 6).sum()
            vals[(Y, pos)] = (rec_pts / max(d['tgt'].sum(), 1), rush_pts / max(d['car'].sum(), 1))
    return vals

def build_rows(g, draft):
    vals = opp_values(g)
    rs = rk.rookie_seasons(g, draft)
    tables = {Y: rk.fit_table(rs, [s for s in rk.TABLE_FIT if s != Y]) for Y in TRAIN}
    held = rk.fit_table(rs, rk.TABLE_FIT)
    rows = []
    for pid, pg in g.groupby('pid', sort=False):
        seasons = {s: sg for s, sg in pg.groupby('season')}
        for Y in TRAIN + HELDOUT:
            cur = seasons.get(Y)
            if cur is None: continue
            pos = cur['spos'].mode().iat[0]
            if pos not in POS: continue
            prior_g = sum(len(seasons.get(Y - k, [])) for k in (1, 2, 3))
            if pid in draft and draft[pid][0] == Y:
                pre = (held if Y in HELDOUT else tables[Y])[pos][rk.tier(draft[pid][1])]; grp = 'rookie'
            elif prior_g >= 1:
                numr = den = 0.0
                for k, bw in zip((1, 2, 3), (0.6, 0.3, 0.1)):
                    sg = seasons.get(Y - k)
                    if sg is None or len(sg) == 0: continue
                    n = len(sg); ww = bw * min(1.0, n / 8)
                    numr += ww * bs.bt_pts(sg, pos).sum() / n; den += ww
                pre = numr / den; grp = 'vet' if prior_g >= 8 else 'thin'
            else:
                continue
            if pre is None or np.isnan(pre): continue
            vt, vc = vals[(Y, pos)]
            pts = bs.bt_pts(cur, pos); wk = cur['week'].to_numpy()
            xfp = (cur['tgt'].to_numpy() * vt + cur['car'].to_numpy() * vc)
            for N in CHECKS:
                b, a = wk <= N, wk > N
                G, An = int(b.sum()), int(a.sum())
                if G < 1 or An < MIN_AFTER: continue
                rows.append({'pid': pid, 'season': Y, 'pos': pos, 'group': grp, 'N': N, 'G': G, 'K': K[grp],
                             'pre': pre, 'sofar': pts[b].mean(), 'xfp': xfp[b].mean(), 'actual': pts[a].mean()})
    return pd.DataFrame(rows), vals

def pred(df, v):
    w = df['G'].to_numpy() / (df['G'].to_numpy() + df['K'].to_numpy())
    obs = (1 - v) * df['sofar'].to_numpy() + v * df['xfp'].to_numpy()
    return w * obs + (1 - w) * df['pre'].to_numpy()

def pooled(err, df):                                     # mean of the per-checkpoint RMSEs
    n = df['N'].to_numpy()
    return float(np.mean([math.sqrt(np.mean(err[n == c] ** 2)) for c in CHECKS if (n == c).any()]))

def main():
    ap = argparse.ArgumentParser(); m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument('--count', action='store_true'); m.add_argument('--run', action='store_true')
    a = ap.parse_args()
    lock = None
    if a.run: bs.PREREG = PREREG; lock = bs.require_locked_prereg()
    g, _ = bs.load_games()
    g = load_usage(g)
    df, vals = build_rows(g, rk.load_draft())
    print('[USAGE] points per target / per carry used for 2023:', {p: tuple(round(x, 3) for x in vals[(2023, p)]) for p in POS})
    print('[USAGE] graded player-checkpoints (rows: season, columns: after week N)')
    print(df.groupby(['season', 'N']).size().unstack('N').to_string())
    h = df[df['season'].isin(HELDOUT)]
    print(f"[USAGE] training rows {int(df['season'].isin(TRAIN).sum())} · held-out rows {len(h)} · held-out player-seasons "
          f"{h[['pid','season']].drop_duplicates().shape[0]} · by group {h[['pid','season','group']].drop_duplicates()['group'].value_counts().to_dict()} "
          f"· by position {h[['pid','season','pos']].drop_duplicates()['pos'].value_counts().to_dict()}")
    if a.count: print('[USAGE] --count: no errors computed.'); return

    tr, te = df[df['season'].isin(TRAIN)], df[df['season'].isin(HELDOUT)]
    def err(d, v): return pred(d, v) - d['actual'].to_numpy()
    oof = {v: float(np.mean([pooled(err(tr[tr['season'] == s], v), tr[tr['season'] == s]) for s in TRAIN])) for v in V_GRID}
    v_star = min(V_GRID, key=lambda v: (oof[v], v))       # ties go to the smaller v (closer to today)
    print('[USAGE] training error by v:', {v: round(e, 4) for v, e in oof.items()}, '-> chosen v =', v_star)
    out = {'lock': lock, 'v_chosen': v_star, 'training_error_by_v': oof}
    if v_star == 0.0:
        out.update({'SHIP': False, 'note': 'v = 0 chosen on training: usage adds nothing to the live blend.'})
        print(json.dumps(out, indent=2, default=float)); return

    e0, e1 = err(te, 0.0), err(te, v_star)
    r0, r1 = pooled(e0, te), pooled(e1, te); lift = 1 - r1 / r0
    rng = np.random.default_rng(SEED)
    keys = (te['pid'] + '|' + te['season'].astype(str)).to_numpy()
    uniq, inv = np.unique(keys, return_inverse=True); ge = 0
    for _ in range(SHUFFLES):
        f = (rng.random(len(uniq)) < 0.5)[inv]
        if 1 - pooled(np.where(f, e0, e1), te) / pooled(np.where(f, e1, e0), te) >= lift: ge += 1
    p = (ge + 1) / (SHUFFLES + 1)
    s_arr, p_arr, g_arr, n_arr = te['season'].to_numpy(), te['pos'].to_numpy(), te['group'].to_numpy(), te['N'].to_numpy()
    sub = lambda mk: 1 - pooled(e1[mk], te[mk]) / pooled(e0[mk], te[mk]) if mk.any() else None
    per_season = {int(s): sub(s_arr == s) for s in HELDOUT}
    pos_n = {ps: te[p_arr == ps][['pid', 'season']].drop_duplicates().shape[0] for ps in POS}
    per_pos = {ps: sub(p_arr == ps) for ps in POS}
    per_group = {gg: sub(g_arr == gg) for gg in K}
    per_check = {c: 1 - math.sqrt(np.mean(e1[n_arr == c] ** 2)) / math.sqrt(np.mean(e0[n_arr == c] ** 2)) for c in CHECKS}
    gates = {'size_>=2%': lift >= 0.02, 'p<0.05': p < 0.05,
             'every_heldout_season': all(v is not None and v > 0 for v in per_season.values()),
             'no_position_worse_than_-1%_(n>=30)': all(v >= -0.01 for k, v in per_pos.items() if v is not None and pos_n[k] >= MIN_POS_N)}
    out.update({'heldout': {'live_rmse': r0, 'usage_rmse': r1, 'lift': lift, 'p': p},
                'per_season': per_season, 'per_position': per_pos, 'position_player_seasons': pos_n,
                'per_group_reported_only': per_group, 'per_checkpoint_reported_only': per_check,
                'gates': gates, 'SHIP': all(gates.values())})
    print(json.dumps(out, indent=2, default=float))
    (ROOT / 'data-cache' / 'usage-study-result.json').write_text(json.dumps(out, indent=2, default=float))

if __name__ == '__main__':
    main()
