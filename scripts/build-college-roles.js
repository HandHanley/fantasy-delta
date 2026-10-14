/**
 * DELTA — College Role Changes (14 Oct 2026). Writes data/college-roles.json.
 *
 * ROLE SCORE (owner's name, 13 Oct): how much of his team's offense goes through a
 * player in one game, 0-100. Built from the per-game team totals the college nightly
 * keeps on every game row (tc = team carries, tr = team catches, ty = team receiving
 * yards; added 13 Oct, 3bc7332). College box scores have no targets, air yards or red
 * zone, so this is NOT the NFL Alpha / Workhorse and deliberately has its own name.
 *
 *   RB      0.8 x carry share / 0.50  +  0.2 x catch share / 0.15
 *   WR      0.5 x catch share / 0.35  +  0.5 x yard share / 0.40
 *   TE      0.5 x catch share / 0.26  +  0.5 x yard share / 0.26
 *   each part capped at 1. The divisors sit near the top 5% of the 2026 season
 *   (measured 13 Oct), the same way the NFL scores were calibrated.
 *
 * EARLY vs RECENT: the middle (median) of his first three games and of his last three,
 * as on the NFL board, so one odd game cannot move him on its own. 5+ games with a
 * known team total. College swings far more game to game than the NFL; the bars show
 * that honestly and the owner accepted it (14 Oct).
 *
 * WHO COUNTS: every Power 4 player we track, Big Board players, and anyone else once
 * his recent Role Score reaches the top quarter of his position. The page shows Power 4
 * by default with an All Schools switch (owner, 14 Oct).
 *
 * THREE LISTS per position:
 *   new   New To A Big Role: recent in the top quarter, early NOT in the early top
 *         quarter, and not a big role last season. "Last season" uses that season's
 *         totals (catch share for WR/TE; rushing Dominator for RB, because last season's
 *         file has no team carries) against the same top-quarter rule. Close, not exact.
 *   up    Role Score up 20+, not already in `new`.
 *   dn    Role Score down 20+.
 *
 * DISPLAY ONLY. Facts, never a call; nothing scored reads this file.
 *
 *   node scripts/build-college-roles.js
 */
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const D = (f) => path.join(ROOT, 'data', f);
const MIN_GAMES = 5, MIN_MOVE = 20, TOP_Q = 0.75;
const CEIL = { RB: [0.50, 0.15], WR: [0.35, 0.40], TE: [0.26, 0.26] };
const CLS = { 1: 'Fr', 2: 'So', 3: 'Jr', 4: 'Sr', 5: 'Sr' };

const med = (a) => { const b = a.slice().sort((x, y) => x - y), m = b.length >> 1; return b.length % 2 ? b[m] : (b[m - 1] + b[m]) / 2; };
const cutAt = (vals) => { const v = vals.slice().sort((x, y) => x - y); return v.length ? v[Math.min(v.length - 1, Math.floor(TOP_Q * v.length))] : Infinity; };
const n0 = (v) => { const x = parseFloat(v); return isFinite(x) ? x : 0; };

function score(r, pos) {
  const [a, b] = CEIL[pos];
  if (pos === 'RB') {
    if (!r.tc) return null;
    const cs = n0(r.car) / r.tc, rs = r.tr ? n0(r.rec) / r.tr : 0;
    return 100 * (0.8 * Math.min(1, cs / a) + 0.2 * Math.min(1, rs / b));
  }
  if (!r.tr || !r.ty) return null;
  return 100 * (0.5 * Math.min(1, n0(r.rec) / r.tr / a) + 0.5 * Math.min(1, Math.max(0, n0(r.rey)) / r.ty / b));
}
function shareLines(pos, G) {
  const pct = (arr) => arr.length ? Math.round(100 * med(arr)) : null;
  if (pos === 'RB') return [['Carry share', pct(G.filter(r => r.tc).map(r => n0(r.car) / r.tc))],
                            ['Catch share', pct(G.filter(r => r.tr).map(r => n0(r.rec) / r.tr))]];
  return [['Catch share', pct(G.filter(r => r.tr).map(r => n0(r.rec) / r.tr))],
          ['Yard share', pct(G.filter(r => r.ty).map(r => Math.max(0, n0(r.rey)) / r.ty))]];
}

function build() {
  const cur = JSON.parse(fs.readFileSync(D('college-players.json'), 'utf8'));
  const season = cur.season;
  let prev = { players: [] };
  try { prev = JSON.parse(fs.readFileSync(D(`college-players-${season - 1}.json`), 'utf8')); }
  catch (e) { console.warn(`  no ${season - 1} file — "not a big role last season" check skipped`); }
  let board = {};
  try { board = JSON.parse(fs.readFileSync(D('devy-board.json'), 'utf8')).players || {}; } catch (e) {}
  const bbRank = {};
  for (const k in board) bbRank[board[k].cfbName || k] = board[k].rank;

  const rows = [];
  let withTotals = 0;
  for (const p of cur.players || []) {
    if (!CEIL[p.pos]) continue;
    const G = (p.g || []).slice().sort((x, y) => x.w - y.w).filter(r => score(r, p.pos) != null);
    if (G.length) withTotals++;
    if (G.length < MIN_GAMES) continue;
    const s = G.map(r => Math.round(score(r, p.pos)));
    const e = Math.round(med(s.slice(0, 3))), rc = Math.round(med(s.slice(-3)));
    const a = shareLines(p.pos, G.slice(0, 3)), b = shareLines(p.pos, G.slice(-3));
    rows.push({ n: p.n, pos: p.pos, tm: p.tm, conf: p.conf || '', p4: p.p4 ? 1 : 0, cls: CLS[p.cls] || '',
      bb: bbRank[p.n] || null, e, r: rc, ch: rc - e,
      wk: G.map((r, i) => [r.w, s[i]]),
      lines: [0, 1].filter(i => a[i][1] != null && b[i][1] != null).map(i => [a[i][0], a[i][1], b[i][1]]) });
  }
  if (!withTotals) {
    console.error('::error title=College Role Changes::No game row carries team totals (tc/tr/ty). Not writing.');
    process.exit(1);
  }

  const cut = {}, cutE = {}, lastCut = {};
  for (const pos in CEIL) {
    cut[pos] = cutAt(rows.filter(x => x.pos === pos).map(x => x.r));
    cutE[pos] = cutAt(rows.filter(x => x.pos === pos).map(x => x.e));
    const key = pos === 'RB' ? 'rdom' : 'rsh';
    lastCut[pos] = [key, cutAt((prev.players || []).filter(p => p.pos === pos && (p.gms || 0) >= MIN_GAMES).map(p => p[key] || 0))];
  }
  const prevBy = {};
  for (const p of prev.players || []) prevBy[p.n + '|' + p.pos] = p;
  const bigLast = (x) => { const p = prevBy[x.n + '|' + x.pos]; if (!p) return false; const [k, c] = lastCut[x.pos]; return (p[k] || 0) >= c; };

  const out = { generated: new Date().toISOString(), season, min_games: MIN_GAMES, min_move: MIN_MOVE,
    note: 'College Role Changes. Role Score 0-100 = share of his team’s offense per game (see scripts/build-college-roles.js). Display only.',
    cut, pos: {} };
  for (const pos in CEIL) {
    const P = rows.filter(x => x.pos === pos && (x.p4 || x.bb || x.r >= cut[pos]));
    const isNew = (x) => x.r >= cut[pos] && x.e < cutE[pos] && !bigLast(x);
    const nw = P.filter(isNew).sort((a, b) => b.ch - a.ch || a.n.localeCompare(b.n));
    const up = P.filter(x => x.ch >= MIN_MOVE && !isNew(x)).sort((a, b) => b.ch - a.ch || a.n.localeCompare(b.n));
    const dn = P.filter(x => x.ch <= -MIN_MOVE).sort((a, b) => a.ch - b.ch || a.n.localeCompare(b.n));
    out.pos[pos] = { pool: P.length, new: nw, up, dn };
    console.log(`  ${pos}: pool ${P.length} | new ${nw.length} (P4 ${nw.filter(x => x.p4).length}) | more ${up.length} | less ${dn.length} | top-quarter ${cut[pos]}`);
  }
  fs.writeFileSync(D('college-roles.json'), JSON.stringify(out));
  console.log(`  wrote data/college-roles.json (${(fs.statSync(D('college-roles.json')).size / 1024).toFixed(0)} KB)`);
}

if (require.main === module) build();
module.exports = { score, med, CEIL };
