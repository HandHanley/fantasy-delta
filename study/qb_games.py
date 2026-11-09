"""
QB games under DELTA's Start Profile rule (delta-engine.js qbSpCounts, owner 21-22 Oct 2026), for the Own Value Scale
(docs/PREREG-ovs-available-ppg.md §8).

A QB week is a GAME when he took part (a pass, carry, target or catch, or any offensive snap) and either
  - the schedule names him as his team's starting QB (nflverse schedules home_qb_id / away_qb_id; an injury exit is
    still a start), or
  - he played 75%+ of the offensive snaps (nflverse snap counts, 2012 on), or
  - before 2012 (no snap counts): he threw the most passes for his team that week, 10 or more.
A week he took part in that is not a game is a CAMEO (mop-up, kneel-downs, a planned rest): its points and the week
itself are left out. Taking part is required, so a schedule that keeps naming a replaced starter (Mariota 2024) does
not hand him games he never played.

    qb_weeks(weekly_dir, sched_file, snaps_dir, players_file, week) -> (games, cameos), sets of (gsis_id, season, week)
"""
import glob, os
import pandas as pd

SNAP_SHARE, FIRST_SNAP_SEASON, MIN_ATT = 0.75, 2012, 10


def qb_weeks(weekly_dir, sched_file, snaps_dir, players_file, week, return_parts=False):
    W = pd.concat([pd.read_csv(f, low_memory=False, usecols=['player_id', 'season', 'week', 'season_type', 'team', 'position',
                                                             'attempts', 'carries', 'targets', 'receptions'])
                   for f in sorted(glob.glob(os.path.join(weekly_dir, 'stats_player_week_*.csv')))], ignore_index=True)
    W = W[(W.season_type == 'REG') & (W.week <= week) & (W.position == 'QB')].copy()
    W['g'] = W[['attempts', 'carries', 'targets', 'receptions']].fillna(0).sum(axis=1) > 0
    G = pd.read_csv(sched_file, low_memory=False); G = G[(G.game_type == 'REG') & (G.week <= week)]
    starts = set(zip(G.home_qb_id, G.season, G.week)) | set(zip(G.away_qb_id, G.season, G.week))
    pl = pd.read_csv(players_file, low_memory=False, usecols=['gsis_id', 'pfr_id']).dropna()
    pfr = dict(zip(pl.pfr_id, pl.gsis_id))
    snap, team_qb = {}, {}
    for f in sorted(glob.glob(os.path.join(snaps_dir, 'snap_counts_*.csv'))):
        s = pd.read_csv(f, low_memory=False, usecols=['season', 'game_type', 'week', 'pfr_player_id', 'position', 'team',
                                                      'offense_snaps', 'offense_pct'])
        s = s[(s.game_type == 'REG') & (s.week <= week) & (s.position == 'QB')]
        for p, y, w, t, n, pc in zip(s.pfr_player_id, s.season, s.week, s.team, s.offense_snaps, s.offense_pct):
            g = pfr.get(p)
            if g is None: continue
            key = (g, int(y), int(w)); snap[key] = (float(n or 0), float(pc or 0))
            team_qb.setdefault((int(y), int(w), t), []).append((g, float(pc or 0)))
    other95 = set()                     # engine rule: a listed start does not count when another QB on the team played 95%+
    for (y, w, t), lst in team_qb.items():
        for g, _ in lst:
            if any(g2 != g and pc2 >= 0.95 for g2, pc2 in lst): other95.add((g, y, w))
    W['att'] = W.attempts.fillna(0)
    top = W.groupby(['season', 'week', 'team']).att.transform('max')
    took = {(k, int(y), int(w)): (bool(g_), float(a), float(tp)) for k, y, w, g_, a, tp in zip(W.player_id, W.season, W.week, W.g, W.att, top)}
    for key, (n, pc) in snap.items():
        if n > 0 and key not in took: took[key] = (False, 0.0, 0.0)          # snaps but no stat: a one-snap rest week
    games, cameos, why = set(), set(), {'start': 0, 'snaps_75': 0, 'most_passes_pre2012': 0, 'listed_but_other_qb_95': 0}
    for key, (g_, att, tp) in took.items():
        n, pc = snap.get(key, (0.0, 0.0)); y = key[1]
        if not (g_ or n > 0): continue
        if key in starts and key not in other95: games.add(key); why['start'] += 1
        elif pc >= SNAP_SHARE: games.add(key); why['snaps_75'] += 1
        elif y < FIRST_SNAP_SEASON and att >= MIN_ATT and att == tp: games.add(key); why['most_passes_pre2012'] += 1
        else:
            cameos.add(key)
            if key in starts: why['listed_but_other_qb_95'] += 1
    if return_parts:
        return games, cameos, {'games': len(games), 'cameos': len(cameos), 'game_because': why,
                               'snap_rows_matched': len(snap)}
    return games, cameos
