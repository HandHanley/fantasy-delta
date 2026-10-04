#!/usr/bin/env python3
"""
THIS SEASON SO FAR — the Alpha / Workhorse inputs for the season being played.
Writes data/season-so-far.json for the player cards' "2026 So Far" line.

DISPLAY ONLY (owner, 4 Oct 2026). The DELTA Score's Alpha and Workhorse are
built from the last completed season and do not move on weekly stats (§10b).
This file lets a reader see a role change as it happens without the Score
moving. Nothing in the engine's scoring, the freeze or any other pipeline
reads it. If it fails it writes nothing; the workflow step is continue-on-error.

SAME DEFINITIONS AS THE SCORE, BY CONSTRUCTION. This script does not compute a
single share itself: it imports scripts/fetch-player-stats.py and runs that
script's own fetch_season_stats(), fetch_redzone(), match_names() and
build_output() with SEASONS swapped to the current season. So "target share"
here is exactly the number the 2025 Alpha Score was built from, just for this
season. Run with --check-season 2025 to prove it: the output must reproduce
data/player-stats.json's 2025 fields exactly.

ADDED HERE, AND ONLY THIS: team_games — how many games the player's team has
played so far. The card needs it to scale a part-season onto the 17-game basis
the score formulas assume (see opportunitySoFar in delta-engine.js).
"""

import importlib.util, json, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT     = Path(__file__).parent.parent
OUT_FILE = ROOT / "data" / "season-so-far.json"
FIELDS   = ["games", "target_share", "air_yds_share", "rz_targets", "rush_share", "rz_carries"]
MIN_PLAYERS = 150   # skill players with a game this season; ~300 by Week 4


def die(msg):
    print(f"\n[DELTA] ABORTED — {msg}", file=sys.stderr)
    print("[DELTA] Nothing was written. Existing data/season-so-far.json is untouched.", file=sys.stderr)
    sys.exit(1)


def load_pipeline():
    path = ROOT / "scripts" / "fetch-player-stats.py"
    spec = importlib.util.spec_from_file_location("fps", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)          # defines functions only; main() is guarded
    return mod


def build(season, fill=True):
    mod = load_pipeline()
    nfl = mod.nfl
    mod.SEASONS = [season]                 # every pipeline function reads this global at call time

    names, _no_data, meta = mod.get_delta_players()
    if len(names) < mod.MIN_UNIVERSE:
        die(f"only {len(names)} players parsed from RAW")
    agg, _hs, _qs, _qsp = mod.fetch_season_stats()
    # No "no 2025 data" skip list here: this season's rookies DO have data.
    matched = mod.match_names(agg, names, set())
    rz = mod.fetch_redzone([season])
    if season not in rz:
        die(f"red-zone counts for {season} did not build")
    players, _h, _r, _t = mod.build_output(agg, matched, rz, None)

    # Team games played so far, regular season — counted from the SAME weekly stats
    # file the shares come from, not the schedule. The schedule posts a result hours
    # before the stats land; counting from it would add a game the shares don't yet
    # contain and understate everyone on that team until the next run.
    wk = nfl.load_player_stats(seasons=[season]).to_pandas()
    wk = wk[wk["season_type"] == "REG"]
    team_games = {tm: int(n) for tm, n in wk.groupby("team")["week"].nunique().items()}
    through = int(wk["week"].max()) if len(wk) else 0

    # The player's current team for the denominator: the row build_output used
    # (the most recent stint — the same edge behaviour as the pipeline's shares).
    team_of = {}
    for _, r in agg.iterrows():
        team_of[(r["player_name"], int(r["season"]))] = r.get("team")

    # RED-ZONE NAME GAP, display only. The pipeline finds a player's red-zone counts
    # by abbreviated name ("B.Robinson"). nflverse uses TWO letters when teammates
    # share an initial — 2026 has "Bi.Robinson" (Bijan) and "Br.Robinson" (Brian) —
    # so the pipeline reports Bijan as not found. Fixing it in the pipeline would
    # also fill one 2025 gap (Jimmy Horn's red-zone targets) and so move a DELTA
    # Score mid-season; that waits for the offseason roll (owner's call). Here, for
    # this display file only, a miss gets one more try with the two-letter form.
    rzs = rz.get(season, {})
    def two_letter(lookup, nfl_name):
        parts = [p for p in str(nfl_name).split() if p not in {"Jr.", "Jr", "Sr.", "Sr", "II", "III", "IV", "V"}]
        if len(parts) >= 2 and len(parts[0]) >= 2:
            k = parts[0][:2] + "." + parts[-1]
            if k in lookup:
                return int(lookup[k])
        return None
    filled = 0
    for dn, pdata in (players.items() if fill else ()):
        s = pdata.get(season)
        if not s:
            continue
        for fld, key in (("rz_targets", "player_rz_tgt"), ("rz_carries", "player_rz_car")):
            if s.get(fld) is None:
                v = two_letter(rzs.get(key, {}), matched[dn])
                if v is not None:
                    s[fld] = v; filled += 1
    if filled:
        print(f"[DELTA] Red-zone counts filled by the two-letter name form: {filled}")

    out, no_team = {}, []
    for dn, pdata in players.items():
        s = pdata.get(season)
        pos = meta.get(dn, (None, None))[1]
        if not s or pos not in ("RB", "WR", "TE"):
            continue
        tm = team_of.get((matched[dn], season))
        tg = team_games.get(tm)
        if not tg:
            no_team.append(dn)
            continue
        row = {k: s.get(k) for k in FIELDS}
        row["team_games"] = tg
        out[dn] = row
    if no_team:
        print(f"[DELTA] WARNING: no team games for {len(no_team)} players, left out: {no_team[:10]}")
    return out, through


def main():
    args = sys.argv[1:]
    if args[:1] == ["--check-season"]:
        # Proof of definitions: rebuild a finished season and compare with player-stats.json.
        season = int(args[1])
        out, _ = build(season, fill=False)   # the pipeline's own numbers, untouched
        ref = json.loads((ROOT / "data" / "player-stats.json").read_text())["players"]
        same = diff = 0
        for dn, row in out.items():
            r = (ref.get(dn) or {}).get(str(season))
            if not r:
                continue
            bad = [k for k in FIELDS if r.get(k) != row.get(k)]
            if bad:
                diff += 1
                if diff <= 10:
                    print(f"[DELTA] DIFF {dn}: " + ", ".join(f"{k} {r.get(k)} vs {row.get(k)}" for k in bad))
            else:
                same += 1
        print(f"[DELTA] check {season}: {same} identical, {diff} different")
        sys.exit(1 if diff else 0)

    try:
        import nflreadpy as nfl
        season = int(nfl.get_current_season())
    except Exception as e:
        die(f"could not read the current season: {e}")
    try:
        out, through = build(season)
    except SystemExit:
        raise
    except Exception as e:
        die(f"build failed: {e}")
    if len(out) < MIN_PLAYERS and through >= 2:
        die(f"only {len(out)} players with {season} games through week {through} — expected far more")

    doc = {"season": season, "through_week": through,
           "built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "players": out}
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(doc, separators=(",", ":")))
    print(f"[DELTA] Wrote {OUT_FILE.name}: {len(out)} players, through week {through}, "
          f"{OUT_FILE.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
