# P4 bikes: bike counters + MPD aggregates verdict note (issue #309, single-param demo)

Demo (#309) implements the Tallinna rattaloendurid + city mobility
MPD aggregates ingestion + P4-032 end-to-end in Tallinn
(parameters4.md P4-032 sources (1)+(2): aggregated evening foot/bike
counters, "counts only, no individuals", e.g. city mobility project
MPD aggregates where open; Tallinna rattaloendurid). Single-param: no
follow-up coverage issue uses this source (per the #309 body,
remaining 0 params).

Scope guard: sibling P4-032 legs are scored where they live —
untouched (`dims_p4_elron.py` (`elron_evening_ridership`, NULL),
`dims_p4_tlt.py` (`tlt_evening_ridership`, NULL), `dims_p4_osm.py`
(`activity`, OSM leisure-density proxy),
`dims_p4_veebi.py` (`lit_street_usage`, lit-street usage leg);
`livability.py`, WEIGHTS, shared/group files all unmodified; 3 new
files only). This module scores ONLY the counters+MPD leg
(`usage_bikes_hex`). It never touches `dims_p4_elron.py` or any
shared/group file.

## Openness verdict: dated negative (2026-09-13, re-confirmed 2026-09-16 per #309)

The §7.7 dig ran the issue's own three steps and closed with the
dig evidence (the negative that names what the counters publish
and where — itself the deliverable; P4-032 stays on OSM cycleway
proxies, `usage_bikes_hex` stays NULL):

Tallinna bike-counter counts and MPD aggregates are NOT published as
an open machine-readable bulk feed. Polite evidence, ~10 tiny requests
total (custom UA, >= 3 s pacing between same-host hits, headers +
visible-text keyword scope read only, no scraping, no auth, no TLS
bypass):

```
web search (no target load) -> Bicification (EIT Urban Mobility pilot,
  ~1 500 users, Tallinn/Istanbul/Braga, 4 months) built a municipality
  dashboard + cycling heatmaps for the city plus a "more limited,
  public" Open Data Platform per its guidebook; the project site itself
  is now unreachable (SSL certificate expired, curl (60), no bypass
  attempted) and no live pollable Tallinn aggregate endpoint surfaced
GET avaandmed.tallinn.ee/       -> HTTP 200 universal table-param API
  landing (datasets documented at the Estonian Open Data Portal)
GET avaandmed.tallinn.ee/openapi.json -> HTTP 200, confirms the
  table-param shape (no table catalogue endpoint)
GET avaandmed.tallinn.ee/data/?table=rattaloendurid&per_page=1
  -> HTTP 500 {"detail":"404: Table not found"} (a name guess, recorded
  as tried — proves only that no counter table lives under that name)
GET andmed.eesti.ee/dataset?q=rattaloendur -> HTTP 200, ~75 KB JS
  "Teabevärav" shell, 10 visible chars, 0 hits for rattaloendur/ratta/
  jalgratta/loendur/Bicification/MPD/mobility (same shell as #264/#277)
GET www.tallinn.ee/et/search?query=rattaloendur -> HTTP 301 to /et/otsing
GET www.tallinn.ee/et/otsing?query=rattaloendur -> HTTP 200, ~129 KB,
  ~7.5k visible chars; results are AJAX-loaded, server HTML has only nav
  + the query echo — no counter dataset/table/CSV/API link
GET tallinn.ee/et/liikuvus/jalgratas -> HTTP 404
GET tallinn.ee/et/liikuvus/mikromobiilsus -> HTTP 200, ~63 KB bike
  PARKING page (Bikeep rattaparklad); 0 hits for loendur/andmestik/
  avaandmed/CSV — no counter feed linked from the cycling pages
```

### Dig steps (2026-09-16, 6 tiny reads, custom UA, ≥2 s pacing, no 429)

1. Counter-publication pages behind tallinn.ee search:
   `/et/search?search_api_fulltext=rattaloendur` → 301 to
   `/et/otsing` → HTTP 200 (~130 KB): results still AJAX-loaded
   (server HTML nav-only); no counter page, but the hub links to
   `/et/uuringud-ja-statistika` (studies & statistics).
2. Chart/page bundles for data endpoints: the trail ends at the
   studies hub `uuringud.tallinn.ee` (302 → `/uuring/otsing`,
   server-rendered, `marksonad` search): exactly 1 study,
   "Tallinna rattaloendused 2021–2023" (nr 2023-16, Liikuvus).
   Its detail page carries ONE attachment —
   `Rattaloenduste_kokkuvõte_12.2023.pdf` (HEAD: attachment,
   PDF) — and the summary is MANUAL intersection counts
   (crossings nearly doubled in a year; Vana-Kalamaja +
   Reisijate/Kopli evening peak; e-scooters ~1/3), i.e. observer
   prose, not automatic-counter streams. No CSV/XLS/JSON, no
   chart bundle with a data endpoint, no counter locations, no
   deeper history.
3. Nothing keyless exists → close with this evidence: the city
   publishes a triennial PDF of manual crossing counts, not a
   counter feed; no Eco-Counter-style public dashboard surfaced.

Raw headers/pages: `/tmp/hf-p4-bikes/` (2026-09-13) +
`/tmp/hf-dig-bikes/` (2026-09-16 dig) — one-off PR records, not
committed. Pull contract: max 1 download / 24 h per cache dir
(`BIKES_TTL_S = 86400`; parameters4.md P4-032 states no cadence —
counters stream continuously, so daily per AGENTS.md §5 polite-cron
guidance), single GET, no retries — HTTP 429/errors are a stop signal.
`BIKES_BULK_URL` stays `None` until the checklist below names a
verified bulk URL; until then the fetcher performs no requests and the
scorer stays NULL with an Estonian EI OLE reason. The scored shape is
proven on fixtures only (hermetic tests).

## Honest shape (checklist / bands, NULL stays NULL)

| Param | Dim key | Window | Scored shape | NULL when |
|---|---|---|---|---|
| P4-032 usage, counters+MPD leg (demo) | `usage_bikes_hex` | listing's own hex_id, exact match | summed evening-count band: 0→30, 1–9→55, 10–49→75, ≥50→90 | no snapshot / hex not covered / hex_id missing |

Covered hex with 0 evening counts scores 30 (measured quiet, low —
never lively); missing join stays NULL. Neighbour-hex counts never
leak in. The scored reason says `hinnang` with components (hex id,
count) and the usage-not-safety label (PPA/Päästeamet pole allikas);
every NULL reason says `EI OLE` and names the missing input plus the
buyer-side check (kohapealne õhtune vaatlus). Elron/TLT ridership,
OSM leisure-density and lit-street legs are named EI OLE, never faked.

## Judgment calls (for the reviewer)

1. Single-param demo, no coverage pairing: unlike demo+coverage
   pairs, the #309 body states the remaining 0 params need no
   follow-up issue for this source — one snapshot (`hexes` roster +
   `counts` rows), one dim.
2. Hex-exact join, no buffer: "hex usage hinnang" joins the listing's
   own opaque hex_id only (rel2021 no-gradient precedent); the module
   never geocodes an address into a hex (central hook's job) —
   hex-less listings stay NULL, pinned by test.
3. Counter + MPD rows SUM per hex (both are this source's two feeds;
   `kind` informational, never filtered — unknown kinds still count
   when otherwise well-formed, pinned by test). Overlap
   double-counting (one counter + one MPD cell seeing the same
   cyclists) is unresolvable without a live feed: documented here, NOT
   solved — MUST be revisited from real histograms on reopen.
4. Periods and the feed's evening window informational, never
   filtered: freshness is the TTL / re-pull problem, not a scorer
   filter (no live table, so no latest period to pin).
5. Malformed counts skipped, never faked: negative, non-int, bool and
   absent `evening_count` values stay out (bool excluded explicitly —
   `isinstance(True, int)`), pinned by test.
6. Bands (30/55/75/90) are a first-cut judgment with no live
   calibration; the 90 cap marks the leg partial by construction.
   MUST be recalibrated from a real snapshot on reopen.
7. No shared-file edits; central hook (snapshot feed + WEIGHTS
   rebalance) stays one joint change across all batches.

## Reopening checklist (when Tallinn publishes counter/MPD bulk data)

1. Re-run the portal + tallinn.ee + studies-hub (`uuringud.tallinn.ee/uuring/otsing?marksonad=rattaloendused`) probes when the next count round lands (last round 2021–2023, published 2023); paste fresh evidence.
2. Set `BIKES_BULK_URL` to the verified bulk URL; pull one snapshot.
3. Verify the hex-id scheme + `kind` codelist + evening-window
   definition against the live feed; adjust roster/row handling.
4. Recalibrate `USAGE_BANDS` from real histograms; resolve the
   counter↔MPD overlap rule with the central hook.
5. Add the explicitly-flagged live integration test (not a unit run).
