import re, json, sys, numpy as np, pandas as pd
def norm(s):
    s = re.sub(r"[.'’]", '', str(s).lower()); s = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', s); return re.sub(r'[^a-z]', '', s)
pp = pd.read_csv('/home/claude/nfl/players.csv', low_memory=False)
alias = {}
for r in pp.itertuples():
    nm = {r.display_name} | {f'{f} {r.last_name}' for f in (r.first_name, r.football_name, r.common_first_name) if isinstance(f, str)}
    alias[r.gsis_id] = {norm(x) for x in nm if isinstance(x, str)}
L = pd.DataFrame(json.load(open('/home/claude/vote/pool_all.json')))
def ranked(lines):
    V = pd.read_pickle(f'/tmp/ssp/vals_{lines}.pkl')
    idx = {}
    for i, (nm, k, p) in enumerate(zip(V.name, V.key, V.pos)):
        for n in {norm(nm)} | alias.get(k, set()): idx.setdefault((n, p), set()).add(i)
    L2 = L.copy(); L2['i'] = [next(iter(idx[(norm(n), p)])) if len(idx.get((norm(n), p), ())) == 1 else None for n, p in zip(L2.n, L2.pos)]
    M = L2[L2.i.notna()].copy(); M['i'] = M.i.astype(int)
    for c in ('new_value', 'games26', 'rookie', 'age', 'contract'): M[c] = V[c].values[M.i]
    M['new_rank'] = M.new_value.rank(ascending=False, method='min').astype(int)
    return M
old, new = ranked('old'), ranked('new')
print('matched', len(old), 'of', len(L))
chk = {'Omar Cooper': (3797, 47), 'Justin Jefferson': (2064, 80), 'Brock Bowers': (4650, 36), 'Deshaun Watson': (3168, 58),
       'Derrick Henry': (317, 212), 'Christian McCaffrey': (1856, 90), 'Jonnu Smith': (0, 353), 'Josh Allen': (9810, 2)}
O = old.set_index('n')
for n, (v, rk) in chk.items():
    print(n, 'v5', v, rk, '| rebuilt', int(O.new_value[n]), int(O.new_rank[n]))
old.to_pickle('/tmp/ssp/rank_old.pkl'); new.to_pickle('/tmp/ssp/rank_new.pkl')
