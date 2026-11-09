"""
Injury-neutral games (docs/DECISION-no-games-in-matching.md §5).

A week counts as OUT HURT when his club played that week, he recorded no pass, carry, target or catch, and either:
  - the weekly roster shows him on a reserve list (RES, PUP or RSN). How depends on the season's file format:
      week-by-week seasons (from 2016): his status that week;
      older seasons, whose weekly files carry one end-of-season status and drop players once they go on IR: every week
      after his last listing, when that last listing is a reserve status (Le'Veon Bell 2015: listed through week 8, RES);
    a season is "older" when more than 5% of its reserve listings fall in weeks he played (2002-2014 about 50%, 2016+ 0%);
  - or, from 2009, the official injury report listed him Out or Doubtful for that week.
Weeks cut, on the practice squad, a healthy scratch, suspended or off a roster are not out hurt.
Known gap: older files omit players who spent the whole season on IR (Jordy Nelson 2015), so those count as missed.

    injured_weeks(weekly_dir, wrost_dir, inj_dir, week) -> {(gsis_id, season): weeks out hurt through `week`}
"""
import glob, os
import numpy as np, pandas as pd

RESERVE = {'RES', 'PUP', 'RSN'}
REPORT_OUT = {'Out', 'Doubtful'}
OLD_FORMAT_PLAYED = 0.05
# roster and injury files use each club's code of the time; the stats files use today's franchise code
TO_STATS = {'ARZ': 'ARI', 'BLT': 'BAL', 'CLV': 'CLE', 'HST': 'HOU', 'OAK': 'LV', 'SD': 'LAC', 'SL': 'LA', 'STL': 'LA'}


def _read(pattern, cols):
    fs = sorted(glob.glob(pattern)); assert fs, pattern
    return pd.concat([pd.read_csv(f, usecols=cols, low_memory=False) for f in fs], ignore_index=True)


def injured_weeks(weekly_dir, wrost_dir, inj_dir, week, return_parts=False):
    W = _read(os.path.join(weekly_dir, 'stats_player_week_*.csv'),
              ['player_id', 'season', 'week', 'season_type', 'team', 'attempts', 'carries', 'targets', 'receptions'])
    W = W[(W.season_type == 'REG') & (W.week <= week)]
    W['g'] = W[['attempts', 'carries', 'targets', 'receptions']].fillna(0).sum(axis=1) > 0
    team_weeks = set(zip(W.season, W.team, W.week))                         # weeks each club played
    played = set(zip(W.player_id[W.g], W.season[W.g], W.week[W.g]))

    R = _read(os.path.join(wrost_dir, 'roster_weekly_*.csv'), ['season', 'week', 'team', 'gsis_id', 'status', 'game_type'])
    R['team'] = R.team.replace(TO_STATS)
    Aall = R[(R.game_type == 'REG') & (R.week <= week) & R.gsis_id.notna()]                  # every listing
    R = Aall[Aall.status.isin(RESERVE)]
    I = _read(os.path.join(inj_dir, 'injuries_*.csv'), ['season', 'game_type', 'team', 'week', 'gsis_id', 'report_status'])
    I['team'] = I.team.replace(TO_STATS)
    I = I[(I.game_type == 'REG') & (I.week <= week) & I.report_status.isin(REPORT_OUT) & I.gsis_id.notna()]

    def keep(df):
        return {(g, int(s), int(w)) for g, s, w, t in zip(df.gsis_id, df.season, df.week, df.team)
                if (s, t, w) in team_weeks and (g, s, w) not in played}
    # which seasons' weekly files are week-by-week
    pl_res = pd.Series([(g, s, w) in played for g, s, w in zip(R.gsis_id, R.season, R.week)], index=R.index)
    played_share = pl_res.groupby(R.season).mean().to_dict()
    old = {int(s) for s, v in played_share.items() if v > OLD_FORMAT_PLAYED}
    res = keep(R[~R.season.isin(old)])
    # older seasons: weeks after his last listing, when that listing is a reserve status
    A = Aall[Aall.season.isin(old)].sort_values('week').drop_duplicates(['season', 'gsis_id'], keep='last')
    A = A[A.status.isin(RESERVE)]
    weeks_by_club = {}
    for s_, t_, w_ in team_weeks: weeks_by_club.setdefault((s_, t_), []).append(w_)
    for g, s_, t_, lw in zip(A.gsis_id, A.season, A.team, A.week):
        for w_ in weeks_by_club.get((s_, t_), ()):
            if w_ > lw and (g, s_, w_) not in played: res.add((g, int(s_), int(w_)))
    rep = keep(I)
    both = res | rep
    out = {}
    for g, s, w in both:
        out[(g, s)] = out.get((g, s), 0) + 1
    if return_parts:
        return out, {'reserve_weeks': len(res), 'report_weeks': len(rep), 'report_only_weeks': len(rep - res), 'older_format_seasons': sorted(old),
                     'team_code_check': {'reserve_rows': int(len(R)), 'reserve_rows_on_a_club_week': int(sum((s, t, w) in team_weeks for s, t, w in zip(R.season, R.team, R.week)))}}
    return out


def neutral_games(S, inj, week):
    """games so far + weeks out hurt, never above the week number."""
    add = np.array([inj.get((k, int(t)), 0) for k, t in zip(S.key.values, S.t.values)], float)
    g = S.games.values.astype(float)
    return np.where(np.isnan(g), g, np.minimum(g + add, week)), add


# ── Available games (docs/PREREG-ovs-available-ppg.md) ───────────────────────────────────────────────────────────────
INJ_REPORT_ANY = {'Out', 'Doubtful', 'Questionable'}
ACTIVE = {'ACT', 'INA'}                    # week-by-week files: on the game-day roster


def available_weeks(weekly_dir, wrost_dir, inj_dir, week, return_parts=False, drop=frozenset(), add=frozenset()):
    """{(gsis_id, season): weeks available through `week`} = weeks he played, plus weeks he was on a club's game-day
    roster, his club played, and he did not play and was not hurt. Hurt = the injured_weeks rule, plus any injury-report
    listing (Out, Doubtful or Questionable) in a week he did not play. Weeks suspended, exempt, on bye or on no club are
    not available. Older-format seasons (weekly files list only active-roster weeks, one status per season): every
    listing counts as on the game-day roster."""
    W = _read(os.path.join(weekly_dir, 'stats_player_week_*.csv'),
              ['player_id', 'season', 'week', 'season_type', 'team', 'attempts', 'carries', 'targets', 'receptions'])
    W = W[(W.season_type == 'REG') & (W.week <= week)]
    W['g'] = W[['attempts', 'carries', 'targets', 'receptions']].fillna(0).sum(axis=1) > 0
    team_weeks = set(zip(W.season, W.team, W.week))
    played = set(zip(W.player_id[W.g], W.season[W.g], W.week[W.g]))
    R = _read(os.path.join(wrost_dir, 'roster_weekly_*.csv'), ['season', 'week', 'team', 'gsis_id', 'status', 'game_type'])
    R['team'] = R.team.replace(TO_STATS)
    R = R[(R.game_type == 'REG') & (R.week <= week) & R.gsis_id.notna()]
    res_pl = pd.Series([(g, s, w) in played for g, s, w in zip(R.gsis_id, R.season, R.week)], index=R.index)
    rr = R.status.isin(RESERVE)
    share = res_pl[rr].groupby(R.season[rr]).mean().to_dict()
    old = {int(s) for s, v in share.items() if v > OLD_FORMAT_PLAYED}
    I = _read(os.path.join(inj_dir, 'injuries_*.csv'), ['season', 'game_type', 'team', 'week', 'gsis_id', 'report_status'])
    I = I[(I.game_type == 'REG') & (I.week <= week) & I.report_status.isin(INJ_REPORT_ANY) & I.gsis_id.notna()]
    reported = set(zip(I.gsis_id, I.season.astype(int), I.week.astype(int)))
    on_roster = R[R.season.isin(old) | R.status.isin(ACTIVE)]
    avail = {(g, int(s), int(w)) for g, s, w in played}
    healthy_zero = 0
    for g, s, w, t in zip(on_roster.gsis_id, on_roster.season, on_roster.week, on_roster.team):
        key = (g, int(s), int(w))
        if key in avail or (s, t, w) not in team_weeks or key in reported: continue
        avail.add(key); healthy_zero += 1
    avail = (avail - set(drop)) | {k for k in add if k[2] <= week}        # QB cameos out, QB starts without a stat in
    out = {}
    for g, s, w in avail: out[(g, s)] = out.get((g, s), 0) + 1
    if return_parts:
        return out, {'played_weeks': len(played), 'healthy_zero_weeks': healthy_zero, 'older_format_seasons': sorted(old)}
    return out
