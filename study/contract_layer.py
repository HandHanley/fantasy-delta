"""Contract Security layer for the Own Value Scale display build (docs/PREREG-contract-security.md §11).

Measured on deals a team signed: contract year x0.77, 1 year left x0.95, 2+ years left x1.08. Rookie deals, free agents
and anyone not in the table get no layer (x1.00). Years left count from NEXT season, the first season of the value's
three-season window (a week-W value of season Y covers Y+1..Y+3; the study measured status at that first kickoff).
A deal ending this season (`expiring`) has no measured group: `expiring='contract_year'` treats it as x0.77,
`expiring='none'` leaves it at x1.00 until he signs. Display only; not part of any locked test.
"""
import json, re

LAYER = {0: 0.7692947141173002, 1: 0.9547539143952655, 2: 1.0781335965973162}   # ovs_contract_security_results.json
TEAM_SIGNED = {'veteran', 'extension', 'franchise_tag', 'transition_tag', 'rfa_tender', 'practice_squad', 'rookie_option'}


def norm(s):
    s = re.sub(r"[.'’]", '', str(s).lower()); s = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', s); return re.sub(r'[^a-z]', '', s)


def load(path):
    P = json.load(open(path))['players']
    out = {}
    for name, p in P.items():
        k = norm(name)
        out[k] = None if k in out else p                                    # a name shared by two players: no layer
    return out


def factor(name, table, season, expiring='contract_year'):
    """(multiplier, label) for one player in the week-W build of `season`."""
    p = table.get(norm(name))
    if p is None: return 1.0, 'not in table'
    if p.get('kind') not in TEAM_SIGNED or p.get('end') is None: return 1.0, p.get('kind') or 'none'
    left = int(p['end']) - (season + 1)
    if left < 0:
        return (LAYER[0], 'expiring') if expiring == 'contract_year' else (1.0, 'expiring')
    return LAYER[min(left, 2)], ['contract year', '1 year left', '2+ years left'][min(left, 2)]
