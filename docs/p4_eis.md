# P4 EIS (ex-KredEx) verdict note (issues #260 demo + #341 coverage)

Date: 2026-09-13. Scope: P4-010 (demo) plus the 2 coverage params in
#341, all consuming one EIS grant/queue/guarantee per-building
ingestion (`services/scoring/dims_p4_eis.py`). The EHR mirror slice
(`dim_renovation_grant` in `dims_p4_ehr.py`, issues #249/#333) is a
separate pipeline — untouched.

## Openness verdict: OPEN-but-gated (dated negative on anonymous bulk)

Polite probes, one GET each, `home-finder-verification` User-Agent,
cached to /tmp/hf-eis, 2026-09-13 ~13:43 UTC:

| Probe | Result |
|---|---|
| `curl https://www.eis.ee/` | HTTP 301 → `https://eis.ee/`, HTTP 200, 294612 bytes — live EIS site |
| `curl https://kredex.ee/` | HTTP 200 → `https://eis.ee/avaleht-elamumajandus/` — legacy KredEx housing domain now serves the EIS housing section (ex-KredEx continuity) |
| `curl "https://eis.ee/rekonstrueerimise-kulude-kalkulaator-korteruhistutele/?context=eluase-eestis"` | HTTP 200, 216542 bytes — guidance calculator, not a bulk register |
| `curl https://etoetus.rtk.ee/` | HTTP 200 → `/esf2web/` AngularJS SPA shell (3592 bytes) — state grant application portal, login-gated, no anonymous bulk |
| `curl https://andmed.eesti.ee/` | HTTP 200, 75497-byte Teabevärav SPA — no CKAN API (EHR #249 precedent); dataset search needs JS |

No anonymous direct-download per-building EIS grant/queue CSV URL
verified on 2026-09-13 — dated negative keeps this verdict. The
source stays OPEN-but-gated (published programme pages + gated
e-toetus portal). Consequence, kept honestly in code:

- `fetch_eis_csv` targets the documented register layout with
  `EIS_TTL_DAYS = 91` (quarterly bulk per parameters4.md P4-010),
  single polite GET, file cache; transport/HTTP errors RAISE and are
  never cached as data; HTTP 429 propagates (stop signal).
- Every dim scores ONLY joined records; with no `ehr_code`/`eis_id`
  match all 3 return NULL with an Estonian reason. No anonymous bulk
  = no backfill = NULLs until a gated export is joined. That is the
  honest shape, not a gap to paper over.

## Honest-shape table (per-building join dims)

| Param | EIS slice consumed | Shape when joined | When missing |
|---|---|---|---|
| P4-010 grant (demo) | grant_status + queue_pos | 85 / 60 / 50 / 35 (mirrors EHR slice) | NULL → KÜ/EIS |
| P4-007 loan (coverage) | guarantee_status + amount | 70 active / 50 pending-or-none (neutral) | NULL → e-Äriregister annual reports |
| P4-060 queue (coverage) | subsidy_queue_pos (+ grant_status) | 55 numbered / 70 granted / 50 status-only | NULL → Tallinna Vesi fee zones + KÜ/EIS |

## Pairing rationale (why these slices, why these bands)

- P4-010 bands (85/60/50/35) are copied verbatim from the EHR slice
  so both sources agree when joined; this module is the primary EIS
  ingestion, the EHR field is its mirror.
- P4-007 scores ONLY the EIS käendus slice: the full param (KÜ loan
  + remondifond + heating €/m² from annual reports) belongs to the
  e-Äriregister pipeline — "no guarantee" is neutral (50), never bad.
- P4-060 scores ONLY the queue slice (P4-010 join per
  parameters4.md source 3): the stormwater fee zone table belongs to
  Tallinna Vesi / Tallinna ÜVK, so the zone half stays NULL with
  that pointer in every reason.

## TTL

Quarterly (`EIS_TTL_DAYS = 91`) per parameters4.md P4-010. Grant
decisions and queues move slower than weekly permit feeds; a gated
export joined once per quarter is the honest refresh rate until an
anonymous bulk endpoint is verified.
