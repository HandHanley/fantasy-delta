#!/usr/bin/env python3
"""
DELTA Price Calendar Study — when in the dynasty year is each kind of player dearest?
scripts/price-calendar-study.py · pre-registration: docs/PREREG-price-calendar.md

    python3 scripts/price-calendar-study.py --count   # groups and snapshot dates; reads only the May (start) prices
    python3 scripts/price-calendar-study.py --crash   # May prices + synthetic later prices (noise, then a planted effect)
    python3 scripts/price-calendar-study.py --run     # the study; refuses unless the pre-registration is committed

Cycles: May 2021 -> April 2022 ... May 2025 -> April 2026 (five). Month m = 0 (May) .. 11 (April).
Snapshot for a month: the DynastyProcess `files/values.csv` commit dated nearest the 15th, within 14 days.
Price = value_2qb (superflex, DELTA's anchor). L(v) = log(v + 100). A player absent from a snapshot that
exists counts as price 0.
Cohort: QB/RB/WR/TE in the top 300 by value_2qb in the May snapshot. Groups fixed in May, in this order:
  Rookie (drafted that spring) · Second-Year (drafted the spring before) ·
  RB 26+ · WR 29+ · QB 32+ (age on 15 May; drafted two or more springs earlier).
Everyone else in the cohort with a known draft year and age is the comparison pool.
Measure: d_m = L(v_m) - L(v_May). Price-matched gap r_m = d_m minus the comparison pool's line
(d_m on L(v_May), fitted per cycle and month). Windows graded: Aug (3), Nov (6), Jan (8), Apr (11).
IDs: fantasypros_id -> gsis_id via DynastyProcess's own crosswalk; draft year from nflverse draft
picks by gsis_id (DynastyProcess's draft_year as fallback); birthdate from the crosswalk. Never by name.
"""
import argparse, hashlib, io, subprocess, sys, urllib.request
from pathlib import Path
import numpy as np
import pandas as pd

ROOT    = Path(__file__).resolve().parent.parent
CACHE   = ROOT / 'data-cache' / 'price-calendar'
PREREG  = 'docs/PREREG-price-calendar.md'
DP_GIT  = 'https://github.com/dynastyprocess/data.git'
DP_DIR  = CACHE / 'dynastyprocess-data'
REL     = 'https://github.com/nflverse/nflverse-data/releases/download'
CYCLES  = [2021, 2022, 2023, 2024, 2025]
MONTHS  = ['May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr']
WINDOWS = {3: 'Aug (Preseason)', 6: 'Nov (Midseason)', 8: 'Jan (Season Over)', 11: 'Apr (Pre-Draft)'}
GROUPS  = ['Rookie', 'Second-Year', 'RB 26+', 'WR 29+', 'QB 32+']
SKILL   = ['QB', 'RB', 'WR', 'TE']
TOP_N   = 300
MAX_LAG = 14          # days from the 15th
OFFSET  = 100.0
SIZE    = 0.05        # |gap| on the log scale (about 5%)
CI      = 99          # percent; 20 window tests
BOOT    = 4000
SEED    = 20261003

def L(v): return np.log(np.asarray(v, float) + OFFSET)

# ── data ──────────────────────────────────────────────────────────────────
def git(*a, binary=False):
    r = subprocess.run(['git', *a], cwd=DP_DIR, capture_output=True, check=True)
    return r.stdout if binary else r.stdout.decode()

def ensure_repo():
    CACHE.mkdir(parents=True, exist_ok=True)
    if not DP_DIR.exists():
        subprocess.run(['git', 'clone', '-q', '--filter=blob:none', '--no-checkout', DP_GIT, str(DP_DIR)], check=True)

def snapshot_plan():
    """{(cycle, m): (commit, commit_date, days_off)} — chosen from commit DATES only, no file read."""
    commits = [l.split() for l in git('log', '--format=%H %cs', '--', 'files/values.csv').splitlines() if l]
    plan = {}
    for Y in CYCLES:
        for m in range(12):
            y, mo = (Y, 5 + m) if m < 8 else (Y + 1, m - 7)
            t = pd.Timestamp(y, mo, 15)
            h, d = min(commits, key=lambda c: abs((pd.Timestamp(c[1]) - t).days))
            off = abs((pd.Timestamp(d) - t).days)
            if off <= MAX_LAG:
                plan[(Y, m)] = (h, d, off)
    return plan

def read_snapshot(h):
    v = pd.read_csv(io.BytesIO(git('show', f'{h}:files/values.csv', binary=True)), dtype={'fp_id': str},
                    usecols=['fp_id', 'pos', 'value_2qb', 'scrape_date', 'player', 'draft_year'])
    return v[v['pos'].isin(SKILL)].drop_duplicates('fp_id', keep='last')

def id_tables():
    ids = pd.read_csv(io.BytesIO(git('show', 'HEAD:files/db_playerids.csv', binary=True)), dtype=str,
                      usecols=['fantasypros_id', 'gsis_id', 'birthdate'])
    ids = ids.dropna(subset=['fantasypros_id']).drop_duplicates('fantasypros_id')
    p = CACHE / 'draft_picks.parquet'
    if not p.exists():
        urllib.request.urlretrieve(f'{REL}/draft_picks/draft_picks.parquet', p)
    dp = pd.read_parquet(p, columns=['season', 'gsis_id']).dropna(subset=['gsis_id'])
    return ids, dict(zip(dp['gsis_id'].astype(str), dp['season'].astype(int)))

def cohort(Y, may, ids, draft):
    """Top 300 in the May snapshot, with group labels. Uses ONLY the May (starting) prices."""
    c = may.copy()
    c['rank'] = c['value_2qb'].rank(ascending=False, method='first')
    c = c[c['rank'] <= TOP_N].merge(ids, left_on='fp_id', right_on='fantasypros_id', how='left')
    c['dy'] = c['gsis_id'].map(draft)
    c['dy'] = c['dy'].fillna(pd.to_numeric(c['draft_year'], errors='coerce'))
    c['age'] = (pd.Timestamp(Y, 5, 15) - pd.to_datetime(c['birthdate'], errors='coerce')).dt.days / 365.25
    vet = c['dy'] <= Y - 2
    def label(r):
        if pd.isna(r['dy']): return None
        if r['dy'] == Y: return 'Rookie'
        if r['dy'] == Y - 1: return 'Second-Year'
        if pd.isna(r['age']): return None
        if r['pos'] == 'RB' and r['age'] >= 26 and r['dy'] <= Y - 2: return 'RB 26+'
        if r['pos'] == 'WR' and r['age'] >= 29 and r['dy'] <= Y - 2: return 'WR 29+'
        if r['pos'] == 'QB' and r['age'] >= 32 and r['dy'] <= Y - 2: return 'QB 32+'
        return 'Pool'
    c['group'] = c.apply(label, axis=1)
    c = c[c['group'].notna()].copy()
    c['cycle'] = Y
    c['L0'] = L(c['value_2qb'])
    return c[['cycle', 'fp_id', 'player', 'pos', 'age', 'dy', 'group', 'L0']]

def paths(coh, plan, price_of):
    """d[(cycle, m)] = L(v_m) - L(v_May) per cohort row. price_of(cycle, m, fp_ids) -> values (0 if absent)."""
    out = coh.copy()
    for m in range(1, 12):
        col = np.full(len(out), np.nan)
        for Y in CYCLES:
            if (Y, m) not in plan: continue
            idx = (out['cycle'] == Y).to_numpy()
            col[idx] = L(price_of(Y, m, out.loc[idx, 'fp_id'])) - out.loc[idx, 'L0'].to_numpy()
        out[f'd{m}'] = col
    return out

def matched_gaps(P):
    """r_m = d_m minus the comparison pool's straight line (d_m on L0), fitted per cycle and month."""
    R = P.copy()
    for m in range(1, 12):
        R[f'r{m}'] = np.nan
        for Y in CYCLES:
            cy = R['cycle'] == Y
            pool = R[cy & (R['group'] == 'Pool')].dropna(subset=[f'd{m}'])
            if len(pool) < 20: continue
            b, a = np.polyfit(pool['L0'], pool[f'd{m}'], 1)
            R.loc[cy, f'r{m}'] = R.loc[cy, f'd{m}'] - (a + b * R.loc[cy, 'L0'])
    return R

def grade(R, rng):
    """Point estimate: full-sample pool line. Range: each resample redraws the comparison pool (per cycle,
    refitting its line) AND the group's players — the line's wobble moves every group member in that cycle
    together, so leaving it fixed made the ranges too narrow (caught by the crash test, 3 Oct 2026)."""
    rows = []
    for m, wname in WINDOWS.items():
        col, dcol = f'r{m}', f'd{m}'
        # bootstrap pool lines: A[b, k], B[b, k] for cycle k
        cyc_list = [Y for Y in CYCLES if R[(R['cycle'] == Y) & (R['group'] == 'Pool')][dcol].notna().sum() >= 20]
        A = np.zeros((BOOT, len(CYCLES))); Bm = np.zeros((BOOT, len(CYCLES)))
        for k, Y in enumerate(CYCLES):
            if Y not in cyc_list: continue
            pool = R[(R['cycle'] == Y) & (R['group'] == 'Pool')].dropna(subset=[dcol])
            x, y = pool['L0'].to_numpy(), pool[dcol].to_numpy()
            pk = rng.integers(0, len(x), size=(BOOT, len(x)))
            xs, ys = x[pk], y[pk]
            mx, my = xs.mean(1, keepdims=True), ys.mean(1, keepdims=True)
            b = ((xs - mx) * (ys - my)).sum(1) / ((xs - mx) ** 2).sum(1)
            Bm[:, k] = b; A[:, k] = my[:, 0] - b * mx[:, 0]
        for gname in GROUPS:
            g = R[(R['group'] == gname)].dropna(subset=[col])
            if g.empty:
                rows.append(dict(group=gname, window=wname, n=0)); continue
            mean = g[col].mean()
            pids = g['fp_id'].unique(); pix = {p: i for i, p in enumerate(pids)}
            P, K = len(pids), len(CYCLES)
            Sd = np.zeros(P); N = np.zeros((P, K)); Sx = np.zeros((P, K))
            for r in g.itertuples():
                i, k = pix[r.fp_id], CYCLES.index(r.cycle)
                Sd[i] += getattr(r, dcol); N[i, k] += 1; Sx[i, k] += r.L0
            pk = rng.integers(0, P, size=(BOOT, P))
            totd, totN, totSx = Sd[pk].sum(1), N[pk].sum(1), Sx[pk].sum(1)          # (BOOT,), (BOOT,K), (BOOT,K)
            boots = (totd - (A * totN + Bm * totSx).sum(1)) / totN.sum(1)
            lo, hi = np.percentile(boots, [(100 - CI) / 2, 100 - (100 - CI) / 2])
            cyc = g.groupby('cycle')[col].mean()
            same = int((np.sign(cyc) == np.sign(mean)).sum()); ncyc = len(cyc)
            need = max(4, ncyc - 1) if ncyc >= 4 else None
            shown = (abs(mean) >= SIZE) and (lo > 0 or hi < 0) and (need is not None and same >= need)
            rows.append(dict(group=gname, window=wname, n=len(g), players=g['fp_id'].nunique(),
                             gap=mean, lo=lo, hi=hi, cycles_same=f'{same}/{ncyc}',
                             verdict='SHOWN' if shown else 'not shown'))
    order = {g: i for i, g in enumerate(GROUPS)}
    T = pd.DataFrame(rows)
    return T.sort_values('group', key=lambda s: s.map(order), kind='stable').reset_index(drop=True)

def pct(x): return f'{100 * (np.exp(x) - 1):+.1f}%'

def show_grades(T):
    for _, r in T.iterrows():
        if r['n'] == 0:
            print(f"  {r['group']:<12} {r['window']:<18} no data"); continue
        print(f"  {r['group']:<12} {r['window']:<18} n {r['n']:>3} ({r['players']:>3} players)  gap {pct(r['gap']):>7}"
              f"  {CI}% range {pct(r['lo'])} to {pct(r['hi'])}  same sign {r['cycles_same']}  {r['verdict']}")

def require_locked_prereg():
    try:
        subprocess.run(['git', 'ls-files', '--error-unmatch', PREREG], cwd=ROOT, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        sys.exit(f'[CAL] REFUSED: {PREREG} is not committed. Commit it first — that is the lock.')
    if subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', PREREG], cwd=ROOT).returncode != 0:
        sys.exit(f'[CAL] REFUSED: {PREREG} has uncommitted edits. Commit or discard them.')
    sha = subprocess.run(['git', 'log', '-1', '--format=%H %cI', '--', PREREG], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip()
    if not sha:
        sys.exit(f'[CAL] REFUSED: {PREREG} has no commit history.')
    return sha, hashlib.sha256((ROOT / PREREG).read_bytes()).hexdigest()[:16]

# ── main ──────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--count', action='store_true')
    mode.add_argument('--crash', action='store_true')
    mode.add_argument('--run', action='store_true')
    a = ap.parse_args()
    lock = require_locked_prereg() if a.run else None
    ensure_repo()
    plan = snapshot_plan()
    ids, draft = id_tables()

    print('[CAL] snapshot plan (days from the 15th; -- = none within 14):')
    for Y in CYCLES:
        print(f'  {Y}-{(Y + 1) % 100:02d} ' + ' '.join(f'{MONTHS[m]}:{plan[(Y, m)][2] if (Y, m) in plan else "--"}'
                                                    for m in range(12)))
    missing_start = [Y for Y in CYCLES if (Y, 0) not in plan]
    if missing_start: sys.exit(f'[CAL] no May snapshot for {missing_start}')

    mays = {Y: read_snapshot(plan[(Y, 0)][0]) for Y in CYCLES}
    coh = pd.concat([cohort(Y, mays[Y], ids, draft) for Y in CYCLES], ignore_index=True)
    print('[CAL] cohort (top 300 in May; groups fixed then):')
    print(coh.pivot_table(index='group', columns='cycle', values='fp_id', aggfunc='count', fill_value=0).to_string())
    for gname in GROUPS:
        ex = coh[(coh['group'] == gname) & (coh['cycle'] == 2024)].nsmallest(4, 'L0')['player'].tolist()
        print(f'  e.g. 2024 {gname}: {", ".join(ex)}')

    if a.count:
        return

    if a.crash:
        rng = np.random.default_rng(SEED)
        L0 = {(r.cycle, r.fp_id): r.L0 for r in coh.itertuples()}
        grp = {(r.cycle, r.fp_id): r.group for r in coh.itertuples()}
        for label, plant in [('noise only, draw 1 (expect: nothing SHOWN)', None),
                             ('noise only, draw 2 (expect: nothing SHOWN)', None),
                             ('noise only, draw 3 (expect: nothing SHOWN)', None),
                             ('planted: Rookies +10% Aug-Nov (expect: Rookie Aug, Nov SHOWN)', ('Rookie', {3, 4, 5, 6}, 1.10)),
                             ('planted: RB 26+ -15% from Nov on (expect: RB 26+ Nov, Jan, Apr SHOWN)', ('RB 26+', set(range(6, 12)), 0.85))]:
            sd = 0.30
            def price_of(Y, m, fps, plant=plant):
                v0 = np.exp(np.array([L0[(Y, f)] for f in fps])) - OFFSET
                v = v0 * rng.lognormal(-sd * sd / 2, sd, len(v0))       # mean exactly 1 (lesson 11)
                if plant and m in plant[1]:
                    v = v * np.array([plant[2] if grp[(Y, f)] == plant[0] else 1.0 for f in fps])
                return np.maximum(v, 0)
            T = grade(matched_gaps(paths(coh, plan, price_of)), np.random.default_rng(SEED))
            print(f'[CAL] crash test — {label}:'); show_grades(T)
            excl = int(((T['lo'] > 0) | (T['hi'] < 0)).sum())
            print(f'  SHOWN count: {(T["verdict"] == "SHOWN").sum()} · ranges excluding zero, any size: {excl} of {len(T)}')
        return

    # ── the run ──
    snaps = {}
    def price_of(Y, m, fps):
        if (Y, m) not in snaps:
            s = read_snapshot(plan[(Y, m)][0]); snaps[(Y, m)] = dict(zip(s['fp_id'], s['value_2qb']))
        d = snaps[(Y, m)]
        return np.array([d.get(f, 0.0) for f in fps], float)
    P = paths(coh, plan, price_of)
    R = matched_gaps(P)
    T = grade(R, np.random.default_rng(SEED))
    print(f'[CAL] RESULT — price-matched gap vs players who started at the same May price ({CI}% ranges, {BOOT} resamples):')
    show_grades(T)
    print('[CAL] full calendar, price-matched gap by month (reported only):')
    print('  ' + f'{"":<12}' + ''.join(f'{MONTHS[m]:>8}' for m in range(1, 12)))
    for gname in GROUPS:
        G = R[R['group'] == gname]
        print('  ' + f'{gname:<12}' + ''.join(f'{pct(G[f"r{m}"].mean()):>8}' for m in range(1, 12)))
    print('[CAL] raw average price change from May — NOT price-matched (reported only; includes drift and drop-outs):')
    for gname in GROUPS + ['Pool']:
        G = P[P['group'] == gname]
        print('  ' + f'{gname:<12}' + ''.join(f'{pct(G[f"d{m}"].mean()):>8}' for m in range(1, 12)))
    print('[CAL] by cycle at each window (price-matched):')
    for gname in GROUPS:
        G = R[R['group'] == gname]
        print('  ' + f'{gname:<12}' + '  '.join(f'{WINDOWS[m].split()[0]}: ' + ' '.join(
            f'{pct(G[G.cycle == Y][f"r{m}"].mean()) if G[G.cycle == Y][f"r{m}"].notna().any() else "--"}'
            for Y in CYCLES) for m in WINDOWS))
    print(f'[CAL] lock: prereg commit {lock[0]} · sha256 {lock[1]} · seed {SEED} · cycles {CYCLES}')

if __name__ == '__main__':
    main()
