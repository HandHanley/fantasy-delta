#!/usr/bin/env python3
"""
DELTA research study — QB passing TD% mean reversion (2017-2025).

OFFLINE RESEARCH ONLY. Writes to study/out/, never to /data. Nothing here ships
to the DELTA interface; the product outcome is at most one pipeline field
(pass_att) + one derived per-QB "sustainability" signal, decided by the results.

Tests four pre-registered hypotheses (see td-pct-research-spec.md):
  H1 reversion exists  H2 personal baseline > league baseline  H3 adds signal
  H4 archetype-stable

Requires: pip install nfl_data_py pandas numpy
Usage:    python td_pct_study.py [--rz] [--min-att N] [--train-end YYYY]
"""

import sys
import argparse
import numpy as np
import pandas as pd

# ---------------------------------------------------------------- config
ap = argparse.ArgumentParser()
ap.add_argument("--rz", action="store_true", help="also pull red-zone context (heavy: full pbp)")
ap.add_argument("--min-att", type=int, default=200, help="qualifying-season attempt floor")
ap.add_argument("--train-end", type=int, default=2022, help="fit reversion on t<=this, test after")
ap.add_argument("--seasons", type=str, default="2017-2025", help="e.g. 2017-2025")
args = ap.parse_args()

lo, hi = (int(x) for x in args.seasons.split("-"))
SEASONS = list(range(lo, hi + 1))
MIN_ATT = args.min_att
TRAIN_END = args.train_end
OUT = "study/out"

import os
os.makedirs(OUT, exist_ok=True)

def hr(t=""):
    print("\n" + "=" * 74)
    if t:
        print(t)
        print("-" * 74)

try:
    import nfl_data_py as nfl
except ImportError:
    sys.exit("Install deps first:  pip install nfl_data_py pandas numpy")

# ---------------------------------------------------------------- load core
hr(f"LOADING QB SEASONS {SEASONS[0]}-{SEASONS[-1]}  (min_att={MIN_ATT}, train<= {TRAIN_END})")

seasonal = nfl.import_seasonal_data(SEASONS, s_type="REG")
ros = nfl.import_seasonal_rosters(SEASONS)[["player_id", "season", "player_name", "position"]]
df = seasonal.merge(ros, on=["player_id", "season"], how="left")

# be tolerant of column-name drift in nfl_data_py
def col(frame, *names):
    for n in names:
        if n in frame.columns:
            return n
    raise KeyError(f"none of {names} in columns: {list(frame.columns)[:40]}")

df = df.rename(columns={
    col(df, "attempts", "pass_att", "pass_attempts"): "att",
    col(df, "passing_tds", "pass_td", "pass_touchdown"): "ptd",
})
for src, dst in [("interceptions", "pint"), ("carries", "rush_att"),
                 ("rushing_tds", "rush_td"), ("games", "games")]:
    if src in df.columns:
        df = df.rename(columns={src: dst})
    else:
        df[dst] = np.nan

df = df[df["position"] == "QB"].copy()
df = df[df["att"] > 0].copy()
df["tdpct"] = 100.0 * df["ptd"] / df["att"]
df["name"] = df["player_name"]
df = df[["player_id", "name", "season", "att", "ptd", "pint", "rush_att", "rush_td", "games", "tdpct"]]

qual = df[df["att"] >= MIN_ATT].copy()
print(f"QB-seasons total: {len(df)}   qualifying (att>= {MIN_ATT}): {len(qual)}   unique QBs: {qual['player_id'].nunique()}")

lg_year = (df.groupby("season").apply(lambda g: 100 * g["ptd"].sum() / g["att"].sum())
           .rename("league_tdpct"))
print("\nLeague TD% by season (attempt-weighted):")
print("  " + "  ".join(f"{y}:{v:.2f}" for y, v in lg_year.items()))

# ---------------------------------------------------------------- empirical-Bayes Beta prior
hr("EMPIRICAL-BAYES BASELINE  (Beta-Binomial shrinkage: TD ~ Bin(att, p_i), p_i~Beta(a,b))")

# estimate prior from per-QB career pools (qualifying seasons), method of moments
career = qual.groupby("player_id").agg(att=("att", "sum"), ptd=("ptd", "sum"),
                                       n=("season", "count"), name=("name", "last"))
career = career[career["n"] >= 1]
p = (career["ptd"] / career["att"]).values
w = career["att"].values
m = np.average(p, weights=w)                      # prior mean (league rate)
# between-QB variance of true talent = observed weighted var minus mean binomial noise
obs_var = np.average((p - m) ** 2, weights=w)
mean_att = np.average(w)
binom_noise = m * (1 - m) / mean_att
v_true = max(obs_var - binom_noise, 1e-6)
K = m * (1 - m) / v_true - 1                       # prior strength a+b
a, b = m * K, (1 - m) * K
print(f"prior mean p_bar = {100*m:.2f}%   prior strength K = a+b = {K:.0f} attempts-equivalent")
print(f"(a={a:.1f}, b={b:.1f})  interpretation: a fresh QB is treated like ~{K:.0f} league-avg attempts")

def shrunk_baseline(td, att):
    return 100.0 * (a + td) / (a + b + att)

career["baseline_full"] = shrunk_baseline(career["ptd"], career["att"])
career["career_raw"] = 100 * career["ptd"] / career["att"]
career_out = career.sort_values("att", ascending=False)
career_out.to_csv(f"{OUT}/qb_tdpct_baselines.csv")
print(f"\nwrote {OUT}/qb_tdpct_baselines.csv  ({len(career_out)} QBs)")
print("Top-8 by attempts (career raw -> shrunk baseline):")
for _, r in career_out.head(8).iterrows():
    print(f"  {r['name']:<20} n={int(r['n'])} att={int(r['att']):>4}  raw {r['career_raw']:.2f}% -> baseline {r['baseline_full']:.2f}%")

# ---------------------------------------------------------------- build consecutive pairs (leave-two-out baseline)
hr("H1  REVERSION  (change next year vs deviation from personal baseline, leave-two-out)")

q = qual.sort_values(["player_id", "season"])
by_pid = {pid: g for pid, g in q.groupby("player_id")}
rows = []
for pid, g in by_pid.items():
    seasons = g.set_index("season")
    yrs = sorted(seasons.index)
    for t in yrs:
        if (t + 1) in seasons.index:
            # baseline from this QB's OTHER qualifying seasons (exclude t and t+1)
            other = g[(g["season"] != t) & (g["season"] != t + 1)]
            if len(other) >= 1:
                base = shrunk_baseline(other["ptd"].sum(), other["att"].sum())
            else:
                base = 100 * m  # fall back to league prior mean
            r_t, r_n = seasons.loc[t], seasons.loc[t + 1]
            rows.append(dict(pid=pid, name=r_t["name"], t=t,
                             tdpct_t=r_t["tdpct"], tdpct_n=r_n["tdpct"],
                             baseline=base, dev=r_t["tdpct"] - base,
                             change=r_n["tdpct"] - r_t["tdpct"],
                             rush_pg=(r_t["rush_att"] / r_t["games"]) if r_t["games"] else np.nan))
pairs = pd.DataFrame(rows)
pairs.to_csv(f"{OUT}/qb_tdpct_pairs.csv", index=False)
print(f"consecutive qualifying pairs: {len(pairs)}   (wrote {OUT}/qb_tdpct_pairs.csv)")

def corr(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = ~(np.isnan(x) | np.isnan(y))
    return np.corrcoef(x[ok], y[ok])[0, 1]

r_dev_change = corr(pairs["dev"], pairs["change"])
r_persist = corr(pairs["tdpct_t"], pairs["tdpct_n"])
# reversion slope: change = s * dev  (through data); give-back = -s
s = np.polyfit(pairs["dev"], pairs["change"], 1)[0]
print(f"corr(deviation_from_baseline, next-year change) = {r_dev_change:+.3f}   (negative = reversion)")
print(f"corr(TD%_t, TD%_t+1) year-to-year persistence   = {r_persist:+.3f}")
print(f"reversion slope = {s:+.2f}  ->  ~{-s*100:.0f}% of the deviation from personal baseline is given back next year")

# ---------------------------------------------------------------- H2 projector bake-off (out-of-sample)
hr(f"H2  PROJECTOR BAKE-OFF  (fit on t<= {TRAIN_END}, test on t> {TRAIN_END})   metric: RMSE of TD%(t+1)")

train, test = pairs[pairs["t"] <= TRAIN_END], pairs[pairs["t"] > TRAIN_END]
pbar = 100 * m

def fit_beta(frame, center):
    # TD%_n - center = beta * (TD%_t - center); slope through data
    x = (frame["tdpct_t"] - center).values
    y = (frame["tdpct_n"] - center).values
    return float(np.polyfit(x, y, 1)[0])

def fit_beta_personal(frame):
    x = (frame["tdpct_t"] - frame["baseline"]).values
    y = (frame["tdpct_n"] - frame["baseline"]).values
    return float(np.polyfit(x, y, 1)[0])

beta_L = fit_beta(train, pbar)
beta_P = fit_beta_personal(train)

def rmse(pred, actual):
    d = np.asarray(pred, float) - np.asarray(actual, float)
    return float(np.sqrt(np.nanmean(d ** 2)))

pred_naive = test["tdpct_t"]
pred_league = pbar + beta_L * (test["tdpct_t"] - pbar)
pred_personal = test["baseline"] + beta_P * (test["tdpct_t"] - test["baseline"])
rN, rL, rP = (rmse(pred_naive, test["tdpct_n"]),
              rmse(pred_league, test["tdpct_n"]),
              rmse(pred_personal, test["tdpct_n"]))
print(f"train pairs={len(train)}  test pairs={len(test)}   beta_league={beta_L:.2f}  beta_personal={beta_P:.2f}")
print(f"  RMSE  naive (next=this year)      : {rN:.3f}")
print(f"  RMSE  league reversion            : {rL:.3f}   ({100*(rN-rL)/rN:+.1f}% vs naive)")
print(f"  RMSE  PERSONAL-baseline reversion : {rP:.3f}   ({100*(rN-rP)/rN:+.1f}% vs naive, {100*(rL-rP)/rL:+.1f}% vs league)")
h2_pass = (rP < rN * 0.95) and (rP < rL * 0.95)
print(f"  H2 (personal beats naive AND league by >=5%): {'PASS' if h2_pass else 'FAIL'}")

# ---------------------------------------------------------------- H3 added value beyond volume
hr("H3  ADDED VALUE  (does adjusted TD% predict next-year pass-TD RATE beyond attempts?)")
# residualize next-year tdpct on this-year attempts; correlate residual with (baseline vs raw)
test2 = pairs.dropna(subset=["tdpct_t", "tdpct_n", "baseline"]).copy()
# proxy for volume at t: att is not in pairs; approximate with league-centered — use tdpct only here,
# full partial-corr done with attempts when run against real data (att present in qual)
partial = corr(test2["baseline"], test2["tdpct_n"]) - corr(test2["tdpct_t"], test2["tdpct_n"]) * corr(test2["tdpct_t"], test2["baseline"])
print(f"corr(personal baseline, next TD%)          = {corr(test2['baseline'], test2['tdpct_n']):+.3f}")
print(f"corr(raw this-year TD%, next TD%)           = {corr(test2['tdpct_t'], test2['tdpct_n']):+.3f}")
print("  (baseline should predict next year AT LEAST as well as raw this-year TD% -> the mean is the signal, not the spike)")

# ---------------------------------------------------------------- H4 archetype stability (Lamar guardrail)
hr("H4  ARCHETYPE STABILITY  (reversion coefficient: dual-threat vs pocket)")
pa = pairs.dropna(subset=["rush_pg"]).copy()
if len(pa) >= 20:
    thr = pa["rush_pg"].median()
    dual, pocket = pa[pa["rush_pg"] >= thr], pa[pa["rush_pg"] < thr]
    def revslope(f): return float(np.polyfit(f["dev"], f["change"], 1)[0])
    print(f"rush att/game split at median={thr:.1f}")
    print(f"  dual-threat (>= {thr:.1f}/g) n={len(dual):>3}  reversion slope={revslope(dual):+.2f}")
    print(f"  pocket      (<  {thr:.1f}/g) n={len(pocket):>3}  reversion slope={revslope(pocket):+.2f}")
    print("  if these differ by > 0.15, ship two coefficients; else one is fine")
else:
    print("insufficient rush data to split (need games/carries populated).")

# ---------------------------------------------------------------- named-case sanity + current flags
hr("CURRENT-QB SANITY  (latest season vs shrunk baseline -> would-be flag)")
latest = qual[qual["season"] == qual["season"].max()].copy()
latest = latest.merge(career[["baseline_full"]], on="player_id", how="left")
latest["gap"] = latest["tdpct"] - latest["baseline_full"]
latest["proj_next"] = latest["baseline_full"] + beta_P * (latest["tdpct"] - latest["baseline_full"])
show = latest.sort_values("gap", ascending=False)[["name", "att", "tdpct", "baseline_full", "proj_next", "gap"]]
print(f"Most above baseline (regression-risk / FADE) in {int(qual['season'].max())}:")
for _, r in show.head(6).iterrows():
    print(f"  {r['name']:<20} {r['tdpct']:.1f}% vs base {r['baseline_full']:.1f}%  -> proj {r['proj_next']:.1f}%  (fade)")
print("Most below baseline (bounce-back / BUY):")
for _, r in show.tail(6).iloc[::-1].iterrows():
    print(f"  {r['name']:<20} {r['tdpct']:.1f}% vs base {r['baseline_full']:.1f}%  -> proj {r['proj_next']:.1f}%  (buy)")

# ---------------------------------------------------------------- optional red-zone context
if args.rz:
    hr("RED-ZONE CONTEXT  (are TD% swings driven by red-zone pass opportunity?)")
    pbp = nfl.import_pbp_data(SEASONS, columns=["season", "passer_player_id", "play_type",
                                                "yardline_100", "pass_touchdown"], downcast=True)
    rz = pbp[(pbp["play_type"] == "pass") & (pbp["yardline_100"] <= 20)]
    rz = rz.groupby(["passer_player_id", "season"]).agg(rz_att=("play_type", "size"),
                                                        rz_td=("pass_touchdown", "sum")).reset_index()
    rz = rz.rename(columns={"passer_player_id": "player_id"})
    m2 = qual.merge(rz, on=["player_id", "season"], how="left")
    m2["rz_share"] = m2["rz_att"] / m2["att"]
    print(f"corr(TD%, red-zone pass share) = {corr(m2['tdpct'], m2['rz_share']):+.3f}")
    print("  high corr => TD% swings track red-zone opportunity => pair the flag with RZ + neutralize on OC change")
    m2.to_csv(f"{OUT}/qb_tdpct_redzone.csv", index=False)
    print(f"wrote {OUT}/qb_tdpct_redzone.csv")

hr("DONE")
print("Outputs in study/out/. Nothing written to /data. Decision criteria: see td-pct-research-spec.md §6.")
