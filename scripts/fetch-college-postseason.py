#!/usr/bin/env python3
"""
DELTA — FETCH COLLEGE POSTSEASON

Pulls bowl and College Football Playoff game lines and writes data/college-postseason.json.

DELIBERATELY SEPARATE FROM THE MAIN COLLEGE DATASET.

  Everything in data/college-players-YYYY.json is regular season only, because
  fetch-college.py requests season_type="regular". That is the right basis for the
  metrics: dDOM is a SHARE of team production and PPA is PER PLAY, so both are
  computed against a uniform slate every player actually played.

  Postseason is not uniform. Some players sit bowls out, most teams play one extra
  game, and a playoff team can play four. Folding those into the pool would mean
  ranking players against each other on different amounts of football — a title
  run counted as if it were a regular Saturday.

  So this data NEVER enters dDOM, PPA, any percentile, any peer pool, or the Scout
  ordering. It is displayed as its own section, clearly labelled, and that is all.
  Nothing here touches the NFL side of DELTA in any way.

Matching: athlete id first, then normalised name + team, against the players already
in that season's college file. Players outside the tracked universe are skipped —
this is context for players we already show, not a second universe.

Env:  CFBD_API_KEY (required)
Usage:
  python3 scripts/fetch-college-postseason.py --dry-run
  python3 scripts/fetch-college-postseason.py --confirm
  python3 scripts/fetch-college-postseason.py --confirm --years 2024-2025
"""
import os, sys, json, glob, unicodedata, datetime, collections

OUT = 'data/college-postseason.json'
POST_WEEKS = 6          # bowls land in wk 1; the 12-team playoff runs several more
OFF_CATS = {"passing", "rushing", "receiving"}
KEYMAP = {
    ("receiving", "REC"): "rec", ("receiving", "YDS"): "rey", ("receiving", "TD"): "ret",
    ("rushing",   "CAR"): "car", ("rushing",   "YDS"): "ry",  ("rushing",   "TD"): "rt",
    ("passing",   "YDS"): "py",  ("passing",   "TD"): "pt",   ("passing",   "INT"): "pi",
    ("passing", "C/ATT"): "ca",  ("passing", "COMPLETIONS"): "cmp", ("passing", "ATT"): "pa",
}


def norm(s):
    if not s: return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return "".join(c for c in s.lower() if c.isalnum())


def g(o, *names, default=None):
    for n in names:
        v = getattr(o, n, None)
        if v is not None: return v
    return default


def season_years():
    out = []
    for f in glob.glob('data/college-players-*.json'):
        base = os.path.basename(f)
        y = base.replace('college-players-', '').replace('.json', '')
        if y.isdigit(): out.append(int(y))
    return sorted(out)


def load_universe(year):
    """id -> name and (normname, team) -> name, for the players we already track."""
    path = f'data/college-players-{year}.json'
    if not os.path.exists(path): return None, None
    players = json.load(open(path)).get('players') or []
    by_id, by_nt = {}, {}
    for p in players:
        if p.get('id') is not None: by_id[str(p['id'])] = p['n']
        by_nt[(norm(p['n']), norm(p.get('tm')))] = p['n']
    return by_id, by_nt


def main():
    args = sys.argv[1:]
    dry, confirm = '--dry-run' in args, '--confirm' in args
    years = season_years()
    if '--years' in args:
        spec = args[args.index('--years') + 1]
        if '-' in spec:
            a, b = spec.split('-'); years = list(range(int(a), int(b) + 1))
        else:
            years = [int(spec)]

    if not dry and not confirm:
        print("REFUSED — this run would write data/college-postseason.json.")
        print("Add --confirm to write it, or --dry-run to rehearse.\n")
        print("Usage: python3 scripts/fetch-college-postseason.py --confirm [--years 2024-2025]")
        sys.exit(2)
    if dry and confirm:
        print("Pass either --dry-run or --confirm, not both."); sys.exit(2)

    key = (os.environ.get("CFBD_API_KEY") or "").strip()
    if not key:
        print("ERROR: CFBD_API_KEY not set"); sys.exit(1)
    try:
        import cfbd
    except ImportError:
        print("ERROR: pip install cfbd"); sys.exit(1)

    print("=" * 74)
    print(f"DELTA — FETCH COLLEGE POSTSEASON   seasons: {', '.join(map(str, years))}")
    print("mode: " + ("DRY RUN — nothing will be written" if dry else "WRITE"))
    print("Separate dataset. Never enters dDOM, PPA, percentiles or Scout ordering.")
    print("=" * 74)

    cfg = cfbd.Configuration(access_token=key)
    out, calls, totals = {}, 0, collections.Counter()
    with cfbd.ApiClient(cfg) as api:
        games_api = cfbd.GamesApi(api)
        for year in years:
            by_id, by_nt = load_universe(year)
            if by_id is None:
                print(f"\n{year}: SKIP — no data/college-players-{year}.json"); continue
            print(f"\n{year}  (universe {len(by_nt)} players)")
            matched = collections.defaultdict(dict)
            seen_games = 0
            for wk in range(1, POST_WEEKS + 1):
                calls += 1
                try:
                    games = games_api.get_game_player_stats(
                        year=year, week=wk, classification="fbs", season_type="postseason")
                except Exception as e:
                    print(f"  [{calls:>3}] wk{wk} FAILED: {str(e)[:120]}")
                    continue
                games = games or []
                if not games:
                    print(f"  [{calls:>3}] wk{wk}: no games")
                    continue
                seen_games += len(games)
                print(f"  [{calls:>3}] wk{wk}: {len(games)} game(s)")
                for gm in games:
                    # Key on the GAME id, never on (week, team). CFBD files the entire
                    # postseason under week 1 — December bowls and the January title game
                    # alike — so a playoff team appears several times in the same week.
                    # Keying by week+team silently SUMS those games into one line: Will
                    # Howard's 2024 run came out as a single 1,150-yard "game".
                    gid = g(gm, "id", "game_id")
                    teams = g(gm, "teams") or []
                    for tm in teams:
                        tname = g(tm, "team")
                        opp = next((g(o, "team") for o in teams if g(o, "team") != tname), None)
                        for cat in (g(tm, "categories") or []):
                            cname = (g(cat, "name") or "").lower()
                            if cname not in OFF_CATS: continue
                            for typ in (g(cat, "types") or []):
                                ck = KEYMAP.get((cname, (g(typ, "name") or "").upper()))
                                if ck is None: continue
                                for ath in (g(typ, "athletes") or []):
                                    aid = g(ath, "id")
                                    nm = by_id.get(str(aid)) if aid is not None else None
                                    if nm is None:
                                        nm = by_nt.get((norm(g(ath, "name")), norm(tname)))
                                    if nm is None: continue      # outside the universe
                                    gkey = (gid if gid is not None else (wk, tname, opp))
                                    rec = matched[nm].setdefault(
                                        gkey, {"w": wk, "opp": opp, "tm": tname,
                                               "gid": gid})
                                    val = g(ath, "stat")
                                    if ck == "ca":
                                        rec["ca"] = str(val)
                                    else:
                                        try: rec[ck] = rec.get(ck, 0) + float(val or 0)
                                        except (TypeError, ValueError): pass
            n_players = 0
            for nm, games_by_key in matched.items():
                rows = []
                for _, r in sorted(games_by_key.items(), key=lambda kv: str(kv[0])):
                    r.pop('gid', None)
                    for k, v in list(r.items()):
                        if isinstance(v, float) and v.is_integer(): r[k] = int(v)
                    rows.append(r)
                if rows:
                    out.setdefault(nm, {})[str(year)] = rows
                    n_players += 1
            totals[year] = n_players
            dist = collections.Counter(len(v[str(year)]) for v in out.values() if str(year) in v)
            print(f"  -> {seen_games} postseason games · {n_players} tracked players with a line")
            print(f"     games per player: " + ", ".join(f"{k}:{v}" for k, v in sorted(dist.items())))
            # Physically impossible single-game lines are the signature of games being
            # merged. Loud, because the numbers stay plausible-looking at a glance.
            bad = []
            for nm, v in out.items():
                for r in v.get(str(year), []):
                    if (r.get('py') or 0) > 650 or (r.get('car') or 0) > 45 or (r.get('rec') or 0) > 20:
                        bad.append(f"{nm} ({r.get('py',0)} py, {r.get('car',0)} car, {r.get('rec',0)} rec)")
            if bad:
                print(f"     WARNING: {len(bad)} implausible single-game line(s) — games may be merging:")
                for b in bad[:5]: print(f"       {b}")

    print()
    tot_players = len(out)
    tot_lines = sum(len(v) for pl in out.values() for v in [pl])
    print(f"players with postseason data: {tot_players} · API calls: {calls}")
    for y in sorted(totals): print(f"   {y}: {totals[y]}")

    payload = {
        'generated': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'years': years,
        'note': ('Bowl and College Football Playoff lines. SEPARATE from the regular-season '
                 'dataset ON PURPOSE: postseason participation is not uniform (opt-outs, and '
                 'a playoff team plays several extra games), so folding it into the pool would '
                 'rank players on different amounts of football. Display only — never feeds '
                 'dDOM, PPA, percentiles, peer pools or Scout ordering.'),
        'players': out,
    }
    body = json.dumps(payload, separators=(',', ':'))
    print(f"size: {len(body)/1024:.0f} KB")

    if dry:
        print(f"\nDRY RUN — {OUT} not written.")
    elif not out:
        print(f"\nNOT WRITING {OUT} — no players matched. Check the season files exist first.")
        sys.exit(1)
    else:
        with open(OUT + '.tmp', 'w') as f: f.write(body)
        os.replace(OUT + '.tmp', OUT)
        print(f"\nWROTE {OUT}")
    print("=" * 74)


if __name__ == '__main__':
    main()
