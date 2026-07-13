#!/usr/bin/env python3
"""
SELF-TEST for scheme_ship_gate_study.py

Imports the shipping functions (NULL-RESULTS lesson #2 -- never a retyped copy).

WHAT IT CHECKS
    The whole point of this study is THE COEFFICIENT: how big is the coordinator-change
    penalty, really? A pass/fail is useless -- you cannot fix the engine with a pass/fail.

    So: plant a KNOWN penalty in a synthetic panel and check the study reads it back.

    planted  0%   -> must FAIL. No false positives on a lever that does nothing.
    planted -3%   -> must recover ~-3%. A small real effect must be read as SMALL,
                     not rounded up to the engine's -12%.
    planted -12%  -> must recover ~-12% and PASS. If the engine is right, the study
                     must be able to say so.

    The middle case is the one that matters. If the engine applies -12% and the truth
    is -3%, the study has to be able to TELL THEM APART -- otherwise it cannot fix
    anything, it can only agree or disagree.
"""

import sys
import numpy as np
import pandas as pd


from scheme_ship_gate_study import race, loso_rmse, gamefp

BASE = ["ppg", "vol_pg", "age"]
N_TEAMS, SEASONS = 32, [2022, 2023, 2024]
PER_TEAM = 6              # ~576 WR pairs, close to what the real panel will hold


def synth_panel(effect, seed=3, noise=2.2):
    """
    core     = 0.70*ppg + 0.03*vol_pg - 0.06*age          the production core
    next_ppg = core * (1 + effect*oc_change) + noise       the scheme adjustment

    MULTIPLICATIVE, because that is exactly how delta-engine.js applies it
    (line ~4099: net = dSys + dOc + sty.total, applied as a multiplier on the projection).
    So a planted -0.12 IS the engine's worst-case dOc for a WR, in the engine's own units,
    and the study's coef_pct must read it back as -12%.

    An earlier version of this test planted the effect ADDITIVELY against the current-year
    mean while the study normalises by the NEXT-year mean. The verdicts were all correct
    and the coefficients were silently off by 1.7x. The study was right; the test was wrong.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for s in SEASONS:
        for t in range(N_TEAMS):
            oc = int(rng.random() < 0.35)          # ~35% of teams change playcallers
            fp = rng.normal(0, 1) * oc             # fingerprint feature: 0 when nobody new
            for k in range(PER_TEAM):
                ppg = max(1.0, rng.normal(12.0, 4.5))
                vol = max(1.0, rng.normal(12, 5))
                age = rng.normal(26, 3)
                core = 0.70 * ppg + 0.03 * vol - 0.06 * age
                nxt = core * (1 + effect * oc) + rng.normal(0, noise)
                rows.append(dict(player_id=f"{t}_{k}", position="WR", team=t, season=s,
                                 ppg=ppg, vol_pg=vol, age=age, next_ppg=max(0.0, nxt),
                                 oc_change=oc, fp_pass_rate_neutral=fp))
    return pd.DataFrame(rows)


def main():
    print("=" * 88)
    print("SELF-TEST — planting a known coordinator penalty, checking the study reads it back")
    print("=" * 88)
    print("The engine applies -12% to a WR on a new-coordinator team.")
    print("If the truth is -3%, the study must RULE THE ENGINE OUT without overclaiming.")
    print("If it is really -12%, it must say KEEP. Otherwise the study cannot fix anything.\n")

    rng = np.random.default_rng(42)
    ENGINE = -0.12
    fails = []
    print(f"  {'planted':>8} | {'recovered':>9} {'95% CI':>18} {'lift':>7} | decision")
    print("  " + "-" * 78)

    for planted, want in [(0.00, "ENGINE"), (-0.03, "ENGINE"), (-0.12, "KEEP")]:
        D = synth_panel(planted)
        r = race(D, "WR", BASE, ["oc_change"], "A", ENGINE, n_perm=200, n_boot=600, rng=rng)
        ci = f"[{r['ci_lo']:+.1%}, {r['ci_hi']:+.1%}]"
        got, dec = r["coef_pct"], r["decision"].split(" ")[0]
        print(f"  {planted:>7.0%}  | {got:>9.1%} {ci:>18} {r['lift']:>+7.1%} | {r['decision']}")

        if abs(got - planted) > 0.045:
            fails.append(f"planted {planted:.0%}, read {got:.1%} — cannot size the lever")
        if dec != want:
            fails.append(f"planted {planted:.0%}: said {dec}, expected {want}")

    print()
    if fails:
        print("SELF-TEST FAILED:")
        for f in fails:
            print("   x " + f)
        sys.exit(1)

    print("SELF-TEST PASSED.")
    print()
    print("  * planted   0%  -> ENGINE RULED OUT. Correct: -12% is outside the CI.")
    print("  * planted  -3%  -> ENGINE RULED OUT. THIS IS THE CASE THAT MATTERS. At n=576 the")
    print("                     study honestly CANNOT prove -3% differs from zero -- but it CAN")
    print("                     prove it is not -12%. That is decisive without being overclaimed.")
    print("  * planted -12%  -> KEEP. If the hand table is right, the study says so.")
    print()
    print("  And critically: the study NEVER says KEEP when the truth is 0% or -3%.")
    print("  It cannot be talked into validating a lever that is not there.")
    print()
    print("  Note the RMSE lift even at a PERFECTLY correct -12% is only ~+1.9%. That is why the")
    print("  usual 2% RMSE bar is NOT the gate here — it would reject the engine's own lever.")
    print("  The gate is the coefficient and its cluster-bootstrapped CI.")


if __name__ == "__main__":
    main()
