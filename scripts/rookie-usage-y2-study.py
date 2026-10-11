#!/usr/bin/env python3
"""
DELTA Rookie Playing-Time Study (Year Two) — scripts/rookie-usage-y2-study.py
Pre-registration: docs/PREREG-rookie-usage-y2.md

    python3 scripts/rookie-usage-y2-study.py --count   # eligibility only; reads NO year-two points
    python3 scripts/rookie-usage-y2-study.py --crash   # full path with year-two points replaced by noise
    python3 scripts/rookie-usage-y2-study.py --run     # refuses unless the pre-registration is committed

Question: after Week 4 (and Week 8) of a drafted RB/WR/TE's rookie season, does his PLAYING TIME so far
(targets and carries, valued as points) tell us his YEAR-TWO points per game better than DELTA's rookie
projection does today?

  Today (live engine):  w x PPG so far + (1 - w) x draft-slot baseline,          w = G / (G + 3)
  Contender (one v):    w x [(1 - v) x PPG so far + v x xFP so far] + (1 - w) x draft-slot baseline
  xFP = his targets and carries, each valued at what an average one at his position was worth over
        the THREE PREVIOUS seasons (league-wide, half PPR + TE premium), per game.
  Outcome: his year-two PPG (4+ games played that season).

v chosen once on the 2018-2021 classes; graded once on the 2022-2024 classes. The 2015-2017 classes
are an era check, reported only. Machinery (games, scoring, IDs, draft table, lock) is imported
unchanged from scripts/blend-study.py and scripts/blend-study-rookies.py; xFP values follow
scripts/usage-study.py exactly.
"""
import argparse, importlib.util, json, math, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
def _load(n, f):
    s = importlib.util.spec_from_file_location(n, ROOT / 'scripts' / f); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
rk = _load('rk', 'blend-study-rookies.py'); bs = rk.bs

PREREG    = 'docs/PREREG-rookie-usage-y2.md'
POS       = ['RB', 'WR', 'TE']
CHECKS    = [4, 8]
TRAIN     = [2018, 2019, 2020, 2021]          # rookie classes used to choose v
TEST      = [2022, 2023, 2024]                # rookie classes graded once
ERA       = [2015, 2016, 2017]                # era check, reported only
TABLE_SEASONS = list(range(2015, 2025))       # rookie seasons available for the draft-slot table
V_GRID    = [round(0.1 * i, 1) for i in range(11)]
K_ROOKIE  = 3                                 # live engine
MIN_Y2    = 4                                 # year-two games played to be graded
MIN_POS_N = 30
SEED, SHUFFLES = 20261010, 2000

# xFP for the 2015 class needs 2012-2014. nflverse has player stats for 2012 but no snap-count file
# (snap counts start 2013). Snaps only decide whether a zero-production week counts as played; a
# zero-production week adds nothing to league-wide points per target or carry, so 2012 is loaded
# with an empty snap table. 2012 is never graded and never feeds anyone's PPG.
bs.YEARS = list(range(2012, 2026))
_fetch = bs.fetch
def _fetch_patched(url, dest):
    if url.endswith('snap_counts_2012.parquet'):
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame({'pfr_player_id': pd.Series(dtype=str), 'season': pd.Series(dtype=int),
                          'week': pd.Series(dtype=int), 'game_type': pd.Series(dtype=str),
                          'offense_snaps': pd.Series(dtype=float)}).to_parquet(dest)
        return dest
    return _fetch(url, dest)
bs.fetch = _fetch_patched

def load_usage(g):
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

def opp_values(g, seasons):
    """usage-study.py opp_values(), for any season: points per target / per carry over Y-3..Y-1."""
    vals = {}
    for Y in seasons:
        for pos in POS:
            d = g[(g['season'].between(Y - 3, Y - 1)) & (g['spos'] == pos)]
            rp = 1.0 if pos == 'TE' else 0.5
            rec_pts = (d['rec'] * rp + d['rey'] * 0.1 + d['ret'] * 6).sum()
            rush_pts = (d['ry'] * 0.1 + d['rt'] * 6).sum()
            vals[(Y, pos)] = (rec_pts / max(d['tgt'].sum(), 1), rush_pts / max(d['car'].sum(), 1))
    return vals

def build_rows(g, draft, noise=None):
    classes = ERA + TRAIN + TEST
    vals = opp_values(g, classes)
    rs = rk.rookie_seasons(g, draft)
    # Draft-slot baseline refit without the class being predicted (no leak). Rookie-season PPG only.
    tables = {Y: rk.fit_table(rs, [s for s in TABLE_SEASONS if s != Y]) for Y in classes}
    rows = []
    for pid, pg in g.groupby('pid', sort=False):
        if pid not in draft: continue
        Y, pick = draft[pid]
        if Y not in classes: continue
        cur, nxt = pg[pg['season'] == Y], pg[pg['season'] == Y + 1]
        if len(cur) == 0: continue
        pos = cur['spos'].mode().iat[0]
        if pos not in POS: continue
        if len(nxt) < MIN_Y2: continue                              # eligibility: games, not points
        pre = tables[Y][pos][rk.tier(pick)]
        if pre is None or np.isnan(pre): continue
        vt, vc = vals[(Y, pos)]
        pts = bs.bt_pts(cur, pos); wk = cur['week'].to_numpy()
        xfp = cur['tgt'].to_numpy() * vt + cur['car'].to_numpy() * vc
        if noise is None:
            y2 = None if a_count else float(bs.bt_pts(nxt, pos).mean())
        else:
            y2 = float(noise.uniform(0, 20))
        for N in CHECKS:
            b = wk <= N; G = int(b.sum())
            if G < 1: continue
            rows.append({'pid': pid, 'cls': Y, 'pos': pos, 'N': N, 'G': G, 'pick': pick, 'pre': pre,
                         'sofar': float(pts[b].mean()), 'xfp': float(xfp[b].mean()), 'y2': y2})
    return pd.DataFrame(rows), vals

def pred(df, v):
    G = df['G'].to_numpy(); w = G / (G + K_ROOKIE)
    return w * ((1 - v) * df['sofar'].to_numpy() + v * df['xfp'].to_numpy()) + (1 - w) * df['pre'].to_numpy()

def pooled(err, df):                                                # mean of the per-checkpoint RMSEs
    n = df['N'].to_numpy()
    return float(np.mean([math.sqrt(np.mean(err[n == c] ** 2)) for c in CHECKS if (n == c).any()]))

a_count = False
def main():
    global a_count
    ap = argparse.ArgumentParser(); m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument('--count', action='store_true'); m.add_argument('--crash', action='store_true'); m.add_argument('--run', action='store_true')
    a = ap.parse_args(); a_count = a.count
    lock = None
    if a.run: bs.PREREG = PREREG; lock = bs.require_locked_prereg()
    g, info = bs.load_games()
    g = load_usage(g)
    df, vals = build_rows(g, rk.load_draft(), noise=np.random.default_rng(1) if a.crash else None)
    print('[ROOKIE-Y2] points per target / per carry used for the 2022 class:', {p: tuple(round(x, 3) for x in vals[(2022, p)]) for p in POS})
    print('[ROOKIE-Y2] graded rookies (rows: class, columns: after week N)')
    print(df.groupby(['cls', 'N']).size().unstack('N').to_string())
    t = df[df['cls'].isin(TEST)]
    print(f"[ROOKIE-Y2] training rookies {df[df['cls'].isin(TRAIN)]['pid'].nunique()} · test rookies {t['pid'].nunique()} "
          f"· by position {t[['pid','pos']].drop_duplicates()['pos'].value_counts().to_dict()} · era-check rookies {df[df['cls'].isin(ERA)]['pid'].nunique()}")
    if a.count: print('[ROOKIE-Y2] --count: no year-two points read.'); return

    def err(d, v): return pred(d, v) - d['y2'].to_numpy()
    tr, te, era = df[df['cls'].isin(TRAIN)], df[df['cls'].isin(TEST)], df[df['cls'].isin(ERA)]
    train_err = {v: float(np.mean([pooled(err(tr[tr['cls'] == c], v), tr[tr['cls'] == c]) for c in TRAIN])) for v in V_GRID}
    v_star = min(V_GRID, key=lambda v: (train_err[v], v))          # ties go to the smaller v
    print('[ROOKIE-Y2] training error by v:', {v: round(e, 4) for v, e in train_err.items()}, '-> chosen v =', v_star)
    out = {'mode': 'CRASH TEST (noise outcomes)' if a.crash else 'RUN', 'lock': lock, 'v_chosen': v_star, 'training_error_by_v': train_err}
    if v_star == 0.0:
        out.update({'SHIP': False, 'note': 'v = 0 chosen on training: playing time adds nothing.'})
        print(json.dumps(out, indent=2, default=float)); return

    e0, e1 = err(te, 0.0), err(te, v_star)
    r0, r1 = pooled(e0, te), pooled(e1, te); lift = 1 - r1 / r0
    # Paired randomisation: for each rookie, randomly swap which forecast is "today" and which is
    # "playing time". Tests improvement against ZERO, not against a noisy nudge (market-form flaw).
    rng = np.random.default_rng(SEED)
    uniq, inv = np.unique(te['pid'].to_numpy(), return_inverse=True); ge = 0
    for _ in range(SHUFFLES):
        f = (rng.random(len(uniq)) < 0.5)[inv]
        if 1 - pooled(np.where(f, e0, e1), te) / pooled(np.where(f, e1, e0), te) >= lift: ge += 1
    p = (ge + 1) / (SHUFFLES + 1)
    c_arr, p_arr, n_arr = te['cls'].to_numpy(), te['pos'].to_numpy(), te['N'].to_numpy()
    sub = lambda mk: 1 - pooled(e1[mk], te[mk]) / pooled(e0[mk], te[mk]) if mk.any() else None
    per_class = {int(c): sub(c_arr == c) for c in TEST}
    pos_n = {ps: te[p_arr == ps]['pid'].nunique() for ps in POS}
    per_pos = {ps: sub(p_arr == ps) for ps in POS}
    per_check = {c: 1 - math.sqrt(np.mean(e1[n_arr == c] ** 2)) / math.sqrt(np.mean(e0[n_arr == c] ** 2)) for c in CHECKS}
    ea0, ea1 = err(era, 0.0), err(era, v_star)
    era_lift = 1 - pooled(ea1, era) / pooled(ea0, era) if len(era) else None
    gates = {'size_>=2%': lift >= 0.02, 'p<0.05': p < 0.05,
             'every_test_class': all(v is not None and v > 0 for v in per_class.values()),
             'no_position_worse_than_-1%_(n>=30)': all(v >= -0.01 for k, v in per_pos.items() if v is not None and pos_n[k] >= MIN_POS_N)}
    out.update({'test': {'today_rmse': r0, 'playing_time_rmse': r1, 'lift': lift, 'p': p, 'rookies': int(te['pid'].nunique())},
                'per_class': per_class, 'per_position': per_pos, 'position_rookies': pos_n,
                'per_checkpoint_reported_only': per_check, 'era_check_2015_2017_reported_only': era_lift,
                'gates': gates, 'SHIP': all(gates.values())})
    print(json.dumps(out, indent=2, default=float))
    if a.run: (ROOT / 'data-cache' / 'rookie-usage-y2-result.json').write_text(json.dumps(out, indent=2, default=float))

if __name__ == '__main__':
    main()
