#!/usr/bin/env python3
"""
DELTA research — GOAL-LINE OPPORTUNITY (does it earn a place in the model?)

BACKGROUND. The TD% study (rounds 1-2) found:
  - TD rate mean-reverts hard (~69% of the gap given back) and is only weakly
    sticky year to year (r = +0.38). Most of a big TD% year is noise.
  - BUT it added almost nothing to fantasy projection beyond production DELTA
    already models (+1.7% OOS lift; failed the 2% bar). Shown, not scored.

That failure points at the real gap. TD *conversion* is noise; TD *opportunity*
should be signal — goal-line touches are a role a coach assigns, not a coin flip.
DELTA currently stores only inside-20 counts, which lump a 19-yard-line target in
with a 1-yard-line carry. This study asks whether inside-5 (goal-line) opportunity
is (a) genuinely sticky and (b) INCREMENTAL to what DELTA already sees.

PRE-REGISTERED HYPOTHESES + SHIP CRITERIA (fixed before looking at output):

  G1 STICKINESS. GL opportunity share is a real role, not noise.
     PASS if year-to-year r(GL share) >= 0.45  -- i.e. clearly stickier than TD
     rate's 0.38. If GL share is as noisy as TD rate, it cannot be a role signal.

  G2 EXPECTED TDs. TDs regress toward opportunity, not the other way round.
     Build expected TDs from GL/RZ usage (league TD-per-GL-touch rate). PASS if
     corr(TD_over_expected, next-year change in TDs) <= -0.25 (i.e. players who
     out-scored their opportunity give it back).

  G3 INCREMENTAL  <-- THE SHIP GATE. Does GL share improve next-year fantasy PPG
     prediction BEYOND current PPG + volume? This is the exact test TD% failed.
     PASS if adding gl_share to a controls-only model (ppg_now, touches/gm,
     tgt_share) improves held-out RMSE by >= 3%.

  ALL THREE must pass to feed the projection. If G1/G2 pass but G3 fails, the
  honest outcome is the same as TD%: keep it as DISPLAY-ONLY opportunity context,
  do not score it. If G1 fails, drop the idea entirely.

OFFLINE RESEARCH ONLY. Writes study/out/. Never touches /data or the engine.

Install:  pip install nflreadpy pandas numpy
Usage:    python gl_opportunity_study.py [--seasons 2017-2025] [--train-end 2022]
          [--pos RB|WR|TE|ALL] [--te-premium 0.5] [--ppr 0.5]
"""

import os
import sys
import argparse
import traceback

import numpy as np
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("--seasons", default="2017-2025")
ap.add_argument("--train-end", type=int, default=2022)
ap.add_argument("--pos", default="ALL", help="RB, WR, TE, or ALL")
ap.add_argument("--ppr", type=float, default=0.5, help="points per reception (DELTA = half PPR)")
ap.add_argument("--te-premium", type=float, default=0.5, help="extra PPR for TEs (DELTA = +0.5)")
ap.add_argument("--min-games", type=int, default=8)
ap.add_argument("--inspect", action="store_true")
args = ap.parse_args()

lo, hi = (int(x) for x in args.seasons.split("-"))
SEASONS = list(range(lo, hi + 1))
OUT = "study/out"
os.makedirs(OUT, exist_ok=True)


def hr(t=""):
    print("\n" + "=" * 76, flush=True)
    if t:
        print(t)
        print("-" * 76, flush=True)


def corr(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = ~(np.isnan(x) | np.isnan(y))
    if ok.sum() < 3:
        return float("nan")
    return float(np.corrcoef(x[ok], y[ok])[0, 1])


def ols(y, Xcols, names, quiet=False):
    X = np.column_stack([np.ones(len(Xcols[0]))] + [np.asarray(c, float) for c in Xcols])
    y = np.asarray(y, float)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = max(X.shape[0] - X.shape[1], 1)
    s2 = float(resid @ resid) / dof
    se = np.sqrt(np.diag(s2 * np.linalg.pinv(X.T @ X)))
    tt = beta / se
    r2 = 1 - float(resid @ resid) / float(((y - y.mean()) ** 2).sum())
    if not quiet:
        print(f"    n={X.shape[0]}  R2={r2:.3f}")
        print(f"    {'term':<14}{'coef':>10}{'se':>9}{'t':>8}")
        for nm, b, s, t in zip(["intercept"] + names, beta, se, tt):
            print(f"    {nm:<14}{b:>10.3f}{s:>9.3f}{t:>8.2f}{' *' if abs(t) >= 2 else ''}")
    return dict(zip(["intercept"] + names, beta)), dict(zip(["intercept"] + names, tt))


def rmse(pred, act):
    d = np.asarray(pred, float) - np.asarray(act, float)
    return float(np.sqrt(np.nanmean(d ** 2)))


# ============================================================== LOAD
hr(f"GOAL-LINE OPPORTUNITY STUDY  {SEASONS[0]}-{SEASONS[-1]}   pos={args.pos}")

try:
    import nflreadpy as nfl
    print(f"backend: nflreadpy {getattr(nfl, '__version__', '?')}")
except ImportError:
    sys.exit("pip install nflreadpy pandas numpy")


def topd(x):
    return x.to_pandas() if hasattr(x, "to_pandas") else pd.DataFrame(x)


print("loading weekly player stats...")
ps = topd(nfl.load_player_stats(seasons=SEASONS))
print("loading play-by-play (for goal-line / red-zone usage)... this is the slow part")
pbp = topd(nfl.load_pbp(seasons=SEASONS))
print(f"  player stats: {len(ps):,} rows | pbp: {len(pbp):,} rows")

if args.inspect:
    print("\nplayer stats cols:", sorted(ps.columns))
    print("\npbp cols (subset):", [c for c in sorted(pbp.columns) if "yard" in c or "player" in c or "rush" in c or "pass" in c][:40])
    sys.exit(0)


def find(f, *c, required=True):
    for x in c:
        if x in f.columns:
            return x
    low = {k.lower(): k for k in f.columns}
    for x in c:
        if x.lower() in low:
            return low[x.lower()]
    if required:
        print(f"FATAL: none of {c} found. Available: {sorted(f.columns)[:50]}")
        sys.exit(1)
    return None


P = {
    "pid": find(ps, "player_id", "gsis_id"),
    "name": find(ps, "player_display_name", "player_name"),
    "pos": find(ps, "position", "position_group"),
    "team": find(ps, "recent_team", "team", "team_abbr"),
    "season": find(ps, "season"),
    "stype": find(ps, "season_type", required=False),
    "rec": find(ps, "receptions", "rec"),
    "recyd": find(ps, "receiving_yards"),
    "rectd": find(ps, "receiving_tds"),
    "tgt": find(ps, "targets"),
    "car": find(ps, "carries", "rushing_attempts"),
    "rushyd": find(ps, "rushing_yards"),
    "rushtd": find(ps, "rushing_tds"),
}

d = ps.copy()
if P["stype"]:
    d = d[d[P["stype"]].astype(str).str.upper().isin(["REG", "REGULAR"])]
POSES = ["RB", "WR", "TE"] if args.pos == "ALL" else [args.pos]
d = d[d[P["pos"]].astype(str).str.upper().isin(POSES)]

num = ["rec", "recyd", "rectd", "tgt", "car", "rushyd", "rushtd"]
agg = {P[k]: "sum" for k in num}
s = d.groupby([P["pid"], P["season"]]).agg(agg).reset_index()
g = d.groupby([P["pid"], P["season"]]).size().rename("games").reset_index()
meta = d.groupby([P["pid"], P["season"]]).agg(
    name=(P["name"], "last"), pos=(P["pos"], "last"), team=(P["team"], "last")).reset_index()
s = s.merge(g, on=[P["pid"], P["season"]]).merge(meta, on=[P["pid"], P["season"]])
s = s.rename(columns={P["pid"]: "pid", P["season"]: "season", **{P[k]: k for k in num}})
s[num] = s[num].fillna(0)

# ---- fantasy points in DELTA's format (half-PPR + TE premium), computed from components
PPR, TEP = args.ppr, args.te_premium
s["rec_pts"] = s["rec"] * (PPR + np.where(s["pos"].str.upper() == "TE", TEP, 0.0))
s["fpts"] = (s["recyd"] / 10 + s["rectd"] * 6 + s["rec_pts"] +
             s["rushyd"] / 10 + s["rushtd"] * 6)
s["ppg"] = s["fpts"] / s["games"]
s["td"] = s["rectd"] + s["rushtd"]
s["touch_pg"] = (s["car"] + s["tgt"]) / s["games"]

# ============================================================== GL / RZ from pbp
hr("EXTRACT GOAL-LINE (inside 5) AND RED-ZONE (inside 20) OPPORTUNITY")

B = {
    "yl": find(pbp, "yardline_100"),
    "season": find(pbp, "season"),
    "posteam": find(pbp, "posteam"),
    "rec_id": find(pbp, "receiver_player_id"),
    "rush_id": find(pbp, "rusher_player_id"),
    "pass_a": find(pbp, "pass_attempt", "pass", required=False),
    "rush_a": find(pbp, "rush_attempt", "rush", required=False),
}
if "season_type" in pbp.columns:
    pbp = pbp[pbp["season_type"].astype(str).str.upper().isin(["REG", "REGULAR"])]


def usage(frame, tag):
    """player + team goal-line/red-zone target & carry counts -> shares (by player_id, no name matching)."""
    t = frame[frame[B["rec_id"]].notna()]
    if B["pass_a"]:
        t = t[t[B["pass_a"]] == 1]
    r = frame[frame[B["rush_id"]].notna()]
    if B["rush_a"]:
        r = r[r[B["rush_a"]] == 1]

    ptg = t.groupby([B["rec_id"], B["season"]]).size().rename(f"{tag}_tgt").reset_index()
    ptg = ptg.rename(columns={B["rec_id"]: "pid", B["season"]: "season"})
    pcr = r.groupby([B["rush_id"], B["season"]]).size().rename(f"{tag}_car").reset_index()
    pcr = pcr.rename(columns={B["rush_id"]: "pid", B["season"]: "season"})

    ttg = t.groupby([B["posteam"], B["season"]]).size().rename(f"team_{tag}_tgt").reset_index()
    ttg = ttg.rename(columns={B["posteam"]: "team", B["season"]: "season"})
    tcr = r.groupby([B["posteam"], B["season"]]).size().rename(f"team_{tag}_car").reset_index()
    tcr = tcr.rename(columns={B["posteam"]: "team", B["season"]: "season"})
    return ptg, pcr, ttg, tcr


gl_tg, gl_cr, gl_ttg, gl_tcr = usage(pbp[pbp[B["yl"]] <= 5], "gl")
rz_tg, rz_cr, rz_ttg, rz_tcr = usage(pbp[pbp[B["yl"]] <= 20], "rz")
print(f"goal-line: {len(gl_tg)} receiver-seasons, {len(gl_cr)} rusher-seasons")
print(f"red zone : {len(rz_tg)} receiver-seasons, {len(rz_cr)} rusher-seasons")

for f in (gl_tg, gl_cr, rz_tg, rz_cr):
    s = s.merge(f, on=["pid", "season"], how="left")
for f in (gl_ttg, gl_tcr, rz_ttg, rz_tcr):
    s = s.merge(f, on=["team", "season"], how="left")
for c in ["gl_tgt", "gl_car", "rz_tgt", "rz_car"]:
    s[c] = s[c].fillna(0)

# a player's GL opportunity = his share of the team's goal-line touches (targets + carries)
s["gl_touch"] = s["gl_tgt"] + s["gl_car"]
s["team_gl_touch"] = s["team_gl_tgt"].fillna(0) + s["team_gl_car"].fillna(0)
s["gl_share"] = np.where(s["team_gl_touch"] > 0, s["gl_touch"] / s["team_gl_touch"], np.nan)
s["rz_touch"] = s["rz_tgt"] + s["rz_car"]
s["team_rz_touch"] = s["team_rz_tgt"].fillna(0) + s["team_rz_car"].fillna(0)
s["rz_share"] = np.where(s["team_rz_touch"] > 0, s["rz_touch"] / s["team_rz_touch"], np.nan)
s["gl_touch_pg"] = s["gl_touch"] / s["games"]

q = s[(s["games"] >= args.min_games) & s["gl_share"].notna()].copy()
print(f"\nqualifying player-seasons (>= {args.min_games} games): {len(q)}   players: {q['pid'].nunique()}")

# ============================================================== G1 stickiness
hr("G1  STICKINESS — is goal-line opportunity a ROLE, or is it noise like TD rate?")

q = q.sort_values(["pid", "season"])
pairs = []
for pid, gg in q.groupby("pid"):
    ix = gg.set_index("season")
    for t in ix.index:
        if (t + 1) in ix.index:
            a, b = ix.loc[t], ix.loc[t + 1]
            pairs.append(dict(
                pid=pid, name=a["name"], pos=a["pos"], t=int(t),
                gl_share=a["gl_share"], gl_share_next=b["gl_share"],
                rz_share=a["rz_share"], rz_share_next=b["rz_share"],
                gl_touch=a["gl_touch"], rz_touch=a["rz_touch"],
                td=a["td"], td_next=b["td"], td_pg=a["td"] / a["games"], td_pg_next=b["td"] / b["games"],
                ppg_now=a["ppg"], ppg_next=b["ppg"],
                touch_pg=a["touch_pg"], tgt=a["tgt"], games=a["games"],
            ))
PR = pd.DataFrame(pairs)
PR.to_csv(f"{OUT}/gl_pairs.csv", index=False)
print(f"consecutive pairs: {len(PR)}  (wrote {OUT}/gl_pairs.csv)")
if len(PR) < 60:
    sys.exit("too few pairs")

r_gl = corr(PR["gl_share"], PR["gl_share_next"])
r_rz = corr(PR["rz_share"], PR["rz_share_next"])
r_tdpg = corr(PR["td_pg"], PR["td_pg_next"])
print(f"  year-to-year r, GOAL-LINE share : {r_gl:+.3f}")
print(f"  year-to-year r, RED-ZONE share  : {r_rz:+.3f}")
print(f"  year-to-year r, TD/game         : {r_tdpg:+.3f}   <- the noisy thing we are trying to beat")
print(f"  (TD RATE stickiness from the QB study was +0.38)")
g1 = r_gl >= 0.45
print(f"  G1 (GL share r >= 0.45): {'PASS' if g1 else 'FAIL'}")
for pos in sorted(PR["pos"].unique()):
    sub = PR[PR["pos"] == pos]
    if len(sub) > 20:
        print(f"     {pos}: r={corr(sub['gl_share'], sub['gl_share_next']):+.3f}  (n={len(sub)})")

# ============================================================== G2 expected TDs
hr("G2  EXPECTED TDs — do TDs regress toward OPPORTUNITY?")
# league TD rate per goal-line touch and per red-zone touch, fit on TRAIN years only
tr_mask = q["season"] <= args.train_end
lg_gl = float(q.loc[tr_mask, "td"].sum() / max(q.loc[tr_mask, "gl_touch"].sum(), 1))
lg_rz = float(q.loc[tr_mask, "td"].sum() / max(q.loc[tr_mask, "rz_touch"].sum(), 1))
print(f"league TDs per goal-line touch: {lg_gl:.3f}   per red-zone touch: {lg_rz:.3f}")

# expected TDs = blend of GL and RZ opportunity (GL weighted, it is the sharper signal)
PR["xtd"] = 0.65 * (PR["gl_touch"] * lg_gl) + 0.35 * (PR["rz_touch"] * lg_rz)
PR["td_oe"] = PR["td"] - PR["xtd"]          # TDs over expected: + = out-scored his opportunity
PR["d_td"] = PR["td_next"] - PR["td"]

r_oe = corr(PR["td_oe"], PR["d_td"])
print(f"  corr(TDs over expected, next-year change in TDs) = {r_oe:+.3f}")
print(f"  corr(this-yr TDs,        next-year change in TDs) = {corr(PR['td'], PR['d_td']):+.3f}")
print(f"  corr(expected TDs,       NEXT-year TDs)           = {corr(PR['xtd'], PR['td_next']):+.3f}")
print(f"  corr(actual TDs,         NEXT-year TDs)           = {corr(PR['td'], PR['td_next']):+.3f}")
print("    ^ if EXPECTED beats ACTUAL at predicting next year, opportunity > outcome. That is the thesis.")
g2 = r_oe <= -0.25
print(f"  G2 (corr <= -0.25): {'PASS' if g2 else 'FAIL'}")

# ============================================================== G3 incremental (SHIP GATE)
hr("G3  INCREMENTAL  <-- SHIP GATE.  Does GL share add lift BEYOND what DELTA already models?")
print("    (This is the exact test TD% failed: +1.7% vs a 2% bar.)")

PR = PR.dropna(subset=["gl_share", "ppg_now", "ppg_next", "touch_pg"])
print("\n-- OLS: next-year PPG ~ controls + gl_share --")
co, tv = ols(PR["ppg_next"], [PR["ppg_now"], PR["touch_pg"], PR["gl_share"]],
             ["ppg_now", "touch_pg", "gl_share"])

train, test = PR[PR["t"] <= args.train_end], PR[PR["t"] > args.train_end]
print(f"\ntrain={len(train)}  test={len(test)}")


def fitpred(tr, te, cols):
    Xtr = np.column_stack([np.ones(len(tr))] + [tr[c].values.astype(float) for c in cols])
    Xte = np.column_stack([np.ones(len(te))] + [te[c].values.astype(float) for c in cols])
    b, *_ = np.linalg.lstsq(Xtr, tr["ppg_next"].values.astype(float), rcond=None)
    return Xte @ b


g3 = False
if len(test) >= 25:
    ctrl = ["ppg_now", "touch_pg"]
    r_ctrl = rmse(fitpred(train, test, ctrl), test["ppg_next"])
    r_gl_m = rmse(fitpred(train, test, ctrl + ["gl_share"]), test["ppg_next"])
    r_both = rmse(fitpred(train, test, ctrl + ["gl_share", "td_oe"]), test["ppg_next"])
    lift = 100 * (r_ctrl - r_gl_m) / r_ctrl
    lift2 = 100 * (r_ctrl - r_both) / r_ctrl
    print(f"  RMSE controls only (ppg_now, touch_pg)      : {r_ctrl:.3f}")
    print(f"  RMSE + gl_share                             : {r_gl_m:.3f}   ({lift:+.1f}%)")
    print(f"  RMSE + gl_share + TD-over-expected          : {r_both:.3f}   ({lift2:+.1f}%)")
    g3 = lift >= 3.0 or lift2 >= 3.0
    print(f"  G3 (>= 3% lift): {'PASS' if g3 else 'FAIL'}")
else:
    print("  test split too small")

# per-position lift (RB goal-line usage should matter most)
print("\n  per-position OOS lift from gl_share:")
for pos in sorted(PR["pos"].unique()):
    trp, tep = train[train["pos"] == pos], test[test["pos"] == pos]
    if len(trp) >= 40 and len(tep) >= 15:
        rc = rmse(fitpred(trp, tep, ["ppg_now", "touch_pg"]), tep["ppg_next"])
        rg = rmse(fitpred(trp, tep, ["ppg_now", "touch_pg", "gl_share"]), tep["ppg_next"])
        print(f"     {pos}: controls {rc:.3f} -> +gl_share {rg:.3f}   ({100*(rc-rg)/rc:+.1f}%)   n_test={len(tep)}")

# ============================================================== current reads
hr(f"CURRENT READS ({int(q['season'].max())}) — biggest TD luck gaps")
latest = q[q["season"] == q["season"].max()].copy()
latest["xtd"] = 0.65 * (latest["gl_touch"] * lg_gl) + 0.35 * (latest["rz_touch"] * lg_rz)
latest["td_oe"] = latest["td"] - latest["xtd"]
sh = latest[latest["gl_touch"] >= 3].sort_values("td_oe", ascending=False)
print("OUT-SCORED his opportunity (TD regression risk -> SELL):")
for _, r in sh.head(8).iterrows():
    print(f"  {r['name']:<24}{r['pos']:<4} {int(r['td']):>2} TD vs {r['xtd']:.1f} expected  (GL touches {int(r['gl_touch'])}, share {100*r['gl_share']:.0f}%)")
print("UNDER-SCORED his opportunity (positive regression -> BUY):")
for _, r in sh.tail(8).iloc[::-1].iterrows():
    print(f"  {r['name']:<24}{r['pos']:<4} {int(r['td']):>2} TD vs {r['xtd']:.1f} expected  (GL touches {int(r['gl_touch'])}, share {100*r['gl_share']:.0f}%)")
sh.to_csv(f"{OUT}/gl_current_reads.csv", index=False)

# ============================================================== verdict
hr("VERDICT")
print(f"  G1 stickiness  : {'PASS' if g1 else 'FAIL'}")
print(f"  G2 expected TDs: {'PASS' if g2 else 'FAIL'}")
print(f"  G3 INCREMENTAL : {'PASS' if g3 else 'FAIL'}   <- ship gate")
print()
if g1 and g2 and g3:
    print("  ALL PASS -> goal-line opportunity adds signal DELTA does not already have.")
    print("  Wire gl_share / TD-over-expected into the projection (model change -> ledger).")
elif g1 and g2:
    print("  G1+G2 pass, G3 fails -> the football is TRUE (opportunity is sticky, TDs regress")
    print("  toward it) but DELTA already captures the fantasy consequence via production.")
    print("  Same outcome as TD%: ship as DISPLAY-ONLY context (a 'TD luck' read on the card),")
    print("  do NOT feed the projection.")
else:
    print("  G1 or G2 failed -> the premise does not hold. Write up as a null result.")
print(f"\nwrote {OUT}/gl_pairs.csv and {OUT}/gl_current_reads.csv — nothing written to /data")
