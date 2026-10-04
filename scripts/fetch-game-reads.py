#!/usr/bin/env python3
"""
DELTA Read Of A Finished Game — NFL. Writes data/game-reads.json for live.html.

DISPLAY ONLY. Nothing in the engine, the freeze or any pipeline reads this file,
and this script reads nothing DELTA produces. If it fails it writes nothing and
the previous file stands; the workflow step around it is continue-on-error, so a
failure here can never hold back market values, game logs or the Engine Audit.

WHAT IT MEASURES, per finished game, from nflverse play-by-play:
  Value added per play (EPA) and success rate (share of plays with EPA > 0),
  for each offence and for each player who touched the ball.

EVERY PLAY COUNTS (owner, 4 Oct 2026). No garbage-time filter. A play is any
row nflverse flags pass == 1 or rush == 1 — its standard definition, which
includes sacks, scrambles and plays wiped out by a defensive penalty. Kneels,
spikes, kicks and two-point tries are not plays here (nflverse gives them no
pass/rush flag).

WHO GETS EACH PLAY:
  Passer      every dropback, scored on qb_epa (nflverse's QB number: a fumble
              after the catch is the receiver's, not his). Scrambles are
              dropbacks — nflverse's `passer` column already credits them so.
  Rusher      designed runs, on epa.
  Receiver    targets, on epa.
A completed pass counts once for the passer and once for the target. That is
the point: each row is that player's own plays.

KEYED BY ESPN GAME ID — nflverse's schedule carries it (`espn` column), so
live.html matches the game exactly, never by team names.

Stores raw counts (plays, total EPA, successes); the page does the division, so
rounding happens once, at display.
"""

import json, sys
from datetime import datetime, timezone
from pathlib import Path

OUT_FILE = Path(__file__).parent.parent / "data" / "game-reads.json"


def die(msg):
    print(f"\n[DELTA] ABORTED — {msg}", file=sys.stderr)
    print("[DELTA] Nothing was written. Existing data/game-reads.json is untouched.", file=sys.stderr)
    sys.exit(1)


def main():
    try:
        import nflreadpy as nfl
    except Exception as e:
        die(f"nflreadpy not importable: {e}")

    # The season rolls by itself — no third hard-coded year to bump in the offseason.
    try:
        season = int(nfl.get_current_season())
    except Exception as e:
        die(f"could not read the current season: {e}")
    print(f"[DELTA] Game reads for {season}")

    try:
        sch = nfl.load_schedules(seasons=[season]).to_pandas()
    except Exception as e:
        die(f"schedule load failed: {e}")
    espn_of = {}
    for _, r in sch.iterrows():
        e = r.get("espn")
        if e is not None and str(e).strip() not in ("", "nan", "None"):
            espn_of[r["game_id"]] = str(e).strip().split(".")[0]

    try:
        pbp = nfl.load_pbp(seasons=[season]).to_pandas()
    except Exception as e:
        # Before Week 1 there is no file yet. That is not an error worth a red run,
        # but there is also nothing to write.
        die(f"play-by-play load failed (normal before Week 1): {e}")

    need = ["game_id", "week", "posteam", "pass", "rush", "epa", "qb_epa", "success",
            "passer_id", "rusher_id", "receiver_id"]
    missing = [c for c in need if c not in pbp.columns]
    if missing:
        die(f"play-by-play is missing columns {missing} — nflverse renamed something")

    plays = pbp[((pbp["pass"] == 1) | (pbp["rush"] == 1)) & pbp["epa"].notna() & pbp["posteam"].notna()]

    try:
        pl = nfl.load_players().to_pandas()
        who = {r["gsis_id"]: (r.get("display_name") or "", r.get("position") or "")
               for _, r in pl.iterrows() if r.get("gsis_id")}
    except Exception as e:
        die(f"player list load failed: {e}")

    games, unmapped, skipped = {}, [], []
    for gid, g in plays.groupby("game_id"):
        espn = espn_of.get(gid)
        if not espn:
            unmapped.append(gid)
            continue
        offences = sorted(g["posteam"].unique())
        if len(offences) != 2:
            skipped.append(f"{gid} ({len(offences)} offences)")
            continue

        teams = {}
        for tm, t in g.groupby("posteam"):
            teams[tm] = [int(len(t)), round(float(t["epa"].sum()), 2), int((t["success"] == 1).sum())]

        acc = {}   # player id -> [team, plays, epa, successes]
        def add(pid, tm, val, ok):
            if not pid or val != val:   # NaN check
                return
            a = acc.setdefault(pid, [tm, 0, 0.0, 0])
            a[1] += 1; a[2] += float(val); a[3] += 1 if ok else 0

        for _, r in g.iterrows():
            tm, ok = r["posteam"], r["success"] == 1
            passer, rusher, rec = r["passer_id"], r["rusher_id"], r["receiver_id"]
            passer = passer if isinstance(passer, str) else None
            rusher = rusher if isinstance(rusher, str) else None
            rec    = rec    if isinstance(rec, str)    else None
            if passer:
                qv = r["qb_epa"] if r["qb_epa"] == r["qb_epa"] else r["epa"]
                add(passer, tm, qv, ok)
            if rusher and rusher != passer:
                add(rusher, tm, r["epa"], ok)
            if rec and rec != passer:
                add(rec, tm, r["epa"], ok)

        rows = []
        for pid, (tm, n, epa, s) in acc.items():
            name, pos = who.get(pid, ("", ""))
            if not name:
                continue   # an id nflverse cannot name is left out, never shown as a code
            rows.append([name, tm, pos, n, round(epa, 2), s])
        rows.sort(key=lambda x: -x[4])
        games[espn] = {"wk": int(g["week"].iloc[0]), "t": teams, "p": rows}

    if unmapped:
        print(f"[DELTA] WARNING: {len(unmapped)} game(s) with no ESPN id in the schedule, left out: {unmapped}")
    if skipped:
        print(f"[DELTA] WARNING: skipped {skipped}")
    if plays["game_id"].nunique() and not games:
        die("play-by-play has games but none could be written")

    # Spot check, printed so a run log shows real numbers.
    for espn, gm in list(games.items())[-2:]:
        line = " · ".join(f"{tm} {v[1]/v[0]:+.2f}/play {100*v[2]/v[0]:.0f}% ({v[0]} plays)" for tm, v in gm["t"].items())
        top = gm["p"][0] if gm["p"] else None
        print(f"[DELTA] {espn} wk{gm['wk']}: {line}" + (f" | top: {top[0]} {top[4]:+.1f} on {top[3]}" if top else ""))

    out = {"season": season, "built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "games": games}
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, separators=(",", ":")))
    print(f"[DELTA] Wrote {OUT_FILE.name}: {len(games)} games, {OUT_FILE.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
