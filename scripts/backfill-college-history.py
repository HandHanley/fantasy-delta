#!/usr/bin/env python3
"""
DELTA — COLLEGE HISTORY BACKFILL (12 Nov 2026). Feeds docs/PREREG-pick-class-strength.md.

Pulls whole college seasons from before DELTA's college data starts (2020), so the class-strength test can see
each rookie class's final college season back to the 2014 class. Steve approved the pull on 12 Nov 2026 with the
existing CollegeFootballData key.

HOW IT STAYS AWAY FROM THE LIVE SITE
  It runs the live pipeline, scripts/fetch-college.py, UNCHANGED, once per season, from a throwaway folder. That
  script writes everything under a relative data/ folder, so every file it writes lands in the throwaway copy:
    - data/college-players-YYYY.json   -> copied to study/data/college-history/ (the only thing kept)
    - data/college-portal.json         -> thrown away. Run in the repo, a backfill would overwrite the LIVE portal
                                          list with that old season's (empty before 2021).
    - data/college-classes-YYYY.json   -> thrown away.
    - data/college-players.json        -> never written (CFBD_CURRENT_SEASON pinned to 2026; backfill < current).
  Nothing is written to data/, so the College tab index (build-college-index.js reads every
  data/college-players-YYYY.json) and the published site are untouched. study/ is excluded from deploys.

WHAT IS DIFFERENT FROM A LIVE SEASON FILE
  - Wider position quotas (QB 120, RB 250, WR 400, TE 150, against 70/110/160/70). Checked 12 Nov 2026 on the
    2021-2023 classes: the normal pool missed drafted rookies whose last season was quiet (Joshua Palmer,
    Roschon Johnson, Michael Wilson). Costs no API calls. The study must rank everyone against the same fixed
    pool in every season (top N by production at each position), so a wider file does not change percentiles.
  - No draft-board door (DELTA_BOARD_FILE points nowhere): today's board means nothing for 2013.
  - Roster rescue on (CFBD_RESCUE_UNROSTERED=1, 12 Nov 2026): CFBD's older rosters leave out real players whose
    box-score rows exist (Chubb and Michel, Georgia 2017). They are kept when CFBD's PPA or usage list names them
    at a skill position for the same team, and marked "rescued": 1. See fetch-college.py.
  - The continuity door reads the season before from the throwaway folder, so seasons run oldest first.

THE BUDGET RULE
  CFBD's free tier is 1,000 calls a month and the live college refresh needs its share until the count resets
  (about 30 calls a run, three runs a week in season). Before pulling, the script asks CFBD (GET /info) how many
  calls are left and when they reset, keeps a reserve for the live refresh, and pulls only the seasons that fit,
  oldest first. Anything that does not fit is reported as postponed, never pulled. If CFBD cannot say, nothing
  is pulled.

    python scripts/backfill-college-history.py --years 2013-2019            # dry run: budget and plan, no pulls
    python scripts/backfill-college-history.py --years 2013-2019 --confirm  # pull, write study/data/college-history/

Env: CFBD_API_KEY (required). CFBD_BASE overrides the API host (offline tests only).
"""
import argparse, collections, datetime, json, math, os, re, shutil, subprocess, sys, tempfile, urllib.error, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FETCH = ROOT / 'scripts' / 'fetch-college.py'
OUT_DIR = ROOT / 'study' / 'data' / 'college-history'
REPORT = OUT_DIR / 'backfill-report.json'
LIVE_FROM = 2020                 # data/college-players-2020.json onward already exists and is live
PER_SEASON = 31                  # fbs, roster, usage, talent (+3 carry-forward), PPA, portal, 5 recruiting, weeks 0-16
RUN_COST, RUNS_PER_WEEK, SPARE = 30, 3, 30   # the live refresh's needs until the reset, plus a spare
QUOTAS = {'Q_QB': '120', 'Q_RB': '250', 'Q_WR': '400', 'Q_TE': '150'}
MIN_PLAYERS = 300                # a real season file holds well over this; fewer means the pull went wrong

KEY = (os.environ.get('CFBD_API_KEY') or '').strip()
BASE = os.environ.get('CFBD_BASE') or 'https://api.collegefootballdata.com'


def ann(level, title, msg):
    msg = str(msg).replace(KEY, '***') if KEY else str(msg)
    print(f"::{level} title={title}::{msg.replace(chr(10), ' ')[:900]}", flush=True)


def parse_years(s):
    out = set()
    for part in str(s).replace(' ', '').split(','):
        if not part: continue
        if '-' in part:
            a, b = (int(x) for x in part.split('-', 1)); out.update(range(min(a, b), max(a, b) + 1))
        else:
            out.add(int(part))
    return sorted(out)


def cfbd_info():
    """GET /info -> (remaining calls, reset datetime or None). Raises on any failure: no answer, no pull."""
    req = urllib.request.Request(BASE + '/info', headers={'Authorization': 'Bearer ' + KEY, 'Accept': 'application/json',
                                                          'User-Agent': 'DELTA/1.0 (college history backfill)'})
    with urllib.request.urlopen(req, timeout=30) as r:
        info = json.loads(r.read().decode('utf-8') or 'null')
    if not isinstance(info, dict) or info.get('remainingCalls') is None:
        raise RuntimeError(f'CFBD /info gave no remaining-call count: {str(info)[:200]}')
    reset = None
    try:
        reset = datetime.datetime.fromisoformat(str(info.get('resetAt')).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        pass
    return int(info['remainingCalls']), reset, info


def reserve_for(reset, now=None):
    """Calls to leave for the live college refresh until the monthly count resets. Unknown reset date -> a full
    month's worth, so an unreadable date can only make the backfill smaller."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    days = 31 if reset is None else max(0.0, (reset - now).total_seconds() / 86400)
    return int(math.ceil(days / 7 * RUNS_PER_WEEK * RUN_COST)) + SPARE


def plan(years, remaining, reserve):
    """Oldest first, as many seasons as fit inside remaining - reserve. Returns (pull, postponed)."""
    room = remaining - reserve
    n = max(0, min(len(years), room // PER_SEASON))
    return years[:n], years[n:]


def coverage(players):
    n = len(players) or 1
    out = {}
    for fld in ('ppa', 'usg', 'rsh', 'ddom', 'dom', 'stars', 'cls', 'rcls'):
        out[fld] = round(sum(1 for p in players if p.get(fld) is not None) / n, 3)
    return out


def run_season(y, scratch):
    """One season through the unchanged live pipeline, inside scratch/. Returns a report row."""
    data = scratch / 'data'
    data.mkdir(parents=True, exist_ok=True)
    prev = OUT_DIR / f'college-players-{y - 1}.json'          # continuity door: last season's universe
    if prev.exists() and not (data / prev.name).exists():
        shutil.copyfile(prev, data / prev.name)
    env = dict(os.environ, CFBD_YEAR=str(y), CFBD_WEEKS='16', CFBD_CURRENT_SEASON='2026', CFBD_PROBE='',
               CFBD_PROBE_WEEK='', CFBD_PORTAL_YEAR=str(y), CFBD_RESCUE_UNROSTERED='1',
               DELTA_BOARD_FILE=str(scratch / 'no-board.json'), **QUOTAS)
    print(f'\n{"#" * 72}\n# season {y}\n{"#" * 72}', flush=True)
    p = subprocess.run([sys.executable, str(FETCH)], cwd=str(scratch), env=env, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(p.stdout, flush=True)
    # Every request fetch-college.py makes prints a numbered line, "  [  7] GET /talent ...", even when it exits
    # early, so the highest number is the season's real cost. No numbered line at all -> assume the estimate.
    m = re.findall(r'^\s*\[\s*(\d+)\]', p.stdout, flags=re.M)
    calls = max(map(int, m)) if m else PER_SEASON
    row = {'season': y, 'calls': calls, 'exit': p.returncode, 'rescue': True}
    # call() in fetch-college.py turns a failed request into an empty answer, so an outage or a used-up key can
    # look exactly like a season CFBD has no data for. Its "FAILED:" line is the only way to tell them apart.
    failed = [ln.strip() for ln in p.stdout.splitlines() if re.match(r'^\s*\[\s*\d+\].*FAILED:', ln)]
    # One known exception: fetch-college.py always asks for week 0 (late-August games before week 1), and CFBD
    # answers 400 Bad Request for a season that had no week 0 (2013, seen 12 Nov 2026). That is "no such week",
    # not an outage, so it is noted and not counted. Every other failure still stops the backfill.
    no_wk0 = [ln for ln in failed if re.search(r'GET /games/players wk0\s+FAILED: \(400\)', ln)]
    if no_wk0:
        row['no_week0'] = True
        failed = [ln for ln in failed if ln not in no_wk0]
    if failed:
        row['failed_calls'] = failed[:5]
    f = data / f'college-players-{y}.json'
    if p.returncode != 0 or (failed and not f.exists()):
        row['status'] = 'failed'
        return row
    if not f.exists():
        row['status'] = 'no data'                                # CFBD had no rosters or games for the season
        return row
    d = json.load(open(f))
    pl = d.get('players') or []
    weeks = sorted({r.get('w') for x in pl for r in x.get('g', []) if r.get('w') is not None})
    row.update(players=len(pl), rescued=sum(1 for x in pl if x.get('rescued')),
               by_pos=dict(collections.Counter(x['pos'] for x in pl)), doors=d.get('counts'),
               weeks=weeks, coverage=coverage(pl), file_season=d.get('season'))
    if d.get('season') != y or len(pl) < MIN_PLAYERS:
        row['status'] = 'rejected'                               # wrong season or implausibly small: not kept
        return row
    if failed:
        row['status'] = 'incomplete'                             # a week or a feed missing: holes, not kept
        return row
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(f, OUT_DIR / f.name)
    row['status'] = 'saved'
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--years', default='2013-2019')
    ap.add_argument('--confirm', action='store_true', help='pull and write; without it, budget and plan only')
    a = ap.parse_args()
    years = parse_years(a.years)
    bad = [y for y in years if y >= LIVE_FROM or y < 2004]
    if bad or not years:
        ann('error', 'College history backfill', f'Seasons {bad or a.years} refused: only 2004-{LIVE_FROM - 1}. '
            f'{LIVE_FROM} onward is already in data/ and live.')
        return 1
    # A re-run after a partial one pays only for the gaps. A season counts as saved only if it was pulled with
    # the roster rescue (12 Nov 2026): the first 2013-2019 files were saved without it and are pulled again.
    done = {}
    if REPORT.exists():
        done = {r['season']: r for r in json.load(open(REPORT)).get('seasons', [])}
    have = [y for y in years if (OUT_DIR / f'college-players-{y}.json').exists()
            and done.get(y, {}).get('status') == 'saved' and done.get(y, {}).get('rescue')]
    if have:
        ann('notice', 'Already saved', f'Skipping {", ".join(map(str, have))}: delete the file to pull a season again.')
        years = [y for y in years if y not in have]
        if not years:
            return 0
    if not KEY:
        ann('error', 'College history backfill', 'CFBD_API_KEY is not set.'); return 1
    try:
        remaining, reset, info = cfbd_info()
    except Exception as e:
        ann('error', 'College history backfill', f'Could not read the CFBD budget, so nothing was pulled: {e}')
        return 1
    reserve = reserve_for(reset)
    pull, later = plan(years, remaining, reserve)
    ann('notice', 'CFBD budget', f'{remaining} calls left (used {info.get("usedCalls")} of {info.get("monthlyLimit")}), '
        f'resets {info.get("resetAt")}. Keeping {reserve} for the live college refresh until then. '
        f'About {PER_SEASON} calls a season.')
    ann('notice', 'Backfill plan', f'Pull: {", ".join(map(str, pull)) or "nothing"} (about {PER_SEASON * len(pull)} calls). '
        f'Postponed until the count resets: {", ".join(map(str, later)) or "none"}.')
    if not a.confirm:
        ann('notice', 'Dry run', 'Nothing pulled. Run again with confirm = yes to pull the seasons above.')
        return 0
    rows, spent = [], 0
    with tempfile.TemporaryDirectory(prefix='delta-cfb-history-') as tmp:
        scratch = Path(tmp)
        for y in pull:
            if remaining - spent - PER_SEASON < reserve:          # a season cost more than estimated: stop early
                later = [s for s in pull if s >= y] + later
                ann('warning', 'Backfill stopped', f'Budget reached before {y}; postponed: {later}')
                break
            row = run_season(y, scratch)
            spent += row['calls']; rows.append(row)
            cov = row.get('coverage') or {}
            ann({'saved': 'notice', 'no data': 'warning'}.get(row['status'], 'error'), f'Season {y}: {row["status"]}',
                f'{row.get("players", 0)} players ({row.get("rescued", 0)} rescued) {row.get("by_pos", {})}, {row["calls"]} calls, '
                f'weeks {row.get("weeks", [])[:1]}-{row.get("weeks", [])[-1:]}, PPA {cov.get("ppa")}, '
                f'usage {cov.get("usg")}, dDOM {cov.get("ddom")}, stars {cov.get("stars")}.')
            if row['status'] in ('failed', 'rejected', 'incomplete'):   # do not keep spending into a broken feed
                later = [s for s in pull if s > y] + later
                break
    old = {}
    if REPORT.exists():
        old = {r['season']: r for r in json.load(open(REPORT)).get('seasons', [])}
    for r in rows: old[r['season']] = r
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json.dump({'generated': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
               'note': ('College seasons before 2020 for docs/PREREG-pick-class-strength.md. Built by '
                        'scripts/backfill-college-history.py through the unchanged fetch-college.py with wider quotas '
                        '(' + ', '.join(f'{k[2:]} {v}' for k, v in QUOTAS.items()) + ') and no board door. Study data '
                        'only: never read by the site. Source: CollegeFootballData (credited on the site).'),
               'quotas': QUOTAS, 'calls_this_run': spent, 'postponed': later,
               'seasons': [old[k] for k in sorted(old)]}, open(REPORT, 'w'), indent=1)
    print(f'\nwrote {REPORT}  ({spent} calls this run)')
    return 1 if any(r['status'] in ('failed', 'rejected', 'incomplete') for r in rows) else 0


if __name__ == '__main__':
    sys.exit(main())
