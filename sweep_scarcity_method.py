#!/usr/bin/env python3
"""
DELTA research — SCARCITY CURVE: METHOD REVERSE-ENGINEERING SWEEP

WHY
---
The first derivation run FAILED its own validation gate. Validation = reproduce the
COMMITTED RB curve (the one that genuinely IS production-derived, 2026-06-28):

    rank   committed   my v1     diff
    RB6      0.843     0.748    -0.095
    RB12     0.686     0.655    -0.031
    RB26     0.579     0.509    -0.070
    RB34     0.508     0.425    -0.083
    MAD = 0.051     (gate: < 0.035)

If I cannot reproduce RB, then adopting my QB/WR/TE curves would leave the engine
holding curves derived by TWO DIFFERENT methods — exactly the inconsistency this
work exists to remove. So: do not guess. Sweep the plausible method space and let
the RB control select the method, then apply THAT ONE METHOD to all four positions.

HYPOTHESES TESTED (and one already discarded)
---------------------------------------------
- DISCARDED: normalization order (avg-then-norm vs norm-then-avg). I predicted
  Jensen's inequality would make norm-then-avg systematically higher. Pre-tested it
  on synthetic data: the effect is ~0.000 unless rank-1 carries large INDEPENDENT
  noise. Far too small to explain a 0.05-0.09 gap. Still swept, but it is not the answer.
- LEADING: RANK SMOOTHING. My curve is LOWER at every rank, which means my denominator
  (rank 1) is too HIGH. Raw rank-1 is a single outlier — the best season in the window.
  A rolling average over adjacent ranks pulls it down and lifts every ratio. Synthetic
  check: k=1 smoothing takes MAD from 0.040 -> 0.028. Right direction, right magnitude.
- ALSO SWEPT: median vs mean across seasons (robust to an outlier year), qualification
  floor (games-based vs "real contributor" opportunity-based), season window, scoring
  format, ranking metric.

OFFLINE RESEARCH ONLY. Writes study/out/. Never touches /data or the engine.

Install:  pip install nflreadpy pandas numpy
Usage:    python sweep_scarcity_method.py
"""

import os
import sys
import json
import itertools
import urllib.request

import numpy as np
import pandas as pd

OUT = "study/out"
os.makedirs(OUT, exist_ok=True)

CURRENT = {
    "QB": [[1, 1.0], [6, 0.865], [9, 0.796], [12, 0.769], [15, 0.731], [18, 0.721], [22, 0.647], [26, 0.608], [32, 0.471]],
    "RB": [[1, 1.0], [6, 0.843], [12, 0.686], [19, 0.614], [26, 0.579], [34, 0.508]],   # THE CONTROL
    "WR": [[1, 1.0], [8, 0.705], [16, 0.588], [24, 0.537], [36, 0.473], [48, 0.362]],
    "TE": [[1, 1.0], [3, 0.788], [5, 0.667], [8, 0.605], [11, 0.582], [14, 0.563], [18, 0.507]],
}
SCAR_STARTERS = {"QB": {"1qb": 1.0, "sf": 1.8}, "RB": 2.4, "WR": 3.0, "TE": 1.1}
BREAKS = {p: [r for r, _ in c] for p, c in CURRENT.items()}
GATE = 0.035


def hr(t=""):
    print("\n" + "=" * 78, flush=True)
    if t:
        print(t)
        print("-" * 78, flush=True)


def cv(curve, rank):
    if rank <= curve[0][0]:
        return curve[0][1]
    for i in range(len(curve) - 1):
        if rank <= curve[i + 1][0]:
            r0, v0 = curve[i]
            r1, v1 = curve[i + 1]
            return v0 + (rank - r0) / (r1 - r0) * (v1 - v0)
    return curve[-1][1]


def scarcity(curves, pos, teams, qbfmt):
    st = SCAR_STARTERS["QB"][qbfmt] if pos == "QB" else SCAR_STARTERS[pos]
    stD = SCAR_STARTERS["QB"]["sf"] if pos == "QB" else SCAR_STARTERS[pos]
    gap = 1 - cv(curves[pos], (teams or 12) * st)
    gapD = 1 - cv(curves[pos], 12 * stD)
    return gap / gapD if gapD > 0 else 1.0


def mad_vs(curve, pos):
    ref = dict(CURRENT[pos])
    return float(np.mean([abs(v - ref[r]) for r, v in curve]))


# ==================================================== LOAD
hr("LOADING 2016-2025")
try:
    import nflreadpy as nfl
except ImportError:
    sys.exit("pip install nflreadpy pandas numpy")

d = nfl.load_player_stats(seasons=list(range(2016, 2026)))
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
        sys.exit(f"FATAL: none of {c}")
    return None


C = {k: find(d, *v) for k, v in {
    "pid": ("player_id", "gsis_id"), "name": ("player_display_name", "player_name"),
    "pos": ("position", "position_group"), "season": ("season",),
    "py": ("passing_yards",), "pt": ("passing_tds",),
    "pi": ("passing_interceptions", "interceptions"),
    "ry": ("rushing_yards",), "rt": ("rushing_tds",),
    "rec": ("receptions",), "rey": ("receiving_yards",), "ret": ("receiving_tds",),
    "att": ("attempts", "passing_attempts"), "car": ("carries", "rushing_attempts"),
    "tgt": ("targets",),
}.items()}
C["stype"] = find(d, "season_type", required=False)
for k, cands in [("fl_r", ("rushing_fumbles_lost",)), ("fl_c", ("receiving_fumbles_lost",)),
                 ("fl_s", ("sack_fumbles_lost",))]:
    C[k] = find(d, *cands, required=False)

if C["stype"]:
    d = d[d[C["stype"]].astype(str).str.upper().isin(["REG", "REGULAR"])]
d = d[d[C["pos"]].astype(str).str.upper().isin(["QB", "RB", "WR", "TE"])]

cols = [C[k] for k in ["py", "pt", "pi", "ry", "rt", "rec", "rey", "ret", "att", "car", "tgt"]]
cols += [C[k] for k in ["fl_r", "fl_c", "fl_s"] if C[k]]
S = d.groupby([C["pid"], C["season"]])[cols].sum().reset_index()
G = d.groupby([C["pid"], C["season"]]).size().rename("games").reset_index()
M = d.groupby([C["pid"], C["season"]]).agg(pos=(C["pos"], "last")).reset_index()
S = S.merge(G, on=[C["pid"], C["season"]]).merge(M, on=[C["pid"], C["season"]]).fillna(0)
S = S.rename(columns={C["pid"]: "pid", C["season"]: "season"})
S["pos"] = S["pos"].str.upper()
FLS = sum(S[C[k]] for k in ["fl_r", "fl_c", "fl_s"] if C[k])
if not isinstance(FLS, pd.Series):
    FLS = pd.Series(0.0, index=S.index)
S["fl"] = FLS
S["opp"] = np.where(S["pos"] == "QB", S[C["att"]],
                    np.where(S["pos"] == "RB", S[C["car"]] + S[C["tgt"]], S[C["tgt"]]))

REC_PTS = {
    "half_tep":  lambda p: np.where(p == "TE", 1.0, np.where(p == "QB", 0.0, 0.5)),   # DELTA (gamefp)
    "half_flat": lambda p: np.where(p == "QB", 0.0, 0.5),
    "full_ppr":  lambda p: np.where(p == "QB", 0.0, 1.0),
    "standard":  lambda p: np.where(p == "QB", 0.0, 0.0),
}
OPP_FLOOR = {"QB": 100, "RB": 50, "WR": 25, "TE": 25}

WINDOWS = {
    "2021-2025 (5y)": list(range(2021, 2026)),
    "2019-2025 (7y)": list(range(2019, 2026)),
    "2017-2025 (9y)": list(range(2017, 2026)),
    "2023-2025 (3y)": list(range(2023, 2026)),
    "2016-2025 (10y)": list(range(2016, 2026)),
}
FLOORS = [("games", 4), ("games", 6), ("games", 8), ("games", 10), ("opp", 0)]
SCORINGS = list(REC_PTS)
METRICS = ["ppg", "total"]
NORMS = ["avg_then_norm", "norm_then_avg"]
AGGS = ["mean", "median"]
SMOOTHS = [0, 1, 2, 3]


def season_vectors(pos, window, floor_kind, floor_val, scoring, metric):
    """Sorted value vector per season (the expensive part — cached per base combo)."""
    f = S[(S["season"].isin(window)) & (S["pos"] == pos)]
    f = f[f["games"] >= floor_val] if floor_kind == "games" else f[f["opp"] >= OPP_FLOOR[pos]]
    if f.empty:
        return {}
    rp = REC_PTS[scoring](f["pos"].values)
    fp = (f[C["py"]] * 0.04 + f[C["pt"]] * 4 + f[C["pi"]] * -2
          + f[C["ry"]] * 0.1 + f[C["rt"]] * 6
          + f[C["rec"]] * rp + f[C["rey"]] * 0.1 + f[C["ret"]] * 6
          + f["fl"] * -2)
    val = fp if metric == "total" else fp / f["games"].clip(lower=1)
    out = {}
    for season, idx in f.groupby("season").groups.items():
        v = np.sort(val.loc[idx].values)[::-1]
        out[season] = v
    return out


def build(vecs, pos, norm, agg, k):
    need = max(BREAKS[pos])
    usable = [v for v in vecs.values() if len(v) >= need]
    if len(usable) < 3:
        return None
    A = np.mean if agg == "mean" else np.median

    def smooth(v):
        if k == 0:
            return v
        return np.array([v[max(0, i - k): i + k + 1].mean() for i in range(len(v))])

    if norm == "norm_then_avg":
        rows = []
        for v in usable:
            sv = smooth(v)
            if sv[0] <= 0:
                continue
            rows.append([sv[r - 1] / sv[0] for r in BREAKS[pos]])
        if not rows:
            return None
        vals = A(np.array(rows), axis=0)
    else:
        trunc = np.array([smooth(v)[:need] for v in usable])
        avg = A(trunc, axis=0)
        if avg[0] <= 0:
            return None
        vals = np.array([avg[r - 1] / avg[0] for r in BREAKS[pos]])
    return [[r, round(float(x), 3)] for r, x in zip(BREAKS[pos], vals)]


# ==================================================== SWEEP
hr("SWEEP — which method reproduces the COMMITTED RB curve?")
print("RB is the control: the one curve that was genuinely production-derived.")
print("Whatever variant recovers it is the method that was used.\n")

results = []
for (wname, window), (fk, fv), sc, me in itertools.product(
        WINDOWS.items(), FLOORS, SCORINGS, METRICS):
    vecs = season_vectors("RB", window, fk, fv, sc, me)
    if not vecs:
        continue
    for nm, ag, k in itertools.product(NORMS, AGGS, SMOOTHS):
        c = build(vecs, "RB", nm, ag, k)
        if c is None:
            continue
        results.append(dict(
            window=wname, floor=(f"games>={fv}" if fk == "games" else "contributor"),
            scoring=sc, metric=me, norm=nm, agg=ag, smooth=k,
            mad=mad_vs(c, "RB"), curve=json.dumps(c)))

R = pd.DataFrame(results).sort_values("mad").reset_index(drop=True)
R.drop(columns=["curve"]).to_csv(f"{OUT}/method_sweep.csv", index=False)
print(f"{len(R)} variants tested.  Best 15 by RB reproduction:\n")
print(f"  {'MAD':>6}  {'window':<16}{'floor':<13}{'scoring':<11}{'metric':<7}{'norm':<15}{'agg':<8}{'smooth'}")
for _, r in R.head(15).iterrows():
    flag = "  <== REPRODUCES" if r["mad"] < GATE else ""
    print(f"  {r['mad']:>6.3f}  {r['window']:<16}{r['floor']:<13}{r['scoring']:<11}"
          f"{r['metric']:<7}{r['norm']:<15}{r['agg']:<8}k={r['smooth']}{flag}")

print("\nWhich knob actually mattered? (best MAD achievable per setting)")
for dim in ["smooth", "norm", "agg", "metric", "scoring", "floor", "window"]:
    b = R.groupby(dim)["mad"].min().sort_values()
    line = "   ".join(f"{k}={v:.3f}" for k, v in b.items())
    print(f"  {dim:<9} {line}")

best = R.iloc[0]
print(f"\nBEST MAD = {best['mad']:.3f}   (gate < {GATE})")

if best["mad"] >= GATE:
    hr("METHOD NOT RECOVERED — STOPPING (as pre-registered)")
    bc = json.loads(best["curve"])
    print(f"  {'rank':<7}{'committed':>11}{'best derived':>14}{'diff':>9}")
    for (r, vo), (_, vn) in zip(CURRENT["RB"], bc):
        print(f"  RB{str(r):<5}{vo:>11.3f}{vn:>14.3f}{vn - vo:>+9.3f}")
    print("\nNo variant in this space reproduces the committed RB curve. The original method")
    print("is something we are not replicating (hand-adjustment after derivation, a fitted")
    print("parametric curve, or a different data source).")
    print("\nDO NOT adopt derived QB/WR/TE curves — that would leave the engine with curves")
    print("from two different methods, the exact inconsistency this work exists to remove.")
    print("Next step: locate the original derivation (repo history around 2026-06-28).")
    sys.exit(0)

# ==================================================== APPLY WINNING METHOD TO ALL FOUR
hr("METHOD RECOVERED — deriving ALL FOUR curves with the SAME method")
print(f"  window={best['window']}  floor={best['floor']}  scoring={best['scoring']}")
print(f"  metric={best['metric']}  norm={best['norm']}  agg={best['agg']}  smooth=k{best['smooth']}\n")

window = WINDOWS[best["window"]]
fk, fv = (("games", int(best["floor"].split(">=")[1])) if ">=" in best["floor"] else ("opp", 0))
derived, ok = {}, True
for pos in ["QB", "RB", "WR", "TE"]:
    vecs = season_vectors(pos, window, fk, fv, best["scoring"], best["metric"])
    c = build(vecs, pos, best["norm"], best["agg"], int(best["smooth"]))
    if c is None:
        print(f"  {pos}: INSUFFICIENT DEPTH — keeping current curve")
        derived[pos] = CURRENT[pos]
        continue
    derived[pos] = c
    vals = [v for _, v in c]
    mono = all(vals[i + 1] <= vals[i] + 1e-9 for i in range(len(vals) - 1))
    tag = "   (CONTROL)" if pos == "RB" else ""
    print(f"{pos}{tag}")
    print(f"  {'rank':<8}{'current':>10}{'derived':>10}{'change':>10}")
    for (r, vo), (_, vn) in zip(CURRENT[pos], c):
        a = "^" if vn > vo + 0.005 else ("v" if vn < vo - 0.005 else "=")
        print(f"  {pos}{str(r):<6}{vo:>10.3f}{vn:>10.3f}{vn - vo:>+9.3f} {a}")
    if not mono:
        print("  ! NON-MONOTONIC — a deeper rank out-produces a shallower one (noise)")
        ok = False
    if pos == "RB":
        mm = mad_vs(c, "RB")
        print(f"  -> RB control MAD = {mm:.3f}  {'OK' if mm < GATE else 'FAILED'}")
    print()

print("Drop-in replacement (delta-engine.js SCAR_CURVE):")
for pos in ["QB", "RB", "WR", "TE"]:
    print(f"  {pos}: [{','.join(f'[{r},{v}]' for r, v in derived[pos])}],")

# ==================================================== IMPACT
hr("IMPACT ON scarcity() — all 8 settings x 4 positions")
print(f"  {'setting':<9}{'pos':<5}{'current':>9}{'derived':>9}{'change':>9}")
for fmt in ["1qb", "sf"]:
    for teams in [8, 10, 12, 14]:
        for pos in ["QB", "RB", "WR", "TE"]:
            a, b = scarcity(CURRENT, pos, teams, fmt), scarcity(derived, pos, teams, fmt)
            if pos == "QB" or abs(b - a) > 0.02:
                print(f"  {str(teams)+fmt:<9}{pos:<5}{a:>9.3f}{b:>9.3f}{b - a:>+9.3f}")

# ==================================================== MARKET YARDSTICK
hr("MARKET YARDSTICK (FantasyCalc)  ** MEASUREMENT ONLY, NEVER A TARGET **")
print("DELTA is market-blind: the model-vs-market gap IS the product. A narrowing here")
print("is a BYPRODUCT of better data. A widening would be a legitimate disagreement.\n")
try:
    V = json.loads(urllib.request.urlopen(
        "https://raw.githubusercontent.com/HandHanley/fantasy-delta/main/data/scarcity-validation.json",
        timeout=30).read().decode())
    ac = an = tot = 0
    q1c, q1n = [], []
    print(f"  {'setting':<9}{'pos':<5}{'market':>8}{'current':>9}{'derived':>9}{'cur gap':>10}{'new gap':>10}")
    for st in V["settings"]:
        t, f = st["teams"], st["qb"]
        for pos, info in st["positions"].items():
            mf = info.get("marketFactor")
            if mf is None:
                continue
            a, b = scarcity(CURRENT, pos, t, f), scarcity(derived, pos, t, f)
            tot += 1
            ac += bool(np.sign(a - 1) == np.sign(mf - 1) or abs(a - mf) < 0.02)
            an += bool(np.sign(b - 1) == np.sign(mf - 1) or abs(b - mf) < 0.02)
            gc, gn = (mf - a) / mf * 100, (mf - b) / mf * 100
            if pos == "QB" and f == "1qb":
                q1c.append(gc)
                q1n.append(gn)
            if pos == "QB":
                print(f"  {str(t)+f:<9}{pos:<5}{mf:>8.3f}{a:>9.3f}{b:>9.3f}{gc:>+9.1f}%{gn:>+9.1f}%")
    print(f"\n  directional agreement:  current {int(ac)}/{tot}   derived {int(an)}/{tot}")
    if int(an) < tot:
        print("  !! derived curves BREAK a directional agreement — do not adopt without investigating")
        ok = False
    if q1c:
        print(f"  QB-in-1QB over-discount:  current {min(q1c):+.1f}%..{max(q1c):+.1f}%    "
              f"derived {min(q1n):+.1f}%..{max(q1n):+.1f}%")
except Exception as e:
    print(f"  (validation file unavailable: {e})")

hr("VERDICT")
print(f"  RB control reproduced : {'YES' if best['mad'] < GATE else 'NO'}  (MAD {best['mad']:.3f})")
print(f"  All curves monotonic  : {'YES' if ok else 'NO'}")
print(f"  Directional agreement : see above")
print("\n  If all three are clean, these four curves come from ONE consistent, validated")
print("  method and are safe to discuss adopting. Nothing has been committed.")
print(f"\nwrote {OUT}/method_sweep.csv")
