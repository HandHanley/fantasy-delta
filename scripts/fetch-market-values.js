/**
 * DELTA Live Data Fetch Script
 * Runs nightly via GitHub Actions
 * 
 * Fetches:
 *   1. FantasyCalc dynasty SF values (players + picks)
 *   2. Sleeper NFL player ID map (name → ID)
 *   3. Sleeper historical stats (2023, 2024, current season)
 *      Stores RAW stat lines so loader can calc PPG per scoring format
 * 
 * Writes:
 *   data/market-values.json   — ktc/FC values
 *   data/player-stats.json    — raw stat lines per player per season
 */

const https = require('https');
const fs    = require('fs');
const path  = require('path');

// ── CONFIG ────────────────────────────────────────────────────────────────
const FC_URL = 'https://api.fantasycalc.com/values/current?isDynasty=true&numQbs=2&numTeams=12&ppr=1&includePicksAsPlayers=true';
const CURRENT_SEASON = 2025; // last completed season
const STAT_SEASONS   = [2023, 2024, 2025];

// ── HTTP HELPER ───────────────────────────────────────────────────────────
function fetchJson(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; DELTA/1.0)',
        'Accept':     'application/json',
      }
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch (e) { reject(new Error(`JSON parse failed for ${url}: ${e.message}`)); }
      });
    });
    req.on('error', reject);
    req.setTimeout(30000, () => { req.destroy(); reject(new Error(`Timeout: ${url}`)); });
  });
}

// ── ENSURE OUTPUT DIR ─────────────────────────────────────────────────────
const outDir = path.join(process.cwd(), 'data');
if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

// ─────────────────────────────────────────────────────────────────────────
// STEP 1 — FantasyCalc market values
// ─────────────────────────────────────────────────────────────────────────
async function fetchMarketValues() {
  console.log('[DELTA] Fetching FantasyCalc values...');
  const data = await fetchJson(FC_URL);
  if (!Array.isArray(data) || !data.length) throw new Error('Bad FC response');

  const values = {};
  let playerCount = 0, pickCount = 0;

  for (const item of data) {
    const name  = item?.player?.name;
    const value = item?.value;
    if (!name || value == null) continue;
    const isPick = name.includes('Round Pick');
    values[name] = {
      value:        Math.round(value),
      overallRank:  item.overallRank  || null,
      positionRank: item.positionRank || null,
      trend30Day:   item.trend30Day   || 0,
      position:     item?.player?.position   || null,
      team:         item?.player?.maybeTeam  || null,
    };
    if (isPick) pickCount++; else playerCount++;
  }

  fs.writeFileSync(
    path.join(outDir, 'market-values.json'),
    JSON.stringify({ fetched: new Date().toISOString(), playerCount, pickCount, values }, null, 2)
  );
  console.log(`[DELTA] market-values.json — ${playerCount} players, ${pickCount} picks`);

  // Spot check
  for (const name of ['Josh Allen', 'Brock Bowers', 'Jeremiyah Love']) {
    const v = values[name];
    console.log(`  ${name}: ${v ? v.value + ' (#' + v.overallRank + ')' : 'NOT FOUND'}`);
  }
}

// ─────────────────────────────────────────────────────────────────────────
// STEP 2 — Sleeper player ID map
// ─────────────────────────────────────────────────────────────────────────
async function buildPlayerIdMap() {
  console.log('\n[DELTA] Fetching Sleeper player database (~2MB)...');
  const players = await fetchJson('https://api.sleeper.app/v1/players/nfl');

  // Map: normalized_name → { sleeper_id, position, team }
  const nameToId = {};
  const idToName = {};

  for (const [id, p] of Object.entries(players)) {
    if (!p.first_name || !p.last_name) continue;
    if (!['QB','RB','WR','TE'].includes(p.position)) continue;
    if (p.status === 'Inactive' && !p.fantasy_positions?.length) continue;

    const fullName = `${p.first_name} ${p.last_name}`;
    const key      = fullName.toLowerCase().replace(/[^a-z\s']/g, '').trim();

    nameToId[key] = {
      id,
      position: p.position,
      team:     p.team || 'FA',
      fullName,
    };
    idToName[id] = fullName;
  }

  console.log(`[DELTA] Sleeper player map: ${Object.keys(nameToId).length} entries`);
  return { nameToId, idToName };
}

// ─────────────────────────────────────────────────────────────────────────
// STEP 3 — Fetch season stats for all DELTA players
// ─────────────────────────────────────────────────────────────────────────

// Normalise a player name the same way we do in nameToId
function normName(name) {
  return name.toLowerCase()
    .replace(/\bsr\.?\b/g, '').replace(/\bjr\.?\b/g, '')
    .replace(/\bii\b/g,'').replace(/\biii\b/g,'')
    .replace(/[^a-z\s']/g,'').replace(/\s+/g,' ').trim();
}

// DELTA RAW player names we need stats for (extracted from HTML at build time)
// The Action writes this list from the actual RAW array via a companion step,
// but for robustness we also accept it as an env var JSON array.
function getDeltaPlayerNames() {
  try {
    const envList = process.env.DELTA_PLAYER_NAMES;
    if (envList) return JSON.parse(envList);
  } catch {}
  // Fallback: read index.html and extract RAW names
  const htmlPath = path.join(process.cwd(), 'index.html');
  if (!fs.existsSync(htmlPath)) return [];
  const html    = fs.readFileSync(htmlPath, 'utf8');
  const rawStart = html.indexOf('const RAW=[');
  const rawEnd   = html.indexOf('\nconst PICKS=', rawStart);
  const raw      = html.slice(rawStart, rawEnd);
  return [...raw.matchAll(/n:'([^']+)'/g)].map(m => m[1]);
}

async function fetchPlayerStats(nameToId, idToName) {
  console.log('\n[DELTA] Fetching player stats from Sleeper...');

  const deltaNames = getDeltaPlayerNames();
  console.log(`[DELTA] ${deltaNames.length} players to look up`);

  // Build DELTA name → Sleeper ID mapping
  const playerLookup = {}; // deltaName → sleeperId
  const notFound     = [];

  for (const name of deltaNames) {
    const key    = normName(name);
    const entry  = nameToId[key];

    if (entry) {
      playerLookup[name] = entry.id;
    } else {
      // Try dropping suffix words one at a time
      const words  = key.split(' ');
      let matched  = false;
      for (let len = words.length - 1; len >= 2; len--) {
        const partial = words.slice(0, len).join(' ');
        const found   = Object.values(nameToId).find(e =>
          e.fullName.toLowerCase().startsWith(partial)
        );
        if (found) {
          playerLookup[name] = found.id;
          matched = true;
          break;
        }
      }
      if (!matched) notFound.push(name);
    }
  }

  console.log(`[DELTA] Matched: ${Object.keys(playerLookup).length}, Unmatched: ${notFound.length}`);
  if (notFound.length < 30) console.log('  Unmatched:', notFound.join(', '));

  // Fetch season stats for each season
  // Sleeper endpoint: /v1/stats/nfl/player/{id}?season_type=regular&season={year}
  // Returns: { rec, rec_yd, rec_td, rush_yd, rush_td, pass_yd, pass_td, gp, ... }

  const playerStats = {}; // deltaName → { 2023: {...}, 2024: {...}, 2025: {...} }

  // Batch by season — fetch all players per season in parallel chunks
  for (const season of STAT_SEASONS) {
    console.log(`\n[DELTA] Fetching ${season} stats...`);
    const entries = Object.entries(playerLookup);
    const CHUNK   = 20; // parallel requests per batch
    let fetched   = 0;

    for (let i = 0; i < entries.length; i += CHUNK) {
      const chunk = entries.slice(i, i + CHUNK);
      await Promise.all(chunk.map(async ([name, id]) => {
        try {
          const url  = `https://api.sleeper.app/v1/stats/nfl/player/${id}?season_type=regular&season=${season}`;
          const data = await fetchJson(url);

          if (!playerStats[name]) playerStats[name] = {};

          // Extract the stats we need
          const stats = data?.stats || data || {};
          playerStats[name][season] = {
            rec:      Math.round((stats.rec      || 0) * 10) / 10,
            rec_yds:  Math.round((stats.rec_yd   || stats.rec_yds   || 0)),
            rec_td:   Math.round((stats.rec_td   || 0)),
            rush_yds: Math.round((stats.rush_yd  || stats.rush_yds  || 0)),
            rush_td:  Math.round((stats.rush_td  || 0)),
            pass_yds: Math.round((stats.pass_yd  || stats.pass_yds  || 0)),
            pass_td:  Math.round((stats.pass_td  || 0)),
            pass_int: Math.round((stats.pass_int || 0)),
            games:    Math.round((stats.gp       || stats.games     || 0)),
          };
          fetched++;
        } catch (e) {
          // Player had no stats that season — set zeros
          if (!playerStats[name]) playerStats[name] = {};
          playerStats[name][season] = null; // null = no data
        }
      }));

      // Small delay between chunks to be polite to Sleeper API
      if (i + CHUNK < entries.length) {
        await new Promise(r => setTimeout(r, 200));
      }
    }
    console.log(`[DELTA] ${season}: fetched stats for ${fetched} players`);
  }

  // Write player stats
  const output = {
    fetched:  new Date().toISOString(),
    seasons:  STAT_SEASONS,
    scoring: {
      note: 'Raw stats — PPG calculated client-side per scoring format dropdown',
      formats: {
        half_ppr_te_prem: 'RB/WR 0.5 PPR, TE 1.0 PPR, 4PT pass TD, 6PT rush/rec TD',
        full_ppr:         'All positions 1.0 PPR, 4PT pass TD, 6PT rush/rec TD',
        standard:         '0 PPR, 4PT pass TD, 6PT rush/rec TD',
      }
    },
    players: playerStats,
  };

  fs.writeFileSync(
    path.join(outDir, 'player-stats.json'),
    JSON.stringify(output, null, 2)
  );

  const kb = Math.round(JSON.stringify(output).length / 1024);
  console.log(`\n[DELTA] player-stats.json written (${kb}KB, ${Object.keys(playerStats).length} players)`);

  // Spot check PPG calculation for Josh Allen
  const allen = playerStats['Josh Allen']?.[2025];
  if (allen && allen.games > 0) {
    const pts = (allen.pass_yds * 0.04) + (allen.pass_td * 4) - (allen.pass_int * 2)
              + (allen.rush_yds * 0.1) + (allen.rush_td * 6);
    console.log(`  Josh Allen 2025: ${allen.games}g, ${(pts/allen.games).toFixed(1)} PPG (4PT pass TD, 6PT rush)`);
  }
}

// ─────────────────────────────────────────────────────────────────────────
// MAIN
// ─────────────────────────────────────────────────────────────────────────
async function main() {
  console.log(`[DELTA] Starting data fetch at ${new Date().toISOString()}\n`);

  // Step 1: Market values (FC)
  await fetchMarketValues();

  // Step 2 + 3: Sleeper player IDs + stats
  try {
    const { nameToId, idToName } = await buildPlayerIdMap();
    await fetchPlayerStats(nameToId, idToName);
  } catch (e) {
    console.warn('[DELTA] Sleeper stats fetch failed (non-fatal):', e.message);
    console.warn('[DELTA] Market values still written successfully');
  }

  console.log('\n[DELTA] All done.');
}

main().catch(err => {
  console.error('[DELTA] Fatal error:', err.message);
  process.exit(1);
});
