#!/usr/bin/env python3
"""
DELTA research — SCARCITY CURVE DERIVATION (QB / WR / TE)

THE FINDING THAT PROMPTED THIS
------------------------------
delta-engine.js SCAR_CURVE has four positional value-by-rank curves. Exactly ONE
of them has provenance:

    RB: [...]   // multi-year production-derived (2026-06-28); was [...]
    QB: [...]   <- no comment
    WR: [...]   <- no comment
    TE: [...]   <- no comment

RB was upgraded to a data-derived curve. QB, WR and TE are still the original
HAND-TUNED numbers. The long-standing "QB-in-1QB over-discount" (DELTA craters QB
9-23% harder than the market) is most likely just that: the QB curve was never
derived from anything.

WHAT THIS SCRIPT DOES  (research only -- writes study/out/, never /data)
-----------------------------------------------------------------------
1. METHOD VALIDATION FIRST. We do NOT have the script that produced the RB curve.
   So rather than invent a method, we derive RB with a candidate method and check
   whether it REPRODUCES the committed RB curve. If it does, the method is
   validated and we can trust it on QB/WR/TE. If it does not, we do not proceed.
2. Derive QB/WR/TE curves at the SAME rank breakpoints (drop-in replacement).
3. Show the before/after impact on scarcity() across all 8 league settings.
4. Compare to the FantasyCalc yardstick -- as a MEASUREMENT, never a target.
   DELTA is market-blind: any narrowing of the QB gap is a byproduct, not a goal.
5. Sensitivity: seasons window, min-games floor, PPG vs total-points ranking.

SCORING is replicated EXACTLY from the engine's gamefp():
    py*0.04 + pt*4 + pi*-2 + ry*0.1 + rt*6 + rec*recAbs + rey*0.1 + ret*6 + fl*-2
    recAbs = 1.0 (TE: 0.5 PPR + 0.5 TE premium) | 0.5 (RB/WR) | 0 (QB)

Install:  pip install nflreadpy pandas numpy
Usage:    python derive_scarcity_curves.py [--seasons 2021-2025] [--min-games 6]
                                           [--rank-by ppg|total]
"""

import os
import sys
import json
import argparse
import urllib.request

import numpy as np
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("--seasons", default="2021-2025", help="derivation window")
ap.add_argument("--min-games", type=int, default=6)
ap.add_argument("--rank-by", default="ppg", choices=["ppg", "total"])
ap.add_argument("--inspect", action="store_true")
args = ap.parse_args()

lo, hi = (int(x) for x in args.seasons.split("-"))
SEASONS = list(range(lo, hi + 1))
OUT = "study/out"
os.makedirs(OUT, exist_ok=True)

# ---- the engine's current state (verbatim from delta-engine.js) ----
CURRENT = {
    "QB": [[1, 1.0], [6, 0.865], [9, 0.796], [12, 0.769], [15, 0.731], [18, 0.721], [22, 0.647], [26, 0.608], [32, 0.471]],
    "RB": [[1, 1.0], [6, 0.843], [12, 0.686], [19, 0.614], [26, 0.579], [34, 0.508]],   # <- the one that IS derived
    "WR": [[1, 1.0], [8, 0.705], [16, 0.588], [24, 0.537], [36, 0.473], [48, 0.362]],
    "TE": [[1, 1.0], [3, 0.788], [5, 0.667], [8, 0.605], [11, 0.582], [14, 0.563], [18, 0.507]],
}
SCAR_STARTERS = {"QB": {"1qb": 1.0, "sf": 1.8}, "RB": 2.4, "WR": 3.0, "TE": 1.1}
BREAKS = {p: [r for r, _ in c] for p, c in CURRENT.items()}


def hr(t=""):
    print("\n" + "=" * 78, flush=True)
    if t:
        print(t)
        print("-" * 78, flush=True)


def cv(curve, rank):
    """scarCurveVal() — replicated EXACTLY from the engine (linear interp between breakpoints)."""
    if rank <= curve[0][0]:
        return curve[0][1]
    for i in range(len(curve) - 1):
        if rank <= curve[i + 1][0]:
            r0, v0 = curve[i]
            r1, v1 = curve[i + 1]
            return v0 + (rank - r0) / (r1 - r0) * (v1 - v0)
    return curve[-1][1]


def starters(pos, qbfmt):
    return SCAR_STARTERS["QB"][qbfmt] if pos == "QB" else SCAR_STARTERS[pos]


def scarcity(curves, pos, teams, qbfmt):
    """scarcity() — replicated EXACTLY from the engine."""
    gap = 1 - cv(curves[pos], (teams or 12) * starters(pos, qbfmt))
    gapD = 1 - cv(curves[pos], 12 * starters(pos, "sf"))     # anchor: 12-team superflex
    return gap / gapD if gapD > 0 else 1.0


# ============================================================ LOAD + SCORE
hr(f"DERIVING SCARCITY CURVES FROM DELTA'S OWN PRODUCTION  ({SEASONS[0]}-{SEASONS[-1]})")

try:
    import nflreadpy as nfl
except ImportError:
    sys.exit("pip install nflreadpy pandas numpy")

d = nfl.load_player_stats(seasons=SEASONS)
d = d.to_pandas() if hasattr(d, "to_pandas") else pd.DataFrame(d)
print(f"loaded {len(d):,} weekly rows")


def find(f, *c, required=True):
    for x in c:
        if x in f.columns:
            return x
    low = {k.lower(): k for k in f.columns}
    for x in c:
        if x.lower() in low:
            return low[x.lower()]
    if required:
        print(f"FATAL: none of {c}. Available: {sorted(f.columns)[:60]}")
        sys.exit(1)
    return None


C = {
    "pid": find(d, "player_id", "gsis_id"),
    "name": find(d, "player_display_name", "player_name"),
    "pos": find(d, "position", "position_group"),
    "season": find(d, "season"),
    "stype": find(d, "season_type", required=False),
    "py": find(d, "passing_yards"),
    "pt": find(d, "passing_tds"),
    "pi": find(d, "passing_interceptions", "interceptions"),
    "ry": find(d, "rushing_yards"),
    "rt": find(d, "rushing_tds"),
    "rec": find(d, "receptions"),
    "rey": find(d, "receiving_yards"),
    "ret": find(d, "receiving_tds"),
}
for k, cands in [("fl_r", ("rushing_fumbles_lost",)), ("fl_c", ("receiving_fumbles_lost",)),
                 ("fl_s", ("sack_fumbles_lost",)), ("tp_p", ("passing_2pt_conversions",)),
                 ("tp_r", ("rushing_2pt_conversions",)), ("tp_c", ("receiving_2pt_conversions",))]:
    C[k] = find(d, *cands, required=False)

if args.inspect:
    print(sorted(d.columns))
    sys.exit(0)

if C["stype"]:
    d = d[d[C["stype"]].astype(str).str.upper().isin(["REG", "REGULAR"])]
d = d[d[C["pos"]].astype(str).str.upper().isin(["QB", "RB", "WR", "TE"])]

sumcols = [C[k] for k in ["py", "pt", "pi", "ry", "rt", "rec", "rey", "ret"]]
sumcols += [C[k] for k in ["fl_r", "fl_c", "fl_s", "tp_p", "tp_r", "tp_c"] if C[k]]
s = d.groupby([C["pid"], C["season"]])[sumcols].sum().reset_index()
g = d.groupby([C["pid"], C["season"]]).size().rename("games").reset_index()
m = d.groupby([C["pid"], C["season"]]).agg(name=(C["name"], "last"), pos=(C["pos"], "last")).reset_index()
s = s.merge(g, on=[C["pid"], C["season"]]).merge(m, on=[C["pid"], C["season"]])
s = s.rename(columns={C["pid"]: "pid", C["season"]: "season"})
s = s.fillna(0)

fl = sum(s[C[k]] for k in ["fl_r", "fl_c", "fl_s"] if C[k])
tp = sum(s[C[k]] for k in ["tp_p", "tp_r", "tp_c"] if C[k])
if not isinstance(fl, pd.Series):
    fl = 0
if not isinstance(tp, pd.Series):
    tp = 0

# recAbs: TE 1.0 (half PPR + TE premium) | RB/WR 0.5 | QB 0   -- exactly gamefp()
recabs = np.where(s["pos"].str.upper() == "TE", 1.0,
                  np.where(s["pos"].str.upper() == "QB", 0.0, 0.5))
s["fpts"] = (s[C["py"]] * 0.04 + s[C["pt"]] * 4 + s[C["pi"]] * -2
             + s[C["ry"]] * 0.1 + s[C["rt"]] * 6
             + s[C["rec"]] * recabs + s[C["rey"]] * 0.1 + s[C["ret"]] * 6
             + fl * -2 + tp * 2)
s["ppg"] = s["fpts"] / s["games"]

# --- scoring sanity check against a value baked in the engine's player table ---
print("\nscoring sanity (engine's baked table says Josh Allen 2025 ppg25 = 22.0):")
ja = s[(s["name"].str.contains("Josh Allen", na=False)) & (s["season"] == 2025)]
if len(ja):
    r = ja.iloc[0]
    print(f"  derived Josh Allen 2025: {r['ppg']:.1f} PPG over {int(r['games'])} games "
          f"-> {'✓ matches' if abs(r['ppg'] - 22.0) < 1.5 else '✗ MISMATCH — check scoring'}")

q = s[s["games"] >= args.min_games].copy()
print(f"\nqualifying player-seasons (>= {args.min_games} games): {len(q)}")
for p in ["QB", "RB", "WR", "TE"]:
    per = q[q["pos"].str.upper() == p].groupby("season").size()
    print(f"  {p}: {per.min()}-{per.max()} per season (need >= {max(BREAKS[p])} for the deepest breakpoint)")


# ============================================================ DERIVE
def derive(frame, pos, rank_by="ppg"):
    """Average the value at each rank across seasons, then normalize to rank 1."""
    metric = "ppg" if rank_by == "ppg" else "fpts"
    by_rank = {}
    for season, gg in frame[frame["pos"].str.upper() == pos].groupby("season"):
        vals = gg.sort_values(metric, ascending=False)[metric].values
        for i, v in enumerate(vals, start=1):
            by_rank.setdefault(i, []).append(float(v))
    avg = {r: float(np.mean(v)) for r, v in by_rank.items() if len(v) >= 2}
    if 1 not in avg:
        return None, None
    top = avg[1]
    curve = []
    for r in BREAKS[pos]:
        if r not in avg:
            return None, avg          # not enough depth at that rank
        curve.append([r, round(avg[r] / top, 3)])
    return curve, avg


hr("STEP 1 — METHOD VALIDATION.  Does this method reproduce the COMMITTED RB curve?")
print("We do not have the original derivation script. If the method is right, it should")
print("recover RB's curve — the one that IS production-derived. If it cannot, we stop.\n")

rb_derived, rb_avg = derive(q, "RB", args.rank_by)
if rb_derived is None:
    sys.exit("could not derive RB — insufficient depth. Lower --min-games.")

print(f"  {'rank':<6}{'committed RB':>14}{'derived RB':>13}{'diff':>9}")
diffs = []
for (r, v_old), (_, v_new) in zip(CURRENT["RB"], rb_derived):
    diffs.append(abs(v_new - v_old))
    print(f"  RB{str(r):<4}{v_old:>14.3f}{v_new:>13.3f}{v_new - v_old:>+9.3f}")
mad = float(np.mean(diffs))
print(f"\n  mean absolute difference: {mad:.3f}")
if mad < 0.035:
    print("  ✓ METHOD VALIDATED — reproduces the committed RB curve closely.")
    method_ok = True
elif mad < 0.07:
    print("  ~ CLOSE but not exact. The original likely used a different window/floor.")
    print("    Treat the QB/WR/TE numbers below as INDICATIVE, and tune the window to")
    print("    minimise this RB gap before trusting them.")
    method_ok = True
else:
    print("  ✗ METHOD DOES NOT MATCH. Do not trust the derived QB/WR/TE curves until")
    print("    the window/floor is tuned so RB reproduces. STOPPING.")
    method_ok = False

# ============================================================ NEW CURVES
hr("STEP 2 — DERIVED CURVES (same breakpoints = drop-in replacement)")
derived = {"RB": rb_derived}
for pos in ["QB", "WR", "TE"]:
    c, _ = derive(q, pos, args.rank_by)
    if c is None:
        print(f"  {pos}: INSUFFICIENT DEPTH at deepest breakpoint — lower --min-games")
        derived[pos] = CURRENT[pos]
        continue
    derived[pos] = c

for pos in ["QB", "WR", "TE", "RB"]:
    old, new = CURRENT[pos], derived[pos]
    tag = "  (already derived — control)" if pos == "RB" else ""
    print(f"\n{pos}{tag}")
    print(f"  {'rank':<7}{'current':>10}{'derived':>10}{'change':>10}")
    for (r, vo), (_, vn) in zip(old, new):
        arrow = "↑" if vn > vo + 0.005 else ("↓" if vn < vo - 0.005 else "=")
        print(f"  {pos}{str(r):<5}{vo:>10.3f}{vn:>10.3f}{vn - vo:>+9.3f} {arrow}")
    # a value curve MUST be monotonically non-increasing
    vals = [v for _, v in new]
    if any(vals[i + 1] > vals[i] + 1e-9 for i in range(len(vals) - 1)):
        print(f"  ⚠ NON-MONOTONIC — a deeper rank out-produces a shallower one. Noise; widen the window.")

print("\nDrop-in replacement (paste into delta-engine.js SCAR_CURVE):")
for pos in ["QB", "RB", "WR", "TE"]:
    body = ",".join(f"[{r},{v}]" for r, v in derived[pos])
    print(f"  {pos}: [{body}],")

# ============================================================ IMPACT
hr("STEP 3 — IMPACT ON scarcity() ACROSS ALL 8 LEAGUE SETTINGS")
print("(factor < 1 = position discounted vs the 12-SF anchor; > 1 = premium)\n")
SETTINGS = [(t, f) for f in ["1qb", "sf"] for t in [8, 10, 12, 14]]
print(f"  {'setting':<10}{'pos':<5}{'current':>9}{'derived':>9}{'change':>9}")
rows = []
for teams, fmt in SETTINGS:
    for pos in ["QB", "RB", "WR", "TE"]:
        a = scarcity(CURRENT, pos, teams, fmt)
        b = scarcity(derived, pos, teams, fmt)
        rows.append(dict(teams=teams, fmt=fmt, pos=pos, cur=a, new=b))
        if pos == "QB" or abs(b - a) > 0.02:
            print(f"  {str(teams)+fmt:<10}{pos:<5}{a:>9.3f}{b:>9.3f}{b - a:>+9.3f}")
IMP = pd.DataFrame(rows)
IMP.to_csv(f"{OUT}/scarcity_impact.csv", index=False)

# ============================================================ MARKET YARDSTICK
hr("STEP 4 — MARKET YARDSTICK (FantasyCalc)  ** MEASUREMENT ONLY, NEVER A TARGET **")
print("DELTA is market-blind by design: the model-vs-market gap IS the product.")
print("We check this only to see whether the derived curves narrow the QB-1QB anomaly")
print("as a BYPRODUCT. If they do not, that is a legitimate disagreement, not a failure.\n")

try:
    url = "https://raw.githubusercontent.com/HandHanley/fantasy-delta/main/data/scarcity-validation.json"
    V = json.loads(urllib.request.urlopen(url, timeout=30).read().decode())
    print(f"  {'setting':<10}{'pos':<5}{'market':>8}{'current':>9}{'derived':>9}{'  cur gap':>10}{'  new gap':>10}")
    agree_cur = agree_new = total = 0
    qb1_cur, qb1_new = [], []
    for st in V["settings"]:
        teams, fmt = st["teams"], st["qb"]
        for pos, info in st["positions"].items():
            mf = info.get("marketFactor")
            if mf is None:
                continue
            a = scarcity(CURRENT, pos, teams, fmt)
            b = scarcity(derived, pos, teams, fmt)
            # directional agreement: do model and market agree the position is
            # discounted (or premium) vs the anchor?
            total += 1
            if np.sign(a - 1) == np.sign(mf - 1) or abs(a - mf) < 0.02:
                agree_cur += 1
            if np.sign(b - 1) == np.sign(mf - 1) or abs(b - mf) < 0.02:
                agree_new += 1
            gc = (mf - a) / mf * 100     # + = DELTA discounts HARDER than market
            gn = (mf - b) / mf * 100
            if pos == "QB" and fmt == "1qb":
                qb1_cur.append(gc)
                qb1_new.append(gn)
            if pos == "QB":
                print(f"  {str(teams)+fmt:<10}{pos:<5}{mf:>8.3f}{a:>9.3f}{b:>9.3f}{gc:>+9.1f}%{gn:>+9.1f}%")
    print(f"\n  directional agreement:  current {agree_cur}/{total}   derived {agree_new}/{total}")
    if qb1_cur:
        print(f"  QB-in-1QB over-discount (DELTA harder than market):")
        print(f"     current: {min(qb1_cur):+.1f}% to {max(qb1_cur):+.1f}%")
        print(f"     derived: {min(qb1_new):+.1f}% to {max(qb1_new):+.1f}%")
        narrowed = np.mean(np.abs(qb1_new)) < np.mean(np.abs(qb1_cur))
        print(f"     -> {'NARROWED' if narrowed else 'did NOT narrow'} (byproduct, not a target)")
except Exception as e:
    print(f"  (could not load the validation file: {e})")

# ============================================================ SENSITIVITY
hr("STEP 5 — SENSITIVITY (is the QB curve stable, or an artifact of my choices?)")
print(f"  {'variant':<34}{'QB@12':>8}{'QB@22':>8}{'RB check (MAD vs committed)':>30}")
base_q = dict(derived["QB"])
for label, seasons, ming, rankby in [
    ("baseline (as configured)", SEASONS, args.min_games, args.rank_by),
    ("3-yr window", list(range(hi - 2, hi + 1)), args.min_games, args.rank_by),
    ("8-yr window", list(range(hi - 7, hi + 1)), args.min_games, args.rank_by),
    ("min-games 4", SEASONS, 4, args.rank_by),
    ("min-games 10", SEASONS, 10, args.rank_by),
    ("rank by TOTAL points", SEASONS, args.min_games, "total"),
]:
    sub = s[(s["season"].isin(seasons)) & (s["games"] >= ming)]
    cq, _ = derive(sub, "QB", rankby)
    cr, _ = derive(sub, "RB", rankby)
    if cq is None or cr is None:
        print(f"  {label:<34}{'(insufficient depth)':>46}")
        continue
    dq = dict(cq)
    rb_mad = float(np.mean([abs(dict(cr)[r] - v) for r, v in CURRENT["RB"]]))
    print(f"  {label:<34}{dq[12]:>8.3f}{dq[22]:>8.3f}{rb_mad:>30.3f}")
print(f"\n  (committed QB curve for reference:  QB@12 = {dict(CURRENT['QB'])[12]:.3f}   QB@22 = {dict(CURRENT['QB'])[22]:.3f})")
print("  A trustworthy result is stable across these variants AND keeps the RB check low.")

hr("DONE — nothing written to /data or the engine")
print(f"wrote {OUT}/scarcity_impact.csv")
print("Review, then decide. No curve is committed by this script.")
