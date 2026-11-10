#!/usr/bin/env python3
"""
DELTA — COMPARABLES VALUE ("PLAYERS LIKE HIM") STUDY

Implements docs/PREREG-comparables-value.md. Read that first; this file is the execution,
not the design, and where the two disagree the pre-registration (with its section 13
amendments) wins.

Question: does a nearest-neighbour comparables value (CV) predict a player's next five
seasons of value-over-replacement (FV) better than simpler averages of similar past players
(B1 production, B2 production + age, B3 draft capital), overall (Q1) and for young players
(Q2), and are its stated odds honest (Q3)?

No market data of any kind is read. Data: nflverse (credit nflverse in anything published).

Usage:
    python comps_value_study.py --data DIR                 # confirmatory run (run ONCE, after lock)
    python comps_value_study.py --data DIR --counts-only   # sample counts and exclusions, no outcomes
"""
import argparse, json, math, os, sys
import numpy as np
import pandas as pd

# ── pre-registered constants ─────────────────────────────────────────────────
POS = ['QB', 'RB', 'WR', 'TE']
REPL_N = {'QB': 24, 'RB': 30, 'WR': 42, 'TE': 14}        # §5 replacement line
STARTER_N = {'QB': 24, 'RB': 24, 'WR': 24, 'TE': 12}     # §5 secondary outcome
DISCOUNT = 0.9                                           # §5, fixed
HORIZON = 5
SNAP_FIRST, SNAP_LAST = 2001, 2020                       # §5
TEST_FIRST, TEST_LAST = 2013, 2020                       # §7
POOL_LAG = 5                                             # §6 time rule: pool season <= t - 5
K_MAIN, K_SENS = 30, (15, 50)                            # §6
K_MIN = 10
BAND_MIN = 30
PROD_BAND = 2.0
AGE_BANDS = [(-1, 23), (24, 25), (26, 27), (28, 29), (30, 31), (32, 99)]   # integer ages
PICK_BANDS = [(1, 10), (11, 32), (33, 64), (65, 105), (106, 10**6), (None, None)]  # last = undrafted
CY_BANDS = [(0, 0), (1, 1), (2, 2), (3, 99)]
UNDRAFTED_PICK = 300
W_V = {'prod': 3.0, 'age': 2.0, 'draft': 1.5, 'cy': 1.0, 'games': 1.0}  # draft x 24/(G+24)
K_FADE = 24.0
W_R0 = {'draft': 3.0, 'age': 1.0}
LIFT_BAR = 0.02
ALPHA = 0.025                                            # two questions (lesson 7)
N_PERM = 10_000
N_CALIB_SIM = 2_000
AGE_DAY = (9, 7)                                         # ages pinned to 7 Sep


# ═════════════════════════════════════════════════════════════════════════════
# 1. DATA
# ═════════════════════════════════════════════════════════════════════════════
def load(data_dir, roster_dir=None):
    """roster_dir: POST-LOCK amendment A11. If given, each player-season's position comes from
    that season's nflverse roster file (roster_YYYY.csv), falling back to the stats file's
    position. The stats files carry a player's LATEST position on every season (Tim Tebow's
    2010-11 QB seasons read TE) and leave some seasons blank. Default (None) is the locked run."""
    s = pd.read_csv(os.path.join(data_dir, 'player_stats_season.csv'), low_memory=False)
    s = s[s.season_type == 'REG']
    s25 = pd.read_csv(os.path.join(data_dir, 'stats_player_reg_2025.csv'), low_memory=False)
    s25 = s25[s25.season_type == 'REG']
    overlap = set(s.season) & set(s25.season)
    assert not overlap, f'season in both stats files: {overlap}'
    cols = ['player_id', 'player_display_name', 'season', 'position', 'games',
            'receptions', 'fantasy_points', 'fantasy_points_ppr']
    st = pd.concat([s[cols], s25[cols]], ignore_index=True)
    assert not st.duplicated(['player_id', 'season']).any(), 'duplicate player-season rows'
    if roster_dir:
        import glob
        R = pd.concat([pd.read_csv(f, low_memory=False, usecols=['season', 'gsis_id', 'position'])
                       for f in sorted(glob.glob(os.path.join(roster_dir, 'roster_*.csv')))])
        R = R.dropna(subset=['gsis_id']).drop_duplicates(['gsis_id', 'season'], keep='last')
        R = R.rename(columns={'gsis_id': 'player_id', 'position': 'rpos'})
        st = st.merge(R, on=['player_id', 'season'], how='left')
        st['stats_position'] = st.position
        # POST-LOCK A12 (2 Nov 2026): a roster label outside QB/RB/WR/TE (FB, KR, ...) falls back to the stats
        # file's position. Before this, such seasons were dropped and counted as zero (286 player-seasons, e.g.
        # Reuben Droughns 2004, Chris Cooley 2005 listed FB). Default path (no roster_dir) unchanged.
        st['position'] = st.rpos.where(st.rpos.isin(POS), st.position)
        # A12, part two: fantasy platforms list fullbacks as running backs, so FB counts as RB here (Mike Tolbert
        # was FB on both the roster and the stats file for 2012-14 and showed as "Did Not Play").
        st.loc[st.position == 'FB', 'position'] = 'RB'
        st = st.drop(columns='rpos')
    st = st[st.position.isin(POS)].copy()
    st['games'] = st.games.fillna(0)
    st['receptions'] = st.receptions.fillna(0)
    st['P'] = (st.fantasy_points.fillna(0) + st.fantasy_points_ppr.fillna(0)) / 2 \
        + np.where(st.position == 'TE', 0.5 * st.receptions, 0.0)
    dp = pd.read_csv(os.path.join(data_dir, 'draft_picks.csv'), low_memory=False)
    pl = pd.read_csv(os.path.join(data_dir, 'players.csv'), low_memory=False)
    return st, dp, pl


def score_check(st):
    """§3: the formula, shown on three known seasons. Hand values are standard scoring from
    the raw stat line (checked separately); the assertion here is the half-PPR/TE algebra."""
    out = []
    for name, yr in [('Patrick Mahomes', 2018), ('Cooper Kupp', 2021), ('Travis Kelce', 2020)]:
        r = st[(st.player_display_name == name) & (st.season == yr)].iloc[0]
        out.append({'player': name, 'season': yr, 'pos': r.position, 'standard': round(r.fantasy_points, 2),
                    'ppr': round(r.fantasy_points_ppr, 2), 'delta_points': round(r.P, 2)})
    return out


def age_on(birth, season):
    """Age in years on 7 Sep of `season`, from a 'YYYY-MM-DD' string."""
    return (pd.Timestamp(season, *AGE_DAY) - pd.Timestamp(birth[:10])).days / 365.25


# ═════════════════════════════════════════════════════════════════════════════
# 2. SNAPSHOTS (§4) AND OUTCOMES (§5)
# ═════════════════════════════════════════════════════════════════════════════
def build(st, dp, pl, snap_last=SNAP_LAST, extra_seasons=(), check_complete=True, prod_override=None):
    # prod_override {(player_id, season): (points, games)} replaces a season's points and games in the production and
    # games features only (Historical Comps: QB games by the Start Profile rule, Steve 10 Nov 2026). Outcomes,
    # eligibility and career games are untouched. Default None = every locked run, unchanged.
    """Return (snaps, counts). One row per snapshot, features use only seasons <= t.
    Outcome columns (FV, n_start, any_start, complete) use t+1..t+5 and are never read by
    eligibility or features. `extra_seasons` adds snapshot seasons beyond snap_last whose
    outcomes are incomplete (used only for the current-player display)."""
    counts = {'excluded': {}}
    seasons_avail = sorted(st.season.unique())
    last_data = max(seasons_avail)

    # replacement and starter lines per (season, position)
    repl, start = {}, {}
    for (yr, pos), g in st.groupby(['season', 'position']):
        p = np.sort(g.P.values)[::-1]
        repl[(yr, pos)] = p[REPL_N[pos] - 1] if len(p) >= REPL_N[pos] else 0.0
        start[(yr, pos)] = p[STARTER_N[pos] - 1] if len(p) >= STARTER_N[pos] else 0.0

    pts = {(r.player_id, r.season): r.P for r in st.itertuples()}
    gms = {(r.player_id, r.season): r.games for r in st.itertuples()}

    # draft info: draft_picks first (by gsis_id), players.csv as fallback
    dq = dp[dp.gsis_id.notna()].sort_values(['season', 'pick']).drop_duplicates('gsis_id')
    draft = {r.gsis_id: (int(r.season), int(r.pick), r.age) for r in dq.itertuples()}
    plx = pl.set_index('gsis_id')
    birth = plx.birth_date.dropna().to_dict()
    pl_draft = {g: (int(r.draft_year), int(r.draft_pick)) for g, r in plx.iterrows()
                if pd.notna(r.draft_year) and pd.notna(r.draft_pick)}
    pl_rookie = plx.rookie_season.dropna().astype(int).to_dict()
    counts['draft_from_players_csv'] = 0

    first_game = st[st.games >= 1].groupby('player_id').season.min().to_dict()
    names = st.drop_duplicates('player_id', keep='last').set_index('player_id').player_display_name.to_dict()

    def outcome(key, pos, t):
        fv, ns, comp = 0.0, 0, True
        for k in range(1, HORIZON + 1):
            yr = t + k
            if yr > last_data:
                comp = False; continue
            p = pts.get((key, yr), 0.0) if key else 0.0
            fv += DISCOUNT ** (k - 1) * max(0.0, p - repl[(yr, pos)])
            ns += int(p >= start[(yr, pos)] and p > 0)
        return fv, ns, comp

    rows = []
    # ── veteran snapshots
    vet = st[(st.games >= 1)]
    snap_seasons = list(range(SNAP_FIRST, snap_last + 1)) + list(extra_seasons)
    for t in snap_seasons:
        for r in vet[vet.season == t].itertuples():
            pid, pos = r.player_id, r.position
            # recent production, DELTA 3/2/1 over seasons actually played
            num = den = 0.0
            for w, yr in ((3, t), (2, t - 1), (1, t - 2)):
                if prod_override is not None and (pid, yr) in prod_override:
                    p_, g = prod_override[(pid, yr)]
                else:
                    g = gms.get((pid, yr), 0); p_ = pts.get((pid, yr), 0.0)
                if g >= 1:
                    num += w * p_ / g; den += w
            if den == 0:                      # only with prod_override: a QB whose seasons were all cameos produced nothing
                assert prod_override is not None
                prod = 0.0
            else:
                prod = num / den
            dinfo = draft.get(pid)
            if dinfo is None and pid in pl_draft:
                dinfo = (pl_draft[pid][0], pl_draft[pid][1], np.nan); counts['draft_from_players_csv'] += 1
            # only a draft that happened by season t counts as known (always true for a player with a game)
            undrafted = not (dinfo and dinfo[0] <= t)
            pick = UNDRAFTED_PICK if undrafted else dinfo[1]
            # age
            if pid in birth:
                age = age_on(birth[pid], t)
            elif dinfo and pd.notna(dinfo[2]):
                age = float(dinfo[2]) + (t - dinfo[0])
            else:
                counts['excluded']['V: no birth date or draft age'] = counts['excluded'].get('V: no birth date or draft age', 0) + 1
                continue
            # career year: first NFL season = draft year if drafted, else first season with a game,
            # else players.csv rookie_season; whichever is earliest and <= t
            cands = [first_game.get(pid, t)]
            if dinfo and dinfo[0] <= t: cands.append(dinfo[0])
            if pid in pl_rookie and pl_rookie[pid] <= t: cands.append(pl_rookie[pid])
            cy = t - min(cands) + 1
            fv, ns, comp = outcome(pid, pos, t)
            rows.append(dict(kind='V', key=pid, name=names.get(pid, pid), t=t, pos=pos, prod=prod,
                             games=float(prod_override[(pid, t)][1] if prod_override is not None and (pid, t) in prod_override else r.games),
                             age=age, cy=cy, pick=pick,
                             draft=math.log(min(pick, UNDRAFTED_PICK)), undrafted=undrafted, G=np.nan, FV=fv, n_start=ns, any_start=int(ns > 0),
                             complete=comp))
    snaps_v = pd.DataFrame(rows)
    # career games through t (1999 onward)
    gtab = st[['player_id', 'season', 'games']]
    cum = {}
    for pid, g in gtab.sort_values('season').groupby('player_id'):
        c = 0.0
        for yr, gg in zip(g.season, g.games):
            c += gg; cum[(pid, yr)] = c
    snaps_v['G'] = [cum[(k, t)] for k, t in zip(snaps_v.key, snaps_v.t)]
    counts['V_career_pre1999'] = int(((snaps_v.t - snaps_v.cy + 1) < 1999).sum())

    # ── incoming-rookie snapshots: drafted at QB/RB/WR/TE in draft year t+1
    rows = []
    # amendment A2: a drafted player with neither a birth date nor a draft age gets the median
    # draft age of his class and position (all such cases never played; excluding them would
    # delete only busts, against §4 "every drafted player is included")
    med_age = dp[dp.position.isin(POS)].groupby(['season', 'position']).age.median().to_dict()
    counts['R0_age_imputed'] = 0
    for t in snap_seasons:
        cls = dp[(dp.season == t + 1) & dp.position.isin(POS)]
        for r in cls.itertuples():
            gid = r.gsis_id if pd.notna(r.gsis_id) else None
            key = gid or f'draft:{r.season}:{r.pick}'
            pos = r.position
            if gid and gid in birth:
                age = age_on(birth[gid], t + 1)
            elif pd.notna(r.age):
                age = float(r.age)
            elif pd.notna(med_age.get((r.season, pos), np.nan)):
                age = float(med_age[(r.season, pos)]); counts['R0_age_imputed'] += 1
            else:
                counts['excluded']['R0: no birth date or draft age'] = counts['excluded'].get('R0: no birth date or draft age', 0) + 1
                continue
            fv, ns, comp = outcome(gid, pos, t)
            rows.append(dict(kind='R0', key=key, name=r.pfr_player_name, t=t, pos=pos, prod=np.nan,
                             games=np.nan, age=age, cy=0, pick=int(r.pick), draft=math.log(min(int(r.pick), UNDRAFTED_PICK)), undrafted=False,
                             G=0.0, FV=fv, n_start=ns, any_start=int(ns > 0), complete=comp))
    snaps = pd.concat([snaps_v, pd.DataFrame(rows)], ignore_index=True)
    snaps['age_int'] = np.floor(snaps.age).astype(int)
    snaps = snaps.reset_index(drop=True)
    main = snaps[snaps.t <= snap_last]
    assert main.complete.all() or not check_complete, 'a snapshot inside 2001-2020 has an incomplete window'
    counts['snapshots'] = {f'{k}': int(v) for k, v in main.groupby('kind').size().items()}
    counts['test'] = {f'{k}': int(v) for k, v in
                      main[(main.t >= TEST_FIRST) & (main.t <= TEST_LAST)].groupby('kind').size().items()}
    counts['test_players'] = int(main[(main.t >= TEST_FIRST)].key.nunique())
    return snaps, counts


# ═════════════════════════════════════════════════════════════════════════════
# 3. NEIGHBOURS AND BANDS — computed once from features; outcomes never read here
# ═════════════════════════════════════════════════════════════════════════════
def _band_idx(val, edges):
    for i, (lo, hi) in enumerate(edges):
        if lo <= val <= hi:
            return i
    raise ValueError(val)


def _grow(order_of, have, start, n_bands, count_fn, ok_fn):
    """Grow a set of contiguous band indices from `start` toward the nearer neighbour until
    ok_fn(count) or all bands are included. order_of(i) is the band midpoint for nearness."""
    lo = hi = start
    while not ok_fn(count_fn(lo, hi)) and (lo > 0 or hi < n_bands - 1):
        cand = []
        if lo > 0: cand.append(('lo', abs(order_of(lo - 1) - have)))
        if hi < n_bands - 1: cand.append(('hi', abs(order_of(hi + 1) - have)))
        side = min(cand, key=lambda c: (c[1], c[0] != 'lo'))[0]
        if side == 'lo': lo -= 1
        else: hi += 1
    return lo, hi


def precompute(snaps, test_first=TEST_FIRST, test_last=TEST_LAST, ks=(K_MAIN,) + K_SENS,
               pool_max_t=None, test_rows=None):
    """For each test snapshot: CV neighbour indices for every k, and B1/B2/B3 member indices.
    Returns dict with 'test' (row indices into snaps), 'nn' {k: list of arrays}, 'b1','b2','b3'
    (lists of arrays) and 'excluded' (row indices with < K_MIN comparables).
    All leak checks of §8.4 are asserted here."""
    S = snaps
    if test_rows is None:
        test_rows = S.index[(S.t >= test_first) & (S.t <= test_last)].values
    keys = S.key.values; tt = S.t.values; pos = S.pos.values; kind = S.kind.values
    res = {'test': [], 'nn': {k: [] for k in ks}, 'b1': [], 'b2': [], 'b3': [], 'excluded': [],
           'pool_size': []}
    pick_mid = [5.5, 21.5, 48.5, 85, 200, 300]
    cy_mid = [0, 1, 2, 4]
    for t in sorted(set(tt[test_rows])):
        pmax = t - POOL_LAG if pool_max_t is None else pool_max_t
        pool_all = S.index[(S.t >= SNAP_FIRST) & (S.t <= pmax)].values
        assert (tt[pool_all] <= t - POOL_LAG).all() or pool_max_t is not None, 'pool leak'
        rows_t = test_rows[tt[test_rows] == t]
        for p in POS:
            for kd in ('V', 'R0'):
                trow = rows_t[(pos[rows_t] == p) & (kind[rows_t] == kd)]
                if not len(trow): continue
                prow = pool_all[(pos[pool_all] == p) & (kind[pool_all] == kd)]
                feats = ['prod', 'age', 'draft', 'cy', 'games'] if kd == 'V' else ['draft', 'age']
                P = S.loc[prow, feats].values.astype(float)
                mu, sd = P.mean(0), P.std(0)
                sd[sd == 0] = 1.0
                Pz = (P - mu) / sd
                Tz = (S.loc[trow, feats].values.astype(float) - mu) / sd
                if kd == 'V':
                    fade = K_FADE / (S.loc[trow, 'G'].values + K_FADE)
                    W = np.stack([np.full(len(trow), W_V['prod']), np.full(len(trow), W_V['age']),
                                  W_V['draft'] * fade, np.full(len(trow), W_V['cy']),
                                  np.full(len(trow), W_V['games'])], 1)
                else:
                    W = np.tile([W_R0['draft'], W_R0['age']], (len(trow), 1))
                d2 = (((Tz[:, None, :] - Pz[None, :, :]) ** 2) * W[:, None, :]).sum(2)
                # B-method pools (band arrays)
                pool_pos = pool_all[pos[pool_all] == p]           # B3 crosses kinds via career year
                for i, r in enumerate(trow):
                    same = keys[prow] == keys[r]
                    dd = d2[i].copy(); dd[same] = np.inf
                    n_avail = int((~same).sum())
                    res['pool_size'].append(n_avail)
                    if n_avail < K_MIN:
                        res['excluded'].append(r); continue
                    res['test'].append(r)
                    order = np.argsort(dd, kind='stable')
                    for k in ks:
                        nn = prow[order[:min(k, n_avail)]]
                        assert keys[r] not in set(keys[nn]), 'self in neighbours'
                        assert (tt[nn] <= t - POOL_LAG).all() or pool_max_t is not None
                        res['nn'][k].append(nn)
                    pv = prow[~same]
                    res['b1'].append(_b1(S, r, pv, kd))
                    res['b2'].append(_b2(S, r, pv, kd))
                    pp = pool_pos[keys[pool_pos] != keys[r]]
                    res['b3'].append(_b3(S, r, pp, pick_mid, cy_mid))
    res['test'] = np.array(res['test'], dtype=int)
    for m in ('b1', 'b2', 'b3'):
        for r, mem in zip(res['test'], res[m]):
            assert keys[r] not in set(keys[mem]), f'self in {m}'
    return res


def _pick_band(pick, undrafted):
    return len(PICK_BANDS) - 1 if undrafted else _band_idx(pick, PICK_BANDS[:-1])


def _prod_bands(vals):
    return np.floor(vals / PROD_BAND).astype(int)


def _b1(S, r, pv, kd):
    if kd == 'R0':
        return pv
    pb = _prod_bands(S.loc[pv, 'prod'].values)
    mine = int(np.floor(S.at[r, 'prod'] / PROD_BAND))
    lo_b, hi_b = min(pb.min(), mine), max(pb.max(), mine)
    have = S.at[r, 'prod']
    lo, hi = _grow(lambda i: (i + lo_b) * PROD_BAND + PROD_BAND / 2, have, mine - lo_b, hi_b - lo_b + 1,
                   lambda a, b: int(((pb >= a + lo_b) & (pb <= b + lo_b)).sum()), lambda c: c >= BAND_MIN)
    return pv[(pb >= lo + lo_b) & (pb <= hi + lo_b)]


def _b2(S, r, pv, kd):
    ages = S.loc[pv, 'age_int'].values
    ab = np.array([_band_idx(a, AGE_BANDS) for a in ages])
    my_ab = _band_idx(S.at[r, 'age_int'], AGE_BANDS)
    amid = lambda i: (max(AGE_BANDS[i][0], 21) + min(AGE_BANDS[i][1], 34)) / 2
    have_a = S.at[r, 'age']
    if kd == 'R0':
        lo, hi = _grow(amid, have_a, my_ab, len(AGE_BANDS),
                       lambda a, b: int(((ab >= a) & (ab <= b)).sum()), lambda c: c >= BAND_MIN)
        return pv[(ab >= lo) & (ab <= hi)]
    pb = _prod_bands(S.loc[pv, 'prod'].values)
    mine = int(np.floor(S.at[r, 'prod'] / PROD_BAND))
    in_p = pb == mine
    lo, hi = _grow(amid, have_a, my_ab, len(AGE_BANDS),
                   lambda a, b: int((in_p & (ab >= a) & (ab <= b)).sum()), lambda c: c >= BAND_MIN)
    m = in_p & (ab >= lo) & (ab <= hi)
    if m.sum() >= BAND_MIN:
        return pv[m]
    # all ages included and still short: widen production (all ages)
    lo_b, hi_b = min(pb.min(), mine), max(pb.max(), mine)
    have = S.at[r, 'prod']
    plo, phi = _grow(lambda i: (i + lo_b) * PROD_BAND + PROD_BAND / 2, have, mine - lo_b, hi_b - lo_b + 1,
                     lambda a, b: int(((pb >= a + lo_b) & (pb <= b + lo_b)).sum()), lambda c: c >= BAND_MIN)
    return pv[(pb >= plo + lo_b) & (pb <= phi + lo_b)]


def _b3(S, r, pp, pick_mid, cy_mid):
    pk = np.array([_pick_band(x, u) for x, u in zip(S.loc[pp, 'pick'].values, S.loc[pp, 'undrafted'].values)])
    cyb = np.array([_band_idx(x, CY_BANDS) for x in S.loc[pp, 'cy'].values])
    my_pk = _pick_band(S.at[r, 'pick'], S.at[r, 'undrafted'])
    my_cy = _band_idx(S.at[r, 'cy'], CY_BANDS)
    in_pk = pk == my_pk
    lo, hi = _grow(lambda i: cy_mid[i], cy_mid[my_cy], my_cy, len(CY_BANDS),
                   lambda a, b: int((in_pk & (cyb >= a) & (cyb <= b)).sum()), lambda c: c >= BAND_MIN)
    m = in_pk & (cyb >= lo) & (cyb <= hi)
    if m.sum() >= BAND_MIN:
        return pp[m]
    plo, phi = _grow(lambda i: math.log(pick_mid[i]), math.log(pick_mid[my_pk]), my_pk, len(PICK_BANDS),
                     lambda a, b: int(((pk >= a) & (pk <= b)).sum()), lambda c: c >= BAND_MIN)
    return pp[(pk >= plo) & (pk <= phi)]


# ═════════════════════════════════════════════════════════════════════════════
# 4. PREDICT, SCORE, TEST
# ═════════════════════════════════════════════════════════════════════════════
def predict(pre, y):
    """y: outcome array indexed like snaps. Returns {method: predictions on pre['test']}."""
    out = {'CV': np.array([y[nn].mean() for nn in pre['nn'][K_MAIN]])}
    for k in K_SENS:
        if k in pre['nn']:
            out[f'CV_k{k}'] = np.array([y[nn].mean() for nn in pre['nn'][k]])
    for m, lab in (('b1', 'B1'), ('b2', 'B2'), ('b3', 'B3')):
        out[lab] = np.array([y[mem].mean() for mem in pre[m]])
    return out


def rmse(a, b): return float(np.sqrt(np.mean((a - b) ** 2)))
def mae(a, b): return float(np.mean(np.abs(a - b)))


def spearman(a, b):
    ra = pd.Series(a).rank().values; rb = pd.Series(b).rank().values
    if ra.std() == 0 or rb.std() == 0: return 0.0
    return float(np.corrcoef(ra, rb)[0, 1])


def perm_test(y, pa, pb, clusters, n_perm=N_PERM, seed=11):
    """Paired permutation: swap the two methods' predictions for ALL of a player's snapshots
    together. Statistic = lift = 1 - RMSE_a / RMSE_b. One-sided: is a better than b?"""
    ea = (pa - y) ** 2; eb = (pb - y) ** 2
    cl = pd.factorize(clusters)[0]
    nc = cl.max() + 1
    sa = np.bincount(cl, ea, nc); sb = np.bincount(cl, eb, nc)
    n = len(y)
    obs = 1 - math.sqrt(sa.sum() / n) / math.sqrt(sb.sum() / n)
    rng = np.random.default_rng(seed)
    cnt = 0
    for start in range(0, n_perm, 1000):
        m = min(1000, n_perm - start)
        sw = rng.random((m, nc)) < 0.5
        A = np.where(sw, sb, sa).sum(1); B = np.where(sw, sa, sb).sum(1)
        lift = 1 - np.sqrt(A / n) / np.sqrt(B / n)
        cnt += int((lift >= obs).sum())
    p = (cnt + 1) / (n_perm + 1)
    return obs, p


def questions(S, pre, y, n_perm=N_PERM, seed=11):
    """Q1 and Q2 on outcome vector y. Returns dict with lifts, p-values and pass flags."""
    pr = predict(pre, y)
    T = pre['test']; yt = y[T]; cl = S.key.values[T]
    out = {}
    lift1, p1 = perm_test(yt, pr['CV'], pr['B2'], cl, n_perm, seed)
    out['Q1'] = {'n': int(len(T)), 'players': int(len(set(cl))), 'baseline': 'B2',
                 'rmse_cv': rmse(pr['CV'], yt), 'rmse_base': rmse(pr['B2'], yt),
                 'lift': lift1, 'p': p1, 'pass': bool(lift1 >= LIFT_BAR and p1 < ALPHA)}
    young = S.cy.values[T] <= 2
    yy = yt[young]
    r2, r3 = rmse(pr['B2'][young], yy), rmse(pr['B3'][young], yy)
    base = 'B2' if r2 <= r3 else 'B3'
    lift2, p2 = perm_test(yy, pr['CV'][young], pr[base][young], cl[young], n_perm, seed + 1)
    out['Q2'] = {'n': int(young.sum()), 'players': int(len(set(cl[young]))), 'baseline': base,
                 'rmse_cv': rmse(pr['CV'][young], yy), 'rmse_B2': r2, 'rmse_B3': r3,
                 'lift': lift2, 'p': p2, 'pass': bool(lift2 >= LIFT_BAR and p2 < ALPHA)}
    return out, pr


# ── Q3: honest odds ──────────────────────────────────────────────────────────
def calib_error(pred, obs, edges):
    b = np.clip(np.searchsorted(edges, pred, side='right') - 1, 0, len(edges) - 2)
    err = 0.0; tab = []
    for i in range(len(edges) - 1):
        m = b == i
        if not m.any(): continue
        err += m.sum() * abs(pred[m].mean() - obs[m].mean())
        tab.append({'bin': f'{edges[i]:.2f}-{edges[i+1]:.2f}', 'n': int(m.sum()),
                    'predicted': float(pred[m].mean()), 'observed': float(obs[m].mean())})
    return err / len(pred), tab


def honest(S, pre, col, n_sim=N_CALIB_SIM, seed=5, mask=None, decile_bins=False, pct=95.0):
    """Calibration error of CV (k=30) for outcome `col`, vs a perfectly honest forecaster
    whose outcomes are drawn from CV's own 30 comparables. Bins: tenths of probability for
    any_start; equal-count tenths (deciles) of the prediction for n_start."""
    T = pre['test']; nns = pre['nn'][K_MAIN]
    if mask is None: mask = np.ones(len(T), bool)
    y = S[col].values.astype(float)
    pred = np.array([y[nn].mean() for nn in nns])[mask]
    obs = y[T][mask]
    if decile_bins:
        edges = np.unique(np.quantile(pred, np.linspace(0, 1, 11)))
        edges[-1] += 1e-9
    else:
        edges = np.linspace(0, 1, 11); edges[-1] += 1e-9
    real, tab = calib_error(pred, obs, edges)
    rng = np.random.default_rng(seed)
    comp_vals = [y[nn] for nn, m in zip(nns, mask) if m]
    lens = np.array([len(v) for v in comp_vals])
    flat = np.concatenate(comp_vals); offs = np.concatenate([[0], np.cumsum(lens)[:-1]])
    sims = np.empty(n_sim)
    for s in range(n_sim):
        draw = flat[offs + (rng.random(len(lens)) * lens).astype(int)]
        sims[s], _ = calib_error(pred, draw, edges)
    lim = float(np.percentile(sims, pct))
    return {'n': int(mask.sum()), 'error': float(real), 'limit': lim, 'pct': pct,
            'honest': bool(real <= lim), 'table': tab}


def q3(S, pre, n_sim=N_CALIB_SIM):
    T = pre['test']; P = S.pos.values[T]
    out = {'overall': {'any_start': honest(S, pre, 'any_start', n_sim),
                       'n_start': honest(S, pre, 'n_start', n_sim, decile_bins=True)}}
    pos_pct = 100 * (1 - 0.05 / 8)        # amendment A6: 8 position checks share 5%
    for p in POS:
        m = P == p
        out[p] = {'any_start': honest(S, pre, 'any_start', n_sim, seed=7, mask=m, pct=pos_pct),
                  'n_start': honest(S, pre, 'n_start', n_sim, seed=8, mask=m, decile_bins=True, pct=pos_pct)}
    out['pass'] = bool(out['overall']['any_start']['honest'] and out['overall']['n_start']['honest']
                       and all(out[p][c]['honest'] for p in POS for c in ('any_start', 'n_start')))
    return out


# ═════════════════════════════════════════════════════════════════════════════
# 5. REPORTING
# ═════════════════════════════════════════════════════════════════════════════
def breakdown(S, pre, pr, y):
    T = pre['test']; yt = y[T]
    groups = {'all': np.ones(len(T), bool)}
    for p in POS: groups[p] = S.pos.values[T] == p
    cy = S.cy.values[T]
    for lab, (lo, hi) in {'cy0': (0, 0), 'cy1': (1, 1), 'cy2': (2, 2), 'cy3-5': (3, 5), 'cy6+': (6, 99)}.items():
        groups[lab] = (cy >= lo) & (cy <= hi)
    out = {}
    for g, m in groups.items():
        out[g] = {'n': int(m.sum())}
        for meth, p in pr.items():
            out[g][meth] = {'rmse': rmse(p[m], yt[m]), 'mae': mae(p[m], yt[m]), 'spearman': spearman(p[m], yt[m])}
    return out


def current_players(S_all, names=('Marvin Harrison Jr.', 'Makai Lemon', 'CeeDee Lamb', 'Javonte Williams',
                                  'Caleb Williams', 'Brock Bowers'), t_now=2025, pool_max_t=2020):
    """§11 display material: comparables for named current players at the end of 2025."""
    out = []
    for nm in names:
        hit = S_all[(S_all.t == t_now) & (S_all.name == nm)]
        if hit.empty:
            out.append({'player': nm, 'error': 'no 2025 snapshot'}); continue
        r = hit.index[0]
        pre = precompute(S_all, ks=(K_MAIN, 10), pool_max_t=pool_max_t, test_rows=np.array([r]))
        if not len(pre['test']):
            out.append({'player': nm, 'error': 'fewer than 10 comparables'}); continue
        nn30 = pre['nn'][K_MAIN][0]; nn10 = pre['nn'][10][0]
        row = S_all.loc[r]
        out.append({'player': nm, 'kind': row.kind, 'pos': row.pos, 'age': round(row.age, 1),
                    'pick': int(row.pick), 'career_year': int(row.cy),
                    'recent_ppg': None if pd.isna(row['prod']) else round(row['prod'], 1),
                    'cv_fv': round(float(S_all.FV.values[nn30].mean()), 1),
                    'cv_chance_starter_season': round(float(S_all.any_start.values[nn30].mean()), 3),
                    'cv_expected_starter_seasons': round(float(S_all.n_start.values[nn30].mean()), 2),
                    'closest_10': [{'name': S_all.at[i, 'name'], 'season': int(S_all.at[i, 't']),
                                    'age': round(S_all.at[i, 'age'], 1), 'pick': int(S_all.at[i, 'pick']),
                                    'recent_ppg': None if pd.isna(S_all.at[i, 'prod']) else round(S_all.at[i, 'prod'], 1),
                                    'FV': round(float(S_all.at[i, 'FV']), 1),
                                    'starter_seasons': int(S_all.at[i, 'n_start'])} for i in nn10]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--out', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out',
                                                 'comps_value_results.json'))
    ap.add_argument('--counts-only', action='store_true')
    ap.add_argument('--rosters', default=None, help='POST-LOCK A11 robustness run: per-season roster positions')
    a = ap.parse_args()
    st, dp, pl = load(a.data, a.rosters)
    S_all, counts = build(st, dp, pl, extra_seasons=(2025,))
    S = S_all[S_all.t <= SNAP_LAST].reset_index(drop=True)
    pre = precompute(S)
    counts['cv_excluded_lt10'] = len(pre['excluded'])
    counts['test_scored'] = int(len(pre['test']))
    print(json.dumps(counts, indent=1))
    if a.counts_only:
        return
    y = S.FV.values.astype(float)
    qs, pr = questions(S, pre, y)
    res = {'prereg': 'docs/PREREG-comparables-value.md', 'scoring_check': score_check(st), 'counts': counts,
           'Q1': qs['Q1'], 'Q2': qs['Q2'], 'Q3': q3(S, pre), 'breakdown': breakdown(S, pre, pr, y),
           'young_mean_vs_median': {
               'FV_mean': float(y[pre['test']][S.cy.values[pre['test']] <= 2].mean()),
               'FV_median': float(np.median(y[pre['test']][S.cy.values[pre['test']] <= 2]))},
           'current_players': current_players(S_all)}
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, 'w') as f:
        json.dump(res, f, indent=1, default=float)
    print(json.dumps({k: res[k] for k in ('Q1', 'Q2')}, indent=1))
    print('Q3 pass:', res['Q3']['pass'])


if __name__ == '__main__':
    main()
