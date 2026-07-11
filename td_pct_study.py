#!/usr/bin/env python3
"""
DELTA research study — QB passing TD% mean reversion (2017-2025).  [v2, hardened]

OFFLINE RESEARCH ONLY. Writes to study/out/, never to /data. Nothing here ships
to the DELTA interface. Product outcome (if it validates) is at most:
one pipeline field (pass_att) + one derived per-QB "sustainability" signal.

v2: nfl_data_py is DEPRECATED (nflverse moved to nflreadpy). This version tries
nflreadpy first, falls back to nfl_data_py, aggregates from WEEKLY data (most
stable schema across both), auto-discovers column names, and prints diagnostics
and tracebacks to stdout so any failure lands in the report.

Install:  pip install nflreadpy pandas numpy     (fallback: nfl_data_py)
Usage:    python td_pct_study.py [--inspect] [--rz] [--min-att N] [--train-end YYYY]
          --inspect : print available columns and exit (diagnose schema issues)
"""

import os
import sys
import argparse
import traceback

import numpy as np
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("--inspect", action="store_true", help="print available columns and exit")
ap.add_argument("--rz", action="store_true", help="also pull red-zone context (heavy)")
ap.add_argument("--min-att", type=int, default=200, help="qualifying-season attempt floor")
ap.add_argument("--train-end", type=int, default=2022, help="fit on t<=this, test after")
ap.add_argument("--seasons", type=str, default="2017-2025")
args = ap.parse_args()

lo, hi = (int(x) for x in args.seasons.split("-"))
SEASONS = list(range(lo, hi + 1))
MIN_ATT = args.min_att
TRAIN_END = args.train_end
OUT = "study/out"
os.makedirs(OUT, exist_ok=True)


def hr(t=""):
    print("\n" + "=" * 74, flush=True)
    if t:
        print(t)
        print("-" * 74, flush=True)


# ==================================================== LOAD (backend-agnostic)
hr(f"LOADING QB SEASONS {SEASONS[0]}-{SEASONS[-1]}  (min_att={MIN_ATT}, train<={TRAIN_END})")

raw = None
backend = None
nflread = None
nfl = None

try:
    import nflreadpy as nflread
    print(f"backend: nflreadpy {getattr(nflread, '__version__', '?')}")
    dat = nflread.load_player_stats(seasons=SEASONS)
    raw = dat.to_pandas() if hasattr(dat, "to_pandas") else pd.DataFrame(dat)
    backend = "nflreadpy"
except Exception as e:
    print(f"nflreadpy unavailable/failed -> {type(e).__name__}: {e}")
    print("falling back to nfl_data_py (deprecated)...")
    try:
        import nfl_data_py as nfl
        print(f"backend: nfl_data_py {getattr(nfl, '__version__', '?')}")
        raw = nfl.import_weekly_data(SEASONS)
        backend = "nfl_data_py"
    except Exception:
        print("\nFATAL: could not load data from either backend.\n")
        traceback.print_exc(file=sys.stdout)
        sys.exit("Install:  pip install nflreadpy   (or)   pip install nfl_data_py")

print(f"loaded {len(raw):,} rows x {len(raw.columns)} cols via {backend}")


def find(frame, *cands, required=True, label=""):
    """Resolve a column name across nflverse schema versions."""
    for c in cands:
        if c in frame.columns:
            return c
    low = {c.lower(): c for c in frame.columns}
    for c in cands:
        if c.lower() in low:
            return low[c.lower()]
    for c in cands:
        for col in frame.columns:
            if c.lower() in col.lower():
                return col
    if required:
        print(f"\nFATAL: no column found for '{label or cands[0]}'. Tried: {cands}")
        print(f"Available columns ({len(frame.columns)}):")
        for c in sorted(frame.columns):
            print(f"    {c}")
        sys.exit(1)
    return None


if args.inspect:
    hr("INSPECT — available columns")
    for c in sorted(raw.columns):
        print(f"  {c}")
    print(f"\nrows: {len(raw):,}\n\nsample row:")
    print(raw.head(1).T.to_string())
    sys.exit(0)

C = {
    "pid": find(raw, "player_id", "gsis_id", label="player id"),
    "season": find(raw, "season"),
    "stype": find(raw, "season_type", required=False),
    "pos": find(raw, "position", "position_group", label="position"),
    "name": find(raw, "player_display_name", "player_name", "display_name", label="name"),
    "att": find(raw, "attempts", "passing_attempts", "pass_attempts", "pass_att", label="pass attempts"),
    "ptd": find(raw, "passing_tds", "pass_touchdowns", "pass_td", label="passing TDs"),
}
C["pint"] = find(raw, "passing_interceptions", "interceptions", "pass_int", required=False)
C["ratt"] = find(raw, "carries", "rushing_attempts", "rush_att", required=False)
C["rtd"] = find(raw, "rushing_tds", "rush_td", required=False)

print("\nresolved columns:")
for k, v in C.items():
    print(f"  {k:<7} -> {v}")

d = raw.copy()
if C["stype"]:
    n0 = len(d)
    d = d[d[C["stype"]].astype(str).str.upper().isin(["REG", "REGULAR"])]
    print(f"\nfiltered to REG season: {n0:,} -> {len(d):,} rows")

d = d[d[C["pos"]].astype(str).str.upper().str.contains("QB", na=False)]
print(f"QB rows: {len(d):,}")

agg = {C["att"]: "sum", C["ptd"]: "sum"}
for k in ("pint", "ratt", "rtd"):
    if C[k]:
        agg[C[k]] = "sum"

season = d.groupby([C["pid"], C["season"]]).agg(agg).reset_index()
games = d.groupby([C["pid"], C["season"]]).size().rename("games").reset_index()
names = d.groupby([C["pid"], C["season"]])[C["name"]].last().reset_index()
season = season.merge(games, on=[C["pid"], C["season"]]).merge(names, on=[C["pid"], C["season"]])
season = season.rename(columns={C["pid"]: "player_id", C["season"]: "season",
                                C["name"]: "name", C["att"]: "att", C["ptd"]: "ptd"})
for key, nm in (("pint", "pint"), ("ratt", "rush_att"), ("rtd", "rush_td")):
    if C[key]:
        season = season.rename(columns={C[key]: nm})
    else:
        season[nm] = np.nan

season = season[season["att"] > 0].copy()
season["tdpct"] = 100.0 * season["ptd"] / season["att"]
print(f"QB-seasons: {len(season)}   unique QBs: {season['player_id'].nunique()}")

qual = season[season["att"] >= MIN_ATT].copy()
print(f"qualifying (att>={MIN_ATT}): {len(qual)}   unique QBs: {qual['player_id'].nunique()}")
if len(qual) < 40:
    print("WARNING: very few qualifying seasons — check attempt floor / data load.")

lg = season.groupby("season").apply(lambda g: 100 * g["ptd"].sum() / g["att"].sum())
print("\nLeague TD% by season (attempt-weighted):")
print("  " + "   ".join(f"{int(y)}:{v:.2f}" for y, v in lg.items()))

# ==================================================== EMPIRICAL-BAYES BASELINE
hr("EMPIRICAL-BAYES BASELINE  (TD ~ Binomial(att, p_i),  p_i ~ Beta(a,b))")

career = qual.groupby("player_id").agg(att=("att", "sum"), ptd=("ptd", "sum"),
                                       n=("season", "count"), name=("name", "last"))
p = (career["ptd"] / career["att"]).values
w = career["att"].values.astype(float)
m = float(np.average(p, weights=w))
obs_var = float(np.average((p - m) ** 2, weights=w))
v_true = max(obs_var - m * (1 - m) / float(np.average(w)), 1e-7)
K = m * (1 - m) / v_true - 1
a, b = m * K, (1 - m) * K
print(f"prior mean = {100*m:.2f}%   prior strength K = {K:.0f} attempt-equivalents")
print(f"(a={a:.1f}, b={b:.1f}) -> a QB with no history is treated as ~{K:.0f} league-average attempts")


def baseline_of(td, att):
    return 100.0 * (a + td) / (a + b + att)


career["baseline"] = baseline_of(career["ptd"], career["att"])
career["career_raw"] = 100 * career["ptd"] / career["att"]
career.sort_values("att", ascending=False).to_csv(f"{OUT}/qb_tdpct_baselines.csv")
print(f"\nwrote {OUT}/qb_tdpct_baselines.csv")
print("Highest baselines (min 3 qualifying seasons) — the QBs a league-mean model would wrongly nerf:")
for _, r in career[career["n"] >= 3].sort_values("baseline", ascending=False).head(8).iterrows():
    print(f"  {r['name']:<22} n={int(r['n'])} att={int(r['att']):>5}  raw {r['career_raw']:.2f}% -> baseline {r['baseline']:.2f}%")

# ==================================================== PAIRS (leave-two-out)
hr("H1  REVERSION  (next-year change vs deviation from PERSONAL baseline; leave-two-out)")

rows = []
for pid, g in qual.sort_values("season").groupby("player_id"):
    ix = g.set_index("season")
    for t in ix.index:
        if (t + 1) in ix.index:
            oth = g[(g["season"] != t) & (g["season"] != t + 1)]
            base = baseline_of(oth["ptd"].sum(), oth["att"].sum()) if len(oth) else 100 * m
            rt, rn = ix.loc[t], ix.loc[t + 1]
            rows.append(dict(pid=pid, name=rt["name"], t=int(t), att_t=float(rt["att"]),
                             tdpct_t=float(rt["tdpct"]), tdpct_n=float(rn["tdpct"]),
                             baseline=float(base), dev=float(rt["tdpct"] - base),
                             change=float(rn["tdpct"] - rt["tdpct"]),
                             rush_pg=(float(rt["rush_att"]) / float(rt["games"])) if rt["games"] else np.nan))
pairs = pd.DataFrame(rows)
pairs.to_csv(f"{OUT}/qb_tdpct_pairs.csv", index=False)
print(f"consecutive qualifying pairs: {len(pairs)}   (wrote {OUT}/qb_tdpct_pairs.csv)")
if len(pairs) < 30:
    sys.exit("Too few pairs — lower --min-att or widen --seasons.")


def corr(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = ~(np.isnan(x) | np.isnan(y))
    return float(np.corrcoef(x[ok], y[ok])[0, 1])


r_rev = corr(pairs["dev"], pairs["change"])
r_per = corr(pairs["tdpct_t"], pairs["tdpct_n"])
slope = float(np.polyfit(pairs["dev"], pairs["change"], 1)[0])
print(f"corr(dev from baseline, next-yr change) = {r_rev:+.3f}   (negative = reversion)")
print(f"corr(TD%_t, TD%_t+1) persistence        = {r_per:+.3f}")
print(f"reversion slope = {slope:+.2f}  ->  ~{-slope*100:.0f}% of the deviation is given back next year")
print(f"H1 (corr <= -0.30 and n >= 60): {'PASS' if (r_rev <= -0.30 and len(pairs) >= 60) else 'FAIL'}")

# ==================================================== H2 BAKE-OFF
hr(f"H2  PROJECTOR BAKE-OFF  (fit t<={TRAIN_END}, test t>{TRAIN_END})   metric: RMSE of next-yr TD%")

train, test = pairs[pairs["t"] <= TRAIN_END], pairs[pairs["t"] > TRAIN_END]
pbar = 100 * m
if len(train) < 20 or len(test) < 10:
    print(f"WARNING: thin split (train={len(train)}, test={len(test)}).")

beta_L = float(np.polyfit(train["tdpct_t"] - pbar, train["tdpct_n"] - pbar, 1)[0])
beta_P = float(np.polyfit(train["tdpct_t"] - train["baseline"],
                          train["tdpct_n"] - train["baseline"], 1)[0])


def rmse(pred, act):
    dd = np.asarray(pred, float) - np.asarray(act, float)
    return float(np.sqrt(np.nanmean(dd ** 2)))


rN = rmse(test["tdpct_t"], test["tdpct_n"])
rL = rmse(pbar + beta_L * (test["tdpct_t"] - pbar), test["tdpct_n"])
rP = rmse(test["baseline"] + beta_P * (test["tdpct_t"] - test["baseline"]), test["tdpct_n"])
print(f"train={len(train)}  test={len(test)}   beta_league={beta_L:.2f}   beta_personal={beta_P:.2f}")
print(f"  RMSE naive (next = this year)    : {rN:.3f}")
print(f"  RMSE league-mean reversion       : {rL:.3f}   ({100*(rN-rL)/rN:+.1f}% vs naive)")
print(f"  RMSE PERSONAL-baseline reversion : {rP:.3f}   ({100*(rN-rP)/rN:+.1f}% vs naive, {100*(rL-rP)/rL:+.1f}% vs league)")
h2 = (rP < 0.95 * rN) and (rP < 0.95 * rL)
print(f"H2 (personal beats naive AND league by >=5%): {'PASS' if h2 else 'FAIL'}")

# ==================================================== H3 ADDED VALUE
hr("H3  ADDED VALUE  (does the baseline predict next year beyond the raw spike + volume?)")
t2 = pairs.dropna(subset=["tdpct_t", "tdpct_n", "baseline", "att_t"])
c_base, c_raw, c_att = (corr(t2["baseline"], t2["tdpct_n"]),
                        corr(t2["tdpct_t"], t2["tdpct_n"]),
                        corr(t2["att_t"], t2["tdpct_n"]))
r_ba = corr(t2["baseline"], t2["att_t"])
partial = (c_base - r_ba * c_att) / np.sqrt(max(1e-9, (1 - r_ba ** 2) * (1 - c_att ** 2)))
print(f"corr(personal baseline, next TD%)      = {c_base:+.3f}")
print(f"corr(raw this-yr TD%,   next TD%)      = {c_raw:+.3f}")
print(f"corr(attempts,          next TD%)      = {c_att:+.3f}")
print(f"PARTIAL corr(baseline, next TD% | att) = {partial:+.3f}")
print(f"H3 (partial >= 0.15 and baseline >= raw): {'PASS' if (partial >= 0.15 and c_base >= c_raw) else 'FAIL'}")
print("  (the baseline out-predicting the raw spike IS the thesis: the mean is the signal, not the spike)")

# ==================================================== H4 ARCHETYPE
hr("H4  ARCHETYPE STABILITY  (dual-threat vs pocket — Lamar guardrail)")
pa = pairs.dropna(subset=["rush_pg"])
if len(pa) >= 30:
    thr = float(pa["rush_pg"].median())
    dual, pock = pa[pa["rush_pg"] >= thr], pa[pa["rush_pg"] < thr]
    sd = float(np.polyfit(dual["dev"], dual["change"], 1)[0])
    sp = float(np.polyfit(pock["dev"], pock["change"], 1)[0])
    print(f"median rush att/game = {thr:.1f}")
    print(f"  dual-threat (>={thr:.1f}/g) n={len(dual):>3}  slope = {sd:+.2f}")
    print(f"  pocket      (< {thr:.1f}/g) n={len(pock):>3}  slope = {sp:+.2f}")
    print(f"  |diff| = {abs(sd-sp):.2f}  -> {'SPLIT the coefficient' if abs(sd - sp) > 0.15 else 'ONE coefficient is fine'}")
else:
    print("insufficient rushing data to split.")

# ==================================================== SENSITIVITY
hr("SENSITIVITY  (does reversion hold at other attempt floors?)")
for floor in (150, 200, 250):
    qq = season[season["att"] >= floor]
    dv, ch = [], []
    for pid, g in qq.sort_values("season").groupby("player_id"):
        ix = g.set_index("season")
        for t in ix.index:
            if (t + 1) in ix.index:
                oth = g[(g["season"] != t) & (g["season"] != t + 1)]
                bs = baseline_of(oth["ptd"].sum(), oth["att"].sum()) if len(oth) else 100 * m
                dv.append(ix.loc[t]["tdpct"] - bs)
                ch.append(ix.loc[t + 1]["tdpct"] - ix.loc[t]["tdpct"])
    if len(dv) >= 30:
        print(f"  att>={floor:>3}: n={len(dv):>3}  corr={corr(dv, ch):+.3f}  slope={float(np.polyfit(dv, ch, 1)[0]):+.2f}")

# ==================================================== CURRENT FLAGS
hr(f"CURRENT-QB READ  ({int(qual['season'].max())} vs personal baseline -> would-be signal)")
latest = qual[qual["season"] == qual["season"].max()].merge(career[["baseline"]], on="player_id", how="left")
latest["gap"] = latest["tdpct"] - latest["baseline"]
latest["proj_next"] = latest["baseline"] + beta_P * latest["gap"]
sh = latest.sort_values("gap", ascending=False)
print("Most ABOVE baseline — regression risk / FADE:")
for _, r in sh.head(6).iterrows():
    print(f"  {r['name']:<22} {r['tdpct']:5.1f}%  base {r['baseline']:4.1f}%  -> proj {r['proj_next']:4.1f}%  (gap {r['gap']:+.1f})")
print("Most BELOW baseline — bounce-back / BUY:")
for _, r in sh.tail(6).iloc[::-1].iterrows():
    print(f"  {r['name']:<22} {r['tdpct']:5.1f}%  base {r['baseline']:4.1f}%  -> proj {r['proj_next']:4.1f}%  (gap {r['gap']:+.1f})")
sh.to_csv(f"{OUT}/qb_tdpct_current_flags.csv", index=False)
print(f"\nwrote {OUT}/qb_tdpct_current_flags.csv")

# ==================================================== RED ZONE (optional)
if args.rz:
    hr("RED-ZONE CONTEXT  (are TD% swings driven by red-zone opportunity?)")
    try:
        if backend == "nflreadpy":
            pb = nflread.load_pbp(seasons=SEASONS)
            pb = pb.to_pandas() if hasattr(pb, "to_pandas") else pd.DataFrame(pb)
        else:
            pb = nfl.import_pbp_data(SEASONS, downcast=True)
        rz = pb[(pb["play_type"] == "pass") & (pb["yardline_100"] <= 20)]
        rz = rz.groupby(["passer_player_id", "season"]).size().rename("rz_att").reset_index()
        rz = rz.rename(columns={"passer_player_id": "player_id"})
        mm = qual.merge(rz, on=["player_id", "season"], how="left")
        mm["rz_share"] = mm["rz_att"] / mm["att"]
        print(f"corr(TD%, red-zone pass share) = {corr(mm['tdpct'], mm['rz_share']):+.3f}")
        print("  strong corr => TD% tracks RZ opportunity => pair the flag with RZ data + neutralize on OC change")
        mm.to_csv(f"{OUT}/qb_tdpct_redzone.csv", index=False)
    except Exception:
        print("red-zone pull failed (non-fatal):")
        traceback.print_exc(file=sys.stdout)

hr("DONE")
print("Outputs in study/out/. Nothing written to /data.")
print("Decision criteria: td-pct-research-spec.md §6 — H1 + H2 + H3 must pass to ship.")
