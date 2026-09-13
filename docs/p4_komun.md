# P4 komun verdict note — Tallinna Keskkonna- ja Kommunaalamet (P4-018 + 17 slices)

> Dated-negative verdict for issues #290 (demo) and #363 (coverage).
> Checked 2026-09-13. All eighteen params are documented no-map NULL dims
> (OTA PR #131 precedent); scorers live in
> `services/scoring/dims_p4_komun.py`, pinned by
> `services/scoring/tests/test_dims_p4_komun.py`.

## Verdict

**No open machine feed — all eighteen dims stay NULL with Estonian reasons.**
Winter-maintenance classes, maintenance-area maps, complaint intake and lag,
tree-felling notices, KÜ-support notices, the ÜVK development plan and the
ice/wood-burning/stormwater notices live on human-readable tallinn.ee pages,
in e-service flows (raieluba, korraldatud jäätmevedu), in the interactive
lumekaart viewer, or on the phone (14410) / in the annateada.ee app. There is
no public bulk feed to poll politely, so there is no ingestion to cache, no
TTL to state beyond this one-off check (re-probe each autumn per the P4-018
autumn TTL), and no honest per-parcel band, hex rate, or calendar to paint.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

6 tiny requests total (six single GETs, labelled one-off user-agent
`home-finder openness probe #290 (one-off, single GETs, file cache for PR
record; contact via GitHub home-finder)`, headers + visible-text keyword
scope read only). Raw bodies: `/tmp/hf-komun-probe/` (one-off PR record,
not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://www.tallinn.ee/` → HTTP 200 (~138 KB, cloudflare) | Storefront links the department page, `/avaandmed/`, `/et/lumi`, the geoportal | Entry points confirmed, nothing machine-readable advertised |
| `https://www.tallinn.ee/et/keskkonna-ja-kommunaalamet` → HTTP 200 (~219 KB) | Human e-service pages (raieluba, road upkeep, waste transport); visible-text sweep (~25.9k chars) 0 for csv / geojson / wfs / andmestik / masinloetav | No open-data page, no developer feed; complaint intake is phone/app only |
| `https://www.tallinn.ee/avaandmed/` → HTTP 200 (~76 KB) | 12 visible characters: JS shell, no server-rendered datasets | No trivially pollable city open-data portal (same shell as #264/#277/#284) |
| `https://www.tallinn.ee/et/lumi` → HTTP 200 (~57 KB) | 2025/2026 winter-maintenance human page ("ühtlane hooldustase", lumekoristus news); maintenance map is an embedded iframe viewer, 0 for csv / geojson / wfs / api / masinloetav | Classes exist as a human map, never a comparable machine vintage — the P4-018 class join cannot be measured |
| `https://gis.tallinn.ee/lumekaart/` → HTTP 200 (~5 KB, IIS) | ArcGIS Web AppBuilder viewer shell ("Talihoolduse kaart", jimu-core/init.js); no WFS/WMS/GeoJSON/CSV endpoint at page level | Interactive viewer, not a pollable per-parcel join |
| `https://andmed.eesti.ee/dataset?q=talihooldus` → HTTP 200 (~76 KB) | 12 visible characters ("Teabevärav" JS shell) | No trivially pollable national-portal talihooldus dataset |

Judgment call: the check stopped at storefront/page/viewer-shell level on
purpose — no lumekaart service enumeration, no e-service flow driving, no
complaint-form probing. Deeper probing is exactly the scraping this repo
refuses (AGENTS.md §5).

## Honest shapes per param (all NULL until a feed appears)

| Param | Dim key | Honest shape when a feed lands | Buyer-side check meanwhile |
|---|---|---|---|
| P4-018 snow class (demo) | `snow_maintenance_class` | per-parcel road-class join (teeregister + lumekaart levels) | tallinn.ee/et/lumi + lumekaart viewer + dims_p4_tlt winter-bus leg + dims_p4_osm winter_service proxy |
| P4-007 KÜ bill | `ku_loan_support` | per-listing dim (Kommunaalamet KÜ-toetused leg) | KÜ annual report (e-Äriregister) + dims_p4_creditinfo |
| P4-010 grant queue | `renovation_grant_queue` | per-building dim (KÜ-renoveerimistoetused leg) | EIS grant register + EHR renovation permits |
| P4-016 geology | `geology_uvk_crosscheck` | per-parcel class join (ÜVK/sademevee cross-check leg) | dims_p4_maa_subsurface EGT slice + ÜVK-arengukava |
| P4-017 water/sewer | `uvk_development_plan` | per-parcel join (ÜVK-arengukava liitumispiirkonnad leg) | dims_p4_tvesi zone table + iseteenindus tech conditions |
| P4-024 farm odour | `farm_odour_cells` | coarse hinnang cells (farm-kaebused leg) | on-site downwind walk |
| P4-026 fix-it lag | `fixit_responsiveness` | hex responsiveness rate (heakorra-teated + removal lag) | ask the linnaosa; KÜ stairwell accounts |
| P4-030 tree felling | `tree_felling_flag` | coarse change flag (raieload/hooldusraie leg) | Maa-amet aerial vintages + EHR permits |
| P4-042 smell cells | `odour_complaint_cells` | coarse hinnang cells, never doorway precision | morning on-site sniff |
| P4-047 small horrors | `small_horrors_calendar` | calendar dims (müra + plow-schedule legs) | street plow schedule (lumi page) + weekend listen |
| P4-053 odour rose | `odour_rose_sectors` | sector + calendar, never circle buffer | Ilmateenistus Harku wind rose + windy-week stay |
| P4-054 quarry season | `quarry_blast_season` | timetable + buffer (blast-complaint leg) | Maa-amet maardlad register + Tark Tee trucks |
| P4-055 schedulable noise | `schedulable_noise_calendar` | calendar dims (komun-validation leg) | Sadam schedule + EANS flight info + dims_p4_elron night-maintenance leg |
| P4-057 heat-pump hum | `heatpump_hum` | weak hinnang (hum-complaint leg) | EHR heating-type changes + evening listen |
| P4-058 ice duties | `icefall_duty_warnings` | per-parcel dims with dates (duty/warning leg) | EHR roof-type slice + Päästeamet ice-fall notices |
| P4-059 wood-burning | `woodburning_zones` | per-parcel rule join (restriction-notice leg) | EHR heating-type slice + kliimakava zones |
| P4-060 stormwater | `stormwater_notices` | zone table + queue dim (teated leg) | dims_p4_tvesi fee table + EIS queue |
| P4-062 rat/ice hex | `rat_icefall_hex` | hex operational flags, never addresses | on-site waste-house check + KÜ waste costs |

Never 0 and never 100 would apply once scored (absence is not proof of calm
or disaster); today every reason says `EI OLE` and points at the concrete
check above. Every scored-future reason must trace to a joined record.

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #363 defines coverage as extending the demoed
   ingestion — with a dated-negative demo there is no ingestion to extend,
   so all seventeen coverage slices land in the same verdict module
   (TLT #277+#351, elektrilevi #264+#344, Elron #284+#358 precedent).
2. Pairing rationale: every coverage param names this department
   (Keskkonnaamet / Kommunaalamet / heakord / ÜVK-arengukava) in its
   parameters4.md source list — see the module docstring for the per-param
   leg mapping. Weakest link is P4-016 (only its source 5, the ÜVK +
   sademevee cross-check, touches this department); it is kept because the
   #363 body lists it and the leg is genuinely the department's, while the
   EGT/Maa-amet legs stay in dims_p4_maa_subsurface and are named there.
3. Complements, not duplicates: P4-017 vs dims_p4_tvesi.dim_water_sewer_zone
   (city development plan vs utility zone table), P4-060 vs
   dims_p4_tvesi.dim_stormwater_fee (city notices vs utility fee table),
   P4-018 vs dims_p4_tlt winter-bus leg (street class vs bus cuts). Each
   reason names the cousin module.
4. P4-026 (fix-it LAG rate) vs P4-062 (complaint COUNT flags) are different
   honest shapes (hex rate vs hex flags) — no double-scoring by
   construction, both NULL.
5. P4-055 covers ONLY the komun mürakaebused-validation leg; the Sadam /
   EANS / Männiku timetable legs belong to future source issues and the
   Elron night-maintenance leg stays scored NULL in dims_p4_elron.
6. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   parameters4.md untouched): 3 new files only. Central hook (enrich join
   + WEIGHTS rebalance) stays one joint change across all batches.

## Reopening checklist (when a pollable feed appears)

1. Re-run the six probes above each autumn (P4-018 TTL: autumn, before the
   winter season); paste fresh evidence in the reopen PR.
2. If gis.tallinn.ee/lumekaart (or avaandmed / andmed.eesti.ee) exposes a
   pollable class layer, transcribe one maintenance-class table into the
   cache dir and run it through a `parse_maintenance_classes` +
   per-parcel join on fixtures first.
3. Graduate dims to bands ONLY from joined records (per-parcel join / hex
   rate / calendar per the table above); keep NULL-with-Estonian-reason
   for every missing leg.
4. Add the explicitly-flagged live integration test (not a unit run).
