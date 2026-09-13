# P4 paaste verdict: Päästeamet (P4-012 demo + 6-param coverage)

Closes #276 (demo) and #350 (coverage) — paired in one PR because the
coverage body states it extends the demo ingestion; no new plumbing was
needed beyond the demo's `coverage` argument (said here as required).

## 1. Openness verdict (2026-09-13, KEEP — dated negative counts)

Three polite single GETs (UA `home-finder-p4-paaste-probe/1.0`,
`--max-time 20`, no retries), cached to `/tmp/hf-paaste-cache`:

| # | URL | Result |
|---|-----|--------|
| 1 | `https://www.rescue.ee/` | **OPEN, human HTML, no key.** `HTTP/2 200`, `content-type: text/html`, 142 568 bytes. Links to `/et/statistika`. |
| 2 | `https://www.rescue.ee/et/statistika` | **OPEN as human HTML hub only.** `HTTP/2 200`, 132 491 bytes, `<title>Statistika - Päästeamet</title>`. Links to KOV-level stats (`statistika-kohalikele-omavalitsustele`), `päästesündmuste-statistika`, the national-portal query `avaandmed.eesti.ee/datasets?ih=paasteamet`, and a Recommy dashboard embed. **No dataset file download**: zero `csv/xls/json/xml/api` dataset hrefs (only hit was `/et/manifest.json`, the PWA manifest) — cross-check reference only, never ingested. |
| 3 | `https://www.rescue.ee/et/juhend/avaandmed` | **OPEN catalogue of named open datasets.** `HTTP/2 200`, 134 612 bytes, `<title>Mõiste ja kasutustingimused - Avaandmed - Päästeamet</title>`. Lists metsa-/maastikutulekahjud, suurõnnetuse-ohuga ja ohtlikud ettevõtted, veevõtukohad, veeohutuse stendid, avalikud varjumiskohad via the national Teabevärav. Human pages, no direct machine endpoint pulled. |
| 4 | Machine event feed (csv/json/xml/api) | **NOT located in the three pulls above (dated negative, kept).** No extra hunting per polite-automation rules. Consequence: point inventories are caller-supplied until a future adapter owns them; dims score honest shapes on fixtures and NULL honestly without data. |

Commands run (evidence):

```bash
mkdir -p /tmp/hf-paaste-cache && cd /tmp/hf-paaste-cache
UA="home-finder-p4-paaste-probe/1.0 (Estonia open-data openness check, single polite pull)"
curl -sS -A "$UA" --max-time 20 -D home.headers -o home.html "https://www.rescue.ee/"
# HTTP:200 SIZE:142568 TYPE:text/html
curl -sS -A "$UA" --max-time 20 -D stats.headers -o statistika.html \
  "https://www.rescue.ee/et/statistika"
# HTTP:200 SIZE:132491 TYPE:text/html, title "Statistika - Päästeamet"
curl -sS -A "$UA" --max-time 20 -D ava.headers -o avaandmed.html \
  "https://www.rescue.ee/et/juhend/avaandmed"
# HTTP:200 SIZE:134612 TYPE:text/html, dataset catalogue, no machine downloads
```

## 2. Ingestion contract (what the demo implements end-to-end)

`services/scoring/dims_p4_paaste.py`: `fetch_stats_snapshot()`
(polite, cache-first, `PAASTE_CACHE_TTL_S = 30 d` — stats move
monthly/annual per parameters4.md P4-012 TTL, so at most one live
pull/month) → `parse_stats_snapshot()` (pure: hub sub-page tables +
portal query + dashboard links, fixture-tested) → the monthly archiver
accumulates snapshots → `coverage` dict (stats catalogue +
caller-resolved linnaosa/season/zone tables) → the seven dims.
Transport errors raise and never touch the cache; HTTP 429 stops the
run. Cache file: `<cache-dir>/paasteamet-statistika.html` (default dir
`/tmp/hf-paaste-cache`).

## 3. Per-param honest shapes (never a measured gradient — no machine feed)

| Param | Shape | No-input / missing-input behaviour |
|-------|-------|------------------------------------|
| P4-012 blackspots + drive-time (demo) | Point-buffer count bands (500 m: 0→75, 1→60, 2–3→40, 4+→20) + straight-line komando penalty (−10 past 5 km) | NULL naming the missing Transpordiamet/Päästeamet inventory + Tark Tee check; module holds NO komando coordinates, computes NO routed time |
| P4-015 insurability (fire slice) | Linnaosa zone join (madal→70, keskmine→50, kõrge→25) + illiquidity flag on kõrge | NULL naming the missing zone table + insurer check; flood/theft legs NOT joined; unknown class → NULL |
| P4-042 smoke cells | Coarse 800 m cell flag, capped 45, inside-only | NULL outside any cell (absence of notices ≠ clean air) |
| P4-047 small horrors | City-wide calendar bands (0→75, 1–2→60, 3–5→45, 6+→30 notices/yr), origin-independent like the ilm baseline | NULL naming the missing calendar + noise/tilihooldus checks |
| P4-058 falling ice | Dated 300 m notice flag with season recency (current→35, previous→45, older→55, undated→45) | NULL outside any notice; no wall-clock in scorers (caller season) |
| P4-059 burn restriction | Rule join (keelatud→20, piiratud→50, lubatud→75) | NULL naming the missing rule table; EHR stove leg NOT joined; unknown rule → NULL |
| P4-062 hex watch (ice slice) | Coarse 500 m hex-flag read, capped 40, inside-only | NULL outside; rat leg NOT joined and named; never addresses |

All NULL reasons say `hinnang` + `EI OLE` and name the buyer-side
check. No Overpass fragment / tag mapping: Päästeamet data is not OSM
data, and the point inventories are caller-supplied until a future
adapter owns them — inventing either would be dishonest plumbing. No
WEIGHTS / livability / layers / docs changes (joint rebalancing stays
a joint change).

## 4. Judgment calls for the reviewer

1. Demo+coverage in ONE PR (AGENTS.md §3 says one issue per PR): the
   coverage issue body explicitly states it extends the demo ingestion,
   so splitting would review the same ingestion twice (ilm #308/#374
   and heat #261/#342 precedent). Both issues close here.
2. Scorers take `(origin, pois, coverage=None)` — the optional third
   argument is the coverage-anticipated new plumbing: zone/rule tables
   and the event calendar have no honest snapshot channel, and stuffing
   linnaosa tables into OSM POIs would abuse the POI channel.
3. P4-012 pairs the buffer count with the komando penalty because the
   demo param asks both halves ("is this crossing safe"); a count
   without the drive-time half would fake completeness. The penalty is
   straight-line only, labelled as such.
4. P4-042/P4-058/P4-062 score ONLY inside their cells/notices/flags;
   outside reads NULL rather than a clean/safe score. Never-a-gradient
   applies to absence too.
5. Band edges, radii (500/800/300/500 m), the 5 km station line, and
   season-string recency are coarse judgments, documented in the module
   docstring — challengeable, dull by design.
6. Test inventories (komando names/coords, notice streets, hex ids) are
   synthetic fixtures (clearly labelled) — real observed values appear
   only in §1 above, never as ingested data.

## 5. DoD evidence (observed 2026-09-13, worktree `276-p4-paaste`)

```text
$ python3 -m pytest services/scoring/tests/test_dims_p4_paaste.py -q
.........................s                                               [100%]
25 passed, 1 skipped in 0.04s

$ python3 -m pytest services/scoring/tests -q
........................................................................ [ 88%]
.......s................................................................ [ 94%]
........................................................................ [ 99%]
..                                                                       [100%]
1295 passed, 3 skipped in 8.99s
```

- Hermetic: default suite makes zero network calls; the single live
  pull runs only with `HF_LIVE_PAASTE=1` (env-gated, skipped otherwise
  — the 1 skip above).
- New files only: `services/scoring/dims_p4_paaste.py`,
  `services/scoring/tests/test_dims_p4_paaste.py`, `docs/p4_paaste.md`.
  No edits to shared files (`livability.py`, WEIGHTS, layers,
  `docs/layers.md`, `docs/nomap.md`, `parameters4.md` — untouched).

## 6. Layer #493: komando-point overlay (dated-NEGATIVE feed → honest-empty layer)

Group B verify-first follow-up: are station locations open, build a
point overlay; response-time gradients are NOT mappable either way.
Verdict 2026-09-13: **stations NOT open as a machine feed — the layer
ships honest-empty (zero points, never invented stations).**

Four polite single GETs (probe UA
`home-finder-p4-paaste-probe/1.0`, `--max-time 20`, no retries,
cache `/tmp/hf-paaste-feed`):

| # | URL | Result |
|---|-----|--------|
| 1 | `https://avaandmed.eesti.ee/datasets?ih=paasteamet` | **301 → new Teabevärav** (`https://andmed.eesti.ee/datasets?ih=paasteamet`): HTTP 200, 75 497 bytes, `<title>Teabevärav</title>` — JS app shell, **zero server-rendered dataset records**, zero `komando/station` mentions, zero dataset/download/api hrefs. No machine list without browser rendering (out of scope per polite-automation rules). |
| 2 | `https://www.rescue.ee/et/kontaktid` | **OPEN, human HTML org tree, no key.** HTTP 200, 131 740 bytes, `<title>Kontaktid - Päästeamet</title>`. Links per päästekeskus (`pohja/laane/louna/ida_paastekeskus`), zero coordinates/geojson. |
| 3 | `https://www.rescue.ee/et/kontaktid/pohja_paastekeskus` | **OPEN, addresses WITHOUT coordinates (dated negative).** HTTP 200, 133 950 bytes: komando names + street addresses (`Erika tn 3, Tallinn`), `latitude/longitude` × 0, map embeds × 0. Addresses are not points — hand-geocoding them would invent stations. |
| 4 | Response-time gradient feed | **NOT mappable (dated negative, kept).** No routed-time source located in pulls 1–3; the P4-012 scorer keeps the straight-line penalty only and says `linnulennult (hinnang, mitte marsruudi-aeg)`. |

What ships (`apps/web/lib/layers_paaste.ts`, `PAASTE-HOOK (#493)` blocks
in `layers.ts`/`overlays.ts`/`server/snapshot.ts`):

* Layer `paaste` (`paramIds: []` + `paramLabel: "P4-012"` — the
  senscom #484 precedent; parameters3 p12 stays schools): bands spec
  `{radiusM: 5000, 60/60/60}` — the coverage twin of the scorer's
  komando leg (`STATION_FAR_KM` parity; flat 60 because response comes
  from the NEAREST komando, extras do not stack; capped because
  proximity is coverage, never safety). PROVISIONAL + dormant (zero
  points → all-NaN unknown everywhere, pinned by test).
* `fallbackPoints: []` BY HONESTY — the demo fallback plots zero
  markers; absence renders as absence. `PAASTE_TAGS` is prose, NOT an
  Overpass fragment (Päästeamet data is not OSM data). No
  `derived-paaste.json` sidecar, no builder, no raster/metro master:
  the route takes the designed 500 → demo-empty path (pinned:
  `SnapshotUnavailable` + null raster in `layers_paaste.test.ts`).
* Title/source/legend all say `hinnang` + `EI OLE` + the buyer-side
  check (rescue.ee kontaktid + Tark Tee + kohapeal).

## 7. Reopening checklist (when feeds change)

* Päästeamet publishes komando coordinates (Teabevärav dataset with
  geometry, or a rescue.ee machine list) → add a polite adapter +
  `derived-paaste.json` sidecar, recalibrate the provisional 60-band,
  joint WEIGHTS rebalancing (per-batch rebalancing stays one joint
  change) — PLUS revisit the two paaste-specific page paths that are
  correct ONLY while the fetch never succeeds: the demo-empty branch
  in `app/layers/page.tsx` (stale points become legitimate again) and
  the bands distance suffix (currently the generic branch; a komando
  wording replaces the DIY one).
* Real routed response times appear → NEW param work; never backfill
  drive time from straight-line distance (a komando 3 km away across
  the bay is not 3 km away by road).
* OSM `amenity=fire_station` stays OUT of scope for this layer even
  then: community-mapped furniture is not the official komando
  inventory (same rule as §1 row 4 — inventing the fragment would be
  dishonest plumbing).
