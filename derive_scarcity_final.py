#!/usr/bin/env python3
"""
DELTA research — SCARCITY CURVES, PRINCIPLED DERIVATION (final)

WHY THIS REPLACES THE SWEEP
---------------------------
The method sweep "succeeded" (RB MAD 0.015) and the result must be THROWN OUT.
Two provable reasons:

1. SMOOTHING ARTIFACT. The winning variant used k=3 rank-smoothing. At shallow
   breakpoints the windows overlap almost entirely, forcing adjacent curve points
   together BY CONSTRUCTION:
       TE rank 1 -> averaged over ranks 1-4
       TE rank 3 -> averaged over ranks 1-6      (67% overlap)
   On realistic TE data the true TE3/TE1 ratio is 0.807; k=3 reports 0.945.
   The "flatter TE curve" was the smoother eating itself. It also flattened the
   top of the QB curve, which cratered the 8-team QB factor (0.524 -> 0.376) and
   blew the market gap out to +38%.
   RB's breakpoints (1,6,12,19,26,34) are wide enough to overlap only 22%, so the
   CONTROL TOLERATES the very setting that destroys TE. The control is misleading.

2. UNIDENTIFIABILITY. 937 of 3200 variants reproduced RB within the gate. Every
   parameter still had multiple "valid" values -- INCLUDING all four scoring
   formats. RB is rushing-dominated so it is blind to PPR, but PPR is the single
   biggest driver of the WR/TE curves. A 0.001 MAD difference on a blind control
   "selected" full_ppr even though DELTA scores half_tep. That is fitting to noise.

THE APPROACH HERE
-----------------
Stop trying to match the old RB curve -- its provenance is unrecoverable. Instead
fix every parameter by KNOWLEDGE or PRINCIPLE, document why, and derive ALL FOUR
curves with that one method. Four curves from one documented method beats one curve
from an unknown method plus three hand-guesses.

    scoring  = half_tep   -- DELTA's actual format, straight from gamefp()
    metric   = PPG        -- validated twice (total-points wrecks RB and destabilises QB)
    smoothing= NONE       -- k>=1 provably distorts shallow ranks (see above)
    window   = 9 seasons  -- reduce noise HONESTLY (more data), not by smoothing
    floor    = contributor-- a real opportunity threshold, not an games artifact
    norm/agg = swept and reported; they move the answer by <0.01 (immaterial)

RB will shift slightly from its committed values. That is expected and fine: we are
replacing an unknown method with a documented one, not claiming the old one was wrong.

NEW: uncertainty bands. Leave-one-season-out resampling gives a spread on every
curve point, so we can see which parts of the curve we actually know.

OFFLINE RESEARCH ONLY. Writes study/out/. Never touches /data or the engine.
Usage:  python derive_scarcity_final.py
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
    "RB": [[1, 1.0], [6, 0.843], [12, 0.686], [19, 0.614], [26, 0.579], [34, 0.508]],
    "WR": [[1, 1.0], [8, 0.705], [16, 0.588], [24, 0.537], [36, 0.473], [48, 0.362]],
    "TE": [[1, 1.0], [3, 0.788], [5, 0.667], [8, 0.605], [11, 0.582], [14, 0.563], [18, 0.507]],
}
SCAR_STARTERS = {"QB": {"1qb": 1.0, "sf": 1.8}, "RB": 2.4, "WR": 3.0, "TE": 1.1}
BREAKS = {p: [r for r, _ in c] for p, c in CURRENT.items()}
OPP_FLOOR = {"QB": 100, "RB": 50, "WR": 25, "TE": 25}
WINDOW = list(range(2017, 2026))          # 9 seasons


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


# ==================================================== LOAD
hr(f"PRINCIPLED SCARCITY DERIVATION  ({WINDOW[0]}-{WINDOW[-1]}, half_tep, PPG, NO smoothing)")
try:
    import nflreadpy as nfl
except ImportError:
    sys.exit("pip install nflreadpy pandas numpy")

d = nfl.load_player_stats(seasons=WINDOW)
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
M = d.groupby([C["pid"], C["season"]]).agg(name=(C["name"], "last"), pos=(C["pos"], "last")).reset_index()
S = S.merge(G, on=[C["pid"], C["season"]]).merge(M, on=[C["pid"], C["season"]]).fillna(0)
S = S.rename(columns={C["pid"]: "pid", C["season"]: "season"})
S["pos"] = S["pos"].str.upper()
FLS = sum(S[C[k]] for k in ["fl_r", "fl_c", "fl_s"] if C[k])
S["fl"] = FLS if isinstance(FLS, pd.Series) else 0.0
S["opp"] = np.where(S["pos"] == "QB", S[C["att"]],
                    np.where(S["pos"] == "RB", S[C["car"]] + S[C["tgt"]], S[C["tgt"]]))

# half_tep — EXACTLY gamefp(): TE 1.0/rec (0.5 PPR + 0.5 TE premium), RB/WR 0.5, QB 0
recpts = np.where(S["pos"] == "TE", 1.0, np.where(S["pos"] == "QB", 0.0, 0.5))
S["fpts"] = (S[C["py"]] * 0.04 + S[C["pt"]] * 4 + S[C["pi"]] * -2
             + S[C["ry"]] * 0.1 + S[C["rt"]] * 6
             + S[C["rec"]] * recpts + S[C["rey"]] * 0.1 + S[C["ret"]] * 6
             + S["fl"] * -2)
S["ppg"] = S["fpts"] / S["games"].clip(lower=1)

ja = S[(S["name"].str.contains("Josh Allen", na=False)) & (S["season"] == 2025)]
if len(ja):
    print(f"scoring check — Josh Allen 2025: {ja.iloc[0]['ppg']:.1f} PPG "
          f"(engine's baked ppg25 = 22.0) {'OK' if abs(ja.iloc[0]['ppg']-22.0) < 1.5 else 'MISMATCH'}")

Q = S[S["opp"] >= S["pos"].map(OPP_FLOOR)].copy()
print(f"\nqualifying player-seasons (contributor floor): {len(Q)}")
for p in ["QB", "RB", "WR", "TE"]:
    n = Q[Q["pos"] == p].groupby("season").size()
    print(f"  {p}: {n.min()}-{n.max()} per season (deepest breakpoint needs {max(BREAKS[p])})")


def vectors(pos, seasons):
    out = {}
    f = Q[(Q["pos"] == pos) & (Q["season"].isin(seasons))]
    for season, gg in f.groupby("season"):
        out[season] = np.sort(gg["ppg"].values)[::-1]
    return out


def build(vecs, pos, norm="avg_then_norm", agg="mean"):
    """NO SMOOTHING — k>=1 provably distorts shallow ranks."""
    need = max(BREAKS[pos])
    usable = [v for v in vecs.values() if len(v) >= need]
    if len(usable) < 3:
        return None
    A = np.mean if agg == "mean" else np.median
    if norm == "norm_then_avg":
        rows = [[v[r - 1] / v[0] for r in BREAKS[pos]] for v in usable if v[0] > 0]
        vals = A(np.array(rows), axis=0)
    else:
        avg = A(np.array([v[:need] for v in usable]), axis=0)
        vals = np.array([avg[r - 1] / avg[0] for r in BREAKS[pos]])
    return [[r, round(float(x), 3)] for r, x in zip(BREAKS[pos], vals)]


# ==================================================== the artifact, for the record
hr("WHY NO SMOOTHING (the artifact that invalidated the sweep)")
print("Smoothing window at rank r covers ranks [r-3, r+3]. At shallow breakpoints the")
print("windows overlap almost entirely, forcing adjacent curve points together:\n")
for pos in ["TE", "RB"]:
    b = BREAKS[pos]
    w1 = set(range(max(0, -3), 4))
    w2 = set(range(max(0, b[1] - 1 - 3), b[1] + 3))
    print(f"  {pos}: rank1 window = ranks {min(w1)+1}-{max(w1)+1} | "
          f"rank{b[1]} window = ranks {min(w2)+1}-{max(w2)+1} | overlap "
          f"{100*len(w1 & w2)/len(w1 | w2):.0f}%"
          f"{'   <-- SEVERE (TE flattened by construction)' if pos == 'TE' else '   <-- mild (why RB tolerated it)'}")
print("\nThat is why the control (RB) endorsed a setting that destroyed TE.")

# ==================================================== derive
hr("DERIVED CURVES — one documented method, all four positions")
derived = {}
for pos in ["QB", "RB", "WR", "TE"]:
    c = build(vectors(pos, WINDOW), pos)
    if c is None:
        print(f"  {pos}: insufficient depth — keeping current")
        derived[pos] = CURRENT[pos]
        continue
    derived[pos] = c

# how much do norm/agg matter? (should be immaterial)
print("norm/agg sensitivity (should be immaterial — if not, flag it):")
for pos in ["QB", "WR", "TE", "RB"]:
    vs = []
    for nm, ag in itertools.product(["avg_then_norm", "norm_then_avg"], ["mean", "median"]):
        c = build(vectors(pos, WINDOW), pos, nm, ag)
        if c:
            vs.append(dict(c))
    if vs:
        mids = BREAKS[pos][len(BREAKS[pos]) // 2]
        spread = max(v[mids] for v in vs) - min(v[mids] for v in vs)
        print(f"  {pos} @rank{mids}: spread across norm/agg choices = {spread:.3f}"
              f"{'  OK' if spread < 0.03 else '  <-- MATERIAL, report both'}")

# ==================================================== uncertainty (leave-one-season-out)
hr("UNCERTAINTY — leave-one-season-out (which parts of the curve do we actually know?)")
print("Re-derive 9 times, each dropping one season. Spread = how much a single season moves it.\n")
bands = {}
for pos in ["QB", "RB", "WR", "TE"]:
    loo = []
    for drop in WINDOW:
        c = build(vectors(pos, [s for s in WINDOW if s != drop]), pos)
        if c:
            loo.append(dict(c))
    if not loo:
        continue
    bands[pos] = {r: (min(x[r] for x in loo), max(x[r] for x in loo)) for r in BREAKS[pos]}
    print(f"{pos}")
    print(f"  {'rank':<8}{'current':>9}{'derived':>9}{'change':>9}{'  LOO range':>18}{'':>4}")
    for (r, vo), (_, vn) in zip(CURRENT[pos], derived[pos]):
        loq, hiq = bands[pos][r]
        wide = (hiq - loq) > 0.05
        arrow = "^" if vn > vo + 0.005 else ("v" if vn < vo - 0.005 else "=")
        note = "  <- unstable" if wide else ""
        print(f"  {pos}{str(r):<6}{vo:>9.3f}{vn:>9.3f}{vn - vo:>+9.3f} {arrow}"
              f"   [{loq:.3f}, {hiq:.3f}]{note}")
    # RB is a sanity check now, NOT a gate — its provenance is unrecoverable
    if pos == "RB":
        mad = float(np.mean([abs(vn - vo) for (_, vo), (_, vn) in zip(CURRENT["RB"], derived["RB"])]))
        print(f"  -> RB vs committed: MAD {mad:.3f}  (sanity check only — the old method is")
        print(f"     unrecoverable, 937 variants reproduced it. We are REPLACING it, not matching it.)")
    print()

print("Drop-in replacement (delta-engine.js SCAR_CURVE):")
for pos in ["QB", "RB", "WR", "TE"]:
    print(f"  {pos}: [{','.join(f'[{r},{v}]' for r, v in derived[pos])}],")

# ==================================================== impact
hr("IMPACT ON scarcity()")
print(f"  {'setting':<9}{'pos':<5}{'current':>9}{'derived':>9}{'change':>9}")
for fmt in ["1qb", "sf"]:
    for teams in [8, 10, 12, 14]:
        for pos in ["QB", "RB", "WR", "TE"]:
            a, b = scarcity(CURRENT, pos, teams, fmt), scarcity(derived, pos, teams, fmt)
            if pos == "QB" or abs(b - a) > 0.02:
                print(f"  {str(teams)+fmt:<9}{pos:<5}{a:>9.3f}{b:>9.3f}{b - a:>+9.3f}")

# ==================================================== market yardstick
hr("MARKET YARDSTICK (FantasyCalc) — MEASUREMENT ONLY, NEVER A TARGET")
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
        print("  !! derived curves BREAK a directional agreement — investigate before adopting")
    if q1c:
        print(f"  QB-in-1QB gap:  current {min(q1c):+.1f}%..{max(q1c):+.1f}%    "
              f"derived {min(q1n):+.1f}%..{max(q1n):+.1f}%")
        print("  (narrowing = byproduct of better data. Widening = legitimate disagreement.")
        print("   Either is acceptable; a BLOW-UP like the sweep's +38% is a red flag.)")
except Exception as e:
    print(f"  (validation file unavailable: {e})")

hr("DONE — nothing committed")
json.dump({"current": CURRENT, "derived": derived,
           "bands": {p: {str(r): v for r, v in b.items()} for p, b in bands.items()}},
          open(f"{OUT}/scarcity_final.json", "w"), indent=2)
print(f"wrote {OUT}/scarcity_final.json")
print("\nDecide from: (a) size of the changes, (b) the LOO stability bands,")
print("(c) directional agreement holding, (d) no market blow-up.")
