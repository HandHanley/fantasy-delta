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

Env: CFBD_API_KEY (required), CFBD_YEAR, CFBD_WEEKS, CFBD_CURRENT_SEASON,
     Q_QB / Q_RB / Q_WR / Q_TE (quota overrides), MIN_GAMES
"""
import os, sys, json, unicodedata, datetime, collections

try:
    import cfbd
except ImportError:
    print("ERROR: pip install cfbd"); sys.exit(1)

def default_season(today=None):
    """The season currently in progress.

    A college season starts in August and finishes in January, so the calendar
    year alone is wrong for half of it: in January 2027 the live season is still
    2026. August is the cutover.

    Derived rather than hard-coded because the hard-coded 2025 that used to sit
    here went stale the moment the 2026 season kicked off, and it went stale
    SILENTLY. It feeds the alias guard below (YEAR >= CURRENT_SEASON), so once
    it lagged a year, a routine 2025 backfill was free to overwrite the live
    season file the whole platform loads by default. A guard that needs an
    annual hand-edit to keep working is a guard that will eventually be wrong.
    """
    d = today or datetime.date.today()
    return d.year if d.month >= 8 else d.year - 1

KEY   = (os.environ.get("CFBD_API_KEY") or "").strip()
YEAR  = int(os.environ.get("CFBD_YEAR")  or default_season())
WEEKS = int(os.environ.get("CFBD_WEEKS") or 16)   # highest week fetched; the loop runs 0..WEEKS
PORTAL_YEAR = int(os.environ.get("CFBD_PORTAL_YEAR") or YEAR)
QUOTA = {"QB": int(os.environ.get("Q_QB") or 70),
         "RB": int(os.environ.get("Q_RB") or 110),
         "WR": int(os.environ.get("Q_WR") or 160),
         "TE": int(os.environ.get("Q_TE") or 70)}
MIN_GAMES = int(os.environ.get("MIN_GAMES") or 4)
# dDOM competition-weighting swing. Median-talent team => x1.0; top/bottom => x(1 +/- SWING).
# PROVISIONAL — calibrate against /draft/picks (does dDOM beat raw dom at predicting draft
# capital?) before treating the magnitude as final. Tunable via env for the calibration loop.
DDOM_SWING = float(os.environ.get("DDOM_SWING") or 0.50)
# Platform season-picker floor. Older seasons may be backfilled for calibration but must
# not appear on the live platform; only seasons >= this show in the picker.
VISIBLE_FROM = int(os.environ.get("CFBD_VISIBLE_FROM") or 2024)
# Hand-maintained consensus draft board. Read-only here — this script never writes it.
BOARD_FILE = os.environ.get("DELTA_BOARD_FILE") or "data/devy-board.json"
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
    metrics_api = cfbd.MetricsApi(api)

    print("\n-- roster & context " + "-" * 51)
    fbs    = call("GET /teams/fbs", teams_api.get_fbs_teams, year=YEAR)
    fbs_names = {g(t, "school") for t in fbs if g(t, "school")}
    # Conference travels with every player: it is both the filter users need and the
    # second-strongest measured signal for reaching the NFL (P4 86% of those who made it
    # vs 46% who did not, 1.9x lift on the 2025 -> 2026 draft-eligible cohort).
    TEAM_CONF = {g(t, "school"): (g(t, "conference") or "") for t in fbs if g(t, "school")}
    P4 = {"SEC", "Big Ten", "Big 12", "ACC"}
    roster = call("GET /roster (fbs)", teams_api.get_roster, year=YEAR, classification="fbs")
    # PRE-SEASON / NO-DATA GUARD. An empty roster means season YEAR isn't underway yet
    # (rosters populate in late summer) — or a transient API hiccup. Either way there is
    # nothing to build, so skip NOW, before spending ~27 more calls on usage/talent/portal/
    # recruiting/16 weeks of games that would all come back empty. Exit 0 (clean no-op) so
    # the nightly job doesn't flag red every night in the off-season, and the existing
    # current-season file is left untouched. A genuine mid-season join failure (roster
    # present but nothing joins) still errors loudly further down.
    if not roster:
        print(f"\n  Season {YEAR} has no FBS roster yet — not underway (or API returned nothing).")
        print(f"  Nothing to build. Leaving the existing current-season file untouched; exiting cleanly.")
        sys.exit(0)
    usage  = call("GET /player/usage", players_api.get_player_usage, year=YEAR)
    # Team talent composite (247 roster-talent sum). The competition-strength signal for
    # dDOM: a target-share earned amid NFL-caliber teammates and schedule is worth more
    # than the same share against weak competition. Keyed by team.
    talent = call("GET /talent", teams_api.get_talent, year=YEAR)
    TEAM_TALENT = {}
    for t in (talent or []):
        nm = g(t, "team", "school")
        tv = g(t, "talent")
        if nm and tv is not None:
            try: TEAM_TALENT[nm] = float(tv)
            except (TypeError, ValueError): pass
    # CARRY-FORWARD: some teams (notably service academies) are missing from a given
    # season's 247 talent feed. Without this, their competition penalty silently vanishes
    # and weak-competition players' dDOM inflates (e.g. a Navy WR jumping to the 100th
    # percentile). Team talent barely moves year to year, so fall back to the most recent
    # prior season we can find. Only fills teams that ACTUALLY have players this season.
    have_teams = {t for t in TEAM_CONF}
    missing = [t for t in have_teams if t not in TEAM_TALENT]
    for back in (1, 2, 3):
        if not missing:
            break
        prev = call(f"GET /talent (carry-forward {YEAR-back})", teams_api.get_talent, year=YEAR - back)
        pmap = {}
        for t in (prev or []):
            nm = g(t, "team", "school"); tv = g(t, "talent")
            if nm and tv is not None:
                try: pmap[nm] = float(tv)
                except (TypeError, ValueError): pass
        filled = [t for t in missing if t in pmap]
        for t in filled:
            TEAM_TALENT[t] = pmap[t]
        if filled:
            print(f"  [talent] carried forward {len(filled)} team(s) from {YEAR-back}: {', '.join(sorted(filled)[:8])}{'...' if len(filled)>8 else ''}")
        missing = [t for t in missing if t not in TEAM_TALENT]

    # Player PPA/EPA — the college equivalent of EPA: per-play predicted points added, a real
    # efficiency signal beyond box-score volume. One call; garbage time excluded for signal.
    # Keyed by athlete id (fallback name+position). Feeds the standalone player page's depth.
    ppa_rows = call("GET /ppa/players/season",
                    metrics_api.get_predicted_points_added_by_player_season,
                    year=YEAR, exclude_garbage_time=True)
    PPA = {}
    for r in (ppa_rows or []):
        avg = g(r, "average_ppa"); tot = g(r, "total_ppa")
        def _f(o, *names):
            v = g(o, *names) if o is not None else None
            try: return round(float(v), 3) if v is not None else None
            except (TypeError, ValueError): return None
        rec = {"ppa": _f(avg, "all"), "ppaPass": _f(avg, "var_pass", "pass"),
               "ppaRush": _f(avg, "rush"), "ppaTot": _f(tot, "all")}
        pid = g(r, "id"); nm = g(r, "name"); pos = g(r, "position")
        if pid is not None: PPA[str(pid)] = rec
        if nm: PPA[("nm", norm(nm), pos)] = rec
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
    TEAM_REY = collections.Counter()   # (team) -> season receiving YARDS, all players (Dominator denom)
    TEAM_RET = collections.Counter()   # (team) -> season receiving TDs, all players (Dominator denom)
    TEAM_RY  = collections.Counter()   # (team) -> season rushing YARDS, all players (rush-Dominator denom)
    TEAM_RT  = collections.Counter()   # (team) -> season rushing TDs, all players (rush-Dominator denom)
    # Range starts at ZERO. Week 0 is a real CFBD designation, not a media label:
    # the season-opening slate (the Dublin game, the other late-August openers) is
    # filed under week 0, a week before "week 1". Looping from 1 dropped those games
    # entirely — invisible in a backfill, where they are a handful of rows among
    # thousands, and total in late August, when they are the ONLY rows that exist.
    # Costs one extra call per run; call() swallows a rejected week as an empty list.
    for wk in range(0, WEEKS + 1):
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
                            # Team receiving denominators must include EVERY receiver, not
                            # just our universe, or shares inflate. Accumulated before the
                            # roster-match filter for that reason.
                            if tname in fbs_names:
                                try:
                                    s = float(g(ath, "stat") or 0)
                                    if   ck == "rec": TEAM_REC[tname] += s
                                    elif ck == "rey": TEAM_REY[tname] += s
                                    elif ck == "ret": TEAM_RET[tname] += s
                                    elif ck == "ry":  TEAM_RY[tname]  += s
                                    elif ck == "rt":  TEAM_RT[tname]  += s
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
        if sum(MATCH.values()) == 0:
            # Rosters exist but no game stat rows yet — season is between roster release and
            # week 1. Nothing to build; skip cleanly rather than fail or overwrite good data.
            print(f"    Season {YEAR} has rosters but no games played yet — nothing to build. Exiting cleanly.")
            sys.exit(0)
        # Game rows exist but none joined to the roster index -> a genuine join bug. Alert.
        print("    !! JOIN FAILED COMPLETELY — production door would be empty. Not writing.")
        sys.exit(1)
    print(f"\n  stat keys discovered: {len(STAT_KEYS)}")
    for kk, n in STAT_KEYS.most_common(18):
        print(f"    {kk:<26} {n:>6,}")

TEAM_REC_TOTAL = dict(TEAM_REC)
TEAM_REY_TOTAL = dict(TEAM_REY)   # Dominator denominator: team season receiving yards
TEAM_RET_TOTAL = dict(TEAM_RET)   # Dominator denominator: team season receiving TDs
TEAM_RY_TOTAL  = dict(TEAM_RY)    # rush-Dominator denominator: team season rushing yards
TEAM_RT_TOTAL  = dict(TEAM_RT)    # rush-Dominator denominator: team season rushing TDs

# Team talent percentile (0-1) across all FBS teams with 247 talent data — the dDOM
# competition-strength axis. Median team lands at ~0.5 (=> no dDOM adjustment).
TALENT_PCT = {}
if TEAM_TALENT:
    ranked = sorted(TEAM_TALENT.items(), key=lambda kv: kv[1])
    n = len(ranked)
    for i, (tm, _) in enumerate(ranked):
        TALENT_PCT[tm] = i / (n - 1) if n > 1 else 0.5

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
    # Dominator Rating — the classic college WR/TE dynasty signal: the average of the
    # player's share of team receiving YARDS and team receiving TDs. Denominators are
    # every receiver on the team (same population as reception share). If a team scored
    # zero receiving TDs, fall back to the yard share alone rather than halving toward 0.
    # Display/context only — NOT a ranking input until validated against draft outcomes.
    ty  = TEAM_REY_TOTAL.get(v["tm"], 0)
    tdd = TEAM_RET_TOTAL.get(v["tm"], 0)
    y_share = (v["tot"]["rey"] / ty)  if ty  > 0 else 0.0
    t_share = (v["tot"]["ret"] / tdd) if tdd > 0 else 0.0
    v["dom"] = round((y_share + t_share) / 2 if tdd > 0 else y_share, 4)
    # Rushing Dominator (RB signal): share of team rushing yards + TDs, same all-player
    # denominators. Context only — pairs with receiving dom for dual-threat backs.
    t_ry = TEAM_RY_TOTAL.get(v["tm"], 0)
    t_rt = TEAM_RT_TOTAL.get(v["tm"], 0)
    ry_share = (v["tot"]["ry"] / t_ry) if t_ry > 0 else 0.0
    rt_share = (v["tot"]["rt"] / t_rt) if t_rt > 0 else 0.0
    v["rdom"] = round((ry_share + rt_share) / 2 if t_rt > 0 else ry_share, 4)
    # dDOM — DELTA Dominator: raw dominator scaled by team competition strength (247 talent
    # percentile). Median-talent team = x1.0; the swing rewards dominance amid strong
    # competition and discounts small-school target-hogging. This is an ANALYTICAL DELTA
    # metric, not a raw fact like dom — shown alongside dom, never replacing it. Magnitude
    # is PROVISIONAL until DDOM_SWING is calibrated against draft outcomes.
    tp = TALENT_PCT.get(v["tm"])
    if tp is None:
        v["ddom"], v["tpct"] = v["dom"], None
    else:
        mult = 1.0 + DDOM_SWING * (tp - 0.5) * 2.0
        mult = max(1.0 - DDOM_SWING, min(1.0 + DDOM_SWING, mult))
        v["ddom"], v["tpct"] = round(v["dom"] * mult, 4), round(tp, 3)
    # QB efficiency — season totals omit completions/attempts, but the game-log rows carry
    # a 'ca' field ("16/24"). Aggregate it to expose completion% and yards/attempt.
    comp = att = 0
    for row in v["g"].values():
        ca = row.get("ca")
        if ca and "/" in str(ca):
            try:
                c_, a_ = str(ca).split("/")[:2]
                comp += int(float(c_)); att += int(float(a_))
            except (ValueError, TypeError):
                pass
    v["cmp"], v["att"] = comp, att
    v["cmppct"] = round(comp / att, 4) if att else None
    v["ypa"]    = round(v["tot"]["py"] / att, 2) if att else None
    v["tdpct"]  = round(v["tot"]["pt"] / att, 4) if att else None
    v["intpct"] = round(v["tot"]["pi"] / att, 4) if att else None
    # ANY/A — adjusted net yards per attempt: (yds + 20*TD - 45*INT) / att. The single
    # best one-number QB-efficiency measure; rewards TDs, punishes INTs, so a
    # completion-inflated dink-and-dunk QB does NOT grade out elite. (Box scores carry no
    # sack data, so this is the passing-only variant of ANY/A.)
    v["anya"] = round((v["tot"]["py"] + 20*v["tot"]["pt"] - 45*v["tot"]["pi"]) / att, 2) if att else None
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

# ── door 4: draft board ────────────────────────────────────────────────────
# Anyone on DELTA's hand-maintained consensus draft board is tracked, whatever his
# production. The other three doors ask "did he produce, was he a blue-chip, was he here
# last year" — all backward-looking. This one asks "does the draft community think he
# matters", which is the question the other three cannot answer.
#
# It exists because the board found real holes: Charlie Becker went 34/679/4 for Indiana
# in 2025 and was absent, while 304 receivers with LESS production were in, including a
# team-mate with three catches. Being on a top-100 board is sufficient reason to track a
# player, and it costs a handful of rows.
board_names = set()
try:
    with open(BOARD_FILE) as f:
        board_names = {norm(n) for n in (json.load(f).get("players") or {})}
    print(f"\n  draft board: {BOARD_FILE} ({len(board_names)} players)")
except FileNotFoundError:
    print(f"\n  draft board: none ({BOARD_FILE} absent - fine, door skipped)")
except Exception as e:
    print(f"\n  draft board: unreadable ({e}) - continuing without it")
board_missing = set(board_names)
for k, v in ply.items():
    board_missing.discard(k[0])
    if k in picked: continue
    if k[0] in board_names:
        picked[k] = v; by_door["board"] += 1
# A board name CFBD has no record of at all is worth saying out loud — it is the only
# way to tell "we chose not to track him" from "the upstream data does not have him".
if board_missing:
    print(f"  board players absent from CFBD entirely: {len(board_missing)}")
    for n in sorted(board_missing)[:10]: print(f"     {n}")

print(f"\n  door: production {by_door['production']:,} | pedigree {by_door['pedigree']:,}"
      f" | continuity {by_door['continuity']:,} | board {by_door['board']:,}"
      f" | UNIVERSE {len(picked):,}")

# Game-log rows dominate the payload (~56% of the college file), and CFBD returns every
# stat as a STRING with zero-value keys present. Storing numbers instead of strings and
# dropping zeros cuts the file substantially with no loss of information — the UI already
# renders a missing key and a 0 identically (as "-").
def compact_row(row):
    out = {}
    for k, val in row.items():
        if k in ("w", "opp"):
            out[k] = val
            continue
        if val is None or val == "":
            continue
        if k == "ca":                      # "16/24" — keep as-is, it isn't numeric
            if val and val != "0/0":
                out[k] = val
            continue
        try:
            f = float(val)
        except (TypeError, ValueError):
            out[k] = val
            continue
        if f == 0:                         # zero == absent for display purposes
            continue
        out[k] = int(f) if f == int(f) else round(f, 2)
    return out



# ---- emit ----
out = {
    "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "season": YEAR,
    "note": ("College TRACKING data. Production facts only — no DELTA Score, no projections. "
             "usg = CFBD share of ALL team offensive plays (NOT target share; ~0.53x it). "
             "ppa = avg predicted points added per play (college EPA); ppaPass/ppaRush split; ppaTot = cumulative. "
             "rsh = reception share (player receptions / team receptions) - the available proxy. "
             "dom = Dominator Rating: avg of receiving-yard share and receiving-TD share (all team "
             "receivers as denominator); the classic WR/TE college dynasty signal. Context only - never scored. "
             "rdom = rushing Dominator (share of team rushing yards+TDs) for RB dual-threat context. "
             "ddom = dDOM (DELTA Dominator): raw dom scaled by team 247-talent percentile (tpct) - an "
             "ANALYTICAL metric adjusting for competition, shown beside raw dom; swing is provisional "
             "pre-calibration. cmp/att/cmppct/ypa/tdpct/intpct/anya = QB efficiency (anya = adj net yds/att). "
             "Season totals use the SAME keys as weekly rows: rey/ret=receiving, ry/rt=rushing, py/pt=passing. "
             "ageEst = ESTIMATE ONLY: 18 + (season - recruiting class). CFBD exposes no birth dates. "
             "Wrong for reclassers/prep-year/JUCO. Display context only - never scored. "
             "Included via production quota or 4-5 star underclassman pedigree."),
    "quota": QUOTA, "min_games": MIN_GAMES,
    # Every season file present after this run, so the UI can offer a season picker
    # without a second request or a hard-coded list.
    # Season picker floor: backtest seasons can be backfilled into data/ for calibration
    # WITHOUT surfacing on the platform. Only seasons >= VISIBLE_FROM appear in the picker.
    "seasons": sorted(s for s in ({int(f.split("-")[-1].split(".")[0])
                       for f in __import__("glob").glob("data/college-players-2*.json")} | {YEAR})
                      if s >= VISIBLE_FROM),
    "counts": {"universe": len(picked), **dict(by_door)},
    "players": [],
}
for v in sorted(picked.values(), key=lambda x: -x["prod"]):
    _ppa = PPA.get(str(v["id"])) or PPA.get(("nm", norm(v["n"]), v["pos"])) or {}
    out["players"].append({
        "id": v["id"], "n": v["n"], "pos": v["pos"], "tm": v["tm"],
        "conf": v.get("conf") or None, "p4": v.get("p4", 0), "cls": v["cls"],
        "stars": v["stars"] or None, "rating": round(v["rating"], 4) or None,
        "rcls": v.get("rcls"),
        "ageEst": (18 + (YEAR - v["rcls"])) if v.get("rcls") else None,
        "usg": v["usg"], "rsh": v["rshare"], "dom": v["dom"], "rdom": v["rdom"],
        "ddom": v["ddom"], "tpct": v["tpct"],
        "cmp": v["cmp"], "att": v["att"], "cmppct": v["cmppct"], "ypa": v["ypa"],
        "tdpct": v["tdpct"], "intpct": v["intpct"], "anya": v["anya"],
        "ppa": _ppa.get("ppa"), "ppaPass": _ppa.get("ppaPass"),
        "ppaRush": _ppa.get("ppaRush"), "ppaTot": _ppa.get("ppaTot"),
        "rec": int(v["tot"]["rec"]), "rey": round(v["tot"]["rey"]), "ret": int(v["tot"]["ret"]),
        "car": int(v["tot"]["car"]), "ry": round(v["tot"]["ry"]),  "rt":  int(v["tot"]["rt"]),
        "py": round(v["tot"]["py"]), "pt": int(v["tot"]["pt"]),    "pi":  int(v["tot"]["pi"]),
        "gms": v["games"],
        "g": [compact_row(v["g"][w]) for w in sorted(v["g"])],
    })

os.makedirs("data", exist_ok=True)
with open(OUT, "w") as f:
    json.dump(out, f, separators=(",", ":"))
size = os.path.getsize(OUT)
print(f"\n  wrote {OUT}: {size/1e6:.2f} MB  ({len(out['players']):,} players)")
# The app loads OUT_CURR (the default alias) as the newest season. ONLY the current
# season may overwrite it — otherwise a backfill run (e.g. 2023) clobbers the default and
# the platform opens to an old season. Backfills write their year-file only.
CURRENT_SEASON = int(os.environ.get("CFBD_CURRENT_SEASON") or default_season())
if YEAR >= CURRENT_SEASON:
    import shutil; shutil.copyfile(OUT, OUT_CURR)
    print(f"  wrote {OUT_CURR} (alias for the current season)")
else:
    print(f"  skipped {OUT_CURR} alias (backfill season {YEAR} < current {CURRENT_SEASON})")

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
