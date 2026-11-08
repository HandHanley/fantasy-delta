#!/usr/bin/env python3
"""
DELTA — WINS ADDED: a weekly, scarcity-aware yardstick for a player's season. docs/PREREG-wins-added.md.

For every regular-season week a player played:
  win added = P(win with him) - P(win with that week's replacement at his position)
            = Phi((his points - replacement points) / (sigma_team * sqrt 2)) - 0.5
  replacement points = the Nth-best score at his position THAT WEEK (N = the 12-team superflex line: QB 24, RB 30,
                       WR 42, TE 14), so a thin week at a thin position has a low replacement
  sigma_team         = that season's spread of a typical starting lineup's weekly score, from the weekly spread of
                       starter-level players at each position, weighted by the slots the lines imply
Season wins added = max(0, sum over his weeks). A week he didn't play adds 0 (his team plays the replacement).
Scoring: half PPR + TE premium, the weekly nflverse file (as comps_in_season.load).
"""
import math
import numpy as np
import pandas as pd
import comps_value_study as C

SLOTS = {p: C.REPL_N[p] / 12 for p in C.POS}       # slots per team the lines imply: QB 2, RB 2.5, WR 3.5, TE 1.17


def season_wins(W, st):
    """(player_id, season) -> season wins added, plus per-season sigma and a weekly table for inspection."""
    G = W[W.g == 1].copy()
    # replacement: Nth-best score at the position that week (0 if fewer played)
    G['rk'] = G.groupby(['season', 'week', 'position']).P.rank(ascending=False, method='first')
    repl = {}
    for (y, wk, ps), g in G.groupby(['season', 'week', 'position']):
        v = np.sort(g.P.values)[::-1]; n = C.REPL_N[ps]
        repl[(y, wk, ps)] = float(v[n - 1]) if len(v) >= n else 0.0
    # sigma_team: weekly variance of starter-level players (top N by season points) per position, summed by slots
    tot = G.groupby(['season', 'position', 'player_id']).P.sum().reset_index()
    sigma = {}
    for y, gy in G.groupby('season'):
        var = 0.0
        for ps in C.POS:
            top = tot[(tot.season == y) & (tot.position == ps)].nlargest(C.REPL_N[ps], 'P').player_id
            v = gy[(gy.position == ps) & gy.player_id.isin(top)].P.var()
            var += SLOTS[ps] * float(v)
        sigma[int(y)] = math.sqrt(var)
    G['repl'] = [repl[(y, wk, ps)] for y, wk, ps in zip(G.season, G.week, G.position)]
    G['sig'] = G.season.map(sigma)
    from math import erf
    z = (G.P - G.repl) / (G.sig * math.sqrt(2))
    G['wa'] = 0.5 * (1 + np.vectorize(erf)(z / math.sqrt(2))) - 0.5
    S = G.groupby(['player_id', 'season']).agg(wa=('wa', 'sum'), weeks=('wa', 'size'), pts=('P', 'sum'),
                                              position=('position', 'last')).reset_index()
    S['wins'] = S.wa.clip(lower=0)
    return S, sigma, G


def three_season(S_rows, wins, horizon=3, last=2025):
    """FW3 for snapshot rows (key, t): sum over t+1..t+3 of 0.9^(k-1) x season wins added."""
    d = {(k, int(y)): float(v) for k, y, v in zip(wins.player_id, wins.season, wins.wins)}
    out = []
    for k, t in zip(S_rows.key.values, S_rows.t.values):
        if t + horizon > last: out.append(np.nan); continue
        out.append(sum(C.DISCOUNT ** (j - 1) * d.get((k, int(t) + j), 0.0) for j in range(1, horizon + 1)))
    return np.array(out)
