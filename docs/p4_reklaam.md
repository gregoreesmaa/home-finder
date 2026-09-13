# P4 välireklaam / reklaamimaks verdict note — gable ad-wall yield (P4-036 slice)

> Dated-negative verdict for issue #318 (demo, single-param).
> Checked 2026-09-13. The one param is a documented procedure-only NULL
> dim (OTA PR #131 precedent); the scorer lives in
> `services/scoring/dims_p4_reklaam.py`, pinned by
> `services/scoring/tests/test_dims_p4_reklaam.py`.

## Verdict

**No open feed — the single dim stays NULL with an Estonian
reason.** Tallinna reklaamimaks rates live in a human-readable
Riigi Teataja regulation, and välireklaam load moves through a
per-permit paigaldusluba taotlus/menetlus on tallinn.ee. There is
no public per-building exposure/load/permit table to join
politely, so there is no ingestion to cache, no TTL to state
beyond this one-off check, and no honest per-building yield band
to paint. Reklaamimaks is a per-m² cost, not yield — scoring the
tax schedule as a yield kicker would invert the param's question.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

7 tiny requests total (single GETs, labelled one-off user-agent
`home-finder openness-check (one-off, no scrape)`, paced ≥ 4 s,
headers + visible-text keyword scope read only, no form
submissions, no XHR probing). Raw bodies:
`/tmp/hf-reklaam/` (one-off PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://www.riigiteataja.ee/akt/427042018036` ("Reklaamimaks Tallinnas") → 200, 51763 B | JS-only viewer shell ("Laeb... Ilma Javascript toeta lehitsejad ei ole toetatud"); zero server-rendered text | Regulation is human law (per-m² tax rules), not a per-building dataset by construction |
| `https://www.tallinn.ee/et/search?search_api_fulltext=reklaam` (301 → `/et/otsing`) → 200, 146341 B, "Otsi \| Tallinn" | Visible text: reklaam 38x, välireklaam 11x, reklaamimaks 3x; masinloetav / csv / xlsx / json / api / X-tee / andmestik all 0 (avaandmed 2x is footer nav) | Result links are human service pages, not feeds |
| `https://www.tallinn.ee/et/teenused/valireklaami-ja-teabe-paigaldamine` ("Välireklaami ja teabe paigaldamine") → 200, 162842 B | Visible text: välireklaam 11x, reklaamimaks 5x, taotlus 20x, menetlus 7x, luba 3x; machine markers all 0 | Per-permit admin procedure (taotlus/menetlus/luba): no per-building load feed, no rate table |
| `https://andmed.eesti.ee/dataset?q=reklaam` and `?q=välireklaam` → 200 each, identical 75497 B JS "Teabevärav" shells | Zero server-rendered topical hits | No trivially pollable national-portal dataset |

Judgment call: the check stopped at storefront/procedure-page level
on purpose — no permit-register enumeration, no search-form
submission, no XHR probing, no vendor rate-card scraping. Deeper
probing is exactly the scraping this repo refuses (AGENTS.md §5).

## Sibling slices (owned elsewhere, untouched)

- **P4-036 Elering feed-in rules + mikrotootja slice:**
  `dims_p4_elering.dim_feed_in_rules`.
- **P4-036 Elektrilevi liitumiskaart export-feasibility slice:**
  `dims_p4_elektrilevi.dim_roof_export`.
- **P4-036 Maa-amet LiDAR/LoD2 roof-facet slice:**
  `dims_p4_maa_lidar.dim_roof_income`.
- **P4-036 EHR katuse slice:** `dims_p4_ehr.dim_roof_income`.
- **P4-036 Utilitas return-temp bonus slice:**
  `dims_p4_heat.dim_roof_bonus`.

This source feeds only P4-036, so there is no follow-up coverage
issue (single-param, like #262/#295).

## What stays open (overturn path, not wired here)

Tallinn (or andmed.eesti.ee) publishes a machine per-building
ad-load/permit/yield table — ideally with exposure and permit
status per address — → re-open #318, build the polite cached
ingestion (quarterly TTL per parameters4.md P4-036), and graduate
`ad_wall_yield` to a per-building upside join. Until then the
buyer-side check is: haldur + KÜ on viiluseina sobivus and
loavõimalus via the Tallinna paigaldusluba procedure.
