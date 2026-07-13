#!/usr/bin/env python3
"""
SELF-TEST for playcaller_crux_study.py

Methodology lesson #2 from NULL-RESULTS.md: "Test the code that actually ships, not a
retyped copy. An OLS bug survived a 'passing' test because the test re-implemented the
function instead of importing it." So this file IMPORTS the shipping functions. If the
study is edited, this test exercises the edit.

WHAT IT DOES
    Plants a KNOWN coach effect in synthetic play-by-play, wires it through the REAL
    playcallers.csv (so the real design is tested: 13 within-season changes, ~14 moves,
    real stint lengths), and asserts the study recovers what was planted.

    Generative model:   style(team, coach) = base + T[team] + C[coach] + noise
    Control knob:       rho = sigma_coach / sigma_team

    The estimator alpha has a closed form under this model:
        alpha = sigma_C^2 / (sigma_T^2 + sigma_C^2)      <- the coach's SHARE OF VARIANCE
    which is exactly what you want: 0 = pure team property, 1 = pure coach property.
    That is why the C2 bar is set on alpha and not on a coin-flip rate.

SCENARIOS
    rho = 0.0   pure team property     -> C1a must FAIL, C2 must FAIL, alpha ~ 0
    rho = 0.8   coach is 80% of team   -> alpha ~ 0.39, C2 must PASS
                ...and v1's carry rate must FAIL here. That is the whole argument.
    rho = 1.5   coach dominant         -> alpha ~ 0.69, both must PASS
"""

import sys
import numpy as np
import pandas as pd

# import the code that SHIPS
from playcaller_crux_study import (
    prepare, build_style_table, zscale, zvec, make_whitener,
    c1a_within_season, c1b_year_over_year, c2_portability,
    METRICS_EXPECTED, MIN_GAMES_FP,
)

PLAYS_PER_WEEK = 70
LATENT = ["db", "shotgun", "nohuddle", "pa", "sec", "adot_mu", "adot_sd", "rb", "te", "motion"]
BASE = dict(db=0.58, shotgun=0.62, nohuddle=0.08, pa=0.26, sec=27.0,
            adot_mu=7.5, adot_sd=8.0, rb=0.18, te=0.22, motion=0.45)
SPREAD = dict(db=0.06, shotgun=0.10, nohuddle=0.04, pa=0.07, sec=2.5,
              adot_mu=1.0, adot_sd=0.8, rb=0.04, te=0.05, motion=0.10)

# a mid-season replacement inherits the install and cannot fully reshape the offense.
# Modelling that makes C1a CONSERVATIVE -- the claim made in the study docstring.
MIDSEASON_DAMP = 0.6


def synth_pbp(PC, rho, seed=7):
    """Generate play-by-play from planted team + coach effects, wired through the real stints."""
    rng = np.random.default_rng(seed)
    teams = sorted(PC.team.unique())
    coaches = sorted(PC.playcaller.unique())

    T = {t: {k: rng.normal(0, SPREAD[k]) for k in LATENT} for t in teams}
    C = {c: {k: rng.normal(0, SPREAD[k] * rho) for k in LATENT} for c in coaches}

    rows, motion_flags = [], []
    pid = 0
    for _, r in PC.iterrows():
        # a coach arriving mid-season only partially imposes his scheme
        eff = MIDSEASON_DAMP if (r["split"] == "midseason" and r["week_start"] > 1) else 1.0
        par = {k: BASE[k] + T[r["team"]][k] + eff * C[r["playcaller"]][k] for k in LATENT}
        for k in ("db", "shotgun", "nohuddle", "pa", "rb", "te", "motion"):
            par[k] = float(np.clip(par[k], 0.02, 0.95))
        par["adot_sd"] = max(par["adot_sd"], 3.0)

        for wk in range(int(r["week_start"]), int(r["week_end"]) + 1):
            gid = f"{r['season']}_{wk:02d}_{r['team']}"
            gsr = 3600.0
            for i in range(PLAYS_PER_WEEK):
                pid += 1
                burn = max(4.0, rng.normal(par["sec"], 6.0))
                gsr -= burn
                drive = i // 6
                down = int(rng.choice([1, 2, 3], p=[0.42, 0.36, 0.22]))
                qtr = min(4, 1 + int((3600 - gsr) / 900))
                sd = int(rng.normal(0, 9))
                db = int(rng.random() < min(0.95, par["db"] + (0.05 if down == 1 else 0.0)))
                ay = float(rng.normal(par["adot_mu"], par["adot_sd"])) if db else np.nan
                if db:
                    u = rng.random()
                    rp = "RB" if u < par["rb"] else ("TE" if u < par["rb"] + par["te"] else "WR")
                else:
                    rp = None
                rows.append((
                    gid, pid, int(r["season"]), wk, r["team"], "REG",
                    "pass" if db else "run", down, qtr, sd, gsr, drive,
                    int(rng.random() < par["shotgun"]), int(rng.random() < par["nohuddle"]),
                    db, int(db and rng.random() < par["pa"]), ay, rp,
                ))
                motion_flags.append(float(rng.random() < par["motion"]))

    pbp = pd.DataFrame(rows, columns=[
        "game_id", "play_id", "season", "week", "posteam", "season_type", "play_type",
        "down", "qtr", "score_differential", "game_seconds_remaining", "drive",
        "shotgun", "no_huddle", "qb_dropback", "play_action", "air_yards", "receiver_position",
    ])
    return pbp, pd.Series(motion_flags, index=pbp.index)


def run(rho, PC, seed=7):
    pbp, motion = synth_pbp(PC, rho, seed)
    pbp = prepare(pbp, motion)
    FULL, STINT, metrics = build_style_table(pbp, PC, use_ftn=True)
    scale = zscale(FULL, metrics)
    Z = np.vstack([zvec(r, metrics, scale) for _, r in FULL.iterrows()])
    wh = make_whitener(Z, "mahalanobis")
    rng = np.random.default_rng(99)

    _, s1a = c1a_within_season(pbp, PC, FULL, metrics, scale, wh, True, rng)
    _, s1b = c1b_year_over_year(STINT, metrics, scale, wh, rng=rng)
    _, s2 = c2_portability(STINT, FULL, metrics, scale, wh, n_perm=600, rng=rng)
    return s1a, s1b, s2


def main():
    PC = pd.read_csv("playcallers.csv")
    PC = PC[PC.season.between(2022, 2025)]
    PC = PC[~PC["split"].isin(["within_game", "contested"])]

    print("=" * 84)
    print("SELF-TEST — planting known coach effects and checking the study recovers them")
    print("=" * 84)
    print(f"design under test: {len(PC)} stints | "
          f"{(PC.split=='midseason').sum()//2} within-season changes | "
          f"{PC.playcaller.nunique()} playcallers")
    print(f"generative model: style = base + T[team] + C[coach];  "
          f"expected alpha = rho^2/(1+rho^2)\n")

    fails = []
    print(f"{'rho':>5} {'exp a':>6} | {'C1a d':>7} {'C1a p':>7} {'C1a':>5} | "
          f"{'a_hat':>6} {'lift':>7} {'C2 p':>7} {'C2':>5} | {'v1 carry':>9}")
    print("-" * 84)

    for rho, exp_c1a, exp_c2 in [(0.0, False, False), (0.8, True, True), (1.5, True, True)]:
        exp_a = rho ** 2 / (1 + rho ** 2)
        s1a, s1b, s2 = run(rho, PC)
        c1a_ok = s1a.get("PASS", False)
        c2_ok = s2.get("PASS", False)
        print(f"{rho:>5.1f} {exp_a:>6.2f} | {s1a['cohens_d']:>+7.2f} {s1a['p_perm']:>7.4f} "
              f"{'PASS' if c1a_ok else 'FAIL':>5} | "
              f"{s2['alpha']:>6.2f} {s2['oos_lift']:>+7.1%} {s2['p_perm']:>7.4f} "
              f"{'PASS' if c2_ok else 'FAIL':>5} | {s2['v1_carry_rate']:>8.0%}")

        if c1a_ok != exp_c1a:
            fails.append(f"rho={rho}: C1a returned {c1a_ok}, expected {exp_c1a}")
        if c2_ok != exp_c2:
            fails.append(f"rho={rho}: C2 returned {c2_ok}, expected {exp_c2}")
        if rho > 0 and abs(s2["alpha"] - exp_a) > 0.18:
            fails.append(f"rho={rho}: alpha={s2['alpha']:.2f}, expected ~{exp_a:.2f}")
        if rho == 0 and abs(s2["alpha"]) > 0.20:
            fails.append(f"rho=0: alpha={s2['alpha']:.2f}, expected ~0 (pure team property)")

        # THE HEADLINE ASSERTION.
        # rho=0.8 is a coach effect 80% the size of the team effect -- a large, obviously
        # useful fingerprint. v1's carry rate should record it as a hard FAIL (< 60%) while
        # the new C2 recovers it. That is the bug, demonstrated on the real design.
        if rho == 0.8:
            v1_verdict = "PASS" if s2["v1_carry_rate"] > 0.60 else "FAIL"
            if v1_verdict != "FAIL":
                fails.append("rho=0.8: expected v1's carry rate to FAIL a real fingerprint")
            if not c2_ok:
                fails.append("rho=0.8: new C2 failed to recover a real fingerprint")

    print()
    if fails:
        print("SELF-TEST FAILED:")
        for f in fails:
            print("   x " + f)
        sys.exit(1)

    print("SELF-TEST PASSED.")
    print()
    print("  * rho=0.0 : pure team property. Both tests correctly FAIL. No false positives.")
    print("  * rho=0.8 : a fingerprint 80% the size of the team effect.")
    print("              v1's carry rate: FAIL  (it is a variance-RATIO test in disguise)")
    print("              new C2:          PASS  (and returns alpha, which sizes the adjustment)")
    print("              ^ this is the bug, reproduced on the real 14-move design.")
    print("  * rho=1.5 : coach-dominant. Both PASS, alpha recovered.")
    print()
    print("  Note C1a passes at rho=0.8 DESPITE the mid-season damping (0.6) baked into the")
    print("  generator -- confirming the study's claim that C1a is a conservative FLOOR.")


if __name__ == "__main__":
    main()
