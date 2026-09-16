# P4 notice-watch verdict note (issue #550)

Date: 2026-09-16. Scope: early-warning notices feed (quarry/felling/zoning)
from Ametlikud Teadaanded open data. Module
`services/scoring/dims_p4_notices.py`. No shared files touched.

## Openness verdict: OPEN feed, ZERO structured parcel linkage

Polite probes, one GET each, custom `home-finder-probe-550` User-Agent:

| Probe | Result |
|---|---|
| `GET andmed.eesti.ee/datasets/ametlike-teadaannete-avaandmed` | HTTP 200, 75497 bytes — Angular JS shell (12 chars visible text, no server-rendered distribution/API URL). Bundle dig stopped per polite budget. |
| `GET www.ametlikudteadaanded.ee/avalik/uriotsing` | HTTP 200, 152268 bytes. Machine interface = documented URI scheme `/ee/{andmeandja}/{pealiik}/{alaliik}/{aasta}/{kuu}/{paev}/{teate_number}/{xml}`. Trailing-component drop lists notices; `+xml` returns an XML koondfail aggregate. 1000-result cap. No auth. Publisher Ministry of Justice and Digital Affairs, CC BY-SA 4.0. |

## Notice-type taxonomy (observed in page, buyer-relevant slice)

| Pealiik | Alaliigid scored | Family |
|---|---|---|
| `keskkonnaluba` | `kaevandamisloa-andmine-voi-muutmine`, `-eelnou-avalikustamine`, `-menetluse-algatamine`, `-saamise-enampakkumine`, `keskkonna-…`, `keskkonnaloa-eelnou-…`, `keskkonnaloa-menetluse-algatamise-teade` | quarry → flag 35 ≤1 km ≤12 mo |
| `planeeringud` | `detailplaneeringu-algatamine`, `-kehtestamine`, `-osalise-kehtetuks-tunnistamine` | zoning → flag 55 ≤1 km ≤12 mo |
| `maakatastri-teated` | `maakatastri-teade` | cadastre → flag 60 ≤500 m ≤12 mo |

Felling: no mandatory AT channel. Only forest hit is
`metsa-raieoiguse-ja-metsamaterjali-myyk` (felling-rights/timber sale,
commercial — not a permit). `metsateatis` lives in the Forest Register.
`dim_felling_watch` is a documented no-map NULL with a metsaregister
check reason.

## Location fields: none structured (linkage rate 0)

URI components carry publisher/type/date/number only; the notice XML
schema (per `dims_p4_ata`) has no parcel/address/coordinate field —
location, if present, is free text in `sisendid`/`kinnitatud_sisu`.
Structured linkage rate: **0 locatable / total**. Unlocatable notices
stay out (counted in the NULL reason). Harjumaa volume per type is
therefore unmeasurable without a harvester that pages the 1000-cap
windows month by month — deferred to the harvest PR, which must also
solve parcel linkage (cadastre text-mining) before any distance band
goes live.

## Honest-shape table

| State | Shape |
|---|---|
| No joined pull | NULL (`EI OLE`) |
| Joined, unlinked / expired / out-of-band | NULL, unlinked counted |
| Active linked quarry ≤1 km ≤12 mo | 35 + "teadaanne ei ole heakskiit" |
| Active linked zoning ≤1 km ≤12 mo | 55, same legend |
| Active linked cadastre ≤500 m ≤12 mo | 60, same legend |
| Joined pull, zero in-scope notices | 70 capped weak-good (1000-cap caveat named) |

Harvest: weekly at most (`NOTICE_TTL_DAYS = 7`); transport errors raise,
never cached; HTTP 429 propagates. Applicants never named in reasons
(notice-type stats + parcel links only). Announcement ≠ approval in
every scored reason and would be in the overlay legend (no overlay
shipped: events with expiry are flags, never a gradient).
