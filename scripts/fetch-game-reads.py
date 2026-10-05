#!/usr/bin/env python3
"""
DELTA Read Of A Finished Game — NFL. Writes data/game-reads.json for live.html.

DISPLAY ONLY. Nothing in the engine, the freeze or any pipeline reads this file.
If it fails it writes nothing and the previous file stands; the workflow step
around it is continue-on-error, so a failure can never hold back the nightly.

EACH PLAYER IS MEASURED THE WAY DELTA MEASURES HIM (owner, 4 Oct 2026), beside
the 2025 number for the same measure:

  QB   EPA per dropback — scripts/fetch-player-stats.py's own definition: plays
       with a named passer and qb_dropback == 1, mean of qb_epa. (Scrambles have
       no named passer, so DELTA leaves them out; so does this.) 2025: the e25
       value DELTA itself stores in data/player-stats.json.
  RB   EPA per carry — the same file's definition: plays with a named rusher and
       rush_attempt == 1, mean of epa. 2025: e25 from data/player-stats.json.
  WR / TE  Yards per route run. DELTA's own figure is hand-entered; no free source
       publishes routes during a season. Last season's routes ARE known (nflverse
       participation: who was on the field for each dropback), and counting them
       reproduces DELTA's hand-entered 2025 YPRR at 0.99 — so the "last season"
       column and the tiers use real routes. A game's routes are estimated as
       snaps x the team's dropback rate, then corrected by the receiver's own ratio
       of real to estimated routes last season (position median for newcomers).
       Tested on 2025 with 2024 ratios: typical miss vs real routes 0.10 -> 0.04.

The previous version (success rate, a team table, every play for everyone)
showed measures DELTA does not read and was retired the same day.

KEYED BY ESPN GAME ID — nflverse's schedule carries it, so live.html matches the
game exactly. Regular season and playoffs both; the 2025 baselines are regular
season, as DELTA's are.
"""

import json, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT     = Path(__file__).parent.parent
OUT_FILE = ROOT / "data" / "game-reads.json"
EFF_FILE = ROOT / "data" / "efficiency.json"   # the same numbers by PLAYER, for the cards and rankings
MIN_QB, MIN_RB, MIN_ROUTES = 5, 3, 5        # below this a game line is not shown at all
# Below this, the line shows but gets no tier word: one sack or one long catch would
# decide it (owner, 4 Oct — "Elite" on 14 routes was the example). live.html applies it.
TIER_MIN = {"QB": 15, "RB": 8, "WR": 15, "TE": 15}


def die(msg):
    print(f"\n[DELTA] ABORTED — {msg}", file=sys.stderr)
    print("[DELTA] Nothing was written. Existing data/game-reads.json is untouched.", file=sys.stderr)
    sys.exit(1)


def est_routes(nfl, season, pbp):
    """{(game_id, gsis_id): (rec_yds, est_routes, team)} for one season."""
    plays = pbp[((pbp["pass"] == 1) | (pbp["rush"] == 1)) & pbp["posteam"].notna()]
    dbr = plays.groupby(["game_id", "posteam"])["qb_dropback"].mean().to_dict()
    gid_of = {(int(w), t): g for g, w, t in plays[["game_id", "week", "posteam"]].drop_duplicates().itertuples(index=False)}

    sc = nfl.load_snap_counts(seasons=[season]).to_pandas()
    pl = nfl.load_players().to_pandas()
    gsis_of = {r.pfr_id: r.gsis_id for r in pl.itertuples() if isinstance(r.pfr_id, str) and isinstance(r.gsis_id, str)}
    routes = {}
    for r in sc.itertuples():
        g = gsis_of.get(r.pfr_player_id)
        rate = dbr.get((r.game_id, r.team))
        if g and rate is not None and r.offense_snaps == r.offense_snaps:
            routes[(r.game_id, g)] = (float(r.offense_snaps) * float(rate), r.team)

    ps = nfl.load_player_stats(seasons=[season]).to_pandas()
    yds = {}
    for r in ps.itertuples():
        gid = gid_of.get((int(r.week), r.team))
        if gid and isinstance(r.player_id, str):
            yds[(gid, r.player_id)] = float(r.receiving_yards or 0)
    return {k: (yds.get(k, 0.0), v[0], v[1]) for k, v in routes.items()}


def main():
    try:
        import nflreadpy as nfl
        season = int(nfl.get_current_season())
    except Exception as e:
        die(f"nflreadpy / current season unavailable: {e}")
    print(f"[DELTA] Game reads for {season}")

    try:
        sch = nfl.load_schedules(seasons=[season]).to_pandas()
        pbp = nfl.load_pbp(seasons=[season]).to_pandas()
        prev = nfl.load_pbp(seasons=[season - 1]).to_pandas()
        prev = prev[prev["season_type"] == "REG"]
        pl = nfl.load_players().to_pandas()
    except Exception as e:
        die(f"nflverse load failed (normal before Week 1): {e}")

    need = ["game_id", "week", "posteam", "pass", "rush", "epa", "qb_epa", "qb_dropback",
            "rush_attempt", "passer_player_id", "rusher_player_id"]
    missing = [c for c in need if c not in pbp.columns]
    if missing:
        die(f"play-by-play is missing columns {missing} — nflverse renamed something")

    espn_of = {r.game_id: str(r.espn).split(".")[0] for r in sch.itertuples()
               if r.espn is not None and str(r.espn).strip() not in ("", "nan", "None")}
    who = {r.gsis_id: (r.display_name or "", r.position or "") for r in pl.itertuples() if isinstance(r.gsis_id, str)}

    # 2025 baselines. QB / RB: DELTA's own stored figure, by the name DELTA uses.
    try:
        stats_epa = json.loads((ROOT / "data" / "player-stats.json").read_text()).get("epa", {})
    except Exception as e:
        die(f"data/player-stats.json unreadable: {e}")
    ekey = f"e{str(season - 1)[-2:]}"
    # WR / TE: the same estimate as the game line, over last season.
    try:
        prev_routes = est_routes(nfl, season - 1, prev)
        cur_routes = est_routes(nfl, season, pbp)
    except Exception as e:
        die(f"route estimate failed: {e}")
    # ONE SCALE FOR RECEIVERS (4 Oct 2026). Last season's ROUTES ARE KNOWN: nflverse's
    # participation file lists who was on the field for every dropback, and counting
    # those reproduces DELTA's hand-entered 2025 YPRR at 0.99 (112 receivers). So:
    #   - last season's YPRR (the "2025" column and the tiers) uses real routes;
    #   - this season's snap estimate is corrected by each receiver's OWN ratio of real
    #     to estimated routes last season (players new since then get their position's
    #     median ratio). Tested on 2025 using 2024 ratios: typical miss against real
    #     routes fell from 0.10 to 0.04 yards per route.
    # If participation is missing (it arrives after a season ends), everything falls
    # back to the plain estimate on both sides, still like for like.
    prev_yds, prev_est = {}, {}
    for (gid, pid), (y, r, _t) in prev_routes.items():
        prev_yds[pid] = prev_yds.get(pid, 0.0) + y; prev_est[pid] = prev_est.get(pid, 0.0) + r
    real_routes = {}
    try:
        part = nfl.load_participation(seasons=[season - 1]).to_pandas()
        dbk = prev[prev["qb_dropback"] == 1][["game_id", "play_id"]]
        mm = dbk.merge(part[["nflverse_game_id", "play_id", "offense_players"]],
                       left_on=["game_id", "play_id"], right_on=["nflverse_game_id", "play_id"])
        for cell in mm["offense_players"].dropna():
            for pid in str(cell).split(";"):
                if pid: real_routes[pid] = real_routes.get(pid, 0) + 1
    except Exception as e:
        print(f"[DELTA] participation for {season - 1} unavailable ({e}) — receivers use the plain estimate")
    posof0 = {pid: pos for pid, (_n, pos) in who.items()}
    if real_routes:
        base_yprr = {pid: prev_yds.get(pid, 0.0) / n for pid, n in real_routes.items()
                     if n >= 100 and posof0.get(pid) in ("WR", "TE")}
        ratio = {pid: real_routes[pid] / prev_est[pid] for pid in real_routes
                 if prev_est.get(pid, 0) >= 150 and real_routes[pid] >= 150 and posof0.get(pid) in ("WR", "TE")}
        import statistics
        pos_med = {P: statistics.median([v for pid, v in ratio.items() if posof0.get(pid) == P] or [1.0]) for P in ("WR", "TE")}
        cur_routes = {k: (y, r * ratio.get(k[1], pos_med.get(posof0.get(k[1]), 1.0)), t)
                      for k, (y, r, t) in cur_routes.items()}
        print(f"[DELTA] Receivers: real routes for {len(base_yprr)} ({season - 1}); own route ratio for {len(ratio)}; "
              f"position medians WR {pos_med['WR']:.3f} TE {pos_med['TE']:.3f}")
    else:
        base_yprr = {pid: prev_yds[pid] / prev_est[pid] for pid in prev_est if prev_est[pid] >= 100}

    # TIERS, from last season, per position, among regular players (DELTA's own season
    # floors: 50 dropbacks, 40 carries; ~100 estimated routes for receivers).
    #   [bottom-quarter line, top-quarter line, top-10% line]
    #   below the first: Below Typical · up to the second: Typical · up to the third: Top Tier · above: Elite
    import numpy as np
    def cuts(vals):
        v = np.array(list(vals), dtype=float)
        return [round(float(np.percentile(v, k)), 3) for k in (25, 75, 90)] if len(v) >= 20 else None
    posof = {pid: pos for pid, (_n, pos) in who.items()}
    pq = prev[prev["passer_player_id"].notna() & (prev["qb_dropback"] == 1) & prev["qb_epa"].notna()]
    pq = pq.groupby("passer_player_id")["qb_epa"].agg(["mean", "count"])
    pr = prev[prev["rusher_player_id"].notna() & (prev["rush_attempt"] == 1) & prev["epa"].notna()]
    pr = pr.groupby("rusher_player_id")["epa"].agg(["mean", "count"])
    tiers = {
        "QB": cuts(r["mean"] for pid, r in pq.iterrows() if r["count"] >= 50 and posof.get(pid) == "QB"),
        "RB": cuts(r["mean"] for pid, r in pr.iterrows() if r["count"] >= 40 and posof.get(pid) == "RB"),
        "WR": cuts(v for pid, v in base_yprr.items() if posof.get(pid) == "WR"),
        "TE": cuts(v for pid, v in base_yprr.items() if posof.get(pid) == "TE"),
    }
    if any(v is None for v in tiers.values()):
        die(f"could not set tiers from {season - 1}: {tiers}")
    print(f"[DELTA] Tiers from {season - 1}: {tiers}")

    # THIS SEASON SO FAR, regular season, same definitions as the game line.
    reg = pbp[pbp["season_type"] == "REG"]
    sq = reg[reg["passer_player_id"].notna() & (reg["qb_dropback"] == 1) & reg["qb_epa"].notna()]
    sofar_qb = sq.groupby("passer_player_id")["qb_epa"].agg(["mean", "count"]).to_dict("index")
    sr = reg[reg["rusher_player_id"].notna() & (reg["rush_attempt"] == 1) & reg["epa"].notna()]
    sofar_rb = sr.groupby("rusher_player_id")["epa"].agg(["mean", "count"]).to_dict("index")
    reg_games = set(reg["game_id"].unique())
    sofar_rec = {}
    for (gid, pid), (y, r, _t) in cur_routes.items():
        if gid in reg_games:
            a = sofar_rec.setdefault(pid, [0.0, 0.0]); a[0] += y; a[1] += r
    def sofar(pid, pos):
        if pos == "QB":
            v = sofar_qb.get(pid); return (round(float(v["mean"]), 3), int(v["count"])) if v else (None, 0)
        if pos == "RB":
            v = sofar_rb.get(pid); return (round(float(v["mean"]), 3), int(v["count"])) if v else (None, 0)
        v = sofar_rec.get(pid)
        return (round(v[0] / v[1], 2), int(round(v[1]))) if v and v[1] > 0 else (None, 0)

    per_game = {}          # gsis id -> [[week, opponent, value, count], ...], regular season
    by_game = {}
    for (gid, pid), v in cur_routes.items():
        by_game.setdefault(gid, {})[(gid, pid)] = v
    games, unmapped = {}, []
    for gid, g in pbp.groupby("game_id"):
        espn = espn_of.get(gid)
        if not espn:
            unmapped.append(gid); continue
        offences = sorted(g["posteam"].dropna().unique())
        if len(offences) != 2:
            continue
        rows = []
        opp = lambda tm: next((o for o in offences if o != tm), "")
        # QB: named passer on a dropback, qb_epa — DELTA's definition
        qb = g[g["passer_player_id"].notna() & (g["qb_dropback"] == 1) & g["qb_epa"].notna()]
        for (pid, tm), t in qb.groupby(["passer_player_id", "posteam"]):
            name, pos = who.get(pid, ("", ""))
            if pos != "QB" or not name or len(t) < MIN_QB:
                continue
            b = stats_epa.get(name, {}).get(ekey)
            rows.append([name, tm, "QB", round(float(t["qb_epa"].mean()), 3), int(len(t)), b, *sofar(pid, "QB")])
            if gid in reg_games: per_game.setdefault(pid, []).append([int(g["week"].iloc[0]), opp(tm), round(float(t["qb_epa"].mean()), 3), int(len(t))])
        # RB: named rusher on a rush attempt, epa — DELTA's definition
        rb = g[g["rusher_player_id"].notna() & (g["rush_attempt"] == 1) & g["epa"].notna()]
        for (pid, tm), t in rb.groupby(["rusher_player_id", "posteam"]):
            name, pos = who.get(pid, ("", ""))
            if pos != "RB" or not name or len(t) < MIN_RB:
                continue
            b = stats_epa.get(name, {}).get(ekey)
            rows.append([name, tm, "RB", round(float(t["epa"].mean()), 3), int(len(t)), b, *sofar(pid, "RB")])
            if gid in reg_games: per_game.setdefault(pid, []).append([int(g["week"].iloc[0]), opp(tm), round(float(t["epa"].mean()), 3), int(len(t))])
        # WR / TE: estimated yards per route run, same estimate both sides
        for (g2, pid), (y, r, tm) in by_game.get(gid, {}).items():
            name, pos = who.get(pid, ("", ""))
            if r < MIN_ROUTES or pos not in ("WR", "TE") or not name or tm not in offences:
                continue      # a team code that doesn't match a side: left out, never guessed
            b = base_yprr.get(pid)
            rows.append([name, tm, pos, round(y / r, 2), int(round(r)), round(b, 2) if b is not None else None, *sofar(pid, pos)])
            if gid in reg_games: per_game.setdefault(pid, []).append([int(g["week"].iloc[0]), opp(tm), round(y / r, 2), int(round(r))])
        games[espn] = {"wk": int(g["week"].iloc[0]), "t": {o: 1 for o in offences}, "p": rows}

    if unmapped:
        print(f"[DELTA] WARNING: {len(unmapped)} game(s) with no ESPN id, left out: {unmapped}")
    if pbp["game_id"].nunique() and not games:
        die("play-by-play has games but none could be written")

    for espn, gm in list(games.items())[-1:]:
        for r in gm["p"][:8]:
            print(f"[DELTA] {espn}: {r}")
    out = {"season": season, "built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           # v3: rows are [name, team, pos, game value, game count, last season,
           #               this season so far, so-far count]; tiers and their minimums ride along.
           "v": 3, "tiers": tiers, "tier_min": TIER_MIN, "games": games}
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, separators=(",", ":")))
    print(f"[DELTA] Wrote {OUT_FILE.name}: {len(games)} games, {OUT_FILE.stat().st_size:,} bytes")
    # The by-player file is a second, separate output: if it fails, the game file above
    # still stands and this run still counts as done.
    try:
      write_efficiency(season, tiers, posof, who, stats_epa, ekey, base_yprr, sofar, per_game,
                     dists={"QB": [r["mean"] for pid, r in pq.iterrows() if r["count"] >= 50 and posof.get(pid) == "QB"],
                            "RB": [r["mean"] for pid, r in pr.iterrows() if r["count"] >= 40 and posof.get(pid) == "RB"],
                            "WR": [v for pid, v in base_yprr.items() if posof.get(pid) == "WR"],
                            "TE": [v for pid, v in base_yprr.items() if posof.get(pid) == "TE"]})
    except (Exception, SystemExit) as e:
      print(f"[DELTA] WARNING: efficiency.json not written ({e}); game-reads.json is unaffected")


SEASON_MIN = {"QB": 60, "RB": 25, "WR": 40, "TE": 40}   # season-so-far floor for a tier / a ranking


def write_efficiency(season, tiers, posof, who, stats_epa, ekey, base_yprr, sofar, per_game, dists):
    """data/efficiency.json — the Read's numbers by PLAYER, under DELTA's own names,
    for the player card's 2026 So Far box, the Game Log's Efficiency view and the
    rankings' optional Efficiency columns. Display only, like everything here.
    Names: matched with scripts/fetch-player-stats.py's own match_names(), so a
    player is filed under exactly the name the rest of DELTA uses.
    dist: last season's spread at each position, in 5% steps (21 points), so a page
    can place any value as a percentile without carrying every player."""
    import importlib.util, numpy as np, pandas as pd
    spec = importlib.util.spec_from_file_location("fps", ROOT / "scripts" / "fetch-player-stats.py")
    fps = importlib.util.module_from_spec(spec); spec.loader.exec_module(fps)
    names, _nd, meta = fps.get_delta_players()
    ids_by_name = {}
    for pid, (nm, _p) in who.items():
        ids_by_name.setdefault(nm, []).append(pid)
    agg = pd.DataFrame({"player_name": sorted(ids_by_name)})
    matched = fps.match_names(agg, names, set())
    players = {}
    for dn, nm in matched.items():
        pos = meta.get(dn, (None, None))[1]
        if pos not in ("QB", "RB", "WR", "TE"):
            continue
        cands = [pid for pid in ids_by_name.get(nm, []) if posof.get(pid) == pos]
        if len(cands) != 1:
            continue                     # no id, or two players share the name: leave out, never guess
        pid = cands[0]
        v, n = sofar(pid, pos)
        base = stats_epa.get(dn, {}).get(ekey) if pos in ("QB", "RB") else base_yprr.get(pid)
        gl = sorted(per_game.get(pid, []))
        if v is None and base is None and not gl:
            continue
        players[dn] = {"pos": pos, "sofar": v, "n": n,
                       "base": round(base, 3) if base is not None else None, "games": gl}
    dist = {k: [round(float(np.percentile(np.array(v, dtype=float), q)), 3) for q in range(0, 101, 5)]
            for k, v in dists.items()}
    doc = {"season": season, "built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "tiers": tiers, "tier_min": TIER_MIN, "season_min": SEASON_MIN, "dist": dist, "players": players}
    if len(players) < 150:
        print(f"[DELTA] WARNING: only {len(players)} players matched — efficiency.json NOT written")
        return
    EFF_FILE.write_text(json.dumps(doc, separators=(",", ":")))
    print(f"[DELTA] Wrote {EFF_FILE.name}: {len(players)} players, {EFF_FILE.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
