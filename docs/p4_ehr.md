# P4 EHR / E-ehitus verdict note (issues #249 demo + #333 coverage)

Date: 2026-09-13. Scope: P4-005 (demo) plus the 20 coverage params in
#333, all consuming one EHR / E-ehitus per-ehr_code ingestion
(`services/scoring/dims_p4_ehr.py`). Overturn #234 (parameters3 G2 EHR
bulk, `dims_group02*.py`) is a separate pipeline — untouched.

## Openness verdict: OPEN-but-gated (dated negative on anonymous bulk)

Polite probes, one GET each, `home-finder-verification` User-Agent,
cached to /tmp/hf-ehr, 2026-09-13 ~13:19 UTC:

| Probe | Result |
|---|---|
| `curl https://www.eehitus.ee/infoportal` | HTTP 301 → `https://eehitus.digitaalehitus.ee` |
| `curl https://eehitus.digitaalehitus.ee` | HTTP 200, 695188 bytes — cluster marketing site, no CSV endpoint |
| `curl https://www.ehr.ee` | HTTP 301 → `https://livekluster.ehr.ee/ui/ehr/v1` |
| `curl https://livekluster.ehr.ee/ui/ehr/v1` | HTTP 200, 3663-byte JS shell ("E-ehituse platvorm on Maa- ja Ruumiameti infosüsteem...") — live, login-gated |
| `curl "https://andmed.eesti.ee/api/3/action/package_search?q=ehitisregister"` | HTTP 404 "Cannot GET" — national portal (avaandmed → andmed.eesti.ee Teabevärav SPA) has no CKAN API; search needs JS |

No anonymous direct-download EHR CSV URL verified on 2026-09-13 —
dated negative keeps this verdict. The registry stays OPEN-but-gated
(email-gated infoportal reports, #234 precedent). Consequence, kept
honestly in code:

- `fetch_ehr_csv` targets the documented report layout with
  `EHR_TTL_DAYS = 7` (weekly bulk per parameters4.md P4-005), single
  polite GET, file cache; transport/HTTP errors RAISE and are never
  cached as data; HTTP 429 propagates (stop signal).
- Every dim scores ONLY joined records; with no `ehr_code` match all
  21 return NULL with an Estonian reason. No anonymous bulk = no
  backfill = NULLs until a gated export is joined. That is the honest
  shape, not a gap to paper over.

## Honest-shape table (per-ehr_code join / per-listing dims)

| Param | EHR slice consumed | Shape when joined | When missing |
|---|---|---|---|
| P4-005 permits | has_ehitusluba/kasutusluba | 100 / 50 / 20 binary | NULL (old stock ≠ evidence) |
| P4-010 grant | renovation_grant_status + queue pos | 85 / 60 / 50 / 35 | NULL → EIS/KÜ |
| P4-013 parking | parking_spaces | 75 / 30 | NULL → city tariff zone |
| P4-016 geology | none (EGT/Maa-amet) | always NULL | always NULL |
| P4-021 builder | builder + permit counts | ratio, cap 80 (no TTJA) | NULL |
| P4-023 noise | none (maps/EANS) | always NULL | always NULL |
| P4-030 change | permits_open (echo) | NULL + echo | NULL |
| P4-031 weather | heating_type (echo) | NULL + echo | NULL |
| P4-034 overheat | floors_total + cooling + listing floor/orientation | 30/55/70/80 capped sim | NULL |
| P4-035 darkness | listing floor/orientation | 35/60/80 capped model | NULL |
| P4-036 roof | roof_type | 70/55/50, floor 50 | NULL → Eleri
...[truncated 1583 chars]