/* ═══════════════════════════════════════════════════════════════════════════
   DELTA — local-first account sync
   ───────────────────────────────────────────────────────────────────────────
   LOAD ORDER MATTERS. This file is loaded AFTER delta-engine.js and is never
   allowed in front of first paint. The pre-paint theme script in index.html
   (~line 470) reads localStorage synchronously and must stay exactly as it is.
   Nothing here runs until DSYNC.init() is called at the end of boot.

   THE CONTRACT, in one line:
     localStorage remains the source of truth for rendering. The cloud is a
     backup that reconciles in the background.

   Consequences of that contract, all deliberate:
     * Every push* function is a NO-OP when signed out. That is what makes it
       safe to wire the hooks into dwToggle/saveLeaguePrefs/setTheme now, before
       any of the auth UI exists — anonymous users are completely unaffected.
     * Nothing here ever writes to localStorage during normal operation except
       the sync metadata. Pulls hand data to the app's own setters.
     * A failed network call is logged and forgotten. It must never surface as
       a broken page. The user keeps working locally and the next write retries.

   WHY delta_sync_meta EXISTS:
     Last-write-wins needs to know when the LOCAL copy last changed, and none
     of the existing localStorage keys carry a timestamp. This file adds one
     small bookkeeping key. It is the only new local key.
   ═══════════════════════════════════════════════════════════════════════════ */

var DSYNC = (function () {
  'use strict';

  // ── Config ────────────────────────────────────────────────────────────────
  // The publishable key is DESIGNED to ship in client code. It is not a secret.
  // Safety comes from row-level security in the database, not from hiding this.
  // The secret key (sb_secret_...) must never appear in this file or any file
  // in the repo.
  var SUPABASE_URL  = 'https://zpashsoixmsbzvvuodro.supabase.co';
  var SUPABASE_KEY  = 'sb_publishable_hwGjxh5PXKlD95i_e_4i9Q_VZzb9s_G';
  var SUPABASE_LIB  = 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2';

  // Existing localStorage keys, mirrored from the app. Kept as constants so a
  // rename shows up here as one edit rather than five scattered string typos.
  var LS_SETTINGS = 'delta_settings';
  var LS_THEME    = 'delta_theme';
  var LS_WATCH    = 'delta_watchlist';
  var LS_SLEEPER  = 'delta_sleeper';
  var LS_META     = 'delta_sync_meta';   // new; this file only

  var DEBOUNCE_MS = 1200;   // settings clicks arrive in bursts; coalesce them

  // ── Internal state ────────────────────────────────────────────────────────
  var sb       = null;    // supabase client, null until the library loads
  var user     = null;    // { id, email } when signed in
  var status   = 'idle';  // idle | loading | signed-out | syncing | ready | error
  var lastErr  = null;
  var listeners = [];
  var timers   = {};
  var booted   = false;

  function log() {
    if (typeof console === 'undefined') return;
    var a = Array.prototype.slice.call(arguments);
    console.log.apply(console, ['[dsync]'].concat(a));
  }

  function setStatus(s, err) {
    status = s; lastErr = err || null;
    for (var i = 0; i < listeners.length; i++) {
      try { listeners[i]({ status: status, user: user, error: lastErr }); }
      catch (e) { /* a broken listener must not break sync */ }
    }
  }

  // ── localStorage helpers (never throw; Safari private mode throws on set) ──
  function lsGet(k)      { try { return localStorage.getItem(k); }        catch (e) { return null; } }
  function lsSet(k, v)   { try { localStorage.setItem(k, v); }            catch (e) {} }
  function lsJSON(k, d)  { try { return JSON.parse(lsGet(k) || 'null') || d; } catch (e) { return d; } }

  function meta() { return lsJSON(LS_META, {}); }
  function metaSet(field, ts) {
    var m = meta();
    m[field] = ts || Date.now();
    lsSet(LS_META, JSON.stringify(m));
  }

  /* Mark local state as changed. Called by the app's own save paths via the
     touch() hooks below, so the merge can tell which side is newer. */
  function touch(field) { metaSet(field, Date.now()); }

  // ── Shape helpers ─────────────────────────────────────────────────────────
  /* The watchlist on disk is an array of "ns:name" strings (see dwRaw in
     delta-engine.js). The table stores ns and player as separate columns.
     These two functions are the only place that translation happens. */
  function watchLocalToRows(uid) {
    var arr = lsJSON(LS_WATCH, []);
    if (!Array.isArray(arr)) return [];
    var out = [], seen = {};
    for (var i = 0; i < arr.length; i++) {
      var e = arr[i];
      if (typeof e !== 'string' || !e) continue;
      var ix = e.indexOf(':');
      var ns = ix < 0 ? 'nfl' : e.slice(0, ix);          // legacy bare entry
      var pl = ix < 0 ? e     : e.slice(ix + 1);
      if (!pl) continue;
      if (ns !== 'nfl' && ns !== 'cfb') continue;        // matches the CHECK constraint
      var k = ns + ':' + pl;
      if (seen[k]) continue;
      seen[k] = 1;
      out.push({ user_id: uid, ns: ns, player: pl });
    }
    return out;
  }

  function watchRowsToLocal(rows) {
    var out = [], seen = {};
    for (var i = 0; i < rows.length; i++) {
      var k = rows[i].ns + ':' + rows[i].player;
      if (seen[k]) continue;
      seen[k] = 1;
      out.push(k);
    }
    return out;
  }

  /* Sleeper: localStorage holds ONE connection object; the table holds many
     leagues. The single local connection becomes the active row. */
  function connToRow(uid, conn, active) {
    return {
      user_id: uid,
      league_id: String(conn.leagueId),
      league_name: conn.leagueName || null,
      season: conn.season ? String(conn.season) : null,
      roster_id: (conn.rosterId === null || conn.rosterId === undefined)
        ? null : parseInt(conn.rosterId, 10),
      team_name: conn.teamName || null,
      sleeper_user_id: conn.userId ? String(conn.userId) : null,
      username: conn.username || null,
      is_active: !!active
    };
  }

  function rowToConn(row) {
    return {
      leagueId: row.league_id,
      leagueName: row.league_name,
      season: row.season,
      rosterId: row.roster_id,
      teamName: row.team_name,
      userId: row.sleeper_user_id,
      username: row.username
    };
  }

  // ── Library loading (lazy, never blocks paint) ─────────────────────────────
  function loadLib() {
    return new Promise(function (resolve, reject) {
      if (window.supabase && window.supabase.createClient) return resolve();
      var s = document.createElement('script');
      s.src = SUPABASE_LIB;
      s.async = true;
      s.onload = function () {
        if (window.supabase && window.supabase.createClient) resolve();
        else reject(new Error('supabase-js loaded but createClient missing'));
      };
      s.onerror = function () { reject(new Error('failed to load supabase-js')); };
      document.head.appendChild(s);
    });
  }

  // ═════════════════════════════════════════════════════════════════════════
  //  MERGE — the correctness-critical part
  // ═════════════════════════════════════════════════════════════════════════
  /*  Scenario this exists for: someone uses DELTA anonymously on a laptop for
      months, then signs in on a phone that ALSO has local state. Both sides
      have real data and neither is obviously authoritative.

      RULES, and the reasoning behind each:

      watchlist  → UNION. Never lose a watched player. A two-year college
                   scouting list is the single most expensive thing to lose and
                   the cheapest to over-keep: an unwanted extra name costs one
                   click to remove, a lost name may never be remembered.
                   TRADEOFF, accepted knowingly: a player removed on device A
                   while signed out can reappear after signing in on device B.
                   Once signed in, removals delete the row and propagate.

      settings   → NEWER TIMESTAMP WINS, with one exception below.
      theme        These are single scalars, trivially re-set by hand, so the
                   simple rule is fine.

      EXCEPTION — legacy local state with no recorded timestamp:
                   Existing users have localStorage keys but no delta_sync_meta
                   (it did not exist before this build). For those, local time
                   is unknown. We treat unknown as OLDER than the cloud, so the
                   cloud wins for settings/theme. That is the safe direction:
                   worst case someone re-picks a theme. The watchlist is
                   unaffected because it unions regardless.

      NO LOCAL KEY AT ALL → cloud wins outright. A fresh browser must never
                   push its defaults over a real account.

      leagues    → UNION by league_id. Active league: local's if the local
                   connection exists, else whatever the cloud had.  */

  function mergeScalar(localVal, localTs, cloudVal, cloudTs, hasLocalKey) {
    if (!hasLocalKey)            return { value: cloudVal, source: 'cloud' };
    if (cloudVal === null ||
        cloudVal === undefined)  return { value: localVal, source: 'local' };
    if (!localTs)                return { value: cloudVal, source: 'cloud' };  // legacy, unknown age
    if (!cloudTs)                return { value: localVal, source: 'local' };
    return (localTs > cloudTs)
      ? { value: localVal, source: 'local' }
      : { value: cloudVal, source: 'cloud' };
  }

  function mergeWatchlists(localRows, cloudRows) {
    var seen = {}, merged = [], toPush = [];
    var i, k;
    for (i = 0; i < cloudRows.length; i++) {
      k = cloudRows[i].ns + ':' + cloudRows[i].player;
      if (seen[k]) continue;
      seen[k] = 'cloud';
      merged.push({ ns: cloudRows[i].ns, player: cloudRows[i].player });
    }
    for (i = 0; i < localRows.length; i++) {
      k = localRows[i].ns + ':' + localRows[i].player;
      if (seen[k]) continue;
      seen[k] = 'local';
      merged.push({ ns: localRows[i].ns, player: localRows[i].player });
      toPush.push(localRows[i]);          // exists locally only → send up
    }
    return { merged: merged, toPush: toPush };
  }

  function mergeLeagues(localConn, cloudRows) {
    var byId = {}, order = [], i;
    for (i = 0; i < cloudRows.length; i++) {
      byId[cloudRows[i].league_id] = cloudRows[i];
      order.push(cloudRows[i].league_id);
    }
    var activeId = null;
    for (i = 0; i < cloudRows.length; i++) {
      if (cloudRows[i].is_active) { activeId = cloudRows[i].league_id; break; }
    }
    var newRow = null;
    if (localConn && localConn.leagueId) {
      var lid = String(localConn.leagueId);
      activeId = lid;                                  // local connection wins as active
      if (!byId[lid]) { newRow = localConn; order.push(lid); }
    }
    return { activeId: activeId, newLocalLeague: newRow, ids: order, byId: byId };
  }

  // ═════════════════════════════════════════════════════════════════════════
  //  PULL / PUSH
  // ═════════════════════════════════════════════════════════════════════════
  async function pullAndMerge() {
    if (!sb || !user) return;
    setStatus('syncing');
    var uid = user.id;

    var res = await Promise.all([
      sb.from('user_state').select('settings,theme,updated_at').eq('user_id', uid).maybeSingle(),
      sb.from('watchlist').select('ns,player').eq('user_id', uid),
      sb.from('sleeper_leagues').select('*').eq('user_id', uid)
    ]);

    var stateRes = res[0], watchRes = res[1], leagueRes = res[2];
    if (stateRes.error)  throw stateRes.error;
    if (watchRes.error)  throw watchRes.error;
    if (leagueRes.error) throw leagueRes.error;

    var m         = meta();
    var cloudTs   = stateRes.data && stateRes.data.updated_at
                      ? Date.parse(stateRes.data.updated_at) : 0;
    var cloudState = stateRes.data || {};
    var cloudWatch = watchRes.data || [];
    var cloudLeag  = leagueRes.data || [];

    // ---- settings ----------------------------------------------------------
    var hasLocalSettings = lsGet(LS_SETTINGS) !== null;
    var localSettings    = lsJSON(LS_SETTINGS, null);
    var s = mergeScalar(localSettings, m.settings, cloudState.settings, cloudTs, hasLocalSettings);
    if (s.source === 'cloud' && s.value) {
      lsSet(LS_SETTINGS, JSON.stringify(s.value));
      if (typeof window.dsyncApplySettings === 'function') window.dsyncApplySettings(s.value);
    }

    // ---- theme -------------------------------------------------------------
    var hasLocalTheme = lsGet(LS_THEME) !== null;
    var t = mergeScalar(lsGet(LS_THEME), m.theme, cloudState.theme, cloudTs, hasLocalTheme);
    if (t.source === 'cloud' && t.value) {
      lsSet(LS_THEME, t.value);
      if (typeof window.dlThemeApply === 'function') window.dlThemeApply(t.value);
    }

    // ---- watchlist ---------------------------------------------------------
    var localWatch = watchLocalToRows(uid);
    var w = mergeWatchlists(localWatch, cloudWatch);
    lsSet(LS_WATCH, JSON.stringify(watchRowsToLocal(w.merged)));
    if (w.toPush.length) {
      var wr = await sb.from('watchlist').upsert(w.toPush, { onConflict: 'user_id,ns,player' });
      if (wr.error) log('watchlist push failed:', wr.error.message);
    }

    // ---- sleeper leagues ---------------------------------------------------
    var localConn = lsJSON(LS_SLEEPER, null);
    var lg = mergeLeagues(localConn, cloudLeag);
    if (lg.newLocalLeague) {
      var lr = await sb.from('sleeper_leagues')
        .upsert([connToRow(uid, lg.newLocalLeague, false)], { onConflict: 'user_id,league_id' });
      if (lr.error) log('league push failed:', lr.error.message);
    }
    if (lg.activeId) {
      // RPC, not a direct update: the partial unique index allows one active
      // league per user, so turning B on while A is on fails. See schema §4b.
      var ar = await sb.rpc('set_active_league', { p_league_id: lg.activeId });
      if (ar.error) log('set_active_league failed:', ar.error.message);
      if (!localConn && lg.byId[lg.activeId]) {
        lsSet(LS_SLEEPER, JSON.stringify(rowToConn(lg.byId[lg.activeId])));
      }
    }

    // If local won a scalar, make sure the cloud reflects it.
    if (s.source === 'local' || t.source === 'local') await pushState(true);

    setStatus('ready');
    log('merge complete —',
        'settings:', s.source, 'theme:', t.source,
        'watchlist:', w.merged.length, '(' + w.toPush.length + ' pushed)',
        'leagues:', lg.ids.length);
  }

  function debounce(key, fn) {
    if (timers[key]) clearTimeout(timers[key]);
    timers[key] = setTimeout(function () { timers[key] = null; fn(); }, DEBOUNCE_MS);
  }

  async function pushState(immediate) {
    if (!sb || !user) return;                      // no-op when signed out
    var body = {
      user_id: user.id,
      settings: lsJSON(LS_SETTINGS, {}) || {},
      theme: lsGet(LS_THEME) || 'teal'
    };
    var r = await sb.from('user_state').upsert([body], { onConflict: 'user_id' });
    if (r.error) { log('state push failed:', r.error.message); setStatus('error', r.error); }
    else if (!immediate) setStatus('ready');
  }

  // ═════════════════════════════════════════════════════════════════════════
  //  PUBLIC API
  // ═════════════════════════════════════════════════════════════════════════
  return {
    /* Called once, AFTER first paint. Safe to call when the user has never
       signed in — it resolves to signed-out and does nothing further. */
    init: async function () {
      if (booted) return;
      booted = true;
      setStatus('loading');
      try {
        await loadLib();
        sb = window.supabase.createClient(SUPABASE_URL, SUPABASE_KEY, {
          auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true }
        });
        sb.auth.onAuthStateChange(function (event, session) {
          var was = user ? user.id : null;
          user = session && session.user
            ? { id: session.user.id, email: session.user.email } : null;
          if (user && user.id !== was) {
            pullAndMerge().catch(function (e) {
              log('merge failed:', e.message); setStatus('error', e);
            });
          } else if (!user) {
            setStatus('signed-out');
          }
        });
        var sess = await sb.auth.getSession();
        if (sess.data && sess.data.session) {
          user = { id: sess.data.session.user.id, email: sess.data.session.user.email };
          await pullAndMerge();
        } else {
          setStatus('signed-out');
        }
      } catch (e) {
        // Sync is optional. A failure here must leave the app fully usable.
        log('init failed (app continues locally):', e.message);
        setStatus('error', e);
      }
    },

    signInGoogle: async function () {
      if (!sb) return { error: new Error('sync not ready') };
      return sb.auth.signInWithOAuth({
        provider: 'google',
        options: { redirectTo: window.location.origin + window.location.pathname }
      });
    },

    signInEmail: async function (email) {
      if (!sb) return { error: new Error('sync not ready') };
      return sb.auth.signInWithOtp({
        email: email,
        options: { emailRedirectTo: window.location.origin + window.location.pathname }
      });
    },

    /* Sign out leaves ALL local data in place on purpose. Signing out is not
       "delete my stuff" — the user keeps working anonymously with exactly what
       they had a moment ago. */
    signOut: async function () {
      if (!sb) return;
      await sb.auth.signOut();
      user = null;
      setStatus('signed-out');
    },

    // ---- hooks called by the app's existing save paths --------------------
    // Each one records the local change time, then syncs if signed in.
    // All are no-ops for anonymous users beyond the local timestamp.
    noteSettings: function () { touch('settings'); debounce('state', function () { pushState(); }); },
    noteTheme:    function () { touch('theme');    debounce('state', function () { pushState(); }); },

    noteWatch: function (ns, player, watched) {
      touch('watchlist');
      if (!sb || !user) return;
      var row = { user_id: user.id, ns: ns || 'nfl', player: player };
      var p = watched
        ? sb.from('watchlist').upsert([row], { onConflict: 'user_id,ns,player' })
        : sb.from('watchlist').delete()
            .eq('user_id', user.id).eq('ns', row.ns).eq('player', player);
      Promise.resolve(p).then(function (r) {
        if (r && r.error) log('watch sync failed:', r.error.message);
      });
    },

    noteSleeperConnect: function (conn) {
      touch('leagues');
      if (!sb || !user || !conn || !conn.leagueId) return;
      sb.from('sleeper_leagues')
        .upsert([connToRow(user.id, conn, false)], { onConflict: 'user_id,league_id' })
        .then(function (r) {
          if (r.error) { log('league upsert failed:', r.error.message); return; }
          return sb.rpc('set_active_league', { p_league_id: String(conn.leagueId) });
        })
        .then(function (r) { if (r && r.error) log('set active failed:', r.error.message); });
    },

    /* Disconnect clears the LOCAL connection only. The saved league stays in
       the account — that is the whole point of multi-league. Removing a league
       from the account is a separate, explicit action. */
    noteSleeperDisconnect: function () { touch('leagues'); },

    forgetLeague: async function (leagueId) {
      if (!sb || !user) return;
      var r = await sb.from('sleeper_leagues').delete()
        .eq('user_id', user.id).eq('league_id', String(leagueId));
      if (r.error) log('forget league failed:', r.error.message);
    },

    listLeagues: async function () {
      if (!sb || !user) return [];
      var r = await sb.from('sleeper_leagues').select('*').eq('user_id', user.id)
        .order('updated_at', { ascending: false });
      if (r.error) { log('list leagues failed:', r.error.message); return []; }
      return (r.data || []).map(function (row) {
        var c = rowToConn(row); c.isActive = row.is_active; return c;
      });
    },

    switchLeague: async function (leagueId) {
      if (!sb || !user) return { error: new Error('not signed in') };
      var r = await sb.rpc('set_active_league', { p_league_id: String(leagueId) });
      if (r.error) return r;
      var rows = await sb.from('sleeper_leagues').select('*')
        .eq('user_id', user.id).eq('league_id', String(leagueId)).maybeSingle();
      if (rows.data) lsSet(LS_SLEEPER, JSON.stringify(rowToConn(rows.data)));
      return { data: rows.data || null, error: null };
    },

    // ---- introspection for the UI ----------------------------------------
    onChange: function (cb) { listeners.push(cb); cb({ status: status, user: user, error: lastErr }); },
    state:    function () { return { status: status, user: user, error: lastErr }; },
    isSignedIn: function () { return !!user; },

    // exposed for testing only
    _merge: { scalar: mergeScalar, watchlists: mergeWatchlists, leagues: mergeLeagues,
              watchLocalToRows: watchLocalToRows, watchRowsToLocal: watchRowsToLocal,
              connToRow: connToRow, rowToConn: rowToConn }
  };
})();
