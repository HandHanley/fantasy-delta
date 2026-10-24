/* build-share-images.js — link-preview pictures for every NFL player (23 Oct 2026, owner).
 *
 * Runs in the Deploy Pages workflow, on the copy of the site about to be published. Draws one
 * 1200 x 630 picture per player with the engine's own dlImgPlayerOG() in a real browser (the
 * same code a phone runs, so no second drawing engine), writes p/<slug>/card.png, and points
 * that player's /p/<slug>/ page at it. Nothing is committed: the pictures live only in the
 * published site, so the repository does not grow by ~35 MB each time a number moves.
 *
 * Numbers are at the 12-team superflex anchor, like the pages' own titles. The picture holds
 * only things that rarely change in-season (no prices, no date): chat apps keep a link's
 * preview once fetched. The image address carries a short hash of the picture, so when a
 * player's picture changes, a newly pasted link fetches the new one.
 *
 * Safe to fail: the workflow step is continue-on-error, and a page is only re-pointed after
 * its picture is written. Pages without a picture keep the site-wide og-image.png.
 *
 * Usage: node scripts/build-share-images.js <site dir>      (needs the playwright package;
 *        PW_DIR = where it is installed, PW_CHROMIUM = optional browser path)
 */
const fs = require('fs'), path = require('path'), http = require('http'), crypto = require('crypto');
const SITE_URL = 'https://fantasydelta.com';
const DIR = path.resolve(process.argv[2] || '.');
const pwPath = process.env.PW_DIR ? path.join(process.env.PW_DIR, 'node_modules', 'playwright') : 'playwright';
const { chromium } = require(pwPath);

const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.css': 'text/css',
  '.png': 'image/png', '.svg': 'image/svg+xml', '.jsonl': 'text/plain', '.csv': 'text/plain', '.ico': 'image/x-icon' };

function serve(dir) {
  return new Promise((resolve) => {
    const srv = http.createServer((req, res) => {
      const rel = decodeURIComponent(req.url.split('?')[0]).replace(/^\/+/, '') || 'index.html';
      const f = path.join(dir, rel);
      if (!f.startsWith(dir) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end(); }
      res.writeHead(200, { 'Content-Type': TYPES[path.extname(f)] || 'application/octet-stream' });
      fs.createReadStream(f).pipe(res);
    });
    srv.listen(0, '127.0.0.1', () => resolve(srv));
  });
}

(async () => {
  const map = JSON.parse(fs.readFileSync(path.join(DIR, 'data', 'share-pages.json'), 'utf8'));
  const slugs = map.players || {};
  const names = Object.keys(slugs);
  if (names.length < 300) throw new Error(`share-pages.json lists only ${names.length} players; refusing`);

  const srv = await serve(DIR);
  const base = `http://127.0.0.1:${srv.address().port}/`;
  const browser = await chromium.launch(process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : {});
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  // Only this site and its fonts. Analytics must not count a build as a visit.
  await page.route('**/*', (r) => {
    const u = r.request().url();
    if (u.startsWith(base) || /^https:\/\/fonts\.(googleapis|gstatic)\.com\//.test(u)) return r.continue();
    return r.abort();
  });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(base + 'index.html', { waitUntil: 'load' });
  // Wait for the END of boot, not for ASSETS: ASSETS exists from the parse-time render on
  // baked numbers before any data file has loaded (a first test run drew 409 pictures from
  // those, model-value centre 0.935 against the site's 0.847).
  await page.waitForFunction(() => window.DL_BOOTED === true && typeof dlImgPlayerOG === 'function', null, { timeout: 120000 });
  const failed = await page.evaluate(() => (typeof DL_LOAD_FAIL !== 'undefined' ? DL_LOAD_FAIL.slice() : ['DL_LOAD_FAIL missing']));
  if (failed.length) throw new Error('data files did not load: ' + failed.join(', ') + ' — refusing to draw from fallback numbers');
  // 12-team superflex anchor, full page rebuild (renderAll does the model-value calibration).
  const set = await page.evaluate(async () => {
    leagueTeams = 12; qbFmt = 'sf'; scoringFmt = 'half_tep';
    if (typeof applyMarketForSetting === 'function') applyMarketForSetting();
    renderAll();
    const fams = ['800 64px "Nunito Sans"', '700 28px "Nunito Sans"', '600 28px "Nunito Sans"', '700 30px "Josefin Sans"', '700 30px "JetBrains Mono"', '800 120px "JetBrains Mono"'];
    try { await Promise.all(fams.map((f) => document.fonts.load(f))); } catch (e) {}
    return { t: leagueTeams, q: qbFmt, f: scoringFmt, center: MV_CENTER, n: COMP.length };
  });
  if (!(set.center > 0) || set.center === 1) throw new Error('model value calibration did not run; calls would not match the site');
  console.log(`[IMG] page ready: ${set.n} players, ${set.t}-${set.q}-${set.f}, centre ${set.center.toFixed(4)}`);

  let made = 0, skipped = 0, pointed = 0;
  const BATCH = 25;
  for (let i = 0; i < names.length; i += BATCH) {
    const batch = names.slice(i, i + BATCH);
    const out = await page.evaluate(async (ns) => {
      const r = {};
      for (const n of ns) {
        const p = COMP.find((x) => x.n === n);
        if (!p) { r[n] = null; continue; }
        const cv = await dlImgPlayerOG(p);
        r[n] = cv.toDataURL('image/png').split(',')[1];
      }
      return r;
    }, batch);
    for (const n of batch) {
      const slug = slugs[n];
      if (!out[n] || !slug) { skipped++; continue; }
      const dir = path.join(DIR, 'p', slug);
      const html = path.join(dir, 'index.html');
      if (!fs.existsSync(html)) { skipped++; continue; }
      const png = Buffer.from(out[n], 'base64');
      fs.writeFileSync(path.join(dir, 'card.png'), png);
      made++;
      const v = crypto.createHash('sha1').update(png).digest('hex').slice(0, 10);
      const src = fs.readFileSync(html, 'utf8');
      const generic = `${SITE_URL}/og-image.png`;
      const hits = src.split(generic).length - 1;
      if (hits !== 2) { console.warn(`[IMG] ${slug}: expected 2 og-image references, found ${hits}; page left as is`); continue; }
      fs.writeFileSync(html, src.split(generic).join(`${SITE_URL}/p/${slug}/card.png?v=${v}`));
      pointed++;
    }
  }
  await browser.close(); srv.close();
  console.log(`[IMG] ${made} pictures written, ${pointed} pages pointed at them, ${skipped} skipped${errors.length ? '; page errors: ' + errors.slice(0, 3).join(' | ') : ''}`);
  if (made < 300) { console.error('[IMG] fewer than 300 pictures — something is wrong'); process.exit(1); }
})().catch((e) => { console.error('[IMG] failed:', e.message); process.exit(1); });
