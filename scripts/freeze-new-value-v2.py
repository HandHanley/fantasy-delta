#!/usr/bin/env python3
"""
DELTA — NEW VALUE MID-SEASON FREEZE, VERSION 2 (26 Nov 2026). Rules: docs/LEDGER-NEW-VALUE-MIDSEASON-2026.md (§9 for
version 2), committed before this file was first run. Version 1 (freeze-2026-nv-midseason.json) was withdrawn before
any outcome and is never touched.

Writes data/freeze-2026-nv-midseason-v2.json ONCE. Refuses to overwrite it. Every input is checked byte for byte against
the exact commit it came from before anything is written:
  - New Value:      data/new-value.json at NV_COMMIT (the New Value Weekly run of 26 Nov 2026, built from NV_BUILT_FROM)
  - Season-enders:  data/injury-overrides.json at INJ_COMMIT, kept verbatim (no buy/sell call on them, ledger §9)
  - FantasyCalc:    data/market-values.json at FC_COMMIT, the "12|sf" list kept verbatim
  - KeepTradeCut:   github.com/dachhack/stathead public/data/ktc_rankings_superflex.json at KTC_COMMIT. FINGERPRINT
                    ONLY in the public file (KeepTradeCut's terms bar using its data on another website). The exact
                    bytes go, gzipped and base64-encoded, to --ktc-private for the owner's private Claude Project.

    python scripts/freeze-new-value-v2.py (--ktc-repo /path/to/stathead --ktc-commit SHA --ktc-private OUT | --no-ktc REASON) [--confirm]

Without --confirm it checks everything and prints the headline, writing nothing.
"""
import argparse, base64, datetime as dt, gzip, hashlib, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'freeze-2026-nv-midseason-v2.json')
PREREG = 'docs/LEDGER-NEW-VALUE-MIDSEASON-2026.md'
NV_PATH, NV_COMMIT, NV_BUILT_FROM, NV_RUN = 'data/new-value.json', '38e7d331f8283cd4bf09d1e1299adcf0ccad2a4d', '4b3bd4bdad43dacb9cea53511c05b9b3ebb7dd6c', 45842700859
FC_PATH, FC_COMMIT, FC_KEY = 'data/market-values.json', '6d4cb120addb5838c22d975f9f3cd6abe8937853', '12|sf'   # last capture before week 12
INJ_PATH, INJ_COMMIT = 'data/injury-overrides.json', 'bee8a2fd20256e45cba63eb2ac78a252f084bd85'
KTC_REPO, KTC_PATH = 'github.com/dachhack/stathead', 'public/data/ktc_rankings_superflex.json'
WEEK12_FIRST_KICKOFF_UTC = '2026-11-26T01:00:00Z'   # GB at LA, Wed 25 Nov 20:00 ET


def git(repo, *args):
    return subprocess.run(['git', '-C', repo, *args], check=True, capture_output=True).stdout


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ktc-repo'); ap.add_argument('--ktc-commit'); ap.add_argument('--ktc-private'); ap.add_argument('--no-ktc')
    ap.add_argument('--confirm', action='store_true')
    a = ap.parse_args()
    if os.path.exists(OUT):
        sys.exit(f'REFUSED: {OUT} already exists. The freeze is written once and never regenerated.')

    # New Value: the committed bytes, and the working copy must be the same bytes
    nv_b = git(ROOT, 'show', f'{NV_COMMIT}:{NV_PATH}')
    assert open(os.path.join(ROOT, NV_PATH), 'rb').read() == nv_b, 'working new-value.json differs from the frozen commit'
    nv = json.loads(nv_b)
    assert nv['meta']['through_week'] == 11 and nv['meta']['season'] == 2026 and len(nv['players']) == 642, nv['meta']
    assert a.no_ktc or (a.ktc_repo and a.ktc_commit and a.ktc_private), 'give the KTC repo, commit and private path, or --no-ktc'
    inj_b = git(ROOT, 'show', f'{INJ_COMMIT}:{INJ_PATH}')
    assert open(os.path.join(ROOT, INJ_PATH), 'rb').read() == inj_b, 'working injury-overrides.json differs from its commit'
    inj = json.loads(inj_b)
    built = git(ROOT, 'log', '-1', '--format=%cI', NV_COMMIT).decode().strip()

    # FantasyCalc: the committed file, 12-team superflex list verbatim
    fc_b = git(ROOT, 'show', f'{FC_COMMIT}:{FC_PATH}')
    fc = json.loads(fc_b)
    fc_sf = fc['settings'][FC_KEY]
    assert fc['ppr'] == 1 and len(fc_sf) >= 300, (fc['ppr'], len(fc_sf))

    # KeepTradeCut: the upstream commit's bytes, upstream commit date as the third-party timestamp
    if a.no_ktc:
        ktc_b = None; ktc_sec = {'publisher': 'KeepTradeCut (keeptradecut.com)', 'captured': False, 'reason': a.no_ktc}
    else:
        KTC_COMMIT = a.ktc_commit
        ktc_b = git(a.ktc_repo, 'show', f'{KTC_COMMIT}:{KTC_PATH}')
        url = git(a.ktc_repo, 'remote', 'get-url', 'origin').decode().strip().lower()
        assert url.rstrip('/').endswith('dachhack/stathead'), url
        ktc_date = git(a.ktc_repo, 'log', '-1', '--format=%cI', KTC_COMMIT).decode().strip()
        ktc_blob = git(a.ktc_repo, 'rev-parse', f'{KTC_COMMIT}:{KTC_PATH}').decode().strip()
        ktc = json.loads(ktc_b)
        assert isinstance(ktc, list) and len(ktc) >= 300 and all('superflexValue' in r for r in ktc), len(ktc)
        ktc_sec = {'publisher': 'KeepTradeCut (keeptradecut.com), via the dachhack/stathead public archive', 'captured': True,
                   'repo': KTC_REPO, 'path': KTC_PATH, 'commit': KTC_COMMIT, 'commit_date': ktc_date,
                   'git_blob': ktc_blob, 'sha256': sha(ktc_b), 'bytes': len(ktc_b), 'players': len(ktc),
                   'basis': 'superflexValue', 'public_copy': 'FINGERPRINT ONLY. KeepTradeCut\'s terms bar using '
                   'its data on another website. The exact bytes are in the owner\'s private Claude Project as '
                   'claude/freeze-2026-nv-midseason-v2-ktc.json.gz.b64.txt (restore: base64 -d | gunzip; the '
                   'SHA-256 must equal sha256 here).'}

    prereg_commit = git(ROOT, 'log', '-1', '--format=%H %cI', '--', PREREG).decode().strip()
    me = open(os.path.abspath(__file__), 'rb').read()
    freeze = {
        'what': 'DELTA New Value, mid-season freeze, 2026, version 2. Graded by docs/LEDGER-NEW-VALUE-MIDSEASON-2026.md '
                '(§9: version 2 rules). Never edited, regenerated or corrected.',
        'frozen_utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'preregistration': {'path': PREREG, 'commit_and_date': prereg_commit},
        'claim': 'Value over the next three seasons (2027-2029), 12-team superflex, full PPR: FV = sum k=1..3 of '
                 '0.9^(k-1) x max(0, points in 2026+k - starter line), lines QB24/RB34/WR48/TE14.',
        'timing_note': f'A true 11-week sample (Steve, 26 Nov). New Value runs through week 11: no week-12 game is in it '
                       '(values match a build from data with no week-12 rows). FantasyCalc is its last capture before week '
                       f'12 began ({WEEK12_FIRST_KICKOFF_UTC}, GB at LA). Test A counts no 2026 games.',
        'new_value': {'path': NV_PATH, 'commit': NV_COMMIT, 'commit_date': built, 'built_from_commit': NV_BUILT_FROM,
                      'workflow_run': NV_RUN, 'sha256': sha(nv_b), 'bytes': len(nv_b),
                      'build_script_sha256_at_built_from': sha(git(ROOT, 'show', f'{NV_BUILT_FROM}:study/new_value_weekly.py')),
                      'content': nv},
        'fantasycalc': {'publisher': 'FantasyCalc (fantasycalc.com)', 'path': FC_PATH, 'commit': FC_COMMIT,
                        'file_sha256': sha(fc_b), 'polled_utc': fc.get('fetched'), 'ppr': fc['ppr'], 'setting': FC_KEY,
                        'players': len(fc_sf), 'values': fc_sf},
        'keeptradecut': ktc_sec,
        'season_enders': {'path': INJ_PATH, 'commit': INJ_COMMIT, 'sha256': sha(inj_b), 'content': inj},
        'version': 'Version 2. Version 1 (data/freeze-2026-nv-midseason.json) was withdrawn before any outcome (ledger §8); it stays untouched and is reported beside this at grading.',
        'attribution': ['FantasyCalc values: fantasycalc.com', 'KeepTradeCut values: keeptradecut.com (not reproduced here)'],
        'freeze_script_sha256': sha(me),
    }
    head = (f"New Value {len(nv['players'])} players (through week {nv['meta']['through_week']}, sha {sha(nv_b)[:16]}) | "
            f"FantasyCalc {len(fc_sf)} (polled {fc.get('fetched')}) | KeepTradeCut " +
            (f"{ktc_sec['players']} (upstream {ktc_sec['commit_date']})" if ktc_b else f"NOT CAPTURED ({a.no_ktc})") +
            f" | season-enders {len([k for k in inj if not k.startswith('_')])} | pre-registration {prereg_commit}")
    print(head)
    if not a.confirm:
        print('dry run: nothing written'); return
    data = json.dumps(freeze, indent=1, ensure_ascii=False).encode()
    with open(OUT, 'xb') as f: f.write(data)
    print(f'wrote {OUT}: {len(data):,} bytes, sha256 {sha(data)}')
    if ktc_b:
        with open(a.ktc_private, 'w') as f: f.write(base64.b64encode(gzip.compress(ktc_b, mtime=0)).decode())
        back = gzip.decompress(base64.b64decode(open(a.ktc_private).read()))
        assert sha(back) == sha(ktc_b), 'private KTC copy does not restore to the same bytes'
        print(f'wrote {a.ktc_private} (restores to sha256 {sha(back)})')


if __name__ == '__main__':
    main()
