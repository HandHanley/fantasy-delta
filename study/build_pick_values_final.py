#!/usr/bin/env python3
"""
Builds study/out/pick_values_final.json: the rookie pick values for all 36 league formats, for the Trade Calc.

  1QB formats        docs/PREREG-pick-values-formats.md results (study/out/pick_values_formats_results.json)
  Superflex formats  docs/PREREG-superflex-pick-order.md results (study/out/pick_values_sf_results.json)

Display rule (Steve, 7 Nov): a later pick is never worth more than an earlier one. If a later slot range comes out
above an earlier one, the ranges are averaged (weighted by how many slots each covers), repeated until the order holds.
Then: by pick label for the league size, a year out x 0.9, a 1st with its slot unknown = average of the first round.

    python build_pick_values_final.py
"""
import json, os
import numpy as np
import pick_values_formats as F

HERE = os.path.dirname(os.path.abspath(__file__))
BINS = F.BINS
WIDTH = [b - a + 1 for a, b in BINS]


def never_rising(vals, width=WIDTH):
    """Pool adjacent ranges until no later range is above an earlier one (weighted averages)."""
    blocks = [[float(v), float(w), [i]] for i, (v, w) in enumerate(zip(vals, width))]
    i = 0
    while i < len(blocks) - 1:
        if blocks[i + 1][0] > blocks[i][0]:
            a, b = blocks[i], blocks[i + 1]
            w = a[1] + b[1]
            blocks[i] = [(a[0] * a[1] + b[0] * b[1]) / w, w, a[2] + b[2]]
            del blocks[i + 1]
            i = max(i - 1, 0)
        else:
            i += 1
    out = [0] * len(vals)
    for v, _, ix in blocks:
        for j in ix: out[j] = round(v)
    return out


def main():
    one = json.load(open(os.path.join(HERE, 'out', 'pick_values_formats_results.json')))['formats']
    sf = json.load(open(os.path.join(HERE, 'out', 'pick_values_sf_results.json')))['formats']
    src = {tuple(x['key']): ('formats study (1QB order)', x) for x in one if x['key'][1] == '1QB'}
    src.update({tuple(x['key']): ('superflex order study', x) for x in sf})
    assert len(src) == 36, len(src)
    rows, changed = [], []
    for key in sorted(src):
        where, x = src[key]
        raw = list(x['slot_bins'].values())
        sm = never_rising(raw)
        assert all(sm[i] >= sm[i + 1] for i in range(len(sm) - 1)), (x['format'], sm)
        if sm != raw: changed.append({'format': x['format'], 'measured': raw, 'shown': sm})
        teams = key[0]
        first = round(np.mean([sm[next(i for i, (a, b) in enumerate(BINS) if a <= s <= b)] for s in range(1, teams + 1)]))
        rows.append({'format': x['format'], 'key': list(key), 'source': where, 'fix_R': round(x['R'], 3),
                     'fix_range': [round(v, 3) for v in x['range']],
                     'slot_ranges': {f'{a}-{b}': v for (a, b), v in zip(BINS, sm)},
                     'slot_ranges_measured': {f'{a}-{b}': v for (a, b), v in zip(BINS, raw)},
                     'by_pick': F.by_pick(teams, sm),
                     'by_pick_year_out': {k: round(0.9 * v) for k, v in F.by_pick(teams, sm).items()},
                     'first_slot_unknown': first, 'first_slot_unknown_year_out': round(0.9 * first)})
    doc = {'built': '2026-11-07', 'rule': 'later picks never above earlier ones (adjacent ranges averaged, weighted by slots)',
           'notes': ['Each format is on its own 0-10,000 ruler (its top 2025 player = 10,000).',
                     'Slots past 36 (late 3rd round, 14 teams) take the 25-36 value: a stated convention, likely generous.',
                     'The 1.01 is priced with slots 1-4 (Steve, 7 Nov).'],
           'smoothed': changed, 'formats': rows}
    json.dump(doc, open(os.path.join(HERE, 'out', 'pick_values_final.json'), 'w'), indent=1)
    print(f'{len(rows)} formats written; {len(changed)} smoothed')
    for c in changed: print(f"  {c['format']:<40} measured {c['measured']} -> shown {c['shown']}")


if __name__ == '__main__':
    assert never_rising([10, 5, 6, 2, 1], [4, 4, 4, 12, 12]) == [10, 6, 6, 2, 1]     # 5.5 rounds to 6 (half to even)
    assert never_rising([10, 8, 6, 2, 1]) == [10, 8, 6, 2, 1]
    assert never_rising([5, 6, 7, 2, 1], [4, 4, 4, 12, 12]) == [6, 6, 6, 2, 1]
    main()
