#!/usr/bin/env python3
"""
DELTA — CROWD VALUES FROM THE VOTE PAGE (docs/PREREG-crowd-values.md).

The crowd sets the ORDER (a Bradley-Terry fit to every "would you rather" pick); DELTA's own value curve sets the
PRICE of each spot in line (study/data/crowd-price-list-2026-11-10.json). No market data anywhere.

    python crowd_values.py --simulate                  # how well the method recovers a known order, by vote count
    python crowd_values.py --run vote_picks.csv        # the board from a Supabase export of vote_picks
"""
import argparse, json, os
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, 'out')
ITEMS = os.path.join(HERE, 'data', 'crowd-board-2026-11-10.json')       # the page's 159 items with their slot r
PRICES = os.path.join(HERE, 'data', 'crowd-price-list-2026-11-10.json')  # value of the k-th spot in line
MIN_VOTES, OWNER_CAP, GIMME_MISS, GIMME_MIN, HALF = 30, 0.20, 1 / 3, 3, 0.5
PRIOR = 1.0            # each item plays one pseudo-win and one pseudo-loss against an average item
SPLITS, STEADY = 200, 0.85


def fit(items, a, b, win_a, w, iters=500):
    """Weighted Bradley-Terry strengths (log scale), MM algorithm with the PRIOR pseudo-games. a, b: item indices."""
    n = len(items); s = np.ones(n)
    wins = np.full(n, PRIOR) + np.bincount(np.where(win_a, a, b), weights=w, minlength=n)
    for _ in range(iters):
        d = w / (s[a] + s[b])
        den = np.bincount(a, weights=d, minlength=n) + np.bincount(b, weights=d, minlength=n) + 2 * PRIOR / (s + 1.0)
        new = wins / den; new /= np.exp(np.mean(np.log(new)))
        if np.max(np.abs(np.log(new) - np.log(s))) < 1e-9: s = new; break
        s = new
    return np.log(s)


def weights(df, slot):
    """§2: gimme check (half weight), then the owner cap (owner votes on a player <= 20% of that player's weight)."""
    w = np.ones(len(df))
    g = df[df.pair_type == 'gimme']
    miss = g.apply(lambda r: slot[r.pick] > slot[r.b if r.pick == r.a else r.a], axis=1) if len(g) else pd.Series(dtype=bool)
    rate = miss.groupby(g.session).agg(['mean', 'size']) if len(g) else pd.DataFrame(columns=['mean', 'size'])
    bad = set(rate[(rate['size'] >= GIMME_MIN) & (rate['mean'] > GIMME_MISS)].index)
    w[df.session.isin(bad).values] *= HALF
    own = (df.tag == 'owner').values
    if own.any():
        fac = {}
        for p in set(df.a) | set(df.b):
            m = ((df.a == p) | (df.b == p)).values
            wo, wn = w[m & own].sum(), w[m & ~own].sum()
            fac[p] = 1.0 if wo <= OWNER_CAP / (1 - OWNER_CAP) * wn else (OWNER_CAP / (1 - OWNER_CAP) * wn) / wo
        f = np.array([min(fac[x], fac[y]) for x, y in zip(df.a, df.b)])
        w = np.where(own, w * f, w)
    return w, bad


def board(df, items, prices):
    """Crowd order among items with >= MIN_VOTES real votes; the k-th item gets the k-th price."""
    idx = {x['n']: i for i, x in enumerate(items)}
    df = df[df.pick.notna() & df.a.isin(idx) & df.b.isin(idx)].copy()
    slot = {x['n']: x['r'] for x in items}
    w, bad = weights(df, slot)
    a = df.a.map(idx).values; b = df.b.map(idx).values; win_a = (df.pick == df.a).values
    st = fit(items, a, b, win_a, w)
    n_votes = np.bincount(a, minlength=len(items)) + np.bincount(b, minlength=len(items))
    ok = n_votes >= MIN_VOTES
    order = [i for i in np.argsort(-st) if ok[i]]
    rows = [{'crowd_rank': k + 1, 'name': items[i]['n'], 'pos': items[i]['pos'], 'value': prices[k] if k < len(prices) else None,
             'votes': int(n_votes[i]), 'strength': round(float(st[i]), 3)} for k, i in enumerate(order)]
    rows += [{'crowd_rank': None, 'name': items[i]['n'], 'pos': items[i]['pos'], 'value': None, 'votes': int(n_votes[i]),
              'strength': None} for i in range(len(items)) if not ok[i]]
    return pd.DataFrame(rows), st, ok, w, bad


def steadiness(df, items, prices, rng):
    """§4: random halves of devices, a board from each, rank agreement over items qualifying in both. Median of SPLITS."""
    sess = df.session.unique(); out = []
    for _ in range(SPLITS):
        h = set(rng.choice(sess, len(sess) // 2, replace=False))
        b1, *_ = board(df[df.session.isin(h)], items, prices); b2, *_ = board(df[~df.session.isin(h)], items, prices)
        m = b1.dropna(subset=['crowd_rank']).merge(b2.dropna(subset=['crowd_rank']), on='name')
        if len(m) >= 10: out.append(m.crowd_rank_x.rank().corr(m.crowd_rank_y.rank()))
    return (float(np.median(out)) if out else None), len(out)


def simulate(items, prices, rng, n_votes, n_dev=150, noise=1.0):
    """Planted truth: true strength falls with the page's slot; voters pick by Bradley-Terry with extra noise;
    pairs as the page draws them (close 74%, random 20%, gimme 6%). Returns rank agreement with the truth."""
    r = np.array([x['r'] for x in items]); true = -np.log(r) * 2.0
    rows = []
    for _ in range(n_votes):
        i = rng.integers(len(items)); roll = rng.random()
        if roll < 0.06: c = np.where(np.abs(r - r[i]) >= 90)[0]; t = 'gimme'
        elif roll < 0.26: c = np.delete(np.arange(len(items)), i); t = 'random'
        else: c = np.where((np.abs(r - r[i]) <= 12) & (np.arange(len(items)) != i))[0]; t = 'close'
        if len(c) == 0: c = np.delete(np.arange(len(items)), i); t = 'random'          # the page does the same
        j = rng.choice(c)
        p = 1 / (1 + np.exp(-(true[i] - true[j]) / noise))
        rows.append({'session': f's{rng.integers(n_dev)}', 'tag': 'organic', 'a': items[i]['n'], 'b': items[j]['n'],
                     'pick': items[i]['n'] if rng.random() < p else items[j]['n'], 'pair_type': t})
    df = pd.DataFrame(rows)
    bd, st, ok, *_ = board(df, items, prices)
    truth = pd.Series(true, index=[x['n'] for x in items])
    q = bd.dropna(subset=['crowd_rank'])
    agree = q.crowd_rank.rank().corr((-truth[q.name.values]).rank().reset_index(drop=True)) if len(q) > 10 else None
    return {'votes': n_votes, 'items_with_value': int(ok.sum()), 'agreement_with_truth': None if agree is None else round(float(agree), 3),
            'steadiness': round(steadiness(df, items, prices, rng)[0] or float('nan'), 3)}


def main():
    ap = argparse.ArgumentParser(); g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--simulate', action='store_true'); g.add_argument('--run')
    a = ap.parse_args()
    items = json.load(open(ITEMS)); prices = json.load(open(PRICES))['prices']; rng = np.random.default_rng(20261111)
    if a.simulate:
        res = []
        for n in (1000, 2500, 5000, 10000):
            x = simulate(items, prices, rng, n); res.append(x); print(x, flush=True)
        json.dump(res, open(os.path.join(OUT, 'crowd_values_simulation.json'), 'w'), indent=1); return
    df = pd.read_csv(a.run)
    bd, st, ok, w, bad = board(df, items, prices)
    std, nsplit = steadiness(df[df.pick.notna()], items, prices, rng)
    rep = {'rows': int(len(df)), 'votes': int(df.pick.notna().sum()), 'skips': int(df.pick.isna().sum()),
           'devices': int(df.session.nunique()), 'by_tag': df.tag.value_counts().to_dict(),
           'devices_half_weight_gimmes': len(bad), 'items_with_value': int(ok.sum()), 'steadiness': std, 'splits': nsplit,
           'steady': bool(std is not None and std >= STEADY)}
    bd.to_csv(os.path.join(OUT, 'crowd_board.csv'), index=False)
    json.dump(rep, open(os.path.join(OUT, 'crowd_board_report.json'), 'w'), indent=1)
    print(json.dumps(rep, indent=1))


if __name__ == '__main__':
    main()
