# EHR open-data API backfill (issue #537)

Dive-deeper on `docs/p4_ehr.md` (#249/#333, OPEN-but-gated) for the
missing bulk behind `docs/overturn_ehr.md` (#234): the swaggerUI
open-data interfaces were never requested. They are now.

## Source

- Catalogue: `sources/ehitisregister-25c1cc53.md` (Ministry of Climate
  Affairs, EHR since 1994, CC_BY_SA_3.0, DAILY, all-Estonia)
- Interface list: https://swaggerui.ehr.ee/ (open-data API descriptions)
- Access guide: https://livekluster.ehr.ee/ui/ehr/v1/infoportal/info

## Openness probe (2026-09-16, custom UA, single GETs, no 429)

| Probe | Result |
|---|---|
| swaggerUI root | **Reachable shell**: HTTP 200 text/html, 691 B ("E-ehituse API services in Openapi format" — lead, not verdict) |
| JS bundle (`/static/js/main.0f7bd159.js`) | HTTP 200 application/javascript, 1400550 B, read statically: **43 embedded OpenAPI specs** (`avaandmed.yaml`, `avaandmed2.yaml`, `ehrapi.yaml`, `geoapi.yaml`, `statistikaportaal.yaml`, …) |
| `avaandmed.yaml` chunk (via asset-manifest) | HTTP 200, 10898 B: **EHR Avaandmete API v1.7.1** ("REST API EHR avaandmete jaoks"). Servers: dev `https://devkluster.ehr.ee/api/av/v1`, test `http://testkluster.ehr.ee/api/av/v1`, live `http://livekluster.ehr.ee/api/av/v1`. GET `/alus/reports` (public-report metadata), GET `/reports/{report_code}`, 16× GET `/info/reports/{…}`, `/params/…`, `/version`. Report creation is POST-with-email — not anonymous, never attempted |
| Anonymous per-code query proof | **Dated negative**: `https://livekluster.ehr.ee/api/av/v1/version` → HTTP 404 "default backend - 404"; `…/alus/reports` → same 404; plain-http → 301 back to the unrouted path. The documented live base is UNROUTED (not key-gated: nothing answers at all) |
| Infoportal guide | HTTP 200 — the gated path stays email/portal-placed, same as #234 |

Interface list (buildings? permits? energy labels?): buildings
(`eh_ehitised`), building parts (`eh_ehitis_osad`), **energy labels**
(`hoone_energia_margised` — the heating-cost second leg, schema-proof
only), addresses, cadastre units, classifiers. Auth: anonymous reads
are specified but unrouted on live; writes need an email body (out of
scope — no auth attempts, no personal data, AGENTS.md §5).

Raw probe files: one-off `/tmp` working copies, never committed.

## Verdict: documented no-map (doubles as the #234 re-probe record)

No anonymous per-`ehr_code` query is reachable, so no viable backfill —
per-code dims keep their bands (present-but-empty stays NULL, old stock
predates digital records). `fetch_av_report` ships behind the existing
`fetch_ehr_bulk` contract (quarterly TTL, cache-first, transport errors
raise and are never cached, 429 propagates) for the day the route is
restored; the energy-label leg is schema-proof only (bands second).

## Judgment calls (for the reviewer)

1. Not key-gated but unrouted: probed one level deeper than "login
   wall" — the 404 "default backend" means no anonymous bulk exists to
   request, so no per-code proof on Harjumaa codes was possible (and no
   further hammering was polite).
2. POST report creation deliberately untested (email body = personal
   data + non-anonymous by construction).
3. No shared-file edits: 3 new files only (`dims_ehr_backfill.py`,
   `tests/test_dims_ehr_backfill.py`, this note). `dims_p4_ehr.py`,
   `dims_group02*.py`, `dims_overturn_ehr.py`, `overturn_ehr.md`
   untouched. No bands without evidence.

## Reopening checklist

1. Re-GET `/api/av/v1/version` on live (https + http); if 200, walk
   `/alus/reports` → one `/info/reports/eh_ehitised` pull → per-code
   proof on 2–3 public Harjumaa codes → wire `fetch_av_report` output
   into `fetch_ehr_bulk` fixtures.
2. Scope the energy-label leg second (schema key confirmed here).
3. Paste fresh evidence on the reopen PR with the live integration test.
