#!/usr/bin/env python3
"""
DELTA QB Starter Lift x Missed-Time Cut — scripts/qb-missedtime-study.py
Pre-registration: docs/PREREG-qb-missedtime.md (read it first; this script implements it).

    python3 scripts/qb-missedtime-study.py --count   # eligibility counts only. Computes NO errors.
    python3 scripts/qb-missedtime-study.py --crash   # every outcome replaced by synthetic numbers BEFORE
                                                     # anything is computed. Never reads a real outcome.
    python3 scripts/qb-missedtime-study.py --run     # the study. Refuses unless the pre-registration is
                                                     # committed to git and unmodified.

Question: for a Week-1 starting QB who played under 8 games last season, the engine first lifts his
starting number toward a typical starter (calcProj QB STARTER-BASELINE OVERRIDE, K = 6) and THEN cuts
it for missed time (missedTimeMult). Is the cut double-counting? Live = lift x cut; candidate = lift only.

Imported UNCHANGED: the engine's starting number (scripts/weights-study.py base(), ENGINE = 3/2/1
'steps', verified 315/315 against the live engine), the missed-time sizes (scripts/startprofile-study.py
mt_mult(), identical to delta-engine.js), and backtest scoring (scripts/blend-study.py bt_pts()).
"""
import argparse, hashlib, importlib.util, json, subprocess, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
def _load(name, f):
    s = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
bs = _load('bs_q', 'blend-study.py'); ws = _load('ws_q', 'weights-study.py'); sp = _load('sp_q', 'startprofile-study.py')

PREREG    = 'docs/PREREG-qb-missedtime.md'
LOAD      = list(range(1999, 2026))           # nflverse weekly stats start 1999
SEASONS   = list(range(2002, 2026))           # every graded season has all three prior seasons on file
HALVES    = (list(range(2002, 2014)), list(range(2014, 2026)))
K_LIFT    = 6                                 # delta-engine.js calcProj, 'fitted 2000-2014'
SB_MIN_G, SB_MIN_N = 14, 8                    # qbStarterBaseline(): median PPG of QBs with 14+ games
WK1_MIN_ATT = 10                              # Week-1 starter: most attempts in his team's first game
MIN_NOW   = 4                                 # graded: 4+ played games in the season
GROUP_GATE_N = 25
SHUFFLES, SEED = 2000, 20261002
CRASH_SIMS, CRASH_SD = 200, (0.25, 0.35)

STAT = {'py': ['passing_yards'], 'pt': ['passing_tds'], 'pi': ['passing_interceptions'],
        'ry': ['rushing_yards'], 'rt': ['rushing_tds'], 'rec': ['receptions'],
        'rey': ['receiving_yards'], 'ret': ['receiving_tds'],
        'vol': ['attempts', 'completions', 'carries', 'targets']}

def load():
    """One row per (player, season, week) with ANY production — the same rule in every season."""
    out = []
    for y in LOAD:
        w = pd.read_parquet(bs.fetch(f'{bs.REL}/stats_player/stats_player_week_{y}.parquet', bs.CACHE / f'w{y}.parquet'))
        w = w[w['season_type'] == 'REG']
        d = pd.DataFrame({'pid': w['player_id'].astype(str), 'name': w['player_display_name'],
                          'position': w['position'], 'team': w['team'],
                          'season': w['season'].astype(int), 'week': w['week'].astype(int),
                          'att': w['attempts'].fillna(0)})
        for k, cols in STAT.items():
            d[k] = sum(w[c].fillna(0) for c in cols if c in w.columns)
        d = d[(d[list(STAT)] != 0).any(axis=1)]
        out.append(d)
    return pd.concat(out, ignore_index=True)

def group_of(g0):
    return 'skipped season' if g0 == 0 else ('1-3 games' if g0 <= 3 else '4-7 games')

def build(g):
    qbseas = {(p, s): sg for (p, s), sg in g.groupby(['pid', 'season'])}
    ppg = lambda sg: bs.bt_pts(sg, 'QB').sum() / len(sg)
    sb = {}
    for y in range(min(LOAD), max(LOAD) + 1):
        v = [ppg(sg) for (p, s), sg in qbseas.items() if s == y and len(sg) >= SB_MIN_G and (sg['position'] == 'QB').any()]
        sb[y] = float(np.median(v)) if len(v) >= SB_MIN_N else 0.0
    rows = []
    for Y in SEASONS:
        cur = g[g['season'] == Y]                 # any listed position: nflverse labels a player by his LATEST
                                                  # position (Terrelle Pryor = WR), so the starter is found by attempts
        for team, tg in cur.groupby('team'):
            fw = tg['week'].min(); st = tg[tg['week'] == fw].sort_values('att', ascending=False).iloc[0]
            if st['att'] < WK1_MIN_ATT:
                continue
            pid = st['pid']
            gs, vs = [], []
            for k in (1, 2, 3):
                sg = qbseas.get((pid, Y - k)); n = 0 if sg is None else len(sg)
                gs.append(n); vs.append(ppg(sg) if n else 0.0)
            if gs[0] >= 8:
                continue                                         # the lift only fires under 8 games
            row = {'g': gs, 'v': vs}
            has_hist = (gs[0] >= 4 and vs[0] > 0) or vs[1] > 0 or vs[2] > 0   # calcProj: den > 0
            if not has_hist or sb.get(Y - 1, 0) <= 0:
                continue
            curp = qbseas.get((pid, Y))
            if curp is None or len(curp) < MIN_NOW:
                continue
            base = ws.base(row, *ws.ENGINE)
            w = gs[0] / (gs[0] + K_LIFT)
            lifted = w * base + (1 - w) * sb[Y - 1]
            cut = sp.mt_mult(gs, vs)
            rows.append({'pid': pid, 'name': st['name'], 'season': Y, 'team': team, 'g_prev': gs[0],
                         'group': group_of(gs[0]), 'lifted': lifted, 'cut': cut,
                         'live': lifted * cut, 'cand': lifted,
                         'actual': ppg(curp), 'g_now': len(curp)})
    return pd.DataFrame(rows)

def rmse(e): return float(np.sqrt(np.mean(e ** 2)))
def mult(p, a): return float((p * a).sum() / (p * p).sum())

def grade(df, rng=None, shuffles=SHUFFLES):
    a = df['actual'].to_numpy(); el = df['live'].to_numpy() - a; ec = df['cand'].to_numpy() - a
    lift = 1 - rmse(ec) / rmse(el)
    rng = rng or np.random.default_rng(SEED); hits = rev = 0
    for _ in range(shuffles):                         # paired: swap each QB's two REAL forecasts
        sw = rng.random(len(a)) < 0.5
        b2 = np.where(sw, ec, el); c2 = np.where(sw, el, ec); x = 1 - rmse(c2) / rmse(b2)
        hits += x >= lift; rev += x <= lift
    p = (hits + 1) / (shuffles + 1); p_rev = (rev + 1) / (shuffles + 1)
    halves = [1 - rmse(ec[df['season'].isin(h)]) / rmse(el[df['season'].isin(h)]) for h in HALVES]
    grp = {k: (int((df['group'] == k).sum()), 1 - rmse(ec[(df['group'] == k).to_numpy()]) / rmse(el[(df['group'] == k).to_numpy()]))
           for k in sorted(df['group'].unique())}
    gates = {'1_size': lift >= 0.02, '2_fluke': p < 0.05, '3_halves': all(h > 0 for h in halves),
             '4_groups': all(l >= -0.01 for n, l in grp.values() if n >= GROUP_GATE_N)}
    return {'lift_removing_cut': lift, 'p': p, 'p_reverse': p_rev, 'halves': halves, 'groups': grp,
            'gates': gates, 'passed': all(gates.values()),
            'cut_confirmed': (-lift / (1 + lift)) >= 0.02 and p_rev < 0.05,   # reported only
            'rmse_live': rmse(el), 'rmse_cand': rmse(ec),
            'mae_live': float(np.mean(np.abs(el))), 'mae_cand': float(np.mean(np.abs(ec)))}

def require_locked_prereg():
    try:
        subprocess.run(['git', 'ls-files', '--error-unmatch', PREREG], cwd=ROOT, check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        sys.exit(f'[QB-MT] REFUSED: {PREREG} is not committed. Commit it first — that is the lock.')
    if subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', PREREG], cwd=ROOT).returncode != 0:
        sys.exit(f'[QB-MT] REFUSED: {PREREG} has uncommitted edits. Commit or discard them.')
    sha = subprocess.run(['git', 'log', '-1', '--format=%H %cI', '--', PREREG], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return {'prereg_commit': sha, 'prereg_sha256': hashlib.sha256((ROOT / PREREG).read_bytes()).hexdigest()[:16]}

def main():
    ap = argparse.ArgumentParser(); m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument('--count', action='store_true'); m.add_argument('--crash', action='store_true')
    m.add_argument('--run', action='store_true'); a = ap.parse_args()
    lock = require_locked_prereg() if a.run else None
    df = build(load())
    if not a.run:
        df['actual'] = np.nan                         # count and crash never keep a real outcome
    print(f'[QB-MT] graded QBs {len(df)} | by group {df["group"].value_counts().to_dict()}')
    print(f'[QB-MT] by half {[int(df["season"].isin(h).sum()) for h in HALVES]} | live cut sizes {df["cut"].round(3).value_counts().to_dict()}')
    print('[QB-MT] by season:', df['season'].value_counts().sort_index().to_dict())
    if a.count:
        print(df[df['season'] >= 2023][['season', 'name', 'team', 'g_prev', 'group']].to_string(index=False))
        return
    if a.crash:
        rng = np.random.default_rng(SEED); level = 0.97
        for sd in CRASH_SD:
            for label, truth in (('cut exactly right', 'cut'), ('cut 3/4 right', 'q'), ('cut half right', 'half'),
                                 ('cut pure double-count', 'none')):
                passes = []; lifts = []
                for _ in range(CRASH_SIMS):
                    t = {'cut': df['cut'], 'q': 1 - 0.75 * (1 - df['cut']), 'half': (1 + df['cut']) / 2, 'none': 1.0}[truth]
                    sim = df.copy(); sim['actual'] = sim['lifted'] * t * level * rng.lognormal(-sd * sd / 2, sd, len(df))   # noise averages exactly 1
                    r = grade(sim, rng, shuffles=200); passes.append(r['passed']); lifts.append(r['lift_removing_cut'])
                print(f'[CRASH] noise {sd:.2f} truth: {label:22s} removing the cut passes {np.mean(passes):5.1%}; '
                      f'median lift {np.median(lifts):+.1%}')
        print('[CRASH] synthetic outcomes only — says nothing about real quarterbacks.')
        return
    r = grade(df)
    fit = {k: mult(g['lifted'].to_numpy(), g['actual'].to_numpy()) for k, g in df.groupby('group')}
    out = {**lock, **r, 'n': int(len(df)),
           'reported_only': {'best_fit_multiplier_on_the_lift_by_group': fit,
                             'best_fit_all': mult(df['lifted'].to_numpy(), df['actual'].to_numpy())}}
    print(json.dumps(out, indent=2, default=float))
    (ROOT / 'data-cache').mkdir(exist_ok=True)
    (ROOT / 'data-cache' / 'qb-missedtime-result.json').write_text(json.dumps(out, indent=2, default=float))

if __name__ == '__main__':
    main()
