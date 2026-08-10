#!/usr/bin/env python3
"""
DELTA — SCHEME SHIP GATE

THE QUESTION
    DELTA's projection multiplies every player by a scheme adjustment. Does that
    adjustment earn its place?

    This is the SAME gate that killed TD% mean-reversion (+1.7% lift, bar 2%) and
    goal-line opportunity (made prediction WORSE). Both were true football. Neither
    improved the forecast. The rule from NULL-RESULTS.md:

        "A signal ships ONLY if it improves out-of-sample prediction of next-year
         fantasy value beyond what DELTA's production core already captures.
         Being true football is not sufficient."

    That gate has never been pointed at the scheme adjustment itself.

WHAT IS ACTUALLY SHIPPING  (delta-engine.js, line ~4099:  net = dSys + dOc + sty.total)

    dSys   from SYS.s   hand-typed     non-QB:  +4% / +1% / -4% / -10%
    dOc    from SYS.c   hand-typed     non-QB WR: +3% / +1% / -4% / -8% / -12%
    sty    styleFactors  VALIDATED     capped at +/-4%

    Worst case, unproven WR, weak system + new coordinator:  -4% + -12% = -16%.
    Best case, WR, strong system + continuity:                +4% +  +3% =  +7%.

    A 23-point hand-typed swing sitting on top of an 8-point validated one. The
    unvalidated levers are ~3x the validated one, and they are shipping today.

WHAT CAN AND CANNOT BE TESTED

    SYS.s CANNOT be backtested. There is no historical SYS table -- it exists only as
    a current snapshot. You cannot validate a number you never recorded. That is not a
    finding about football, it is a finding about the code: a lever swinging projections
    by 10% was built in a form that makes validation impossible. (Fix: freeze it now,
    log it, and let the accuracy ledger judge it in a year. That is what the ledger is for.)

    dOc CAN be backtested, and it is the BIGGER lever (-12% vs -10%). "Did this team
    change playcallers?" is a FACT, not an opinion. playcallers.csv has it, hand-verified,
    2022-2026. No hindsight, no survivorship, no contamination.

    So this study races three horses, per position, out of sample:

      A.  OC CHANGE      -- the dOc lever. Does a new playcaller actually cost a player
                            fantasy points? The engine says up to -12%. What does the data say?
      B.  FINGERPRINT    -- the matrix the crux study said was buildable (alpha = 0.46).
                            Predict the team's style shift from the ARRIVING coach's history,
                            and use the position-relevant slice of it.
      C.  NOTHING        -- the control. The production core alone.

    Whoever beats the control by >= 2% out of sample, wins. If nobody does, the levers
    come out of the engine before the freeze.

THE COEFFICIENT IS THE POINT
    A pass/fail tells you nothing you can act on. The coefficient tells you the SIZE.
    If the engine applies -12% and the data says -1%, that is a 12x overcorrection and
    you can fix it today. That is the number this study exists to produce.

USAGE
    python scheme_ship_gate_study.py
    python scheme_ship_gate_study.py --seasons 2022-2025
    python test_scheme_ship_gate.py          # self-test on synthetic data
"""

import argparse
import sys
import numpy as np
import pandas as pd

from playcaller_crux_study import (
    prepare, build_style_table, zscale, zvec, active_metrics, load_data as load_crux,
)

# --------------------------------------------------------------------------------------
# PRE-REGISTRATION.  Printed before a single row is read.
# --------------------------------------------------------------------------------------

PREREG = """
================================================================================
PRE-REGISTERED CRITERIA  (fixed before the data is seen)
================================================================================

TARGET      next season's fantasy PPG, scored with DELTA's own gamefp()
            (half-PPR, TE premium +0.5 -> a TE reception is worth 1.0)

BASELINE    the production core, which DELTA already prices:
                next_ppg ~ ppg + volume_per_game + age
            Fit and reported PER POSITION. Never pooled.
            (NULL-RESULTS lesson #3: pooled correlations across positions lie.)

POPULATION  players who STAYED on the same team, >= 8 games in both years. A player who
            changes teams has his scheme change confounded with everything else.

--------------------------------------------------------------------------------
WHY THE GATE IS NOT THE USUAL 2% RMSE BAR  (decided BEFORE the run, and here is why)

    TD% and goal-line were asked "should this signal be ADDED?" Both applied to EVERY
    player, so a 2% out-of-sample RMSE bar could see them.

    dOc is different: it ALREADY SHIPS, at -12%, and it only touches the ~third of teams
    that changed playcallers. The self-test plants a PERFECTLY CORRECT -12% penalty and
    measures the resulting RMSE lift:  +1.9%.  The 2% bar would REJECT THE ENGINE'S OWN
    LEVER even if the engine were exactly right. A gate that cannot see the thing it is
    judging is not a gate.

    The question is not "should this exist." It exists. It is -12% today.
    The question is "IS -12% THE RIGHT NUMBER." That is a question about the COEFFICIENT
    AND ITS CONFIDENCE INTERVAL.

THE GATE
    Fit the coefficient. Cluster-bootstrap a 95% CI by TEAM-SEASON -- oc_change is a
    team-level feature with 6-15 players attached to it, and treating those players as
    independent would shrink the CI by roughly 3x and manufacture significance.

        CI excludes 0, and CONTAINS the engine's value  -> the hand table is RIGHT. Keep it.
        CI excludes 0, and EXCLUDES the engine's value  -> real, wrong size. SHRINK to fitted.
        CI CONTAINS 0                                   -> not distinguishable from nothing.
                                                           DELETE, or shrink to the +/-4%
                                                           band styleFactors actually earned.
        CI too wide to separate 0 from the engine       -> UNDERPOWERED. Say so. Do not pretend.

    Out-of-sample RMSE lift is still computed and reported, for continuity with the TD%
    and goal-line record. It is NOT the gate. It was never the right gate for this question.

HORSES      A  oc_change     1 if the team has a new primary playcaller, else 0
            B  fingerprint   alpha * (arriving coach's historical style - team's current
                             style), position-relevant dimension:
                                 QB -> pass rate      RB -> RB target share
                                 WR -> pass rate      TE -> TE target share

NO GOALPOST MOVING. This gate is fixed now, before the data. It does not move again.
================================================================================
"""

POS_DIM = {"QB": "pass_rate_neutral", "RB": "rb_tgt_share",
           "WR": "pass_rate_neutral", "TE": "te_tgt_share"}

# what delta-engine.js applies today, for the comparison table
ENGINE_DOC = {"QB": -0.11, "RB": -0.05, "WR": -0.12, "TE": -0.12}   # worst-case dOc, c < .30
ALPHA = 0.46          # from the crux study's C2
MIN_GAMES = 8


# --------------------------------------------------------------------------------------
# DELTA's scoring, transcribed from gamefp() in delta-engine.js
# --------------------------------------------------------------------------------------

SCORING_COLS = [
    "passing_yards", "passing_tds", "passing_interceptions",
    "rushing_yards", "rushing_tds", "receptions", "receiving_yards", "receiving_tds",
    "rushing_fumbles_lost", "receiving_fumbles_lost", "sack_fumbles_lost",
    "passing_2pt_conversions", "rushing_2pt_conversions", "receiving_2pt_conversions",
    "special_teams_tds",
]


def gamefp(df, pos):
    """half_tep: 0.5/reception, +0.5 more for TE. QBs get nothing for receptions.

    A MISSING COLUMN IS A CRASH, NOT A ZERO.
    The first draft used df.get(c, 0), which quietly hands back the number 0 when a column
    is absent. The nflverse column is `passing_interceptions`, not `interceptions` -- so
    that draft would have scored EVERY QB with ZERO interceptions. Every QB's fantasy points
    inflated by ~4 a season, silently, and the study would have run to a confident verdict.

    It only crashed by luck (an int has no .fillna). Same disease as the FTN play_action
    hole: a wrong column name that degrades into a plausible-looking number instead of an
    error. Never default a missing input to zero.
    """
    missing = [c for c in SCORING_COLS if c not in df.columns]
    assert not missing, (
        f"scoring columns absent from nflverse player_stats: {missing}. "
        f"A missing column must NEVER default to 0 -- that silently rescores every player. "
        f"Fix the names against the schema before proceeding."
    )
    rec_pts = 1.0 if pos == "TE" else (0.0 if pos == "QB" else 0.5)
    g = lambda c: pd.to_numeric(df[c], errors="coerce").fillna(0)
    return (
        g("passing_yards") * 0.04 + g("passing_tds") * 4 + g("passing_interceptions") * -2
        + g("rushing_yards") * 0.1 + g("rushing_tds") * 6
        + g("receptions") * rec_pts + g("receiving_yards") * 0.1 + g("receiving_tds") * 6
        + (g("rushing_fumbles_lost") + g("receiving_fumbles_lost") + g("sack_fumbles_lost")) * -2
        + (g("passing_2pt_conversions") + g("rushing_2pt_conversions")
           + g("receiving_2pt_conversions")) * 2
        + g("special_teams_tds") * 6
    )


def build_panel(seasons):
    """One row per player-season: his PPG, his volume, his age, his team."""
    import nflreadpy as nfl

    ws = nfl.load_player_stats(seasons).to_pandas()
    ws = ws[ws["season_type"].eq("REG")].copy()
    tcol = "team" if "team" in ws.columns else "recent_team"
    ncol = "player_display_name" if "player_display_name" in ws.columns else "player_name"

    ws["fp"] = 0.0
    for pos in POS_DIM:
        m = ws["position"].eq(pos)
        ws.loc[m, "fp"] = gamefp(ws[m], pos)

    for c in ("attempts", "carries", "targets"):
        assert c in ws.columns, f"volume column '{c}' missing from player_stats"
    num = lambda c: pd.to_numeric(ws[c], errors="coerce").fillna(0)
    ws["volume"] = num("attempts") + num("carries") + num("targets")

    # DELTA's DNP rule (locked): a game counts if he took >= 1 offensive snap. nflverse only
    # emits a weekly row for a player who was on the field, so a row IS the snap.
    P = (ws.groupby(["player_id", ncol, "position", tcol, "season"])
           .agg(fp=("fp", "sum"), vol=("volume", "sum"), g=("week", "nunique"))
           .reset_index()
           .rename(columns={ncol: "name", tcol: "team"}))
    P = P[P["position"].isin(POS_DIM) & (P["g"] >= MIN_GAMES)]
    P["ppg"] = P["fp"] / P["g"]
    P["vol_pg"] = P["vol"] / P["g"]

    # age
    try:
        pl = nfl.load_players().to_pandas()
        idc = "gsis_id" if "gsis_id" in pl.columns else "player_id"
        bd = pl[[idc, "birth_date"]].rename(columns={idc: "player_id"})
        P = P.merge(bd, on="player_id", how="left")
        P["age"] = P["season"] - pd.to_datetime(P["birth_date"], errors="coerce").dt.year
        P["age"] = P["age"].fillna(P.groupby("position")["age"].transform("median"))
    except Exception as e:
        print(f"  (age unavailable: {e} -- using position median)")
        P["age"] = 26.0

    P["team"] = P["team"].str.upper().replace({"LA": "LAR", "OAK": "LV", "SD": "LAC", "STL": "LAR"})
    return P[["player_id", "name", "position", "team", "season", "ppg", "vol_pg", "age", "g"]]


# --------------------------------------------------------------------------------------
# The two scheme features
# --------------------------------------------------------------------------------------

def build_features(PC, STINT, FULL, metrics, scale):
    """
    For each (team, season t -> t+1):
        oc_change    did the primary playcaller change?
        fp_delta[m]  alpha * (arriving coach's own historical style - the team's current style)
                     i.e. how much the crux model expects each style dimension to MOVE.
                     Zero when nobody new arrives. NaN when the new man has no history --
                     which is the honest answer: an unknown coach has no fingerprint.
    """
    prim = STINT[STINT["is_primary"]].copy()
    prim["_v"] = [zvec(r, metrics, scale) for _, r in prim.iterrows()]
    style = {(r["season"], r["team"]): r["_v"] for _, r in prim.iterrows()}
    pc_of = {(r["season"], r["team"]): r["playcaller"] for _, r in prim.iterrows()}

    # every playcaller's most recent style vector BEFORE a given season
    hist = {}
    for _, r in prim.sort_values("season").iterrows():
        hist.setdefault(r["playcaller"], []).append((r["season"], r["_v"]))

    def prior_style(pc, before):
        got = [v for (s, v) in hist.get(pc, []) if s < before]
        return got[-1] if got else None

    rows = []
    for (s, t), v_now in style.items():
        nxt = pc_of.get((s + 1, t))
        if nxt is None:
            continue
        changed = int(nxt != pc_of[(s, t)])
        d = {"season": s, "team": t, "oc_change": changed}

        if not changed:
            for m in metrics:
                d[f"fp_{m}"] = 0.0                    # nobody new: no predicted shift
        else:
            ph = prior_style(nxt, s + 1)
            if ph is None:
                for m in metrics:
                    d[f"fp_{m}"] = np.nan             # first-time playcaller: no fingerprint exists
            else:
                delta = ALPHA * (ph - v_now)          # the crux model's predicted style move
                for j, m in enumerate(metrics):
                    d[f"fp_{m}"] = float(delta[j])
        rows.append(d)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------
# Out-of-sample evaluation
# --------------------------------------------------------------------------------------

def loso_rmse(D, feats):
    """Leave-one-season-out. Fit on the other seasons, predict the held-out one."""
    errs = []
    for s in sorted(D["season"].unique()):
        tr, te = D[D.season != s], D[D.season == s]
        if len(tr) < 20 or len(te) < 5:
            continue
        X = np.column_stack([np.ones(len(tr))] + [tr[f].values for f in feats])
        y = tr["next_ppg"].values
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        Xt = np.column_stack([np.ones(len(te))] + [te[f].values for f in feats])
        errs.append(te["next_ppg"].values - Xt @ beta)
    if not errs:
        return np.nan
    return float(np.sqrt(np.mean(np.concatenate(errs) ** 2)))


def fit_coef(D, feats, target="next_ppg"):
    X = np.column_stack([np.ones(len(D))] + [D[f].values for f in feats])
    beta, *_ = np.linalg.lstsq(X, D[target].values, rcond=None)
    return beta


def race(D, pos, base, extra, label, engine_val, n_perm=2000, n_boot=2000, rng=None):
    """
    Size the lever. The coefficient and its CLUSTER-bootstrapped 95% CI are the deliverable;
    the RMSE lift is reported but is not the gate (see PREREG).
    """
    rng = rng or np.random.default_rng(5)
    feats = base + extra
    k = 1 + len(base)                      # index of the scheme coefficient

    mean_ppg = D["next_ppg"].mean()
    coef = fit_coef(D, feats)[k]
    coef_pct = coef / mean_ppg if mean_ppg else np.nan

    # ---- CLUSTER bootstrap by team-season. oc_change is a TEAM-level feature; 6-15 players
    # hang off each value of it. Resampling players independently would shrink the CI ~3x
    # and manufacture significance that is not there.
    D = D.copy()
    D["_cl"] = D["team"].astype(str) + "_" + D["season"].astype(str)
    clusters = D["_cl"].unique()
    idx = {c: D.index[D["_cl"] == c].values for c in clusters}
    boots = []
    for _ in range(n_boot):
        pick = rng.choice(clusters, size=len(clusters), replace=True)
        rows = np.concatenate([idx[c] for c in pick])
        B = D.loc[rows]
        if B[extra[0]].nunique() < 2:
            continue
        try:
            b = fit_coef(B, feats)[k] / B["next_ppg"].mean()
            if np.isfinite(b):
                boots.append(b)
        except np.linalg.LinAlgError:
            continue
    lo, hi = (np.percentile(boots, [2.5, 97.5]) if len(boots) > 100 else (np.nan, np.nan))

    # ---- secondary: out-of-sample RMSE lift (reported, not the gate)
    r_base = loso_rmse(D, base)
    r_full = loso_rmse(D, feats)
    lift = 1 - r_full / r_base if np.isfinite(r_base) and np.isfinite(r_full) else np.nan

    # ---- permutation, ALSO clustered: shuffle the feature across TEAM-SEASONS, not players
    cl_val = D.groupby("_cl")[extra[0]].first()
    null = []
    for _ in range(n_perm):
        Q = D.copy()
        shuffled = pd.Series(rng.permutation(cl_val.values), index=cl_val.index)
        Q[extra[0]] = Q["_cl"].map(shuffled)
        r = loso_rmse(Q, feats)
        if np.isfinite(r) and np.isfinite(r_base):
            null.append(1 - r / r_base)
    p = ((np.asarray(null) >= lift).sum() + 1) / (len(null) + 1) if null else np.nan

    # ---- THE DECISION
    has0 = lo <= 0 <= hi
    hasE = lo <= engine_val <= hi
    if not np.isfinite(lo):
        decision = "?  bootstrap failed"
    elif has0 and hasE:
        decision = "UNDERPOWERED — the CI spans BOTH zero and the engine. Cannot decide."
    elif has0 and not hasE:
        # The box that matters most, and the one the first draft of this tree did not have.
        # You cannot prove the effect is real -- but you CAN prove the engine's number is wrong.
        # That is decisive even without significance.
        decision = (f"ENGINE RULED OUT — cannot prove the effect is nonzero, but {engine_val:+.0%} "
                    f"is OUTSIDE the CI. Shrink to the CI bound or delete.")
    elif hasE:
        decision = "KEEP — the hand table is inside the CI"
    else:
        decision = f"SHRINK — real, but the engine's {engine_val:+.0%} is outside the CI"

    return {
        "pos": pos, "horse": label, "n": len(D), "n_clusters": len(clusters),
        "coef_pct": coef_pct, "ci_lo": lo, "ci_hi": hi,
        "engine": engine_val, "lift": lift, "p": float(p) if np.isfinite(p) else np.nan,
        "decision": decision,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", default="2022-2025")
    ap.add_argument("--permutations", type=int, default=2000)
    ap.add_argument("--no-ftn", action="store_true",
                    help="REQUIRED for any window starting before 2022 -- FTN charting only "
                         "exists 2022+ and nflreadpy raises otherwise. Drops play_action + motion.")
    a = ap.parse_args()

    print(PREREG)
    lo, hi = (int(x) for x in a.seasons.split("-"))
    seasons = list(range(lo, hi + 1))
    rng = np.random.default_rng(20260713)

    print(f"seasons {lo}-{hi} | FTN={'ON' if not a.no_ftn else 'OFF'}")
    use_ftn = not a.no_ftn
    if lo < 2022 and use_ftn:
        sys.exit("ABORT: FTN charting starts in 2022. Re-run with --no-ftn for a pre-2022 window.")
    pbp, PC, motion = load_crux(seasons, use_ftn=use_ftn)
    pbp = prepare(pbp, motion)
    FULL, STINT, metrics = build_style_table(pbp, PC, use_ftn=use_ftn)
    scale = zscale(FULL, metrics)

    P = build_panel(seasons)
    F = build_features(PC, STINT, FULL, metrics, scale)
    print(f"  {len(P)} player-seasons | {len(F)} team transitions | "
          f"{int(F.oc_change.sum())} with a new playcaller")

    # next year's PPG, same team only
    N = P[["player_id", "season", "team", "ppg"]].rename(columns={"ppg": "next_ppg"})
    N["season"] = N["season"] - 1
    D = P.merge(N, on=["player_id", "season", "team"], how="inner").merge(
        F, on=["season", "team"], how="left")
    D = D.dropna(subset=["next_ppg", "ppg", "vol_pg", "age", "oc_change"])
    print(f"  {len(D)} same-team year-over-year pairs with a next season\n")

    BASE = ["ppg", "vol_pg", "age"]
    out = []
    for pos in ["QB", "RB", "WR", "TE"]:
        dim = f"fp_{POS_DIM[pos]}"
        Dp = D[D.position == pos].copy()
        if len(Dp) < 40:
            print(f"  {pos}: only {len(Dp)} pairs -- too few, skipped")
            continue

        out.append(race(Dp, pos, BASE, ["oc_change"], "A  oc_change",
                        ENGINE_DOC[pos], a.permutations, rng=rng))

        Df = Dp.dropna(subset=[dim])
        if len(Df) >= 40:
            out.append(race(Df, pos, BASE, [dim], "B  fingerprint",
                            0.0, a.permutations, rng=rng))

    R = pd.DataFrame(out)

    print("=" * 92)
    print("HORSE A — THE COORDINATOR-CHANGE LEVER (dOc).  Is -12% anywhere near the truth?")
    print("=" * 92)
    A = R[R.horse.str.startswith("A")]
    print(f"  {'pos':<4} {'n':>5} {'teams':>6} {'engine':>8} {'data says':>10} "
          f"{'95% CI':>18} {'RMSE lift':>10}")
    for _, r in A.iterrows():
        ci = f"[{r.ci_lo:+.1%}, {r.ci_hi:+.1%}]"
        print(f"  {r.pos:<4} {r.n:>5} {r.n_clusters:>6} {r.engine:>8.0%} "
              f"{r.coef_pct:>10.1%} {ci:>18} {r.lift:>+10.1%}")
    print()
    for _, r in A.iterrows():
        print(f"  {r.pos}: {r.decision}")

    print("\n" + "=" * 92)
    print("HORSE B — THE FINGERPRINT (the matrix the crux said was buildable, alpha=0.46)")
    print("=" * 92)
    B = R[R.horse.str.startswith("B")]
    if B.empty:
        print("  no position had enough new-playcaller teams with a coach who HAS a history.")
    else:
        print(f"  {'pos':<4} {'n':>5} {'coef/SD':>9} {'95% CI':>18} {'RMSE lift':>10}  decision")
        for _, r in B.iterrows():
            ci = f"[{r.ci_lo:+.1%}, {r.ci_hi:+.1%}]"
            print(f"  {r.pos:<4} {r.n:>5} {r.coef_pct:>9.1%} {ci:>18} {r.lift:>+10.1%}  {r.decision}")

    print("\n" + "=" * 92)
    print("VERDICT")
    print("=" * 92)
    keep = A[A.decision.str.startswith("KEEP")]
    shrink = A[A.decision.str.startswith("SHRINK")]
    ruled = A[A.decision.str.startswith("ENGINE RULED OUT")]
    weak = A[A.decision.str.startswith("UNDERPOWERED")]

    if len(ruled) and not len(keep):
        print("  THE ENGINE'S COORDINATOR PENALTY IS RULED OUT.")
        print("  At every position where this study can see, the fitted effect's confidence")
        print("  interval EXCLUDES the value delta-engine.js is applying -- and in most cases")
        print("  cannot even rule out zero. DELTA is docking players up to 12% of their")
        print("  projection for something the data will not confirm.")
        print("\n  -> dOc comes DOWN before the freeze. To the CI bound at most; to zero if you")
        print("     want to be honest about what you actually know.")
        print("  -> And dSys with it. Same hand, same table, and it cannot even be backtested.")
    elif len(shrink):
        print("  THE PENALTY IS REAL BUT THE ENGINE HAS IT TOO BIG:")
        for _, r in shrink.iterrows():
            print(f"     {r.pos}: engine {r.engine:+.0%}  ->  data {r.coef_pct:+.1%} "
                  f"(95% CI [{r.ci_lo:+.1%}, {r.ci_hi:+.1%}])")
        print("\n  -> RETUNE dOc to the fitted values. A validated -3% beats an invented -12%.")
    elif len(keep) == len(A) and len(A):
        print("  THE HAND TABLE IS INSIDE THE CONFIDENCE INTERVAL AT EVERY POSITION.")
        print("  Steve's football intuition is VALIDATED. The freeze rests on something defensible.")
    else:
        print("  MIXED / UNDERPOWERED. Read the per-position decisions above and do not round them")
        print("  into a headline. Where the CI spans both zero and the engine, this study cannot")
        print("  tell you the answer and will not pretend to.")

    print("\n  SEPARATELY, AND NOT OPTIONAL:")
    print("  SYS.s cannot be validated at all. There is no historical table -- it exists only as")
    print("  a current snapshot, so there is nothing to backtest. A lever swinging projections by")
    print("  10% was built in a form that makes validation impossible. Freeze it, log it, and let")
    print("  the accuracy ledger judge it in a year. That is what the ledger is for.")
    print()


if __name__ == "__main__":
    main()
