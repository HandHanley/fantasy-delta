#!/usr/bin/env python3
"""
SELF-TEST for rb_dominator_weight_study.py

Plants a KNOWN weight in synthetic running backs, runs them through the REAL selection
procedure from the study, and asserts the procedure recovers what was planted.

Why this runs first and aborts the workflow on failure:
  The entire point of the pre-registration is that the first pass at this question
  produced w = 0.30 by picking the peak of a sweep, and that answer did not survive
  contact with held-out data. A procedure that cannot recover a weight it was GIVEN has
  no business reporting a weight it INFERRED. Better to die on synthetic data in a few
  seconds than publish a confident wrong number.

Three properties are asserted:
  1. STRONG SIGNAL, weight below 0.5  -> recovers near the planted weight.
  2. STRONG SIGNAL, weight above 0.5  -> recovers near the planted weight.
     (1 and 2 together prove the 1-SE rule's pull toward 0.50 does not overwhelm real
     signal in either direction — the failure mode that would make the study always
     answer 0.50 and look reassuringly sensible while being useless.)
  3. PURE NOISE -> returns exactly 0.50 and the power check FAILS.
     The study must not invent a weight from nothing.
"""
import sys, random
import rb_dominator_weight_study as S


def synth(n, w_true, noise, seed):
    """Synthetic backs. Outcome is driven by the planted blend plus noise, so the
    procedure has a known right answer to find."""
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        rdom = rng.betavariate(2, 4)          # rushing share, right-skewed like real data
        dom = rng.betavariate(1.5, 12)        # receiving share, much smaller
        signal = w_true * rdom + (1 - w_true) * dom
        outcome = signal + rng.gauss(0, noise)
        rows.append({'n': f'P{i}', 'rdom': rdom, 'dom': dom, 'tpct': 0.5,
                     'outcome': outcome})
    return rows


def check(label, rows, expect, tol=None, expect_power_fail=False):
    res = S.select_weight(rows, repeats=60, seed=3)
    w = res['selected']
    power_ok = res['has_signal'] and res['can_discriminate']
    print(f"  {label}")
    print(f"     selected w = {w:.2f}   (expected {expect})   "
          f"signal={'Y' if res['has_signal'] else 'N'} "
          f"discriminates={'Y' if res['can_discriminate'] else 'N'}")
    ok = True
    if tol is not None:
        if abs(w - expect) > tol:
            print(f"     FAIL: selected {w:.2f} is more than {tol} from planted {expect}")
            ok = False
    else:
        if w != expect:
            print(f"     FAIL: expected exactly {expect}, got {w:.2f}")
            ok = False
    if expect_power_fail and power_ok:
        print("     FAIL: expected the power check to FAIL on pure noise, but it passed")
        ok = False
    if not expect_power_fail and not power_ok:
        print("     FAIL: expected the power check to pass on strong signal")
        ok = False
    print("     -> PASS" if ok else "     -> FAIL")
    return ok


def main():
    print("=" * 72)
    print("SELF-TEST — can the selection procedure recover a weight it was given?")
    print("=" * 72)
    allok = True

    print("\n1. Strong signal, planted w = 0.20 (receiving-heavy)")
    allok &= check("n=400, low noise", synth(400, 0.20, 0.02, 11), 0.20, tol=0.15)

    print("\n2. Strong signal, planted w = 0.80 (rushing-heavy)")
    allok &= check("n=400, low noise", synth(400, 0.80, 0.02, 12), 0.80, tol=0.15)

    print("\n3. Pure noise — outcome unrelated to either input")
    rng = random.Random(99)
    noise_rows = synth(300, 0.5, 0.0, 13)
    for r in noise_rows:
        r['outcome'] = rng.gauss(0, 1)          # sever the link entirely
    allok &= check("n=300, no signal", noise_rows, 0.50, tol=None, expect_power_fail=True)

    print("\n" + "=" * 72)
    if allok:
        print("SELF-TEST PASSED — the procedure recovers planted weights and refuses to")
        print("invent one from noise. Safe to run on real data.")
        print("=" * 72)
        return 0
    print("SELF-TEST FAILED — the study will NOT be run on real data.")
    print("=" * 72)
    return 1


if __name__ == '__main__':
    sys.exit(main())
