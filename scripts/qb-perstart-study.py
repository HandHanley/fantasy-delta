#!/usr/bin/env python3
"""
DELTA QB Points-Per-Start Projection — scripts/qb-perstart-study.py
Pre-registration: docs/PREREG-qb-perstart.md (read it first; this script implements it).

    python3 scripts/qb-perstart-study.py --count   # eligibility counts only. Computes NO errors.
    python3 scripts/qb-perstart-study.py --crash   # outcomes replaced by synthetic numbers BEFORE anything
                                                   # is computed. Never reads a real outcome.
    python3 scripts/qb-perstart-study.py --run     # the study. Refuses unless the pre-registration is
                                                   # committed to git and unmodified.

Definition (owner, 2 Oct 2026): a QB's projection is his points per game WHEN HE STARTS. Starts only;
no backup cut; no missed-time cut. The question is the few-starts modifier — what a thin record should
be blended toward:
  baseline  = (n x own + 6 x sb) / (n + 6)          today's starter lift, translated to starts
  candidate = (n x own + K x a.sb) / (n + K)        K and a fitted on 2002-2014, graded on 2015-2025
n = starts in the three prior seasons; own = his points per start over them (3/2/1 season weights);
sb = median points per start of QBs with 14+ starts the season before.

Loader and scoring imported UNCHANGED from scripts/qb-missedtime-study.py (any-production played games,
starter found by attempts not position label) and scripts/blend-study.py (bt_pts, half PPR).
"""
import argparse, hashlib, importlib.util, json, subprocess, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
def _load(name, f):
    s = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
qm = _load('qm_ps', 'qb-missedtime-study.py'); bs = qm.bs

PREREG     = 'docs/PREREG-qb-perstart.md'
SEASONS    = list(range(2002, 2026))   # every season graded once, forecast from the OTHER seasons
HALVES     = (list(range(2002, 2014)), list(range(2014, 2026)))
START_MIN_ATT = 10                     # a start: his team's most pass attempts that game, 10+
MIN_NOW    = 4                         # graded: 4+ starts in the season
SB_MIN     = 14                        # anchor: median points per start of QBs with 14+ starts last season
THIN_MAX   = 16                        # thin history: 16 or fewer starts across the three prior seasons
K_BASE, A_BASE = 6, 1.00               # today's lift, translated (calcProj K = 6, anchor = the median)
K_GRID     = np.arange(1, 31)
A_GRID     = np.round(np.arange(0.70, 1.1001, 0.01), 2)
W          = (3, 2, 1)                 # the engine's season weights
SHUFFLES, SEED = 2000, 20261003
CRASH_SIMS, CRASH_SD = 200, (0.20, 0.30)

def starts_table(g):
    g = g.copy()
    g['pts'] = bs.bt_pts(g, 'QB')
    lead = g.loc[g.groupby(['season', 'team', 'week'])['att'].idxmax()]
    return lead[lead['att'] >= START_MIN_ATT][['pid', 'name', 'season', 'team', 'week', 'pts']]

def build(g):
    st = starts_table(g)
    ps = st.groupby(['pid', 'season'])['pts'].agg(['size', 'mean'])
    ps.columns = ['n', 'ppst']; ps = ps.reset_index()
    sb = {y: float(ps[(ps.season == y) & (ps.n >= SB_MIN)]['ppst'].median())
          for y in range(min(qm.LOAD), max(qm.LOAD) + 1) if ((ps.season == y) & (ps.n >= SB_MIN)).sum() >= 8}
    S = {(r.pid, r.season): (int(r.n), float(r.ppst)) for r in ps.itertuples()}
    seen = set(map(tuple, g[['pid', 'season']].drop_duplicates().itertuples(index=False)))
    names = st.groupby('pid')['name'].last().to_dict()
    gp = g.assign(pts=bs.bt_pts(g, 'QB')).groupby(['pid', 'season'])['pts'].agg(['size', 'mean'])
    GP = {k: (int(v['size']), float(v['mean'])) for k, v in gp.iterrows()}   # per-appearance games and PPG
    rows = []
    for (pid, Y), (n_now, actual) in S.items():
        if Y not in SEASONS:
            continue
        if n_now < MIN_NOW or (Y - 1) not in sb:
            continue
        if not any((pid, Y - k) in seen for k in (1, 2, 3)):
            continue                                        # rookies: the engine's rookie path, untouched
        num = den = 0.0; n = 0
        for k, w in zip((1, 2, 3), W):
            s_k, p_k = S.get((pid, Y - k), (0, 0.0))
            num += w * s_k * p_k; den += w * s_k; n += s_k
        own = num / den if den > 0 else np.nan
        gs = [GP.get((pid, Y - k), (0, 0.0))[0] for k in (1, 2, 3)]; vs = [GP.get((pid, Y - k), (0, 0.0))[1] for k in (1, 2, 3)]
        # REPORTED ONLY: today's per-appearance starting number x missed-time cut (no QB lift, no backup
        # flags — neither can be rebuilt for past seasons). Context for the definition change, never gated.
        engine_now = qm.ws.base({'g': gs, 'v': vs}, *qm.ws.ENGINE) * qm.sp.mt_mult(gs, vs)
        rows.append({'engine_now': engine_now, 'pid': pid, 'name': names.get(pid, pid), 'season': Y, 'n_prior': n, 'own': own,
                     'sb': sb[Y - 1], 'actual': actual, 'starts_now': n_now,
                     'group': 'thin' if n <= THIN_MAX else 'established'})
    return pd.DataFrame(rows)

def forecast(df, K, a):
    n = df['n_prior'].to_numpy(float); own = np.nan_to_num(df['own'].to_numpy(float)); anc = a * df['sb'].to_numpy(float)
    return (n * own + K * anc) / (n + K)

def season_sums(df):
    """Per season and K: the three sums that give the squared error for any anchor a exactly —
    SSE(K, a) = S0 + 2a.S1 + a^2.S2 with c1 = n.own/(n+K), c2 = K.sb/(n+K), r = c1 - actual."""
    seasons = sorted(df['season'].unique()); out = np.zeros((len(seasons), len(K_GRID), 3))
    for i, y in enumerate(seasons):
        d = df[df['season'] == y]
        n = d['n_prior'].to_numpy(float); own = np.nan_to_num(d['own'].to_numpy(float))
        sbv = d['sb'].to_numpy(float); act = d['actual'].to_numpy(float)
        for j, K in enumerate(K_GRID):
            c1 = n * own / (n + K); c2 = K * sbv / (n + K); r = c1 - act
            out[i, j] = ((r * r).sum(), (r * c2).sum(), (c2 * c2).sum())
    return seasons, out

def best(sums):
    """Grid minimum over K and a from summed S0/S1/S2 (identical to brute force on the grid)."""
    sse = sums[:, 0][:, None] + 2 * A_GRID[None, :] * sums[:, 1][:, None] + (A_GRID ** 2)[None, :] * sums[:, 2][:, None]
    i, j = np.unravel_index(np.argmin(sse), sse.shape)
    return int(K_GRID[i]), float(A_GRID[j])

def fit(df, seasons=None):
    d = df if seasons is None else df[df['season'].isin(seasons)]
    _, s = season_sums(d); return best(s.sum(axis=0))

def rmse(e): return float(np.sqrt(np.mean(e ** 2)))

def loso(df):
    """Every season forecast with K and a fitted on the OTHER seasons only."""
    seasons, sums = season_sums(df); tot = sums.sum(axis=0); t = df.copy(); t['cand'] = np.nan; ka = {}
    for i, y in enumerate(seasons):
        K, a = best(tot - sums[i]); ka[int(y)] = (K, a); m = t['season'] == y
        t.loc[m, 'cand'] = forecast(t[m], K, a)
    t['base'] = forecast(t, K_BASE, A_BASE)
    return t, ka

def grade(t, rng=None, shuffles=SHUFFLES):
    def lift_of(m):
        x = t[m]; return 1 - rmse(x['cand'] - x['actual']) / rmse(x['base'] - x['actual'])
    thin = (t['group'] == 'thin').to_numpy(); est = ~thin
    th = t[thin]; a_ = th['actual'].to_numpy(); eb = th['base'].to_numpy() - a_; ec = th['cand'].to_numpy() - a_
    lift = 1 - rmse(ec) / rmse(eb)
    rng = rng or np.random.default_rng(SEED); hits = 0
    for _ in range(shuffles):                          # paired: swap each QB-season's two real forecasts
        sw = rng.random(len(a_)) < 0.5
        b2 = np.where(sw, ec, eb); c2 = np.where(sw, eb, ec); hits += (1 - rmse(c2) / rmse(b2)) >= lift
    p = (hits + 1) / (shuffles + 1)
    halves = [lift_of(thin & t['season'].isin(h).to_numpy()) for h in HALVES]
    est_lift = lift_of(est)
    gates = {'1_size': lift >= 0.02, '2_fluke': p < 0.05, '3_halves': all(h > 0 for h in halves),
             '4_established': est_lift >= -0.01}
    return {'lift_thin': lift, 'p': p, 'halves': halves, 'lift_established': est_lift,
            'n_thin': int(thin.sum()), 'n_established': int(est.sum()), 'gates': gates, 'passed': all(gates.values()),
            'rmse_thin_base': rmse(eb), 'rmse_thin_cand': rmse(ec),
            'mae_thin_base': float(np.mean(np.abs(eb))), 'mae_thin_cand': float(np.mean(np.abs(ec)))}

def require_locked_prereg():
    try:
        subprocess.run(['git', 'ls-files', '--error-unmatch', PREREG], cwd=ROOT, check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        sys.exit(f'[QB-PS] REFUSED: {PREREG} is not committed. Commit it first — that is the lock.')
    if subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', PREREG], cwd=ROOT).returncode != 0:
        sys.exit(f'[QB-PS] REFUSED: {PREREG} has uncommitted edits. Commit or discard them.')
    sha = subprocess.run(['git', 'log', '-1', '--format=%H %cI', '--', PREREG], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return {'prereg_commit': sha, 'prereg_sha256': hashlib.sha256((ROOT / PREREG).read_bytes()).hexdigest()[:16]}

def main():
    ap = argparse.ArgumentParser(); m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument('--count', action='store_true'); m.add_argument('--crash', action='store_true')
    m.add_argument('--run', action='store_true'); a = ap.parse_args()
    lock = require_locked_prereg() if a.run else None
    df = build(qm.load())
    if not a.run:
        df['actual'] = np.nan                         # count and crash never keep a real outcome
    print(f'[QB-PS] graded 2002-2025: {len(df)} QB-seasons | thin {int((df.group=="thin").sum())} | '
          f'established {int((df.group=="established").sum())} | no prior starts {int((df.n_prior==0).sum())}')
    t = df[df.group == 'thin']
    print(f'[QB-PS] thin by half: {[int(t.season.isin(h).sum()) for h in HALVES]}')
    print(f'[QB-PS] anchor sb by season: { {y: round(v, 2) for y, v in sorted(df.groupby("season").sb.first().items())} }')
    if a.count:
        return
    if a.crash:
        rng = np.random.default_rng(SEED)
        for sd in CRASH_SD:
            for label, K0, a0 in (('anchor = median (baseline right)', 6, 1.00), ('anchor 8% lower', 6, 0.92),
                                  ('anchor 15% lower', 6, 0.85), ('trust builds slower (K 15)', 15, 1.00)):
                passes = []; fits = []
                for _ in range(CRASH_SIMS):
                    sim = df.copy()
                    sim['actual'] = forecast(sim, K0, a0) * rng.lognormal(-sd * sd / 2, sd, len(sim))
                    t, _ = loso(sim); r = grade(t, rng, shuffles=200)
                    passes.append(r['passed']); fits.append(fit(sim))
                f = np.array(fits)
                print(f'[CRASH] noise {sd:.2f} truth: {label:34s} passes {np.mean(passes):5.1%} | '
                      f'fitted K median {np.median(f[:,0]):.0f}, a median {np.median(f[:,1]):.2f}')
        print('[CRASH] synthetic outcomes only — says nothing about real quarterbacks.')
        return
    t, ka = loso(df); r = grade(t); K_all, a_all = fit(df)
    th = t[t.group == 'thin']; own_only = np.where(th.n_prior > 0, th.own, th.sb)
    rep = {'thin_no_modifier_rmse': rmse(own_only - th['actual'].to_numpy()),
           'today_engine_approx_rmse': {'thin': rmse(th['engine_now'] - th['actual']), 'all': rmse(t['engine_now'] - t['actual'])},
           'baseline_rmse_all': rmse(t['base'] - t['actual']), 'candidate_rmse_all': rmse(t['cand'] - t['actual']),
           'no_prior_starts_n': int((th.n_prior == 0).sum()),
           'K_a_by_left_out_season': ka}
    out = {**lock, **r, 'ship_K': K_all, 'ship_a': a_all, 'reported_only': rep}
    print(json.dumps(out, indent=2, default=float))
    (ROOT / 'data-cache').mkdir(exist_ok=True)
    (ROOT / 'data-cache' / 'qb-perstart-result.json').write_text(json.dumps(out, indent=2, default=float))

if __name__ == '__main__':
    main()
