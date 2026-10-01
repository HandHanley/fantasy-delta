#!/usr/bin/env python3
"""
DELTA Mid-Season Team Change Study — scripts/midseason-trade-study.py
Pre-registration: docs/PREREG-midseason-trades.md (read it first; this script implements it).

    python3 scripts/midseason-trade-study.py --count   # eligibility counts only. Computes NO errors.
    python3 scripts/midseason-trade-study.py --crash   # every outcome replaced by synthetic numbers
                                                       # BEFORE anything is computed. Proves the code
                                                       # runs and checks the design on noise and on a
                                                       # planted effect. Never reads a real outcome.
    python3 scripts/midseason-trade-study.py --run     # the study. Refuses unless the pre-registration
                                                       # is committed to git and unmodified.

The test applies the SHIPPED offseason size (x0.898) to mid-season movers. Nothing about the size is
fitted on these players, so none of the few cases are spent estimating it. Stayers calibrate both sides.

Question: when a player changes teams DURING a season, does he score less over the rest of that
season than DELTA's in-season forecast says — relative to players who stayed put all season?

Machinery imported UNCHANGED from the locked scripts/blend-study.py: the played-game rule (live DNP
rule), backtest.js scoring, the preseason starting number (A) and the Start Profile penalty. The
forecast is the engine's shipped in-season form D at K = 4 (every graded player has 8+ prior games).
"""
import argparse, hashlib, importlib.util, json, subprocess, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
_s = importlib.util.spec_from_file_location('bs', ROOT / 'scripts' / 'blend-study.py')
bs = importlib.util.module_from_spec(_s); _s.loader.exec_module(bs)

PREREG    = 'docs/PREREG-midseason-trades.md'
bs.YEARS  = list(range(2013, 2026))     # 2012 has no snap counts (0 rows) — never loaded
SEASONS   = list(range(2016, 2026))     # graded seasons: all three prior seasons under one rule
HALVES    = ([2016, 2017, 2018, 2019, 2020], [2021, 2022, 2023, 2024, 2025])
K         = 4                           # engine BLEND_K for 8+ prior games
SHIPPED   = 0.898                       # TEAM_CHANGE_MULT, delta-engine.js 28a — the size under test, fixed
MIN_BEFORE, MIN_AFTER = 3, 3            # played games on each side of the checkpoint
POS_GATE_N = 25                         # positions with this many movers are gated
SHUFFLES, SEED = 2000, 20261001
CRASH_SIMS = 200
CRASH_SD   = (0.35, 0.45)   # 0.35 reproduces the blend study's real typical miss scaled to movers; 0.45 pessimistic

# ── teams ─────────────────────────────────────────────────────────────────
def team_weeks():
    """(pid, season) -> list of (week, team) from stats rows, regular season, sorted by week."""
    rows = []
    for y in bs.YEARS:
        w = pd.read_parquet(bs.fetch(f'{bs.REL}/stats_player/stats_player_week_{y}.parquet', bs.CACHE / f'w{y}.parquet'),
                            columns=['player_id', 'season', 'week', 'season_type', 'team'])
        rows.append(w[(w['season_type'] == 'REG') & w['team'].notna()])
    t = pd.concat(rows, ignore_index=True)
    t['pid'] = t['player_id'].astype(str)
    out = {}
    for (pid, s), g in t.sort_values('week').groupby(['pid', 'season']):
        out[(pid, int(s))] = list(zip(g['week'].astype(int), g['team']))
    return out

def classify(tw, Y, pid, prev_main):
    """'stay' | ('move', switch_week) | None (excluded). Offseason movers are excluded from both groups."""
    seq = tw.get((pid, Y))
    if not seq:
        return None
    teams = [t for _, t in seq]
    if prev_main is not None and teams[0] != prev_main:
        return None                                   # changed teams in the offseason
    changes = [i for i in range(1, len(teams)) if teams[i] != teams[i - 1]]
    if not changes:
        return 'stay'
    if len(changes) == 1:
        return ('move', seq[changes[0]][0])
    return None                                       # more than one switch: excluded

# ── rows ──────────────────────────────────────────────────────────────────
def build_rows(g, tw):
    rows = []
    for pid, pg in g.groupby('pid', sort=False):
        seasons = {s: sg for s, sg in pg.groupby('season')}
        for Y in SEASONS:
            if Y not in seasons:
                continue
            pos = seasons[Y]['spos'].mode().iat[0]
            numr = den = 0.0; prior_g = 0
            for k, bw in zip((1, 2, 3), (0.6, 0.3, 0.1)):      # blend-study A, verbatim
                sg = seasons.get(Y - k)
                if sg is None or len(sg) == 0:
                    continue
                n = len(sg); v = bs.bt_pts(sg, pos).sum() / n
                w = bw * min(1.0, n / 8)
                numr += w * v; den += w; prior_g += n
            if den == 0 or prior_g < bs.MIN_PRIOR:
                continue
            pre = numr / den
            prev = tw.get((pid, Y - 1))
            prev_main = (pd.Series([t for _, t in prev]).mode().sort_values().iat[0]) if prev else None
            kind = classify(tw, Y, pid, prev_main)
            if kind is None:
                continue
            cur = seasons[Y]; wk = cur['week'].to_numpy()
            cur_bt = bs.bt_pts(cur, pos)
            hist = pg[pg['season'] < Y]
            hist_sp = bs.sp_pts(hist, pos) if len(hist) else np.array([])
            cur_sp = bs.sp_pts(cur, pos)
            checks = [kind[1] - 1] if kind != 'stay' else range(MIN_BEFORE, 17)
            for N in checks:
                before = wk <= N; after = wk > N
                G = int(before.sum()); A_n = int(after.sum())
                if G < MIN_BEFORE or A_n < MIN_AFTER:
                    continue
                sofar = cur_bt[before].sum() / G
                dvol = bs.d_volatility(np.concatenate([hist_sp, cur_sp[before]]), pos)
                rows.append({'pid': pid, 'name': cur['name'].iat[0], 'season': Y, 'pos': pos, 'N': int(N),
                             'mover': kind != 'stay', 'pre': pre,
                             'D': ((G / (G + K)) * sofar + (K / (G + K)) * pre) * (1 + 0.5 * dvol),
                             'actual': cur_bt[after].sum() / A_n, 'n_after': A_n})
    return pd.DataFrame(rows)

# ── the test ──────────────────────────────────────────────────────────────
def mult(p, a): return float((p * a).sum() / (p * p).sum())    # best-fit multiplier through zero
def rmse(e): return float(np.sqrt(np.mean(e ** 2)))

def loso(df):
    """Leave one season out: every mover is forecast with multipliers fitted on the OTHER seasons."""
    mv = df[df['mover']].copy()
    base = np.zeros(len(mv)); cand = np.zeros(len(mv)); rs = {}
    for Y in SEASONS:
        tr = df[df['season'] != Y]; te = mv['season'].to_numpy() == Y
        if not te.any():
            continue
        st = tr[~tr['mover']]
        mS = {N: mult(g['D'].to_numpy(), g['actual'].to_numpy()) for N, g in st.groupby('N')}
        mS_all = mult(st['D'].to_numpy(), st['actual'].to_numpy())
        trm = tr[tr['mover']]
        p_tr = trm['D'].to_numpy() * np.array([mS.get(n, mS_all) for n in trm['N']])
        r = mult(p_tr, trm['actual'].to_numpy()); rs[Y] = r
        p_te = mv.loc[te, 'D'].to_numpy() * np.array([mS.get(n, mS_all) for n in mv.loc[te, 'N']])
        base[te] = p_te; cand[te] = p_te * SHIPPED       # the test: the shipped size, nothing fitted
    mv['base'] = base; mv['cand'] = cand
    return mv, rs                                      # rs: a freshly fitted size per season, REPORTED ONLY

def grade(mv, rng=None, shuffles=SHUFFLES):
    a = mv['actual'].to_numpy(); eb = mv['base'].to_numpy() - a; ec = mv['cand'].to_numpy() - a
    lift = 1 - rmse(ec) / rmse(eb)
    rng = rng or np.random.default_rng(SEED)
    hits = 0
    for _ in range(shuffles):                          # paired: swap the two REAL forecasts per player
        sw = rng.random(len(a)) < 0.5
        b2 = np.where(sw, ec, eb); c2 = np.where(sw, eb, ec)
        if 1 - rmse(c2) / rmse(b2) >= lift: hits += 1
    p = (hits + 1) / (shuffles + 1)
    halves = [1 - rmse(ec[mv['season'].isin(h)]) / rmse(eb[mv['season'].isin(h)]) for h in HALVES]
    pos = {}
    for P, gm in mv.groupby('pos'):
        m = mv['pos'].to_numpy() == P
        pos[P] = (int(m.sum()), 1 - rmse(ec[m]) / rmse(eb[m]))
    gates = {'1_size': lift >= 0.02, '2_fluke': p < 0.05, '3_halves': all(h > 0 for h in halves),
             '4_positions': all(l >= -0.01 for n, l in pos.values() if n >= POS_GATE_N)}
    return {'lift': lift, 'p': p, 'halves': halves, 'pos': pos, 'gates': gates, 'passed': all(gates.values()),
            'rmse_base': rmse(eb), 'rmse_cand': rmse(ec),
            'mae_base': float(np.mean(np.abs(eb))), 'mae_cand': float(np.mean(np.abs(ec)))}

def require_locked_prereg():
    try:
        subprocess.run(['git', 'ls-files', '--error-unmatch', PREREG], cwd=ROOT, check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        sys.exit(f'[MIDSEASON] REFUSED: {PREREG} is not committed. Commit it first — that is the lock.')
    if subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', PREREG], cwd=ROOT).returncode != 0:
        sys.exit(f'[MIDSEASON] REFUSED: {PREREG} has uncommitted edits. Commit or discard them.')
    sha = subprocess.run(['git', 'log', '-1', '--format=%H %cI', '--', PREREG], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip()
    return {'prereg_commit': sha, 'prereg_sha256': hashlib.sha256((ROOT / PREREG).read_bytes()).hexdigest()[:16]}

def main():
    ap = argparse.ArgumentParser(); m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument('--count', action='store_true'); m.add_argument('--crash', action='store_true')
    m.add_argument('--run', action='store_true'); a = ap.parse_args()
    lock = require_locked_prereg() if a.run else None
    g, info = bs.load_games(); tw = team_weeks()
    df = build_rows(g, tw)
    if not a.run:
        df['actual'] = np.nan                          # count and crash never keep a real outcome
    mv = df[df['mover']]
    print(f'[MIDSEASON] played games loaded: {info["played_games"]:,}; snap rows unmapped: {info["snap_rows_unmapped_to_id"]:,}')
    print(f'[MIDSEASON] movers {len(mv)} | stayer checkpoints {int((~df["mover"]).sum()):,} '
          f'from {df.loc[~df["mover"], ["pid","season"]].drop_duplicates().shape[0]:,} stayer seasons')
    print('[MIDSEASON] movers by position:', mv['pos'].value_counts().to_dict())
    print('[MIDSEASON] movers by season:', mv['season'].value_counts().sort_index().to_dict())
    print('[MIDSEASON] movers by half:', [int(mv['season'].isin(h).sum()) for h in HALVES])
    print('[MIDSEASON] checkpoint week (last game before the switch):', mv['N'].value_counts().sort_index().to_dict())
    if a.count:
        return
    if a.crash:
        rng = np.random.default_rng(SEED)
        stay_lvl = 0.95                                # every forecast runs a little high, as in life
        for sd, label, effect in ((sd, l, e) for sd in CRASH_SD for l, e in
                                  (('NOISE, no mover effect', 1.00), ('PLANTED, movers x0.85', 0.85),
                                   ('PLANTED, movers x0.90', 0.90))):
            passes = []; lifts = []
            for _ in range(CRASH_SIMS):
                noise = rng.lognormal(0, sd, len(df))
                sim = df.copy(); sim['actual'] = sim['D'] * stay_lvl * noise * np.where(sim['mover'], effect, 1.0)
                mvs, _ = loso(sim); r = grade(mvs, rng, shuffles=200)
                passes.append(r['passed']); lifts.append(r['lift'])
            print(f'[CRASH] noise {sd:.2f} {label:26s} pass rate {np.mean(passes):5.1%} over {CRASH_SIMS} simulations; '
                  f'median lift {np.median(lifts):+.1%}')
        print('[CRASH] synthetic outcomes only — says nothing about real mid-season movers.')
        return
    mvs, rs = loso(df); r = grade(mvs)
    r_all = mult(mvs['base'].to_numpy(), mvs['actual'].to_numpy())
    out = {**lock, **{k: v for k, v in r.items()}, 'tested_size': SHIPPED, 'n_movers': int(len(mvs)),
           'reported_only': {'fitted_size_by_left_out_season': rs, 'fitted_size_all_seasons': r_all}}
    print(json.dumps(out, indent=2, default=float))
    (ROOT / 'data-cache').mkdir(exist_ok=True)
    (ROOT / 'data-cache' / 'midseason-result.json').write_text(json.dumps(out, indent=2, default=float))

if __name__ == '__main__':
    main()
