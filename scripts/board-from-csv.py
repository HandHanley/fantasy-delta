#!/usr/bin/env python3
"""
DELTA — CONSENSUS BOARD FROM A CSV (24 Oct 2026, owner)

Turns a downloaded consensus big board CSV (Pro Football Network's "Industry Consensus" export
is the one this was written for) into data/big-board-raw.txt, which build-devy-board.py then
builds into data/devy-board.json exactly as it does a pasted board.

WHAT IT KEEPS, AND WHY ONLY THAT
  Skill positions only (QB, RB, WR, TE), and for each only the overall consensus rank, name,
  position and school. The CSV also carries each outlet's own rank (PFN, CBS, ESPN, NBC, ...),
  an average and a mock ADP; none of that is used, and none of it goes into the repo. The
  site's terms could not be read when this was written, so DELTA records the publicly stated
  consensus rank of the players it covers and nothing more of their table.

The rank kept is the board's OWN overall rank (its "Rank" column), not a position rank and not
a re-sort: the Mock Draft turns overall rank into fantasy value by position, so the overall
number is the one that matters.

Usage:
  python3 scripts/board-from-csv.py <file.csv> --source "PFN Industry Consensus" --date 2026-10-24
  python3 scripts/board-from-csv.py <file.csv> --source "..." --date ... --out data/big-board-raw.txt
Without --out it prints to the screen. The output's '# source:' and '# board date:' lines are
read by build-devy-board.py (a change of source restarts week-over-week movement).
"""
import csv, sys, re, datetime

SKILL = ('QB', 'RB', 'WR', 'TE')
MIN_SKILL = 20


def main():
    a = sys.argv[1:]
    if not a or a[0].startswith('--'):
        print(__doc__); sys.exit(2)
    path = a[0]
    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else d
    source, date, out = opt('--source'), opt('--date'), opt('--out')
    if not source or not date:
        sys.exit('ERROR: --source and --date are both required (they label the board on the site).')
    try:
        datetime.date.fromisoformat(date)
    except ValueError:
        sys.exit(f'ERROR: --date must look like 2026-10-24, got {date!r}')

    with open(path, encoding='utf-8-sig', newline='') as f:
        rd = csv.DictReader(f)
        cols = {c.strip().lower(): c for c in (rd.fieldnames or [])}
        need = ('rank', 'name', 'position', 'school')
        miss = [c for c in need if c not in cols]
        if miss:
            sys.exit(f'ERROR: the CSV has no {", ".join(miss)} column. Columns found: {rd.fieldnames}')
        rows, seen_ranks = [], set()
        for r in rd:
            pos = (r[cols['position']] or '').strip().upper()
            rank_s = (r[cols['rank']] or '').strip()
            if not re.fullmatch(r'\d{1,3}', rank_s):
                continue
            rank = int(rank_s)
            if rank in seen_ranks:
                sys.exit(f'ERROR: rank {rank} appears twice — this does not look like one board.')
            seen_ranks.add(rank)
            if pos not in SKILL:
                continue
            name = re.sub(r'\s+', ' ', (r[cols['name']] or '').strip())
            school = re.sub(r'\s+', ' ', (r[cols['school']] or '').strip())
            if not name or ',' in name or '|' in name:
                sys.exit(f'ERROR: rank {rank}: a name the board parser cannot read safely: {name!r}')
            rows.append((rank, name, pos, school.replace('|', '/')))
    if len(rows) < MIN_SKILL:
        sys.exit(f'ERROR: only {len(rows)} QB/RB/WR/TE rows found (expected at least {MIN_SKILL}). Nothing written.')
    rows.sort()
    lines = [f'# source: {source}', f'# board date: {date}',
             f'# Skill positions only, from the board\'s CSV; the number is its overall rank '
             f'({len(seen_ranks)} players ranked, {len(rows)} at QB/RB/WR/TE).']
    lines += [f'{rk}. {n}, {p}, {sc}' for rk, n, p, sc in rows]
    text = '\n'.join(lines) + '\n'
    if out:
        with open(out, 'w', encoding='utf-8') as f:
            f.write(text)
        by = {}
        for _, _, p, _ in rows: by[p] = by.get(p, 0) + 1
        print(f'WROTE {out}: {len(rows)} skill players of {len(seen_ranks)} ranked '
              f'({", ".join(f"{k} {by.get(k, 0)}" for k in SKILL)}); deepest rank {max(seen_ranks)}')
    else:
        sys.stdout.write(text)


if __name__ == '__main__':
    main()
