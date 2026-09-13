#!/usr/bin/env node
/*
 * DELTA league-history fetcher  —  ONE-OFF TOOL, NOT PART OF THE APP.
 *
 * Pulls the COMPLETE transaction history of a Sleeper dynasty league: every
 * season it has ever existed for, every week of each season, plus that season's
 * manager list and every draft with all of its selections. Writes one file per
 * season to data/fixtures/.
 *
 * Failed waiver claims are DROPPED. They are ~24% of every season and carry no
 * information — "this player was claimed by another owner", "your roster will
 * have too many players". Only status:"complete" rows are kept.
 *
 * Why this exists: Sleeper files offseason activity under week 1 and in-season
 * activity under the week it happened, so a full season needs 18 calls, not 1.
 * Doing that by hand across four seasons is 70+ copy-pastes.
 *
 * NOTHING IN THE APP READS THESE FILES. They are test material for building the
 * trade-history feature, which fetches from Sleeper in the browser at runtime.
 * That is why this workflow is deliberately NOT in the Deploy Pages trigger list.
 *
 * Sleeper IS reachable from GitHub Actions — scripts/detect-ripples.js has been
 * fetching /players/nfl nightly for months. (The "Sleeper blocks server-side
 * requests" comment in index.html is about the old stats pipeline and does not
 * hold for CI.)
 *
 * Usage:
 *   node scripts/fetch-league-history.js <leagueId>
 *   node scripts/fetch-league-history.js <leagueId> --out data/fixtures
 *   node scripts/fetch-league-history.js <leagueId> --from-dir test/fixtures
 *
 * --from-dir skips the network entirely and reads local files named
 *   <leagueId>-league.json  and  <leagueId>-<week>.json
 * so the walk / merge / dedupe / write logic can be executed and asserted on
 * without touching Sleeper. Same pattern as detect-ripples.js --dry-run.
 */
const fs = require('fs');
const path = require('path');

const API = 'https://api.sleeper.app/v1';
const OUT_DEFAULT = path.join(__dirname, '..', 'data', 'fixtures');
const MAX_WEEK = 18;        // NFL regular season; Sleeper returns [] beyond it
const MAX_SEASONS = 20;     // loop guard — a league chain should never be this long
const PAUSE_MS = 150;       // be polite to a free API

// ---------------------------------------------------------------- arguments

function parseArgs(argv) {
  const args = { leagueId: null, out: OUT_DEFAULT, fromDir: null };
  const rest = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--out') { args.out = argv[++i]; }
    else if (a === '--from-dir') { args.fromDir = argv[++i]; }
    else if (a.startsWith('--')) { throw new Error(`unrecognised argument: ${a}`); }
    else { rest.push(a); }
  }
  if (rest.length !== 1) {
    throw new Error('usage: node scripts/fetch-league-history.js <leagueId> [--out DIR] [--from-dir DIR]');
  }
  args.leagueId = rest[0];
  if (!/^\d{6,}$/.test(args.leagueId) && !args.fromDir) {
    throw new Error(`league id looks wrong: "${args.leagueId}" (expected a long number)`);
  }
  return args;
}

// ------------------------------------------------------------------ sources
// Two interchangeable sources. The network one is what runs in CI; the local
// one exists so every line below it can be executed in a test.

function networkSource() {
  const get = async (url) => {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`${url} -> HTTP ${r.status}`);
    return r.json();
  };
  return {
    league: (id) => get(`${API}/league/${id}`),
    users: (id) => get(`${API}/league/${id}/users`),
    drafts: (id) => get(`${API}/league/${id}/drafts`),
    draftPicks: (draftId) => get(`${API}/draft/${draftId}/picks`),
    transactions: (id, week) => get(`${API}/league/${id}/transactions/${week}`),
    pause: () => new Promise(res => setTimeout(res, PAUSE_MS)),
  };
}

function localSource(dir) {
  const read = (file) => {
    const p = path.join(dir, file);
    if (!fs.existsSync(p)) return null;
    return JSON.parse(fs.readFileSync(p, 'utf8'));
  };
  return {
    league: async (id) => {
      const d = read(`${id}-league.json`);
      if (!d) throw new Error(`missing local file: ${id}-league.json`);
      return d;
    },
    users: async (id) => read(`${id}-users.json`) || [],
    drafts: async (id) => read(`${id}-drafts.json`) || [],
    draftPicks: async (draftId) => read(`draft-${draftId}-picks.json`) || [],
    transactions: async (id, week) => read(`${id}-${week}.json`) || [],
    pause: async () => {},
  };
}

// -------------------------------------------------------------------- fetch

// Walk previous_league_id back to the inaugural season. Returns newest first.
async function walkChain(src, startId, log) {
  const chain = [];
  const seen = new Set();
  let id = startId;
  while (id && chain.length < MAX_SEASONS) {
    if (seen.has(id)) throw new Error(`league chain loops at ${id}`);
    seen.add(id);
    const lg = await src.league(id);
    if (!lg || !lg.league_id) throw new Error(`league ${id} returned nothing`);
    chain.push({ league_id: lg.league_id, season: lg.season, name: lg.name, status: lg.status });
    log(`  ${lg.season}  ${lg.name}  (${lg.league_id})`);
    id = lg.previous_league_id || null;
    await src.pause();
  }
  if (chain.length >= MAX_SEASONS) throw new Error('league chain hit the season cap — check for a loop');
  return chain;
}

// Every week of one season, merged and de-duplicated by transaction_id.
// Managers, by Sleeper user id. Pulled per season on purpose: a manager who left
// the league two years ago is absent from the CURRENT season's user list, and
// their old trades would otherwise render as a bare id.
async function fetchUsers(src, league) {
  const raw = await src.users(league.league_id);
  if (!Array.isArray(raw)) throw new Error(`${league.season} users returned ${typeof raw}, expected an array`);
  const out = {};
  for (const u of raw) {
    if (!u || !u.user_id) continue;
    const meta = u.metadata || {};
    out[u.user_id] = {
      display_name: u.display_name || null,
      team_name: meta.team_name || null,   // manager's own team name, when they set one
    };
  }
  return out;
}

// Drafts, and every selection in them.
//
// THIS IS THE PIECE THAT TURNS A TRADED PICK INTO A PLAYER. Sleeper records a
// traded pick as "roster 4's 2025 1st" — a round and an ORIGINAL owner, never a
// pick number. The draft's slot_to_roster_id says which draft slot belonged to
// roster 4, and slot + round gives the pick number, which names the player.
// The board in the app cannot supply this: it shows who MADE each pick, which
// is the owner after trades, not the original owner.
//
// Kept deliberately slim — the raw picks payload carries a large metadata blob
// per selection and we need six fields of it.
async function fetchDrafts(src, league, log) {
  const list = await src.drafts(league.league_id);
  if (!Array.isArray(list)) throw new Error(`${league.season} drafts returned ${typeof list}, expected an array`);
  const out = [];
  for (const d of list) {
    if (!d || !d.draft_id) continue;
    const picks = await src.draftPicks(d.draft_id);
    if (!Array.isArray(picks)) throw new Error(`draft ${d.draft_id} picks returned ${typeof picks}`);
    out.push({
      draft_id: d.draft_id,
      season: d.season,
      status: d.status,
      type: d.type,                       // snake / linear — decides the pick-number maths
      rounds: (d.settings && d.settings.rounds) || null,
      teams: (d.settings && d.settings.teams) || null,
      start_time: d.start_time || null,
      slot_to_roster_id: d.slot_to_roster_id || null,   // THE mapping
      picks: picks.map(p => {
        const m = p.metadata || {};
        return {
          pick_no: p.pick_no,
          round: p.round,
          draft_slot: p.draft_slot,
          roster_id: p.roster_id,          // who actually made the selection
          picked_by: p.picked_by || null,
          player_id: p.player_id,
          name: [m.first_name, m.last_name].filter(Boolean).join(' ') || null,
          pos: m.position || null,
        };
      }),
    });
    log(`    draft ${d.draft_id}: ${d.type}, ${picks.length} picks, slot map ${d.slot_to_roster_id ? 'present' : 'MISSING'}`);
    await src.pause();
  }
  return out;
}

async function fetchSeason(src, league, log) {
  const byId = new Map();
  const perWeek = {};
  let skipped = 0;
  for (let week = 1; week <= MAX_WEEK; week++) {
    const rows = await src.transactions(league.league_id, week);
    if (!Array.isArray(rows)) throw new Error(`${league.season} week ${week} returned ${typeof rows}, expected an array`);
    perWeek[week] = rows.length;
    for (const row of rows) {
      if (!row || !row.transaction_id) throw new Error(`${league.season} week ${week}: row without transaction_id`);
      // Failed waiver claims are noise: "somebody else got him" / "your roster is
      // full". 24% of every season and worth nothing to any view we build.
      if (row.status !== 'complete') { skipped++; continue; }
      byId.set(row.transaction_id, row);   // last write wins; ids are unique anyway
    }
    await src.pause();
  }
  const transactions = [...byId.values()].sort((a, b) => b.created - a.created);
  const weeksWithData = Object.entries(perWeek).filter(([, n]) => n > 0).map(([w]) => Number(w));
  const trades = transactions.filter(t => t.type === 'trade').length;
  log(`  ${league.season}: ${transactions.length} records, ${trades} trades, ${skipped} incomplete dropped, weeks with data: ${weeksWithData.join(', ') || 'none'}`);
  return { transactions, perWeek, weeksWithData, trades, skipped };
}

// --------------------------------------------------------------------- main

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const log = (...m) => console.log(...m);
  const src = args.fromDir ? localSource(args.fromDir) : networkSource();

  log(args.fromDir ? `Reading local files from ${args.fromDir}` : 'Fetching from Sleeper');
  log('Walking the league chain:');
  const chain = await walkChain(src, args.leagueId, log);
  log(`Found ${chain.length} season(s).\n`);

  fs.mkdirSync(args.out, { recursive: true });

  const written = [];
  let totalRecords = 0, totalTrades = 0;

  for (const league of chain) {
    const users = await fetchUsers(src, league);
    const drafts = await fetchDrafts(src, league, log);
    const { transactions, perWeek, weeksWithData, trades, skipped } = await fetchSeason(src, league, log);
    const payload = {
      source: 'sleeper',
      league_id: league.league_id,
      league_name: league.name,
      season: league.season,
      league_status: league.status,
      fetched_at: new Date().toISOString(),
      weeks_requested: MAX_WEEK,
      weeks_with_data: weeksWithData,
      records_per_week: perWeek,
      incomplete_dropped: skipped,
      managers: users,
      drafts,
      count: transactions.length,
      trade_count: trades,
      transactions,
    };
    const file = path.join(args.out, `slp-history-${league.season}.json`);
    fs.writeFileSync(file, JSON.stringify(payload, null, 1));
    written.push(file);
    totalRecords += transactions.length;
    totalTrades += trades;
  }

  log('');
  log(`Wrote ${written.length} file(s) to ${args.out}`);
  log(`Total: ${totalRecords} records, ${totalTrades} trades across ${chain.length} season(s)`);
  for (const f of written) log(`  ${path.relative(process.cwd(), f)}  ${fs.statSync(f).size} bytes`);
}

main().catch(err => { console.error('FAILED:', err.message); process.exit(1); });
