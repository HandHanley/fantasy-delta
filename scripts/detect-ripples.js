#!/usr/bin/env node
/*
 * DELTA nightly ripple detector / proposal builder.
 *
 * Flow:
 *   1. Pull Sleeper /players/nfl  (current league-wide roster truth).
 *   2. Diff vs data/roster-snapshot.json (previous run) -> skill-position moves.
 *   3. Join each moved/incumbent player to opportunity + draft data
 *      (data/backtest-data.json, keyed by name; gsis_id used when present).
 *   4. Run the validated generator -> proposed ripples.
 *   5. Write data/ripple-pending.json (for PR review) and refresh the snapshot.
 *
 * The engine NEVER reads ripple-pending.json — only data/ripple.json, which is
 * updated by MERGING the review PR. Nothing here touches users until merged.
 *
 * Detection is keyed by Sleeper's own player_id, so the diff needs no name
 * matching. The crosswalk (dynastyprocess db_playerids) + name normalization
 * are only used to JOIN moves to our opp/draft data.
 *
 * Runs in CI (Sleeper + crosswalk reachable there). `--dry-run <prev> <curr>`
 * skips the network and reads two local snapshot files instead, for testing.
 */
const fs = require('fs'), path = require('path');
const { detectMoves, groupByTeam } = require('./ripple/detect-moves.js');
const { generateRipple } = require('./ripple/generate-ripple.js');

const DATA = path.join(__dirname, '..', 'data');
const SLEEPER_URL = 'https://api.sleeper.app/v1/players/nfl';
const CROSSWALK_URL = 'https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv';
const SKILL = new Set(['RB', 'WR', 'TE']);  // QB excluded — opportunity model doesn't cover QB
const ROOKIE_YEAR = new Date().getMonth() >= 2 ? new Date().getFullYear() : new Date().getFullYear() - 1; // draft is in spring

const norm = s => (s || '').toLowerCase().replace(/[.'’`]/g, '')
  .replace(/\b(jr|sr|ii|iii|iv|v)\b/g, '').replace(/\s+/g, ' ').trim();

async function fetchJSON(u) { const r = await fetch(u); if (!r.ok) throw new Error(`${u} -> ${r.status}`); return r.json(); }
async function fetchText(u) { const r = await fetch(u); if (!r.ok) throw new Error(`${u} -> ${r.status}`); return r.text(); }

// Sleeper /players/nfl is a big {id: {...}} map; trim to skill players we care about.
function trimSleeper(raw) {
  const out = {};
  for (const [id, p] of Object.entries(raw)) {
    if (!p || !SKILL.has(p.position)) continue;
    const full = p.full_name || [p.first_name, p.last_name].filter(Boolean).join(' ');
    out[id] = { full_name: full, position: p.position, team: p.team || null };
  }
  return out;
}

// Minimal quote-aware CSV row splitter (player names have no internal commas, but be safe).
function csvRow(line) {
  const out = []; let cur = '', q = false;
  for (const ch of line) {
    if (ch === '"') q = !q;
    else if (ch === ',' && !q) { out.push(cur); cur = ''; }
    else cur += ch;
  }
  out.push(cur); return out;
}

// crosswalk: build sleeper_id -> { name, gsis_id, draft_year, draft_pick }
function parseCrosswalk(csv) {
  const lines = csv.split(/\r?\n/).filter(Boolean);
  const hdr = csvRow(lines[0]).map(h => h.trim());
  const ix = n => hdr.indexOf(n);
  const c = { sid: ix('sleeper_id'), name: ix('name'), gsis: ix('gsis_id'),
              dy: ix('draft_year'), dp: ix('draft_pick'), dr: ix('draft_round') };
  const map = {};
  for (let k = 1; k < lines.length; k++) {
    const r = csvRow(lines[k]);
    const sid = r[c.sid]; if (!sid) continue;
    map[sid] = {
      name: c.name >= 0 ? r[c.name] : null,
      gsis_id: c.gsis >= 0 ? r[c.gsis] : null,
      draft_year: c.dy >= 0 ? parseInt(r[c.dy]) || null : null,
      draft_pick: c.dp >= 0 ? parseInt(r[c.dp]) || null : null,
    };
  }
  return map;
}

// Build name/gsis indexes over our opp+draft data (backtest-data.json).
function indexPlayerData(bt) {
  const ppg = (s, pos) => { const r = pos === 'TE' ? 1 : (pos === 'QB' ? 0 : 0.5);
    const f = s.pass_yds*0.04 + s.pass_td*4 - s.pass_int*2 + s.rush_yds*0.1 + s.rush_td*6 + s.rec_yds*0.1 + s.rec_td*6 + s.rec*r;
    return s.games ? +(f/s.games).toFixed(1) : 0; };
  const byName = {}, byGsis = {};
  for (const [name, p] of Object.entries(bt.players)) {
    const ys = Object.keys(p.seasons).map(Number).sort((a,b)=>b-a);
    if (!ys.length) continue;
    const latest = p.seasons[String(ys[0])];
    const rec = { name, pos: p.pos, opp_pg: latest.opp_pg, baseline_ppg: ppg(latest, p.pos),
                  played: true, gsis_id: p.gsis_id || null };
    byName[norm(name)] = rec;
    if (p.gsis_id) byGsis[p.gsis_id] = rec;
  }
  // draft (all skill players, incl. those with no season = never played)
  const draftByName = {};
  for (const [name, d] of Object.entries(bt.draft || {})) draftByName[norm(name)] = d;
  return { byName, byGsis, draftByName };
}

// Resolve a Sleeper player (by name, gsis via crosswalk) to opp/draft facts.
function resolve(name, sleeperId, cross, idx) {
  const xw = cross[sleeperId];
  const gsis = xw && xw.gsis_id;
  let rec = (gsis && idx.byGsis[gsis]) || idx.byName[norm(name)] || null;     // opp/baseline (prefers ID)
  const draft = idx.draftByName[norm(xw && xw.name || name)] ||
                (xw && xw.draft_year ? { y: xw.draft_year, p: xw.draft_pick } : null);
  return { rec, draft };
}

function buildArrival(name, sleeperId, pos, cross, idx) {
  const { rec, draft } = resolve(name, sleeperId, cross, idx);
  const played = !!rec;
  if (draft && draft.y >= ROOKIE_YEAR && !played) return { name, rookie: true, pick: draft.p || 999 };
  return { name, rookie: false, prior_opp_pg: rec ? rec.opp_pg : 0 };
}

function buildProposals(prevSnap, currSnap, cross, idx) {
  const groups = groupByTeam(detectMoves(prevSnap, currSnap));
  // sleeper_id lookup by name within a team (to resolve incumbents/moves to ids)
  const idByName = {};
  for (const [id, p] of Object.entries(currSnap)) idByName[`${p.team}|${norm(p.full_name)}`] = id;
  const proposals = [];
  for (const g of groups) {
    const moved = new Set([...g.departures, ...g.arrivals].map(norm));
    const incumbents = Object.entries(currSnap)
      .filter(([,p]) => p.team === g.team && p.position === g.pos && !moved.has(norm(p.full_name)))
      .map(([id, p]) => { const { rec } = resolve(p.full_name, id, cross, idx);
        return { name: p.full_name, opp_pg: rec ? rec.opp_pg : 0, baseline_ppg: rec ? rec.baseline_ppg : 0 }; });
    const move = {
      team: g.team, pos: g.pos,
      departures: g.departures.map(n => { const id = idByName[`${g.team}|${norm(n)}`]; const { rec } = resolve(n, id, cross, idx);
        return { name: n, opp_pg: rec ? rec.opp_pg : 0 }; }),
      arrivals: g.arrivals.map(n => buildArrival(n, idByName[`${g.team}|${norm(n)}`], g.pos, cross, idx)),
      incumbents,
    };
    const prop = generateRipple(move);
    proposals.push(prop);
  }
  return proposals;
}

// Convert proposals to ripple.json entries — INCUMBENTS ONLY. Rookies/arrivals
// are projected by the engine's own ppg25 path (which skips ripples by design),
// so emitting them here would double-count. We emit only the established players
// whose opportunity shifts because of the move.
function proposalsToRipples(proposals) {
  const out = [];
  for (const p of proposals)
    for (const r of p.ripples)
      if (r.role === 'incumbent' && r.delta && r.delta !== '+0%')
        out.push({ n: r.n, d: r.d, reason: r.reason || `opportunity shift from ${p.team} ${p.pos} moves`, delta: r.delta });
  return out;
}

// Merge new entries into the existing ripple.json by player name (update/add;
// untouched players stay). Returns the merged array.
function mergeRipples(existing, fresh) {
  const map = new Map(existing.map(e => [e.n, e]));
  for (const r of fresh) map.set(r.n, r);
  return [...map.values()];
}

// Seed roster-snapshot.json from last season's team assignments in
// backtest-data, keyed by sleeper_id (via the crosswalk gsis->sleeper). This
// lets the first real run diff against last season and backfill the whole
// offseason in one pass. Needs gsis_id in backtest-data (re-pull) + crosswalk.
// nflverse → Sleeper team-abbrev aliases (else a Rams player on 'LA' vs 'LAR'
// reads as a phantom move when seeding from backtest data).
const TEAM_ALIAS = { LA:'LAR', STL:'LAR', SD:'LAC', OAK:'LV', WSH:'WAS', JAC:'JAX', ARZ:'ARI' };
const teamNorm = t => TEAM_ALIAS[t] || t;

function seedSnapshotFromBacktest(bt, cross) {
  const gsisToSleeper = {};
  for (const [sid, x] of Object.entries(cross)) if (x.gsis_id) gsisToSleeper[x.gsis_id] = sid;
  const snap = {};
  for (const [name, p] of Object.entries(bt.players)) {
    const ys = Object.keys(p.seasons).map(Number).sort((a, b) => b - a);
    if (!ys.length) continue;
    const team = teamNorm(p.seasons[String(ys[0])].team);
    const sid = p.gsis_id && gsisToSleeper[p.gsis_id];
    if (!sid) continue;                          // no crosswalk match → skip (name fallback handled live)
    snap[sid] = { full_name: name, position: p.pos, team };
  }
  return snap;
}

async function main() {
  const mode = process.argv[2];
  const dry = mode === '--dry-run';
  let prevSnap, currSnap, cross, bt;
  bt = JSON.parse(fs.readFileSync(path.join(DATA, 'backtest-data.json'), 'utf8'));
  const idx = indexPlayerData(bt);

  if (dry) {
    prevSnap = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
    currSnap = JSON.parse(fs.readFileSync(process.argv[4], 'utf8'));
    cross = fs.existsSync(process.argv[5] || '') ? parseCrosswalk(fs.readFileSync(process.argv[5], 'utf8')) : {};
  } else {
    console.log('[ripple] fetching Sleeper players + crosswalk ...');
    currSnap = trimSleeper(await fetchJSON(SLEEPER_URL));
    cross = parseCrosswalk(await fetchText(CROSSWALK_URL));
    const snapPath = path.join(DATA, 'roster-snapshot.json');
    if (!fs.existsSync(snapPath)) {
      // First run: backfill the whole offseason by seeding from LAST SEASON's
      // teams (so the diff vs current Sleeper surfaces every move), instead of
      // seeding from current (which would detect nothing on run one).
      prevSnap = seedSnapshotFromBacktest(bt, cross);
      console.log(`[ripple] no snapshot — seeded prev from backtest 2025 (${Object.keys(prevSnap).length} players) for offseason backfill`);
    } else {
      prevSnap = JSON.parse(fs.readFileSync(snapPath, 'utf8'));
    }
  }

  const proposals = buildProposals(prevSnap, currSnap, cross, idx)
    .filter(p => p.ripples.some(r => r.role === 'incumbent'));
  const fresh = proposalsToRipples(proposals);

  if (dry) {
    console.log(JSON.stringify(fresh, null, 2));
    console.log(`\n[ripple] ${fresh.length} incumbent ripples from ${proposals.length} affected rooms`);
    return;
  }
  // Merge into the live ripple.json (the engine reads ONLY this file), write the
  // candidate, refresh the snapshot. The workflow PRs both; merge = go-live.
  const ripPath = path.join(DATA, 'ripple.json');
  const existing = fs.existsSync(ripPath) ? JSON.parse(fs.readFileSync(ripPath, 'utf8')) : [];
  const merged = mergeRipples(Array.isArray(existing) ? existing : [], fresh);
  fs.writeFileSync(ripPath, JSON.stringify(merged, null, 2));
  fs.writeFileSync(path.join(DATA, 'roster-snapshot.json'), JSON.stringify(currSnap, null, 0));
  console.log(`[ripple] merged ${fresh.length} ripples → ripple.json (${merged.length} total); snapshot refreshed`);
}
main().catch(e => { console.error('[ripple] FAILED:', e.message); process.exit(1); });
