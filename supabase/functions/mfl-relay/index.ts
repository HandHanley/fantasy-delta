/* ═══════════════════════════════════════════════════════════════════════════
   DELTA — MyFantasyLeague relay (Supabase Edge Function: mfl-relay)
   ───────────────────────────────────────────────────────────────────────────
   WHY THIS EXISTS
     MFL's API refuses to let any web page outside myfantasyleague.com read its
     answers (tested 7 Oct 2026 from fantasydelta.com: CORS blocked, and the
     CALLBACK= script route blocked too). A server is not subject to that rule,
     so this function fetches on the page's behalf and passes the answer back.

   THE RULE: PLUMBING, NEVER SCORING
     This function fetches and forwards. It never computes a DELTA Score,
     projection, model value or call. Those stay in delta-engine.js, in the
     browser, where they are public and covered by the Engine Audit. If you are
     tempted to add a calculation here, it belongs in the engine instead.

   SOURCE OF RECORD
     This file in the repo is the source of record. The copy deployed in the
     Supabase dashboard must be a paste of this file, byte for byte. Change it
     here first, then re-paste.

   WHAT IT WILL DO, AND NOTHING ELSE
     * Public leagues only. No MFL usernames, passwords or cookies, ever.
     * Only the request types in TYPES below. Anything else is refused.
     * Only *.myfantasyleague.com, including where MFL redirects to.
     * Answers are kept for a while (TTL per type) so DELTA stays well inside
       MFL's per-server request limits. This cache lives in the function's
       memory: it is best-effort and empties whenever Supabase restarts it.
     * A simple per-visitor limit (THROTTLE_*) so one visitor cannot spend the
       shared MFL allowance for everyone.

   DEPLOY SETTING
     "Verify JWT" must be OFF for this function. It is called by visitors who
     have no DELTA account, and its safety comes from the allowlists here, not
     from a key.
   ═══════════════════════════════════════════════════════════════════════════ */

const VERSION = '2026-10-07a';

// Request types the relay will forward, and how long each answer is kept.
// `league: true` means the request needs a league ID (L=).
const TYPES: Record<string, { league: boolean; ttl: number; extra?: string }> = {
  league:          { league: true,  ttl: 60 * 60 * 1000 },        // settings, franchises — 1 hour
  rosters:         { league: true,  ttl: 10 * 60 * 1000 },        // 10 minutes
  futureDraftPicks:{ league: true,  ttl: 30 * 60 * 1000 },        // 30 minutes
  players:         { league: false, ttl: 12 * 60 * 60 * 1000 },   // MFL updates it at most daily
};

// Pages allowed to read the relay's answers.
const ORIGINS = ['https://fantasydelta.com', 'https://www.fantasydelta.com'];

const MFL_FIRST_HOST = 'api.myfantasyleague.com';
const MAX_REDIRECTS = 3;
const TIMEOUT_MS = 12000;
const MAX_BYTES = 6 * 1024 * 1024;                   // refuse anything larger
const THROTTLE_WINDOW_MS = 60 * 1000;
const THROTTLE_MAX = 40;                             // requests per visitor per minute
const CACHE_MAX_ENTRIES = 300;
const USER_AGENT = 'DELTA/1.0 (+https://fantasydelta.com)';

type FetchFn = (url: string, init?: RequestInit) => Promise<Response>;

export function isMflHost(host: string): boolean {
  host = host.toLowerCase();
  return host === 'myfantasyleague.com' || host.endsWith('.myfantasyleague.com');
}

export function makeHandler(fetchImpl: FetchFn, now: () => number = Date.now) {
  const cache = new Map<string, { at: number; ttl: number; body: string }>();
  const hits = new Map<string, number[]>();

  function corsHeaders(origin: string | null): Record<string, string> {
    const h: Record<string, string> = {
      'Vary': 'Origin',
      'X-Delta-Relay': VERSION,
    };
    if (origin && ORIGINS.includes(origin)) {
      h['Access-Control-Allow-Origin'] = origin;
      h['Access-Control-Allow-Methods'] = 'GET, OPTIONS';
      h['Access-Control-Allow-Headers'] = 'content-type';
      h['Access-Control-Max-Age'] = '86400';
    }
    return h;
  }

  function reply(status: number, obj: unknown, origin: string | null, extra: Record<string, string> = {}): Response {
    return new Response(typeof obj === 'string' ? obj : JSON.stringify(obj), {
      status,
      headers: { 'Content-Type': 'application/json; charset=utf-8', ...corsHeaders(origin), ...extra },
    });
  }

  // If the visitor's address is missing, everyone lands in one shared bucket,
  // so that bucket gets a far looser limit rather than locking out the site.
  function throttled(key: string): boolean {
    const t = now();
    const list = (hits.get(key) || []).filter((x) => t - x < THROTTLE_WINDOW_MS);
    list.push(t);
    hits.set(key, list);
    if (hits.size > 5000) hits.clear();               // never let this grow without bound
    return list.length > (key === 'unknown' ? THROTTLE_MAX * 10 : THROTTLE_MAX);
  }

  async function fetchMfl(path: string): Promise<{ status: number; body: string }> {
    let url = 'https://' + MFL_FIRST_HOST + path;
    for (let hop = 0; hop <= MAX_REDIRECTS; hop++) {
      const r = await fetchImpl(url, {
        redirect: 'manual',
        headers: { 'User-Agent': USER_AGENT, 'Accept': 'application/json' },
        signal: AbortSignal.timeout(TIMEOUT_MS),
      });
      if (r.status >= 300 && r.status < 400) {
        const loc = r.headers.get('location');
        if (!loc) throw new RelayError(502, 'MFL redirected without a destination');
        const next = new URL(loc, url);
        if (next.protocol !== 'https:' && next.protocol !== 'http:') throw new RelayError(502, 'MFL redirected to an unexpected address');
        if (!isMflHost(next.hostname)) throw new RelayError(502, 'MFL redirected outside myfantasyleague.com — refused');
        next.protocol = 'https:';
        url = next.toString();
        continue;
      }
      const len = Number(r.headers.get('content-length') || 0);
      if (len > MAX_BYTES) throw new RelayError(502, 'MFL answer too large');
      const body = await r.text();
      if (body.length > MAX_BYTES) throw new RelayError(502, 'MFL answer too large');
      return { status: r.status, body };
    }
    throw new RelayError(502, 'MFL redirected too many times');
  }

  return async function handler(req: Request): Promise<Response> {
    const origin = req.headers.get('origin');
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: corsHeaders(origin) });
    if (req.method !== 'GET') return reply(405, { error: 'GET only' }, origin);

    const q = new URL(req.url).searchParams;
    const type = q.get('type') || '';
    const spec = Object.prototype.hasOwnProperty.call(TYPES, type) ? TYPES[type] : null;
    if (!spec) return reply(400, { error: 'Unknown type. Allowed: ' + Object.keys(TYPES).join(', ') }, origin);

    const thisYear = new Date(now()).getUTCFullYear();
    const yearRaw = q.get('year') || String(thisYear);
    if (!/^\d{4}$/.test(yearRaw)) return reply(400, { error: 'year must be four digits' }, origin);
    const year = Number(yearRaw);
    if (year < 2015 || year > thisYear + 1) return reply(400, { error: 'year out of range' }, origin);

    let league = '';
    if (spec.league) {
      league = q.get('league') || '';
      if (!/^\d{1,8}$/.test(league)) return reply(400, { error: 'league must be the numeric MFL league ID' }, origin);
    }

    const who = (req.headers.get('x-forwarded-for') || '').split(',')[0].trim() || 'unknown';
    if (throttled(who)) return reply(429, { error: 'Too many requests — try again in a minute' }, origin, { 'Retry-After': '60' });

    const path = '/' + year + '/export?TYPE=' + type + (league ? '&L=' + league : '') + (spec.extra || '') + '&JSON=1';
    const key = path;
    const hit = cache.get(key);
    const maxAge = String(Math.floor(spec.ttl / 1000));
    if (hit && now() - hit.at < hit.ttl) {
      return reply(200, hit.body, origin, { 'X-Delta-Cache': 'hit', 'Cache-Control': 'public, max-age=' + maxAge });
    }

    let got: { status: number; body: string };
    try {
      got = await fetchMfl(path);
    } catch (e) {
      const status = e instanceof RelayError ? e.status : 504;
      const msg = e instanceof RelayError ? e.message : 'MFL did not answer in time';
      return reply(status, { error: msg }, origin);
    }

    if (got.status !== 200) return reply(502, { error: 'MFL returned HTTP ' + got.status }, origin);

    let parsed: unknown;
    try { parsed = JSON.parse(got.body); }
    catch { return reply(502, { error: 'MFL answer was not JSON' }, origin); }

    // MFL reports refusals (private league, bad ID) as HTTP 200 with an `error` object.
    // Pass them through so the page can say why, but never cache them.
    if (parsed && typeof parsed === 'object' && 'error' in (parsed as Record<string, unknown>)) {
      return reply(200, got.body, origin, { 'X-Delta-Cache': 'skip-error', 'Cache-Control': 'no-store' });
    }

    if (cache.size >= CACHE_MAX_ENTRIES) cache.delete(cache.keys().next().value as string);
    cache.set(key, { at: now(), ttl: spec.ttl, body: got.body });
    return reply(200, got.body, origin, { 'X-Delta-Cache': 'miss', 'Cache-Control': 'public, max-age=' + maxAge });
  };
}

class RelayError extends Error {
  status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
}

// Supabase runs this file under Deno. The guard lets the same file be tested in Node.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const denoRuntime = (globalThis as any).Deno;
if (denoRuntime && typeof denoRuntime.serve === 'function') denoRuntime.serve(makeHandler((u, i) => fetch(u, i)));
