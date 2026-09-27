#!/usr/bin/env python3
"""
DELTA New-Team Calibration Check — scripts/teamchange-study.py
Pre-registration: docs/PREREG-team-change.md

    python3 scripts/teamchange-study.py --count   # eligibility only; computes NO outcomes
    python3 scripts/teamchange-study.py --run     # refuses unless the pre-registration is committed

A MEASUREMENT, not a ship test. The live engine's team adjustments (system, QB quality, play-caller)
cannot be rebuilt for past seasons, so no replacement for them can be tested. What can be measured:
how much players who changed teams in the offseason actually scored relative to the starting number,
compared with players who stayed — and whether that gap matches the engine's own (recorded before the
run from the live engine, 27 Sep 2026: changers x0.823 vs stayers x0.886, a gap of -7.1%).

Starting number: the engine's rule (scripts/weights-study.py, verified 315/315) x the missed-time
multipliers shipped 27 Sep (imported from scripts/startprofile-study.py). Teams: last season = the team
he played most games for; this season = the team in his first game. nflverse uses today's franchise
codes for every season, so relocations are not counted as changes.
"""
import argparse, importlib.util, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
def _load(n, f):
    s = importlib.util.spec_from_file_location(n, ROOT / 'scripts' / f); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
sp = _load('sp', 'startprofile-study.py'); ws = sp.ws; bs = ws.bs

PREREG = 'docs/PREREG-team-change.md'
ENGINE_GAP = 0.823 / 0.886 - 1          # live engine 27 Sep 2026, recorded before the run
SEED, BOOT = 20260927, 2000

def team_table():
    rows = []
    for y in bs.YEARS:
        w = pd.read_parquet(bs.fetch(f'{bs.REL}/stats_player/stats_player_week_{y}.parquet', bs.CACHE / f'w{y}.parquet'),
                            columns=['player_id', 'season', 'week', 'season_type', 'team'])
        rows.append(w[(w['season_type'] == 'REG') & w['team'].notna()])
    t = pd.concat(rows, ignore_index=True)
    t['pid'] = t['player_id'].astype(str)
    last = t.groupby(['pid', 'season'])['team'].agg(lambda s: s.mode().iat[0]).to_dict()            # most games
    first = t.sort_values('week').groupby(['pid', 'season'])['team'].first().to_dict()              # first game
    return last, first

def build(g):
    last, first = team_table()
    rows = ws.build_rows(g)
    out = []
    for r in rows.to_dict('records'):
        prev, now = last.get((r['pid'], r['season'] - 1)), first.get((r['pid'], r['season']))
        if prev is None or now is None: continue
        r['changed'] = prev != now
        r['p0'] = ws.base(r, *ws.ENGINE) * sp.mt_mult(r['g'], r['v'])
        out.append(r)
    return pd.DataFrame(out)

def mult(d): return float((d['p0'] * d['actual']).sum() / (d['p0'] ** 2).sum())

def main():
    ap = argparse.ArgumentParser(); m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument('--count', action='store_true'); m.add_argument('--run', action='store_true')
    a = ap.parse_args()
    lock = None
    if a.run: bs.PREREG = PREREG; lock = bs.require_locked_prereg()
    g, _ = bs.load_games()
    df = build(g)
    c = df.groupby(['season', 'changed']).size().unstack('changed').rename(columns={True: 'changed', False: 'stayed'})
    print('[TEAM] player-seasons by season:'); print(c.to_string())
    print(f"[TEAM] total {len(df)} · changed {int(df['changed'].sum())} · stayed {int((~df['changed']).sum())} · "
          f"changers by position {df[df['changed']]['pos'].value_counts().to_dict()}")
    if a.count: print('[TEAM] --count: no outcomes computed.'); return

    C, S = df[df['changed']], df[~df['changed']]
    gap = mult(C) / mult(S) - 1
    rng = np.random.default_rng(SEED); pids = df['pid'].unique(); by = {p: d for p, d in df.groupby('pid')}; boots = []
    for _ in range(BOOT):
        d = pd.concat([by[p] for p in rng.choice(pids, len(pids), replace=True)], ignore_index=True)
        cc, ss = d[d['changed']], d[~d['changed']]
        if len(cc) and len(ss): boots.append(mult(cc) / mult(ss) - 1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    verdict = ('ABOUT RIGHT — the engine\'s gap is inside the historical range' if lo <= ENGINE_GAP <= hi else
               'ENGINE TOO SOFT — history is harsher on team-changers than the engine' if hi < ENGINE_GAP else
               'ENGINE TOO HARSH — history is gentler on team-changers than the engine')
    per_pos = {}
    for ps in bs.SKILL:
        cp, spp = C[C['pos'] == ps], S[S['pos'] == ps]
        if len(cp) >= 30 and len(spp): per_pos[ps] = {'n_changed': int(len(cp)), 'gap': mult(cp) / mult(spp) - 1}
    out = {'lock': lock, 'n_changed': int(len(C)), 'n_stayed': int(len(S)),
           'multiplier_changed': mult(C), 'multiplier_stayed': mult(S),
           'historical_gap': gap, 'range_95': [float(lo), float(hi)], 'engine_gap_recorded': ENGINE_GAP,
           'VERDICT': verdict, 'by_position_reported_only_(30+_changers)': per_pos,
           'by_season_reported_only': {int(s): mult(d[d['changed']]) / mult(d[~d['changed']]) - 1
                                       for s, d in df.groupby('season') if d['changed'].any()}}
    print(json.dumps(out, indent=2, default=float))
    (ROOT / 'data-cache' / 'teamchange-result.json').write_text(json.dumps(out, indent=2, default=float))

if __name__ == '__main__':
    main()
