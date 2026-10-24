#!/usr/bin/env python3
"""
DELTA — BUILD DEVY BOARD

Turns a pasted consensus big board into data/devy-board.json.

WHY THIS IS SEMI-MANUAL, AND WILL STAY THAT WAY
  The consensus boards worth reading are somebody's product. NFL Mock Draft Database
  aggregates 800+ sources and sells API access to the result; scraping it would be taking
  the thing they sell, and their terms say so. So DELTA does not fetch the board.

  What it CAN do is remove every other manual step. You paste the board into
  data/big-board-raw.txt, commit, and this script does the parsing, the position filter,
  the tiering, the match against college data, and the week-over-week movement. The human
  step is one paste. Everything after it is automated.

  That also makes the compilation DELTA's own, which is the point: we are recording
  publicly stated projections, not republishing anyone's table.

WHY RAW SNAPSHOTS ARE KEPT
  Each paste is archived to data/board-history/YYYY-MM-DD.txt. Two reasons: git history
  then shows exactly what the board said on any date, and the movement arrows on the page
  come from diffing against the previous snapshot. A riser is only visible if you kept
  what he rose from.

Input format: tolerant. It reads the raw copy-paste from a board page — markdown links,
stray vote counts, blank lines and all. A line is a player when it has a name, a
position and a school; anything else is skipped and reported.

Usage:
  python3 scripts/build-devy-board.py --dry-run
  python3 scripts/build-devy-board.py --confirm
  python3 scripts/build-devy-board.py --confirm --class 2027
"""
import os, re, sys, json, glob, unicodedata, datetime

RAW_IN      = 'data/big-board-raw.txt'
OUT         = 'data/devy-board.json'
HIST_DIR    = 'data/board-history'
SKILL       = {'QB', 'RB', 'WR', 'TE'}
COLLEGE_DIR = 'data'
MIN_PLAYERS = 20          # below this the paste is almost certainly truncated or malformed
NFLMDD      = 'NFL Mock Draft Database'


def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode()
    return ''.join(c for c in s.lower() if c.isalnum())


def loose(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', s)
    return ''.join(c for c in s if c.isalnum())


def tier_of(rank):
    if rank <= 10:  return 'T1'
    if rank <= 32:  return 'T2'
    if rank <= 64:  return 'T3'
    return 'T4'


TIER_LABEL = {'T1': 'Top 10 overall', 'T2': 'Round 1', 'T3': 'Round 2', 'T4': 'Round 3+'}
POS_RE = r'(QB|RB|WR|TE|OT|IOL|OL|C|G|EDGE|DL|DT|DE|LB|ILB|OLB|CB|S|DB|K|P|LS|ATH|FB)'
# Consensus mock-draft slot on the school line: [#1LAC](...consensus-mock-draft...).
MOCK_RE = r'\[#\s*(\d{1,3})\s*([A-Z]{2,3})\]\([^)]*mock-draft'


def parse(text):
    """Pull (rank, name, pos, school) out of a pasted board.

    Markdown-link form, which is what a browser copy-paste produces:
        1
        [Arch Manning](.../arch-manning)
        QB[Texas](.../texas-longhorns)
    Plain form is also accepted:
        1. Arch Manning, QB, Texas
    """
    lines = [l.rstrip() for l in text.splitlines()]
    out, skipped, rank = [], [], None
    consumed = set()          # lines eaten as the position/school of the player above
    for i, ln in enumerate(lines):
        if i in consumed:
            continue
        s = ln.strip()
        if not s or s.startswith('#'):            # blank, or a '# source:' style header line
            continue
        if re.fullmatch(r'\d{1,3}', s):          # a bare number is the board rank
            rank = int(s); continue
        name = None
        mock_pick = mock_team = None
        m = re.match(r'\[([^\]]+)\]\(', s)       # [Name](url)
        if m:
            name = m.group(1).strip()
            pos = school = None
            if i + 1 < len(lines):
                nxt = lines[i + 1].strip()
                pm = re.match(POS_RE + r'\s*\[?([^\]\[(]*)', nxt)
                if pm:
                    pos = pm.group(1)
                    school = (pm.group(2) or '').strip(' ,|')
                    consumed.add(i + 1)           # do not report it as an unparsed line
                    # The same line carries the consensus MOCK slot when he has one:
                    # [#1LAC](.../consensus-mock-draft-2027). Round 1 only, so most rows
                    # have none, and that is the honest answer for them.
                    mm = re.search(MOCK_RE, nxt)
                    if mm:
                        mock_pick, mock_team = int(mm.group(1)), mm.group(2)
            if pos is None:
                continue                          # this was the school link, not the player
        else:
            pm = re.match(r'(?:(\d{1,3})[.)]\s*)?(.+?)[,|]\s*' + POS_RE + r'[,|]\s*(.+)$', s)
            if not pm:
                skipped.append(s[:70]); continue
            if pm.group(1): rank = int(pm.group(1))
            name, pos, school = pm.group(2).strip(), pm.group(3), pm.group(4).strip()
        if not name or rank is None:
            continue
        out.append({'rank': rank, 'n': name, 'pos': pos, 'school': school or None,
                    'mockPick': mock_pick, 'mockTeam': mock_team})
        rank = None
    # keep the best (lowest) rank if a name somehow appears twice
    best = {}
    for r in out:
        k = norm(r['n'])
        if k not in best or r['rank'] < best[k]['rank']: best[k] = r
    return sorted(best.values(), key=lambda r: r['rank']), skipped


def board_meta(text):
    """Where a paste came from. A converted CSV carries '# source:' and '# board date:' header
    lines (scripts/board-from-csv.py writes them); a browser paste from NFL Mock Draft Database
    carries that site's links. Every board before 24 Oct 2026 came from there."""
    meta = {'source': None, 'boardDate': None}
    for ln in text.splitlines():
        m = re.match(r'\s*#\s*(source|board date)\s*:\s*(.+?)\s*$', ln, re.I)
        if m:
            meta['source' if m.group(1).lower() == 'source' else 'boardDate'] = m.group(2)
    if not meta['source'] and 'nflmockdraftdatabase.com' in text:
        meta['source'] = NFLMDD
    return meta


def newest_college_file():
    yrs = []
    for f in glob.glob(os.path.join(COLLEGE_DIR, 'college-players-*.json')):
        m = re.search(r'college-players-(\d{4})\.json$', f)
        if m: yrs.append((int(m.group(1)), f))
    return max(yrs)[1] if yrs else None


def main():
    args = sys.argv[1:]
    dry, confirm = '--dry-run' in args, '--confirm' in args
    draft_class = 2027
    if '--class' in args: draft_class = int(args[args.index('--class') + 1])
    if not dry and not confirm:
        print('REFUSED — this run would rewrite data/devy-board.json.')
        print('Add --confirm to write it, or --dry-run to rehearse.\n')
        print('Usage: python3 scripts/build-devy-board.py --confirm [--class 2027]')
        sys.exit(2)
    if dry and confirm:
        print('Pass either --dry-run or --confirm, not both.'); sys.exit(2)
    if not os.path.exists(RAW_IN):
        print(f'ERROR: {RAW_IN} not found. Paste a consensus big board into it and re-run.')
        sys.exit(1)

    text = open(RAW_IN, encoding='utf-8').read()
    rows, skipped = parse(text)
    print('=' * 74)
    print(f'DELTA — BUILD DEVY BOARD   class {draft_class}' + ('   (DRY RUN)' if dry else ''))
    print('=' * 74)
    print(f'parsed {len(rows)} board entries from {RAW_IN}')
    if skipped:
        print(f'  {len(skipped)} line(s) did not parse (first few):')
        for s in skipped[:5]: print('     ', s)
    # Two guards. A short parse means a truncated paste. More unparsed lines than parsed
    # ones means the format changed and we are reading it wrong — either way, do not
    # overwrite a good board with a bad one.
    if len(rows) < MIN_PLAYERS:
        print(f'\nABORT: only {len(rows)} entries parsed (expected at least {MIN_PLAYERS}).')
        print('The paste looks truncated. Nothing written.')
        sys.exit(1)
    if len(skipped) > len(rows):
        print(f'\nABORT: {len(skipped)} unparsed lines against {len(rows)} parsed.')
        print('The board format has probably changed. Nothing written.')
        sys.exit(1)

    skill = [r for r in rows if r['pos'] in SKILL]
    from collections import Counter
    print(f'  skill-position players: {len(skill)}  ' +
          ' '.join(f'{k}:{v}' for k, v in sorted(Counter(r["pos"] for r in skill).items())))
    print(f'  deepest rank on the board: {max(r["rank"] for r in rows)}')

    # match against the newest college season we hold
    cfile = newest_college_file()
    matched, unmatched = 0, []
    if cfile:
        pool = json.load(open(cfile)).get('players') or []
        idx, idxl = {}, {}
        for p in pool:
            idx.setdefault(norm(p['n']), []).append(p)
            idxl.setdefault(loose(p['n']), []).append(p)
        for r in skill:
            c = ([x for x in idx.get(norm(r['n']), []) if x['pos'] == r['pos']] or
                 [x for x in idxl.get(loose(r['n']), []) if x['pos'] == r['pos']])
            if c: r['cfbName'] = c[0]['n']; matched += 1
            else: r['cfbName'] = None; unmatched.append(f"{r['n']} ({r['pos']}, {r['school']})")
        print(f'  matched to {os.path.basename(cfile)}: {matched}/{len(skill)}')
        if unmatched:
            print('  no college record (the board door in fetch-college.py will pull these in'
                  ' next run, if CFBD has them at all):')
            for u in unmatched: print('     ', u)
    else:
        print('  no college season files found — skipping the match step')

    # movement against the previous snapshot
    meta = board_meta(text)
    print(f"  source: {meta['source'] or 'unknown'}" + (f"  (board date {meta['boardDate']})" if meta['boardDate'] else ''))
    prev, prev_payload = {}, {}
    if os.path.exists(OUT):
        try:
            prev_payload = json.load(open(OUT))
            prev = {norm(k): v.get('rank') for k, v in (prev_payload.get('players') or {}).items()}
        except Exception:
            pass
    # A rank on one site's board is not comparable with a rank on another's, so a change of
    # source starts movement afresh instead of printing arrows that are only the switch.
    prev_source = prev_payload.get('source') or (NFLMDD if prev else None)
    if prev and meta['source'] != prev_source:
        print(f"  board source changed ({prev_source} -> {meta['source']}): movement starts fresh this week")
        prev = {}
    # The NFL team in the consensus MOCK comes only from an NFL Mock Draft Database paste. A
    # board from elsewhere keeps the last ones on file, with their date, rather than dropping them.
    mock_as_of, mock_source = None, None
    if any(r.get('mockPick') for r in skill):
        mock_as_of, mock_source = meta['boardDate'] or datetime.date.today().isoformat(), meta['source']
    elif prev_payload.get('players'):
        pm = {norm(k): v for k, v in prev_payload['players'].items() if v.get('mockPick')}
        for r in skill:
            v = pm.get(norm(r['n']))
            if v: r['mockPick'], r['mockTeam'] = v.get('mockPick'), v.get('mockTeam')
        if pm:
            mock_as_of = prev_payload.get('mockAsOf') or prev_payload.get('generated')
            mock_source = prev_payload.get('mockSource') or NFLMDD
            print(f"  consensus mock slots carried from the previous board ({mock_source}, {mock_as_of}): "
                  f"{sum(1 for r in skill if r.get('mockPick'))} players")
    risers = fallers = new = 0
    for r in skill:
        p = prev.get(norm(r['n']))
        r['prevRank'] = p
        r['move'] = (p - r['rank']) if p else None      # positive = moved up the board
        if p is None: new += 1
        elif r['move'] > 0: risers += 1
        elif r['move'] < 0: fallers += 1
    if prev:
        print(f'  movement vs previous board: {risers} up · {fallers} down · {new} new')

    players = {r['n']: {'rank': r['rank'], 'pos': r['pos'], 'school': r['school'],
                        'tier': tier_of(r['rank']), 'cfbName': r.get('cfbName'),
                        'prevRank': r.get('prevRank'), 'move': r.get('move'),
                        'mockPick': r.get('mockPick'), 'mockTeam': r.get('mockTeam')}
               for r in skill}
    print(f'  consensus mock slot on file for {sum(1 for r in skill if r.get("mockPick"))} of {len(skill)}'
          ' skill players (the mock is one round deep)')
    payload = {
        'generated': datetime.date.today().isoformat(),
        'class': draft_class,
        'source': meta['source'],
        'boardDate': meta['boardDate'],
        'mockSource': mock_source,
        'mockAsOf': mock_as_of,
        'note': ('Consensus big-board position for skill-position prospects, compiled by hand '
                 'from publicly published boards. Stored as a rank plus a coarse tier; the tier '
                 'is what the platform shows, because this far out a tier stays true for weeks '
                 'while an exact rank is stale in days. CONTEXT ONLY — feeds no score, no '
                 'percentile and no ranking, exactly like market value on the NFL side.'),
        'tiers': TIER_LABEL,
        'coverage': {'boardDepth': max(r['rank'] for r in rows),
                     'entriesParsed': len(rows),
                     'skillPlayers': len(skill),
                     'matchedToCollegeData': matched,
                     'unmatched': [u.split(' (')[0] for u in unmatched]},
        'players': players,
    }
    if dry:
        print(f'\nDRY RUN — {OUT} not written.')
    else:
        os.makedirs(HIST_DIR, exist_ok=True)
        snap = os.path.join(HIST_DIR, datetime.date.today().isoformat() + '.txt')
        with open(snap, 'w', encoding='utf-8') as f: f.write(text)
        with open(OUT + '.tmp', 'w') as f: json.dump(payload, f, indent=1)
        os.replace(OUT + '.tmp', OUT)
        print(f'\nWROTE {OUT}  ({len(players)} players)')
        print(f'WROTE {snap}  (raw snapshot, so movement can be computed next time)')
    print('=' * 74)


if __name__ == '__main__':
    main()
