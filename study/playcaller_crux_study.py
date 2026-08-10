#!/usr/bin/env python3
"""
DELTA — PLAYCALLER CRUX STUDY  (v2, 2026-07-13)

THE QUESTION
    Is offensive scheme a property of the PLAYCALLER, or of the TEAM?

    If scheme is a playcaller property -> fingerprints are real -> the tendencies matrix
    is buildable, and DELTA's founding thesis survives.
    If scheme is really a TEAM property (roster / GM / HC) -> "Shanahan-ball" is just
    "the 49ers' personnel", the matrix is superstition with a name tag, and the thesis
    is wrong.

METHOD RULE (do not violate)
    Style = what a coach CHOOSES: pass rate, motion, play-action, pace, aDOT, target shares.
    NEVER outcome (points, EPA, wins). Outcome = choices + talent. Grading Nagy on results
    blames him for Trubisky's arm and permanently punishes whoever inherits a bad roster.

    Corollary, and this is where v1 leaked: every style metric must be measured on the
    NEUTRAL SCRIPT (early downs, one-score, pre-Q4). A team down 21 throws every down
    regardless of philosophy. v1 applied the neutral filter to only 6 of its 12 metrics --
    aDOT, deep rate, screen rate, RB/TE target share and motion were all computed on ALL
    plays, which smuggled game script (i.e. team quality, i.e. roster) into the "style"
    vector. Team quality is sticky year over year and belongs to the TEAM. That bug biased
    BOTH C1 and C2 toward FAIL, i.e. toward killing the thesis. Fixed here.

    Outcome IS allowed for one thing only: selecting a matched control group (C1a's
    struggling-offense placebo). It never enters a style vector.

WHAT CHANGED FROM v1
    1.  Stint-level. playcallers.csv now carries week ranges. A mid-season change yields
        TWO style vectors, not one blended discard. 15 blended team-seasons were found
        (v1's notes-regex caught 9).
    2.  C1a is new and is now the PRIMARY test: the 13 mid-season changes are a
        within-season natural experiment. Same team, same roster, same GM, same year --
        only the playcaller changes. Year-over-year can never hold personnel constant.
    3.  C2 is rewritten. v1's carry rate (d_pc < d_tm) is a variance-RATIO test in
        disguise: because the coach effect cancels out of d_pc and the team effect cancels
        out of d_tm, `carried` is really asking "is the coach bigger than the team?" It
        reports ~31% -- a hard FAIL -- for a fingerprint 80% the size of the team effect,
        which would be enormously useful. Replaced with DELTA's standard ship gate: does
        knowing the arriving coach's history beat "the team stays the same", out of sample?
        That test also returns alpha -- the transfer coefficient -- which is the number you
        need to SIZE the adjustment. A binary carry rate gives you nothing to calibrate.
    4.  Whitened (Mahalanobis) distance. Raw Euclidean over correlated z-scores silently
        weights the "passiness" construct ~2-3x (pass rate, 1st-down pass rate and shotgun
        are near-collinear) and under-weights motion / PA -- the dimensions DELTA has
        already proven matter. --distance euclidean reruns v1's metric as a robustness check.
    5.  C3 gets a permutation baseline. Raw one-way R^2 with 61 playcaller groups vs 32 team
        groups on 128 obs hands playcaller a +0.23 R^2 head start from degrees of freedom
        alone, on every metric, even if coaches are irrelevant.
    6.  Hard METRICS assertion. v1 auto-derived its metric set from whatever columns
        survived and swallowed FTN failures in a bare try/except -- a silent motion failure
        would change every distance and could flip the verdict, with one quiet line in the log.

USAGE
    python playcaller_crux_study.py                      # the pre-registered run
    python playcaller_crux_study.py --distance euclidean # robustness
    python playcaller_crux_study.py --no-ftn             # drop play_action+motion; frees the 2022 floor
    python test_playcaller_crux.py                       # self-test on synthetic data
"""

import argparse
import sys
import numpy as np
import pandas as pd

# --------------------------------------------------------------------------------------
# PRE-REGISTRATION.  Printed before a single row of data is read.
# --------------------------------------------------------------------------------------

PREREG = """
================================================================================
PRE-REGISTERED DECISION CRITERIA  (fixed before the data is seen)
================================================================================

C1a  DISCONTINUITY -- within season  [PRIMARY]
     The 13 mid-season playcaller changes. Same team, same roster, same year.
     Compare style(stint A) vs style(stint B) against a placebo built from clean
     team-seasons split at THE SAME WEEK (so play counts, weather, opponent
     strength and any late-season drift are matched).
       PASS  if  mean percentile of the real changes within their matched placebo
                 pools is > 0.50 at permutation p < .05, AND Cohen's d >= 0.50.
     This test is CONSERVATIVE: a mid-season hire inherits the install and cannot
     fully reshape the offense. Whatever shows up is a FLOOR on the coach effect.

C1b  DISCONTINUITY -- year over year  [SECONDARY, continuity with v1]
     95 transitions, 47 changed / 48 same, primary playcaller only.
       PASS  if  Cohen's d >= 0.50 at permutation p < .05.

C2   PORTABILITY  [THE SHIP GATE]
     Can you predict what an ARRIVING playcaller will do?
       baseline model:  y_hat = style(new team, last year)        "nothing changes"
       coach model:     y_hat = a * style(coach, his last team) + (1-a) * style(new team)
     Fit `a` by leave-one-out across the moves. Permutation null: shuffle which
     coach's history is attached to which move.
       PASS  if  permutation p < .05  AND  a_hat >= 0.20.
     a_hat < 0.20 means less than a fifth of the fingerprint transfers -- too small
     to move a projection honestly, whatever its p-value.

C3   VARIANCE DECOMPOSITION  [SUPPORTING ONLY, never decisive]
     Excess R^2 (observed minus permutation-null) by team vs by playcaller.

DECISION TREE
     C1a FAILS                  -> scheme is a team property. Founding thesis is wrong.
                                   Do not build the matrix. Leave SYS.s alone or delete it.
     C1a passes, C2 FAILS       -> playcallers change scheme but carry no portable
                                   fingerprint. "New playcaller = uncertainty" is validated
                                   (which is what DELTA does today). Matrix NOT buildable.
     C1a passes, C2 passes      -> fingerprints are real. Build the matrix, then run it
                                   head to head against hand-assigned SYS.s.

     If C1a and C1b disagree, C1a wins. It holds the roster constant; C1b cannot.

NO GOALPOST MOVING. These bars are final. A near miss is a miss.
================================================================================
"""

# --------------------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------------------

METRICS_EXPECTED = [
    "pass_rate_neutral",   # dropback rate on neutral script (the PROE base, not play_type)
    "pass_rate_1st",       # dropback rate on 1st down
    "shotgun_rate",
    "no_huddle_rate",
    "play_action_rate",
    "sec_per_play",        # pace: seconds burned before the snap, within-drive
    "adot",
    "deep_rate",           # air yards >= 20
    "behind_los_rate",     # screens / swings
    "rb_tgt_share",
    "te_tgt_share",
    "motion_rate",         # FTN charting; dropped under --no-motion
]

MIN_PLAYS = 100     # per stint, all plays
MIN_NEUTRAL = 60    # per stint, neutral script
MIN_GAMES_FP = 6    # a stint must cover >= 6 weeks to anchor a C2 fingerprint
RIDGE = 0.05        # eigenvalue floor for the whitener, as a fraction of the mean eigenvalue


# --------------------------------------------------------------------------------------
# Style profiling.  EVERY metric is computed on the neutral script.
# --------------------------------------------------------------------------------------

def active_metrics(use_ftn):
    """Deterministic -- depends only on the flag, never on the data. Must be known BEFORE
    profiling so profile() can reject a stint that cannot fill it."""
    FTN = {"motion_rate", "play_action_rate"}
    return [m for m in METRICS_EXPECTED if use_ftn or m not in FTN]


def neutral_mask(df):
    """Early downs, one score, pre-Q4. Where a coach is choosing freely."""
    return (
        df["down"].isin([1, 2])
        & df["score_differential"].abs().le(8)
        & df["qtr"].le(3)
    )


def pace_table(pbp):
    """
    Seconds burned before each snap, computed WITHIN A DRIVE on the full play sequence.

    v1 diffed game_seconds_remaining across consecutive *neutral* plays, so any play the
    neutral filter removed mid-drive produced a diff spanning two plays. Diff on the full
    sequence, then select neutral plays, so the value attached to a neutral play is the
    time actually burned before it.
    """
    drive_col = "drive" if "drive" in pbp.columns else "fixed_drive"
    p = pbp.sort_values(["game_id", "play_id"]).copy()
    dt = -p.groupby(["game_id", drive_col])["game_seconds_remaining"].diff()
    p["sec_before_snap"] = dt.where((dt > 0) & (dt < 60))
    return p[["game_id", "play_id", "sec_before_snap"]]


def profile(plays, metrics, use_ftn=True):
    """
    Style vector for one coach-stint. `plays` is that stint's plays, already filtered to
    regular-season run/pass with a posteam. `motion` is an optional per-play motion flag
    (FTN), aligned on play_id.

    Returns None if the stint is too thin to profile.
    """
    if len(plays) < MIN_PLAYS:
        return None
    ng = plays[neutral_mask(plays)]
    if len(ng) < MIN_NEUTRAL:
        return None

    d = {}

    # ---- called-pass rate. qb_dropback, not play_type: play_type files a scramble as a
    # run and a sack as a pass. A scramble is a CALLED pass that broke down -- it is the
    # coach's choice we are measuring, not the QB's legs. This is the same denominator
    # PROE uses, which DELTA has already validated.
    db = ng["qb_dropback"]
    d["pass_rate_neutral"] = db.mean()

    fd = ng[ng["down"] == 1]
    d["pass_rate_1st"] = fd["qb_dropback"].mean() if len(fd) >= 25 else np.nan

    d["shotgun_rate"] = ng["shotgun"].mean()
    d["no_huddle_rate"] = ng["no_huddle"].mean()

    dbp = ng[ng["qb_dropback"] == 1]
    d["play_action_rate"] = (dbp["play_action"].mean()
                             if use_ftn and len(dbp) >= 25 else np.nan)

    d["sec_per_play"] = ng["sec_before_snap"].mean()

    # ---- passing shape, NEUTRAL ONLY (v1 used all plays; that is game script, not scheme)
    ps = ng[(ng["qb_dropback"] == 1) & ng["air_yards"].notna()]
    if len(ps) >= 30:
        ay = ps["air_yards"]
        d["adot"] = ay.mean()
        d["deep_rate"] = (ay >= 20).mean()
        d["behind_los_rate"] = (ay < 0).mean()
    else:
        d["adot"] = d["deep_rate"] = d["behind_los_rate"] = np.nan

    # ---- target distribution, NEUTRAL ONLY (a trailing team checks down to its back)
    tg = ng[ng["receiver_position"].notna()]
    if len(tg) >= 30:
        d["rb_tgt_share"] = (tg["receiver_position"] == "RB").mean()
        d["te_tgt_share"] = (tg["receiver_position"] == "TE").mean()
    else:
        d["rb_tgt_share"] = d["te_tgt_share"] = np.nan

    # ---- motion, NEUTRAL ONLY.  Read off the frame; never a parallel Series (see prepare()).
    if use_ftn and "_motion" in ng.columns:
        m = ng["_motion"].dropna()
        d["motion_rate"] = m.mean() if len(m) >= MIN_NEUTRAL else np.nan
    else:
        d["motion_rate"] = np.nan

    # sanity: every rate must be a rate
    for k, v in d.items():
        if k in ("adot", "sec_per_play") or pd.isna(v):
            continue
        assert -0.001 <= v <= 1.001, f"IMPOSSIBLE RATE {k}={v}. A rate above 1.0 does not exist."

    # ---- A STINT THAT CANNOT BE PROFILED IS NOT EVIDENCE.
    # v2.0 shipped with this hole and it cost the study its primary test. A short stint on a
    # team that is getting blown out (TEN 2025: Callahan, weeks 1-3, 0-3) clears MIN_PLAYS and
    # MIN_NEUTRAL, then starves a SUB-threshold (>=30 targets / >=30 air-yards / >=60 motion),
    # and that metric returns np.nan. The old code returned the dict anyway. The NaN rode into
    # the distance; `NaN < NaN` is False, so `pct` scored 0.000 -- the most anti-thesis value
    # the statistic can take -- and `cohens_d` went NaN, which made the PASS gate False for
    # ANY data. A crash was wearing a verdict's clothes.
    if any(pd.isna(d[m]) for m in metrics):
        return None
    return d


def prepare(pbp, motion=None):
    """Attach pace and motion as COLUMNS, once. Everything downstream reads the frame.

    This is not cosmetic. merge() hands back a fresh RangeIndex; pbp arrives from a boolean
    filter and therefore has a gappy index. Any Series carried alongside and reindexed onto
    the post-merge frame silently becomes NaN. Motion would read as absent, every distance
    would change, and the only thing between that and a published verdict would be the
    coverage assertion. Put it in the frame.
    """
    pbp = pbp.merge(pace_table(pbp), on=["game_id", "play_id"], how="left")
    if motion is not None:
        pbp["_motion"] = np.asarray(motion, dtype=float)
    return pbp


def build_style_table(pbp, PC, use_ftn=True):
    """
    Two outputs:
      FULL  -- one style vector per (season, team), ALL that team's neutral plays.
               The reference population: sets the per-season z-scale, and is what a
               team "looked like last year" for C2's baseline model.
      STINT -- one style vector per (season, team, playcaller, week range).
    """
    metrics = active_metrics(use_ftn)

    full_rows = []
    for (s, t), g in pbp.groupby(["season", "posteam"]):
        pr = profile(g, metrics, use_ftn)
        if pr:
            full_rows.append({"season": s, "team": t, **pr})
    FULL = pd.DataFrame(full_rows)

    stint_rows = []
    for _, r in PC.iterrows():
        g = pbp[
            (pbp["season"] == r["season"])
            & (pbp["posteam"] == r["team"])
            & (pbp["week"].between(r["week_start"], r["week_end"]))
        ]
        pr = profile(g, metrics, use_ftn)
        if pr:
            stint_rows.append({
                "season": r["season"], "team": r["team"], "playcaller": r["playcaller"],
                "week_start": r["week_start"], "week_end": r["week_end"],
                "is_primary": r["is_primary"], "split": r["split"], **pr,
            })
    STINT = pd.DataFrame(stint_rows)

    # ---- THE ASSERTION v1 DID NOT HAVE.
    # v1 derived its metric list from whatever columns happened to survive an >80% coverage
    # filter, and swallowed FTN merge failures in a bare try/except. A silent motion failure
    # changes every Euclidean distance in the study and can flip the verdict, announced by
    # one quiet line in a long log. Fail loudly instead.
    missing = [m for m in metrics if m not in STINT.columns]
    assert not missing, f"METRIC SET CHANGED: {missing} absent. Fix the pipeline, do not proceed."
    for m in metrics:
        cov = STINT[m].notna().mean()
        assert cov > 0.80, (
            f"METRIC '{m}' is only {cov:.0%} populated. Expected >80%. "
            f"Something upstream broke. Fix it, do not proceed on a silently different metric set."
        )

    FULL = FULL.dropna(subset=metrics).reset_index(drop=True)
    STINT = STINT.dropna(subset=metrics).reset_index(drop=True)
    return FULL, STINT, metrics


def zscale(FULL, metrics):
    """Per-season mean/sd taken from the 32 full team-seasons, not from the stints.
    Blended seasons contribute extra stint rows; letting them move the scale would
    distort it. The reference frame stays the league."""
    return {
        s: (g[metrics].mean().values, g[metrics].std(ddof=0).replace(0, 1).values)
        for s, g in FULL.groupby("season")
    }


def zvec(row, metrics, scale):
    """Accepts a Series or a plain dict."""
    mu, sd = scale[row["season"]]
    v = np.array([float(row[m]) for m in metrics])
    return (v - mu) / sd


# --------------------------------------------------------------------------------------
# Distance.  Whitened (Mahalanobis) by default.
# --------------------------------------------------------------------------------------

def make_whitener(Z, mode="mahalanobis"):
    """
    Raw Euclidean over correlated dims is an implicit weighting nobody chose. pass_rate_neutral
    and pass_rate_1st are near the same construct, so "style distance" quietly becomes ~2x a
    pass-rate distance -- and under-weights motion and PA, which are the dimensions DELTA has
    already PROVEN predict fantasy production (System Score v2). Whiten so each independent
    direction of style counts once.
    """
    if mode == "euclidean":
        return lambda v: v
    S = np.cov(Z, rowvar=False)
    w, V = np.linalg.eigh(S)
    w = np.maximum(w, RIDGE * w.mean())      # ridge: do not divide by a near-zero eigenvalue
    W = V @ np.diag(w ** -0.5) @ V.T
    return lambda v: v @ W


def dist(a, b, wh):
    return float(np.linalg.norm(wh(a - b)))


# --------------------------------------------------------------------------------------
# Stats helpers (numpy only -- no scipy dependency in the runner)
# --------------------------------------------------------------------------------------

def cohens_d(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return np.nan
    sp = np.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2))
    return (a.mean() - b.mean()) / sp if sp > 0 else np.nan


def perm_p_meandiff(a, b, n=5000, rng=None):
    """One-sided permutation test: is mean(a) > mean(b)?"""
    rng = rng or np.random.default_rng(0)
    a, b = np.asarray(a, float), np.asarray(b, float)
    obs = a.mean() - b.mean()
    pool = np.concatenate([a, b])
    na = len(a)
    hits = 0
    for _ in range(n):
        rng.shuffle(pool)
        if pool[:na].mean() - pool[na:].mean() >= obs:
            hits += 1
    return (hits + 1) / (n + 1)


def perm_p_meanpct(pcts, n=5000, rng=None):
    """Under H0 the percentiles are uniform on [0,1] (mean .50). Is the observed mean higher?"""
    rng = rng or np.random.default_rng(0)
    pcts = np.asarray(pcts, float)
    obs = pcts.mean()
    null = rng.uniform(0, 1, size=(n, len(pcts))).mean(axis=1)
    return ((null >= obs).sum() + 1) / (n + 1)




def assert_finite(stat, name):
    """A FAIL and a CRASH must never be indistinguishable.

    v2.0's C1a returned FAIL because Cohen's d was NaN -- `NaN >= 0.50` is False, so the
    PASS gate was False for any data whatsoever. The report said "C1a: FAIL. The founding
    thesis is wrong." It had not tested anything. Never again: if a gate statistic is not
    finite, the run DIES. Loudly.
    """
    for k in ("cohens_d", "p_perm", "mean_pct", "alpha", "oos_lift"):
        if k in stat and not np.isfinite(stat[k]):
            raise RuntimeError(
                f"{name}: gate statistic '{k}' is {stat[k]}. A gate statistic cannot be NaN. "
                f"Something upstream produced an unprofilable stint that was not excluded. "
                f"FIX IT -- do not read the verdict, there isn't one."
            )


# --------------------------------------------------------------------------------------
# C1a -- WITHIN-SEASON DISCONTINUITY  [PRIMARY]
# --------------------------------------------------------------------------------------

def c1a_within_season(pbp, PC, FULL, metrics, scale, wh, use_ftn=True, rng=None):
    """
    The 13 mid-season playcaller changes, against a placebo of clean team-seasons split at
    THE SAME WEEK.

    The matched week is not a nicety, it is the whole design. A stint of 5 games has a noisier
    style vector than a stint of 12, and noise inflates distance. Splitting the placebo at the
    same week gives the control the same play counts, the same weather, the same slice of the
    schedule and the same late-season drift. Only the identity of the man with the sheet differs.
    """
    rng = rng or np.random.default_rng(1)
    changes = PC[PC["split"] == "midseason"].groupby(["season", "team"])
    clean = PC[PC["split"] == "none"][["season", "team"]].drop_duplicates()

    rows, dropped = [], []
    for (s, t), g in changes:
        g = g.sort_values("week_start")
        if len(g) != 2:
            continue
        a, b = g.iloc[0], g.iloc[1]
        cut = int(a["week_end"])                      # coach A calls <= cut, coach B calls > cut

        def half(team, w0, w1):
            sub = pbp[(pbp.season == s) & (pbp.posteam == team) & (pbp.week.between(w0, w1))]
            return profile(sub, metrics, use_ftn)

        pa, pb = half(t, 1, cut), half(t, cut + 1, 18)
        if not pa or not pb:
            dropped.append(f"{s} {t} (cut wk {cut}): a stint is too thin to profile on the "
                           f"neutral script -- EXCLUDED, not scored")
            continue
        try:
            va = zvec({**pa, "season": s}, metrics, scale)
            vb = zvec({**pb, "season": s}, metrics, scale)
        except KeyError:
            continue
        d_obs = dist(va, vb, wh)

        # placebo: every clean team-season THAT YEAR, cut at the same week, same coach both sides
        plac = []
        for tm in clean[clean.season == s].team:
            if tm == t:
                continue
            qa, qb = half(tm, 1, cut), half(tm, cut + 1, 18)
            if not qa or not qb:
                continue
            plac.append(dist(zvec({**qa, "season": s}, metrics, scale),
                             zvec({**qb, "season": s}, metrics, scale), wh))
        if len(plac) < 8:
            dropped.append(f"{s} {t} (cut wk {cut}): only {len(plac)} usable placebos -- EXCLUDED")
            continue

        rows.append({
            "season": s, "team": t, "cut_week": cut,
            "from": a["playcaller"], "to": b["playcaller"],
            "d_changed": d_obs,
            "placebo_mean": float(np.mean(plac)),
            "pct": float((np.asarray(plac) < d_obs).mean()),   # percentile within its own placebo pool
            "n_placebo": len(plac),
            "_plac": plac,
        })

    for msg in dropped:
        print(f"  DROPPED  {msg}")
    R = pd.DataFrame(rows)
    if R.empty:
        return R, {}

    all_plac = np.concatenate([np.asarray(x) for x in R["_plac"]])
    stat = {
        "n_changes": len(R),
        "mean_d_changed": float(R["d_changed"].mean()),
        "mean_d_placebo": float(all_plac.mean()),
        "mean_pct": float(R["pct"].mean()),
        "cohens_d": float(cohens_d(R["d_changed"].values, all_plac)),
        "p_perm": float(perm_p_meanpct(R["pct"].values, rng=rng)),
        "n_above_median": int((R["pct"] > 0.5).sum()),
    }
    assert_finite(stat, "C1a")
    stat["PASS"] = bool(
        stat["mean_pct"] > 0.50 and stat["p_perm"] < 0.05 and stat["cohens_d"] >= 0.50
    )
    return R.drop(columns=["_plac"]), stat


# --------------------------------------------------------------------------------------
# C1b -- YEAR-OVER-YEAR DISCONTINUITY  [SECONDARY]
# --------------------------------------------------------------------------------------

def c1b_year_over_year(STINT, metrics, scale, wh, drop_blended=False, rng=None):
    rng = rng or np.random.default_rng(2)
    P = STINT[STINT["is_primary"]].copy()
    if drop_blended:
        P = P[P["split"] == "none"]

    V = {(r["season"], r["team"]): (zvec(r, metrics, scale), r["playcaller"])
         for _, r in P.iterrows()}

    ch, sm, rows = [], [], []
    for (s, t), (v0, pc0) in V.items():
        nxt = V.get((s + 1, t))
        if nxt is None:
            continue
        v1, pc1 = nxt
        d = dist(v0, v1, wh)
        changed = pc0 != pc1
        (ch if changed else sm).append(d)
        rows.append({"team": t, "t": s, "from": pc0, "to": pc1, "changed": changed, "d": d})

    if len(ch) < 5 or len(sm) < 5:
        return pd.DataFrame(rows), {}
    stat = {
        "n_changed": len(ch), "n_same": len(sm),
        "mean_changed": float(np.mean(ch)), "mean_same": float(np.mean(sm)),
        "cohens_d": float(cohens_d(ch, sm)),
        "p_perm": float(perm_p_meandiff(ch, sm, rng=rng)),
    }
    assert_finite(stat, "C1b")
    stat["PASS"] = bool(stat["cohens_d"] >= 0.50 and stat["p_perm"] < 0.05)
    return pd.DataFrame(rows), stat


# --------------------------------------------------------------------------------------
# C2 -- PORTABILITY  [THE SHIP GATE]
# --------------------------------------------------------------------------------------

def fit_alpha(Y, Xown, Xtm):
    """
    y = a * x_own + (1-a) * x_tm  ->  (y - x_tm) = a * (x_own - x_tm)
    OLS through the origin, pooled over moves and dimensions.
    a = 0 : the coach brings nothing; the team stays itself.
    a = 1 : the coach fully imposes his fingerprint on the new roster.
    """
    r = (Y - Xtm).ravel()
    d = (Xown - Xtm).ravel()
    dd = float(d @ d)
    return float(r @ d) / dd if dd > 1e-12 else 0.0


def c2_portability(STINT, FULL, metrics, scale, wh, n_perm=5000, rng=None):
    """
    Can you predict what an ARRIVING playcaller will do?

    v1 asked `d(his old style, new style) < d(team's prior, new style)` and called it a coin
    flip at 50%. It is not a coin flip -- the coach effect cancels out of the first distance
    and the team effect cancels out of the second, so the statistic really tests
    "sigma_coach > sigma_team". It records a hard FAIL for a fingerprint 80% the size of the
    team effect. That is a fingerprint you would absolutely want.

    So: run DELTA's actual ship gate instead. Does the coach's history beat "nothing changes",
    out of sample? And by how much -- because `a` is what sizes the projection adjustment.
    """
    rng = rng or np.random.default_rng(3)

    # a stint must be long enough to be a fingerprint, not a fragment
    S = STINT[(STINT["week_end"] - STINT["week_start"] + 1) >= MIN_GAMES_FP].copy()
    S["_v"] = [zvec(r, metrics, scale) for _, r in S.iterrows()]
    fullv = {(r["season"], r["team"]): zvec(r, metrics, scale) for _, r in FULL.iterrows()}

    moves = []
    for pc, g in S.groupby("playcaller"):
        g = g.sort_values("season")
        for i in range(len(g) - 1):
            a, b = g.iloc[i], g.iloc[i + 1]
            if b["season"] != a["season"] + 1 or a["team"] == b["team"]:
                continue
            prior = fullv.get((a["season"], b["team"]))     # destination team, the year before
            if prior is None:
                continue
            moves.append({
                "pc": pc, "from": a["team"], "to": b["team"], "season": int(b["season"]),
                "x_own": a["_v"], "x_tm": prior, "y": b["_v"],
            })

    M = pd.DataFrame(moves)
    if len(M) < 8:
        return M, {"n_moves": len(M), "ABORT": "too few moves to test portability"}

    # whiten, so every independent direction of style counts once
    Y = np.vstack([wh(m) for m in M["y"]])
    XO = np.vstack([wh(m) for m in M["x_own"]])
    XT = np.vstack([wh(m) for m in M["x_tm"]])

    def loo_rmse(Y, XO, XT):
        """Leave-one-out: fit alpha WITHOUT this move, then predict it."""
        errs = []
        for i in range(len(Y)):
            k = np.arange(len(Y)) != i
            a = fit_alpha(Y[k], XO[k], XT[k])
            yhat = a * XO[i] + (1 - a) * XT[i]
            errs.append(Y[i] - yhat)
        return float(np.sqrt(np.mean(np.concatenate(errs) ** 2)))

    rmse_base = float(np.sqrt(np.mean((Y - XT) ** 2)))     # "nothing changes"
    rmse_coach = loo_rmse(Y, XO, XT)
    lift = 1 - rmse_coach / rmse_base
    a_hat = fit_alpha(Y, XO, XT)

    # permutation null: attach a RANDOM other coach's history to each move.
    # This breaks the coach->destination link while preserving the marginal distribution
    # of "what an arriving coach's style looks like".
    null = []
    idx = np.arange(len(Y))
    for _ in range(n_perm):
        p = rng.permutation(idx)
        if (p == idx).all():
            continue
        null.append(1 - loo_rmse(Y, XO[p], XT) / rmse_base)
    null = np.asarray(null)
    p_perm = float(((null >= lift).sum() + 1) / (len(null) + 1))

    # which dimensions of style actually travel?
    per_dim = {}
    for j, m in enumerate(metrics):
        per_dim[m] = fit_alpha(Y[:, [j]], XO[:, [j]], XT[:, [j]])

    # v1's carry rate, reported for continuity ONLY -- it is not the gate
    carried = float(np.mean([
        np.linalg.norm(Y[i] - XO[i]) < np.linalg.norm(Y[i] - XT[i]) for i in range(len(Y))
    ]))

    stat = {
        "n_moves": len(M),
        "alpha": a_hat,
        "rmse_base": rmse_base,
        "rmse_coach": rmse_coach,
        "oos_lift": lift,
        "p_perm": p_perm,
        "v1_carry_rate": carried,
        "per_dim_alpha": per_dim,
    }
    assert_finite(stat, "C2")
    stat["PASS"] = bool(p_perm < 0.05 and a_hat >= 0.20)
    return M.drop(columns=["x_own", "x_tm", "y"]), stat


# --------------------------------------------------------------------------------------
# C3 -- VARIANCE DECOMPOSITION  [SUPPORTING ONLY]
# --------------------------------------------------------------------------------------

def _r2_by(df, key, metric):
    grand = df[metric].mean()
    sst = ((df[metric] - grand) ** 2).sum()
    if sst <= 0:
        return np.nan
    ssb = sum(len(g) * (g[metric].mean() - grand) ** 2 for _, g in df.groupby(key))
    return ssb / sst


def c3_variance(STINT, metrics, n_perm=1000, rng=None):
    """
    Raw one-way R^2 is NOT comparable across groupings with different group counts.
    With 128 team-seasons, 32 team groups and ~61 playcaller groups, a RANDOM labelling
    scores E[R^2] ~= (g-1)/(n-1): 0.24 for team, 0.47 for playcaller. Playcaller starts
    with a +0.23 head start on every metric even if coaches are irrelevant. Subtract the
    permutation null so the two are on the same footing.
    """
    rng = rng or np.random.default_rng(4)
    P = STINT[STINT["is_primary"]].copy()
    out = []
    for m in metrics:
        row = {"metric": m}
        for key in ("team", "playcaller"):
            obs = _r2_by(P, key, m)
            null = []
            for _ in range(n_perm):
                q = P.copy()
                q[key] = rng.permutation(q[key].values)
                null.append(_r2_by(q, key, m))
            row[f"r2_{key}"] = obs
            row[f"null_{key}"] = float(np.nanmean(null))
            row[f"excess_{key}"] = obs - float(np.nanmean(null))
        out.append(row)
    return pd.DataFrame(out)


# --------------------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------------------

def load_data(seasons, use_ftn):
    """
    Two of the twelve metrics -- play_action and motion -- are NOT in base nflverse pbp.
    Both come from FTN charting. v1 read `play_action` straight off the pbp frame; if it
    is absent the column is NaN, the >80%-coverage filter quietly drops it, and the study
    runs to a verdict on 11 metrics with one line in the log. Make the dependency explicit
    and assert it.

    FTN is also what pins the window at 2022. Drop it (--no-ftn) and you could run
    2017-2025 -- roughly triple the transitions and triple the moves -- at the cost of two
    metrics. Given C2 is power-starved at n=14, that trade is probably worth taking. It
    needs playcallers.csv extended back to 2016 first, which is real hand-verification work.
    """
    import nflreadpy as nfl

    pbp = nfl.load_pbp(seasons).to_pandas()
    pbp = pbp[
        pbp["season_type"].eq("REG")
        & pbp["posteam"].notna()
        & pbp["play_type"].isin(["pass", "run"])
    ].copy()
    for c in ("shotgun", "no_huddle", "qb_dropback"):
        pbp[c] = pd.to_numeric(pbp[c], errors="coerce").fillna(0)

    # ---- receiver position: pbp gives an id, not a position. Join rosters.
    if "receiver_position" not in pbp.columns:
        ros = (nfl.load_rosters(seasons).to_pandas()[["season", "gsis_id", "position"]]
               .dropna().drop_duplicates(subset=["season", "gsis_id"]))
        pbp = pbp.merge(
            ros.rename(columns={"gsis_id": "receiver_player_id", "position": "receiver_position"}),
            on=["season", "receiver_player_id"], how="left",
        )
    hit = pbp.loc[pbp["receiver_player_id"].notna(), "receiver_position"].notna().mean()
    assert hit > 0.90, f"receiver_position resolved for only {hit:.0%} of targets. Fix the roster join."

    # ---- FTN: play_action + motion. Hard-fail rather than silently shrink the metric set.
    motion = None
    if use_ftn:
        f = nfl.load_ftn_charting(seasons).to_pandas()
        cols = {c.lower(): c for c in f.columns}
        pa_col = next((cols[c] for c in cols if "play_action" in c), None)
        mo_col = next((cols[c] for c in cols if "motion" in c), None)
        assert pa_col and mo_col, (
            f"FTN charting is missing play_action and/or motion (found {sorted(cols)[:12]}...). "
            f"Do NOT proceed on a silently different metric set -- fix the column names, or run "
            f"--no-ftn so the 10-metric run is an explicit choice."
        )
        f = f.rename(columns={"nflverse_game_id": "game_id", "nflverse_play_id": "play_id"})
        pbp = pbp.merge(f[["game_id", "play_id", pa_col, mo_col]],
                        on=["game_id", "play_id"], how="left")
        pbp["play_action"] = pd.to_numeric(pbp[pa_col], errors="coerce")
        motion = pd.to_numeric(pbp[mo_col], errors="coerce")
        cov = pbp.loc[pbp["qb_dropback"] == 1, "play_action"].notna().mean()
        assert cov > 0.80, f"FTN merged onto only {cov:.0%} of dropbacks. The join key is wrong."
    else:
        pbp["play_action"] = np.nan

    PC = pd.read_csv("playcallers.csv")
    PC["team"] = PC["team"].astype(str).str.strip().str.upper()
    PC["playcaller"] = PC["playcaller"].astype(str).str.strip()
    PC["is_primary"] = PC["is_primary"].astype(str).str.lower().isin(["true", "1", "yes"])
    PC = PC[PC["season"].between(min(seasons), max(seasons))]

    # PRE-REGISTERED EXCLUSIONS. JAC 2022 split play-calling INSIDE every game (Pederson
    # called first halves, Press Taylor second halves) -- it cannot be attributed to a man.
    # NYG 2023 has no clean week boundary (Daboll took the sheet "at points").
    drop = PC["split"].isin(["within_game", "contested"])
    if drop.any():
        print(f"  excluded (unattributable): {sorted(set(zip(PC[drop].season, PC[drop].team)))}")
    return pbp, PC[~drop].copy(), motion


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", default="2022-2025")
    ap.add_argument("--distance", choices=["mahalanobis", "euclidean"], default="mahalanobis")
    ap.add_argument("--no-ftn", action="store_true",
                    help="drop play_action + motion (both are FTN). Frees the 2022 window floor.")
    ap.add_argument("--permutations", type=int, default=5000)
    a = ap.parse_args()

    print(PREREG)   # criteria first. always.

    lo, hi = (int(x) for x in a.seasons.split("-"))
    seasons = list(range(lo, hi + 1))
    use_ftn = not a.no_ftn
    rng = np.random.default_rng(20260713)

    print(f"seasons {lo}-{hi} | distance={a.distance} | FTN={'ON' if use_ftn else 'OFF'}")
    pbp, PC, motion = load_data(seasons, use_ftn)
    pbp = prepare(pbp, motion)
    print(f"  {len(pbp):,} plays | {len(PC)} coach-stints | "
          f"{PC.playcaller.nunique()} playcallers | "
          f"{(PC.split=='midseason').sum()//2} mid-season changes")

    FULL, STINT, metrics = build_style_table(pbp, PC, use_ftn)
    print(f"  {len(FULL)} full team-seasons | {len(STINT)} stints profiled | "
          f"{len(metrics)} metrics: {', '.join(metrics)}")

    scale = zscale(FULL, metrics)
    Z = np.vstack([zvec(r, metrics, scale) for _, r in FULL.iterrows()])
    wh = make_whitener(Z, a.distance)

    # ---------------- C1a
    print("\n" + "=" * 80 + "\nC1a  WITHIN-SEASON DISCONTINUITY   [PRIMARY]\n" + "=" * 80)
    R1a, s1a = c1a_within_season(pbp, PC, FULL, metrics, scale, wh, use_ftn, rng)
    if R1a.empty:
        sys.exit("  ABORT: no within-season changes could be profiled. Check playcallers.csv "
                 "week ranges against the pbp `week` column before interpreting anything.")
    if True:
        print(R1a[["season", "team", "cut_week", "from", "to",
                   "d_changed", "placebo_mean", "pct"]].to_string(index=False))
        print(f"\n  usable within-season changes: {s1a['n_changes']} of 13")
        print(f"  changed-playcaller distance : {s1a['mean_d_changed']:.3f}")
        print(f"  same-coach placebo (matched): {s1a['mean_d_placebo']:.3f}")
        print(f"  mean percentile             : {s1a['mean_pct']:.3f}   (null = 0.500)")
        print(f"  above own placebo median    : {s1a['n_above_median']}/{s1a['n_changes']}")
        print(f"  Cohen's d                   : {s1a['cohens_d']:+.3f}   (bar: >= 0.50)")
        print(f"  permutation p               : {s1a['p_perm']:.4f}   (bar: < .05)")
        print(f"\n  C1a: {'PASS' if s1a['PASS'] else 'FAIL'}")

    # ---------------- C1b
    print("\n" + "=" * 80 + "\nC1b  YEAR-OVER-YEAR DISCONTINUITY   [SECONDARY]\n" + "=" * 80)
    for drop in (False, True):
        _, s1b = c1b_year_over_year(STINT, metrics, scale, wh, drop_blended=drop, rng=rng)
        tag = "blended dropped" if drop else "all primaries "
        if s1b:
            print(f"  {tag} | changed {s1b['mean_changed']:.3f} (n={s1b['n_changed']})  "
                  f"same {s1b['mean_same']:.3f} (n={s1b['n_same']})  "
                  f"d={s1b['cohens_d']:+.3f}  p={s1b['p_perm']:.4f}  "
                  f"{'PASS' if s1b['PASS'] else 'FAIL'}")

    # ---------------- C2
    print("\n" + "=" * 80 + "\nC2  PORTABILITY   [THE SHIP GATE]\n" + "=" * 80)
    M, s2 = c2_portability(STINT, FULL, metrics, scale, wh, a.permutations, rng)
    if "ABORT" in s2:
        print(f"  {s2['ABORT']} (n={s2['n_moves']})")
        s2["PASS"] = False
    else:
        print(M.to_string(index=False))
        print(f"\n  baseline RMSE ('nothing changes') : {s2['rmse_base']:.3f}")
        print(f"  coach-model RMSE (leave-one-out)  : {s2['rmse_coach']:.3f}")
        print(f"  out-of-sample lift                : {s2['oos_lift']:+.1%}")
        print(f"  alpha (fraction that transfers)   : {s2['alpha']:.3f}   (bar: >= 0.20)")
        print(f"  permutation p                     : {s2['p_perm']:.4f}   (bar: < .05)")
        print(f"\n  which dimensions travel?")
        for m, v in sorted(s2["per_dim_alpha"].items(), key=lambda x: -abs(x[1])):
            print(f"      {m:<20} alpha = {v:+.2f}")
        print(f"\n  [v1's carry rate, for continuity only, NOT the gate: "
              f"{s2['v1_carry_rate']:.1%}]")
        print(f"\n  C2: {'PASS' if s2['PASS'] else 'FAIL'}")

    # ---------------- C3
    print("\n" + "=" * 80 + "\nC3  VARIANCE DECOMPOSITION   [SUPPORTING ONLY]\n" + "=" * 80)
    C3 = c3_variance(STINT, metrics, n_perm=500, rng=rng)
    print(C3[["metric", "r2_team", "null_team", "excess_team",
              "r2_playcaller", "null_playcaller", "excess_playcaller"]]
          .round(3).to_string(index=False))
    print(f"\n  mean EXCESS R^2 -- team: {C3.excess_team.mean():+.3f}   "
          f"playcaller: {C3.excess_playcaller.mean():+.3f}")
    print("  (raw R^2 is not comparable: 61 playcaller groups vs 32 team groups on 128 obs)")

    # ---------------- verdict
    print("\n" + "=" * 80 + "\nVERDICT\n" + "=" * 80)
    if not s1a.get("PASS"):
        print("  C1a FAILED. Scheme does not move when the playcaller does, even with the")
        print("  roster held constant. Scheme is a TEAM property. The founding thesis is wrong.")
        print("  -> DO NOT build the tendencies matrix. Delete SYS.s or leave it as documented")
        print("     intuition -- but do not dress it up as validated.")
    elif not s2.get("PASS"):
        print("  C1a PASSED, C2 FAILED. Playcallers DO change scheme -- but you cannot predict")
        print("  what an arriving one will do. His history does not beat 'nothing changes'.")
        print("  -> 'New playcaller = uncertainty' is VALIDATED. That is what DELTA already does")
        print("     (styleFactors OC-change neutralization). Matrix NOT buildable. Stop here.")
    else:
        print("  C1a PASSED, C2 PASSED. Fingerprints are real and they travel.")
        print(f"  -> BUILD THE MATRIX. alpha = {s2['alpha']:.2f} sizes the adjustment.")
        print("  -> Then run it HEAD TO HEAD against hand-assigned SYS.s. If the derived score")
        print("     does not beat the hand table at predicting production, Steve's intuition is")
        print("     validated and the freeze rests on something defensible either way.")
    print()


if __name__ == "__main__":
    main()
