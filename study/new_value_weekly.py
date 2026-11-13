#!/usr/bin/env python3
"""
DELTA — NEW VALUE, WEEKLY BUILD. Writes data/new-value.json. Display build, not a test: it applies only adopted rules.

What it is (each rule has its write-up in docs/):
  - In-season Own Value Scale: the 30 most similar past players at the same week, what they produced over the next
    three seasons above the starter line (PREREG-ovs-in-season, -era, -available-ppg incl. §7 and §8).
  - Production per available game; no games number in matching (DECISION-no-games-in-matching).
  - Full PPR, no TE premium, 12-team superflex; measured starter lines QB24/RB34/WR48/TE14 (DECISION-replacement-lines).
  - Contract Security, a deal ending this season counted as a contract year (PREREG-contract-security).
  - A first-year player with no game yet takes his incoming-rookie value (draft slot and age): §7's rule, for every
    position. A veteran with no game yet is valued from his earlier seasons, as the in-season value already does.
  - The 2026 player list comes from the season roster file as well as the game stats, so players who haven't recorded
    a stat (an injured rookie, a QB who hasn't played) are valued too.

    python new_value_weekly.py --data DIR [--week N] [--season 2026] [--out ../data/new-value.json]

DIR holds: nflv/{players,draft_picks,player_stats_season,stats_player_reg_2025}.csv, rosters/roster_YYYY.csv,
weekly/stats_player_week_YYYY.csv, wrost/roster_weekly_YYYY.csv, inj/injuries_YYYY.csv, snaps/snap_counts_YYYY.csv,
sched/games.csv (the layout the GitHub workflow downloads).
"""
import argparse, datetime as dt, json, os, sys, types
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import comps_value_study as C
import comps_draft_drop as DD
import own_value_scale as V
import ovs_in_season as I
import comps_in_season as CI
import ovs_available_ppg as AP
import ovs_qb_starts as QS
import contract_layer as CL
import ovs_small_samples as SSm                                    # imported before any patch (it keeps the original)

POS = ('QB', 'RB', 'WR', 'TE')


def last_complete_week(sched, season):
    g = pd.read_csv(sched, low_memory=False)
    g = g[(g.season == season) & (g.game_type == 'REG')]
    done = g.groupby('week').apply(lambda x: bool(x.result.notna().all()) if 'result' in x else bool(x.home_score.notna().all()))
    weeks = [int(w) for w, ok in done.items() if ok]
    return max(weeks) if weeks else None


def patch_loads(D, season):
    """Full PPR everywhere; add the season's players from game stats and from the season roster file."""
    _orig = C.load

    def load_season(nflverse, rosters):
        st, dp, pl = _orig(nflverse, rosters)
        st['P'] = st.fantasy_points_ppr.fillna(0).where(st.season < season, 0.0)
        wk = pd.read_csv(os.path.join(D, 'weekly', f'stats_player_week_{season}.csv'), low_memory=False)
        wk = wk[wk.season_type == 'REG']
        rs = pd.read_csv(os.path.join(D, 'rosters', f'roster_{season}.csv'), low_memory=False,
                         usecols=['gsis_id', 'position', 'full_name']).rename(columns={'gsis_id': 'player_id', 'position': 'rpos'})
        rs = rs.dropna(subset=['player_id']).drop_duplicates('player_id')
        agg = wk.groupby('player_id').agg(player_display_name=('player_display_name', 'last'), position=('position', 'last')).reset_index()
        agg = agg.merge(rs[['player_id', 'rpos']], on='player_id', how='left')
        agg['position'] = agg.rpos.where(agg.rpos.isin(POS), agg.position)
        extra = rs[~rs.player_id.isin(agg.player_id) & rs.rpos.isin(POS)]
        extra = pd.DataFrame({'player_id': extra.player_id, 'player_display_name': extra.full_name, 'position': extra.rpos})
        allp = pd.concat([agg[['player_id', 'player_display_name', 'position']], extra], ignore_index=True)
        allp.loc[allp.position == 'FB', 'position'] = 'RB'
        allp = allp[allp.position.isin(POS)]
        add = pd.DataFrame({'player_id': allp.player_id, 'player_display_name': allp.player_display_name, 'season': season,
                            'position': allp.position, 'games': 0.0, 'P': 0.0})
        st = st[st.season != season]
        return pd.concat([st, add.reindex(columns=st.columns)], ignore_index=True), dp, pl

    C.load = load_season
    _ci = CI.load

    def ci_load(*a, **k):
        st, dp, pl, W = _ci(*a, **k)
        W['P'] = np.where(W.g == 1, W.fantasy_points_ppr.fillna(0), 0.0)
        return st, dp, pl, W

    CI.load = ci_load


CAP = {}
_orig_prod = AP.prod_available


def _capture(Sin, W, week, L_full, L_upto, st, A_full, A_upto, rookie_qb_sits=False):
    """prod_available, plus the number of games this season's production rests on (its own denominator)."""
    out = SSm._capturing_prod(Sin, W, week, L_full, L_upto, st, A_full, A_upto, rookie_qb_sits=rookie_qb_sits)
    CAP['n'] = SSm.CAP['n']
    return out


def add_unplayed_rookies(D, Sb, Sin, season, played_ever):
    """R0 rows (draft slot and age, as comps_in_season.snapshots builds them) for players on the season roster who have
    never played an NFL game and so have no snapshot: this year's rookies, earlier draftees still waiting, and
    undrafted players (valued at the undrafted slot). Only for this build; no study frame changes."""
    rs = pd.read_csv(os.path.join(D, 'rosters', f'roster_{season}.csv'), low_memory=False, usecols=['gsis_id', 'position', 'full_name'])
    rs = rs.dropna(subset=['gsis_id']).drop_duplicates('gsis_id')
    rs = rs[rs.position.isin(POS) & ~rs.gsis_id.isin(set(Sin.key.values[Sin.t.values == season])) & ~rs.gsis_id.isin(played_ever)]
    dp = pd.read_csv(os.path.join(D, 'nflv', 'draft_picks.csv'), low_memory=False)
    dq = dp[dp.gsis_id.notna() & (dp.season <= season)].sort_values(['season', 'pick']).drop_duplicates('gsis_id').set_index('gsis_id')
    pl = pd.read_csv(os.path.join(D, 'nflv', 'players.csv'), low_memory=False).set_index('gsis_id')
    rows = []
    for k, ps, nm in zip(rs.gsis_id, rs.position, rs.full_name):
        if k in dq.index:
            pick, dy, dage = int(dq.pick[k]), int(dq.season[k]), dq.age[k]
        elif k in pl.index and pd.notna(pl.draft_pick.get(k)) and pd.notna(pl.draft_year.get(k)) and pl.draft_year[k] <= season:
            pick, dy, dage = int(pl.draft_pick[k]), int(pl.draft_year[k]), np.nan
        else:
            pick, dy, dage = C.UNDRAFTED_PICK, (int(pl.rookie_season[k]) if k in pl.index and pd.notna(pl.rookie_season.get(k)) else season), np.nan
        undrafted = pick >= C.UNDRAFTED_PICK
        b = pl.birth_date.get(k) if k in pl.index else None
        if isinstance(b, str): age = C.age_on(b, season)
        elif pd.notna(dage): age = float(dage) + (season - dy)
        else: continue
        rows.append(dict(key=k, name=nm, t=season, pos=ps, age=age, cy=season - dy + 1, pick=pick,
                         draft=np.log(min(pick, C.UNDRAFTED_PICK)), undrafted=undrafted, n_start=0, any_start=0,
                         complete=False, FV=np.nan, rookie_Y=True, kind='R0', prod=np.nan, games=np.nan, G=np.nan))
    Sb2 = pd.concat([Sb, pd.DataFrame(rows).reindex(columns=Sb.columns)], ignore_index=True)
    return Sb2, np.arange(len(Sb), len(Sb2))


# Common first-name forms, both ways. The site names players as Sleeper does ("Matt Hibner", "Drew Ogletree",
# "Scotty Miller") and nflverse often has the full form ("Matthew", "Andrew", "Scott"), so the site found no New Value
# for them (13 Nov 2026: 3 of the site's 843 rostered skill players). Each player also gets these spellings as keys,
# unless one would equal another player's own key.
NICKNAMES = [('matthew', 'matt'), ('andrew', 'drew'), ('andrew', 'andy'), ('scott', 'scotty'), ('michael', 'mike'),
             ('christopher', 'chris'), ('joshua', 'josh'), ('nicholas', 'nick'), ('william', 'will'), ('robert', 'rob'),
             ('robert', 'bobby'), ('daniel', 'danny'), ('benjamin', 'ben'), ('joseph', 'joe'), ('kenneth', 'kenny'),
             ('zachary', 'zach'), ('jonathan', 'jon'), ('samuel', 'sam'), ('thomas', 'tommy'), ('anthony', 'tony'),
             ('gabriel', 'gabe'), ('jacob', 'jake'), ('timothy', 'tim'), ('cameron', 'cam'), ('alexander', 'alex'),
             ('jeffrey', 'jeff'), ('gregory', 'greg'), ('patrick', 'pat'), ('richard', 'ricky'), ('edward', 'eddie'),
             ('charles', 'charlie'), ('james', 'jimmy'), ('david', 'dave'), ('steven', 'steve'), ('stephen', 'steve'),
             ('nathaniel', 'nate'), ('donald', 'don'), ('ronald', 'ron'), ('frederick', 'fred'), ('lawrence', 'larry')]


def nickname_forms(name):
    """Other spellings of a full name with a common first-name form swapped, e.g. Matthew Hibner -> Matt Hibner."""
    parts = str(name).split()
    if len(parts) < 2: return set()
    first = parts[0].lower().strip('.'); out = set()
    for a, b in NICKNAMES:
        for x, y in ((a, b), (b, a)):
            if first == x: out.add(' '.join([y.capitalize()] + parts[1:]))
    return out


def name_key(n, pos):
    """Same rule as index.html nvKey: lower case, drop . ' ’ and Jr/Sr/II-V, letters only, then |POS."""
    import re
    s = re.sub(r"[.'’]", '', str(n).lower())
    s = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', s)
    return re.sub(r'[^a-z]', '', s) + '|' + pos


def values(S, rows, y, season):
    pa = DD.neighbours(S, rows, 'A', pool_max_t=None)
    out = {}
    for r, nn in zip(pa['test'], pa['nn'][30]):
        assert (S.t.values[nn] <= season - I.LAG).all() and S.key.values[r] not in set(S.key.values[nn])
        w = 0.5 ** ((season - S.t.values[nn]) / V.HALF_LIFE); w /= w.sum()
        out[int(r)] = float((w * y[nn]).sum())
    return out


def build(D, season, week, contracts):
    patch_loads(D, season)
    C.HORIZON = 3
    C.REPL_N = dict(C.REPL_N_FULL_ADOPTED)
    if week not in I.WEEKS:
        I.WEEKS = tuple(I.WEEKS) + (week,)
    QS.WEEK = week
    st, W, Sin, Sb, skipped = I.build(os.path.join(D, 'nflv'), os.path.join(D, 'rosters'), os.path.join(D, 'weekly'), week, extra=(season,))
    Lf, Lu = I.levels(W)
    a = types.SimpleNamespace(weekly=os.path.join(D, 'weekly'), wrost=os.path.join(D, 'wrost'), inj=os.path.join(D, 'inj'))
    AP.prod_available = _capture
    try:
        SS, X, parts = QS.build_S(Sin, W, st, Lf, Lu, a, os.path.join(D, 'sched', 'games.csv'), os.path.join(D, 'snaps'),
                                  os.path.join(D, 'nflv', 'players.csv'))
    finally:
        AP.prod_available = _orig_prod
    n = CAP['n'].copy()
    Sin['prod'] = SS['prod'].values; Sin['kind'] = SS['kind'].values
    C.W_V['games'] = 0.0; C.POOL_LAG, C.SNAP_FIRST = I.LAG, I.FIRST_Y
    y = np.nan_to_num(Sin.FV.values.astype(float)); yb = np.nan_to_num(Sb.FV.values.astype(float))
    cur = (Sin.t.values == season)
    rook = Sin.rookie_Y.values.astype(bool)
    # first-year player with no game yet (QBs: no real game, §7/§8; others: no available game) -> incoming-rookie value
    qb = Sin.pos.values == 'QB'
    incoming = cur & rook & np.where(qb, X, n == 0) & (Sb.kind.values == 'R0')
    vrows = Sin.index[cur & ~incoming & (Sin.kind.values == 'V')].values
    xrows = Sin.index[incoming].values
    v_in = values(Sin, vrows, y, season)
    v_x = values(Sb, xrows, yb, season)
    # players on the season roster who have never played an NFL game and have no row: incoming-rookie value
    Sb2, extra = add_unplayed_rookies(D, Sb, Sin, season, set(W.player_id[W.g == 1]))
    yb2 = np.concatenate([yb, np.zeros(len(Sb2) - len(Sb))])
    v_x.update(values(Sb2, extra, yb2, season))
    NAME = dict(zip(range(len(Sb2)), Sb2.name.values)); KEY = dict(zip(range(len(Sb2)), Sb2.key.values))
    T = CL.load(contracts)
    out = []
    for r, v in list(v_in.items()) + list(v_x.items()):
        S_ = Sin if r < len(Sin) else Sb2
        f, lab = CL.factor(S_.name.values[r], T, season, 'contract_year')
        g_ = S_.games.values[r] if r < len(Sin) else 0
        out.append({'gsis_id': str(S_.key.values[r]), 'name': str(S_.name.values[r]), 'pos': str(S_.pos.values[r]),
                    'age': round(float(S_.age.values[r]), 1) if S_.age.values[r] == S_.age.values[r] else None,
                    'games': int(g_), 'rookie': bool(S_.rookie_Y.values[r]), 'contract': lab, 'contract_factor': round(float(f), 4),
                    'basis': 'incoming rookie' if r in v_x else 'this season', 'raw': v * f})
    # name keys for the site, which matches by name and position (index.html nvKey uses the same rule)
    pl = pd.read_csv(os.path.join(D, 'nflv', 'players.csv'), low_memory=False).set_index('gsis_id')
    for o in out:
        names = {o['name']}
        if o['gsis_id'] in pl.index:
            r = pl.loc[o['gsis_id']]
            names |= {x for x in [r.get('display_name')] if isinstance(x, str)}
            names |= {f"{f} {r.get('last_name')}" for f in (r.get('first_name'), r.get('football_name'), r.get('common_first_name'))
                      if isinstance(f, str) and isinstance(r.get('last_name'), str)}
        o['keys'] = sorted({name_key(n, o['pos']) for n in names})
    own = {k for o in out for k in o['keys']}
    for o in out:
        extra = {name_key(n, o['pos']) for nm in [o['name']] for n in nickname_forms(nm)} - own
        o['keys'] = sorted(set(o['keys']) | extra)
    top = max(o['raw'] for o in out)
    for o in out:
        o['value'] = int(round(10000 * o.pop('raw') / top))
    out.sort(key=lambda o: -o['value'])
    for i, o in enumerate(out):
        o['rank'] = 1 + sum(1 for p in out if p['value'] > o['value'])
    meta = {'season': season, 'through_week': week, 'built_utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'scoring': 'full PPR, no TE premium, 12-team superflex', 'lines': C.REPL_N,
            'contract_security': 'on (deal ending this season counts as a contract year)',
            'players': len(out), 'incoming_rookie_values': len(v_x), 'top_raw': top,
            'note': 'Display build. Not used by the site\'s engine.'}
    meta['picks'] = 'Stage 1 slot values (docs/PLAN-pick-values-now.md), scaled by this week\'s top_raw'
    return {'meta': meta, 'players': out, 'picks': pick_rows(season + 1, top)}


def pick_rows(cls, top):
    """Next class's rookie picks: Stage 1 of docs/PLAN-pick-values-now.md (history of what each slot produced over a
    rookie's first three seasons), on this week's scale. Board names (Early/Mid/Late) and each slot 1.01-3.12."""
    pv = json.load(open(os.path.join(HERE, 'out', 'pick_values_now.json')))['stage1']['new_lines']
    rows = [{'name': f'{cls} {nm.split()[1]} {nm.split()[0]}', 'value': int(round(10000 * d['fv3'] / top))}
            for nm, d in pv['names'].items()]
    curve = pv['per_slot_curve_fv3']
    rows += [{'name': f'{cls} {1 + k // 12}.{1 + k % 12:02d}', 'value': int(round(10000 * curve[k] / top))} for k in range(36)]
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--season', type=int, default=2026)
    ap.add_argument('--week', type=int, default=None)
    ap.add_argument('--out', default=os.path.join(HERE, '..', 'data', 'new-value.json'))
    ap.add_argument('--contracts', default=os.path.join(HERE, '..', 'data', 'delta-contracts.json'))
    a = ap.parse_args()
    week = a.week or last_complete_week(os.path.join(a.data, 'sched', 'games.csv'), a.season)
    assert week and week >= 1, 'no completed week found'
    res = build(a.data, a.season, min(week, 18), a.contracts)
    json.dump(res, open(a.out, 'w'), indent=1)
    print(json.dumps(res['meta'], indent=1))
    print('top 5:', [(p['name'], p['value']) for p in res['players'][:5]])


if __name__ == '__main__':
    main()
