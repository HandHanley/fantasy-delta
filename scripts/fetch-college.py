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
PORTAL_YEAR = int(os.environ.get("CFBD_PORTAL_YEAR") or YEAR)
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
OUT      = f"data/college-players-{YEAR}.json"
OUT_CURR = "data/college-players.json"   # alias the app loads by default
PREV_FILE = f"data/college-players-{YEAR-1}.json"

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
    # Conference travels with every player: it is both the filter users need and the
    # second-strongest measured signal for reaching the NFL (P4 86% of those who made it
    # vs 46% who did not, 1.9x lift on the 2025 -> 2026 draft-eligible cohort).
    TEAM_CONF = {g(t, "school"): (g(t, "conference") or "") for t in fbs if g(t, "school")}
    P4 = {"SEC", "Big Ten", "Big 12", "ACC"}
    roster = call("GET /roster (fbs)", teams_api.get_roster, year=YEAR, classification="fbs")
    usage  = call("GET /player/usage", players_api.get_player_usage, year=YEAR)
    # Transfer portal. A receiver moving from a G5 offence to an SEC one is a genuine
    # dynasty event: his competition level, his target competition and his old team's
    # vacated share all change at once. One call; emitted as a separate file so the
    # main universe payload stays lean.
    portal = call(f"GET /player/portal {PORTAL_YEAR}", players_api.get_transfer_portal, year=PORTAL_YEAR)

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
            "cls": g(p, "year"), "stars": 0, "rating": 0.0, "rcls": None,
            "conf": TEAM_CONF.get(team, ""), "p4": 1 if TEAM_CONF.get(team, "") in P4 else 0,
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
    by_athlete, by_recid, by_namepos, ambiguous = {}, {}, {}, set()
    for r in recruits:
        st = g(r, "stars") or 0
        payload = (st, float(g(r, "rating") or 0), g(r, "year"))
        aid, rid = g(r, "athlete_id"), g(r, "id")
        if aid is not None: by_athlete[str(aid)] = payload
        if rid is not None: by_recid[str(rid)] = payload
        nk = (norm(g(r, "name")), (g(r, "position") or "").upper())
        if nk in by_namepos and by_namepos[nk] != payload:
            ambiguous.add(nk)          # same name+position in >1 class: unresolvable
        by_namepos[nk] = payload
    npool = len(by_namepos)
    blue = sum(1 for v in by_namepos.values() if v[0] >= 4)

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
                nk = (k[0], rp)
                if nk in ambiguous: tier["ambiguous"] += 1; continue
                m = by_namepos.get(nk)
                if m: hit, why = m, "name+pos"; break
        if hit and hit[2] and v.get("cls"):
            expected = YEAR - int(v["cls"]) + 1
            if not (expected - 2 <= int(hit[2]) <= expected + 1):
                tier["implausible"] += 1
                hit = None            # class year contradicts class standing
        if hit:
            v["stars"], v["rating"], v["rcls"] = hit[0], hit[1], hit[2]
            tier[why] += 1
    total = sum(tier.values())
    print(f"  recruits indexed: {npool:,} (4-5 star: {blue:,})  -> matched: {total:,}"
          f" ({total/max(1,len(ply))*100:.0f}% of skill players)")
    print(f"    by athlete_id {tier['athlete_id']:,} | by recruit_ids {tier['recruit_ids']:,}"
          f" | by name+position {tier['name+pos']:,}")
    print(f"    rejected: {tier['ambiguous']:,} ambiguous name+pos, "
          f"{tier['implausible']:,} class-year implausible  ({len(ambiguous):,} ambiguous keys)")

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

AGG = {"rec": "rec", "rey": "rey", "ret": "ret", "car": "car",
       "ry": "ry", "rt": "rt", "py": "py", "pt": "pt", "pi": "pi"}
for v in ply.values():
    tot = {k: 0.0 for k in AGG}
    for row in v["g"].values():
        for k in AGG: tot[k] += num(row.get(k, 0))
    v["tot"] = tot
    rec_y, rush_y, pass_y = tot["rey"], tot["ry"], tot["py"]
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

# ── door 3: continuity ─────────────────────────────────────────────────────
# Anyone in LAST season's universe stays in, provided he is still on an FBS roster.
# Without this a player who qualified in year N-1 and then slumps simply vanishes in
# year N — and his card would lose the current season at exactly the moment the decline
# became the interesting fact. A fade should be visible, not a disappearance.
prev_names = set()
try:
    with open(PREV_FILE) as f:
        prev_names = {norm(x["n"]) for x in json.load(f).get("players", [])}
    print(f"\n  prior season file: {PREV_FILE} ({len(prev_names):,} players)")
except FileNotFoundError:
    print(f"\n  prior season file: none ({PREV_FILE} absent - first season, fine)")
except Exception as e:
    print(f"\n  prior season file: unreadable ({e}) - continuing without continuity")
for k, v in ply.items():
    if k in picked: continue
    if k[0] in prev_names:
        picked[k] = v; by_door["continuity"] += 1

print(f"\n  door: production {by_door['production']:,} | pedigree {by_door['pedigree']:,}"
      f" | continuity {by_door['continuity']:,} | UNIVERSE {len(picked):,}")

# ---- emit ----
out = {
    "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "season": YEAR,
    "note": ("College TRACKING data. Production facts only — no DELTA Score, no projections. "
             "usg = CFBD share of ALL team offensive plays (NOT target share; ~0.53x it). "
             "rsh = reception share (player receptions / team receptions) - the available proxy. "
             "Season totals use the SAME keys as weekly rows: rey/ret=receiving, ry/rt=rushing, py/pt=passing. "
             "ageEst = ESTIMATE ONLY: 18 + (season - recruiting class). CFBD exposes no birth dates. "
             "Wrong for reclassers/prep-year/JUCO. Display context only - never scored. "
             "Included via production quota or 4-5 star underclassman pedigree."),
    "quota": QUOTA, "min_games": MIN_GAMES,
    "counts": {"universe": len(picked), **dict(by_door)},
    "players": [],
}
for v in sorted(picked.values(), key=lambda x: -x["prod"]):
    out["players"].append({
        "id": v["id"], "n": v["n"], "pos": v["pos"], "tm": v["tm"],
        "conf": v.get("conf") or None, "p4": v.get("p4", 0), "cls": v["cls"],
        "stars": v["stars"] or None, "rating": round(v["rating"], 4) or None,
        "rcls": v.get("rcls"),
        "ageEst": (18 + (YEAR - v["rcls"])) if v.get("rcls") else None,
        "usg": v["usg"], "rsh": v["rshare"],
        "rec": int(v["tot"]["rec"]), "rey": round(v["tot"]["rey"]), "ret": int(v["tot"]["ret"]),
        "car": int(v["tot"]["car"]), "ry": round(v["tot"]["ry"]),  "rt":  int(v["tot"]["rt"]),
        "py": round(v["tot"]["py"]), "pt": int(v["tot"]["pt"]),    "pi":  int(v["tot"]["pi"]),
        "gms": v["games"],
        "g": [v["g"][w] for w in sorted(v["g"])],
    })

os.makedirs("data", exist_ok=True)
with open(OUT, "w") as f:
    json.dump(out, f, separators=(",", ":"))
# The app loads the alias; season files are what the player card reaches back through.
import shutil; shutil.copyfile(OUT, OUT_CURR)
size = os.path.getsize(OUT)
print(f"\n  wrote {OUT}: {size/1e6:.2f} MB  ({len(out['players']):,} players)")
print(f"  wrote {OUT_CURR} (alias for the current season)")

# ── transfer portal ────────────────────────────────────────────────────────
# Filtered to skill positions landing at an FBS school — an FCS-bound transfer is not
# a dynasty event. Origin/destination competition tiers travel with each row so the UI
# can show the level change without a second lookup.
port_rows = []
for r in (portal or []):
    pos = (g(r, "position") or "").upper()
    if pos not in SKILL: continue
    dest = g(r, "destination")
    if not dest or dest not in fbs_names: continue          # must land in FBS
    orig = g(r, "origin") or ""
    nm = f"{g(r,'first_name') or ''} {g(r,'last_name') or ''}".strip()
    if not nm: continue
    dc, oc = TEAM_CONF.get(dest, ""), TEAM_CONF.get(orig, "")
    port_rows.append({
        "n": nm, "pos": pos, "from": orig, "to": dest,
        "fc": oc or None, "tc": dc or None,
        "fp4": 1 if oc in P4 else 0, "tp4": 1 if dc in P4 else 0,
        "fbs_from": 1 if orig in fbs_names else 0,           # 0 => stepping up from FCS
        "stars": (g(r, "stars") or 0) or None,
        "rating": round(float(g(r, "rating") or 0), 4) or None,
        "elig": g(r, "eligibility") or None,
        "date": (str(g(r, "transfer_date"))[:10] if g(r, "transfer_date") else None),
    })
port_rows.sort(key=lambda x: (-(x["stars"] or 0), x["n"]))
pout = {"generated": out["generated"], "season": PORTAL_YEAR,
        "note": ("Skill-position transfers landing at an FBS school. fp4/tp4 mark Power-4 "
                 "origin/destination; fbs_from=0 means he came up from FCS. Facts only \u2014 "
                 "no score, no projection."),
        "count": len(port_rows), "players": port_rows}
with open("data/college-portal.json", "w") as f:
    json.dump(pout, f, separators=(",", ":"))
print(f"  wrote data/college-portal.json: {os.path.getsize('data/college-portal.json')/1e3:.0f} KB "
      f"({len(port_rows):,} transfers)")
up = sum(1 for r in port_rows if r["tp4"] and not r["fp4"])
down = sum(1 for r in port_rows if r["fp4"] and not r["tp4"])
print(f"  level moves: {up:,} up to Power-4 | {down:,} down from Power-4")

print(f"  API calls used: {CALLS}")
n = len(out["players"]) or 1
for fld, label in (("ageEst", "age estimate"), ("stars", "recruit stars"),
                   ("rsh", "reception share"), ("usg", "usage share")):
    have = sum(1 for p in out["players"] if p.get(fld) is not None)
    print(f"  coverage: {label:<16} {have:>4}/{n} ({have/n*100:.0f}%)")
for pos in ("QB", "RB", "WR", "TE"):
    rows = [p for p in out["players"] if p["pos"] == pos]
    rows.sort(key=lambda x: -(x["py"] if pos == "QB" else x["rey"] + x["ry"]))
    print(f"\n  top 6 {pos} (by {'pass yds' if pos=='QB' else 'scrimmage yds'}):")
    for p in rows[:6]:
        print(f"    {p['n']:<24} {p['tm']:<20} rec {p['rey']:>5} rush {p['ry']:>5} "
              f"pass {p['py']:>5}  rsh {p['rsh']}  {p['stars'] or '-'}★ cls{p['cls']}"
              f" rc{p['rcls'] or '----'} age~{p['ageEst'] or '--'}")
