# P4 PRIA verdict note — field blocks off the keyless WFS (P4-024)

> Demo verdict for issue #299 (single-param demo, no coverage
> issue — the issue states 0 remaining params use this source, so
> no follow-up coverage issue exists), updated by the 2026-09-16
> §7.7 dig. The dim is SCORED (coarse spray-drift hinnang off the
> keyless PRIA WFS); the scorer lives in
> `services/scoring/dims_p4_pria.py`, pinned by
> `services/scoring/tests/test_dims_p4_pria.py`.

## Verdict

**OPEN (keyless WFS 2.0.0 download service, polite daily BBOX
pull).** The 2026-09-13 check found PRIA's daily-bulk claim
pointing at a JS-shell catalogue and stopped; the 2026-09-16 dig
(§7.7) resolved the pointer through the catalogue's own JSON API
to the keyless GeoServer behind the Veebikaart and validated a
bounded Tallinn-fringe pull: 429 joined blocks (Rae/Harku/Saue/
Viimsi/Jõelähtme/Kiili vald + 1 inside Tallinn), fresh modification
timestamps (September 2025+), per-block crop and area. The dim
scores coarse distance bands (block-adjacent vs 200 m+ clear; never
0/100 on this leg alone); per-parcel doorway precision stays
unscored and origins outside the pulled frame stay NULL.

## Openness evidence II (the §7.7 dig, 2026-09-16 — P4-024 OPEN)

10 tiny reads total (labelled one-off user-agent `home-finder pria
dig (issue #299, one-off, tiny reads, no scrape)`, 2–4 s pacing,
`--max-time 25–90`, headers + visible-text + bundle-static +
API-JSON scope read only, no scraping, no auth, no form driving, no
retries; no HTTP 429 hit). Raw bodies: `/tmp/hf-dig-pria/`
(one-off PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `GET andmed.eesti.ee/api/3/action/package_search?q=pria` → HTTP 404 | Not CKAN (custom Teabevärav app) | Catalogue API found via the bundle instead |
| Portal shell + `main-CenoT8FQ.js` bundle (1 274 241 B, static read) | Same-origin JSON API `/api/datasets/search` (GET `lang/page/limit/search/…`), basePath `/api` | Server-rendered pointer resolved — the 2026-09-13 shell is now an API |
| `GET /api/datasets/search?lang=et&page=1&limit=5&search=pria` → HTTP 200 | Exactly 1 dataset: "PRIA kodulehe statistikamoodul" (web stats, not blocks) | Subsidy stats live elsewhere; not this leg |
| `GET …&search=põllumassiiv` → HTTP 200 | 2 hits: "Põllumassiivide register" + soil-maps WMS | Register record names the download service |
| `GET /api/datasets/slug/pollumassiivide-register` → HTTP 200 | PUBLIC, accrualPeriodicity DAILY; citations: `kls.pria.ee/geoserver/pria_avalik/wfs` WMS view + WFS download (all three catalogue urlBroken flags STALE — verified live below) | Daily TTL anchor + service URLs, documented |
| `GET …/pria_avalik/wfs?SERVICE=WFS&REQUEST=GetCapabilities` → HTTP 200 (99 655 B) | WFS 2.0.0, GetFeature + GetPropertyValue; `pria_avalik:pria_massiivid` ("PRIA Põllumassiivid", default EPSG:3301) + pollud/plk/maastikuelemendid/mesilad/ehitised | Keyless download service named and live |
| `GET kls.pria.ee/kaart/` + `js/app.min.js?11` (98 799 B, static read) | Map renders tiled WMS `https://kls.pria.ee/geoserver/avk/wms` (prefix `avk:`, `avk:avk_massiivid` — view-only); per-parcel routes `#otsi=massiivid/<11-digit-nr>` | Endpoint inventory: WMS = view, WFS = download; per-parcel enumeration refused (scraping, not polling) |
| WFS GetFeature validation (bounded Tallinn BBOX, GeoJSON) | lat,lon-order bbox → `totalFeatures=0` (axis lesson: this server wants lon,lat); wide fringe bbox → >8 MB (aborted by the size guard); tight bbox (24.55,59.35,24.95,59.52) + propertyName slimming → HTTP 200, 1 463 119 B, **429 blocks** | Tight BBOX + slimming is the pull contract; full-layer pulls stay out |

Feature schema (verified): MultiPolygon, GeoJSON lon-first
(`[24.46, 59.26]`-style points), properties `{xy_id, pindala (ha),
massiivi_maakasutus, kultuur/kultuur2, maakond, vald,
viimase_muutmise_aeg}` (sample `2025-09-12` — the last-two-years
claim window is live). Pull contract: ONE WFS GetFeature (tight
BBOX, propertyName-slimmed) max 1 / 24 h per cache dir
(`PRIA_TTL_S = 86400`, per the register's DAILY accrual); body
stored only on HTTP 200 + JSON under 8 MB; 429/errors stop and
cache nothing.

## Openness evidence I (first round, 2026-09-13, no scraping, no auth)

8 served requests total (single GETs, labelled one-off user-agent
`home-finder openness probe #299 (one-off, single GETs; contact via
GitHub home-finder)`, headers + visible-text keyword scope read
only; no form driving, no AJAX walking, redirects not spidered
beyond the single canonical documented link). Raw bodies:
`/tmp/hf-pria-probe/` (one-off PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://www.pria.ee/` → HTTP 200, 146074 bytes, title "PRIA" | Portal front; links `/avaandmed`, `/registrid/pria-kaardiandmed`, `https://kls.pria.ee/kaart/`; sweep: avaandmed x1, põllumassiiv x3, kaart x4; zero WMS/WFS/API/CSV/JSON pointers | Working host confirmed; data paths documented one click deeper, no machine feed on the landing |
| `https://kaart.pria.ee/` → DNS failure (host does not resolve) | Stale guess, tried once | Live map is at kls.pria.ee, not kaart.pria.ee |
| `https://andmed.eesti.ee/dataset?q=pria` → HTTP 200, 75497 bytes, title "Teabevärav" | JS app shell, 12 visible characters, no server-rendered results | No trivially pollable national-portal PRIA dataset (same shell as the #264/#277/#284 checks) |
| `https://www.pria.ee/avaandmed` → HTTP 200, 72856 bytes, title "Avaandmed \| PRIA" (added 27.12.2019, changed 30.03.2021) | "Avaandmed on avalikud kõigile vabalt kasutamiseks antud ja veebist kättesaadavad andmed"; info consolidated in the national portal | Open-data policy exists; no direct bulk link on the page |
| `https://www.pria.ee/registrid/pria-kaardiandmed` → HTTP 200, 78599 bytes, title "PRIA kaardiandmed \| PRIA" (changed 12.03.2026) | Public web map shows ONLY blocks with area-support claims in the last two years; spatial data "kättesaadavad Andmete teabeväravast" in ESRI SHP / MapInfo TAB / MS Excel (2007) / CSV, "uuendamise sagedus: igapäevaselt" | Documented bulk claim with a daily cadence — but it points at the catalogue, not at a file URL |
| `https://kls.pria.ee/kaart/` → HTTP 200, 54913 bytes, title "PRIA Veebikaart" (app v26.9.0, base map © Maa- ja Ruumiamet) | Layer list (Põllumassiivid, loomaregistri tegevuskohad, pärandniidud, katastriüksused); 11-digit-number + address search; verbatim: "Veebikaardil on nähtavad kahel viimasel aastal pindalatoetuste taotlustel märgitud põllumassiivid" | Interactive lookup UI, not a bulk feed |
| Documented holder link (`avaandmed.eesti.ee/information-holders/...`) → HTTP 301 to the canonical `andmed.eesti.ee` host | Single documented-link follow | Redirect target confirmed, not spidered further |
| Canonical holder page → HTTP 200, 75497 bytes, JS "Teabevärav" shell, 12 visible characters | Zero hits for põllumassiiv / ruumiandmed / SHP / CSV / WMS / WFS | No server-rendered bulk URL to poll — dated negative proven, not assumed |

Judgment call: the check stopped at storefront/page level on
purpose — no kls.pria.ee search driving, no AJAX walking, no
Teabevärav JS-app driving (tervise #289 precedent). Driving a
query UI parcel-by-parcel would be scraping human publications,
not polling a feed — exactly what AGENTS.md §5 refuses.

## Honest shape (SCORED 2026-09-16 — coarse cells, never parcels)

| Param | Dim key | Honest shape | Buyer-side check meanwhile |
|---|---|---|---|
| P4-024 Country-health, PRIA slice (demo) | `pollupuhver_pria` | SCORED Tallinn-fringe hinnang cells: metres from the listing origin (lat,lon) to the nearest joined block polygon — ≤50 m → 30 (adjacent, caution), ≤200 m → 55 (near, wind care), beyond → 80 (clear; capped, leg partial). Never 0/100 on this leg alone. Origins outside the pulled frame, missing origins, and missing snapshots stay NULL (EI OLE). Crop is recorded, never scored | kohapealne vaatlus (pritsimisriba / roheline serv / farmilõhn) + küsi KÜ-lt/naabritelt pritsimisgraafikut; scored cousins: õietolm dims_p4_kaur + elupaik dims_p4_eelis; NULL cousins: puuk/suplusvesi dims_p4_tervise + farmilõhn dims_p4_komun |

Every scored reason traces to a joined field-block record (block
number/vald/landuse/crop + snapshot date); a single interactive
lookup never scores a parcel; distance math is equirectangular
metres on validated lon-first rings (holes ignored — coarse by
design, far below the 50 m band edge).

## Judgment calls (for the reviewer)

1. Single-param demo, no coverage issue: #299 states the remaining
   0 params using this source need only a follow-up created after
   this demo — with the dig resolving the bulk, one scored dim in
   one module is the whole honest scope.
2. Split-slice contract: the scored KAUR pollen leg
   (dims_p4_kaur dim_tervis_kaur) and EELIS habitat-proxy leg
   (dims_p4_eelis dim_maaloodus_eelis) plus the NULL Terviseamet
   tick/bathing leg (dims_p4_tervise dim_country_health_nuisances)
   and komun farm-odour leg (dims_p4_komun dim_farm_odour_cells)
   stay where they live and are named, never re-scored here.
   Sibling modules were read first; parameters4.md untouched.
3. The documented daily cadence ("igapäevaselt", now confirmed
   as the register's accrualPeriodicity DAILY) is the pull's TTL
   anchor (`PRIA_TTL_S = 86400`) — a cadence stated by the source,
   not assumed by the repo.
4. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   parameters4.md untouched): this dig edits only the 3 files the
   re-opened issue owns (dims module + its test + this note).
   Central hook (enrich join + WEIGHTS rebalance) stays one joint
   change across all batches.

## Reopening checklist (post-dig)

1. Re-pull the tight BBOX each spring before spraying season (daily
   TTL handles freshness; the spring check recalibrates
   `BUFFER_BANDS` from spray-drift literature — the 50/200 m edges
   are first-cut with no live calibration — and re-verifies the
   429-block count).
2. Wider Harjumaa frame ONLY if the per-day byte budget allows:
   the wide fringe already exceeds 8 MB, so county graduation needs
   paging or a coarser layer (e.g. `pria_plk_alad`), not a bigger
   single pull.
3. Crop-weighted caution ONLY from literature: `kultuur` is
   recorded per block today, never scored.
4. If the WFS goes dark: keep the last fresh snapshot until TTL,
   then NULL — transport errors are never data.
5. Add the explicitly-flagged live integration test (not a unit run).
