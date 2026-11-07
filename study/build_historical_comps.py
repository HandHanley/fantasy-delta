#!/usr/bin/env python3
"""Builds data/historical-comps.json: the Historical Comps view of the Comparable Players card (player page).

For each current DELTA player, his 30 closest past snapshots under the rules already tested and adopted:
  - matching: Version A (docs/PREREG-draft-drop.md) - no draft slot for veterans with 2+ seasons
  - weights:  Fix 2 (docs/PREREG-honest-odds.md, -v3.md) - recent comparables count more, half-life 8 seasons
  - outcome:  starter seasons (top 24 QB/RB/WR, top 12 TE) in the three seasons after the matched season
Pool = snapshots whose three-year window has fully closed (season <= LAST_FULL - 3).

Display only. Nothing here feeds the DELTA Score, a value or a call.
Rebuild once a year: after the season ends (new veteran snapshots) and after the draft (new rookies).

Usage: python3 build_historical_comps.py NFLVERSE_DIR ROSTERS_DIR UNIVERSE_JSON OUT_JSON [--snap 2025]
  UNIVERSE_JSON: [{"n": name, "pos": "WR"}, ...] - the player page's list (COMP), names exactly as the site uses them.
"""
import sys, json, re, argparse, datetime
import numpy as np
import comps_value_study as C, honest_odds_study as O, comps_draft_drop as DD

LABELS = ['No Starter Seasons', 'One Starter Season', 'Two Or More Starter Seasons']
BUCKET = lambda n: 0 if n == 0 else (1 if n == 1 else 2)


def norm(s):
    s = re.sub(r"[.'’]", '', str(s).lower())
    s = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', s)
    return re.sub(r'[^a-z]', '', s)


def rounded_pct(w_by_bucket):
    """Whole percentages that add to exactly 100 (largest remainder)."""
    raw = [100 * x for x in w_by_bucket]
    pct = [int(np.floor(x)) for x in raw]
    for i in sorted(range(3), key=lambda i: raw[i] - pct[i], reverse=True)[:100 - sum(pct)]:
        pct[i] += 1
    return pct


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('nflverse'); ap.add_argument('rosters'); ap.add_argument('universe'); ap.add_argument('out')
    ap.add_argument('--snap', type=int, default=2025, help='season the current snapshots are taken at')
    a = ap.parse_args()
    SNAP, POOL_MAX = a.snap, a.snap - 3

    C.HORIZON, C.POOL_LAG = 3, 3
    st, dp, pl = C.load(a.nflverse, a.rosters)
    S, _ = C.build(st, dp, pl, snap_last=POOL_MAX, extra_seasons=(SNAP,), check_complete=False)
    S = S.reset_index(drop=True)
    assert S[S.t <= POOL_MAX].complete.all(), 'pool has an unfinished three-year window'

    st['rank'] = st.groupby(['season', 'position']).P.rank(ascending=False, method='min')
    PTS = {(p, int(y)): float(v) for p, y, v in zip(st.player_id, st.season, st.P)}
    GMS = {(p, int(y)): float(v) for p, y, v in zip(st.player_id, st.season, st.games)}
    BYPOS = {k: np.sort(g.P.values)[::-1] for k, g in st.groupby(['season', 'position'])}
    g = st[st.games >= 1].groupby(['season', 'position']).size()
    N = {(int(s), p): int(n) for (s, p), n in g.items()}

    def finish(k, y, ps):
        if (k, y) not in PTS: return None
        return int((BYPOS[(y, ps)] > PTS[(k, y)]).sum()) + 1

    # match the site's players to current snapshots, by name + position
    uni = json.load(open(a.universe))
    cur = S[S.t == SNAP]
    idx = {}
    import pandas as pd, os
    pp = pd.read_csv(os.path.join(a.nflverse, 'players.csv'), low_memory=False)
    alias = {}                                 # gsis id -> every name nflverse knows him by (Chig / Chigoziem Okonkwo)
    for r in pp.itertuples():
        names_ = {r.display_name} | {f'{f} {r.last_name}' for f in (r.first_name, r.football_name, r.common_first_name)
                                    if isinstance(f, str)}
        alias[r.gsis_id] = {norm(x) for x in names_ if isinstance(x, str)}
    for i, nm, ps, k in zip(cur.index, cur.name, cur.pos, cur.key):
        for nmz in {norm(nm)} | alias.get(k, set()):
            if int(i) not in idx.get((nmz, ps), []):
                idx.setdefault((nmz, ps), []).append(int(i))
    rows, missing, ambiguous = {}, [], []
    for u in uni:
        hit = idx.get((norm(u['n']), u['pos']), [])
        if len(hit) == 1: rows[u['n']] = hit[0]
        elif len(hit) > 1: ambiguous.append(u['n'])
        else: missing.append(u['n'])

    names = list(rows)
    R = np.array([rows[n] for n in names])
    pre = DD.neighbours(S, R, 'A', pool_max_t=POOL_MAX)
    parts = O.version_parts(S, N, pre, 'Fix 2')
    out = {}
    # neighbours() returns rows grouped by position and kind, NOT in the order given, and skips rows with too
    # few candidates: always pair results through pre['test'], never through the input order.
    by_row = {r: n for n, r in rows.items()}
    assert len(pre['test']) == len(parts)
    for r, (nn, w, _) in zip(pre['test'], parts):
        nm = by_row[int(r)]
        assert (S.t.values[nn] <= POOL_MAX).all(), nm
        assert S.key.values[r] not in set(S.key.values[nn]), nm
        ns = S.n_start.values[nn]
        pct = rounded_pct([w[ns == 0].sum(), w[ns == 1].sum(), w[ns >= 2].sum()])
        ex = [[], [], []]; seen = set()
        for i in nn:                                   # nearest first, each past player once
            k = S.key.values[i]
            if k in seen: continue
            seen.add(k)
            t = int(S.t.values[i]); ps = S.pos.values[i]
            if sum(GMS.get((k, y), 0) for y in (t + 1, t + 2, t + 3)) == 0:
                continue                               # never played again in the window: not shown as an example
            b = BUCKET(S.n_start.values[i])
            if len(ex[b]) >= 3: continue
            ranks = [f for f in (finish(k, y, ps) for y in (t + 1, t + 2, t + 3)) if f is not None]
            ex[b].append([S.name.values[i], t + 1 if S.kind.values[i] == 'R0' else t,
                          f'{ps}{min(ranks)}' if ranks else None])
        row = S.loc[r]; rookie = row.kind == 'R0'
        und = S.undrafted.values[nn].astype(bool); picks = S.pick.values[nn]
        m = {'age': [round(float(row.age), 1), int(np.floor(S.age.values[nn].min())), int(np.floor(S.age.values[nn].max()))]}
        if rookie or row.cy < 2:
            m['pick'] = [None if row.undrafted else int(row.pick),
                         int(picks[~und].min()) if (~und).any() else None,
                         int(picks[~und].max()) if (~und).any() else None, int(und.sum())]
        if not rookie:
            m['ppg'] = [round(float(row['prod']), 1), round(float(np.nanmin(S['prod'].values[nn])), 1),
                        round(float(np.nanmax(S['prod'].values[nn])), 1)]
            gm = S.games.values[nn]
            m['games'] = [None if np.isnan(row.games) else int(row.games), int(np.nanmin(gm)), int(np.nanmax(gm))]
            m['cy'] = [int(row.cy), int(S.cy.values[nn].min()), int(S.cy.values[nn].max())]
        sea = S.t.values[nn]
        out[nm] = {'k': 'R' if rookie else 'V', 'pct': pct, 'ex': ex, 'm': m, 'n': len(seen),
                   's': [int(sea.min()) + (1 if rookie else 0), int(sea.max()) + (1 if rookie else 0)]}

    doc = {'built': datetime.date.today().isoformat(), 'snap': SNAP, 'pool_to': POOL_MAX,
           'rules': 'Version A matching (PREREG-draft-drop), Fix 2 weights (PREREG-honest-odds), 3-season window; display only',
           'labels': LABELS, 'players': out}
    json.dump(doc, open(a.out, 'w'), separators=(',', ':'), ensure_ascii=False)
    dropped = [n for n in names if n not in out]
    print(f'{len(out)} players written; {len(dropped)} matched but too few candidates {dropped}; {len(missing)} with no {SNAP} snapshot; {len(ambiguous)} ambiguous')
    if ambiguous: print('AMBIGUOUS:', ambiguous)
    print('NO SNAPSHOT:', ', '.join(sorted(missing)))


if __name__ == '__main__':
    main()
