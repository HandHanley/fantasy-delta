#!/usr/bin/env python3
"""
DELTA — BACKFILL COLLEGE PPA

Fills ppa / ppaPass / ppaRush / ppaTot into college season files that were built
before the pipeline started pulling /ppa/players/season. As of Aug 2026 that is
2020, 2021 and 2022 (0 PPA rows each); 2023-2025 already carry it.

WHY THIS AND NOT A RE-RUN OF fetch-college.py:
  Re-running the full pipeline for an old season would rebuild that file from
  scratch using TODAY's quota and inclusion logic, which can change WHICH players
  are in that season's universe. Those files are already being read by the player
  pages. This script only ever writes four numeric keys onto records that already
  exist, and never adds, removes or reorders a player. One API call per season
  instead of ~27.

MATCHING is copied from fetch-college.py so the join behaves identically:
  athlete id first, then (normalised name, position). norm() strips accents and
  non-alphanumerics — the Gainwell / Ja'Marr class of bug lives exactly here.

Env:  CFBD_API_KEY (required)
Usage:
  python3 scripts/backfill-college-ppa.py --dry-run
  python3 scripts/backfill-college-ppa.py --confirm
  python3 scripts/backfill-college-ppa.py --confirm --years 2022
  python3 scripts/backfill-college-ppa.py --confirm --force     # overwrite existing PPA
"""
import os, sys, json, glob, unicodedata, datetime

DEFAULT_YEARS = [2020, 2021, 2022]
MIN_MATCH_RATE = 0.55          # abort a season below this; something is wrong upstream
ALIAS = "data/college-players.json"


# ── helpers: identical to fetch-college.py ────────────────────────────────────
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


def _f(o, *names):
    v = g(o, *names) if o is not None else None
    try:
        return round(float(v), 3) if v is not None else None
    except (TypeError, ValueError):
        return None


def build_ppa_index(ppa_rows):
    """Same shape fetch-college.py builds: id key plus (nm, name, pos) fallback."""
    PPA = {}
    for r in (ppa_rows or []):
        avg = g(r, "average_ppa"); tot = g(r, "total_ppa")
        rec = {"ppa": _f(avg, "all"), "ppaPass": _f(avg, "var_pass", "pass"),
               "ppaRush": _f(avg, "rush"), "ppaTot": _f(tot, "all")}
        pid = g(r, "id"); nm = g(r, "name"); pos = g(r, "position")
        if pid is not None: PPA[str(pid)] = rec
        if nm: PPA[("nm", norm(nm), pos)] = rec
    return PPA


# ── the merge: pure, so it can be tested without the API ──────────────────────
def merge_ppa(players, PPA, force=False):
    """Writes the four PPA keys onto existing records. Returns a stats dict.
    Never adds, removes or reorders players."""
    st = {"total": len(players), "by_id": 0, "by_name": 0, "missed": 0,
          "skipped_existing": 0, "written": 0, "misses": []}
    for p in players:
        if not force and p.get("ppa") is not None:
            st["skipped_existing"] += 1
            continue
        rec = None
        pid = p.get("id")
        if pid is not None and str(pid) in PPA:
            rec = PPA[str(pid)]; st["by_id"] += 1
        else:
            k = ("nm", norm(p.get("n")), p.get("pos"))
            if k in PPA:
                rec = PPA[k]; st["by_name"] += 1
        if rec is None:
            st["missed"] += 1
            if len(st["misses"]) < 12:
                st["misses"].append(f"{p.get('n')} ({p.get('pos')}, {p.get('tm')})")
            continue
        p["ppa"] = rec["ppa"]; p["ppaPass"] = rec["ppaPass"]
        p["ppaRush"] = rec["ppaRush"]; p["ppaTot"] = rec["ppaTot"]
        st["written"] += 1
    st["matched"] = st["by_id"] + st["by_name"]
    considered = st["total"] - st["skipped_existing"]
    st["rate"] = (st["matched"] / considered) if considered else 1.0
    return st


def season_path(year, data):
    """The alias file holds whichever season the app treats as current."""
    p = f"data/college-players-{year}.json"
    if os.path.exists(p): return p
    if os.path.exists(ALIAS):
        try:
            if json.load(open(ALIAS)).get("season") == year: return ALIAS
        except Exception:
            pass
    return p


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    confirm = "--confirm" in args
    force = "--force" in args
    years = DEFAULT_YEARS
    if "--years" in args:
        i = args.index("--years")
        years = [int(x) for x in args[i + 1].split(",")]

    if not dry and not confirm:
        print("BACKFILL REFUSED — this run would rewrite college season files.")
        print("Add --confirm to write them, or --dry-run to rehearse without writing.")
        print("Nothing was written.\n")
        print("Usage: python3 scripts/backfill-college-ppa.py --confirm [--force] [--years 2022]")
        print("       python3 scripts/backfill-college-ppa.py --dry-run")
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

    print("=" * 72)
    print(f"DELTA — BACKFILL COLLEGE PPA   seasons: {', '.join(map(str, years))}")
    print(f"mode: {'DRY RUN — nothing will be written' if dry else 'WRITE'}"
          f"{'  (--force: existing PPA will be overwritten)' if force else ''}")
    print("=" * 72)

    cfg = cfbd.Configuration(access_token=key)
    results, calls = [], 0
    with cfbd.ApiClient(cfg) as api:
        metrics_api = cfbd.MetricsApi(api)
        for year in years:
            path = season_path(year, None)
            if not os.path.exists(path):
                print(f"\n{year}: SKIP — {path} does not exist"); continue
            data = json.load(open(path))
            players = data.get("players") or []
            have = sum(1 for p in players if p.get("ppa") is not None)
            print(f"\n{year}  {path}  ({len(players)} players, {have} already have PPA)")
            if have and not force:
                print(f"  SKIP — season already has PPA. Use --force to overwrite.")
                continue

            calls += 1
            try:
                rows = metrics_api.get_predicted_points_added_by_player_season(
                    year=year, exclude_garbage_time=True)
                print(f"  [{calls}] GET /ppa/players/season {year} -> {len(rows) if rows else 0} rows")
            except Exception as e:
                print(f"  [{calls}] GET /ppa/players/season {year} FAILED: {str(e)[:150]}")
                continue
            if not rows:
                print(f"  ABORT {year}: no PPA rows returned; leaving the file untouched.")
                continue

            PPA = build_ppa_index(rows)
            st = merge_ppa(players, PPA, force=force)
            print(f"  matched {st['matched']}/{st['total'] - st['skipped_existing']} "
                  f"({st['rate']*100:.1f}%)  by id {st['by_id']} · by name {st['by_name']} · missed {st['missed']}")
            if st["misses"]:
                print(f"  unmatched (first {len(st['misses'])}): " + "; ".join(st["misses"]))

            if st["rate"] < MIN_MATCH_RATE:
                print(f"  ABORT {year}: match rate below {MIN_MATCH_RATE*100:.0f}% — "
                      f"that usually means the season or the endpoint shape changed. File untouched.")
                continue

            if dry:
                print(f"  DRY RUN: would write {st['written']} records to {path}")
            else:
                data["players"] = players
                data.setdefault("backfill", {})["ppa"] = {
                    "at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "written": st["written"], "matched": st["matched"],
                    "rate": round(st["rate"], 4),
                    "source": "GET /ppa/players/season (exclude_garbage_time=True)",
                    "note": ("PPA added after the original build. All other fields are as "
                             "the original run produced them."),
                }
                tmp = path + ".tmp"
                with open(tmp, "w") as f:
                    json.dump(data, f, separators=(",", ":"))
                os.replace(tmp, path)
                print(f"  WROTE {st['written']} records to {path}")
            results.append((year, st))

    print("\n" + "=" * 72)
    if not results:
        print("Nothing to do.")
    for year, st in results:
        print(f"  {year}: {st['written']} written · {st['rate']*100:.1f}% matched")
    print(f"  API calls used: {calls}")
    if dry:
        print("  DRY RUN — nothing was written.")
    print("=" * 72)


if __name__ == "__main__":
    main()
