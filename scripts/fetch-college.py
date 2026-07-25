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
            "g": {}, "prod": 0.0, "usg": None,
        }
    print(f"\n  FBS skill players on rosters: {len(ply):,}")
    # Join indexes. Athlete ID is authoritative; (name, team) is the fallback for
    # rows where an ID is missing. A silent join failure here would zero out every
    # production number and quietly hand the whole universe to the pedigree door,
    # so the match rate is reported loudly below — never assumed.
    by_id = {str(v["id"]): v for v in ply.values() if v.get("id") is not None}
    by_nt = ply

    # ---- pedigree join (name-based; report the match rate, never assume it) ----
    rec_by_name = {}
    for r in recruits:
        st = g(r, "stars") or 0
        if st < 4: continue
        rec_by_name.setdefault(norm(g(r, "name")), (st, float(g(r, "rating") or 0)))
    hits = 0
    for k, v in ply.items():
        m = rec_by_name.get(k[0])
        if m: v["stars"], v["rating"] = m[0], m[1]; hits += 1
    print(f"  4-5 star recruits in pool   : {len(rec_by_name):,}"
          f"  -> matched to roster: {hits:,} ({hits/max(1,len(ply))*100:.0f}%)")

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
                    for typ in (g(cat, "types") or []):
                        tkey = (g(typ, "name") or "").upper()
                        STAT_KEYS[f"{cname}.{tkey}"] += 1
                        for ath in (g(typ, "athletes") or []):
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
                            row[f"{cname[:4]}_{tkey}"] = g(ath, "stat")

    tot = sum(MATCH.values()) or 1
    print(f"\n  stat-row join: by id {MATCH['by_id']:,} | by name {MATCH['by_name']:,}"
          f" | UNMATCHED {MATCH['unmatched']:,} ({MATCH['unmatched']/tot*100:.1f}%)")
    if MISS: print("    unmatched samples:", "; ".join(MISS))
    if MATCH['by_id'] + MATCH['by_name'] == 0:
        print("    !! JOIN FAILED COMPLETELY — production door would be empty. Not writing.")
        sys.exit(1)
    print(f"\n  stat keys discovered: {len(STAT_KEYS)}")
    for kk, n in STAT_KEYS.most_common(18):
        print(f"    {kk:<26} {n:>6,}")

# ---- production scoring (yards only; TD/eff live as display columns) ----
def num(v):
    try: return float(str(v).split("/")[0])
    except Exception: return 0.0

for v in ply.values():
    rec_y = rush_y = pass_y = 0.0
    for row in v["g"].values():
        for kk, val in row.items():
            if kk in ("w", "opp"): continue
            if kk.endswith("_YDS"):
                if kk.startswith("rece"): rec_y  += num(val)
                elif kk.startswith("rush"): rush_y += num(val)
                elif kk.startswith("pass"): pass_y += num(val)
    v["ry"], v["uy"], v["py"] = rec_y, rush_y, pass_y
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
             "usg = season share of team offense (context, not a ranking). "
             "Included via production quota or 4-5 star underclassman pedigree."),
    "quota": QUOTA, "min_games": MIN_GAMES,
    "counts": {"universe": len(picked), **dict(by_door)},
    "players": [],
}
for v in sorted(picked.values(), key=lambda x: -x["prod"]):
    out["players"].append({
        "id": v["id"], "n": v["n"], "pos": v["pos"], "tm": v["tm"], "cls": v["cls"],
        "stars": v["stars"] or None, "rating": round(v["rating"], 4) or None,
        "usg": v["usg"], "ry": round(v["ry"]), "uy": round(v["uy"]), "py": round(v["py"]),
        "gms": v["games"],
        "g": [v["g"][w] for w in sorted(v["g"])],
    })

os.makedirs("data", exist_ok=True)
with open(OUT, "w") as f:
    json.dump(out, f, separators=(",", ":"))
size = os.path.getsize(OUT)
print(f"\n  wrote {OUT}: {size/1e6:.2f} MB  ({len(out['players']):,} players)")
print(f"  API calls used: {CALLS}")
print("\n  top 12 by production:")
for p in out["players"][:12]:
    print(f"    {p['n']:<24} {p['pos']:<3} {p['tm']:<18} rec {p['ry']:>5} rush {p['uy']:>5} "
          f"pass {p['py']:>5}  usg {p['usg']}")
