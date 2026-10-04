#!/usr/bin/env python3
"""
DELTA Rushing QB Study — is a quarterback's rushing production more reliable year to year than his passing?
scripts/qb-rushing-study.py · pre-registration: docs/PREREG-qb-rushing.md

    python3 scripts/qb-rushing-study.py --count   # pairs and groups from season-Y data only; reads no next season
    python3 scripts/qb-rushing-study.py --crash   # next season replaced by synthetic numbers (noise, then planted)
    python3 scripts/qb-rushing-study.py --run     # the study; refuses unless the pre-registration is committed

A start: his team's most pass attempts that game, 10+ (scripts/qb-perstart-study.py starts_table, imported unchanged).
Loader: scripts/qb-missedtime-study.py load() (1999-2025, any-production games), imported unchanged.
Scoring: blend-study bt_pts split in two —  passing = py*.04 + pt*4 - pi*2 ;  rushing = ry*.1 + rt*6.
Pair: a QB with 8+ starts in season Y AND 8+ starts in Y+1 (Y = 1999..2024), per-start averages each season.
  Q1  corr(rush_Y, rush_Y+1) - corr(pass_Y, pass_Y+1)  — REPORTED ONLY: the crash test showed equal relative
      wobble on both reads 'rushing stickier' (+0.27), because QBs differ far more in rushing than passing
  Q2  Runners (top third of rush share in Y, within season) minus Pocket (bottom third):
      average gap to the line  total_Y+1 ~ total_Y + age   (fitted on the MIDDLE third only)
  Q3  same groups: average SIZE of the miss to that line (negative = Runners more predictable)
Ranges: 4,000 resamples of QBs (a QB appears in many pairs), refitting the line each time. 99%.
"""
import argparse, hashlib, importlib.util, subprocess, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
def _load(name, f):
    s = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
ps = _load('ps_rq', 'qb-perstart-study.py'); qm = ps.qm; bs = ps.bs

PREREG  = 'docs/PREREG-qb-rushing.md'
YEARS   = list(range(1999, 2025))                 # Y; pairs run to 2025
HALVES  = (list(range(1999, 2012)), list(range(2012, 2025)))
MIN_STARTS = 8
CI, BOOT, SEED = 99, 4000, 20261004
SIZE = {'Q1': 0.10, 'Q2': 1.0, 'Q3': 0.5}         # correlation points; points per start; points per start

def pass_pts(d): return d['py'] * .04 + d['pt'] * 4 + d['pi'] * -2
def rush_pts(d): return d['ry'] * .1 + d['rt'] * 6

def season_table():
    g = qm.load()
    st = ps.starts_table(g)[['pid', 'name', 'season', 'team', 'week']]
    s = st.merge(g, on=['pid', 'season', 'team', 'week'], how='left', suffixes=('', '_g'))
    s['pas'] = pass_pts(s); s['rus'] = rush_pts(s)
    t = s.groupby(['pid', 'season']).agg(name=('name', 'last'), n=('week', 'size'),
                                         pas=('pas', 'mean'), rus=('rus', 'mean')).reset_index()
    t['tot'] = t['pas'] + t['rus']
    players = pd.read_parquet(bs.fetch(f'{bs.REL}/players/players.parquet', bs.CACHE / 'players.parquet'),
                              columns=['gsis_id', 'birth_date'])
    bd = dict(zip(players['gsis_id'].astype(str), pd.to_datetime(players['birth_date'], errors='coerce')))
    t['age'] = [(pd.Timestamp(y, 9, 1) - bd.get(p, pd.NaT)).days / 365.25 if pd.notna(bd.get(p, pd.NaT)) else np.nan
                for p, y in zip(t['pid'], t['season'])]
    return t

def pairs_from(t):
    """Season-Y rows of QBs with 8+ starts in Y; next-season columns attached ONLY for --run / --crash use."""
    now = t[(t['n'] >= MIN_STARTS) & t['season'].isin(YEARS)].copy()
    nxt = t[t['n'] >= MIN_STARTS][['pid', 'season', 'pas', 'rus', 'tot']].copy()
    nxt['season'] -= 1
    P = now.merge(nxt, on=['pid', 'season'], suffixes=('', '_1'))
    P = P[P['age'].notna() & (P['tot'] > 0)].copy()
    P['share'] = P['rus'] / P['tot']
    P['grp'] = 'Middle'
    for y, ix in P.groupby('season').groups.items():
        q = P.loc[ix, 'share'].rank(pct=True, method='first')
        P.loc[ix[q.to_numpy() > 2 / 3], 'grp'] = 'Runners'
        P.loc[ix[q.to_numpy() <= 1 / 3], 'grp'] = 'Pocket'
    return P.reset_index(drop=True)

def fit_line(df):
    """Line fitted on the MIDDLE third only, applied to everyone. Fitting it on all pairs let a Runners-only
    effect leak into the age terms (Runners skew young): a planted +2 a start read +0.4 (crash test, 4 Oct)."""
    X = np.column_stack([np.ones(len(df)), df['tot'], df['age']])
    mid = (df['grp'] == 'Middle').to_numpy()
    beta, *_ = np.linalg.lstsq(X[mid], df['tot_1'].to_numpy()[mid], rcond=None)
    return df['tot_1'].to_numpy() - X @ beta

def stats(df):
    r_r = np.corrcoef(df['rus'], df['rus_1'])[0, 1]; r_p = np.corrcoef(df['pas'], df['pas_1'])[0, 1]
    e = fit_line(df); R = (df['grp'] == 'Runners').to_numpy(); K = (df['grp'] == 'Pocket').to_numpy()
    return {'Q1': r_r - r_p, 'Q2': e[R].mean() - e[K].mean(), 'Q3': np.abs(e[R]).mean() - np.abs(e[K]).mean(),
            'r_rush': r_r, 'r_pass': r_p, 'lvl_R': e[R].mean(), 'lvl_K': e[K].mean(),
            'miss_R': np.abs(e[R]).mean(), 'miss_K': np.abs(e[K]).mean()}

def grade(P, rng):
    full = stats(P)
    pids = P['pid'].unique(); rows_of = P.groupby('pid').indices
    boots = {q: [] for q in ('Q1', 'Q2', 'Q3')}
    for _ in range(BOOT):
        pick = rng.choice(len(pids), size=len(pids), replace=True)
        idx = np.concatenate([rows_of[pids[i]] for i in pick])
        b = stats(P.iloc[idx])
        for q in boots: boots[q].append(b[q])
    halves = [stats(P[P['season'].isin(h)]) for h in HALVES]
    out = {}
    for q in ('Q1', 'Q2', 'Q3'):
        lo, hi = np.percentile(boots[q], [(100 - CI) / 2, 100 - (100 - CI) / 2])
        both = all(np.sign(h[q]) == np.sign(full[q]) for h in halves)
        shown = abs(full[q]) >= SIZE[q] and (lo > 0 or hi < 0) and both
        verdict = 'reported only' if q == 'Q1' else ('SHOWN' if shown else 'not shown')
        out[q] = dict(est=full[q], lo=lo, hi=hi, halves=[h[q] for h in halves], verdict=verdict)
    return full, out, halves

def show(full, out, halves, label):
    print(f'[RQB] {label}')
    print(f"  year-to-year correlation: rushing {full['r_rush']:.3f} · passing {full['r_pass']:.3f}")
    print(f"  gap to the line (pts/start): Runners {full['lvl_R']:+.2f} · Pocket {full['lvl_K']:+.2f}")
    print(f"  size of miss (pts/start):    Runners {full['miss_R']:.2f} · Pocket {full['miss_K']:.2f}")
    names = {'Q1': 'Q1 rushing minus passing correlation', 'Q2': 'Q2 Runners minus Pocket, points kept',
             'Q3': 'Q3 Runners minus Pocket, size of miss'}
    for q, r in out.items():
        print(f"  {names[q]:<40} {r['est']:+.3f}  {CI}% range {r['lo']:+.3f} to {r['hi']:+.3f}"
              f"  halves {r['halves'][0]:+.3f} / {r['halves'][1]:+.3f}  {r['verdict']}")

def require_locked_prereg():
    try:
        subprocess.run(['git', 'ls-files', '--error-unmatch', PREREG], cwd=ROOT, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        sys.exit(f'[RQB] REFUSED: {PREREG} is not committed. Commit it first — that is the lock.')
    if subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', PREREG], cwd=ROOT).returncode != 0:
        sys.exit(f'[RQB] REFUSED: {PREREG} has uncommitted edits. Commit or discard them.')
    sha = subprocess.run(['git', 'log', '-1', '--format=%H %cI', '--', PREREG], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip()
    if not sha: sys.exit(f'[RQB] REFUSED: {PREREG} has no commit history.')
    return sha, hashlib.sha256((ROOT / PREREG).read_bytes()).hexdigest()[:16]

def main():
    ap = argparse.ArgumentParser()
    m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument('--count', action='store_true'); m.add_argument('--crash', action='store_true')
    m.add_argument('--run', action='store_true')
    a = ap.parse_args()
    lock = require_locked_prereg() if a.run else None
    t = season_table()
    P = pairs_from(t)
    NEXT = ['pas_1', 'rus_1', 'tot_1']
    print(f'[RQB] QB-seasons with {MIN_STARTS}+ starts, {YEARS[0]}-{YEARS[-1] + 1}: {int((t["n"] >= MIN_STARTS).sum())}')
    print(f'[RQB] pairs (8+ starts in Y and Y+1, age known): {len(P)} from {P["pid"].nunique()} QBs · '
          f'halves {[int(P["season"].isin(h).sum()) for h in HALVES]}')
    print('[RQB] groups:', P['grp'].value_counts().to_dict())
    ex = P[P['season'] == 2024].sort_values('share', ascending=False)
    print('  e.g. 2024 Runners:', ', '.join(ex[ex.grp == 'Runners']['name'].head(6)))
    print('  e.g. 2024 Pocket: ', ', '.join(ex[ex.grp == 'Pocket']['name'].tail(6)))
    print(f"  rush share, season Y only — Runners median {P[P.grp=='Runners']['share'].median():.0%}, "
          f"Pocket median {P[P.grp=='Pocket']['share'].median():.0%}")
    if a.count:
        return
    if a.crash:
        rng = np.random.default_rng(SEED)
        def synth(plant=None, base='shuffle'):
            S = P.drop(columns=NEXT).copy()
            if base == 'shuffle':                                       # next season = ANOTHER QB's season-Y line
                for y, ix in S.groupby('season').groups.items():
                    perm = rng.permutation(ix)
                    S.loc[ix, 'pas_1'] = S.loc[perm, 'pas'].to_numpy(); S.loc[ix, 'rus_1'] = S.loc[perm, 'rus'].to_numpy()
                sd = 0.2
            else:                                                       # 'persist': his OWN season-Y line, plus noise
                S['pas_1'] = S['pas']; S['rus_1'] = S['rus']; sd = 0.25
            S['pas_1'] *= rng.lognormal(-sd * sd / 2, sd, len(S)); S['rus_1'] *= rng.lognormal(-sd * sd / 2, sd, len(S))
            if plant == 'rush sticks':
                S['rus_1'] = S['rus'] * rng.lognormal(-0.15 ** 2 / 2, 0.15, len(S))
            if plant in ('runners keep +2', 'runners keep +3'):
                S.loc[S.grp == 'Runners', 'rus_1'] += 2.0 if plant.endswith('+2') else 3.0
            if plant == 'runners steadier':
                base = S['pas'] + S['rus']
                noise = np.where(S.grp == 'Runners', 1.0, 3.0) * rng.standard_normal(len(S))
                S['pas_1'] = (base + noise) * (S['pas'] / base); S['rus_1'] = (base + noise) * (S['rus'] / base)
            S['tot_1'] = S['pas_1'] + S['rus_1']
            return S
        for lab, pl, bs_ in [('shuffle noise 1 (expect nothing SHOWN)', None, 'shuffle'),
                             ('shuffle noise 2 (expect nothing SHOWN)', None, 'shuffle'),
                             ('shuffle noise 3 (expect nothing SHOWN)', None, 'shuffle'),
                             ('persist noise 1 (expect Q2, Q3 not SHOWN)', None, 'persist'),
                             ('persist noise 2 (expect Q2, Q3 not SHOWN)', None, 'persist'),
                             ('planted: rushing repeats (Q1 reported; Q2 should rise)', 'rush sticks', 'shuffle'),
                             ('planted: Runners keep +2 a start (power check)', 'runners keep +2', 'persist'),
                             ('planted: Runners keep +3 a start (expect Q2 SHOWN)', 'runners keep +3', 'persist'),
                             ('planted: Runners steadier (expect Q3 SHOWN, negative)', 'runners steadier', 'shuffle')]:
            show(*grade(synth(pl, bs_), np.random.default_rng(SEED)), f'crash test — {lab}')
        return
    full, out, halves = grade(P, np.random.default_rng(SEED))
    show(full, out, halves, 'RESULT')
    print('[RQB] reported only:')
    sp = lambda a, b: pd.Series(a).rank().corr(pd.Series(b).rank())
    print(f"  rank correlation (Spearman): rushing {sp(P['rus'], P['rus_1']):.3f} · passing {sp(P['pas'], P['pas_1']):.3f}")
    for h, s in zip(HALVES, halves):
        print(f"  {h[0]}-{h[-1]}: corr rushing {s['r_rush']:.3f} · passing {s['r_pass']:.3f} · "
              f"Runners kept {s['lvl_R']:+.2f} vs Pocket {s['lvl_K']:+.2f} · miss {s['miss_R']:.2f} vs {s['miss_K']:.2f}")
    e = fit_line(P); P2 = P.assign(e=e)
    X = np.column_stack([np.ones(len(P)), P['tot']]); mid = (P['grp'] == 'Middle').to_numpy()
    b, *_ = np.linalg.lstsq(X[mid], P['tot_1'].to_numpy()[mid], rcond=None); e2 = P['tot_1'].to_numpy() - X @ b
    print(f"  without age in the line: Runners {e2[(P.grp=='Runners').to_numpy()].mean():+.2f} · Pocket {e2[(P.grp=='Pocket').to_numpy()].mean():+.2f}")
    print('  biggest Runners drops:', ', '.join(f"{r.name} {r.season} {r.e:+.1f}" for r in P2[P2.grp=='Runners'].nsmallest(5, 'e').itertuples()))
    print('  biggest Runners gains:', ', '.join(f"{r.name} {r.season} {r.e:+.1f}" for r in P2[P2.grp=='Runners'].nlargest(5, 'e').itertuples()))
    print(f'[RQB] lock: prereg commit {lock[0]} · sha256 {lock[1]} · seed {SEED}')

if __name__ == '__main__':
    main()
