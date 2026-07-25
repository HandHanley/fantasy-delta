#!/usr/bin/env python3
"""
DELTA COLLEGE PIPELINE — builds data/college-players.json

Writes a file that NOTHING in the app fetches yet. Zero user-facing risk: it is
inert until the ?college=1 tab ships.

TWO INCLUSION DOORS (both needed — verified against real 2025 data):
  1. PRODUCTION — position quotas by scrimmage production among FBS.
  2. PEDIGREE   — 4-5 star underclassmen regardless of production. Necessary
     because 1,096 FBS pass-catchers played 4+ games in 2025 and still finished
     under the WR/TE production floor; a blue-chip freshman behind two veterans
     is exactly the player you want to meet EARLY, and production-only hides him.

DELIBERATELY NOT DONE HERE:
  - No DELTA Score. College production is not the same quantity as demonstrated
    NFL dynasty value, and a comparable-looking number would imply false parity.
  - No projections. This is a tracker: what happened, not what will happen.

Env: CFBD_API_KEY (required), CFBD_YEAR, CFBD_WEEKS,
     Q_QB / Q_RB / Q_WR / Q_TE (quota overrides), MIN_GAMES
"""
import os, sys, json, unicodedata, datetime, collections

try:
    import cfbd
except ImportError:
    print("ERROR: pip install cfbd"); sys.exit(1)

KEY   = (os.environ.get("CFBD_API_KEY") or "").strip()
YEAR  = int(os.environ.get("CFBD_YEAR")  or 2025)
WEEKS = int(os.environ.get("CFBD_WEEKS") or 16)
QUOTA = {"QB": int(os.environ.get("Q_QB") or 70),
         "RB": int(os.environ.get("Q_RB") or 110),
         "WR": int(os.environ.get("Q_WR") or 160),
         "TE": int(os.environ.get("Q_TE") or 70)}
MIN_GAMES = int(os.environ.get("MIN_GAMES") or 4)
SKILL = set(QUOTA)
OFF_CATS = {"passing", "rushing", "receiving"}
# Canonical compact keys, mirroring data/game-logs.json so the front end reads one dialect.
KEYMAP = {
    ("receiving", "REC"): "rec", ("receiving", "YDS"): "rey", ("receiving", "TD"): "ret",
    ("rushing",   "CAR"): "car", ("rushing",   "YDS"): "ry",  ("rushing",   "TD"): "rt",
    ("passing",   "YDS"): "py",  ("passing",   "TD"): "pt",   ("passing",   "INT"): "pi",
    ("passing", "C/ATT"): "ca",  ("passing",  "COMPLETIONS"): "cmp", ("passing", "ATT"): "pa",
}
OUT = "data/college-players.json"

if not KEY:
    print("ERROR: CFBD_API_KEY not set"); sys.exit(1)

CALLS = 0
def call(label, fn, **kw):
    global CALLS
    CALLS += 1
    try:
        out = fn(**kw)
        print(f"  [{CALLS:>3}] {label:<38} {len(out) if hasattr(out,'__len__') else 1:>7,}")
        return out
    except Exception as e:
        print(f"  [{CALLS:>3}] {label:<38} FAILED: {str(e)[:150]}")
        return []

def norm(s):
    """Name key for joining. Mirrors the NFL pipeline's apostrophe/accent handling —
    the Gainwell/Ja'Marr class of bug lives exactly here."""
    if not s: return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return "".join(c for c in s.lower() if c.isalnum())

def g(o, *names, default=None):
    for n in names:
        v = getattr(o, n, None)
        if v is not None: return v
    return default

print("=" * 72)
print(f"DELTA COLLEGE PIPELINE — season {YEAR}")
print("=" * 72)

cfg = cfbd.Configuration(access_token=KEY)
with cfbd.ApiClient(cfg) as api:
    teams_api, players_api, games_api = cfbd.TeamsApi(api), cfbd.PlayersApi(api), cfbd.GamesApi(api)
    recruit_api = cfbd.RecruitingApi(api)

    print("\n-- roster & context " + "-" * 51)
    fbs    = call("GET /teams/fbs", teams_api.get_fbs_teams, year=YEAR)
    fbs_names = {g(t, "school") for t in fbs if g(t, "school")}
    roster = call("GET /roster (fbs)", teams_api.get_roster, year=YEAR, classification="fbs")
    usage  = call("GET /player/usage", players_api.get_player_usage, year=YEAR)

    # Recruiting classes still on a 2025 roster: a true freshman was a 2025 recruit,
    # a 5th-year was ~2021. Pull the window so the pedigree door has data.
    recruits = []
    for cy in range(YEAR - 4, YEAR + 1):
        recruits += call(f"GET /recruiting/players {cy}", recruit_api.get_recruits, year=cy) or []

    # ---- roster index (position + class are authoritative here, not inferred) ----
    ply = {}
    for p in roster:
        pos = g(p, "position") or ""
        if pos not in SKILL: continue
        nm = f"{g(p,'first_name','firstName','') or ''} {g(p,'last_name','lastName','') or ''}".strip()
        if not nm: continue
        team = g(p, "team")
        if team not in fbs_names: continue
        ply[(norm(nm), team)] = {
            "id": g(p, "id"), "n": nm, "pos": pos, "tm": team,
            "cls": g(p, "year"), "stars": 0, "rating": 0.0,
            "recruit_ids": g(p, "recruit_ids") or [],
            "g": {}, "prod": 0.0, "usg": None,
        }
    print(f"\n  FBS skill players on rosters: {len(ply):,}")
    # Join indexes. Athlete ID is authoritative; (name, team) is the fallback for
    # rows where an ID is missing. A silent join failure here would zero out every
    # production number and quietly hand the whole universe to the pedigree door,
    # so the match rate is reported loudly below — never assumed.
    by_id = {str(v["id"]): v for v in ply.values() if v.get("id") is not None}
    by_nt = ply

    # ---- pedigree join ----------------------------------------------------
    # Three tiers, strongest first. A name-only join is NOT safe here: recruit
    # classes cover every position, so "John Smith" the 4-star linebacker would
    # otherwise hand his pedigree to "John Smith" the wide receiver. Tier 3 is
    # therefore position-gated, and the tier breakdown is printed so a collapse
    # in the exact-match tiers is visible rather than silent.
    RPOS = {"QB": {"QB", "PRO", "DUAL"}, "RB": {"RB", "APB", "ATH"},
            "WR": {"WR", "ATH"},        "TE": {"TE", "ATH"}}
    by_athlete, by_recid, by_namepos = {}, {}, {}
    for r in recruits:
        st = g(r, "stars") or 0
        if st < 4: continue
        payload = (st, float(g(r, "rating") or 0))
        aid, rid = g(r, "athlete_id"), g(r, "id")
        if aid is not None: by_athlete[str(aid)] = payload
        if rid is not None: by_recid[str(rid)] = payload
        by_namepos[(norm(g(r, "name")), (g(r, "position") or "").upper())] = payload
    npool = len(by_namepos)

    tier = collections.Counter()
    for k, v in ply.items():
        hit = None
        if v.get("id") is not None and str(v["id"]) in by_athlete:
            hit, why = by_athlete[str(v["id"])], "athlete_id"
        if hit is None:
            for rid in (v.get("recruit_ids") or []):
                if str(rid) in by_recid:
                    hit, why = by_recid[str(rid)], "recruit_ids"; break
        if hit is None:
            for rp in RPOS.get(v["pos"], set()):
                m = by_namepos.get((k[0], rp))
                if m: hit, why = m, "name+pos"; break
        if hit:
            v["stars"], v["rating"] = hit[0], hit[1]
            tier[why] += 1
    total = sum(tier.values())
    print(f"  4-5 star recruits in pool   : {npool:,}  -> matched: {total:,}"
          f" ({total/max(1,len(ply))*100:.0f}% of skill players)")
    print(f"    by athlete_id {tier['athlete_id']:,} | by recruit_ids {tier['recruit_ids']:,}"
          f" | by name+position {tier['name+pos']:,}")

    # ---- season usage share (context column, never the ranking) ----
    for u in usage:
        k = (norm(g(u, "name")), g(u, "team"))
        if k in ply:
            uu = g(u, "usage")
            ov = getattr(uu, "overall", None) if uu is not None else None
            if ov is not None: ply[k]["usg"] = round(float(ov), 4)

    # ---- weekly game logs ----
    print("\n-- weekly game logs " + "-" * 51)
    STAT_KEYS = collections.Counter()
    MATCH = collections.Counter()
    MISS = []
    TEAM_REC = collections.Counter()   # (team) -> season receptions, all players
    for wk in range(1, WEEKS + 1):
        games = call(f"GET /games/players wk{wk}", games_api.get_game_player_stats,
                     year=YEAR, week=wk, classification="fbs", season_type="regular")
        for gm in games or []:
            for tm in (g(gm, "teams") or []):
                tname = g(tm, "team")
                opp = None
                for other in (g(gm, "teams") or []):
                    if g(other, "team") != tname: opp = g(other, "team")
                for cat in (g(tm, "categories") or []):
                    cname = (g(cat, "name") or "").lower()
                    if cname not in OFF_CATS: continue   # skip defensive/kicking entirely
                    for typ in (g(cat, "types") or []):
                        tkey = (g(typ, "name") or "").upper()
                        ck = KEYMAP.get((cname, tkey))
                        if ck is None: continue          # drops AVG / LONG / unmapped
                        STAT_KEYS[f"{cname}.{tkey}"] += 1
                        for ath in (g(typ, "athletes") or []):
                            # Team reception denominator must include EVERY receiver, not
                            # just our universe, or shares inflate. Accumulated before the
                            # roster-match filter for that reason.
                            if ck == "rec" and tname in fbs_names:
                                try: TEAM_REC[tname] += float(g(ath, "stat") or 0)
                                except (TypeError, ValueError): pass
                            aid = g(ath, "id")
                            v = by_id.get(str(aid)) if aid is not None else None
                            if v is None:
                                v = by_nt.get((norm(g(ath, "name")), tname))
                                MATCH["by_name" if v is not None else "unmatched"] += 1
                                if v is None and len(MISS) < 8:
                                    MISS.append(f"{g(ath,'name')} ({tname})")
                            else:
                                MATCH["by_id"] += 1
                            if v is None: continue
                            row = v["g"].setdefault(wk, {"w": wk, "opp": opp})
                            row[ck] = g(ath, "stat")

    tot = sum(MATCH.values()) or 1
    print(f"\n  offensive stat-row join: by id {MATCH['by_id']:,} | by name {MATCH['by_name']:,}"
          f" | unmatched {MATCH['unmatched']:,} ({MATCH['unmatched']/tot*100:.1f}%)")
    print("    (unmatched here = FBS offensive players outside the QB/RB/WR/TE roster index,"
          " e.g. OL on a trick play. Defensive rows are no longer counted at all.)")
    if MISS: print("    unmatched samples:", "; ".join(MISS))
    if MATCH['by_id'] + MATCH['by_name'] == 0:
        print("    !! JOIN FAILED COMPLETELY — production door would be empty. Not writing.")
        sys.exit(1)
    print(f"\n  stat keys discovered: {len(STAT_KEYS)}")
    for kk, n in STAT_KEYS.most_common(18):
        print(f"    {kk:<26} {n:>6,}")

TEAM_REC_TOTAL = dict(TEAM_REC)

# ---- production scoring (yards only; TD/eff live as display columns) ----
def num(v):
    try: return float(str(v).split("/")[0])
    except Exception: return 0.0

for v in ply.values():
    rec_y = rush_y = pass_y = 0.0
    for row in v["g"].values():
        rec_y  += num(row.get("rey", 0))
        rush_y += num(row.get("ry", 0))
        pass_y += num(row.get("py", 0))
    v["ry"], v["uy"], v["py"] = rec_y, rush_y, pass_y
    # RECEPTION share — the honest, free stand-in for target share. CFBD's usage.overall
    # is share of ALL offensive plays (measured ~0.53x true target share), so it must not
    # be labelled as targets. Box scores carry no target counts at all, so receptions over
    # team receptions is the closest thing available without pulling play-by-play.
    pr = sum(num(r.get("rec", 0)) for r in v["g"].values())
    tr = TEAM_REC_TOTAL.get(v["tm"], 0)
    v["rshare"] = round(pr / tr, 4) if tr > 0 else None
    v["recs"] = int(pr)
    v["prod"] = rec_y + rush_y + pass_y * 0.4     # pass yards discounted to compare positions
    v["games"] = len(v["g"])

# ---- the two doors ----
elig = [v for v in ply.values() if v["games"] >= MIN_GAMES]
picked, by_door = {}, collections.Counter()
for pos, n in QUOTA.items():
    pool = sorted([v for v in elig if v["pos"] == pos], key=lambda x: -x["prod"])[:n]
    for v in pool: picked[(norm(v["n"]), v["tm"])] = v; by_door["production"] += 1
    if pool: print(f"\n  {pos}: took {len(pool):>3}  production floor {pool[-1]['prod']:.0f} yds")

for k, v in ply.items():
    if k in picked: continue
    if v["stars"] >= 4 and (v["cls"] or 9) <= 2:      # blue-chip underclassmen only
        picked[k] = v; by_door["pedigree"] += 1

print(f"\n  door: production {by_door['production']:,} | pedigree {by_door['pedigree']:,}"
      f" | UNIVERSE {len(picked):,}")

# ---- emit ----
out = {
    "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "season": YEAR,
    "note": ("College TRACKING data. Production facts only — no DELTA Score, no projections. "
             "usg = CFBD share of ALL team offensive plays (NOT target share; ~0.53x it). "
             "rsh = reception share (player receptions / team receptions) - the available proxy. "
             "Included via production quota or 4-5 star underclassman pedigree."),
    "quota": QUOTA, "min_games": MIN_GAMES,
    "counts": {"universe": len(picked), **dict(by_door)},
    "players": [],
}
for v in sorted(picked.values(), key=lambda x: -x["prod"]):
    out["players"].append({
        "id": v["id"], "n": v["n"], "pos": v["pos"], "tm": v["tm"], "cls": v["cls"],
        "stars": v["stars"] or None, "rating": round(v["rating"], 4) or None,
        "usg": v["usg"], "rsh": v["rshare"], "recs": v["recs"], "ry": round(v["ry"]), "uy": round(v["uy"]), "py": round(v["py"]),
        "gms": v["games"],
        "g": [v["g"][w] for w in sorted(v["g"])],
    })

os.makedirs("data", exist_ok=True)
with open(OUT, "w") as f:
    json.dump(out, f, separators=(",", ":"))
size = os.path.getsize(OUT)
print(f"\n  wrote {OUT}: {size/1e6:.2f} MB  ({len(out['players']):,} players)")
print(f"  API calls used: {CALLS}")
for pos in ("QB", "RB", "WR", "TE"):
    rows = [p for p in out["players"] if p["pos"] == pos]
    rows.sort(key=lambda x: -(x["py"] if pos == "QB" else x["ry"] + x["uy"]))
    print(f"\n  top 6 {pos} (by {'pass yds' if pos=='QB' else 'scrimmage yds'}):")
    for p in rows[:6]:
        print(f"    {p['n']:<24} {p['tm']:<20} rec {p['ry']:>5} rush {p['uy']:>5} "
              f"pass {p['py']:>5}  recsh {p['rsh']}  usg {p['usg']}  {p['stars'] or '-'}star cls{p['cls']}")
