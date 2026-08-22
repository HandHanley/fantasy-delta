#!/usr/bin/env python3
"""
DELTA — FETCH DRAFT PICKS (calibration input)

Pulls CFBD /draft/picks for a range of draft years and writes data/draft-picks.json.

WHAT THIS IS FOR:
  Calibration only. fetch-college.py has carried a note since it was written —
  "PROVISIONAL — calibrate against /draft/picks" — for both DDOM_SWING and the
  dominator definition. This is that input.

  The point of draft data is the players it lets us score who are NOT on an NFL roster:
  backs who were drafted and washed out, and backs who went undrafted. Any study
  restricted to current NFL rosters conditions on survival and cannot see them, which is
  what limited the first pass at the RB weight question to 58 players.

WHAT IT IS NOT:
  Not a platform data source. Nothing in the app reads data/draft-picks.json. It exists
  so studies in study/ can join college production to draft capital. It does not touch
  the DELTA Score, projections, the buy/sell call, or the accuracy ledger.

Env:  CFBD_API_KEY (required)
Usage:
  python3 scripts/fetch-draft-picks.py --dry-run
  python3 scripts/fetch-draft-picks.py --confirm
  python3 scripts/fetch-draft-picks.py --confirm --years 2021-2026
"""
import os, sys, json, unicodedata, datetime

OUT = 'data/draft-picks.json'
DEFAULT_FIRST, DEFAULT_LAST = 2021, 2026
MIN_PICKS_PER_YEAR = 200          # a real NFL draft is ~257; far below means a bad pull


def norm(s):
    """Name key for joining. Mirrors fetch-college.py exactly — the Gainwell / Ja'Marr
    class of bug lives here, and a mismatch shows up as a player looking undrafted."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return "".join(c for c in s.lower() if c.isalnum())


def g(o, *names, default=None):
    for n in names:
        v = getattr(o, n, None)
        if v is not None:
            return v
    return default


def main():
    args = sys.argv[1:]
    dry = '--dry-run' in args
    confirm = '--confirm' in args
    first, last = DEFAULT_FIRST, DEFAULT_LAST
    if '--years' in args:
        spec = args[args.index('--years') + 1]
        if '-' in spec:
            a, b = spec.split('-'); first, last = int(a), int(b)
        else:
            first = last = int(spec)

    if not dry and not confirm:
        print("REFUSED — this run would write data/draft-picks.json.")
        print("Add --confirm to write it, or --dry-run to rehearse.\n")
        print("Usage: python3 scripts/fetch-draft-picks.py --confirm [--years 2021-2026]")
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
    print(f"DELTA — FETCH DRAFT PICKS   {first}-{last}")
    print("mode: " + ("DRY RUN — nothing will be written" if dry else "WRITE"))
    print("=" * 72)

    cfg = cfbd.Configuration(access_token=key)
    picks, calls, bad = {}, 0, []
    with cfbd.ApiClient(cfg) as api:
        draft_api = cfbd.DraftApi(api)
        for year in range(first, last + 1):
            calls += 1
            try:
                rows = draft_api.get_draft_picks(year=year)
            except Exception as e:
                print(f"  [{calls:>2}] {year} FAILED: {str(e)[:140]}")
                bad.append(year); continue
            rows = rows or []
            byPos = {}
            for r in rows:
                nm = g(r, 'name')
                if not nm:
                    fn, ln = g(r, 'first_name', default=''), g(r, 'last_name', default='')
                    nm = (str(fn) + ' ' + str(ln)).strip()
                if not nm:
                    continue
                pos = g(r, 'position')
                pos = getattr(pos, 'position_group', None) or getattr(pos, 'name', None) or pos
                overall = g(r, 'overall', 'pick')
                rec = {
                    'name': nm,
                    'year': year,
                    'overall': overall,
                    'round': g(r, 'round'),
                    'pick': g(r, 'pick'),
                    'position': str(pos) if pos is not None else None,
                    'collegeTeam': g(r, 'college_team', 'college'),
                    'nflTeam': g(r, 'nfl_team', 'team'),
                }
                picks[norm(nm) + '|' + str(year)] = rec
                p = rec['position'] or '?'
                byPos[p] = byPos.get(p, 0) + 1
            rb = byPos.get('RB', 0) + byPos.get('Running Back', 0)
            flag = '' if len(rows) >= MIN_PICKS_PER_YEAR else '   <-- LOW, check this year'
            print(f"  [{calls:>2}] {year}: {len(rows):>4} picks · RB {rb:>3}{flag}")
            if len(rows) < MIN_PICKS_PER_YEAR:
                bad.append(year)

    print()
    if bad:
        print(f"WARNING: {len(bad)} year(s) look wrong or failed: {bad}")
        print("A year with too few picks will make its whole class look undrafted, which")
        print("would bias any study using it. Investigate before running the analysis.")
    total = len(picks)
    print(f"total picks collected: {total} across {last - first + 1} years · API calls: {calls}")

    if dry:
        print(f"\nDRY RUN — {OUT} not written.")
    elif bad:
        print(f"\nNOT WRITING {OUT} — resolve the flagged years first, or re-run with just the good ones.")
        sys.exit(1)
    else:
        payload = {
            'generated': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'years': list(range(first, last + 1)),
            'note': ('CFBD /draft/picks. CALIBRATION INPUT ONLY — no app code reads this. '
                     'Keyed by normalised name + draft year. Used by study/ scripts to join '
                     'college production to draft capital, including players who never '
                     'reached an NFL roster.'),
            'picks': picks,
        }
        with open(OUT + '.tmp', 'w') as f:
            json.dump(payload, f, separators=(',', ':'))
        os.replace(OUT + '.tmp', OUT)
        print(f"\nWROTE {OUT}")
    print("=" * 72)


if __name__ == '__main__':
    main()
