#!/usr/bin/env python3
"""
DELTA — System Score v2 validation harness (scripts/validate-style.py)

Puts the three offense-style hypotheses on trial against POSITIONAL FANTASY
OUTCOMES (not just team EPA):

  H1  motion%      -> RB1 / WR-room / team fantasy production
  H2  play-action% -> QB1 / WR1 production
  H3  12-personnel (TE2 snap proxy) -> TE1 up, WR3 down

Inputs (both already in repo — no new fetches):
  data/style-rates.json    team-season style rates (FTN charting, 2022-25)
  data/backtest-data.json  per-player seasons with team attribution

Three test tiers, in rising order of difficulty:
  A. CONTEMPORANEOUS  — pooled 2022-25 correlations, style vs same-season output
  B. PERSISTENCE      — style(t) vs style(t+1), same team: is style knowable ahead?
  C. PREDICTIVE       — style(2022-24) vs NEXT-season positional output, incl.
                        vs the production-only baseline (does style add anything
                        beyond just knowing last year's production?)

Scoring basis: half-PPR + TE premium (DELTA's half_tep model basis).
Read-only research: prints a verdict table, changes nothing.
"""
import json, math
from collections import defaultdict

STYLE = json.load(open("data/style-rates.json"))["teams"]
BT    = json.load(open("data/backtest-data.json"))["players"]

# PBP posteam codes vs player-data team codes
ALIAS = {"LAR": "LA", "JAC": "JAX", "WSH": "WAS", "OAK": "LV", "SD": "LAC", "STL": "LA"}
def tm(code): return ALIAS.get(code, code)

def ppg(s, pos):
    rec_pt = 1.0 if pos == "TE" else 0.5
    fp = (s.get("rush_yds",0)*0.1 + s.get("rush_td",0)*6 +
          s.get("rec_yds",0)*0.1 + s.get("rec_td",0)*6 + s.get("rec",0)*rec_pt +
          s.get("pass_yds",0)*0.04 + s.get("pass_td",0)*4 + s.get("pass_int",0)*-2)
    return fp / s["games"] if s.get("games") else None

# ── team-season positional rollups ──────────────────────────────
# rank a team's players at each position by TOTAL points (role size), report ppg
roll = defaultdict(lambda: defaultdict(list))   # (season,team) -> pos -> [(total, ppg)]
for name, p in BT.items():
    pos = p["pos"]
    if pos not in ("QB","RB","WR","TE"): continue
    for yr, s in p["seasons"].items():
        y = int(yr)
        if y < 2022 or not s.get("team") or not s.get("games"): continue
        g = s["games"]
        if g < (8 if pos=="QB" else 6): continue          # min-sample: no 2-game noise
        v = ppg(s, pos)
        if v is None: continue
        roll[(y, tm(s["team"]))][pos].append((v*g, v))

rows = []   # joined style + positional outputs
for key, st in STYLE.items():
    y, team = key.split("|"); y = int(y); team = tm(team)
    pr = roll.get((y, team))
    if not pr: continue
    def rank(pos, k):
        lst = sorted(pr.get(pos, []), key=lambda x: -x[0])
        return lst[k][1] if len(lst) > k else None
    wr_room = sorted(pr.get("WR", []), key=lambda x: -x[0])[:3]
    rows.append(dict(y=y, team=team,
        motion=st["motion_pct"], pa=st["pa_pct"], te2=st["te2_snap_proxy"],
        qb1=rank("QB",0), rb1=rank("RB",0), wr1=rank("WR",0), wr3=rank("WR",2),
        te1=rank("TE",0),
        wrroom=sum(v for _,v in wr_room) if len(wr_room)==3 else None,
        team_fp=sum(v for lst in pr.values() for _,v in lst)))

print(f"joined team-seasons: {len(rows)} (of {len(STYLE)} style rows)")

def corr(pairs):
    pairs = [(a,b) for a,b in pairs if a is not None and b is not None]
    n = len(pairs)
    if n < 10: return None, n
    xs, ys = zip(*pairs)
    mx, my = sum(xs)/n, sum(ys)/n
    num = sum((a-mx)*(b-my) for a,b in pairs)
    den = math.sqrt(sum((a-mx)**2 for a in xs) * sum((b-my)**2 for b in ys))
    return (num/den if den else 0.0), n

def show(label, pairs, expect):
    r, n = corr(pairs)
    if r is None: print(f"  {label:34} n={n:3}  (insufficient)"); return
    t = abs(r)*math.sqrt(n-2)/math.sqrt(max(1e-9,1-r*r))
    sig = "**" if t > 2.6 else "*" if t > 2.0 else "  "
    hit = "✓" if (r > 0) == (expect == "+") and t > 2.0 else ("✗" if t > 2.0 else "·")
    print(f"  {label:34} n={n:3}  r={r:+.3f}{sig} expect {expect}  {hit}")

print("\n══ TIER A — contemporaneous (pooled 2022-25) ══  (** p<.01, * p<.05)")
print("H1 motion:")
show("motion vs RB1 ppg",       [(r['motion'], r['rb1'])    for r in rows], "+")
show("motion vs WR-room ppg",   [(r['motion'], r['wrroom']) for r in rows], "+")
show("motion vs team fantasy",  [(r['motion'], r['team_fp'])for r in rows], "+")
print("H2 play-action:")
show("PA vs QB1 ppg",           [(r['pa'], r['qb1'])        for r in rows], "+")
show("PA vs WR1 ppg",           [(r['pa'], r['wr1'])        for r in rows], "+")
print("H3 12-personnel proxy:")
show("TE2-proxy vs TE1 ppg",    [(r['te2'], r['te1'])       for r in rows], "+")
show("TE2-proxy vs WR3 ppg",    [(r['te2'], r['wr3'])       for r in rows], "-")

print("\n══ TIER B — persistence: style(t) vs style(t+1), same team ══")
by_ty = {(r['y'], r['team']): r for r in rows}
for metric in ("motion","pa","te2"):
    pairs = [(by_ty[(y,t)][metric], by_ty[(y+1,t)][metric])
             for (y,t) in by_ty if (y+1,t) in by_ty]
    show(f"{metric}(t) vs {metric}(t+1)", pairs, "+")

print("\n══ TIER C — predictive: style(t) vs NEXT-season output (style 2022-24 → output 2023-25) ══")
def nxt(metric, out):
    return [(by_ty[(y,t)][metric], by_ty[(y+1,t)][out])
            for (y,t) in by_ty if (y+1,t) in by_ty]
show("motion(t) vs RB1 ppg(t+1)",   nxt("motion","rb1"), "+")
show("motion(t) vs WR-room(t+1)",   nxt("motion","wrroom"), "+")
show("PA(t) vs QB1 ppg(t+1)",       nxt("pa","qb1"), "+")
show("TE2(t) vs TE1 ppg(t+1)",      nxt("te2","te1"), "+")
show("TE2(t) vs WR3 ppg(t+1)",      nxt("te2","wr3"), "-")
print("\n  baseline for context (how much does plain production persist?):")
show("RB1 ppg(t) vs RB1 ppg(t+1)",  nxt("rb1","rb1"), "+")
show("QB1 ppg(t) vs QB1 ppg(t+1)",  nxt("qb1","qb1"), "+")
show("TE1 ppg(t) vs TE1 ppg(t+1)",  nxt("te1","te1"), "+")
