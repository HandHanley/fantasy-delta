#!/usr/bin/env python3
"""
DELTA Future First Study — is one early first-round rookie pick worth two late firsts?
scripts/future-first-study.py · pre-registration: docs/PREREG-future-first.md

    python3 scripts/future-first-study.py --count   # classes, slots, name matches; reads no NFL production
    python3 scripts/future-first-study.py --crash   # real slots + synthetic outcomes (four shapes)
    python3 scripts/future-first-study.py --run     # the study; refuses unless the pre-registration is committed

SLOTS: Fantasy Football Calculator Dynasty Rookie ADP, 12-team (data/fixtures/ffc-rookie-adp-YYYY.json, fetched
  by scripts/fetch-ffc-rookie-adp.js; mock drafts, human picks only, 1QB, late summer). Classes 2014-2023.
  QB/RB/WR/TE rows only; each must match exactly one player of the same position drafted that year (nflverse
  draft picks; DynastyProcess's crosswalk for undrafted players), by normalised name plus the ALIAS table — the
  one place DELTA joins by name, because FFC carries no shared ID. Unmatched rows and non-rookies are dropped and
  the rest re-ranked by ADP: slot 1 = 1.01 ... 12 = 1.12, 13 = 2.01 ... 36 = 3.12.
OUTCOME: starter-level seasons in his first three seasons (class year, +1, +2): season TOTAL points (DELTA
  scoring, blend-study bt_pts) inside the top 12 at QB/TE or top 24 at RB/WR that season. Missed time counts.
TEST: D = mean(Early 1st, slots 1-4) - 2 x mean(Late 1st, slots 9-12), in starter seasons.
"""
import argparse, hashlib, importlib.util, io, json, re, subprocess, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
def _load(name, f):
    s = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
qm = _load('qm_ff', 'qb-missedtime-study.py'); bs = qm.bs

PREREG  = 'docs/PREREG-future-first.md'
FIX     = ROOT / 'data' / 'fixtures'
CACHE   = ROOT / 'data-cache' / 'future-first'
DP_GIT  = 'https://github.com/dynastyprocess/data.git'
DP_DIR  = CACHE / 'dynastyprocess-data'
CLASSES = list(range(2014, 2024))
HALVES  = (list(range(2014, 2019)), list(range(2019, 2024)))
SKILL   = ['QB', 'RB', 'WR', 'TE']
STARTER = {'QB': 12, 'RB': 24, 'WR': 24, 'TE': 12}
ELITE   = {'QB': 6, 'RB': 12, 'WR': 12, 'TE': 6}
TIERS   = {'Early 1st': range(1, 5), 'Mid 1st': range(5, 9), 'Late 1st': range(9, 13),
           '2nd': range(13, 25), '3rd': range(25, 37)}
ALIAS   = {'hollywoodbrown': 'marquisebrown', 'kennygainwell': 'kennethgainwell',
           'leonteecaroo': 'leontecarroo', 'josephwilliams': 'joewilliams', 'joshuapalmer': 'joshpalmer'}
POS_EXCEPT = {(2014, 'driarcher'): 'WR'}            # FFC lists him RB; nflverse's draft record lists WR
CI, BOOT, SEED, SIZE = 95, 4000, 20261006, 0.10      # SIZE: |D| >= 10% of the Early-1st mean

def norm(s):
    s = str(s).lower(); s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", s); s = re.sub(r"[^a-z]", "", s)
    return ALIAS.get(s, s)

# ── slots ─────────────────────────────────────────────────────────────────
def draft_tables():
    dp = pd.read_parquet(bs.fetch(f'{bs.REL}/draft_picks/draft_picks.parquet', CACHE / 'draft_picks.parquet'),
                         columns=['season', 'pfr_player_name', 'position', 'gsis_id', 'round', 'pick'])
    dp = dp[dp['position'].isin(SKILL)].dropna(subset=['gsis_id']).copy()
    dp['key'] = dp['pfr_player_name'].map(norm)
    ensure_repo()
    ids = pd.read_csv(io.BytesIO(git('show', 'HEAD:files/db_playerids.csv', binary=True)), dtype=str,
                      usecols=['name', 'position', 'draft_year', 'gsis_id', 'fantasypros_id'])
    und = ids[ids['position'].isin(SKILL) & ids['gsis_id'].notna()].copy()
    und['season'] = pd.to_numeric(und['draft_year'], errors='coerce'); und['key'] = und['name'].map(norm)
    und = und[~und['gsis_id'].isin(dp['gsis_id'])]           # undrafted only
    return dp, und, ids

def ffc_slots(dp, und):
    rows, dropped = [], []
    for y in CLASSES:
        R = json.load(open(FIX / f'ffc-rookie-adp-{y}.json'))['response']
        for p in sorted(R['players'], key=lambda p: p['adp']):
            if p['position'] not in SKILL: dropped.append((y, p['name'], 'not QB/RB/WR/TE')); continue
            k = norm(p['name']); want = POS_EXCEPT.get((y, k), p['position'])
            m = dp[(dp.season == y) & (dp.key == k) & (dp.position == want)]
            if len(m) == 0:
                m = und[(und.season == y) & (und.key == k) & (und.position == p['position'])]
            if len(m) != 1:
                other = dp[(dp.key == k) & (dp.position == p['position'])]
                why = (f'not a {y} rookie (drafted {int(other.season.iat[0])})' if len(other) == 1
                       else f'{len(m)} matches')
                dropped.append((y, p['name'], why)); continue
            rows.append(dict(cls=y, name=p['name'], pos=p['position'], gsis=m['gsis_id'].iat[0], adp=p['adp'],
                             drafted=p['times_drafted']))
    S = pd.DataFrame(rows)
    S['slot'] = S.groupby('cls')['adp'].rank(method='first').astype(int)
    S = S[S['slot'] <= 36].copy()
    S['tier'] = [next(t for t, rg in TIERS.items() if s in rg) for s in S['slot']]
    return S, dropped

# ── outcomes ──────────────────────────────────────────────────────────────
def season_ranks():
    g = qm.load()
    g = g[g['season'].between(2014, 2025) & g['position'].isin(SKILL)].copy()
    g['pts'] = 0.0
    for pos in SKILL:
        m = g['position'] == pos; g.loc[m, 'pts'] = bs.bt_pts(g[m], pos)
    t = g.groupby(['pid', 'season', 'position'])['pts'].sum().reset_index()
    t['rank'] = t.groupby(['season', 'position'])['pts'].rank(ascending=False, method='min')
    t = t.sort_values('pts', ascending=False).drop_duplicates(['pid', 'season'])   # one row per player-season
    return {(r.pid, r.season): (r.rank, r.position) for r in t.itertuples()}

def outcomes(S, ranks):
    O = S.copy(); st, el = [], []
    for r in O.itertuples():
        s = e = 0
        for yr in (r.cls, r.cls + 1, r.cls + 2):
            v = ranks.get((r.gsis, yr))
            if v is None: continue
            rank, pos = v
            s += rank <= STARTER[pos]; e += rank <= ELITE[pos]
        st.append(s); el.append(e)
    O['starter'] = st; O['elite'] = el
    return O

# ── test ──────────────────────────────────────────────────────────────────
def test(O, col, rng):
    E, L = O[O.tier == 'Early 1st'][col].to_numpy(float), O[O.tier == 'Late 1st'][col].to_numpy(float)
    D = E.mean() - 2 * L.mean()
    b = E[rng.integers(0, len(E), (BOOT, len(E)))].mean(1) - 2 * L[rng.integers(0, len(L), (BOOT, len(L)))].mean(1)
    lo, hi = np.percentile(b, [(100 - CI) / 2, 100 - (100 - CI) / 2])
    halves = [O[(O.tier == 'Early 1st') & O.cls.isin(h)][col].mean() - 2 * O[(O.tier == 'Late 1st') & O.cls.isin(h)][col].mean()
              for h in HALVES]
    shown = abs(D) >= SIZE * E.mean() and (lo > 0 or hi < 0) and all(np.sign(x) == np.sign(D) for x in halves)
    word = 'one Early 1st beat two Late 1sts' if D > 0 else 'two Late 1sts beat one Early 1st'
    return dict(D=D, lo=lo, hi=hi, halves=halves, early=E.mean(), late=L.mean(), nE=len(E), nL=len(L),
                verdict=f'SHOWN — {word}' if shown else 'not shown')

def show_test(t, label):
    print(f"[FF] {label}: Early 1st {t['early']:.2f} (n {t['nE']}) · Late 1st {t['late']:.2f} (n {t['nL']}) · "
          f"D = Early - 2 x Late = {t['D']:+.2f}  ({CI}% range {t['lo']:+.2f} to {t['hi']:+.2f})  "
          f"halves {t['halves'][0]:+.2f} / {t['halves'][1]:+.2f}  {t['verdict']}")

# ── DynastyProcess superflex comparison (reported only) ───────────────────
def git(*a, binary=False):
    r = subprocess.run(['git', *a], cwd=DP_DIR, capture_output=True, check=True)
    return r.stdout if binary else r.stdout.decode()

def ensure_repo():
    CACHE.mkdir(parents=True, exist_ok=True)
    if not DP_DIR.exists():
        subprocess.run(['git', 'clone', '-q', '--filter=blob:none', '--no-checkout', DP_GIT, str(DP_DIR)], check=True)

def dp_superflex_slots(ids, dpdraft):
    C = sorted((pd.Timestamp(d), h) for h, d in (l.split() for l in git('log', '--format=%H %cs', '--', 'files/values.csv').splitlines() if l))
    fp2g = dict(zip(ids['fantasypros_id'], ids['gsis_id']))
    dy = dict(zip(dpdraft['gsis_id'], dpdraft['season']))
    rows = []
    for y in [2020, 2021, 2022, 2023]:
        d, h = min(C, key=lambda x: abs((x[0] - pd.Timestamp(y, 5, 15)).days))
        v = pd.read_csv(io.BytesIO(git('show', f'{h}:files/values.csv', binary=True)), dtype={'fp_id': str},
                        usecols=['fp_id', 'player', 'pos', 'value_2qb', 'draft_year'])
        v = v[v['pos'].isin(SKILL)].drop_duplicates('fp_id').copy(); v['gsis'] = v['fp_id'].map(fp2g)
        v['dy'] = [dy.get(g, pd.to_numeric(x, errors='coerce')) for g, x in zip(v['gsis'], v['draft_year'])]
        v = v[(v['dy'] == y) & v['gsis'].notna()].sort_values('value_2qb', ascending=False).head(36)
        for i, r in enumerate(v.itertuples(), start=1):
            rows.append(dict(cls=y, name=r.player, pos=r.pos, gsis=r.gsis, slot=i,
                             tier=next(t for t, rg in TIERS.items() if i in rg)))
    return pd.DataFrame(rows)

def require_locked_prereg():
    try:
        subprocess.run(['git', 'ls-files', '--error-unmatch', PREREG], cwd=ROOT, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        sys.exit(f'[FF] REFUSED: {PREREG} is not committed. Commit it first — that is the lock.')
    if subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', PREREG], cwd=ROOT).returncode != 0:
        sys.exit(f'[FF] REFUSED: {PREREG} has uncommitted edits. Commit or discard them.')
    sha = subprocess.run(['git', 'log', '-1', '--format=%H %cI', '--', PREREG], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip()
    if not sha: sys.exit(f'[FF] REFUSED: {PREREG} has no commit history.')
    return sha, hashlib.sha256((ROOT / PREREG).read_bytes()).hexdigest()[:16]

def main():
    ap = argparse.ArgumentParser()
    m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument('--count', action='store_true'); m.add_argument('--crash', action='store_true')
    m.add_argument('--run', action='store_true')
    a = ap.parse_args()
    lock = require_locked_prereg() if a.run else None
    dp, und, ids = draft_tables()
    S, dropped = ffc_slots(dp, und)
    print(f'[FF] FFC slots kept: {len(S)} ({S.groupby("cls").size().to_dict()})')
    print(f'[FF] dropped before ranking ({len(dropped)}):')
    for y, n, why in dropped: print(f'    {y} {n}: {why}')
    print('[FF] firsts by position:', S[S.slot <= 12].groupby('pos').size().to_dict(),
          '· slots 1-36 by position:', S.groupby('pos').size().to_dict())
    print('[FF] times drafted, first-round picks: median', int(S[S.slot <= 12]['drafted'].median()),
          '· fewest', int(S[S.slot <= 12]['drafted'].min()))
    for y in CLASSES:
        f = S[(S.cls == y) & (S.slot <= 12)]
        print(f'  {y}: ' + ', '.join(f'{r.slot}. {r.name}' for r in f.itertuples()))
    if a.count:
        return
    if a.crash:
        rng = np.random.default_rng(SEED)
        def world(p_of_slot):
            O = S.copy(); O['starter'] = rng.binomial(3, [p_of_slot(s) for s in O['slot']]); return O
        def curve(ratio, top=0.6):
            k = np.log(ratio) / 8
            return lambda s: min(0.95, top * np.exp(-k * (s - 2.5)))
        for lab, f in [('slot does not matter (expect SHOWN: two Late beat one Early)', lambda s: 0.25),
                       ('Early exactly 2x Late (expect not shown)', curve(2.0)),
                       ('Early 3.5x Late (expect SHOWN: one Early beats two Late)', curve(3.5)),
                       ('Early 2.75x Late (power check)', curve(2.75))]:
            for rep in (1, 2, 3):
                show_test(test(world(f), 'starter', np.random.default_rng(SEED + rep)), f'crash {rep} — {lab}')
        return
    ranks = season_ranks()
    O = outcomes(S, ranks)
    show_test(test(O, 'starter', np.random.default_rng(SEED)), 'RESULT — starter-level seasons, years 1-3')
    print('[FF] reported only:')
    show_test(test(O, 'elite', np.random.default_rng(SEED)), '  elite seasons (top 6 QB/TE, top 12 RB/WR)')
    show_test(test(O[O.cls != 2016], 'starter', np.random.default_rng(SEED)), '  without the 2016 class')
    print('  by tier — mean starter seasons · at least one · mean elite seasons:')
    for t in TIERS:
        q = O[O.tier == t]
        print(f'    {t:<10} n {len(q):>3}  {q.starter.mean():.2f} · {(q.starter > 0).mean():.0%} · {q.elite.mean():.2f}')
    print('  by first-round slot — mean starter seasons · at least one (10 classes):')
    print('    ' + '  '.join(f'1.{s:02d} {O[O.slot == s].starter.mean():.1f}/{(O[O.slot == s].starter > 0).mean():.0%}' for s in range(1, 13)))
    print('  a future first (any slot 1-12) — mean starter seasons', f'{O[O.slot <= 12].starter.mean():.2f}',
          '· at least one', f'{(O[O.slot <= 12].starter > 0).mean():.0%}',
          '· by class', {y: round(O[(O.cls == y) & (O.slot <= 12)].starter.mean(), 2) for y in CLASSES})
    for pos in SKILL:
        q = O[(O.slot <= 12) & (O.pos == pos)]
        if len(q): print(f'    first-rounders, {pos}: n {len(q)} · mean starter seasons {q.starter.mean():.2f}')
    print('  DynastyProcess SUPERFLEX order (May), classes 2020-2023, same outcome:')
    X = outcomes(dp_superflex_slots(ids, dp), ranks)
    show_test(test(X, 'starter', np.random.default_rng(SEED)), '    superflex 2020-23')
    print(f'[FF] lock: prereg commit {lock[0]} · sha256 {lock[1]} · seed {SEED}')

if __name__ == '__main__':
    main()
