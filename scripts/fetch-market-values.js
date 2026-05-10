/**
 * DELTA Live Market Values — Fetch Script
 * Runs nightly via GitHub Actions
 * Fetches FantasyCalc dynasty SF 12-team 1PPR values for players and picks
 * Writes to data/market-values.json
 * 
 * Player stats are handled separately by scripts/fetch-player-stats.py
 */

const https = require('https');
const fs    = require('fs');
const path  = require('path');

const FC_URL = 'https://api.fantasycalc.com/values/current?isDynasty=true&numQbs=2&numTeams=12&ppr=1&includePicksAsPlayers=true';

function fetchUrl(url) {
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
        catch (e) { reject(new Error(`JSON parse failed: ${e.message}`)); }
      });
    });
    req.on('error', reject);
    req.setTimeout(30000, () => { req.destroy(); reject(new Error('Timeout')); });
  });
}

async function main() {
  console.log(`[DELTA] Fetching FantasyCalc values at ${new Date().toISOString()}`);

  const outDir = path.join(process.cwd(), 'data');
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

  const data = await fetchUrl(FC_URL);
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
      position:     item?.player?.position  || null,
      team:         item?.player?.maybeTeam || null,
    };
    if (isPick) pickCount++; else playerCount++;
  }

  const output = {
    fetched:     new Date().toISOString(),
    playerCount,
    pickCount,
    totalCount:  playerCount + pickCount,
    values,
  };

  fs.writeFileSync(
    path.join(outDir, 'market-values.json'),
    JSON.stringify(output, null, 2)
  );

  console.log(`[DELTA] market-values.json written — ${playerCount} players, ${pickCount} picks`);

  // Spot check
  const checks = ['Josh Allen', 'Brock Bowers', 'Jeremiyah Love', 'Carnell Tate'];
  console.log('[DELTA] Spot check:');
  for (const name of checks) {
    const v = values[name];
    console.log(`  ${name}: ${v ? v.value + ' (rank #' + v.overallRank + ')' : 'NOT FOUND'}`);
  }
}

main().catch(err => {
  console.error('[DELTA] Fatal error:', err.message);
  process.exit(1);
});
