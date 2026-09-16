# P4 veebi: Tallinna veebikaart + lighting verdict note (issues #304 + #373)

Demo (#304) implements the Tallinna veebikaart + lighting source
openness check + P4-035 end-to-end; coverage (#373) wires P4-029 +
P4-032 + P4-040 off the same verdict. One PR closes both because the
#373 body states it extends the demoed ingestion with "no new
plumbing expected" — and with a dated-negative verdict there is no
pipeline to extend, so all four dims land in one verdict module
(komun #290+#363, green #300+#369 precedent).

Second round (2026-09-16): the §7.7 dig opened the Experience
Builder shell and inventoried its backing ArcGIS Server service by
service. No keyless lighting / current-orthophoto / lit-street feed
exists — all four dims stay NULL with the endpoint inventory below
pasted (the "close again with the endpoint inventory" path from the
#304 reopen note). Inventory constants live in
`services/scoring/dims_p4_veebi.py` (`VEEBI_*`), pinned by
`services/scoring/tests/test_dims_p4_veebi.py`.

## Openness verdict: dated negative, twice confirmed

First round (2026-09-13, 6 polite requests, labelled UA). Raw
bodies: `/tmp/hf-veebi-probe/` (one-off PR record, not committed).
Single GETs, 25 s timeout, no retries, 3 s pacing; headers +
visible-text keyword scope only.

| URL | Result | Verdict |
|---|---|---|
| `https://kaart.tallinn.ee/` → 301 → `https://gis.tallinn.ee/veebikaart/` (GET 200, 5 023 B, 21 visible chars, JS app shell) | no WFS/WMS/GeoJSON/CSV endpoint at page level | DATED NEGATIVE for bulk layers (no service enumeration — refused) |
| `https://gis.tallinn.ee/` (GET 200, 703 B, IIS default page) | viewer entry only | DATED NEGATIVE for bulk polygons (same shell as green #300) |
| `https://www.tallinn.ee/et/otsing?search_api_fulltext=valgustus` (GET 200, ~147 KB, ~10.3k visible chars) | 4x valgustus = one human news page (Hirvepargi valgustuslahenduse eskiisprojekt); 0x csv/geojson/wfs/wms/masinloetav/andmestik/lamp | DATED NEGATIVE for the lamp inventory |
| `https://www.tallinn.ee/et/otsing?search_api_fulltext=veebikaart` (GET 200, ~145 KB, ~9.6k visible chars) | 8x veebikaart = human service pages (kaart + aerofoto + aadressiotsing + infokihid + reisiplaneerija in-app; Nõmme leisure map); 0x csv/geojson/wfs/wms/masinloetav/andmestik | DATED NEGATIVE for layer feeds |
| `https://www.tallinn.ee/et/otsing?search_api_fulltext=valgustatud%20teede` (GET 200, ~147 KB, ~9.8k visible chars) | 0x valgustatud/lamp/csv/geojson/wfs/wms | DATED NEGATIVE for the lit-street layer as a feed |
| `https://andmed.eesti.ee/dataset?q=valgustus` (GET 200, ~76 KB, 12 visible chars) | "Teabevärav" JS shell | DATED NEGATIVE (same shell as #264/#277/#284/#290/#300) |

Second round — §7.7 dig (2026-09-16, 12 polite metadata reads:
shell page + bootstrap + 2 not-found config paths + services
directory + 4 folder listings + 3 layer definitions; paced single
GETs, labelled one-off UA `home-finder-openness-check`, 25 s
timeout, no retries, no 429). Raw bodies: `/tmp/hf-dig/veebi/`
(one-off PR record, not committed). Metadata only: services
directory + layer definitions, never feature queries, never
credentialed folders.

| Check | Observed | Meaning |
|---|---|---|
| `https://gis.tallinn.ee/veebikaart/` → HTTP 200 (5 023 B) | ExB 1.19 dev-edition shell; bootstrap `cdn/2/jimu-core/init.js` is the generic loader (no item IDs) | Shell confirmed, config path hunt next |
| `.../veebikaart/config/config.json` → 404; `.../veebikaart/config.json` → 404 (IIS) | App config not at the obvious paths | Boundary recorded — no app-internals guessing beyond this |
| `.../arcgis/rest/services?f=pjson` → HTTP 200 (ArcGIS Server 11.5, keyless) | 22 folders + 70 root services | Backing server is open; folder-by-folder next |
| `.../services/veebikaart?f=pjson` → HTTP 200 | 16 theme services (Asumid, avalik_voim, tualetid, Haridus, jalgpall, jalgsikaigualad, kaubanduskeskused, Kergliiklusteed Map-only, Raamatukogud, sotsiaalteenused, Teehoolduspiirkonnad Map-only, Tervisesport, tervishoid, transport_ja_parkimine, Vaba_aeg, Veevotukohad) | Agency layers confirmed — NO lighting, NO orthophoto |
| `.../services/tehnovorgud?f=pjson` → HTTP 200 | Water/heating networks only (TLNvesi, kaugküte, võrguvaldajate alad, yvk_piirkonnad) | No lighting inventory in utility networks |
| `.../services/Utilities?f=pjson` → HTTP 200 | Esri system tools only (Geometry, PrintingTools) | No data feeds here |
| `.../services/hooldus?f=pjson` → HTTP 200 + `{"error": {"code": 499, "message": "Token Required"}}` | Credentialed folder | REFUSED per contract — boundary recorded, never retried with auth |
| `.../services/Geoveeb?f=pjson` → HTTP 200 | Survey measurements only (mõõdistused ×4) | No lighting, no orthophoto |
| `Andmed_Tallinn/FeatureServer?f=pjson` → HTTP 200 | 9 generic layers (Välikäimlad, Pargi-ja-Reisi, Parklad, parkimistsoonid ×2, Terviserada, ametiasutused, Jäätmejaamad, Korduskasutuskeskused) | No lighting layer |
| `Linnaosad_asumid/FeatureServer?f=pjson` → HTTP 200 | Layers 0=Asumid, 1=Linnaosad (polygons) | Beneficiary: #273/#300 + named #301 per-linnaosa follow-up |
| `ortofoto2005/MapServer?f=pjson` → HTTP 200 | Single layer "Ortofoto 2005", EPSG:3301 (ortofoto2003 likewise) | Dated vintages only — no current-year service, no per-street history feed |

Pull contract: nothing pollable, so no `fetch_*` helper (a fetcher
around human project pages would be brittle scraping dressed as
ingestion; verdict modules carry no network code — komun #290
precedent, pinned by `test_module_adds_no_network_calls`). TTL =
dig date 2026-09-16; re-probe yearly or when the app/portal
changes.

## Honest shapes per param (per-listing dim; NULL stays NULL)

| Param | Dim key | Scored shape | NULL when |
|---|---|---|---|
| P4-035 darkness, veebi legs (demo) | `december_darkness` | per-listing dim (lamp inventory/kaart × VIIRS × sun hours) | always (no inventory/kaart feed, no VIIRS input — second-round confirmed) |
| P4-029 ortho-history leg | `street_ortho_history` | per-listing dim with photo date (veebikaart orthophoto vintages per street) | always (only 2003/2005 vintage rasters; history lives as in-app layer only) |
| P4-032 lit-street leg | `lit_street_usage` | hex usage hinnang, labelled usage-not-safety | always (no valgustatud-teede service anywhere keyless) |
| P4-040 arrival-lighting leg | `arrival_lighting` | per-listing dim with photo date (lit streets + lit windows, November 23:00) | always (no light layer, no window-density proxy) |

Every NULL reason says `hinnang` + `EI OLE` with the concrete buyer
check (detsembri 15:30 jalutuskäik, tänava-ülevaatus foto
kuupäevaga, õhtune 20–22 kasutusjalutus, novembri 23:00
saabumiskäik).

## Beneficiary service URLs (recorded, no separate digs)

Per the #304 reopen note, the #273 (StaMT) and #300 (green) layers
live in this same app — service URLs (all under
`https://gis.tallinn.ee/arcgis/rest/services/`):

- #273 StaMT (Sotsiaal- ja Tervishoiuamet): `veebikaart/tervishoid_veebikaart`
  + `veebikaart/sotsiaalteenused` (FeatureServer + MapServer each).
- #300 green: `Haljastuse_arengukava_muinsuskaitse` (root MapServer;
  no haljastus service inside `veebikaart/`).
- Polygons for both + named #301 per-linnaosa follow-up:
  `Linnaosad_asumid` (0=Asumid, 1=Linnaosad).

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #373 defines coverage as extending the
   demo ingestion — with a dated-negative verdict there is no
   pipeline, so one verdict module holds all four dims.
2. P4-035 is one dim (both veebi legs share one per-listing shape
   and one buyer check); P4-029/P4-032/P4-040 get one veebi leg each.
3. Slice boundary (no double-scoring): EHR owns the
   orientation/floor/window light model (capped), ilm owns the
   December sun-hours baseline (capped), lidar owns LoD2 courtyard
   shading, OSM owns the mapped lit proxy (which itself names the
   veebikaart/VIIRS gap); maa_aerial owns the Mapillary/CV street
   + enclosure/green arrival legs (one genuinely scores), OSM owns
   the sidewalk + evening-anchor + approach proxies, elron/TLT own
   the evening-ridership NULLs. This module owns ONLY the four
   veebikaart/lighting legs above, under distinct dim keys.
4. P4-032 keeps usage-not-safety, P4-040 keeps arrival-feel ≠ safety
   (PPA/Päästeamet explicitly NOT sources per parameters4.md).
5. The hooldus/ token gate was left alone (one 499 read, never
   retried with auth); the unretrievable ExB app config was left
   alone after two 404s (no bundle/traffic sniffing). What stays
   refused: credentialed services, per-record feature queries,
   per-record scraping.
6. No shared-file edits (WEIGHTS/Overpass rebalance stays one joint
   change); pair's own module + test + doc only.

## Refresh checklist (city publishes a machine-readable feed)

1. Re-run the dig (services directory + folder listings above);
   confirm a valgustus/current-ortho/lit-street service + HTTP 200.
2. Add a `fetch_veebi` pull + reviewed snapshot table in a new PR
   (human-reviewed facts, never a JS-app traffic scrape).
3. Score the four dims off the snapshot; keep NULL-with-reason for
   missing joins (unlit street != dark flat without the EHR leg).
4. Add the explicitly-flagged live integration test (not a unit run).
