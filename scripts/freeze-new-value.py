#!/usr/bin/env python3
"""
DELTA — NEW VALUE MID-SEASON FREEZE (13 Nov 2026). Rules: docs/LEDGER-NEW-VALUE-MIDSEASON-2026.md, committed before
this file was first run.

Writes data/freeze-2026-nv-midseason.json ONCE. Refuses to overwrite it. Every input is checked byte for byte against
the exact commit it came from before anything is written:
  - New Value:      data/new-value.json at NV_COMMIT (the New Value Weekly run of 13 Nov 2026, built from NV_BUILT_FROM)
  - FantasyCalc:    data/market-values.json at FC_COMMIT, the "12|sf" list kept verbatim
  - KeepTradeCut:   github.com/dachhack/stathead public/data/ktc_rankings_superflex.json at KTC_COMMIT. FINGERPRINT
                    ONLY in the public file (KeepTradeCut's terms bar using its data on another website). The exact
                    bytes go, gzipped and base64-encoded, to --ktc-private for the owner's private Claude Project.

    python scripts/freeze-new-value.py --ktc-repo /path/to/stathead --ktc-private OUT.gz.b64.txt [--confirm]

Without --confirm it checks everything and prints the headline, writing nothing.
"""
import argparse, base64, datetime as dt, gzip, hashlib, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'freeze-2026-nv-midseason.json')
PREREG = 'docs/LEDGER-NEW-VALUE-MIDSEASON-2026.md'
NV_PATH, NV_COMMIT, NV_BUILT_FROM, NV_RUN = 'data/new-value.json', '3d6fd58', '2c1a869419a688de697141b531bca78501e47919', 43479685276
FC_PATH, FC_COMMIT, FC_KEY = 'data/market-values.json', '14ee8519d2c25e3b95bd5d7710ac331f5f9def12', '12|sf'
KTC_REPO, KTC_PATH, KTC_COMMIT = 'github.com/dachhack/stathead', 'public/data/ktc_rankings_superflex.json', '557cc8aefd7e7dc675d8757895aa0ce6b2f0bd90'


def git(repo, *args):
    return subprocess.run(['git', '-C', repo, *args], check=True, capture_output=True).stdout


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ktc-repo', required=True); ap.add_argument('--ktc-private', required=True)
    ap.add_argument('--confirm', action='store_true')
    a = ap.parse_args()
    if os.path.exists(OUT):
        sys.exit(f'REFUSED: {OUT} already exists. The freeze is written once and never regenerated.')

    # New Value: the committed bytes, and the working copy must be the same bytes
    nv_b = git(ROOT, 'show', f'{NV_COMMIT}:{NV_PATH}')
    assert open(os.path.join(ROOT, NV_PATH), 'rb').read() == nv_b, 'working new-value.json differs from the frozen commit'
    nv = json.loads(nv_b)
    assert nv['meta']['through_week'] == 9 and nv['meta']['season'] == 2026 and len(nv['players']) == 884, nv['meta']
    built = git(ROOT, 'log', '-1', '--format=%cI', NV_COMMIT).decode().strip()

    # FantasyCalc: the committed file, 12-team superflex list verbatim
    fc_b = git(ROOT, 'show', f'{FC_COMMIT}:{FC_PATH}')
    fc = json.loads(fc_b)
    fc_sf = fc['settings'][FC_KEY]
    assert fc['ppr'] == 1 and len(fc_sf) >= 300, (fc['ppr'], len(fc_sf))

    # KeepTradeCut: the upstream commit's bytes, upstream commit date as the third-party timestamp
    ktc_b = git(a.ktc_repo, 'show', f'{KTC_COMMIT}:{KTC_PATH}')
    url = git(a.ktc_repo, 'remote', 'get-url', 'origin').decode().strip().lower()
    assert url.rstrip('/').endswith('dachhack/stathead'), url
    ktc_date = git(a.ktc_repo, 'log', '-1', '--format=%cI', KTC_COMMIT).decode().strip()
    ktc_blob = git(a.ktc_repo, 'rev-parse', f'{KTC_COMMIT}:{KTC_PATH}').decode().strip()
    ktc = json.loads(ktc_b)
    assert isinstance(ktc, list) and len(ktc) >= 300 and all('superflexValue' in r for r in ktc), len(ktc)

    prereg_commit = git(ROOT, 'log', '-1', '--format=%H %cI', '--', PREREG).decode().strip()
    me = open(os.path.abspath(__file__), 'rb').read()
    freeze = {
        'what': 'DELTA New Value, mid-season freeze, 2026. Graded by docs/LEDGER-NEW-VALUE-MIDSEASON-2026.md. Never '
                'edited, regenerated or corrected.',
        'frozen_utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'preregistration': {'path': PREREG, 'commit_and_date': prereg_commit},
        'claim': 'Value over the next three seasons (2027-2029), 12-team superflex, full PPR: FV = sum k=1..3 of '
                 '0.9^(k-1) x max(0, points in 2026+k - starter line), lines QB24/RB34/WR48/TE14.',
        'timing_note': 'Week 10 Thursday (12 Nov) had been played before both market captures; New Value runs through '
                       'week 9 and has not seen it. Test A counts no 2026 games.',
        'new_value': {'path': NV_PATH, 'commit': NV_COMMIT, 'commit_date': built, 'built_from_commit': NV_BUILT_FROM,
                      'workflow_run': NV_RUN, 'sha256': sha(nv_b), 'bytes': len(nv_b),
                      'build_script_sha256_at_built_from': sha(git(ROOT, 'show', f'{NV_BUILT_FROM}:study/new_value_weekly.py')),
                      'content': nv},
        'fantasycalc': {'publisher': 'FantasyCalc (fantasycalc.com)', 'path': FC_PATH, 'commit': FC_COMMIT,
                        'file_sha256': sha(fc_b), 'polled_utc': fc.get('fetched'), 'ppr': fc['ppr'], 'setting': FC_KEY,
                        'players': len(fc_sf), 'values': fc_sf},
        'keeptradecut': {'publisher': 'KeepTradeCut (keeptradecut.com), via the dachhack/stathead public archive',
                         'repo': KTC_REPO, 'path': KTC_PATH, 'commit': KTC_COMMIT, 'commit_date': ktc_date,
                         'git_blob': ktc_blob, 'sha256': sha(ktc_b), 'bytes': len(ktc_b), 'players': len(ktc),
                         'basis': 'superflexValue', 'public_copy': 'FINGERPRINT ONLY. KeepTradeCut\'s terms bar using '
                         'its data on another website. The exact bytes are in the owner\'s private Claude Project as '
                         'claude/freeze-2026-nv-midseason-ktc.json.gz.b64.txt (restore: base64 -d | gunzip; the '
                         'SHA-256 must equal sha256 here). Anyone can re-fetch the original from the repo and commit above.'},
        'attribution': ['FantasyCalc values: fantasycalc.com', 'KeepTradeCut values: keeptradecut.com (not reproduced here)'],
        'freeze_script_sha256': sha(me),
    }
    head = (f"New Value {len(nv['players'])} players (through week {nv['meta']['through_week']}, sha {sha(nv_b)[:16]}) | "
            f"FantasyCalc {len(fc_sf)} (polled {fc.get('fetched')}) | KeepTradeCut {len(ktc)} (upstream {ktc_date}) | "
            f"pre-registration {prereg_commit}")
    print(head)
    if not a.confirm:
        print('dry run: nothing written'); return
    data = json.dumps(freeze, indent=1, ensure_ascii=False).encode()
    with open(OUT, 'xb') as f: f.write(data)
    with open(a.ktc_private, 'w') as f: f.write(base64.b64encode(gzip.compress(ktc_b, mtime=0)).decode())
    back = gzip.decompress(base64.b64decode(open(a.ktc_private).read()))
    assert sha(back) == sha(ktc_b), 'private KTC copy does not restore to the same bytes'
    print(f'wrote {OUT}: {len(data):,} bytes, sha256 {sha(data)}')
    print(f'wrote {a.ktc_private} (restores to sha256 {sha(back)})')


if __name__ == '__main__':
    main()
