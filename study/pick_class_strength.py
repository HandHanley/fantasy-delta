#!/usr/bin/env python3
"""
DELTA — CAN COLLEGE PRODUCTION PRICE A ROOKIE CLASS BEFORE THE NFL DRAFT? Implements docs/PREREG-pick-class-strength.md
(Project: claude/PREREG-pick-class-strength.md); where they disagree, the pre-registration wins.

PICKS AND OUTCOMES are Stage 1's, built by the same code (pick_values_now / pick_values_sf): the superflex rookie-draft
order, classes 2014-2023, slots 1-36, FV3 = value over a rookie's first three seasons, full PPR, the adopted lines.
The run asserts it reproduces Stage 1's saved curve before doing anything else.

COLLEGE SCORE (per drafted player; no NFL data):
  - final college season = the last of the three before his class with at least 4 games (rule 1);
  - position = his NFL draft record's (rule 6), so Curtis Samuel is ranked as a WR;
  - two percentiles against a FIXED pool per season and position, the top 70 / 110 / 160 / 70 by production among
    players with 4+ games (rule 2; the live files' cut, so the wider backfill files don't make an era look stronger):
      share of team production, computed as the site's college card computes it (cfbAdjVal in
      scripts/build-college-index.js: WR/TE receiving dominator, RB 50/50 rushing and receiving, QB ANY/A, each times
      the team-talent multiplier), and raw production (receiving + rushing yards + 0.4 x passing yards);
  - score = the average of the two (0-100). No per-play value (rule 5, Steve 13 Nov: CFBD leaves rescued players out).
  - 2013 and 2014 have no team-talent feed; each team takes its 2015 talent percentile (PROPOSED, for Steve's OK).
  - Small-school players and anyone unmatched have no score; they are left out of their group's average (rule 3).

CLASS STRENGTH: for pick group g (Early/Mid/Late of each round) in class c, the average score of c's matched picks in
g minus the average of g's matched picks in every other class. Groups with no matched pick read 0.

THE TEST: prediction without college = the isotonic slot curve fitted on the other classes; with college = that x
(1 + beta x strength / SD), beta fitted on the other classes by least squares. Strictly held out: a class's prediction
uses no fit that saw its outcomes, including the base predictions beta is fitted on (curves leave out both classes).
Passes on RMSE >= 2% better over all picks AND permutation p < 0.05 (strength vectors shuffled between whole classes).

    python pick_class_strength.py --nflverse DIR --rosters DIR --matches   # who matched what (no outcomes read)
    python pick_class_strength.py --nflverse DIR --rosters DIR --crash     # crash tests, before lock
    python pick_class_strength.py --nflverse DIR --rosters DIR --power     # planted slope + catch rate by effect size
    python pick_class_strength.py --nflverse DIR --rosters DIR --confirm   # the real run, once, after lock
"""
import argparse, itertools, json, os, re, sys, unicodedata
from pathlib import Path
import numpy as np
import pandas as pd
import comps_value_study as C
import pick_values_now as PVN
import pick_values_sf as SF

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / 'out'
CLASSES = PVN.CLASSES
GROUPS = PVN.NAMES                                  # 9 groups: (name, first slot, last slot)
POOL_N = {'QB': 70, 'RB': 110, 'WR': 160, 'TE': 70}
MIN_GAMES = 4
DDOM_SWING, RB_RUSH_W = 0.50, 0.50                  # scripts/build-college-index.js, unchanged
BAR, ALPHA = 0.02, 0.05
BETA_PLANT = 0.25                                   # planted world: one SD stronger -> 25% more
N_NOISE, N_PLANT, N_PERM_CRASH, N_PERM_REAL = 20, 200, 500, 2000
SEED = 20261113
# Names spelled differently between the draft record / ADP board and CFBD (13 Nov coverage check). Printed in full by
# --matches; anything else unmatched is listed there before any run.
ALIAS = {
    'willfuller': ['willfullerv'], 'leonteecaroo': ['leontecarroo'], 'josephwilliams': ['joewilliams'],
    'hollywoodbrown': ['marquisebrown'], 'kennygainwell': ['kennethgainwell'], 'isiahpacheco': ['isaihpacheco'],
    'tankdell': ['nathanieldell'],
}


def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')); s = ''.join(c for c in s if not unicodedata.combining(c))
    k = ''.join(c for c in s.lower() if c.isalnum())
    for suf in ('jr', 'sr', 'iii', 'ii', 'iv'):
        if k.endswith(suf) and len(k) > len(suf) + 3: return k[:-len(suf)]
    return k


def school_key(s):
    s = str(s or '').lower().replace('&', 'and')
    s = re.sub(r'\bst\.?$', 'state', s.strip()); s = re.sub(r'\bst\.? ', 'state ', s)
    return re.sub(r'[^a-z]', '', s)


# ── college side ─────────────────────────────────────────────────────────────────────────────────────
def season_file(y):
    p = HERE / 'data' / 'college-history' / f'college-players-{y}.json' if y < 2020 else ROOT / 'data' / f'college-players-{y}.json'
    return json.load(open(p))['players']


def mult(t):
    return 1.0 if t is None else max(1 - DDOM_SWING, min(1 + DDOM_SWING, 1 + DDOM_SWING * (t - 0.5) * 2))


def adj_val(p, pos):
    m = mult(p.get('tpct'))
    if pos == 'QB': return None if p.get('anya') is None else p['anya'] * m
    if pos == 'RB':
        if p.get('rdom') is None and p.get('dom') is None: return None
        return (RB_RUSH_W * (p.get('rdom') or 0) + (1 - RB_RUSH_W) * (p.get('dom') or 0)) * m
    return None if p.get('dom') is None else p['dom'] * m


def prod(p):
    return (p.get('rey') or 0) + (p.get('ry') or 0) + 0.4 * (p.get('py') or 0)


def pct(peers, v):
    """Same form as pctOf() in build-college-index.js, but placed against the pool (v need not be in it)."""
    if v is None or len(peers) < 2: return None
    return min(100.0, 100.0 * sum(1 for x in peers if x < v) / (len(peers) - 1))


def college_seasons():
    seasons = {y: season_file(y) for y in range(2013, 2023)}
    t15 = {}
    for p in seasons[2015]:
        if p.get('tpct') is not None: t15.setdefault(p['tm'], p['tpct'])
    carried = {}
    for y in (2013, 2014):
        n = 0
        for p in seasons[y]:
            if p.get('tpct') is None and p['tm'] in t15: p['tpct'] = t15[p['tm']]; n += 1
        carried[y] = n
    pools = {}
    for y, P in seasons.items():
        for pos, n in POOL_N.items():
            pool = sorted([p for p in P if p['pos'] == pos and (p.get('gms') or 0) >= MIN_GAMES], key=lambda p: -prod(p))[:n]
            pools[(y, pos)] = {'adj': [v for v in (adj_val(p, pos) for p in pool) if v is not None],
                               'prod': [prod(p) for p in pool]}
    index = {}
    for y, P in seasons.items():
        for p in P: index.setdefault((y, norm(p['n'])), []).append(p)
    return seasons, pools, index, carried


def college_score(row, pools):
    y, pos, p = row['season'], row['pos'], row['p']
    a = pct(pools[(y, pos)]['adj'], adj_val(p, pos)); b = pct(pools[(y, pos)]['prod'], prod(p))
    got = [v for v in (a, b) if v is not None]
    return (sum(got) / len(got) if got else None), a, b


def match(picks, dp, index, pools):
    """Each pick -> its final college season row (or a reason it has none). No outcome is read here."""
    by_gsis = dp.dropna(subset=['gsis_id']).drop_duplicates('gsis_id').set_index('gsis_id')
    out = []
    for i, r in picks.iterrows():
        d = by_gsis.loc[r.gsis] if r.gsis in by_gsis.index else None
        pos = d.position if d is not None and d.position in POS_SET else r.pos
        keys = {norm(r['name'])}
        if d is not None: keys.add(norm(d.pfr_player_name))
        for k in list(keys): keys.update(ALIAS.get(k, []))
        school = school_key(d.college) if d is not None else ''
        found, why = None, 'not found in any of the three seasons before the class'
        for y in (r.cls - 1, r.cls - 2, r.cls - 3):
            if y < 2013: continue
            cand = [p for k in keys for p in index.get((y, k), [])]
            cand = [p for p in cand if (p.get('gms') or 0) >= MIN_GAMES]
            if not cand: continue
            if len(cand) > 1 and school:
                same = [p for p in cand if school_key(p['tm']) == school or school_key(p['tm']).startswith(school[:6])]
                cand = same or cand
            cand.sort(key=lambda p: -(p.get('gms') or 0))
            found = {'season': y, 'pos': pos, 'p': cand[0]}; break
        row = {'i': i, 'cls': int(r.cls), 'slot': int(r.slot), 'name': r['name'], 'draft_pos': pos,
               'college': None if d is None else d.college, 'season': None, 'score': None}
        if found:
            s, a, b = college_score(found, pools)
            row.update(season=found['season'], cfbd_name=found['p']['n'], team=found['p']['tm'], college_pos=found['p']['pos'],
                       games=found['p'].get('gms'), rescued=bool(found['p'].get('rescued')), score=s, share_pct=a, prod_pct=b,
                       final=found['season'] == r.cls - 1)
        else:
            row['why'] = why
        out.append(row)
    return out


POS_SET = {'QB', 'RB', 'WR', 'TE'}


# ── Stage 1's picks and outcomes, built by Stage 1's own code ─────────────────────────────────────────
def stage1(nflverse, rosters):
    B, ff, dp, ids = SF.board()
    b_fit = json.load(open(OUT / 'pick_values_sf_fit.json'))['boost']; assert b_fit == 1.9
    one = SF.build(SF.one_qb(PVN.FMT), nflverse, rosters, B)
    sf = SF.build(PVN.FMT, nflverse, rosters, B)
    slot, E = SF.sf_order(B, one['yb'], {c: b_fit for c in SF.BOARD_CLASSES})
    st, _, _ = C.load(nflverse, rosters)
    assert np.allclose(st.P, st.fantasy_points.fillna(0) + st.receptions)
    m = ~np.isnan(slot) & np.isin(B.cls.values, CLASSES)
    rows = np.where(m)[0]
    lines = dict(C.REPL_N_FULL_ADOPTED); line = sf['line']
    y = np.array([PVN.fv3(st, lines, B.gsis.values[j], line[j], int(B.cls.values[j])) for j in rows])
    s = slot[rows].astype(int)
    fit, xs = PVN.isotonic_dec(s, y)
    saved = json.load(open(OUT / 'pick_values_now.json'))['stage1']['new_lines']['per_slot_curve_fv3']
    assert np.allclose(fit, saved, rtol=0, atol=1e-9), 'Stage 1 curve not reproduced'
    picks = pd.DataFrame({'cls': B.cls.values[rows].astype(int), 'slot': s, 'name': B.name.values[rows],
                          'pos': B.pos.values[rows], 'gsis': B.gsis.values[rows]})
    dpx = pd.read_csv(os.path.join(nflverse, 'draft_picks.csv'), low_memory=False)
    return picks, y, dpx


# ── the test ──────────────────────────────────────────────────────────────────────────────────────────
def group_of(slot):
    return next(k for k, (_, a, b) in enumerate(GROUPS) if a <= slot <= b)


def strengths(cls, grp, score):
    """(class, group) -> class strength. College scores only."""
    S = np.zeros((len(CLASSES), len(GROUPS)))
    ok = ~np.isnan(score)
    for ci, c in enumerate(CLASSES):
        for g in range(len(GROUPS)):
            mine = ok & (cls == c) & (grp == g); oth = ok & (cls != c) & (grp == g)
            if mine.any() and oth.any(): S[ci, g] = score[mine].mean() - score[oth].mean()
    return S


def base_tables(cls, slot, y):
    """Isotonic slot curves with classes left out. base1[i] leaves out i's class; base2[c][i] leaves out c and i's."""
    def curve(mask):
        f, xs = PVN.isotonic_dec(slot[mask], y[mask])
        return np.interp(np.arange(1, 37), xs, f)
    ci = np.array([CLASSES.index(c) for c in cls])
    base1 = np.empty(len(y))
    for k, c in enumerate(CLASSES):
        cv = curve(cls != c); base1[ci == k] = cv[slot[ci == k] - 1]
    base2 = {}
    for a, b in itertools.combinations(range(len(CLASSES)), 2):
        cv = curve((ci != a) & (ci != b))
        base2[(a, b)] = base2[(b, a)] = cv
    return ci, base1, base2


def evaluate(ci, grp, slot, y, base1, base2, S):
    """RMSE gain of the college model over the slot curve, strictly held out. S: (class, group) strengths."""
    sd = S.std()
    if sd == 0: return 0.0
    z = S / sd
    pred = base1.copy()
    for k in range(len(CLASSES)):
        tr = ci != k
        b = np.empty(tr.sum()); idx = np.where(tr)[0]
        for kk in set(ci[idx]):
            sel = idx[ci[idx] == kk]; b[np.searchsorted(idx, sel)] = base2[(k, kk)][slot[sel] - 1]
        x = b * z[ci[idx], grp[idx]]
        den = (x * x).sum()
        beta = (x * (y[idx] - b)).sum() / den if den > 0 else 0.0
        te = ci == k
        pred[te] = np.maximum(0.0, base1[te] * (1 + beta * z[k, grp[te]]))
    r0 = np.sqrt(np.mean((y - base1) ** 2)); r1 = np.sqrt(np.mean((y - pred) ** 2))
    return 1 - r1 / r0


def run_test(ci, grp, slot, y, base1, base2, S, n_perm, rng):
    gain = evaluate(ci, grp, slot, y, base1, base2, S)
    hits = 0
    for _ in range(n_perm):
        Sp = S[rng.permutation(len(CLASSES))]
        if evaluate(ci, grp, slot, y, base1, base2, Sp) >= gain: hits += 1
    p = (1 + hits) / (1 + n_perm)
    return {'gain': float(gain), 'p': float(p), 'pass': bool(gain >= BAR and p < ALPHA)}


def planted_outcomes(ci, grp, y, S, rng):
    """Real outcomes resampled within each pick group (any class), so slot value and noise are real but any real
    college link is gone; then the planted effect: x (1 + 0.25 x strength / SD)."""
    z = S / S.std(); yp = np.empty_like(y)
    for g in range(len(GROUPS)):
        m = np.where(grp == g)[0]
        yp[m] = rng.choice(y[m], len(m)) * np.maximum(0.0, 1 + BETA_PLANT * z[ci[m], g])
    return yp


def main():
    global BETA_PLANT
    ap = argparse.ArgumentParser()
    ap.add_argument('--nflverse', required=True); ap.add_argument('--rosters', required=True)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--matches', action='store_true'); mode.add_argument('--crash', action='store_true')
    mode.add_argument('--confirm', action='store_true'); mode.add_argument('--power', action='store_true')
    a = ap.parse_args()
    picks, y, dpx = stage1(a.nflverse, a.rosters)
    seasons, pools, index, carried = college_seasons()
    M = match(picks, dpx, index, pools)
    score = np.array([np.nan if m['score'] is None else m['score'] for m in M])
    cls, slot = picks.cls.values, picks.slot.values
    grp = np.array([group_of(s) for s in slot])
    S = strengths(cls, grp, score)
    cover = {int(c): {'picks': int((cls == c).sum()), 'scored': int(((cls == c) & ~np.isnan(score)).sum())} for c in CLASSES}
    info = {'prereg': 'claude/PREREG-pick-class-strength.md', 'picks': int(len(y)), 'scored': int((~np.isnan(score)).sum()),
            'coverage_by_class': cover, 'talent_carried_back_from_2015': carried,
            'strength_sd': float(S.std()), 'strength_by_class_group': {int(c): [round(float(v), 2) for v in S[k]] for k, c in enumerate(CLASSES)}}
    if a.matches:
        rows = [{k: v for k, v in m.items() if k != 'i'} for m in M]
        json.dump({**info, 'matches': rows}, open(OUT / 'pick_class_strength_matches.json', 'w'), indent=1, default=float)
        print(json.dumps(info, indent=1, default=float))
        for m in M:
            if m['score'] is None: print('  NO SCORE', m['cls'], m['slot'], m['name'], m['draft_pos'], m['college'], '-', m.get('why'))
        for m in M:
            if m['score'] is not None and (not m['final'] or m['rescued'] or m['college_pos'] != m['draft_pos']):
                print('  NOTE', m['cls'], m['slot'], m['name'], '->', m['cfbd_name'], m['team'], m['season'],
                      'rescued' if m['rescued'] else '', f"college {m['college_pos']} / drafted {m['draft_pos']}")
        return
    ci, base1, base2 = base_tables(cls, slot, y)
    rng = np.random.default_rng(SEED)
    if a.crash:
        noise = []
        for _ in range(N_NOISE):
            perm = rng.permutation(len(CLASSES))
            while (perm == np.arange(len(CLASSES))).all(): perm = rng.permutation(len(CLASSES))
            noise.append(run_test(ci, grp, slot, y, base1, base2, S[perm], N_PERM_CRASH, rng))
        plant = []
        for k in range(N_PLANT):
            yp = planted_outcomes(ci, grp, y, S, rng)
            _, b1p, b2p = base_tables(cls, slot, yp)
            plant.append(run_test(ci, grp, slot, yp, b1p, b2p, S, N_PERM_CRASH, rng))
            if (k + 1) % 20 == 0: print(f'  planted {k + 1}/{N_PLANT}: passed {sum(x["pass"] for x in plant)}', flush=True)
        res = {**info, 'noise': {'runs': N_NOISE, 'passed': sum(x['pass'] for x in noise), 'allowed': 1,
                                 'ok': sum(x['pass'] for x in noise) <= 1, 'gains': [x['gain'] for x in noise]},
               'planted': {'runs': N_PLANT, 'beta': BETA_PLANT, 'passed': sum(x['pass'] for x in plant),
                           'needed': int(0.8 * N_PLANT), 'ok': sum(x['pass'] for x in plant) >= 0.8 * N_PLANT,
                           'median_gain': float(np.median([x['gain'] for x in plant])),
                           'share_gain_over_bar': float(np.mean([x['gain'] >= BAR for x in plant])),
                           'share_p_under_alpha': float(np.mean([x['p'] < ALPHA for x in plant]))}}
        json.dump(res, open(OUT / 'pick_class_strength_crash.json', 'w'), indent=1, default=float)
        print(json.dumps({k: res[k] for k in ('picks', 'scored', 'strength_sd', 'noise', 'planted')}, indent=1, default=float))
        return
    if a.power:
        # Is the planted effect really in the planted data? (slope of outcome / group average on strength, ~BETA)
        z = S / S.std(); sl = []
        for _ in range(200):
            yp = planted_outcomes(ci, grp, y, S, rng)
            r = np.array([yp[i] / yp[grp == grp[i]].mean() for i in range(len(yp))])
            sl.append(np.polyfit(z[ci, grp], r, 1)[0])
        res = {**info, 'planted_slope_at_0.25': float(np.mean(sl)), 'catch_rate': {}}
        for b in (0.25, 0.5, 0.75, 1.0):
            BETA_PLANT = b; got = []
            for _ in range(60):
                yp = planted_outcomes(ci, grp, y, S, rng); _, b1p, b2p = base_tables(cls, slot, yp)
                got.append(run_test(ci, grp, slot, yp, b1p, b2p, S, 200, rng))
            res['catch_rate'][str(b)] = {'pass': float(np.mean([x['pass'] for x in got])),
                                         'median_gain': float(np.median([x['gain'] for x in got])),
                                         'share_p_under_alpha': float(np.mean([x['p'] < ALPHA for x in got]))}
            print(b, res['catch_rate'][str(b)], flush=True)
        BETA_PLANT = 0.25
        json.dump(res, open(OUT / 'pick_class_strength_power.json', 'w'), indent=1, default=float)
        print('planted slope:', round(res['planted_slope_at_0.25'], 3))
        return
    sys.exit('--confirm runs only after the pre-registration is locked; not written yet.')


if __name__ == '__main__':
    main()
