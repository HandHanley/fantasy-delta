#!/usr/bin/env python3
"""
DELTA — System Score v2 research fetch (scripts/fetch-style-rates.py)

Pulls the raw material for testing Steve's offense-style hypotheses:
  H1  pre-snap motion rate  -> offensive success, esp. RB/WR (McVay/Shanahan thesis)
  H2  play-action rate      -> creativity / big-play environment (QB/WR)
  H3  12-personnel rate     -> TE value up, slot-WR3 targets down

Sources (all free nflverse, same stack as the other pipelines):
  - FTN charting (load_ftn_charting, 2022+): is_motion, is_play_action per play,
    plus is_screen_pass / is_rpo / is_no_huddle as free extras.
    NOTE: exact field names are confirmed on first CI run — the sandbox can't
    reach nflverse, so this script prints the schema and tolerates absences.
  - PBP (load_pbp): join keys + pass/rush classification + EPA per play, so the
    validation step can correlate style vs. efficiency directly.
  - Snap counts (load_snap_counts): TE2 snap-rate proxy for 12-personnel
    (formal participation data ends ~2023; TE snap share covers the full window).

Output: data/style-rates.json
  {
    generated, seasons, note,
    teams: { "2022|LAR": { motion_pct, pa_pct, screen_pct, rpo_pct,
                           te2_snap_proxy, plays, pass_epa, rush_epa,
                           pass_rate, proe? }, ... }
  }
RESEARCH ARTIFACT ONLY — nothing in the app reads this file. The validation
harness consumes it; wiring into SYS happens only if the hypotheses survive
out-of-sample testing (train 2022-24, hold out 2025).
"""
import json, os, sys, datetime

try:
    import nflreadpy as nfl
    import polars as pl  # noqa: F401
except ImportError:
    os.system("pip install 'nflreadpy@git+https://github.com/nflverse/nflreadpy' polars pyarrow pandas --quiet")
    import nflreadpy as nfl
    import polars as pl  # noqa: F401

SEASONS = [2022, 2023, 2024, 2025]   # FTN charting floor is 2022


def to_pd(df):
    return df.to_pandas() if hasattr(df, "to_pandas") else df


def main():
    import pandas as pd

    # ── FTN charting ─────────────────────────────────────────────
    print(f"[DELTA] loading FTN charting {SEASONS} ...")
    ftn = to_pd(nfl.load_ftn_charting(seasons=SEASONS))
    print(f"[DELTA] FTN rows: {len(ftn)}")
    print(f"[DELTA] FTN schema: {sorted(ftn.columns.tolist())}")

    # ── PBP for join keys, team attribution, EPA ─────────────────
    print("[DELTA] loading PBP ...")
    pbp = to_pd(nfl.load_pbp(seasons=SEASONS))
    keep = [c for c in ["game_id", "play_id", "season", "posteam", "pass", "rush",
                        "epa", "qb_dropback", "season_type"] if c in pbp.columns]
    pbp = pbp[keep]
    if "season_type" in pbp.columns:
        pbp = pbp[pbp["season_type"] == "REG"]

    # FTN keys are nflverse standard: nflverse_game_id + nflverse_play_id
    gk = "nflverse_game_id" if "nflverse_game_id" in ftn.columns else "game_id"
    pk = "nflverse_play_id" if "nflverse_play_id" in ftn.columns else "play_id"
    # FTN carries its own season/week — drop pre-merge so PBP's 'season' survives
    # un-suffixed (the _x/_y rename was breaking the groupby)
    ftn = ftn.drop(columns=[c for c in ("season", "week") if c in ftn.columns])
    m = pbp.merge(ftn, left_on=["game_id", "play_id"], right_on=[gk, pk], how="inner")
    print(f"[DELTA] joined rows: {len(m)}")

    def flag(col):
        if col in m.columns:
            return m[col].fillna(False).astype(bool)
        print(f"[DELTA] WARNING: FTN field '{col}' absent — rate will be null")
        return None

    is_motion = flag("is_motion")
    is_pa     = flag("is_play_action")
    is_screen = flag("is_screen_pass")
    is_rpo    = flag("is_rpo")

    plays = m[(m.get("pass", 0) == 1) | (m.get("rush", 0) == 1)].copy()
    dropbacks = plays[plays.get("qb_dropback", plays.get("pass", 0)) == 1]

    teams = {}
    for (season, team), g in plays.groupby(["season", "posteam"]):
        if not team or str(team) == "nan":
            continue
        key = f"{int(season)}|{team}"
        db = dropbacks[(dropbacks["season"] == season) & (dropbacks["posteam"] == team)]
        def rate(series, frame):
            if series is None:
                return None
            s = series.loc[frame.index]
            return round(float(s.mean()) * 100, 2) if len(s) else None
        teams[key] = {
            "plays": int(len(g)),
            "motion_pct": rate(is_motion, g),          # all offensive plays
            "pa_pct":     rate(is_pa, db),             # of dropbacks
            "screen_pct": rate(is_screen, db),
            "rpo_pct":    rate(is_rpo, g),
            "pass_rate":  round(float((g["pass"] == 1).mean()) * 100, 2),
            "pass_epa":   round(float(g.loc[g["pass"] == 1, "epa"].mean()), 4) if "epa" in g else None,
            "rush_epa":   round(float(g.loc[g["rush"] == 1, "epa"].mean()), 4) if "epa" in g else None,
        }

    # ── TE2 snap proxy for 12-personnel ─────────────────────────
    print("[DELTA] loading snap counts for TE2 proxy ...")
    try:
        sn = to_pd(nfl.load_snap_counts(seasons=SEASONS))
        if "game_type" in sn.columns:
            sn = sn[sn["game_type"] == "REG"]
        te = sn[sn["position"] == "TE"]
        for (season, team), g in te.groupby(["season", "team"]):
            key = f"{int(season)}|{team}"
            if key not in teams:
                continue
            # per game, rank TEs by snap pct; TE2's average snap share is the proxy
            per_game = g.groupby("game_id").apply(
                lambda x: x.nlargest(2, "offense_pct")["offense_pct"].tolist()
            )
            te2 = [v[1] for v in per_game if len(v) > 1]
            teams[key]["te2_snap_proxy"] = round(float(sum(te2) / len(te2)) * 100, 2) if te2 else 0.0
    except Exception as e:
        print(f"[DELTA] WARNING: snap proxy failed ({e}) — te2_snap_proxy omitted")

    out = {
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "seasons": SEASONS,
        "note": ("System Score v2 RESEARCH ARTIFACT — team-season offense-style rates "
                 "(FTN charting + TE2 snap proxy). Nothing in the app reads this file. "
                 "Validation gate: train 2022-24, hold out 2025; wire only what survives."),
        "teams": teams,
    }
    os.makedirs("data", exist_ok=True)
    with open("data/style-rates.json", "w") as f:
        json.dump(out, f, indent=1)
    print(f"[DELTA] wrote data/style-rates.json — {len(teams)} team-seasons")
    nulls = sum(1 for v in teams.values() if v.get("motion_pct") is None)
    if nulls:
        print(f"[DELTA] WARNING: {nulls} team-seasons missing motion_pct — check FTN schema output above")


if __name__ == "__main__":
    sys.exit(main())
