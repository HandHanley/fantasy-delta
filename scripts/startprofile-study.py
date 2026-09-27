#!/usr/bin/env python3
"""
DELTA Start Profile In The Preseason Projection — scripts/startprofile-study.py
Pre-registration: docs/PREREG-startprofile-preseason.md

    python3 scripts/startprofile-study.py --count   # eligibility only; computes NO errors
    python3 scripts/startprofile-study.py --run     # refuses unless the pre-registration is committed

Two live levers in calcProj read the Start Profile (last 34 played games; 20+ needed) and have never
been tested in the preseason projection:
  PENALTY (RULE 4)  d = -9/-6/-3/-1% at Miss% > 65/55/45/40, eased +3/+1% at Elite% > 30/20 (never
                    above 0); the projection takes half:  x (1 + 0.5 d)
  CEILING (FIX 2)   Miss% > 65: projection capped at 0.92 x posCeil; Miss% > 55: 1.05 x posCeil,
                    posCeil = QB 22.0, TE 11.5, RB/WR 12.5
SCOPE, fixed before any outcome was seen: the CEILING cannot be tested here — on the study's core
projection it changes 0 of 2,134 player-seasons (a player missing the line 55%+ of the time already
projects below the cap; it only bites when the engine's non-reconstructable multipliers push a
projection up) and on the live site it holds back 1 player (Christian Watson). It stays as it is.
The study therefore tests the PENALTY alone: today (on) vs off. The ceiling code below is kept only
so 'today' is reproduced exactly; it is inert on this data. Built on the engine's starting rule
(scripts/weights-study.py, verified 315/315) x the missed-time multipliers shipped 27 Sep
(delta-engine.js 27c). The Start Profile maths is scripts/blend-study.py's (verified 305/305 against the
engine's own profiles), at half PPR + TE premium. The live engine applies the penalty inside a capped
sum of adjustments; here it is a plain multiplier (disclosed).
"""
import argparse, importlib.util, json, math, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
def _load(n, f):
    s = importlib.util.spec_from_file_location(n, ROOT / 'scripts' / f); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
ws = _load('ws', 'weights-study.py'); bs = ws.bs

PREREG = 'docs/PREREG-startprofile-preseason.md'
TRAIN, HELDOUT = ws.TRAIN, ws.HELDOUT
MT = {'sat': 0.721, 'sat2': 0.672, 'g1to3': 0.690, 'g4to7': 0.797}      # delta-engine.js 27c
POS_CEIL = {'QB': 22.0, 'TE': 11.5, 'RB': 12.5, 'WR': 12.5}
VERSIONS = ['both', 'ceiling']          # today (penalty + inert ceiling) vs penalty off
CURRENT, CANDIDATE = 'both', 'ceiling'
MIN_POS_N, SEED, SHUFFLES = 30, 20260927, 2000

def mt_mult(g, v):
    if g[0] == 0: return MT['sat'] if v[1] > 0 else MT['sat2']
    if 1 <= g[0] <= 3: return MT['g1to3']
    if 4 <= g[0] <= 7: return MT['g4to7']
    return 1.0

def profile(hist, pos):
    """Miss% and Elite% over the last 34 played games, as computeStartProfile (JS Math.round)."""
    games = hist[-34:]; n = len(games)
    if n < 20: return None
    hit, elite = bs.LINES[f'{pos}|half_tep']
    return {'n': n, 'miss': math.floor(100 * (games < hit).sum() / n + 0.5), 'elite': math.floor(100 * (games >= elite).sum() / n + 0.5)}

def build(g):
    rows = ws.build_rows(g)
    sp = {}
    for pid, pg in g.groupby('pid', sort=False):
        pg = pg.sort_values(['season', 'week'])
        sp[pid] = pg
    out = []
    for r in rows.to_dict('records'):
        pg = sp[r['pid']]; hist = pg[pg['season'] < r['season']]
        prof = profile(bs.sp_pts(hist, r['pos']), r['pos']) if len(hist) else None
        if prof is None: continue                          # the levers cannot touch this player
        p0 = ws.base(r, *ws.ENGINE) * mt_mult(r['g'], r['v'])
        d = bs.d_volatility(bs.sp_pts(hist, r['pos']), r['pos'])
        r.update({'p0': p0, 'd': d, 'miss': prof['miss'], 'elite': prof['elite']})
        out.append(r)
    return pd.DataFrame(out)

def predict(df, version):
    p = df['p0'].to_numpy().copy()
    if version in ('both', 'penalty'): p = p * (1 + 0.5 * df['d'].to_numpy())
    if version in ('both', 'ceiling'):
        ceil = df['pos'].map(POS_CEIL).to_numpy(); miss = df['miss'].to_numpy()
        p = np.where(miss > 65, np.minimum(p, 0.92 * ceil), np.where(miss > 55, np.minimum(p, 1.05 * ceil), p))
    return p

def rmse(e): return float(np.sqrt(np.mean(e ** 2)))

def main():
    ap = argparse.ArgumentParser(); m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument('--count', action='store_true'); m.add_argument('--run', action='store_true')
    a = ap.parse_args()
    lock = None
    if a.run: bs.PREREG = PREREG; lock = bs.require_locked_prereg()
    g, _ = bs.load_games()
    df = build(g)
    print('[SP] graded player-seasons (20+ games in the Start Profile) by season:', df.groupby('season').size().to_dict())
    h = df[df['season'].isin(HELDOUT)]
    act = lambda d: {'penalty_active': int((d['d'] < 0).sum()), 'ceiling_zone(miss>55)': int((d['miss'] > 55).sum())}
    print(f"[SP] training {int(df['season'].isin(TRAIN).sum())} · held out {len(h)} ({h['pid'].nunique()} players) · "
          f"by position {h['pos'].value_counts().to_dict()} · held-out lever activity {act(h)}")
    if a.count: print('[SP] --count: no errors computed.'); return

    tr, te = df[df['season'].isin(TRAIN)], df[df['season'].isin(HELDOUT)]
    cv = {v: float(np.mean([rmse(predict(tr[tr['season'] == s], v) - tr[tr['season'] == s]['actual'].to_numpy()) for s in TRAIN])) for v in VERSIONS}
    cand = CANDIDATE                      # fixed in advance: penalty off
    print('[SP] training error (reported only):', {('today' if k == 'both' else 'penalty off'): round(v, 4) for k, v in cv.items()})
    y = te['actual'].to_numpy()
    eA, eB = predict(te, CURRENT) - y, predict(te, cand) - y
    lift = 1 - rmse(eB) / rmse(eA)
    rng = np.random.default_rng(SEED)
    uniq, inv = np.unique(te['pid'].to_numpy(), return_inverse=True); ge = 0
    for _ in range(SHUFFLES):
        f = (rng.random(len(uniq)) < 0.5)[inv]
        if 1 - rmse(np.where(f, eA, eB)) / rmse(np.where(f, eB, eA)) >= lift: ge += 1
    p = (ge + 1) / (SHUFFLES + 1)
    s_arr, p_arr = te['season'].to_numpy(), te['pos'].to_numpy()
    sub = lambda mk: 1 - rmse(eB[mk]) / rmse(eA[mk]) if mk.any() else None
    per_season = {int(s): sub(s_arr == s) for s in HELDOUT}
    per_pos = {ps: sub(p_arr == ps) for ps in bs.SKILL}; pos_n = {ps: int((p_arr == ps).sum()) for ps in bs.SKILL}
    gates = {'size_>=2%': lift >= 0.02, 'p<0.05': p < 0.05,
             'every_heldout_season': all(v is not None and v > 0 for v in per_season.values()),
             'no_position_worse_than_-1%_(n>=30)': all(v >= -0.01 for k, v in per_pos.items() if v is not None and pos_n[k] >= MIN_POS_N)}
    out = {'lock': lock, 'candidate': cand, 'training_error': cv,
           'heldout': {'n': int(len(te)), 'current_rmse': rmse(eA), 'candidate_rmse': rmse(eB), 'lift': lift, 'p': p},
           'reported_only_all_versions_heldout_rmse': {v: rmse(predict(te, v) - y) for v in VERSIONS},
           'per_season': per_season, 'per_position': per_pos, 'position_n': pos_n, 'gates': gates, 'SHIP': all(gates.values())}
    print(json.dumps(out, indent=2, default=float))
    (ROOT / 'data-cache' / 'startprofile-result.json').write_text(json.dumps(out, indent=2, default=float))

if __name__ == '__main__':
    main()
