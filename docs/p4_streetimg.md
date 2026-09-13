# P4 crowdsourced street imagery — openness verdict + demo/coverage note (issues #303, #372)

> Verdict date: 2026-09-13 (all probes single polite fetches, cached
> `/tmp/hf-p4-streetimg/`, ≥ 4 s pacing, contact UA
> `home-finder-research/0.1 (polite openness probe; GitHub
> gregoreesmaa/home-finder issue 303)` in headers; no scraping, no bulk).
> Code: `services/scoring/dims_p4_streetimg.py` (demo P4-029 + 2 coverage
> params); tests:
> `services/scoring/tests/test_dims_p4_streetimg.py` (hermetic, synthetic
> fixtures, no network).

## Verdict

| Source | Result | Evidence (2026-09-13) |
|---|---|---|
| Mapillary **developer docs** (API v4 surfaces, auth, rate limits) | **OPEN** | `GET www.mapillary.com/developer/api-documentation` → HTTP 200, 156 271 B. Documents two surfaces (vector tiles + entity endpoints), the 2026-04-02 **Image Radius Search** (`lat`/`lng`, radius default/max **50 m**, limit default 1/max **100**, "best" by proximity+recency+360° preference — the exact per-listing primitive this ingestion uses), the 2026-01-16 bbox ceiling (< 0.01°²), and rate limits (**60 000/min/app** on entity APIs — orders above our one-request-per-listing cadence) |
| Mapillary **Terms of Use** (effective 2024-02-15) | **OPEN-CONDITIONAL** | `GET www.mapillary.com/terms` → HTTP 200, 135 225 B. Other users' content under **CC BY-SA** "unless we indicate otherwise" (some datasets CC BY-NC-SA — comply per dataset); APIs covered by the Terms; scraping/data-mining "not approved by Mapillary" — pulls go through the token API, never page scraping |
| Mapillary **token gate** (first-hand) | **GATED, as documented** | `GET graph.mapillary.com/images?bbox=24.75,59.43,24.76,59.44&limit=1` (one tiny Tallinn-window probe, no token) → `{"error":{"message":"Invalid OAuth 2.0 Access Token","type":"MLYApiException","code":190,…}}`. Endpoint live, OAuth 2.0 client/user token required (free app registration; token from env at pull time, NEVER committed) |
| KartaView docs + API | **DATED PARTIAL-NEGATIVE** | `GET kartaview.org/` and `/api-documentation` → HTTP 200 yet **2 159 B** of `Loading KartaView...` (JS SPA shell, not curl-verifiable); `GET doc.kartaview.org/` → 301 → `kartaview.org/doc` → HTTP 200, again 2 159 B of shell. V3 API surface was cut back in June 2024 (third-party reports). Consequence: schema accepts `kartaview`-sourced frames (gap-fill lands without code changes) but **no KartaView pull is attempted** until its endpoint is re-verified |

Re-verify annually (TTL 365 d); a re-opened KartaView endpoint flips the
gap-fill leg without code changes (schema already carries `source`).

## Pull policy (polite, cached, TTL-stated)

- One request per listing per run via `build_radius_search_url`
  (radius clamped 1–50 m, limit 1–100 per the API ceilings); 25 s
  timeout; contact UA on every request.
- `fetch_cached` (docs/terms) / `fetch_mapillary` (token-gated frames):
  fresh cache wins (no request); transport errors are raised and
  **never cached as data**; HTTP 429 raises immediately (stop signal, no
  retry). The token arrives per call (env) and is never logged or cached.
- TTLs: imagery **30 d** (coverage grows continuously; matches the
  Overpass POI-cache precedent), terms/docs re-verify **365 d**.
- Captured dates come from `captured_at` (ms epoch → YYYY-MM-DD,
  `parse_image_search`, pure); `distance_m` is added by the caller with
  its own haversine (the requested fields carry no per-image
  coordinates). No scraped listing dumps — fixtures only.

## Per-param wiring (all honest shapes = per-listing dim with photo date)

| Param | Wired leg (this ingestion) | Legs honestly missing (EI OLE, named not faked) |
|---|---|---|
| P4-029 block observer (demo) | nearest date-stamped frame + facade/issues + OSM sidewalk cross-check; issues/bad facade → 40, sidewalk-only doubt → 55, stale (> 2 y) cap 60, undated cap 65, fresh clean → 75 | no frame at all → NULL (never a street verdict off zero frames) |
| P4-022 photo forensics | 4-leg cross-check: street-frame facade truth (eye-level, dated) + image-hash dupes + EXIF daylight + photo/EHR room-count; 2+ flags → 30, 1 → 55, clean → 80 | any leg with no data; zero legs → NULL (never a clean bill off zero evidence) |
| P4-040 arrival sequence | date-stamped last-200 m approach frames + lamp/footway legs; weak lamp/footway → 45, clean fresh → 70, stale/undated cap 60; peak-end framing in every reason | no frame inside the 200 m window → NULL even when farther frames exist (the window IS the param); safety registers excluded by design (arrival feel ≠ safety claim) |

Never a gradient: no distance weighting, no interpolation; P4-040 `none`
has no neutral-present band — an uncovered window is NULL, not a guess.

## Pairing + overlap notes (for the reviewer)

- Demo + coverage share ONE PR because #372's body states it extends the
  #303 demo ingestion ("no new plumbing expected") — same precedent as
  #384 (#244 demo + #328 coverage) and #246/#330.
- Same param, different legs — sibling files UNTOUCHED:
  `dims_p4_osm` scores P4-029/P4-040 as mapped walkability proxies
  (footway/sidewalk/lit tags, no frames); `dims_p4_maa_aerial` scores
  P4-022/P4-029 off aerial vintages (top-down change, no eye-level);
  `dims_p4_own_store` keeps P4-029/P4-040 NULLs naming this source as
  missing — this module provides it. The weight-rebalance follow-up
  merges the legs; nothing here double-pushes the sort on its own.
- No livability/WEIGHTS/layers edits — integration and rebalancing stay
  one joint follow-up (existing tests pin WEIGHTS).
- `opencellid.token`, `.agents/`, scraped dumps, and `.worktrees/`
  contents are never committed (repo hygiene per AGENTS.md §5).
