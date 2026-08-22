#!/usr/bin/env python3
"""
DELTA — RB DOMINATOR WEIGHT STUDY

Implements docs/PREREG-rb-dominator-weight.md exactly. Read that first; this file is the
execution, not the design, and where the two disagree the pre-registration wins.

The question is ONLY the weight w in:

    dDOM_RB(w) = [ w * rdom + (1 - w) * dom ] * competition_multiplier(tpct)

Whether receiving belongs in at all is settled and is not on trial (prereg section 1).
If no weight can be distinguished from another, the answer is 0.50 — never a return to
rushing-only.

Usage:
    python rb_dominator_weight_study.py
    python rb_dominator_weight_study.py --inspect     # sample composition only, no result
"""
import json, math, random, sys, os

# ── pre-registered constants (prereg sections 5, 6, 7) ───────────────────────
GRID = [i / 10 for i in range(11)]        # 0.00 .. 1.00, coarse on purpose
DEFAULT_W = 0.50                          # the un-tuned fallback
CV_FOLDS, CV_REPEATS = 5, 200
POWER_MAX_CI = 0.12                       # wider than this => underpowered
GATE_VS_DEFAULT = 0.75                    # challenger must beat 0.50 this often
GATE_VS_CURRENT = 0.60                    # selected must beat 1.00 this often
SPLITS = 500
DDOM_SWING = 0.50                         # unchanged, NOT under test

SEASONS = [2020, 2021, 2022, 2023, 2024, 2025]
LAST_PRIMARY_SEASON = 2024                # 2025 -> draft class 2026, unresolved


def mult(t):
    if t is None: return 1.0
    return max(1 - DDOM_SWING, min(1 + DDOM_SWING, 1 + DDOM_SWING * (t - 0.5) * 2))


def blend(r, w):
    return (w * r['rdom'] + (1 - w) * r['dom']) * mult(r.get('tpct'))


# ── rank statistics ──────────────────────────────────────────────────────────
def _ranks(v):
    idx = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v); i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and v[idx[j + 1]] == v[idx[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[idx[k]] = avg
        i = j + 1
    return r


def spearman(x, y):
    n = len(x)
    if n < 3: return 0.0
    rx, ry = _ranks(x), _ranks(y)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else 0.0


def score(rows, w):
    return spearman([blend(r, w) for r in rows], [r['outcome'] for r in rows])


# ── selection procedure (prereg section 6) ───────────────────────────────────
def select_weight(rows, repeats=CV_REPEATS, seed=17):
    """Repeated k-fold CV, then the one-standard-error rule with ties broken toward 0.50.
    Returns everything needed to report, not just the winner."""
    rng = random.Random(seed)
    per_w = {w: [] for w in GRID}
    n = len(rows)
    for _ in range(repeats):
        idx = list(range(n)); rng.shuffle(idx)
        folds = [idx[i::CV_FOLDS] for i in range(CV_FOLDS)]
        for f in folds:
            test = [rows[i] for i in f]
            if len(test) < 5: continue
            for w in GRID:
                per_w[w].append(score(test, w))
    means, ses = {}, {}
    for w in GRID:
        v = per_w[w]
        if not v:
            means[w], ses[w] = 0.0, 0.0; continue
        m = sum(v) / len(v)
        var = sum((x - m) ** 2 for x in v) / max(1, len(v) - 1)
        means[w] = m
        # AMENDMENT 1 (see prereg section 10). The standard error here must express how
        # uncertain the GENERALISATION estimate is, which is a property of the sample and
        # the fold count — NOT of how many times we chose to repeat the CV. Dividing by
        # the total number of fold-scores let SE shrink toward zero as repeats rose,
        # which narrowed the 1-SE band to nothing and silently turned the rule back into
        # "take the peak" — the exact behaviour it exists to prevent. Caught by the
        # self-test on pure noise. Correct form is the classic Breiman 1-SE: spread
        # across the k folds, divided by sqrt(k), independent of repeat count.
        ses[w] = math.sqrt(var / CV_FOLDS)
    w_star = max(GRID, key=lambda w: means[w])
    thresh = means[w_star] - ses[w_star]
    within = [w for w in GRID if means[w] >= thresh]
    selected = min(within, key=lambda w: (abs(w - DEFAULT_W), w))

    # AMENDMENT 2 (see prereg section 10). TWO bootstrap checks, not one.
    #
    # The original single check was the CI width on rho at w=0.50, read as a power
    # measure. That is wrong: on data with NO relationship at all, rho is reliably ~0 and
    # its CI is narrow, so pure noise scored as WELL POWERED. The self-test caught it.
    #
    #   SIGNAL check        — does the metric relate to the outcome at all? CI on rho at
    #                         0.50 must exclude zero. If it does not, nothing here is
    #                         measuring anything and no weight should be inferred.
    #   DISCRIMINATION check — can the sample tell weights apart? CI on the DIFFERENCE
    #                         rho(w*) - rho(0.50) must exclude zero. If it does not, the
    #                         curve is flat within noise and 0.50 ships as un-tuned.
    boot_def, boot_diff = [], []
    rb = random.Random(seed + 1)
    for _ in range(400):
        samp = [rows[rb.randrange(n)] for _ in range(n)]
        d = score(samp, DEFAULT_W)
        boot_def.append(d)
        boot_diff.append(score(samp, w_star) - d)
    boot_def.sort(); boot_diff.sort()
    lo, hi = boot_def[10], boot_def[389]
    dlo, dhi = boot_diff[10], boot_diff[389]
    has_signal = not (lo <= 0.0 <= hi)
    # AMENDMENT 3 (see prereg section 10). The discrimination check exists to stop a
    # CHALLENGER weight being adopted on noise. When the empirical best IS the default,
    # there is no challenger: rho(w*) - rho(0.50) is identically zero, the CI collapses to
    # [0,0], and a naive reading calls that a FAILURE — reporting an underpowered study
    # when in fact the data agreed with the default. Not applicable is the correct verdict.
    discrim_na = abs(w_star - DEFAULT_W) < 1e-9
    can_discriminate = True if discrim_na else not (dlo <= 0.0 <= dhi)
    if not (has_signal and can_discriminate):
        selected = DEFAULT_W        # no signal, or a flat curve -> un-tuned default
    return {'selected': selected, 'w_star': w_star, 'means': means, 'ses': ses,
            'within': within, 'ci_lo': lo, 'ci_hi': hi, 'ci_width': (hi - lo) / 2,
            'diff_lo': dlo, 'diff_hi': dhi, 'discrim_na': discrim_na,
            'has_signal': has_signal, 'can_discriminate': can_discriminate}


def beat_rate(rows, w_a, w_b, splits=SPLITS, seed=23):
    """How often does w_a beat w_b on a held-out half?"""
    rng = random.Random(seed); wins = 0; n = len(rows)
    for _ in range(splits):
        idx = list(range(n)); rng.shuffle(idx)
        te = [rows[i] for i in idx[n // 2:]]
        if score(te, w_a) > score(te, w_b): wins += 1
    return wins / splits


# ── data assembly (prereg sections 3, 4) ─────────────────────────────────────
def norm(s):
    import unicodedata
    if not s: return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return "".join(c for c in s.lower() if c.isalnum())


def qualifies(p):
    return (p.get('gms') or 0) >= 6 and (p.get('car') or 0) >= 60


def load_rows():
    picks_path = 'data/draft-picks.json'
    if not os.path.exists(picks_path):
        print("ERROR: data/draft-picks.json not found. Run the Fetch Draft Picks workflow first.")
        sys.exit(1)
    picks = json.load(open(picks_path))['picks']
    byname = {}
    for v in picks.values():
        byname.setdefault(norm(v['name']), []).append(v)

    seen = {}
    for y in SEASONS:
        f = f'data/college-players-{y}.json'
        if not os.path.exists(f): continue
        for p in json.load(open(f))['players']:
            if p['pos'] == 'RB' and qualifies(p):
                seen.setdefault(p['n'], {})[y] = p
    finals = {n: max(v) for n, v in seen.items()}

    rows, drop = [], {'season2025': 0, 'missing': 0}
    for name, y in finals.items():
        if y > LAST_PRIMARY_SEASON:
            drop['season2025'] += 1; continue
        p = seen[name][y]
        if p.get('rdom') is None or p.get('dom') is None:
            drop['missing'] += 1; continue
        hits = [h for h in byname.get(norm(name), []) if h['year'] in (y + 1, y + 2)]
        if hits:
            overall = min(h['overall'] or 999 for h in hits)
            outcome = -overall            # earlier pick = better
            drafted = True
        else:
            outcome = -999                # all undrafted tied at the bottom
            drafted = False
        rows.append({'n': name, 'finalYr': y, 'rdom': p['rdom'], 'dom': p['dom'],
                     'tpct': p.get('tpct'), 'outcome': outcome, 'drafted': drafted,
                     'car': p.get('car'), 'ry': p.get('ry'), 'rec': p.get('rec'),
                     'rey': p.get('rey'), 'gms': p.get('gms')})
    return rows, drop, finals


def main():
    print("=" * 74)
    print("DELTA — RB DOMINATOR WEIGHT STUDY")
    print("Implements docs/PREREG-rb-dominator-weight.md. Primary outcome: draft capital.")
    print("=" * 74)

    rows, drop, finals = load_rows()
    n_draft = sum(1 for r in rows if r['drafted'])
    print(f"\nSAMPLE (prereg section 3)")
    print(f"  distinct RBs with a qualifying final season : {len(finals)}")
    print(f"  dropped, final season 2025 (class 2026)     : {drop['season2025']}")
    print(f"  dropped, missing rdom or dom                : {drop['missing']}")
    print(f"  PRIMARY SAMPLE                              : {len(rows)}")
    print(f"     drafted   : {n_draft}")
    print(f"     undrafted : {len(rows) - n_draft}  (retained on purpose — dropping them")
    print(f"                 would condition on the outcome)")
    byyr = {}
    for r in rows: byyr[r['finalYr']] = byyr.get(r['finalYr'], 0) + 1
    print(f"  by final college season: " + ", ".join(f"{k}:{v}" for k, v in sorted(byyr.items())))

    if '--inspect' in sys.argv:
        print("\n--inspect: stopping before any result, as requested.")
        return

    res = select_weight(rows)

    print(f"\nCV CURVE (prereg section 6) — held-out Spearman rho by weight")
    print(f"  {'w (rush share)':>16}  {'mean rho':>9}  {'SE':>6}")
    for w in GRID:
        star = '  <- best' if w == res['w_star'] else ''
        inb = ' *' if w in res['within'] else '  '
        print(f"  {w:>16.2f}  {res['means'][w]:>9.4f}  {res['ses'][w]:>6.4f}{inb}{star}")
    print("  * = within 1 SE of the best")

    print(f"\nPOWER CHECKS (prereg section 7, as amended)")
    print(f"  signal        : rho at w=0.50 CI [{res['ci_lo']:.3f}, {res['ci_hi']:.3f}]"
          f"  -> {'PASS (excludes 0)' if res['has_signal'] else 'FAIL (includes 0)'}")
    if res['discrim_na']:
        print(f"  discrimination: NOT APPLICABLE — the empirical best weight IS the")
        print(f"                  default 0.50, so there is no challenger to test.")
    else:
        print(f"  discrimination: rho(w*) - rho(0.50) CI [{res['diff_lo']:+.3f}, {res['diff_hi']:+.3f}]"
              f"  -> {'PASS (excludes 0)' if res['can_discriminate'] else 'FAIL (includes 0)'}")
    powered = res['has_signal'] and res['can_discriminate']

    selected = res['selected']
    if not powered:
        print(f"  UNDERPOWERED: shipping w = {DEFAULT_W:.2f} as an explicitly un-tuned default.")
        print(f"  The weight question stays OPEN pending a larger sample.")
        selected = DEFAULT_W
    elif res['discrim_na']:
        print(f"  selection rule -> w = {selected:.2f}  (the empirical best and the")
        print(f"  pre-registered default are the same weight — the data agreed with it)")
    else:
        print(f"  selection rule -> w = {selected:.2f}"
              f"  (best was {res['w_star']:.2f}; 1-SE rule + tie-break toward {DEFAULT_W:.2f})")

    print(f"\nGATES (prereg section 7)")
    vs_current = beat_rate(rows, selected, 1.00)
    print(f"  sanity gate: w={selected:.2f} beats today's w=1.00 on "
          f"{vs_current:.0%} of {SPLITS} half-splits (need >= {GATE_VS_CURRENT:.0%})"
          f"  -> {'PASS' if vs_current >= GATE_VS_CURRENT else 'FAIL'}")
    if abs(selected - DEFAULT_W) > 1e-9:
        vs_default = beat_rate(rows, selected, DEFAULT_W)
        print(f"  challenger gate: w={selected:.2f} beats w=0.50 on {vs_default:.0%} "
              f"(need >= {GATE_VS_DEFAULT:.0%}) -> {'PASS' if vs_default >= GATE_VS_DEFAULT else 'FAIL'}")
        if vs_default < GATE_VS_DEFAULT:
            print(f"  -> challenger failed. Shipping w = {DEFAULT_W:.2f}.")
            selected = DEFAULT_W
    else:
        print(f"  challenger gate: not applicable, selection IS the default 0.50")

    if vs_current < GATE_VS_CURRENT:
        print("\n  SANITY GATE FAILED. Nothing ships. This points at the join or the")
        print("  outcome, not at the question — investigate before rerunning.")
        print("=" * 74); return

    print(f"\nSECONDARY OUTCOME (reported regardless — prereg section 4)")
    try:
        sec = load_secondary(rows)
        if len(sec) >= 20:
            print(f"  n = {len(sec)} with real NFL games")
            for w in sorted({1.00, DEFAULT_W, selected}):
                tag = '  (today)' if w == 1.00 else ('  (selected)' if abs(w-selected)<1e-9 else '')
                print(f"     w={w:.2f}: rho = {score(sec, w):+.3f}{tag}")
            agree = score(sec, selected) > score(sec, 1.00)
            print(f"  agrees with primary: {'yes' if agree else 'NO — reported as a disagreement'}")
        else:
            print(f"  n = {len(sec)} — too small to report meaningfully.")
    except Exception as e:
        print(f"  secondary outcome unavailable: {e}")

    print(f"\nBIGGEST MOVERS under w = {selected:.2f} vs today's 1.00")
    show_movers(rows, selected)

    print("\n" + "=" * 74)
    print(f"RESULT: ship w = {selected:.2f}")
    print(f"  dDOM_RB = [{selected:.2f} * rushDom + {1-selected:.2f} * recDom] * competition")
    print("=" * 74)


def load_secondary(rows):
    """Best real NFL season PPG, for the subset that reached the league."""
    ps_path = 'data/player-stats.json'
    if not os.path.exists(ps_path): raise FileNotFoundError('data/player-stats.json')
    ps = json.load(open(ps_path))['players']
    out = []
    for r in rows:
        e = ps.get(r['n'])
        if not e: continue
        best = None
        for y in ('2023', '2024', '2025'):
            s = e.get(y)
            if not s or (s.get('games') or 0) < 4:
                continue
            # player-stats.json carries no points column — the engine derives PPG from the
            # raw lines in loadPlayerStats(). Mirrored here EXACTLY, at the half_tep basis
            # (0.5/reception, no TE premium since every row is an RB), so this study and
            # the site agree on what a player scored.
            ppg = (
                (s.get('rec')      or 0) * 0.5 +
                (s.get('rec_yds')  or 0) * 0.1 +
                (s.get('rec_td')   or 0) * 6 +
                (s.get('rush_yds') or 0) * 0.1 +
                (s.get('rush_td')  or 0) * 6 +
                (s.get('pass_yds') or 0) * 0.04 +
                (s.get('pass_td')  or 0) * 4 -
                (s.get('pass_int') or 0) * 2
            ) / s['games']
            if ppg > 0:
                best = ppg if best is None else max(best, ppg)
        if best:
            q = dict(r); q['outcome'] = best; out.append(q)
    return out


def show_movers(rows, w):
    def pcts(weight):
        v = [blend(r, weight) for r in rows]
        s = sorted(v)
        return [round(100 * sum(1 for x in s if x < a) / (len(s) - 1)) for a in v]
    a, b = pcts(1.00), pcts(w)
    moves = sorted(zip([x - y for x, y in zip(b, a)], [r['n'] for r in rows], a, b))
    print("  falls:")
    for m in moves[:5]: print(f"     {m[1][:24]:24} {m[2]:>3} -> {m[3]:>3}  ({m[0]:+d})")
    print("  rises:")
    for m in moves[-5:]: print(f"     {m[1][:24]:24} {m[2]:>3} -> {m[3]:>3}  ({m[0]:+d})")
    big = sum(1 for m in moves if abs(m[0]) >= 10)
    print(f"  {big} of {len(rows)} move 10+ percentile points ({round(100*big/len(rows))}%)")


if __name__ == '__main__':
    main()
