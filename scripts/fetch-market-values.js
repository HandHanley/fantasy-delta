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

// Minimum entries per grid slice. FantasyCalc returns ~474 per setting (11 Aug 2026)
// with includePicksAsPlayers=true. sliceFromResponse() only ever threw on an EMPTY or
// non-array response, so a degraded-but-non-empty reply — 20 players instead of 474 —
// wrote cleanly, committed, and shipped. The freeze pre-flight would catch it a layer
// later; the live site would not. Floor at ~75% so roster churn cannot trip it.
const MIN_PER_SLICE = 350;

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

/**
 * Append one line per night to data/market-price-log.jsonl.
 *
 * Records the DEFAULT SETTING ONLY (12-SF). The full grid is eight times the
 * size for information that is almost perfectly correlated across settings —
 * FantasyCalc reprices the whole board together. The freeze captures the full
 * grid once, which is what the basis-independence argument actually needs; the
 * nightly series only has to show MOVEMENT over time.
 *
 * Stores value and overall rank per player. Rank matters because raw values
 * drift as the pool changes (picks convert to players, veterans retire), so a
 * player can hold identical real-world value and show a different number. Rank
 * is immune to that, and it is what the 2027 comparison is graded on.
 *
 * JSONL, append-only: one line per day keeps it diffable, and a bad run
 * corrupts a single line rather than the file.
 */
function appendPriceLog(settings, defaultKey) {
  const slice = settings[defaultKey];
  if (!slice) { console.warn('[DELTA] price log: default slice missing, skipped'); return; }
  try {
    const players = {};
    for (const [name, v] of Object.entries(slice)) {
      if (!v || v.value == null) continue;
      players[name] = [v.value, v.overallRank || null];   // array, not object: ~40% smaller
    }
    const line = JSON.stringify({
      date: new Date().toISOString().slice(0, 10),
      ts: new Date().toISOString(),
      setting: defaultKey,
      n: Object.keys(players).length,
      players,
    });
    const p = path.join(process.cwd(), 'data', 'market-price-log.jsonl');

    // One line per DAY. A re-run on the same date replaces that day's line
    // rather than appending a duplicate, so a manual workflow_dispatch does not
    // put two rows on one date and quietly skew any future series analysis.
    const today = new Date().toISOString().slice(0, 10);
    let prior = [];
    if (fs.existsSync(p)) {
      prior = fs.readFileSync(p, 'utf8').split('\n').filter(Boolean)
        .filter(l => { try { return JSON.parse(l).date !== today; } catch (e) { return true; } });
    }
    fs.writeFileSync(p, prior.concat(line).join('\n') + '\n');
    const kb = Math.round(fs.statSync(p).size / 1024);
    console.log(`[DELTA] price log: ${Object.keys(players).length} players at ${defaultKey} ` +
                `(${prior.length + 1} days recorded, ${kb}KB)`);
  } catch (e) {
    // Never fail the run over the observability log — fresh market data
    // publishing matters more than the archive.
    console.warn('[DELTA] price log append failed:', e.message);
  }
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
        const n     = Object.keys(slice).length;
        if (n < MIN_PER_SLICE)
          throw new Error(`only ${n} entries (expected ~474) — degraded response, refusing to ship`);
        settings[key] = slice;
        console.log(`[DELTA]   ${key}: ${n} entries`);
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

  // Append-only history. Runs AFTER the grid is safely written, so a problem
  // here can never cost us the fresh market data.
  appendPriceLog(settings, DEFAULT);
}

main().catch(e => { console.error('[DELTA] FATAL:', e.message); process.exit(1); });
