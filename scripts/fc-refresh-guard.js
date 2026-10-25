/**
 * DELTA — FantasyCalc refresh guard (25 Oct 2026)
 *
 * WHY: FantasyCalc's terms (the 10 Oct 2026 version, as other projects quote it; the owner's
 * research notes are in the Claude Project, claude/RESEARCH-monetization-terms.md) allow each
 * unique set of query parameters to be refreshed no more than once every three hours.
 * DELTA's schedule never comes close (07:20 UTC daily, plus 03:20 UTC on season Mondays),
 * but hand re-runs did: 7 runs in the 30 days to 24 Oct came within three hours of the one
 * before, the closest 16 minutes apart. Owner, 24 Oct: "it doesn't need to be that frequent."
 *
 * HOW: both scripts that call FantasyCalc (fetch-market-values.js and
 * fetch-scarcity-validation.js) ask this first. The clock is each script's own saved file:
 * the time it wrote when its last full pull finished. Inside the window, the script keeps
 * that file and asks FantasyCalc for nothing, so everything downstream reads the same file
 * it read last time (the market history replaces a same-date entry rather than adding one).
 *
 * It pulls anyway, and says why, when the file is missing or unreadable, carries no time,
 * is an empty or sample placeholder, or carries a time in the future (a bad clock must never
 * freeze the data). A pull that failed partway wrote nothing and so leaves no time behind;
 * in that rare case a re-run can ask again for the settings it already got through.
 */
const fs = require('fs');
const path = require('path');

const MIN_HOURS = 3;
const FUTURE_TOLERANCE_MS = 5 * 60 * 1000;

function recentPull(file, field, now = Date.now()) {
  const name = path.basename(file);
  let j;
  try { j = JSON.parse(fs.readFileSync(file, 'utf8')); }
  catch (e) { return { recent: false, why: `no readable ${name}` }; }
  if (!j || typeof j !== 'object') return { recent: false, why: `${name} is not an object` };
  if (j.playerCount === 0 || j.sample === true) return { recent: false, why: `${name} is a placeholder` };
  const t = Date.parse(j[field]);
  if (!Number.isFinite(t)) return { recent: false, why: `${name} has no ${field} time` };
  const ageMs = now - t;
  if (ageMs < -FUTURE_TOLERANCE_MS) return { recent: false, why: `${name} ${field} time ${j[field]} is in the future` };
  const hours = Math.max(0, ageMs) / 3600000;
  return { recent: hours < MIN_HOURS, hours, at: j[field], why: '' };
}

module.exports = { MIN_HOURS, recentPull };
