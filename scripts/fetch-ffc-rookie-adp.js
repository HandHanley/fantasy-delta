#!/usr/bin/env node
/*
 * DELTA rookie-draft ADP fetcher  —  ONE-OFF RESEARCH TOOL, NOT PART OF THE APP.
 *
 * Pulls Fantasy Football Calculator's Dynasty Rookie ADP (12-team, all positions) for every year
 * they publish — 2014 onward — and writes one file per year to data/fixtures/, with FFC's response
 * kept EXACTLY as returned, inside a small wrapper saying where and when it came from.
 *
 * Why: the Future First study (docs/PREREG-future-first.md, in design) needs rookie-draft order for
 * classes older than DynastyProcess's history (which starts with usable IDs in 2020).
 *
 * Source and terms: https://help.fantasyfootballcalculator.com/article/42-adp-rest-api —
 * "Use of the ADP REST API is free for personal and commercial use", with a request for attribution
 * and not to call it too often (it updates once a day). This script makes ONE call per year, a
 * second apart, and is run by hand. Every file carries the attribution line.
 * ⚠ FFC's ADP comes from MOCK drafts on its own site (human picks only), not real leagues.
 *
 * NOTHING IN THE APP READS THESE FILES — which is why its workflow is NOT in the Deploy Pages list.
 *
 * Usage:
 *   node scripts/fetch-ffc-rookie-adp.js                        # 2014 .. current year
 *   node scripts/fetch-ffc-rookie-adp.js --years 2014-2019
 *   node scripts/fetch-ffc-rookie-adp.js --from-dir test/ffc    # no network: reads <dir>/rookie-<year>.json
 */
const fs = require('fs');
const path = require('path');

const API = 'https://fantasyfootballcalculator.com/api/v1/adp/rookie';
const OUT_DEFAULT = path.join(__dirname, '..', 'data', 'fixtures');
const FIRST_YEAR = 2014;               // first year in FFC's rookie year selector
const TEAMS = 12;
const PAUSE_MS = 1000;
const ATTRIBUTION = 'ADP data courtesy of Fantasy Football Calculator — https://fantasyfootballcalculator.com';

function parseArgs(argv) {
  const now = new Date().getUTCFullYear();
  const args = { from: FIRST_YEAR, to: now, out: OUT_DEFAULT, fromDir: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--years') {
      const m = /^(\d{4})(?:-(\d{4}))?$/.exec(argv[++i] || '');
      if (!m) throw new Error('--years takes YYYY or YYYY-YYYY');
      args.from = +m[1]; args.to = +(m[2] || m[1]);
    } else if (a === '--out') { args.out = argv[++i]; }
    else if (a === '--from-dir') { args.fromDir = argv[++i]; }
    else throw new Error(`unrecognised argument: ${a}`);
  }
  if (args.from > args.to) throw new Error('--years: first year is after the last');
  return args;
}

const urlFor = y => `${API}?teams=${TEAMS}&year=${y}&position=all`;

function source(args) {
  if (args.fromDir) {
    return {
      get: async y => {
        const f = path.join(args.fromDir, `rookie-${y}.json`);
        if (!fs.existsSync(f)) throw new Error(`no stub file ${f}`);
        return JSON.parse(fs.readFileSync(f, 'utf8'));
      },
      pause: async () => {},
    };
  }
  return {
    get: async y => {
      const r = await fetch(urlFor(y), { headers: { 'User-Agent': 'DELTA research fetch (fantasydelta.com)' } });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    },
    pause: () => new Promise(res => setTimeout(res, PAUSE_MS)),
  };
}

// A short, shape-tolerant summary for the log. The file keeps the response untouched either way.
function summarise(resp) {
  const players = Array.isArray(resp && resp.players) ? resp.players : [];
  const meta = (resp && resp.meta) || {};
  const pick = k => (meta[k] !== undefined ? meta[k] : '?');
  return {
    players: players.length,
    drafts: pick('total_drafts'),
    window: `${pick('start_date')} to ${pick('end_date')}`,
    status: (resp && resp.status) || '?',
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const src = source(args);
  fs.mkdirSync(args.out, { recursive: true });
  const ok = [], failed = [];
  for (let y = args.from; y <= args.to; y++) {
    try {
      const resp = await src.get(y);
      const s = summarise(resp);
      if (s.players === 0) throw new Error(`no players in response (status ${s.status})`);
      const payload = {
        source: 'fantasyfootballcalculator', format: 'rookie', teams: TEAMS, year: y,
        url: urlFor(y), fetched: new Date().toISOString(), attribution: ATTRIBUTION,
        response: resp,
      };
      const file = path.join(args.out, `ffc-rookie-adp-${y}.json`);
      fs.writeFileSync(file, JSON.stringify(payload, null, 1));
      ok.push(y);
      console.log(`[FFC] ${y}: ${s.players} players · ${s.drafts} drafts · ${s.window} -> ${path.relative(process.cwd(), file)}`);
    } catch (e) {
      failed.push(y);
      console.log(`[FFC] ${y}: FAILED — ${e.message}`);
    }
    if (y < args.to) await src.pause();
  }
  console.log(`[FFC] saved ${ok.length} year(s)${failed.length ? `; failed: ${failed.join(', ')}` : ''}`);
  if (ok.length === 0) process.exit(1);
}

main().catch(err => { console.error('FAILED:', err.message); process.exit(1); });
