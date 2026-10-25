#!/usr/bin/env python3
"""
DELTA — CFBD KEY CHECK (25 Oct 2026)

One look at the CollegeFootballData key the college pipeline uses: its tier, monthly limit,
calls used and left, when the count resets, and the last 31 days of usage by endpoint. The
answers go out as GitHub annotations, because the run logs can't be read from Claude's
workspace (they sit on blob storage outside its network allowlist). Two requests, GET /info
and GET /info/usage; writes no file and commits nothing. The key is never printed.

WHY IT EXISTS: three college runs failed overnight on 25 Oct. 08:16 UTC got no box scores,
08:23 UTC got box scores for weeks 1-2 only, and 12:15 UTC got no rosters either. DELTA's own
count put October at ~435 of the free tier's 1,000 calls, so this tells a used-up limit apart
from CFBD having trouble.

Run it from the Actions tab: "CFBD Key Check" -> Run workflow. Read the result in the run's
summary annotations.
"""
import json, os, sys, urllib.request, urllib.error, collections

KEY = (os.environ.get("CFBD_API_KEY") or "").strip()
BASE = os.environ.get("CFBD_BASE") or "https://api.collegefootballdata.com"   # override only for offline tests


def scrub(s):
    s = str(s)
    return s.replace(KEY, "***") if KEY else s


def get(path):
    req = urllib.request.Request(BASE + path, headers={"Authorization": "Bearer " + KEY,
                                                       "Accept": "application/json",
                                                       "User-Agent": "DELTA/1.0 (key check)"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", errors="replace")
            return r.status, (json.loads(raw) if raw.strip() else None), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")[:400], dict(e.headers or {})
    except Exception as e:  # network, TLS, JSON
        return None, f"{type(e).__name__}: {e}", {}


def ann(level, title, msg):
    msg = scrub(msg).replace("\r", " ").replace("\n", " ")
    print(f"::{level} title={title}::{msg[:900]}")


def limit_headers(h):
    keep = {k: v for k, v in h.items() if any(w in k.lower() for w in ("limit", "remaining", "retry", "reset"))}
    return f" Response headers: {keep}." if keep else ""


if not KEY:
    ann("error", "CFBD key check", "CFBD_API_KEY is not set in this repository's secrets.")
    sys.exit(1)

failed = False

st, info, hdr = get("/info")
if st == 200 and isinstance(info, dict):
    ann("notice", "CFBD key status",
        f"Tier {info.get('tierName')} (patron level {info.get('patronLevel')}): used {info.get('usedCalls')} of "
        f"{info.get('monthlyLimit')} calls, {info.get('remainingCalls')} left, resets {info.get('resetAt')}; "
        f"shared pool {info.get('sharedPool')}." + limit_headers(hdr))
elif st == 200:
    ann("error", "CFBD key status",
        "CFBD answered /info with nothing, which it does when the key is not accepted." + limit_headers(hdr))
    failed = True
else:
    ann("error", "CFBD key status", f"GET /info -> HTTP {st}: {info}." + limit_headers(hdr))
    failed = True

st2, use, hdr2 = get("/info/usage?days=31&limit=50&api=all")
if st2 == 200 and isinstance(use, dict):
    tot, win = use.get("totals") or {}, use.get("window") or {}
    top = ", ".join(f"{e.get('endpoint')} {e.get('requests')}" for e in (use.get("topEndpoints") or [])[:8])
    rec = use.get("recentRequests") or []
    times = sorted(r.get("requestedAt") or "" for r in rec)
    by_ep = collections.Counter(r.get("endpoint") for r in rec).most_common(6)
    ann("notice", "CFBD usage, last 31 days",
        f"{tot.get('requests')} requests ({tot.get('cfbRequests')} CFB, {tot.get('cbbRequests')} CBB) from "
        f"{win.get('start')} to {win.get('end')}. Top endpoints: {top or 'none'}. "
        f"Last {len(rec)} requests ran {times[0] if times else '-'} to {times[-1] if times else '-'}: "
        + (", ".join(f"{ep} {n}" for ep, n in by_ep) or "none") + ".")
else:
    ann("warning", "CFBD usage, last 31 days", f"GET /info/usage -> HTTP {st2}: {use}." + limit_headers(hdr2))

sys.exit(1 if failed else 0)
