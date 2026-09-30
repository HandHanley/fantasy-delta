// Runs DELTA's live dDOM code (index.html, from `const DDOM_SWING` to `function cfbClassName`) on each
// college season and prints, per qualified player: season, name, position, team, dDOM percentile, and the
// same percentile WITHOUT the competition adjustment (the raw dominator / ANY/A).  Used by
// scripts/college-signal-study.py.   node scripts/ddom-dump.js 2020 2021 ...
const fs = require('fs'), vm = require('vm'), path = require('path');
const ROOT = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
const a = html.indexOf('const DDOM_SWING'), b = html.indexOf('function cfbClassName');
if (a < 0 || b < 0 || b < a) throw new Error('dDOM block not found in index.html');
const sb = { Math, Map, Object, Array, CFB: null };
vm.createContext(sb);
vm.runInContext(html.slice(a, b) + ';globalThis.__D__={cfbDDOM,cfbQualifies,cfbRBDom};', sb);
const D = sb.__D__, out = [];
for (const y of process.argv.slice(2)) {
  const d = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', `college-players-${y}.json`), 'utf8'));
  const pool = Array.isArray(d.players) ? d.players : Object.values(d.players);
  const rawOf = p => p.pos === 'QB' ? p.anya : p.pos === 'RB' ? D.cfbRBDom(p) : (p.pos === 'WR' || p.pos === 'TE') ? p.dom : null;
  const byPos = {};
  pool.forEach(p => { if (D.cfbQualifies(p) && rawOf(p) != null) (byPos[p.pos] = byPos[p.pos] || []).push(rawOf(p)); });
  Object.values(byPos).forEach(v => v.sort((x, z) => x - z));
  for (const p of pool) {
    const r = D.cfbDDOM(p, pool); if (!r) continue;
    const peers = byPos[p.pos], rv = rawOf(p); let below = 0; for (const x of peers) if (x < rv) below++;
    out.push({ s: +y, n: p.n, pos: p.pos, tm: p.tm, ddom: r.pct, raw: peers.length > 1 ? Math.round(100 * below / (peers.length - 1)) : 50 });
  }
}
process.stdout.write(JSON.stringify(out));
