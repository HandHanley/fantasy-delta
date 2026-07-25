#!/usr/bin/env python3
"""
CFBD PHASE 0 SPIKE — read-only. Commits nothing, writes nothing to the repo.

Answers exactly two questions before we design anything:
  (1) How many API calls does a realistic weekly pull consume, against the
      free tier's 1,000/month?
  (2) How big is the filtered JSON the browser would have to download?

Everything else it prints is reconnaissance: real field names and real record
counts, so the pipeline gets built against reality instead of my assumptions.

Run via .github/workflows/cfbd-spike.yml (Actions -> Run workflow).
Needs repo secret CFBD_API_KEY. Get a free key at collegefootballdata.com/key
"""
import os, sys, json

try:
    import cfbd
except ImportError:
    print("ERROR: pip install cfbd"); sys.exit(1)

KEY  = (os.environ.get("CFBD_API_KEY") or "").strip()
YEAR = int(os.environ.get("CFBD_YEAR") or 2025)     # last COMPLETED season by default
WEEK = int(os.environ.get("CFBD_WEEK") or 6)
SKILL = {"QB", "RB", "WR", "TE"}

if not KEY:
    print("ERROR: CFBD_API_KEY is empty. Add it as a repository secret.")
    sys.exit(1)

CALLS = 0
def call(label, fn, **kw):
    """One client method == exactly one HTTP request, so counting here is exact."""
    global CALLS
    CALLS += 1
    try:
        out = fn(**kw)
        n = len(out) if hasattr(out, "__len__") else 1
        print(f"  [call {CALLS:>2}] {label:<34} -> {n:>7,} records")
        return out
    except Exception as e:
        msg = str(e).replace("\n", " ")[:220]
        print(f"  [call {CALLS:>2}] {label:<34} -> FAILED: {msg}")
        return []

def fields(obj):
    if obj is None: return []
    d = getattr(obj, "model_fields", None) or getattr(obj, "__fields__", None)
    if d: return list(d.keys())
    return [a for a in dir(obj) if not a.startswith("_")][:25]

def val(o, *names, default=None):
    for n in names:
        v = getattr(o, n, None)
        if v is not None: return v
    return default

print("=" * 74)
print(f"CFBD PHASE 0 SPIKE — season {YEAR}, sample week {WEEK}")
print("=" * 74)

cfg = cfbd.Configuration(access_token=KEY)
with cfbd.ApiClient(cfg) as api:
    teams_api  = cfbd.TeamsApi(api)
    players_api = cfbd.PlayersApi(api)
    games_api  = cfbd.GamesApi(api)

    # ---------- SEASON SETUP (once per season) ----------
    print("\n-- SEASON SETUP (once per season) " + "-" * 39)
    teams  = call("GET /teams/fbs", teams_api.get_fbs_teams, year=YEAR)
    # The decisive test: does `classification` work WITHOUT a team filter?
    # If yes, every FBS roster is one call instead of ~136.
    roster = call("GET /roster (classification=fbs)", teams_api.get_roster,
                  year=YEAR, classification="fbs")
    portal = call("GET /player/portal", players_api.get_transfer_portal, year=YEAR)
    setup_calls = CALLS

    # ---------- WEEKLY PULL ----------
    print("\n-- WEEKLY PULL (repeats each game week) " + "-" * 33)
    before = CALLS
    wk_stats = call(f"GET /games/players (week={WEEK})", games_api.get_game_player_stats,
                    year=YEAR, week=WEEK, classification="fbs", season_type="regular")
    usage    = call("GET /player/usage (season cumulative)", players_api.get_player_usage, year=YEAR)
    weekly_calls = CALLS - before

    # ---------- SHAPE RECON ----------
    print("\n-- ACTUAL FIELD SHAPES " + "-" * 50)
    for label, data in (("roster", roster), ("usage", usage), ("games/players", wk_stats), ("portal", portal)):
        if data:
            print(f"  {label:<16} {fields(data[0])}")
        else:
            print(f"  {label:<16} (no records returned)")

    # age proxy: does anything resembling a birth date exist on a live record?
    if roster:
        age_like = [f for f in fields(roster[0]) if any(k in f.lower() for k in ("birth", "age", "dob"))]
        print(f"\n  age/birth fields on live roster records: {age_like or 'NONE — confirmed'}")
        rec_ids = sum(1 for p in roster if val(p, "recruit_ids"))
        print(f"  recruit_ids populated (age proxy): {rec_ids:,}/{len(roster):,}"
              f" = {(rec_ids/max(1,len(roster)))*100:.0f}%")

    # ---------- UNIVERSE + PAYLOAD ----------
    print("\n-- UNIVERSE FILTERING " + "-" * 51)
    skill = [p for p in roster if (val(p, "position") or "") in SKILL]
    print(f"  all FBS players                : {len(roster):,}")
    print(f"  skill positions (QB/RB/WR/TE)  : {len(skill):,}")

    # rank by share of offense to find the production floor
    ranked = []
    for u in usage:
        pos = val(u, "position") or ""
        if pos not in SKILL: continue
        uu = val(u, "usage")
        overall = getattr(uu, "overall", None) if uu is not None else None
        if overall is None: continue
        ranked.append((float(overall), val(u, "name"), pos, val(u, "team")))
    ranked.sort(reverse=True)
    print(f"  with usage data                : {len(ranked):,}")
    if ranked:
        print(f"  usage.overall range            : {ranked[-1][0]:.4f} .. {ranked[0][0]:.4f}")
        print(f"  top 5: " + ", ".join(f"{n} ({p},{t})" for _, n, p, t in ranked[:5]))

    # Bytes per stored row. Measured against the row we would ACTUALLY persist —
    # not a stub — so the projection isn't flattered. Mirrors the field density of
    # DELTA's existing game-logs.json rows (~118 bytes each).
    row_template = {"s": YEAR, "w": WEEK, "opp": "OSU", "tgt": 9, "rec": 6,
                    "yds": 88, "td": 1, "car": 0, "ry": 0, "rtd": 0, "usg": 0.284}
    per_row = len(json.dumps(row_template, separators=(",", ":")))
    print(f"\n  bytes/row for the row we'd store  : {per_row}"
          f"   (DELTA's game-logs.json runs ~118)")
    if wk_stats:
        raw = len(json.dumps(wk_stats[0].to_dict(), default=str)) if hasattr(wk_stats[0], "to_dict") else 0
        if raw:
            print(f"  raw API record (one game, nested): {raw:,} bytes"
                  f"  <- we store a flattened subset, not this")

    print("\n-- PAYLOAD PROJECTION (13 game weeks) " + "-" * 35)
    print(f"  {'universe':>10}  {'rows':>9}  {'JSON size':>10}   verdict")
    for n in (250, 400, 600, 1000, len(ranked) or 3000):
        rows = n * 13
        mb = rows * per_row / 1e6
        verdict = "comfortable" if mb < 1.0 else ("workable" if mb < 1.8 else "TOO BIG for a static fetch")
        print(f"  {n:>10,}  {rows:>9,}  {mb:>8.2f} MB   {verdict}")

# ---------- THE TWO NUMBERS ----------
print("\n" + "=" * 74)
print("ANSWERS")
print("=" * 74)
season_weeks = 15
projected = setup_calls + weekly_calls * season_weeks
print(f"  (1) CALL BUDGET")
print(f"      season setup            : {setup_calls} calls (once)")
print(f"      per game week           : {weekly_calls} calls")
print(f"      full {season_weeks}-week season   : {projected} calls")
print(f"      free tier               : 1,000 / month")
print(f"      -> uses {projected/1000*100:.1f}% of ONE month's budget for the whole season")
print(f"\n  (2) PAYLOAD — see table above; target a universe that lands under ~1 MB")
print(f"\n  calls consumed by this spike: {CALLS}")
