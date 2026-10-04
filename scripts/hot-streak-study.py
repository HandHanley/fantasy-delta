#!/usr/bin/env python3
"""
DELTA Hot Streak Study — after an unexpected hot streak, does a player's dynasty price fall back further than
players priced the same?   scripts/hot-streak-study.py · pre-registration: docs/PREREG-hot-streak.md

    python3 scripts/hot-streak-study.py --count   # streaks, groups, snapshot dates; reads no price after a streak
    python3 scripts/hot-streak-study.py --crash   # real post-streak prices + synthetic later prices
    python3 scripts/hot-streak-study.py --run     # the study; refuses unless the pre-registration is committed

Hot game: a starter-level week — top 12 at QB/TE, top 24 at RB/WR that week (DELTA scoring: blend-study bt_pts).
Streak: three of HIS games in a row (byes and missed weeks skipped), all hot, third game in Weeks 3-14.
          First streak per player-season. Seasons 2021-2025.
Unexpected: in the last price snapshot before his first streak game, priced outside the SAME starter line
          (top 12 QB/TE, top 24 RB/WR) — a player priced as a bench player who played like a starter three weeks
          running. Must be priced (value > 0) in that snapshot.
Prices: DynastyProcess files/values.csv git history, value_2qb. L(v) = log(v + 100). Absent = 0.
          After snapshot: first commit dated after the third game's week ends, within 10 days.
          Before snapshot: last commit dated before his first streak game's week starts, within 10 days.
          H1 (season over): commit nearest 15 January after the season, within 14 days.
          H2 (next preseason): commit nearest 15 August after the season, within 14 days.
Measure: d = L(v_H) - L(v_after). Pool: every skill player priced in the same after snapshot, overall rank <= 400,
          with no streak of any kind that season. Gap = d minus the pool's line, fitted per after snapshot:
          d ~ L(v_after) + Rookie + Second-Year + Aging  (the price calendar, 4 Oct, showed rookies gain and aging
          veterans fall against players priced the same — without these, a rookie streaker looks like he 'held').
          Rookie / Second-Year: drafted that spring / the spring before (nflverse draft picks).
          Aging: RB 26+, WR 29+, QB 32+ on 1 September. Unknown draft year or age = none of the three.
          Ranges resample the streak players AND each snapshot's pool (refit).
IDs: nflverse gsis_id <-> DynastyProcess fantasypros_id via DynastyProcess's crosswalk. Never by name.
"""
import argparse, hashlib, importlib.util, io, subprocess, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
def _load(name, f):
    s = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
qm = _load('qm_hs', 'qb-missedtime-study.py'); bs = qm.bs

PREREG  = 'docs/PREREG-hot-streak.md'
CACHE   = ROOT / 'data-cache' / 'hot-streak'
DP_GIT  = 'https://github.com/dynastyprocess/data.git'
DP_DIR  = CACHE / 'dynastyprocess-data'
SEASONS = [2021, 2022, 2023, 2024, 2025]
HALVES  = ([2021, 2022, 2023], [2024, 2025])
SKILL   = ['QB', 'RB', 'WR', 'TE']
STREAK = 3
STARTER = {'QB': 12, 'RB': 24, 'WR': 24, 'TE': 12}     # hot-week line AND cheap line
LAST_WEEK, FIRST_END = 14, 3
CHEAP_RANK = STARTER
POOL_RANK = 400
LAG_EVENT, LAG_H = 10, 14
OFFSET, SIZE, CI, BOOT, SEED = 100.0, 0.03, 97.5, 4000, 20261005   # 3%: streak players are cheap, and L shrinks cheap moves most (crash test)
HORIZONS = {'H1': 'Season over (mid-Jan)', 'H2': 'Next preseason (mid-Aug)'}

def L(v): return np.log(np.asarray(v, float) + OFFSET)

# ── prices ─────────────────────────────────────────────────────────────────
def git(*a, binary=False):
    r = subprocess.run(['git', *a], cwd=DP_DIR, capture_output=True, check=True)
    return r.stdout if binary else r.stdout.decode()

def ensure_repo():
    CACHE.mkdir(parents=True, exist_ok=True)
    if not DP_DIR.exists():
        subprocess.run(['git', 'clone', '-q', '--filter=blob:none', '--no-checkout', DP_GIT, str(DP_DIR)], check=True)

def commits():
    c = [l.split() for l in git('log', '--format=%H %cs', '--', 'files/values.csv').splitlines() if l]
    return sorted((pd.Timestamp(d), h) for h, d in c)

_snap = {}
def snapshot(h):
    if h not in _snap:
        v = pd.read_csv(io.BytesIO(git('show', f'{h}:files/values.csv', binary=True)), dtype={'fp_id': str},
                        usecols=['fp_id', 'pos', 'value_2qb'])
        v = v[v['pos'].isin(SKILL)].drop_duplicates('fp_id', keep='last').copy()
        v['orank'] = v['value_2qb'].rank(ascending=False, method='first')
        v['prank'] = v.groupby('pos')['value_2qb'].rank(ascending=False, method='first')
        _snap[h] = v.set_index('fp_id')
    return _snap[h]

def crosswalk():
    ids = pd.read_csv(io.BytesIO(git('show', 'HEAD:files/db_playerids.csv', binary=True)), dtype=str,
                      usecols=['fantasypros_id', 'gsis_id']).dropna().drop_duplicates('gsis_id')
    return dict(zip(ids['gsis_id'], ids['fantasypros_id']))

def attributes():
    """fp_id -> (draft year, birthdate). Draft year from nflverse draft picks by gsis_id."""
    ids = pd.read_csv(io.BytesIO(git('show', 'HEAD:files/db_playerids.csv', binary=True)), dtype=str,
                      usecols=['fantasypros_id', 'gsis_id', 'birthdate', 'draft_year']).dropna(subset=['fantasypros_id'])
    ids = ids.drop_duplicates('fantasypros_id')
    dp = pd.read_parquet(bs.fetch(f'{bs.REL}/draft_picks/draft_picks.parquet', CACHE / 'draft_picks.parquet'),
                         columns=['season', 'gsis_id']).dropna(subset=['gsis_id'])
    dy = dict(zip(dp['gsis_id'].astype(str), dp['season'].astype(int)))
    def year(r):                                   # nflverse first; DynastyProcess's own (covers undrafted) second
        if r.gsis_id in dy: return dy[r.gsis_id]
        v = pd.to_numeric(r.draft_year, errors='coerce'); return int(v) if pd.notna(v) else None
    return {r.fantasypros_id: (year(r), pd.to_datetime(r.birthdate, errors='coerce')) for r in ids.itertuples()}

AGING = {'RB': 26, 'WR': 29, 'QB': 32}
def dummies(fps, poss, y, attr):
    out = np.zeros((len(fps), 3))
    for i, (f, p) in enumerate(zip(fps, poss)):
        d, b = attr.get(f, (None, pd.NaT))
        if d == y: out[i, 0] = 1
        elif d == y - 1: out[i, 1] = 1
        elif p in AGING and pd.notna(b) and (pd.Timestamp(y, 9, 1) - b).days / 365.25 >= AGING[p]: out[i, 2] = 1
    return out

def first_after(C, t, lag):
    for d, h in C:
        if d > t: return (h, d) if (d - t).days <= lag else None
    return None

def last_before(C, t, lag):
    best = None
    for d, h in C:
        if d < t: best = (h, d)
        else: break
    return best if best and (t - best[1]).days <= lag else None

def nearest(C, t, lag):
    d, h = min(C, key=lambda x: abs((x[0] - t).days))
    return (h, d) if abs((d - t).days) <= lag else None

# ── streaks ───────────────────────────────────────────────────────────────
def week_dates():
    g = pd.read_csv(bs.fetch('https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv',
                             bs.CACHE / 'games.csv'), usecols=['season', 'game_type', 'week', 'gameday'])
    g = g[g['game_type'] == 'REG']
    gd = g.groupby(['season', 'week'])['gameday'].agg(['min', 'max'])
    return {k: (pd.Timestamp(a), pd.Timestamp(b)) for k, (a, b) in gd.iterrows()}

def weekly():
    g = qm.load()
    g = g[g['season'].isin(SEASONS + [SEASONS[-1] + 1]) & g['position'].isin(SKILL)].copy()
    g['pts'] = 0.0
    for pos in SKILL:
        m = g['position'] == pos; g.loc[m, 'pts'] = bs.bt_pts(g[m], pos)
    g['wrank'] = g.groupby(['season', 'week', 'position'])['pts'].rank(ascending=False, method='min')
    g['hot'] = g['wrank'] <= g['position'].map(STARTER)
    return g

def find_streaks(g):
    """First streak per player-season: three of his games in a row, all hot, third game in Weeks 3-14."""
    out = []
    for (pid, y), sg in g[g['season'].isin(SEASONS)].sort_values('week').groupby(['pid', 'season']):
        h = sg['hot'].to_numpy(); w = sg['week'].to_numpy()
        for i in range(len(sg) - STREAK + 1):
            if h[i:i + STREAK].all() and FIRST_END <= w[i + STREAK - 1] <= LAST_WEEK:
                out.append(dict(pid=pid, name=sg['name'].iat[i], season=y, pos=sg['position'].iat[i],
                                w1=int(w[i]), w3=int(w[i + STREAK - 1]))); break
    return pd.DataFrame(out)

def events(g, C, wd, xw):
    S = find_streaks(g)
    streaked = {(r.season, r.pid) for r in S.itertuples()}
    rows, drop = [], {'no fp id': 0, 'no before snapshot': 0, 'unpriced before': 0, 'not cheap': 0, 'no after snapshot': 0}
    for r in S.itertuples():
        fp = xw.get(r.pid)
        if fp is None: drop['no fp id'] += 1; continue
        b = last_before(C, wd[(r.season, r.w1)][0], LAG_EVENT)
        if b is None: drop['no before snapshot'] += 1; continue
        sb = snapshot(b[0])
        if fp not in sb.index or sb.at[fp, 'value_2qb'] <= 0: drop['unpriced before'] += 1; continue
        pos = sb.at[fp, 'pos']
        if sb.at[fp, 'prank'] <= CHEAP_RANK[pos]: drop['not cheap'] += 1; continue
        a = first_after(C, wd[(r.season, r.w3)][1], LAG_EVENT)
        if a is None: drop['no after snapshot'] += 1; continue
        rows.append(dict(pid=r.pid, fp=fp, name=r.name, season=r.season, pos=pos, w1=r.w1, w3=r.w3,
                         before=b[0], before_d=b[1], after=a[0], after_d=a[1],
                         prank_before=int(sb.at[fp, 'prank']), v_before=float(sb.at[fp, 'value_2qb'])))
    return pd.DataFrame(rows), streaked, drop, len(S)

def horizon_commits(C):
    H = {}
    for y in SEASONS:
        H[(y, 'H1')] = nearest(C, pd.Timestamp(y + 1, 1, 15), LAG_H)
        H[(y, 'H2')] = nearest(C, pd.Timestamp(y + 1, 8, 15), LAG_H)
    return H

# ── measurement ───────────────────────────────────────────────────────────
def build_frames(E, streaked, xw, H, price_at, attr):
    """Per horizon: streak rows (x = L after, d) and, per after snapshot, the pool (x, d)."""
    fp2pid = {v: k for k, v in xw.items()}
    out = {}
    for hz in HORIZONS:
        ev, pools = [], {}
        for (snap_h, y), grp in E.groupby(['after', 'season']):
            hc = H[(y, hz)]
            if hc is None: continue
            sa = snapshot(snap_h)
            pool = sa[(sa['orank'] <= POOL_RANK) & (sa['value_2qb'] > 0)]
            pool = pool[[(y, fp2pid.get(f)) not in streaked for f in pool.index]]
            px = L(pool['value_2qb'].to_numpy())
            pd_ = L(price_at(hc[0], pool.index, pool['value_2qb'].to_numpy())) - px
            X = np.column_stack([np.ones(len(px)), px, dummies(pool.index, pool['pos'], y, attr)])
            pools[(snap_h, y)] = (X, pd_)
            for r in grp.itertuples():
                va = float(sa.at[r.fp, 'value_2qb']) if r.fp in sa.index else 0.0
                x = float(L(va)); d = float(L(price_at(hc[0], [r.fp], np.array([va]))[0]) - x)
                xe = np.concatenate([[1.0, x], dummies([r.fp], [r.pos], y, attr)[0]])
                ev.append(dict(pid=r.pid, season=y, pos=r.pos, key=(snap_h, y), x=x, d=d, xe=xe, name=r.name,
                               spike=x - float(L(r.v_before)), grp=('Rookie' if xe[2] else 'Second-Year' if xe[3]
                                                                    else 'Aging' if xe[4] else 'Other')))
        out[hz] = (pd.DataFrame(ev), pools)
    return out

def grade(frames, rng):
    res = {}
    for hz, (ev, pools) in frames.items():
        keys = list(pools); kix = {k: i for i, k in enumerate(keys)}; K = len(keys); D = 5
        beta0 = np.zeros((K, D)); beta = np.zeros((BOOT, K, D))
        ridge = 1e-6 * np.eye(D)                       # keeps a dummy with no pool members from breaking the solve
        for k, (X, y) in pools.items():
            i = kix[k]
            beta0[i] = np.linalg.solve(X.T @ X + ridge, X.T @ y)
            pk = rng.integers(0, len(y), size=(BOOT, len(y))); Xs, ys = X[pk], y[pk]
            XtX = np.einsum('bnd,bne->bde', Xs, Xs) + ridge; Xty = np.einsum('bnd,bn->bd', Xs, ys)
            beta[:, i] = np.linalg.solve(XtX, Xty[..., None])[..., 0]
        ev = ev[ev['key'].isin(kix)].copy()
        ev['k'] = ev['key'].map(kix)
        Xe = np.vstack(ev['xe'].to_numpy())
        ev['gap'] = ev['d'].to_numpy() - np.einsum('nd,nd->n', Xe, beta0[ev['k'].to_numpy()])
        pids = ev['pid'].unique(); pix = {p: i for i, p in enumerate(pids)}
        P = len(pids)
        Sd = np.zeros(P); N = np.zeros(P); SX = np.zeros((P, K, D))
        for r, xe in zip(ev.itertuples(), Xe):
            i = pix[r.pid]; Sd[i] += r.d; N[i] += 1; SX[i, r.k] += xe
        pk = rng.integers(0, P, size=(BOOT, P))
        totd, totN = Sd[pk].sum(1), N[pk].sum(1)
        totX = SX[pk].sum(1)                                            # (BOOT, K, D)
        boots = (totd - np.einsum('bkd,bkd->b', totX, beta)) / totN
        lo, hi = np.percentile(boots, [(100 - CI) / 2, 100 - (100 - CI) / 2])
        mean = ev['gap'].mean()
        halves = [ev[ev['season'].isin(h)]['gap'].mean() for h in HALVES]
        both = all(np.sign(h) == np.sign(mean) for h in halves)
        shown = abs(mean) >= SIZE and (lo > 0 or hi < 0) and both
        res[hz] = dict(n=len(ev), players=len(pids), gap=mean, lo=lo, hi=hi, halves=halves,
                       verdict='SHOWN' if shown else 'not shown', ev=ev)
    return res

def pct(x): return f'{100 * (np.exp(x) - 1):+.1f}%'

def show(res, label):
    print(f'[HOT] {label}')
    for hz, r in res.items():
        print(f"  {HORIZONS[hz]:<26} n {r['n']:>3} ({r['players']:>3} players)  gap {pct(r['gap']):>7}  "
              f"{CI}% range {pct(r['lo'])} to {pct(r['hi'])}  halves {pct(r['halves'][0])} / {pct(r['halves'][1])}  {r['verdict']}")

def require_locked_prereg():
    try:
        subprocess.run(['git', 'ls-files', '--error-unmatch', PREREG], cwd=ROOT, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        sys.exit(f'[HOT] REFUSED: {PREREG} is not committed. Commit it first — that is the lock.')
    if subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', PREREG], cwd=ROOT).returncode != 0:
        sys.exit(f'[HOT] REFUSED: {PREREG} has uncommitted edits. Commit or discard them.')
    sha = subprocess.run(['git', 'log', '-1', '--format=%H %cI', '--', PREREG], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip()
    if not sha: sys.exit(f'[HOT] REFUSED: {PREREG} has no commit history.')
    return sha, hashlib.sha256((ROOT / PREREG).read_bytes()).hexdigest()[:16]

# ── main ──────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument('--count', action='store_true'); m.add_argument('--crash', action='store_true')
    m.add_argument('--run', action='store_true')
    a = ap.parse_args()
    lock = require_locked_prereg() if a.run else None
    ensure_repo(); C = commits(); wd = week_dates(); xw = crosswalk(); attr = attributes()
    g = weekly()
    E, streaked, drop, n_all = events(g, C, wd, xw)
    H = horizon_commits(C)
    print(f'[HOT] streaks found, 2021-2025 (first per player-season): {n_all}  ·  dropped: {drop}')
    print(f'[HOT] unexpected streaks kept: {len(E)} from {E["pid"].nunique()} players')
    print('[HOT] by season:', E.groupby('season').size().to_dict(), '· by position:', E.groupby('pos').size().to_dict())
    mix = np.vstack([dummies([r.fp], [r.pos], r.season, attr)[0] for r in E.itertuples()])
    unk = sum(1 for f in E['fp'] if attr.get(f, (None, pd.NaT))[0] is None)
    print(f'[HOT] streak players who are Rookies {int(mix[:,0].sum())} · Second-Year {int(mix[:,1].sum())} · Aging {int(mix[:,2].sum())} · unknown draft year {unk}')
    print('[HOT] horizon snapshots:', {f'{y} {hz}': (str(v[1].date()) if v else None) for (y, hz), v in H.items()})
    lagb = (E.apply(lambda r: (wd[(r.season, r.w1)][0] - r.before_d).days, axis=1))
    laga = (E.apply(lambda r: (r.after_d - wd[(r.season, r.w3)][1]).days, axis=1))
    print(f'[HOT] days before first game: median {lagb.median():.0f}, max {lagb.max()}  ·  days after third game: median {laga.median():.0f}, max {laga.max()}')
    ex = E[E['season'] == 2024].sort_values('prank_before', ascending=False)
    print('  e.g. 2024:', '; '.join(f"{r.name} ({r.pos}{r.prank_before}, wks {r.w1}-{r.w3})" for r in ex.head(8).itertuples()))
    if a.count:
        return
    if a.crash:
        rng = np.random.default_rng(SEED)
        season_of = {v[0]: y for (y, hz), v in H.items() if v and hz == 'H1'}
        def maker(plant=None):
            def price_at(h, fps, v_after):
                v = np.asarray(v_after, float) * rng.lognormal(-0.3 ** 2 / 2, 0.3, len(v_after))   # mean exactly 1
                if plant is not None and plant[0] == 'rookies' and h in season_of:
                    y = season_of[h]
                    mask = np.array([attr.get(f, (None,))[0] == y for f in fps]); v[mask] *= plant[1]
                elif plant is not None and plant[0] != 'rookies' and h in plant[0]:
                    mask = np.array([f in plant[1] for f in fps]); v[mask] *= plant[2]
                return v
            return price_at
        streak_fps = set(E['fp'])
        h1s = {v[0] for (y, hz), v in H.items() if hz == 'H1' and v}; h2s = {v[0] for (y, hz), v in H.items() if hz == 'H2' and v}
        runs = [('noise 1 (expect nothing SHOWN)', None), ('noise 2 (expect nothing SHOWN)', None),
                ('noise 3 (expect nothing SHOWN)', None),
                ('planted: streakers -15% at the next preseason (expect H2 SHOWN only)', (h2s, streak_fps, 0.85)),
                ('planted: streakers -12% at season end (expect H1 SHOWN only)', (h1s, streak_fps, 0.88)),
                ('planted: EVERY rookie +25% at season end, pool too (expect nothing SHOWN — the line absorbs it)', ('rookies', 1.25))]
        for lab, plant in runs:
            res = grade(build_frames(E, streaked, xw, H, maker(plant), attr), np.random.default_rng(SEED))
            show(res, f'crash test — {lab}')
        return
    def price_at(h, fps, v_after):
        s = snapshot(h)
        return np.array([float(s.at[f, 'value_2qb']) if f in s.index else 0.0 for f in fps])
    res = grade(build_frames(E, streaked, xw, H, price_at, attr), np.random.default_rng(SEED))
    show(res, 'RESULT — streak players vs players priced the same right after the streak')
    print('[HOT] reported only:')
    ev = res['H2']['ev']
    print(f"  spike during the streak (raw, before -> after snapshot): median {pct(ev['spike'].median())}, mean {pct(ev['spike'].mean())}")
    for hz, r in res.items():
        e = r['ev']; print(f"  {HORIZONS[hz]} by position: " + ', '.join(f"{p} {pct(e[e.pos==p]['gap'].mean())} (n {int((e.pos==p).sum())})" for p in SKILL if (e.pos == p).any()))
        print(f"  {HORIZONS[hz]} by group:    " + ', '.join(f"{q} {pct(e[e.grp==q]['gap'].mean())} (n {int((e.grp==q).sum())})" for q in ['Rookie','Second-Year','Aging','Other'] if (e.grp == q).any()))
        print(f"  {HORIZONS[hz]} by season:   " + ', '.join(f"{y} {pct(e[e.season==y]['gap'].mean())}" for y in SEASONS if (e.season == y).any()))
    # production: did the points last?
    pts = g.set_index(['pid', 'season', 'week'])['pts']
    rows = []
    for r in E.itertuples():
        sg = g[(g.pid == r.pid) & (g.season == r.season)]
        bef = sg[sg.week < r.w1]['pts']; dur = sg[(sg.week >= r.w1) & (sg.week <= r.w3)]['pts']
        aft = sg[sg.week > r.w3]['pts']; nxt = g[(g.pid == r.pid) & (g.season == r.season + 1)]['pts']
        rows.append(dict(pos=r.pos, bef=bef.mean() if len(bef) else np.nan, dur=dur.mean(),
                         aft=aft.mean() if len(aft) >= 3 else np.nan, nxt=nxt.mean() if len(nxt) >= 6 else np.nan))
    Pr = pd.DataFrame(rows)
    print('  points per game (reported only) — before streak · during · rest of season (3+ games) · next season (6+ games):')
    for p in SKILL:
        q = Pr[Pr.pos == p]
        if len(q): print(f"    {p}: {q.bef.mean():.1f} · {q.dur.mean():.1f} · {q.aft.mean():.1f} (n {q.aft.notna().sum()}) · {q.nxt.mean():.1f} (n {q.nxt.notna().sum()})")
    big = res['H2']['ev'].sort_values('gap')
    print('  biggest give-backs by next preseason:', ', '.join(f"{r.name} {r.season} {pct(r.gap)}" for r in big.head(5).itertuples()))
    print('  biggest further gains:                ', ', '.join(f"{r.name} {r.season} {pct(r.gap)}" for r in big.tail(5).iloc[::-1].itertuples()))
    print(f'[HOT] lock: prereg commit {lock[0]} · sha256 {lock[1]} · seed {SEED}')

if __name__ == '__main__':
    main()
