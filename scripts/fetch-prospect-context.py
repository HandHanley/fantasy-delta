#!/usr/bin/env python3
"""
DELTA — FETCH PROSPECT CONTEXT

Writes two small files the player card reads:

  data/combine.json      athletic testing (height, weight, forty, vertical, broad, cone,
                         shuttle, bench). STATIC — a player's combine never changes, so
                         this only needs re-running when a new draft class tests.

  data/depth-charts.json where he currently sits at his position and who is ahead of him.
                         VOLATILE — this moves through camp and the season, so re-run it
                         whenever you want the card to be current.

Both are DISPLAY CONTEXT ONLY. Nothing here feeds the DELTA Score, the projection, the
buy/sell call, dDOM, PPA or the accuracy ledger. They answer the two questions the card
could not previously answer for a rookie with no NFL snaps: how did he test, and who is
in front of him.

Source is nflverse (nflreadpy), the same library the nightly NFL pipeline already uses —
fetch-player-stats.py has called load_depth_charts for a while, but only ever kept the QB
order. This keeps every offensive skill position.

Scoped to DELTA's universe: RAW in delta-engine.js is the filter, so these files stay
small and no untracked player is carried.

Usage:
  python3 scripts/fetch-prospect-context.py --dry-run
  python3 scripts/fetch-prospect-context.py --confirm
  python3 scripts/fetch-prospect-context.py --confirm --only depth     # just the volatile one
  python3 scripts/fetch-prospect-context.py --confirm --only combine
"""
import os, re, sys, json, math, unicodedata, datetime, subprocess

COMBINE_OUT = 'data/combine.json'
DEPTH_OUT   = 'data/depth-charts.json'
COMBINE_SEASONS = list(range(2015, 2027))
DEPTH_SEASON = 2026
SKILL = {'QB', 'RB', 'WR', 'TE', 'FB', 'LWR', 'RWR', 'SWR'}
MIN_UNIVERSE = 300


def norm(s):
    if not s: return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return "".join(c for c in s.lower() if c.isalnum())


def clean(v):
    """nflverse gives NaN for untested drills; those must become null, not 0."""
    if v is None: return None
    if isinstance(v, float) and math.isnan(v): return None
    return v


def load_universe():
    """DELTA's player list, read from the engine itself rather than parsed by regex."""
    if not os.path.exists('delta-engine.js'):
        print('ERROR: delta-engine.js not found. Run from the repo root.'); sys.exit(1)
    js = ("const fs=require('fs');"
          "const src=fs.readFileSync('delta-engine.js','utf8');"
          "const sb={console,setTimeout,Date,Math,JSON,Promise,URLSearchParams,"
          "location:{search:''},fetch:async()=>({ok:false}),"
          "localStorage:{getItem:()=>null,setItem:()=>{}},"
          "document:{getElementById:()=>null,createElement:()=>({style:{}}),"
          "body:{appendChild:()=>{}},querySelectorAll:()=>[]}};"
          "sb.window=sb;sb.globalThis=sb;require('vm').createContext(sb);"
          "require('vm').runInContext(src+';globalThis.__U__=RAW.map(p=>({n:p.n,pos:p.p,t:p.t}));',sb);"
          "process.stdout.write(JSON.stringify(sb.__U__));")
    try:
        out = subprocess.run(['node', '-e', js], capture_output=True, text=True, timeout=120)
        if out.returncode != 0:
            print('ERROR reading RAW from delta-engine.js:', out.stderr[:300]); sys.exit(1)
        return json.loads(out.stdout)
    except FileNotFoundError:
        print('ERROR: node not available; needed to read RAW from the engine.'); sys.exit(1)


def main():
    args = sys.argv[1:]
    dry, confirm = '--dry-run' in args, '--confirm' in args
    only = None
    if '--only' in args: only = args[args.index('--only') + 1].lower()
    if not dry and not confirm:
        print("REFUSED — this run would write data/combine.json and data/depth-charts.json.")
        print("Add --confirm to write, or --dry-run to rehearse.\n")
        print("Usage: python3 scripts/fetch-prospect-context.py --confirm [--only depth|combine]")
        sys.exit(2)
    if dry and confirm:
        print("Pass either --dry-run or --confirm, not both."); sys.exit(2)
    try:
        import nflreadpy as nfl
    except ImportError:
        print("ERROR: pip install nflreadpy"); sys.exit(1)

    print('=' * 74)
    print('DELTA — FETCH PROSPECT CONTEXT' + ('   (DRY RUN)' if dry else ''))
    print('Display context only. Feeds no score, projection, verdict or ledger.')
    print('=' * 74)

    universe = load_universe()
    if len(universe) < MIN_UNIVERSE:
        print(f'ERROR: only {len(universe)} players read from RAW (expected >= {MIN_UNIVERSE}).')
        sys.exit(1)
    want = {norm(p['n']): p for p in universe}
    print(f'DELTA universe: {len(universe)} players')

    # ── combine ──────────────────────────────────────────────────────────────
    if only in (None, 'combine'):
        print(f'\nCOMBINE  seasons {COMBINE_SEASONS[0]}-{COMBINE_SEASONS[-1]}')
        df = nfl.load_combine(seasons=COMBINE_SEASONS)
        rows = df.to_dicts()
        out, drills = {}, 0
        for r in rows:
            k = norm(r.get('player_name'))
            if k not in want: continue
            rec = {kk: clean(r.get(kk)) for kk in
                   ('ht', 'wt', 'forty', 'bench', 'vertical', 'broad_jump', 'cone', 'shuttle')}
            rec = {kk: vv for kk, vv in rec.items() if vv is not None}
            if not rec: continue
            rec['season'] = r.get('season')
            rec['school'] = r.get('school')
            prev = out.get(want[k]['n'])
            # keep the most complete row if a player somehow appears twice
            if prev is None or len(rec) > len(prev): out[want[k]['n']] = rec
            drills += sum(1 for kk in ('forty','bench','vertical','broad_jump','cone','shuttle') if kk in rec)
        print(f'  matched {len(out)} of {len(universe)} DELTA players · {drills} drill results')
        have40 = sum(1 for v in out.values() if 'forty' in v)
        print(f'  with a forty: {have40} · measurements only (no drills): {len(out)-have40}')
        combine_payload = {
            'generated': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'seasons': [COMBINE_SEASONS[0], COMBINE_SEASONS[-1]],
            'note': ('NFL combine testing, nflverse load_combine, restricted to DELTA players. '
                     'STATIC — re-run only when a new class tests. Display only: feeds no score, '
                     'projection, verdict or ledger. A missing drill means untested, not zero.'),
            'players': out,
        }
    else:
        combine_payload = None

    # ── depth charts ─────────────────────────────────────────────────────────
    if only in (None, 'depth'):
        print(f'\nDEPTH CHARTS  season {DEPTH_SEASON}')
        df = nfl.load_depth_charts(seasons=[DEPTH_SEASON])
        rows = df.to_dicts()
        if not rows:
            print('  no rows returned — leaving the existing file alone'); depth_payload = None
        else:
            latest = max(r['dt'] for r in rows if r.get('dt'))
            cur = [r for r in rows if r.get('dt') == latest and (r.get('pos_abb') or '') in SKILL]
            print(f'  snapshot {latest} · {len(cur)} offensive skill rows')
            # Two shapes. `players` says which room a tracked player belongs to. `rooms`
            # holds the WHOLE room, in listed order, including players DELTA does not
            # track — because the useful question for a rookie is "who else is here",
            # and a veteran blocking him may well be outside our universe.
            groups = {}
            for r in cur:
                groups.setdefault((r.get('team'), r.get('pos_abb')), []).append(r)
            out, rooms = {}, {}
            for (team, slot), lst in groups.items():
                lst.sort(key=lambda r: (r.get('pos_rank') or 99))
                names = []
                for r in lst:
                    nm = r.get('player_name')
                    if nm and nm not in names: names.append(nm)
                rooms[f'{team}|{slot}'] = names
                for r in lst:
                    k = norm(r.get('player_name'))
                    if k not in want: continue
                    rank = r.get('pos_rank') or 99
                    prev = out.get(want[k]['n'])
                    if prev is not None and prev['rank'] <= rank: continue
                    out[want[k]['n']] = {'team': team, 'slot': slot, 'rank': rank,
                                         'name': r.get('player_name')}
            print(f'  matched {len(out)} of {len(universe)} DELTA players · {len(rooms)} position rooms')
            avg = sum(len(v) for v in rooms.values()) / max(1, len(rooms))
            print(f'  average room size: {avg:.1f} players')
            depth_payload = {
                'generated': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'snapshot': latest, 'season': DEPTH_SEASON,
                'note': ('Offensive skill depth chart, nflverse load_depth_charts. `players` maps a '
                         'DELTA player to his room; `rooms` holds every player in that room in listed '
                         'order, including untracked ones. VOLATILE — a camp snapshot, not a settled '
                         'hierarchy. Display only: feeds no score, projection, verdict or ledger.'),
                'players': out, 'rooms': rooms,
            }
    else:
        depth_payload = None

    print()
    if dry:
        if combine_payload: print(f'DRY RUN — would write {COMBINE_OUT} ({len(json.dumps(combine_payload))//1024} KB)')
        if depth_payload:   print(f'DRY RUN — would write {DEPTH_OUT} ({len(json.dumps(depth_payload))//1024} KB)')
    else:
        for path, payload in ((COMBINE_OUT, combine_payload), (DEPTH_OUT, depth_payload)):
            if payload is None: continue
            body = json.dumps(payload, separators=(',', ':'))
            with open(path + '.tmp', 'w') as f: f.write(body)
            os.replace(path + '.tmp', path)
            print(f'WROTE {path}  ({len(body)//1024} KB)')
    print('=' * 74)


if __name__ == '__main__':
    main()
