#!/usr/bin/env python3
"""
DELTA — OWN VALUE SCALE: CONTRACT SECURITY (a measured size, not a 2% test). docs/PREREG-contract-security.md.

Rows: fantasy-relevant veterans 2013-2022 (study/out/contract_history_rows.csv), snapshot entering season n = t + 1.
Status at n's kickoff from study/data/contract-history.json plus the rookie rule; years left = end - n (0, 1, 2+).
Decided on deals a team signed (veteran, extension, tags, RFA tender, practice squad, exercised option); rookie deals
reported. Points delivered = FV (next three seasons) / adopted preseason value; opportunity kept = QB starts, RB
carries + targets, WR/TE targets over the same seasons / the same comparables' own. Ranges: players resampled.

    python ovs_contract_security.py --nflverse D --rosters D --week1 FILE --schedules FILE (--labels | --crash | --run)
"""
import argparse, json, os
import numpy as np, pandas as pd
import comps_value_study as C
import ovs_era as E
import ovs_offseason as O
import ovs_second_contract as SC

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, 'out')
HIST = os.path.join(HERE, 'data', 'contract-history.json')
ROWS = os.path.join(OUT, 'contract_history_rows.csv')
TEAM_SIGNED = {'veteran', 'extension', 'franchise_tag', 'transition_tag', 'rfa_tender', 'practice_squad', 'rookie_option'}
N_BOOT, SEED, GUARD, BUFFER, LEAN_RUNS = 2000, 2026, -0.005, 2, 200
GROUPS = (0, 1, 2)
# League salary cap by season, $ millions (NFL announcements). 2010 was uncapped: 2009's figure is used.
CAP = {2006: 102.0, 2007: 109.0, 2008: 116.0, 2009: 123.0, 2010: 123.0, 2011: 120.0, 2012: 120.6, 2013: 123.0,
       2014: 133.0, 2015: 143.28, 2016: 155.27, 2017: 167.0, 2018: 177.2, 2019: 188.2, 2020: 198.2, 2021: 182.5,
       2022: 208.2, 2023: 224.8, 2024: 255.4, 2025: 279.2}


def deals_for(pid, P, dyear):
    """All deals with an end year, plus the rookie rule for drafts 2011+ (ends draft year + 3)."""
    out = []
    for c in P.get(pid, {}).get('contracts', []):
        if c.get('end') in (None, ''): continue
        signed = c.get('signed') or f"{int(c['first'])}-03-01"                 # §4: no date -> 1 March of its first season
        out.append(dict(c, signed=signed, end=int(c['end'])))
    d = dyear.get(pid)
    if d is not None and d >= 2011:
        out.append({'kind': 'rookie_rule', 'signed': f'{d}-05-01', 'end': d + 3, 'contract': 0, 'source': 'draft',
                    'confidence': 'rule', 'aav': None, 'first': d})
    return out


def status(pid, n, kickoff, P, dyear):
    """The deal in force at kickoff of season n: the latest signed before kickoff and not released before it."""
    cs = [c for c in deals_for(pid, P, dyear) if c['signed'] < kickoff and not (c.get('released') and c['released'] < kickoff)]
    if not cs: return None
    c = max(cs, key=lambda c: (c['signed'], c.get('contract') or 0))
    return c if c['end'] >= n else None


def labels(S, rows, sched, week1, nflverse):
    """Per measured row: group (0/1/2, 'unsigned', 'gap'), team-signed flag, money (aav / cap, sourced only)."""
    P = json.load(open(HIST))['players']
    dp = pd.read_csv(os.path.join(nflverse, 'draft_picks.csv'), low_memory=False).dropna(subset=['gsis_id'])
    dp = dp.sort_values(['season', 'pick']).drop_duplicates('gsis_id'); dyear = {g: int(s) for g, s in zip(dp.gsis_id, dp.season)}
    G = pd.read_csv(sched, low_memory=False); G = G[G.game_type == 'REG']; kick = G.groupby('season').gameday.min().to_dict()
    W = pd.read_csv(week1, low_memory=False); W['team'] = W.team.replace(O.CANON)   # on a club for its first game only
    W = W[(W.week == W.groupby(['season', 'team']).week.transform('min')) & W.status.isin(O.ON_TEAM) & W.gsis_id.notna()]
    on = set(zip(W.gsis_id, W.season.astype(int)))
    out = []
    for r in rows:
        pid, n = S.key.values[r], int(S.t.values[r]) + 1
        c = status(pid, n, kick[n], P, dyear)
        if c is None:
            later = [x for x in deals_for(pid, P, dyear) if x['signed'] >= kick[n] and x['end'] >= n and int(x.get('first') or n) <= n]
            grp = 'unsigned' if ((pid, n) not in on or later) else 'gap'
            out.append({'row': int(r), 'gsis_id': pid, 'n': n, 'group': grp, 'kind': None, 'team_signed': False,
                        'money': np.nan, 'sourced': False})
            continue
        sourced = bool(c.get('source'))
        aav = c.get('aav')
        money = float(aav) / CAP[int(c['first'])] if (sourced and aav not in (None, '') and c['kind'] in TEAM_SIGNED
                                                      and int(c['first']) in CAP) else np.nan
        out.append({'row': int(r), 'gsis_id': pid, 'n': n, 'group': min(c['end'] - n, 2), 'kind': c['kind'],
                    'team_signed': c['kind'] in TEAM_SIGNED, 'money': money, 'sourced': sourced or c['kind'] == 'rookie_rule'})
    return pd.DataFrame(out)


def opportunity(nflverse, sched):
    """Season opportunity per (gsis_id, season): QB = named starts (schedules), others = carries + targets / targets."""
    s = pd.read_csv(os.path.join(nflverse, 'player_stats_season.csv'), low_memory=False)
    s25 = pd.read_csv(os.path.join(nflverse, 'stats_player_reg_2025.csv'), low_memory=False)
    s = pd.concat([s[s.season_type == 'REG'], s25[s25.season_type == 'REG']], ignore_index=True)
    car = {(g, int(y)): float(c) for g, y, c in zip(s.player_id, s.season, s.carries.fillna(0))}
    tgt = {(g, int(y)): float(c) for g, y, c in zip(s.player_id, s.season, s.targets.fillna(0))}
    G = pd.read_csv(sched, low_memory=False); G = G[G.game_type == 'REG']
    qs = pd.concat([G[['season', 'home_qb_id']].rename(columns={'home_qb_id': 'q'}), G[['season', 'away_qb_id']].rename(columns={'away_qb_id': 'q'})])
    starts = qs.dropna().groupby(['q', 'season']).size().to_dict()
    return car, tgt, starts


def opp_vector(S, car, tgt, starts):
    o = np.zeros(len(S))
    for i, (k, t, p) in enumerate(zip(S.key.values, S.t.values.astype(int), S.pos.values)):
        yrs = range(t + 1, t + 1 + E.HORIZON)
        if p == 'QB': o[i] = sum(starts.get((k, y), 0) for y in yrs)
        elif p == 'RB': o[i] = sum(car.get((k, y), 0) + tgt.get((k, y), 0) for y in yrs)
        else: o[i] = sum(tgt.get((k, y), 0) for y in yrs)
    return o


class Boot:
    """Players resampled with replacement: per bootstrap, each player's rows count k times."""
    def __init__(self, players, n_boot, rng):
        self.u, self.ix = np.unique(players, return_inverse=True)
        n = len(self.u)
        self.Wt = np.vstack([np.ones(n)] + [np.bincount(rng.integers(0, n, n), minlength=n) for _ in range(n_boot)])

    def sums(self, vals, mask):
        """Row values summed per player (rows in mask), then per bootstrap (row 0 = the real sample)."""
        per = np.bincount(self.ix[mask], weights=vals[mask], minlength=len(self.u))
        return self.Wt @ per


def ratios(B, y, v, grp, pos=None, cnt_w=False):
    """Relative group ratios m_g = (Σy/Σv in g) / (Σy/Σv overall); by position then row-weighted when pos given."""
    if pos is None:
        tot = B.sums(y, np.ones(len(y), bool)) / B.sums(v, np.ones(len(y), bool))
        return {g: (B.sums(y, grp == g) / B.sums(v, grp == g)) / tot for g in GROUPS}
    out = {g: 0 for g in GROUPS}; n = {g: 0 for g in GROUPS}
    for p in np.unique(pos):
        mp = pos == p; tot = B.sums(y, mp) / B.sums(v, mp)
        for g in GROUPS:
            w = B.sums(np.ones(len(y)), mp & (grp == g))
            out[g] = out[g] + w * (B.sums(y, mp & (grp == g)) / np.maximum(B.sums(v, mp & (grp == g)), 1e-9)) / tot
            n[g] = n[g] + w
    return {g: out[g] / np.maximum(n[g], 1e-9) for g in GROUPS}


def bump(m): return (m[2] - m[0]) / 2


def money_bump(B, y, v, grp, tier):
    """Within each years-left group: (top-third ratio - bottom-third ratio) / 2, relative to the group; row-weighted."""
    num = 0; den = 0
    for g in GROUPS:
        mg = (grp == g) & (tier >= 0)
        rg = B.sums(y, mg) / np.maximum(B.sums(v, mg), 1e-9)
        top = B.sums(y, mg & (tier == 2)) / np.maximum(B.sums(v, mg & (tier == 2)), 1e-9)
        bot = B.sums(y, mg & (tier == 0)) / np.maximum(B.sums(v, mg & (tier == 0)), 1e-9)
        w = B.sums(np.ones(len(y)), mg)
        num = num + w * (top - bot) / (2 * rg); den = den + w
    return num / np.maximum(den, 1e-9)


def summary(x):
    est, b = float(x[0]), x[1:]
    return {'estimate': est, 'range_90': [float(np.quantile(b, .05)), float(np.quantile(b, .95))],
            'range_95': [float(np.quantile(b, .025)), float(np.quantile(b, .975))], 'se': float(b.std(ddof=1)),
            'excludes_zero_95': bool(np.quantile(b, .025) > 0 or np.quantile(b, .975) < 0)}


def shrink(d, se):
    """§3: pulled toward zero by its uncertainty: d x max(0, 1 - se^2 / d^2)."""
    return 0.0 if d == 0 else d * max(0.0, 1 - se ** 2 / d ** 2)


def no_harm(t, y, v, grp, decided):
    """Each season's decided rows take ratios learned with that season and the two either side left out (raw, unshrunk)."""
    new = v.copy()
    for s in np.unique(t):
        learn = decided & (np.abs(t - s) > BUFFER); tot = y[learn].sum() / v[learn].sum()
        for g in GROUPS:
            m = learn & (grp == g)
            if m.sum() == 0: continue
            sel = decided & (t == s) & (grp == g)
            new[sel] = v[sel] * (y[m].sum() / v[m].sum()) / tot
    return float(1 - C.rmse(new, y) / C.rmse(v, y))


def measure(pid, pos, y, v, o, ohat, grp, tier, rng, n_boot=N_BOOT, opp=True):
    B = Boot(pid, n_boot, rng)
    m = ratios(B, y, v, grp); res = {'points': {f'group_{g}': summary(m[g]) for g in GROUPS}, 'points_bump': summary(bump(m))}
    if opp:
        mo = ratios(B, o, ohat, grp, pos=pos)
        res['opportunity'] = {f'group_{g}': summary(mo[g]) for g in GROUPS}; res['opportunity_bump'] = summary(bump(mo))
    if tier is not None and (tier >= 0).sum() > 0:
        res['money_points_bump'] = summary(money_bump(B, y, v, grp, tier))
        if opp: res['money_opportunity_bump'] = summary(money_bump(B, o, ohat, grp, tier))
    return res


def shuffled(grp, tier, pos, t, rng):
    """Contract labels (years-left group and money third together) shuffled among rows of the same position and season."""
    g2, t2 = grp.copy(), (tier.copy() if tier is not None else None)
    for key in set(zip(pos, t)):
        m = np.where((pos == key[0]) & (t == key[1]))[0]; q = rng.permutation(m)
        g2[m] = grp[q]
        if t2 is not None: t2[m] = tier[q]
    return g2, t2


def lean(pid, pos, t, y, v, o, ohat, grp, tier, rng, n=LEAN_RUNS):
    """§2: what the method reads with no real link (labels shuffled), averaged over n shuffles: estimate - null value."""
    B0 = Boot(pid, 0, rng); acc = {}
    def add(k, x, null): acc.setdefault(k, []).append(float(x[0]) - null)
    for _ in range(n):
        g2, t2 = shuffled(grp, tier, pos, t, rng)
        m = ratios(B0, y, v, g2)
        for g in GROUPS: add(('points', f'group_{g}'), m[g], 1.0)
        add(('points_bump',), bump(m), 0.0)
        if o is not None:
            mo = ratios(B0, o, ohat, g2, pos=pos)
            for g in GROUPS: add(('opportunity', f'group_{g}'), mo[g], 1.0)
            add(('opportunity_bump',), bump(mo), 0.0)
        if t2 is not None and (t2 >= 0).sum() > 0:
            add(('money_points_bump',), money_bump(B0, y, v, g2, t2), 0.0)
            if o is not None: add(('money_opportunity_bump',), money_bump(B0, o, ohat, g2, t2), 0.0)
    return {k: float(np.mean(x)) for k, x in acc.items()}


def corrected(res, ln):
    """Subtract the lean from each estimate and both ends of its ranges; re-test whether the 95% range excludes zero."""
    for k, l in ln.items():
        d = res
        for part in k: d = d[part]
        d['lean'] = l; d['estimate'] -= l
        d['range_90'] = [x - l for x in d['range_90']]; d['range_95'] = [x - l for x in d['range_95']]
        null = 1.0 if k[0] in ('points', 'opportunity') else 0.0
        d['excludes_zero_95'] = bool(d['range_95'][0] > null or d['range_95'][1] < null)
    return res


def main():
    ap = argparse.ArgumentParser()
    for k in ('nflverse', 'rosters', 'week1', 'schedules'): ap.add_argument('--' + k, required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--labels', action='store_true'); g.add_argument('--crash', action='store_true'); g.add_argument('--run', action='store_true')
    ap.add_argument('--runs', type=int, default=200)
    ap.add_argument('--dry', action='store_true', help='with --run: every outcome shuffled within position and season (tests the code, reveals nothing)')
    a = ap.parse_args()
    st, S, pre, nn2, W2, nn3, W3, counts = O.setup(a.nflverse, a.rosters, a.week1)
    Rv = pd.read_csv(ROWS); Rv = Rv[Rv.relevant & (Rv.season >= E.TEST[0]) & (Rv.season <= E.TEST[1])]
    keep = set(zip(Rv.gsis_id, Rv.season.astype(int)))
    M = np.array([i for i in range(len(S)) if S.kind.values[i] == 'V' and S.complete.values[i]
                  and (S.key.values[i], int(S.t.values[i])) in keep], int)
    L = labels(S, M, a.schedules, a.week1, a.nflverse)
    L['name'] = S.name.values[M]; L['pos'] = S.pos.values[M]; L['t'] = S.t.values[M]
    info = {'relevant_rows': len(keep), 'measured_rows': int(len(M)), 'groups': L.group.astype(str).value_counts().to_dict(),
            'team_signed_by_group': L[L.team_signed].group.astype(str).value_counts().to_dict(),
            'kinds': L.kind.astype(str).value_counts().to_dict(), 'money_rows': int(L.money.notna().sum()),
            'unsourced_used': int((~L.sourced & L.kind.notna()).sum())}
    print(json.dumps(info, indent=1, default=int), flush=True)
    if a.labels:
        L[L.group == 'gap'][['gsis_id', 'name', 'pos', 't', 'n']].to_csv(os.path.join(OUT, 'contract_security_gaps.csv'), index=False)
        L.drop(columns=['row']).to_csv(os.path.join(OUT, 'contract_security_labels.csv'), index=False)
        json.dump(info, open(os.path.join(OUT, 'contract_security_counts.json'), 'w'), indent=1, default=int)
        return
    # decided rows: team-signed deals with a years-left group
    dec = L.team_signed.values & L.group.isin(GROUPS).values
    rows = M[dec]; grp = L.group.values[dec].astype(int)
    rows_v, nn_, W_ = SC.base_value(S, rows)
    assert len(rows_v) == len(rows), 'base value missing for some decided rows'
    y = S.FV.values.astype(float)
    def scramble(x):
        x = x.copy(); r = np.random.default_rng(7)
        for (_, _), ix in pd.DataFrame({'p': S.pos.values, 't': S.t.values}).groupby(['p', 't']).groups.items():
            ix = np.asarray(ix); x[ix] = x[r.permutation(ix)]
        return x
    if a.dry: y = scramble(y)
    v = E.preds(nn_, W_, y); yd = y[rows]
    pid = S.key.values[rows]; pos = S.pos.values[rows]; t = S.t.values[rows].astype(int)
    money = L.money.values[dec].astype(float); tier = np.full(len(rows), -1)
    for p in np.unique(pos):                                              # thirds within position, contract data only
        mp = (pos == p) & ~np.isnan(money)
        if mp.sum() >= 3:
            q1, q2 = np.quantile(money[mp], [1 / 3, 2 / 3]); tier[mp] = np.where(money[mp] <= q1, 0, np.where(money[mp] <= q2, 1, 2))
    rng = np.random.default_rng(SEED)
    if a.crash:
        res = {'decided_rows': int(len(rows)), 'runs': a.runs}
        for b in (0.0, 0.10, 0.05):
            hit = raw_hit = 0; est = []; raw = []
            for _ in range(a.runs):
                sh, _t = shuffled(grp, None, pos, t, rng)                 # removes any real link
                ys = yd * np.where(sh == 0, 1 - b, np.where(sh == 2, 1 + b, 1.0))
                r = measure(pid, pos, ys, v, None, None, sh, None, rng, n_boot=1000, opp=False)
                raw_hit += r['points_bump']['excludes_zero_95']; raw.append(r['points_bump']['estimate'])
                ln = lean(pid, pos, t, ys, v, None, None, sh, None, rng)
                r = corrected(r, {('points_bump',): ln[('points_bump',)]})['points_bump']
                hit += r['excludes_zero_95']; est.append(r['estimate'])
            res[f'planted_{b}'] = {'excluded_zero': int(hit), 'mean_estimate': float(np.mean(est)),
                                   'uncorrected_excluded_zero': int(raw_hit), 'uncorrected_mean_estimate': float(np.mean(raw))}
            print(b, res[f'planted_{b}'], flush=True)
        res['pass'] = bool(res['planted_0.0']['excluded_zero'] <= 15 and res['planted_0.1']['excluded_zero'] >= 0.8 * a.runs
                           and abs(res['planted_0.1']['mean_estimate'] - 0.10) <= 0.02)
        json.dump(res, open(os.path.join(OUT, 'ovs_contract_security_crash.json'), 'w'), indent=1)
        print('crash pass', res['pass']); return
    # --- the one real run ---
    car, tgt, starts = opportunity(a.nflverse, a.schedules)
    o_all = opp_vector(S, car, tgt, starts)
    if a.dry: o_all = scramble(o_all)
    od = o_all[rows]; ohat = E.preds(nn_, W_, o_all)
    res = {'decided_rows': int(len(rows)), 'by_group': {int(g): int((grp == g).sum()) for g in GROUPS},
           'money_rows': int((tier >= 0).sum())}
    res['decided'] = corrected(measure(pid, pos, yd, v, od, ohat, grp, tier, rng), lean(pid, pos, t, yd, v, od, ohat, grp, tier, rng))
    pb, ob = res['decided']['points_bump'], res['decided']['opportunity_bump']
    harm = no_harm(t, yd, v, grp, np.ones(len(rows), bool))
    res['no_harm_lift'] = harm
    use = pb['excludes_zero_95'] and np.sign(ob['estimate']) == np.sign(pb['estimate']) and harm >= GUARD
    res['status_layer_used'] = bool(use)
    res['status_layer'] = {f'group_{g}': 1 + shrink(res['decided']['points'][f'group_{g}']['estimate'] - 1,
                                                       res['decided']['points'][f'group_{g}']['se']) for g in GROUPS} if use else None
    if 'money_points_bump' in res['decided']:
        mp, mo = res['decided']['money_points_bump'], res['decided']['money_opportunity_bump']
        muse = use and mp['excludes_zero_95'] and np.sign(mo['estimate']) == np.sign(mp['estimate'])
        res['money_layer_used'] = bool(muse)
        res['money_layer_bump'] = shrink(mp['estimate'], mp['se']) if muse else None
    # reported, deciding nothing
    rep = {}
    by = {}
    for p in np.unique(pos):
        mp_ = pos == p
        by[p] = measure(pid[mp_], pos[mp_], yd[mp_], v[mp_], od[mp_], ohat[mp_], grp[mp_], None, rng, n_boot=1000)
    rep['by_position'] = by
    srcd = L.sourced.values[dec]
    rep['without_unsourced'] = measure(pid[srcd], pos[srcd], yd[srcd], v[srcd], od[srcd], ohat[srcd], grp[srcd], None, rng, n_boot=1000)
    rk = (~L.team_signed.values) & L.group.isin(GROUPS).values           # rookie deals
    rrows = M[rk]; rr, nnr, Wr = SC.base_value(S, rrows); assert len(rr) == len(rrows)
    rep['rookie_deals'] = measure(S.key.values[rrows], S.pos.values[rrows], y[rrows], E.preds(nnr, Wr, y), o_all[rrows],
                                  E.preds(nnr, Wr, o_all), L.group.values[rk].astype(int), None, rng, n_boot=1000)
    rep['rookie_deals']['rows'] = int(len(rrows))
    un = M[(L.group == 'unsigned').values]
    if len(un):
        ur, nnu, Wu = SC.base_value(S, un)
        rep['unsigned'] = {'rows': int(len(ur)), 'points_ratio': float(y[ur].sum() / E.preds(nnu, Wu, y).sum()),
                           'opportunity_ratio': float(o_all[ur].sum() / max(E.preds(nnu, Wu, o_all).sum(), 1e-9))}
    res['reported'] = rep
    json.dump(res, open(os.path.join(OUT, 'ovs_contract_security_' + ('dry' if a.dry else 'results') + '.json'), 'w'), indent=1, default=float)
    print(json.dumps({k: res[k] for k in ('decided_rows', 'by_group', 'no_harm_lift', 'status_layer_used', 'status_layer')}, indent=1, default=float))


if __name__ == '__main__':
    main()
