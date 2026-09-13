# Overturn #234 — G2 EHR bulk per-code join (p21/30/33/35/48/79/154/495)

Date: 2026-09-13. Pipeline: `services/scoring/dims_overturn_ehr.py`
(tests: `services/scoring/tests/test_dims_overturn_ehr.py`, 14 hermetic tests).

## Bulk-ingest attempt (polite, /tmp cache, TTL stated)

One GET per endpoint, `home-finder-verification` User-Agent, 2026-09-13
~13:3x UTC. Nothing was cached (no bulk payload exists to cache).

| Probe | Result |
|---|---|
| `curl https://www.eehitus.ee/infoportal` | HTTP 301 → `https://eehitus.digitaalehitus.ee/` |
| `curl https://eehitus.digitaalehitus.ee/` | HTTP 200, 695188 bytes — cluster marketing site, no CSV endpoint |
| `curl https://livekluster.ehr.ee/ui/ehr/v1` | HTTP 200, 3663-byte JS shell — live platform UI, login-gated |
| `curl https://koodivaramu.eesti.ee/mkm-ehr/ehr-v1` | HTTP 302 → `.../users/sign_in` — sign-in-gated, no anonymous bulk |
| andmed.eesti.ee CKAN `/api/3/action` | HTTP 404 "Cannot GET" (#333 precedent — Teabevärav SPA, search needs JS) |

**Dated negative keeps the no-map verdict for area gradients**: no anonymous
direct-download EHR bulk CSV URL is verified, so there is no live backfill
and no gradient map follows (building attributes are not place fields, #136
precedent stands). TTL is still stated in code: `EHR_TTL_DAYS = 30`
(parameters3.md §5.2 — quarterly bulk dump sync, 30-day per-building-code
cache). `fetch_ehr_bulk()` raises `ValueError` on an empty URL instead of
guessing an endpoint; transport errors raise and are never cached; HTTP 429
propagates (stop signal).

## What flipped vs stayed NULL

| Param | Overturn output | Shape |
|---|---|---|
| p21 square footage | **Enrichment** `building_net_area_m2` | Building fact (never the flat's `area_m2`, never a score — #136 filter verdict stands) |
| p33 age | **Enrichment** `build_year` + `building_age_years` | Fact, never a score (taste axis — Vanalinn charm vs new build) |
| p35 energy efficiency | **Enrichment** `energy_class` | Listing wins, EHR fills gaps; scoring stays with group02 `dim_energy` (one band definition, no fork) |
| p30 accessibility | **Per-code dim** (EHR lift + listing floor) | Lift→100, ground→100, walk-up decay 80/60/40/25; NULL when floor+lift both unknown |
| p48 permit history | **Per-code dim** from bulk counts | clean 100 / flagged 20 / recorded violation 0; present-but-empty record → NULL (old stock predates digital records) |
| p79 building permit history | **Per-code dim** (bulk twin of group02b) | 85 / 70 / 45 — same bands, `hulgilaadung` reasons proving join wiring |
| p154 builder warranties | **Per-code dim** (explicit field only) | 90 / 50; never derived from build_year (terms vary — fake precision refused) |
| p495 unpermitted sunroom | **Per-code dim** (bulk twin of group02b) | violation 20 / clean 85 |

With no joined record every dim returns NULL with an Estonian EHR-check
reason (`EI OLE` markers pinned by tests). p196 stays owned by group02b
(not repeated here).

## Proposed GROUP02/02B + nomap.md verdict updates (final index PR owns nomap.md)

- G2 §3 prose: overturn attempted — bulk join pipeline ships, but the dated
  negative (no anonymous bulk) means area gradients stay invalid; per-code
  dims + p21/p33/p35 enrichment are the honest yield.
- Appendix rows p21/p33/p35: "NULL" → "listing-enrichment via EHR bulk join
  (no score — filter/taste/deferred-band verdicts stand)".
- Appendix rows p30/p48/p79/p154/p495: "NULL" → "per-code dim on joined EHR
  record (NULL until gated export joined)".
- p196 row: unchanged (ships).

## Judgment calls (for the reviewer)

See module docstring for the full list. Largest: (1) p21 enriches as a
BUILDING area, never touching the flat's `area_m2`; (2) empty permit records
score NULL, not clean; (3) warranty never computed from age; (4) p79/p154/
p495 deliberately twin group02b bands with distinct reasons — convergence
with listing-attribute dims is left to the joint integration PR (WEIGHTS is
pinned exactly by existing tests, so no per-batch rebalancing here).
