/**
 * fetch-market-values.js
 * 
 * Fetches dynasty player values from FantasyCalc's free public API.
 * Runs inside the GitHub Action and writes data/market-values.json.
 * 
 * FantasyCalc API parameters:
 *   isDynasty=true        — dynasty values (not redraft)
 *   numQbs=2              — superflex (2 QB) scoring
 *   numTeams=12           — 12-team league
 *   ppr=1                 — full PPR
 * 
 * Adjust numQbs to 1 if your league is 1QB format.
 */

const https = require('https');
const fs = require('fs');
const path = require('path');

const API_URL = 'https://api.fantasycalc.com/values/current?isDynasty=true&numQbs=2&numTeams=12&ppr=1';
const OUTPUT_PATH = path.join(__dirname, '..', 'data', 'market-values.json');

function fetchJSON(url) {
  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          reject(new Error(`Failed to parse JSON: ${e.message}`));
        }
      });
    }).on('error', reject);
  });
}

async function main() {
  console.log('Fetching market values from FantasyCalc...');
  
  const raw = await fetchJSON(API_URL);
  console.log(`Received ${raw.length} player entries`);

  // Transform into a clean lookup object keyed by player name
  // DELTA matches players by name, so that's our key
  const values = {};
  
  for (const entry of raw) {
    const name = entry.player?.name;
    if (!name) continue;

    values[name] = {
      value: entry.value,                    // The market value number (0-10000 scale)
      overallRank: entry.overallRank,        // Overall dynasty rank
      positionRank: entry.positionRank,      // Rank within position
      position: entry.player.position,       // QB/RB/WR/TE
      team: entry.player.maybeTeam,          // NFL team abbreviation
      trend30Day: entry.trend30Day,          // Value change over last 30 days
      sleeperId: entry.player.sleeperId,     // Sleeper player ID (useful for Phase 2)
    };
  }

  // Add metadata so DELTA knows when this data was fetched
  const output = {
    fetchedAt: new Date().toISOString(),
    source: 'FantasyCalc',
    format: 'dynasty-superflex-12team-fullppr',
    playerCount: Object.keys(values).length,
    values,
  };

  // Make sure the data directory exists
  fs.mkdirSync(path.dirname(OUTPUT_PATH), { recursive: true });
  fs.writeFileSync(OUTPUT_PATH, JSON.stringify(output, null, 2));

  console.log(`✓ Wrote ${Object.keys(values).length} player values to ${OUTPUT_PATH}`);
  console.log(`  Fetched at: ${output.fetchedAt}`);
}

main().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
