/**
 * DELTA Live Market Values — Fetch Script
 * Runs nightly via GitHub Actions
 * Fetches FantasyCalc dynasty SF 12-team 1PPR values for:
 *   - All players (RAW array updates)
 *   - Pick tier anchors (slot pick rescaling)
 * Writes to data/market-values.json
 */

const https = require('https');
const fs = require('fs');
const path = require('path');

const FC_URL = 'https://api.fantasycalc.com/values/current?isDynasty=true&numQbs=2&numTeams=12&ppr=1&includePicksAsPlayers=true';

function fetch(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; DELTA/1.0)',
        'Accept': 'application/json',
      }
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch (e) { reject(new Error(`JSON parse failed: ${e.message}`)); }
      });
    });
    req.on('error', reject);
    req.setTimeout(30000, () => { req.destroy(); reject(new Error('Timeout')); });
  });
}

async function main() {
  console.log(`[DELTA] Fetching FantasyCalc values at ${new Date().toISOString()}`);

  const data = await fetch(FC_URL);

  if (!Array.isArray(data) || data.length === 0) {
    throw new Error(`Unexpected response format: ${JSON.stringify(data).slice(0, 200)}`);
  }

  console.log(`[DELTA] Received ${data.length} entries from FantasyCalc`);

  // Build values map: name → {value, overallRank, positionRank, trend30Day, position, team}
  const values = {};
  let playerCount = 0;
  let pickCount = 0;

  for (const item of data) {
    const name = item?.player?.name;
    const value = item?.value;
    if (!name || value === undefined) continue;

    const isPick = name.includes('Round Pick') || name.includes('round pick');

    values[name] = {
      value: Math.round(value),
      overallRank: item.overallRank || null,
      positionRank: item.positionRank || null,
      trend30Day: item.trend30Day || 0,
      position: item?.player?.position || null,
      team: item?.player?.maybeTeam || null,
    };

    if (isPick) pickCount++;
    else playerCount++;
  }

  console.log(`[DELTA] Processed: ${playerCount} players, ${pickCount} picks`);

  // Ensure output directory exists
  const outDir = path.join(process.cwd(), 'data');
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

  const output = {
    fetched: new Date().toISOString(),
    playerCount,
    pickCount,
    totalCount: playerCount + pickCount,
    values,
  };

  const outPath = path.join(outDir, 'market-values.json');
  fs.writeFileSync(outPath, JSON.stringify(output, null, 2));
  console.log(`[DELTA] Written to ${outPath} (${Math.round(JSON.stringify(output).length / 1024)}KB)`);

  // Log a few key players for verification
  const checks = ['Josh Allen', 'Brock Bowers', 'Jeremiyah Love', 'Carnell Tate', '2026 1st Round Pick'];
  console.log('\n[DELTA] Spot check:');
  for (const name of checks) {
    const v = values[name] || values[name + ' (Early)'];
    if (v) console.log(`  ${name}: ${v.value} (rank #${v.overallRank})`);
    else console.log(`  ${name}: NOT FOUND`);
  }
}

main().catch(err => {
  console.error('[DELTA] Fetch failed:', err.message);
  process.exit(1);
});
