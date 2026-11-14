#!/usr/bin/env python3
"""
DELTA — ROOKIE SNAP THRESHOLD (Steve, 13 Nov 2026). One source for both the history check
(study/ovs_rookie_snaps.py) and the weekly build (study/new_value_weekly.py), so they can never count differently.

Rule: a first-year player with fewer than THRESHOLD offensive snaps this regular season, through the value's week, keeps
his incoming-rookie (draft-slot) value, as if he had not played. From THRESHOLD on he is valued on what he has done.
Offensive snaps only: special-teams snaps never count (a returner stays on draft value).

Snaps: nflverse snap_counts_YYYY.csv (from 2012), keyed by PFR id, joined to GSIS ids through nflverse players.csv,
the same crosswalk qb_games.qb_weeks uses.
"""
import glob, os
import pandas as pd

THRESHOLD = 150          # fixed by Steve, 13 Nov 2026, before any result was seen


def offense_snaps(snaps_dir, players_file, week, seasons=None):
    """{(gsis_id, season): offensive snaps in regular-season weeks <= week}."""
    pl = pd.read_csv(players_file, low_memory=False, usecols=['gsis_id', 'pfr_id']).dropna()
    pfr = dict(zip(pl.pfr_id, pl.gsis_id))
    out = {}
    for f in sorted(glob.glob(os.path.join(snaps_dir, 'snap_counts_*.csv'))):
        y = int(os.path.basename(f)[12:16])
        if seasons is not None and y not in seasons: continue
        s = pd.read_csv(f, low_memory=False, usecols=['season', 'game_type', 'week', 'pfr_player_id', 'offense_snaps'])
        s = s[(s.game_type == 'REG') & (s.week <= week)]
        g = s.groupby(['pfr_player_id', 'season']).offense_snaps.sum()
        for (p, yy), v in g.items():
            k = pfr.get(p)
            if k is not None: out[(k, int(yy))] = out.get((k, int(yy)), 0.0) + float(v)
    return out


def under(snaps, key, season):
    """True if this player has fewer than THRESHOLD offensive snaps in `season` (no row = 0 snaps)."""
    return snaps.get((key, int(season)), 0.0) < THRESHOLD
