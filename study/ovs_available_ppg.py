#!/usr/bin/env python3
"""
DELTA — OWN VALUE SCALE: POINTS PER AVAILABLE GAME. Implements docs/PREREG-ovs-available-ppg.md.

Week 9, 2013-2022. Versions:
  J   today's in-season value: production per game played + injury-neutral games number   (DECISION §5)
  N   production per AVAILABLE game, games number weight 0                                   (decides)
  NG  production per available game + injury-neutral games number                          (reported)

    python ovs_available_ppg.py --nflverse D --rosters D --weekly D --wrost D --inj D
"""
import argparse, json, os
import numpy as np
import comps_value_study as C
import ovs_era as E
import ovs_in_season as I
import injury_weeks as J

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
WEEK = 9
RMSE_GUARD, TRADE_GUARD = -0.01, -1.0


def prod_available(Sin, W, week, L_full, L_upto, st, A_full, A_upto):
    """ovs_in_season.era_adjust's veteran production with each season's denominator = available games (>= played)."""
    full = W.groupby(['player_id', 'season']).agg(P=('P', 'sum'), G=('g', 'sum'))
    upto = W[W.week <= week].groupby(['player_id', 'season']).agg(P=('P', 'sum'), G=('g', 'sum'))
    FP, FG, UP, UG = full.P.to_dict(), full.G.to_dict(), upto.P.to_dict(), upto.G.to_dict()
    spos = st.set_index(['player_id', 'season']).position.to_dict()
    lifted = {'full': 0, 'upto': 0}

    def den(A, G, key, kind):
        a, g = A.get(key, 0), G.get(key, 0)
        if a < g: lifted[kind] += 1
        return max(a, g)

    def ppg(terms):
        num = d = 0.0
        for w, v in terms:
            if v is not None: num += w * v; d += w
        return num / d if d else np.nan
    out = []
    for k, Y, pos, kin in zip(Sin.key.values, Sin.t.values, Sin.pos.values, Sin.kind.values):
        ps = lambda yr: spos.get((k, yr), pos)

        def full_term(yr):
            a = den(A_full, FG, (k, yr), 'full')
            return (FP.get((k, yr), 0.0) / a) / L_full[(yr, ps(yr))] if a >= 1 and (yr, ps(yr)) in L_full else None
        aY = den(A_upto, UG, (k, Y), 'upto')
        if aY >= 1:
            cur = (UP.get((k, Y), 0.0) / aY) / L_upto[(Y, ps(Y), week)]
            v = ppg([(3, cur), (2, full_term(Y - 1)), (1, full_term(Y - 2))])
        else:
            v = ppg([(3, full_term(Y - 1)), (2, full_term(Y - 2)), (1, full_term(Y - 3))])
        out.append(v if kin == 'V' else np.nan)
    return np.array(out, float), lifted


def paired(rows, ti, nn, w, yi):
    pos = {int(r): j for j, r in enumerate(ti)}
    assert set(pos) == set(int(r) for r in rows)
    return I.preds([nn[pos[int(r)]] for r in rows], [w[pos[int(r)]] for r in rows], yi)


def cmp(S, rows, pa, pb, yt):
    lift, p = C.perm_test(yt, pa, pb, S.key.values[rows], E.N_PERM)
    tr = I.trades(S, rows, pa, pb, yt)
    return {'rmse_new': C.rmse(pa, yt), 'rmse_today': C.rmse(pb, yt), 'change': float(lift), 'p_new_better': float(p),
            'trades_new': tr['acc_in_season'], 'trades_today': tr['acc_baseline'], 'trades_diff': tr['diff']}


def main():
    ap = argparse.ArgumentParser()
    for k in ('nflverse', 'rosters', 'weekly', 'wrost', 'inj'): ap.add_argument('--' + k, required=True)
    a = ap.parse_args()
    assert C.W_V['games'] == 1.0
    st, W, Sin, Sb, skipped = I.build(a.nflverse, a.rosters, a.weekly, WEEK)
    L_full, L_upto = I.levels(W)
    # equivalence: with available = played, the function reproduces today's production exactly
    G_full = W.groupby(['player_id', 'season']).g.sum().to_dict(); G_upto = W[W.week <= WEEK].groupby(['player_id', 'season']).g.sum().to_dict()
    chk, _ = prod_available(Sin, W, WEEK, L_full, L_upto, st, G_full, G_upto)
    same = np.isclose(chk, Sin['prod'].values, equal_nan=True)
    assert same.all(), f'equivalence failed on {int((~same).sum())} rows'
    rows = Sin.index[(Sin.t >= I.TEST[0]) & (Sin.t <= I.TEST[1])].values
    yi = np.nan_to_num(Sin.FV.values.astype(float)); yt = yi[rows]

    inj = J.injured_weeks(a.weekly, a.wrost, a.inj, WEEK)
    A_upto, parts = J.available_weeks(a.weekly, a.wrost, a.inj, WEEK, return_parts=True)
    A_full = J.available_weeks(a.weekly, a.wrost, a.inj, 22)
    newprod, lifted = prod_available(Sin, W, WEEK, L_full, L_upto, st, A_full, A_upto)
    neutral, add = J.neutral_games(Sin, inj, WEEK)

    SJ = Sin.copy(); SJ['games'] = neutral                                   # today: J
    SN = Sin.copy(); SN['games'] = neutral; SN['prod'] = newprod              # new production (+ games for NG)
    ti, nn, w = I.match(SJ, rows); pJ = paired(rows, ti, nn, w, yi)
    ti, nn, w = I.match(SN, rows); pNG = paired(rows, ti, nn, w, yi)
    C.W_V['games'] = 0.0
    ti, nn, w = I.match(SN, rows); pN = paired(rows, ti, nn, w, yi)
    C.W_V['games'] = 1.0

    vet = SN.kind.values[rows] == 'V'
    hurt = add[rows] >= 2
    lowjob = (Sin.games.values[rows] <= 5) & (add[rows] == 0) & vet
    pos = Sin.pos.values[rows]
    res = {'prereg': 'docs/PREREG-ovs-available-ppg.md', 'week': WEEK, 'rows': int(len(rows)),
           'available_data': parts, 'denominator_lifted_to_played': lifted,
           'production_changed_rows': int((~np.isclose(newprod[rows], Sin['prod'].values[rows], equal_nan=True)).sum()),
           'N_vs_today': cmp(Sin, rows, pN, pJ, yt), 'NG_vs_today': cmp(Sin, rows, pNG, pJ, yt), 'NG_vs_N': cmp(Sin, rows, pNG, pN, yt),
           'by_position_N_vs_today': {q: float(1 - C.rmse(pN[pos == q], yt[pos == q]) / C.rmse(pJ[pos == q], yt[pos == q])) for q in C.POS},
           'out_hurt_2plus': {v: {'rows': int(hurt.sum()), 'produced_over_predicted': float(yt[hurt].sum() / p[hurt].sum())} for v, p in (('today', pJ), ('N', pN), ('NG', pNG))},
           'low_games_never_hurt': {v: {'rows': int(lowjob.sum()), 'produced_over_predicted': float(yt[lowjob].sum() / p[lowjob].sum())} for v, p in (('today', pJ), ('N', pN), ('NG', pNG))}}
    n = res['N_vs_today']
    res['decision'] = ('points per available game, no games number' if n['change'] >= RMSE_GUARD and n['trades_diff'] >= TRADE_GUARD
                       else 'keep injury-neutral games')
    json.dump(res, open(os.path.join(OUT, 'ovs_available_ppg_results.json'), 'w'), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == '__main__':
    main()
