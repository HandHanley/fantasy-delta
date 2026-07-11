#!/usr/bin/env python3
"""
DELTA research study — ROUND 2: does TD% regression predict FANTASY value?

Round 1 established (n=203 pairs, 2017-2025):
  - TD% mean-reverts hard: corr(dev from baseline, next-yr change) = -0.62,
    ~69% of the deviation given back. Robust at every attempt floor.
  - Per-QB baselines did NOT beat the league mean (2% RMSE, needed 5%) ->
    true TD% talent SD is only ~0.7pp. Most of a big TD% year is noise.
  - Dual-threat QBs revert HARDER than pocket QBs (-0.75 vs -0.60).

Round 1 tested TD% -> TD%. That is a RATE predicting a RATE. DELTA is a dynasty
VALUE model. This round tests the question that actually justifies shipping:

    Does a QB's TD%-above-baseline predict a DROP IN FANTASY PPG next year,
    AFTER controlling for volume, rushing, and his current PPG level?

Three ways a "real" TD% regression can be fantasy-irrelevant:
  1. RATE vs COUNT  - TD% falls but attempts rise; total TDs (and points) hold.
  2. RUSHING        - passing TDs fall but rushing production absorbs it (Lamar).
  3. NOT INCREMENTAL- the gap only "predicts" via info DELTA's projection already
                      uses (volume/production) -> double-counting, not new signal.

PRE-REGISTERED SHIP CRITERIA (decide before looking at output):
  S1. Raw signal: corr(td_gap, next-yr PPG change) <= -0.15, n >= 100.
  S2. INCREMENTAL: in OLS  d_ppg ~ td_gap + att + rush_ppg + ppg_now,
      the td_gap coefficient stays negative and significant (|t| >= 2.0).
  S3. Out-of-sample lift: adding td_gap to the controls-only model improves
      held-out RMSE of next-yr PPG by >= 2%.
  All three must pass. If S2 fails, the signal is a proxy for volume/production
  DELTA already models -> DO NOT SHIP.

  Also reported (decided in advance, not a ship gate): the same test on
  PASSING-ONLY fantasy points, to separate "TD% predicts passing decline" from
  "TD% predicts total value decline". If it predicts passing decline but total
  value holds up, that is the rushing-absorption story and we do not ship.

OFFLINE RESEARCH ONLY. Writes study/out/. Never touches /data.
Install:  pip install nflreadpy pandas numpy
Usage:    python td_pct_round2.py [--min-att N] [--train-end YYYY] [--seasons 2017-2025]
"""

import os
import sys
import argparse
import traceback

import numpy as np
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("--min-att", type=int, default=200)
ap.add_argument("--train-end", type=int, default=2022)
ap.add_argument("--seasons", type=str, default="2017-2025")
ap.add_argument("--inspect", action="store_true")
args = ap.parse_args()

lo, hi = (int(x) for x in args.seasons.split("-"))
SEASONS = list(range(lo, hi + 1))
MIN_ATT, TRAIN_END = args.min_att, args.train_end
OUT = "study/out"
os.makedirs(OUT, exist_ok=True)


def hr(t=""):
    print("\n" + "=" * 74, flush=True)
    if t:
        print(t)
        print("-" * 74, flush=True)


# ==================================================== LOAD
hr(f"ROUND 2 — TD% GAP vs NEXT-YEAR FANTASY PPG  ({SEASONS[0]}-{SEASONS[-1]})")

try:
    import nflreadpy as nflread
    print(f"backend: nflreadpy {getattr(nflread,'__version__','?')}")
    dat = nflread.load_player_stats(seasons=SEASONS)
    raw = dat.to_pandas() if hasattr(dat, "to_pandas") else pd.DataFrame(dat)
except Exception:
    print("nflreadpy failed; falling back to nfl_data_py")
    traceback.print_exc(file=sys.stdout)
    import nfl_data_py as nfl
    raw = nfl.import_weekly_data(SEASONS)

print(f"loaded {len(raw):,} rows x {len(raw.columns)} cols")


def find(f, *c, required=True, label=""):
    for x in c:
        if x in f.columns:
            return x
    low = {k.lower(): k for k in f.columns}
    for x in c:
        if x.lower() in low:
            return low[x.lower()]
    for x in c:
        for col in f.columns:
            if x.lower() in col.lower():
                return col
    if required:
        print(f"\nFATAL: no column for '{label or c[0]}'. Tried {c}")
        print("Available:")
        for col in sorted(f.columns):
            print("   ", col)
        sys.exit(1)
    return None


if args.inspect:
    for c in sorted(raw.columns):
        print(" ", c)
    sys.exit(0)

C = {
    "pid": find(raw, "player_id", "gsis_id"),
    "season": find(raw, "season"),
    "stype": find(raw, "season_type", required=False),
    "pos": find(raw, "position", "position_group"),
    "name": find(raw, "player_display_name", "player_name"),
    "att": find(raw, "attempts", "passing_attempts", "pass_attempts", label="pass attempts"),
    "ptd": find(raw, "passing_tds", "pass_touchdowns", label="passing TDs"),
    "pyd": find(raw, "passing_yards", "pass_yards", label="passing yards"),
    "pint": find(raw, "passing_interceptions", "interceptions", required=False),
    "ratt": find(raw, "carries", "rushing_attempts", required=False),
    "ryd": find(raw, "rushing_yards", required=False),
    "rtd": find(raw, "rushing_tds", required=False),
    "fum": find(raw, "rushing_fumbles_lost", "sack_fumbles_lost", "fumbles_lost", required=False),
}
print("\nresolved columns:")
for k, v in C.items():
    print(f"  {k:<7} -> {v}")

d = raw.copy()
if C["stype"]:
    d = d[d[C["stype"]].astype(str).str.upper().isin(["REG", "REGULAR"])]
d = d[d[C["pos"]].astype(str).str.upper().str.contains("QB", na=False)]
print(f"\nQB REG rows: {len(d):,}")

num = ["att", "ptd", "pyd", "pint", "ratt", "ryd", "rtd", "fum"]
agg = {C[k]: "sum" for k in num if C[k]}
s = d.groupby([C["pid"], C["season"]]).agg(agg).reset_index()
g = d.groupby([C["pid"], C["season"]]).size().rename("games").reset_index()
nm = d.groupby([C["pid"], C["season"]])[C["name"]].last().reset_index()
s = s.merge(g, on=[C["pid"], C["season"]]).merge(nm, on=[C["pid"], C["season"]])

ren = {C["pid"]: "pid", C["season"]: "season", C["name"]: "name"}
for k in num:
    if C[k]:
        ren[C[k]] = k
s = s.rename(columns=ren)
for k in num:
    if k not in s.columns:
        s[k] = 0.0
s[num] = s[num].fillna(0.0)

# ---- fantasy points, COMPUTED from components (not a black-box column).
# Standard QB scoring: 4/pass TD, 1/25 pass yd, -2 INT, 6/rush TD, 1/10 rush yd, -2 fumble.
# (QB scoring is the same in DELTA's half-PPR + TE-premium format: no receptions involved.)
s["fpts_pass"] = 4 * s["ptd"] + s["pyd"] / 25.0 - 2 * s["pint"]
s["fpts_rush"] = 6 * s["rtd"] + s["ryd"] / 10.0
s["fpts"] = s["fpts_pass"] + s["fpts_rush"] - 2 * s["fum"]
s["ppg"] = s["fpts"] / s["games"]
s["ppg_pass"] = s["fpts_pass"] / s["games"]
s["rush_ppg"] = s["fpts_rush"] / s["games"]
s["tdpct"] = 100.0 * s["ptd"] / s["att"].replace(0, np.nan)
s["att_pg"] = s["att"] / s["games"]

s = s[(s["att"] > 0) & (s["games"] > 0)].copy()
qual = s[s["att"] >= MIN_ATT].copy()
print(f"QB-seasons: {len(s)}   qualifying (att>={MIN_ATT}): {len(qual)}   QBs: {qual['pid'].nunique()}")

# ---- empirical-Bayes baseline (same as round 1)
car = qual.groupby("pid").agg(att=("att", "sum"), ptd=("ptd", "sum"))
p = (car["ptd"] / car["att"]).values
w = car["att"].values.astype(float)
m = float(np.average(p, weights=w))
ov = float(np.average((p - m) ** 2, weights=w))
vt = max(ov - m * (1 - m) / float(np.average(w)), 1e-7)
K = m * (1 - m) / vt - 1
A, B = m * K, (1 - m) * K
print(f"EB prior: league {100*m:.2f}%  K={K:.0f}   (round 1 found true-talent SD ~0.7pp)")


def base_of(td, att):
    return 100.0 * (A + td) / (A + B + att)


# ==================================================== PAIRS
hr("BUILD PAIRS  (year t -> t+1, both qualifying; baseline is leave-two-out)")

rows = []
for pid, gg in qual.sort_values("season").groupby("pid"):
    ix = gg.set_index("season")
    for t in ix.index:
        if (t + 1) in ix.index:
            oth = gg[(gg["season"] != t) & (gg["season"] != t + 1)]
            bs = base_of(oth["ptd"].sum(), oth["att"].sum()) if len(oth) else 100 * m
            a_, b_ = ix.loc[t], ix.loc[t + 1]
            rows.append(dict(
                pid=pid, name=a_["name"], t=int(t),
                tdpct=float(a_["tdpct"]), baseline=float(bs),
                td_gap=float(a_["tdpct"] - bs),
                ppg_now=float(a_["ppg"]), ppg_next=float(b_["ppg"]),
                d_ppg=float(b_["ppg"] - a_["ppg"]),
                ppg_pass_now=float(a_["ppg_pass"]), ppg_pass_next=float(b_["ppg_pass"]),
                d_ppg_pass=float(b_["ppg_pass"] - a_["ppg_pass"]),
                att_pg=float(a_["att_pg"]), rush_ppg=float(a_["rush_ppg"]),
                d_att_pg=float(b_["att_pg"] - a_["att_pg"]),
                d_rush_ppg=float(b_["rush_ppg"] - a_["rush_ppg"]),
            ))
P = pd.DataFrame(rows).dropna(subset=["td_gap", "d_ppg"])
P.to_csv(f"{OUT}/r2_pairs.csv", index=False)
print(f"pairs: {len(P)}   (wrote {OUT}/r2_pairs.csv)")
if len(P) < 60:
    sys.exit("too few pairs.")


def corr(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = ~(np.isnan(x) | np.isnan(y))
    return float(np.corrcoef(x[ok], y[ok])[0, 1])


# ==================================================== S1 raw signal
hr("S1  RAW SIGNAL  (does a TD% spike predict a fantasy PPG DROP next year?)")
r_ppg = corr(P["td_gap"], P["d_ppg"])
r_pass = corr(P["td_gap"], P["d_ppg_pass"])
print(f"corr(td_gap, d_PPG total)   = {r_ppg:+.3f}")
print(f"corr(td_gap, d_PPG passing) = {r_pass:+.3f}   <- if this is much stronger than total,")
print("                                       rushing is absorbing the regression (the Lamar story)")
s1 = (r_ppg <= -0.15) and (len(P) >= 100)
print(f"S1 (corr <= -0.15, n >= 100): {'PASS' if s1 else 'FAIL'}")

# sanity: is the TD% regression itself showing up in TDs?
print(f"\n[context] corr(td_gap, next-yr change in attempts/gm) = {corr(P['td_gap'], P['d_att_pg']):+.3f}")
print(f"[context] corr(td_gap, next-yr change in rush PPG)    = {corr(P['td_gap'], P['d_rush_ppg']):+.3f}")

# ==================================================== S2 incremental (OLS)
hr("S2  INCREMENTAL  (OLS: d_ppg ~ td_gap + att_pg + rush_ppg + ppg_now)")
print("    Is td_gap still negative & significant once volume/rushing/level are controlled?")
print("    If not -> it is a proxy for what DELTA already models. DO NOT SHIP.")


def ols(y, X, names):
    X = np.column_stack([np.ones(len(X))] + [np.asarray(c, float) for c in X])
    y = np.asarray(y, float)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    n, k = X.shape
    dof = max(n - k, 1)
    s2 = float(resid @ resid) / dof
    XtX_inv = np.linalg.pinv(X.T @ X)
    se = np.sqrt(np.diag(s2 * XtX_inv))
    tt = beta / se
    r2 = 1 - float(resid @ resid) / float(((y - y.mean()) ** 2).sum())
    print(f"    n={n}  R2={r2:.3f}")
    print(f"    {'term':<12}{'coef':>10}{'se':>9}{'t':>8}")
    for nm_, b_, s_, t_ in zip(["intercept"] + names, beta, se, tt):
        star = " *" if abs(t_) >= 2.0 else ""
        print(f"    {nm_:<12}{b_:>10.3f}{s_:>9.3f}{t_:>8.2f}{star}")
    return dict(zip(["intercept"] + names, beta)), dict(zip(["intercept"] + names, tt)), r2


print("\n-- total fantasy PPG --")
co, tv, _ = ols(P["d_ppg"], [P["td_gap"], P["att_pg"], P["rush_ppg"], P["ppg_now"]],
                ["td_gap", "att_pg", "rush_ppg", "ppg_now"])
s2 = (co["td_gap"] < 0) and (abs(tv["td_gap"]) >= 2.0)
print(f"    S2 (td_gap negative & |t|>=2.0): {'PASS' if s2 else 'FAIL'}")

print("\n-- passing-only PPG (diagnostic, not a gate) --")
co_p, tv_p, _ = ols(P["d_ppg_pass"], [P["td_gap"], P["att_pg"], P["rush_ppg"], P["ppg_pass_now"]],
                    ["td_gap", "att_pg", "rush_ppg", "ppg_pass_now"])
print(f"    td_gap coef on PASSING points: {co_p['td_gap']:+.3f} (t={tv_p['td_gap']:+.2f})")

# ==================================================== S3 out-of-sample lift
hr(f"S3  OUT-OF-SAMPLE LIFT  (fit t<={TRAIN_END}, test after; predict next-yr PPG)")
tr, te = P[P["t"] <= TRAIN_END], P[P["t"] > TRAIN_END]
print(f"train={len(tr)}  test={len(te)}")


def fit_pred(train, test, cols):
    Xtr = np.column_stack([np.ones(len(train))] + [train[c].values.astype(float) for c in cols])
    Xte = np.column_stack([np.ones(len(test))] + [test[c].values.astype(float) for c in cols])
    beta, *_ = np.linalg.lstsq(Xtr, train["ppg_next"].values.astype(float), rcond=None)
    return Xte @ beta


def rmse(pred, act):
    return float(np.sqrt(np.mean((np.asarray(pred, float) - np.asarray(act, float)) ** 2)))


ctrl = ["ppg_now", "att_pg", "rush_ppg"]
if len(te) >= 15:
    r_ctrl = rmse(fit_pred(tr, te, ctrl), te["ppg_next"])
    r_full = rmse(fit_pred(tr, te, ctrl + ["td_gap"]), te["ppg_next"])
    lift = 100 * (r_ctrl - r_full) / r_ctrl
    print(f"  RMSE controls only (ppg_now, att_pg, rush_ppg) : {r_ctrl:.3f}")
    print(f"  RMSE controls + td_gap                         : {r_full:.3f}   ({lift:+.1f}%)")
    s3 = lift >= 2.0
    print(f"  S3 (lift >= 2%): {'PASS' if s3 else 'FAIL'}")
else:
    s3 = False
    print("  test split too small.")

# ==================================================== effect size in plain english
hr("EFFECT SIZE  (what would this actually mean for a manager?)")
b = co["td_gap"]
print(f"OLS says: each +1.0pt of TD% above baseline -> {b:+.2f} fantasy PPG next year (all else equal).")
for gap, who in [(2.5, "Stafford 2025 (7.7% vs 5.2% base)"), (1.6, "Purdy 2025"), (0.8, "Lamar 2025")]:
    print(f"  {who:<34} gap {gap:+.1f}pt -> predicted {b*gap:+.2f} PPG next year")
print("\n(For scale: a 1.0 PPG swing at QB is roughly the gap between QB8 and QB12 in a season.)")

# ==================================================== VERDICT
hr("VERDICT")
print(f"  S1 raw signal     : {'PASS' if s1 else 'FAIL'}")
print(f"  S2 incremental    : {'PASS' if s2 else 'FAIL'}   <- the one that matters most")
print(f"  S3 OOS lift       : {'PASS' if s3 else 'FAIL'}")
print()
if s1 and s2 and s3:
    print("  ALL PASS -> TD% regression predicts fantasy decline beyond volume/rushing.")
    print("  Ship: league-mean reversion flag (round 1 showed per-QB baselines add nothing).")
    print("  NOTE: this flag WILL fire on dual-threat QBs (they revert harder). Accept that in advance.")
else:
    print("  NOT ALL PASS -> do NOT ship a TD% signal into the projection.")
    print("  TD% reverts beautifully as a RATE, but that does not translate into dynasty VALUE")
    print("  once volume and rushing are accounted for. Write it up as a null result.")
    print("  (Optional: keep it as a DISPLAY-ONLY context stat on the QB card, clearly not")
    print("   feeding the projection — but only if it is genuinely informative to a manager.)")

P.to_csv(f"{OUT}/r2_pairs.csv", index=False)
print(f"\nwrote {OUT}/r2_pairs.csv")
hr("DONE — nothing written to /data")
