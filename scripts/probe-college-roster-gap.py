#!/usr/bin/env python3
"""
DELTA — COLLEGE ROSTER-GAP PROBE (13 Nov 2026). For the class-strength backfill (docs/PREREG-pick-class-strength.md).

The 2017 backfill with the roster rescue on still has no Nick Chubb or Sony Michel, and rescued nobody. Georgia's box
scores hold ~400 carries (68% of the team's) that match no player in the file, so their game rows exist. The rescue
looks players up in CFBD's PPA and usage lists, so either those lists leave them out too or they label them in a
way the rescue does not match. This probe asks CFBD directly, for one team and season, and saves what each source
says about every skill-position player, so the fix is chosen from facts.

About 7 calls: roster, PPA, usage and season stats for the team (one each), one week of box scores for the team,
and one player search per name. Writes study/data/college-history/probe-YEAR-TEAM.json only.

    python scripts/probe-college-roster-gap.py --year 2017 --team Georgia --week 1 --names "Nick Chubb,Sony Michel"

LEAGUE-WIDE SCAN (--team ALL, 13 Nov 2026), about 4 calls: the whole FBS roster plus every player's season rushing,
receiving and passing. Lists roster players with position "?" who touched the ball at least 5 times, and whether each
is in the live data/college-players-YEAR.json (the College tab). Answers "is the live site missing real players?".
Writes study/data/college-history/probe-YEAR-ALL.json only.

    python scripts/probe-college-roster-gap.py --year 2026 --team ALL
"""
import argparse, json, os, re, sys, unicodedata
from pathlib import Path
import cfbd

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / 'study' / 'data' / 'college-history'
KEY = (os.environ.get('CFBD_API_KEY') or '').strip()
CALLS = 0


def norm(s):
    s = unicodedata.normalize('NFKD', str(s or ''))
    return ''.join(c for c in s if not unicodedata.combining(c) and c.isalnum()).lower()


def g(o, k):
    return o.get(k) if isinstance(o, dict) else getattr(o, k, None)


def call(label, fn, **kw):
    global CALLS
    CALLS += 1
    try:
        r = fn(**kw)
        print(f'  [{CALLS}] {label}: {len(r or [])} rows', flush=True)
        return r or [], None
    except Exception as e:
        msg = str(e).replace(KEY, '***') if KEY else str(e)
        print(f'  [{CALLS}] {label}: FAILED {msg[:200]}', flush=True)
        return [], msg[:300]


def num(x):
    try: return float(str(x).split('/')[-1]) if x is not None else 0.0
    except ValueError: return 0.0


def scan(year):
    out = {'year': year, 'mode': 'league-wide', 'errors': {}}
    with cfbd.ApiClient(cfbd.Configuration(access_token=KEY)) as api:
        rows, err = call('GET /roster (fbs)', cfbd.TeamsApi(api).get_roster, year=year, classification='fbs')
        if err: out['errors']['roster'] = err
        roster = [{'id': str(g(p, 'id')), 'n': f"{g(p, 'first_name') or ''} {g(p, 'last_name') or ''}".strip(),
                   'pos': g(p, 'position') or '', 'tm': g(p, 'team'), 'wt': g(p, 'weight')} for p in rows]
        stats = {}
        for cat in ('rushing', 'receiving', 'passing'):
            rows, err = call(f'GET /stats/player/season {cat}', cfbd.StatsApi(api).get_player_season_stats,
                             year=year, category=cat)
            if err: out['errors'][cat] = err
            for r in rows:
                e = stats.setdefault(str(g(r, 'player_id')), {'n': g(r, 'player'), 'pos': g(r, 'position'), 'tm': g(r, 'team')})
                e[f"{cat}.{g(r, 'stat_type')}"] = g(r, 'stat')
    from collections import Counter
    out['roster_positions'] = dict(Counter(r['pos'] or '(blank)' for r in roster).most_common())
    live_p = ROOT / 'data' / f'college-players-{year}.json'
    live = {(norm(p['n']), p['tm']) for p in json.load(open(live_p))['players']} if live_p.exists() else set()
    hits = []
    for r in roster:
        if r['pos'] not in ('?', ''): continue
        st = stats.get(r['id'])
        if not st: continue
        car, rec, att = num(st.get('rushing.CAR')), num(st.get('receiving.REC')), num(st.get('passing.ATT') or st.get('passing.C/ATT'))
        if car + rec + att < 5: continue
        hits.append({'n': r['n'], 'tm': r['tm'], 'roster_pos': r['pos'] or '(blank)', 'stats_pos': st.get('pos'), 'wt': r['wt'],
                     'car': car, 'rush_yds': num(st.get('rushing.YDS')), 'rec': rec, 'rec_yds': num(st.get('receiving.YDS')),
                     'att': att, 'pass_yds': num(st.get('passing.YDS')),
                     'in_live_file': (norm(r['n']), r['tm']) in live})
    hits.sort(key=lambda h: -(h['rush_yds'] + h['rec_yds'] + 0.4 * h['pass_yds']))
    out.update(roster_players=len(roster), unpositioned=sum(1 for r in roster if r['pos'] in ('?', '')),
               unpositioned_with_touches=len(hits), missing_from_live_file=sum(1 for h in hits if not h['in_live_file']),
               live_file=str(live_p.relative_to(ROOT)) if live_p.exists() else None, players=hits, calls=CALLS)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    f = OUT_DIR / f'probe-{year}-ALL.json'
    json.dump(out, open(f, 'w'), indent=1)
    top = '; '.join(f"{h['n']} ({h['tm']}, {h['rush_yds'] + h['rec_yds']:.0f} yds{'' if h['in_live_file'] else ', NOT on site'})" for h in hits[:8])
    print(f"::notice title=Scan {year}::{len(roster)} roster players, {out['unpositioned']} with no position, "
          f"{len(hits)} of them touched the ball 5+ times, {out['missing_from_live_file']} not in the live file. {CALLS} calls.")
    print(f'::notice title=Scan {year} top::{top}'[:900])
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--year', type=int, default=2017)
    ap.add_argument('--team', default='Georgia')
    ap.add_argument('--week', type=int, default=1)
    ap.add_argument('--names', default='Nick Chubb,Sony Michel')
    a = ap.parse_args()
    if not KEY:
        print('::error title=Roster-gap probe::CFBD_API_KEY is not set.'); return 1
    if a.team.strip().upper() == 'ALL':
        return scan(a.year)
    names = [n.strip() for n in a.names.split(',') if n.strip()]
    targets = {norm(n): n for n in names}
    out = {'year': a.year, 'team': a.team, 'week': a.week, 'names': names, 'errors': {}}
    with cfbd.ApiClient(cfbd.Configuration(access_token=KEY)) as api:
        teams, metrics, players = cfbd.TeamsApi(api), cfbd.MetricsApi(api), cfbd.PlayersApi(api)
        games, stats = cfbd.GamesApi(api), cfbd.StatsApi(api)

        rows, err = call('GET /roster', teams.get_roster, team=a.team, year=a.year)
        out['roster'] = [{'id': g(p, 'id'), 'n': f"{g(p, 'first_name') or ''} {g(p, 'last_name') or ''}".strip(),
                          'pos': g(p, 'position'), 'cls': g(p, 'year')} for p in rows]
        if err: out['errors']['roster'] = err

        rows, err = call('GET /ppa/players/season', metrics.get_predicted_points_added_by_player_season,
                         year=a.year, team=a.team, exclude_garbage_time=True)
        out['ppa'] = [{'id': g(r, 'id'), 'n': g(r, 'name'), 'pos': g(r, 'position'), 'tm': g(r, 'team')} for r in rows]
        if err: out['errors']['ppa'] = err

        rows, err = call('GET /player/usage', players.get_player_usage, year=a.year, team=a.team)
        out['usage'] = [{'id': g(r, 'id'), 'n': g(r, 'name'), 'pos': g(r, 'position'), 'tm': g(r, 'team')} for r in rows]
        if err: out['errors']['usage'] = err

        rows, err = call('GET /stats/player/season', stats.get_player_season_stats, year=a.year, team=a.team)
        seen = {}
        for r in rows:
            k = str(g(r, 'player_id'))
            e = seen.setdefault(k, {'id': g(r, 'player_id'), 'n': g(r, 'player'), 'pos': g(r, 'position'),
                                    'tm': g(r, 'team'), 'stats': {}})
            if g(r, 'category') in ('rushing', 'receiving', 'passing') and g(r, 'stat_type') in ('CAR', 'YDS', 'REC', 'ATT'):
                e['stats'][f"{g(r, 'category')}.{g(r, 'stat_type')}"] = g(r, 'stat')
        out['season_stats'] = [e for e in seen.values() if e['stats']]
        if err: out['errors']['season_stats'] = err

        rows, err = call(f'GET /games/players wk{a.week}', games.get_game_player_stats, year=a.year, week=a.week,
                         team=a.team, season_type='regular')
        box = {}
        for gm in rows:
            for tm in (g(gm, 'teams') or []):
                if g(tm, 'team') != a.team: continue
                for cat in (g(tm, 'categories') or []):
                    if (g(cat, 'name') or '').lower() not in ('rushing', 'receiving', 'passing'): continue
                    for typ in (g(cat, 'types') or []):
                        for ath in (g(typ, 'athletes') or []):
                            e = box.setdefault(str(g(ath, 'id')), {'id': g(ath, 'id'), 'n': g(ath, 'name'), 'stats': {}})
                            e['stats'][f"{g(cat, 'name')}.{g(typ, 'name')}"] = g(ath, 'stat')
        out['box_week'] = list(box.values())
        if err: out['errors']['box_week'] = err

        out['search'] = {}
        for n in names:
            rows, err = call(f'GET /player/search {n}', players.search_players, search_term=n, year=a.year)
            out['search'][n] = [{'id': g(r, 'id'), 'n': g(r, 'name'), 'pos': g(r, 'position'), 'tm': g(r, 'team'),
                                 'years': [g(r, 'active_start_year'), g(r, 'active_end_year')]} for r in rows][:10]
            if err: out['errors'][f'search {n}'] = err

    # The answer, per name: where CFBD has him, under which id and position.
    verdict = {}
    for k, n in targets.items():
        def hit(src):
            return [{x: e.get(x) for x in ('id', 'n', 'pos', 'tm') if x in e} for e in out.get(src, []) if norm(e.get('n')) == k]
        verdict[n] = {src: hit(src) for src in ('roster', 'ppa', 'usage', 'season_stats', 'box_week')}
        verdict[n]['search'] = [e for e in out['search'].get(n, []) if norm(e['n']) == k]
    out['verdict'], out['calls'] = verdict, CALLS
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    f = OUT_DIR / f"probe-{a.year}-{re.sub(r'[^A-Za-z0-9]+', '-', a.team)}.json"
    json.dump(out, open(f, 'w'), indent=1)
    for n, v in verdict.items():
        found = ', '.join(f"{src}: {'yes ' + str([(e.get('id'), e.get('pos')) for e in v[src]]) if v[src] else 'NO'}"
                          for src in v)
        print(f'::notice title=Probe {n}::{found}'[:900])
    print(f'::notice title=Probe sizes::roster {len(out["roster"])}, ppa {len(out["ppa"])}, usage {len(out["usage"])}, '
          f'season stats {len(out["season_stats"])}, box week {len(out["box_week"])}; {CALLS} calls; wrote {f.name}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
