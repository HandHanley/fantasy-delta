#!/usr/bin/env python3
"""build-mock-draft-pool.py - the player pool for the Mock Draft tab (23-24 Oct 2026, owner).

Writes data/mock-draft-<class>.json: one rookie class, each player with a market value
taken on a fixed day (for 2026: 26 Apr 2026, the morning of the owner's league's rookie
draft), so bots draft the way the market priced the class at the time. Values are
FantasyCalc's 12-team superflex values from DELTA's own nightly archive of
data/market-values.json (git history since 19 Apr 2026).

Names are DELTA's (RAW in delta-engine.js) where the player is in DELTA, so the page's
DELTA lens can find him; matching is by Sleeper id, then a normalized name.

Usage:
  python3 scripts/build-mock-draft-pool.py --class 2026 --market <market-values.json at that date> \
      --date 2026-04-26 --names <file with one rookie name per line> [--extra-sleeper-draft <fixture json>]
"""
import argparse, json, re, unicodedata, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

def norm(n):
    n = unicodedata.normalize('NFD', n)
    n = ''.join(c for c in n if unicodedata.category(c) != 'Mn').lower()
    n = re.sub(r"[.'’\-]", "", n)
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", n)
    return re.sub(r"\s+", " ", n).strip()

def raw_names():
    src = (ROOT / 'delta-engine.js').read_text()
    out = {}
    for m in re.finditer(r"\{n:'((?:[^'\\]|\\.)*)',t:'[A-Z]*',p:'(QB|RB|WR|TE)'", src):
        n = m.group(1).replace("\\'", "'")
        out[norm(n)] = (n, m.group(2))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--class', dest='klass', type=int, required=True)
    ap.add_argument('--market', required=True)
    ap.add_argument('--date', required=True)
    ap.add_argument('--names', required=True, help='one rookie per line: Name|POS')
    ap.add_argument('--extra-sleeper-draft', help='league history fixture; its rookie-draft picks join the pool')
    a = ap.parse_args()

    mk = json.load(open(a.market))
    vals = mk.get('values')
    if not isinstance(vals, dict):
        sys.exit('market file is not the single-format layout this builder reads (values{name:{value,...}})')
    by_sid = {str(e.get('sleeperId')): (n, e) for n, e in vals.items() if isinstance(e, dict) and e.get('sleeperId')}
    by_norm = {norm(n): (n, e) for n, e in vals.items() if isinstance(e, dict)}
    raw = raw_names()

    pool = {}
    def add(name, pos, sid=None):
        k = norm(name)
        hit = (by_sid.get(str(sid)) if sid else None) or by_norm.get(k)
        dn, dp = raw.get(k, (name, pos))
        v = int(hit[1]['value']) if hit else 0
        if k in pool:
            if v and not pool[k]['v']: pool[k]['v'] = v
            return
        pool[k] = {'n': dn, 'pos': dp or pos, 'v': v, 'delta': k in raw}

    for line in open(a.names):
        line = line.strip()
        if not line: continue
        n, p = line.split('|')
        add(n, p)
    if a.extra_sleeper_draft:
        fx = json.load(open(a.extra_sleeper_draft))
        for d in fx.get('drafts', []):
            for pk in d.get('picks', []):
                if pk.get('pos') in ('QB', 'RB', 'WR', 'TE'):
                    add(pk['name'], pk['pos'], pk.get('player_id'))

    players = sorted(pool.values(), key=lambda x: (-x['v'], x['n']))
    out = {
        'class': a.klass,
        'priced': a.date,
        'source': f"FantasyCalc {mk.get('format', '')}, fetched {mk.get('fetchedAt', '')[:16]} UTC, from DELTA's nightly archive",
        'note': 'Market values as of the priced date. Bots draft from these; the DELTA lens reads the live engine.',
        'players': players,
    }
    dest = ROOT / 'data' / f'mock-draft-{a.klass}.json'
    dest.write_text(json.dumps(out, separators=(',', ':')))
    priced = sum(1 for p in players if p['v'] > 0)
    print(f'[MOCK] {dest.relative_to(ROOT)}: {len(players)} players, {priced} with a market value, '
          f'{sum(1 for p in players if p["delta"])} in DELTA')
    if priced < 30: sys.exit('[MOCK] fewer than 30 priced players - refusing to call this a pool')

if __name__ == '__main__':
    main()
