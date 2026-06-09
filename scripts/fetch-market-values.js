/**
 * DELTA Live Market Values — Fetch Script (per-format grid)
 * Runs via GitHub Actions.
 *
 * Fetches FantasyCalc dynasty values across the league-size × QB-format grid
 * that the app's dropdowns expose: teams {8,10,12,14} × qb {1qb, sf}.
 * This lets the app compare DELTA's model value against the MARKET value in
 * the SAME format the user selected — instead of dividing a format-reactive
 * model by a market frozen at one setting (which made every QB read "strong
 * sell" in shallow 1QB).
 *
 * PPR is held at 1 to reproduce the prior 12-SF anchor bit-for-bit; the
 * model's 12-SF anchor (player.k) is unchanged, so default-setting behaviour
 * does not move. FantasyCalc cannot represent TE-premium, so the scoring
 * (PPR/TEP) axis remains a separate, deliberately-pinned concern.
 *
 * Output: data/market-values.json
 *   { fetched, ppr, playerCount, default:"12|sf",
 *     settings: { "T|Q": { name: {value, overallRank, positionRank,
 *                                  trend30Day, position, team} } } }
 */

const https = require('https');
const fs    = require('fs');
const path  = require('path');

const PPR     = 1;                       // hold scoring axis fixed (matches prior anchor)
const TEAMS   = [8, 10, 12, 14];
const QBS     = ['1qb', 'sf'];           // 1qb -> numQbs=1, sf -> numQbs=2
const DEFAULT = '12|sf';                 // model anchor + pick-scaling basis

const fcUrl = (teams, qb) =>
  `https://api.fantasycalc.com/values/current?isDynasty=true` +
  `&numQbs=${qb === 'sf' ? 2 : 1}&numTeams=${teams}&ppr=${PPR}` +
  `&includePicksAsPlayers=true`;

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

function sliceFromResponse(data) {
  if (!Array.isArray(data) || !data.length) throw new Error('Bad FC response');
  const out = {};
  for (const item of data) {
    const name  = item?.player?.name;
    const value = item?.value;
    if (!name || value == null) continue;
    out[name] = {
      value:        Math.round(value),
      overallRank:  item.overallRank  || null,
      positionRank: item.positionRank || null,
      trend30Day:   item.trend30Day   || 0,
      position:     item?.player?.position  || null,
      team:         item?.player?.maybeTeam || null,
    };
  }
  return out;
}

async function main() {
  console.log(`[DELTA] Fetching FantasyCalc grid at ${new Date().toISOString()} (ppr=${PPR})`);

  const outDir = path.join(process.cwd(), 'data');
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

  const settings = {};
  for (const teams of TEAMS) {
    for (const qb of QBS) {
      const key = `${teams}|${qb}`;
      try {
        const data  = await fetchUrl(fcUrl(teams, qb));
        const slice = sliceFromResponse(data);
        settings[key] = slice;
        console.log(`[DELTA]   ${key}: ${Object.keys(slice).length} entries`);
      } catch (e) {
        console.error(`[DELTA]   ${key}: FAILED — ${e.message}`);
        throw e; // fail the run rather than ship a partial grid
      }
      await new Promise(r => setTimeout(r, 400)); // be polite to the API
    }
  }

  if (!settings[DEFAULT]) throw new Error(`Default setting ${DEFAULT} missing from grid`);

  const out = {
    fetched:     new Date().toISOString(),
    ppr:         PPR,
    default:     DEFAULT,
    playerCount: Object.keys(settings[DEFAULT]).length,
    settings,
  };

  const outPath = path.join(outDir, 'market-values.json');
  fs.writeFileSync(outPath, JSON.stringify(out));
  const kb = Math.round(fs.statSync(outPath).size / 1024);
  console.log(`[DELTA] Wrote ${outPath} — ${Object.keys(settings).length} settings, ` +
              `${out.playerCount} players at default, ${kb}KB`);
}

main().catch(e => { console.error('[DELTA] FATAL:', e.message); process.exit(1); });
