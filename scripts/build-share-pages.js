#!/usr/bin/env node
/**
 * DELTA — Player Link Previews (16 Oct 2026, owner: text previews + a Share button).
 *
 * WHY: a link preview (iMessage, Slack, Discord, X) is built by a robot that reads the page's
 * <meta> tags and runs NO JavaScript. player.html is one page that fills the player in after it
 * loads, so every player link previewed as the same generic "DELTA - Player Card".
 *
 * WHAT THIS WRITES, every night after the data refresh:
 *   p/<slug>/index.html      one tiny page per NFL player: his own title + description, then an
 *                            immediate hand-off to /player.html?name=<name>. A person never sees it.
 *   data/share-pages.json    { name: slug } so the player page knows which short link exists.
 * Pages for players no longer in the universe are deleted, so the folder never goes stale.
 *
 * NUMBERS: the DELTA Score and the call come from the real engine, run headlessly the same way
 * build-scorecard.js does it, at the anchor format the site defaults to (12-team superflex,
 * half PPR + TE premium). The preview says so. Text only, with the shared og-image.png
 * (owner: per-player picture cards can come later on top of this).
 *
 *   node scripts/build-share-pages.js           build
 *   node scripts/build-share-pages.js --check   build into a temp folder, write nothing to the repo
 */
'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm'), os = require('os');

const ROOT = path.resolve(__dirname, '..');
const SITE = 'https://fantasydelta.com';
const CHECK = process.argv.includes('--check');
const OUT_DIR = CHECK ? fs.mkdtempSync(path.join(os.tmpdir(), 'share-')) : path.join(ROOT, 'p');
const MAP_OUT = CHECK ? path.join(OUT_DIR, 'share-pages.json') : path.join(ROOT, 'data', 'share-pages.json');

async function bootEngine() {
  const src = fs.readFileSync(path.join(ROOT, 'delta-engine.js'), 'utf8') + `
;globalThis.__H__={ get COMP(){return COMP}, get BUILD(){return DL_BUILD},
  tag:(p)=>{ const m=(vTag(p)||'').match(/>([a-z ]+)<\\/span>/); return m?m[1]:''; },
  rookieHold:(p)=>typeof dlRookieHold==='function'&&dlRookieHold(p),
  set:(t,q,f)=>{ leagueTeams=t; qbFmt=q; scoringFmt=f; }, recompute:()=>applyMarketForSetting(),
  /* renderAll() in index.html calibrates model value in two passes: measure the population
     center on the raw basis, then divide it out. Without this every model value is raw and
     231 of 409 calls came out different from the site (found 16 Oct by comparing all 409). */
  center:()=>{ MV_CENTER=1; MV_CENTER=computeMvCenter(); return MV_CENTER; },
  boot:async()=>{ await loadLiveMarketValues(); await loadPlayerStats(); await loadPlayerContracts();
    await loadRipples();
    if(typeof loadInjuryOverrides==='function'){ try{ await loadInjuryOverrides(); }catch(e){} }
    if(typeof loadQBStarters==='function'){ try{ await loadQBStarters(); }catch(e){} }
    if(typeof ensureStartData==='function'){ try{ await ensureStartData(); }catch(e){} }
    applyMarketForSetting(); } };`;
  const sb = {
    console: { log: () => {}, warn: () => {}, error: () => {} }, setTimeout, Date, Math, JSON, Promise, URLSearchParams,
    location: { search: '' },
    fetch: async (u) => {
      const rel = String(u).replace(/\?.*$/, '').replace(/^\.?\//, '');
      const p = path.join(ROOT, rel);
      if (!fs.existsSync(p)) return { ok: false, status: 404 };
      const body = fs.readFileSync(p, 'utf8');
      return { ok: true, json: async () => JSON.parse(body), text: async () => body };
    },
    localStorage: { getItem: () => null, setItem: () => {} },
    document: { getElementById: () => null, createElement: () => ({ style: {} }), body: { appendChild: () => {} }, querySelectorAll: () => [] },
  };
  sb.window = sb; sb.globalThis = sb; vm.createContext(sb); vm.runInContext(src, sb);
  const H = sb.__H__; await H.boot(); H.set(12, 'sf', 'half_tep'); H.recompute();
  const c = H.center();
  if (!(c > 0) || c === 1) throw new Error('model value calibration did not run (center ' + c + '); calls would not match the site');
  return H;
}

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const titleCase = (s) => s.replace(/\b[a-z]/g, (c) => c.toUpperCase());
function slugify(n) {
  return n.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
    .replace(/['’.]/g, '').replace(/&/g, ' and ').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
}

function pageHTML(x) {
  const url = `${SITE}/p/${x.slug}/`;
  const dest = `/player.html?name=${encodeURIComponent(x.n)}`;
  return `<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(x.title)}</title>
<meta name="description" content="${esc(x.desc)}">
<link rel="canonical" href="${url}">
<meta name="theme-color" content="#0A0F1A">
<meta property="og:type" content="profile">
<meta property="og:site_name" content="DELTA">
<meta property="og:title" content="${esc(x.title)}">
<meta property="og:description" content="${esc(x.desc)}">
<meta property="og:url" content="${url}">
<meta property="og:image" content="${SITE}/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="${esc(x.title)}">
<meta name="twitter:description" content="${esc(x.desc)}">
<meta name="twitter:image" content="${SITE}/og-image.png">
<meta http-equiv="refresh" content="0; url=${esc(dest)}">
<script>location.replace(${JSON.stringify(dest)});</script>
</head><body style="background:#0A0F1A;color:#EAF0F4;font-family:system-ui,sans-serif;padding:24px">
<a href="${esc(dest)}" style="color:#2DD4BF">Open ${esc(x.n)} on DELTA</a>
</body></html>
`;
}

async function main() {
  const H = await bootEngine();
  const players = H.COMP.filter((p) => ['QB', 'RB', 'WR', 'TE'].includes(p.pos));
  if (players.length < 300) throw new Error(`only ${players.length} players from the engine; refusing to rewrite the pages`);

  // slugs: one per player, unique; a clash gets the position added and is reported, never silently shared
  const bySlug = {}, out = [];
  for (const p of players) {
    let slug = slugify(p.n);
    if (!slug) { console.warn(`[SHARE] no slug for "${p.n}", skipped`); continue; }
    if (bySlug[slug]) { const alt = `${slug}-${p.pos.toLowerCase()}`; console.warn(`[SHARE] slug clash "${slug}" (${bySlug[slug]} / ${p.n}) -> ${alt}`); slug = alt; }
    if (bySlug[slug]) { console.warn(`[SHARE] second clash on "${slug}", ${p.n} skipped`); continue; }
    bySlug[slug] = p.n;
    const hold = H.rookieHold(p), tag = H.tag(p);
    const call = hold ? 'Rookie Hold' : (tag ? titleCase(tag) : '');
    const ds = Math.round(p.dsScore || 0);
    const team = p.t && p.t !== 'FA' ? p.t : 'Free agent';
    const title = `${p.n} · DELTA Score ${ds}${call ? ' · ' + call : ''}`;
    const desc = `${p.pos} · ${team} · Age ${(+p.a || 0).toFixed(1)}. DELTA Score ${ds} of 100`
      + (call ? `, ${call.toLowerCase().startsWith('rookie') ? 'a ' + call : 'a ' + call + ' call'}` : '')
      + ' at 12-team superflex. DELTA rates what a player has actually done: production, age, opportunity and contract.';
    out.push({ n: p.n, slug, title, desc });
  }

  // write: fresh pages, then remove any page whose player is gone
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const keep = new Set(out.map((x) => x.slug));
  for (const x of out) {
    fs.mkdirSync(path.join(OUT_DIR, x.slug), { recursive: true });
    fs.writeFileSync(path.join(OUT_DIR, x.slug, 'index.html'), pageHTML(x));
  }
  let removed = 0;
  for (const d of fs.readdirSync(OUT_DIR, { withFileTypes: true })) {
    if (d.isDirectory() && !keep.has(d.name) && fs.existsSync(path.join(OUT_DIR, d.name, 'index.html'))) {
      fs.rmSync(path.join(OUT_DIR, d.name), { recursive: true, force: true }); removed++;
    }
  }
  const map = {}; for (const x of out) map[x.n] = x.slug;
  fs.writeFileSync(MAP_OUT, JSON.stringify({ generated: new Date().toISOString(), engine: H.BUILD, base: '/p/', players: map }));
  console.log(`[SHARE] ${out.length} player pages written${removed ? `, ${removed} stale removed` : ''} (engine ${H.BUILD})${CHECK ? ' — CHECK MODE, into ' + OUT_DIR : ''}`);
  const s = out.find((x) => x.n === 'Bijan Robinson') || out[0];
  console.log(`[SHARE] sample /p/${s.slug}/  title: ${s.title}`);
  console.log(`[SHARE]   desc: ${s.desc}`);
}

main().catch((e) => { console.error('[SHARE] failed:', e.message); process.exit(1); });
