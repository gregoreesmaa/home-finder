# P4 Maa-subsurface — openness verdict + demo/coverage note (issues #248, #332)

> Verdict date: 2026-09-13 (all probes single polite fetches, cached
> `/tmp/hf-p4-maa-subsurface/`, ≥ 3 s pacing, contact UA in headers).
> Code: `services/scoring/dims_p4_maa_subsurface.py` (demo P4-016 + 2 coverage
> params); tests: `services/scoring/tests/test_dims_p4_maa_subsurface.py`
> (hermetic, synthetic fixtures, no network).

## Verdict

| Source | Result | Evidence (2026-09-13) |
|---|---|---|
| EGT **ruumiandmed** (spatial data page) | **OPEN** (services + downloads, licence, scale caveat) | HTTP 200 (116 953 B): *"Siin lehel on Eesti Geoloogiateenistuse ruumiandmed teenuste ja allalaaditavate failidena. Kaardirakendused on leitavad meie geoportaalist."* + *"arvestada andmestiku mõõtkavaklassi"* → coarse-only shape. |
| EGT **geoportaal Avamus** | **OPEN** (public viewer) | `GET https://gis.egt.ee/geoportaal/` → HTTP 200, 21 195 B, `<title>Avamus - EGT Geoportaal</title>`. |
| Maa-amet **maardlate viewer** (X-GIS2) | **OPEN** (public viewer) | `GET https://xgis.maaamet.ee/xgis2/page/app/maardlad` → HTTP 200, `<title>X-GIS 2.0 [maardlad]</title>`. |
| Keskkonnaagentuur **WFS** (geoloogia/maardlad/põhjavesi layers) | **OPEN** (1091 layers, no auth) | `GetCapabilities` HTTP 200, 1 345 735 B. Karst: `maaamet:geol_hydrogeoloogia_allikadkarstivormid_karstivali`; turvas: `etak:e_307_turbavali_a`; kaitse: `maaamet:geol_hydrogeoloogia_pohjaveekaitstus_pvkhinnang`; kaevud: `maaamet:geol_puurkaevud_wfs`; maardlad: `maaamet:maavarad_gbmv_levialad` (+ `leiukohad`, `perspektiivalad`). |
| Layer **schemas** (karstivali, levialad) | **OPEN** | `DescribeFeatureType` HTTP 200 both (1 798 B / 1 825 B): `shape, objectid, kood, objekt, objekt_en, kirjeldus[, kirjel_juh], nimi, info/viide, markused, pindala` — plain class attributes, ideal for per-parcel joins. |
| **Maavarade register** (state DB, EGT since 2025) | **OPEN for viewing** (map app + geoportal + bulk ZIP); submission/X-tee restricted | Register data *"vaadata ja alla laadida Maa-ameti maardlate kaardirakenduses"*; bulk `Uuringupunktid_kihid_proovid.zip` on gis.egt.ee; web-interface needs user rights (name + isikukood), X-tee needs legal-entity membership. |
| **Lõhkamiste ajagraafik** (blast timetable, Keskkonnaamet load schedules) | **NOT OPEN — dated negative** | No open feed found; P4-054 scores the buffer leg only, every scored reason names the missing timetable leg. |
| Tallinna Vesi **liitumine** (per-parcel connection reality) | **MANUAL — no open per-parcel feed** | Page HTTP 200: connection = iseteenindus technical-conditions request (issued in 2 weeks per parcel) + address service-area checker. Missing facts stay NULL with the check named. |
| Terviseamet **joogivesi** (quality leg) | **OPEN prose verdict, mixed legs** | Page HTTP 200: central water *"hästi kontrollitud"* (~85% of residents); private wells *"ametlikke andmeid ei ole"*; a public quality database exists. Central = monitored, wells = unknown by construction. |

Consequence (honest shape): per-parcel class joins are implemented and
fixture-proven (point-in-polygon over cached WFS polygons, coarse only).
Production parcels with no joined data stay NULL with an Estonian reason
naming the concrete check. Re-probe annually; a newly opened blast
timetable flips P4-054 without code changes (ingestion already caches
with TTL).

## Pull policy (polite, cached, TTL-stated)

- One request per layer per run; `User-Agent: home-finder-research/0.1`
  (polite annual bulk; issues 248/332); 25 s timeout; ≥ 3 s pacing.
- `fetch_cached(url, cache_dir, name, ttl_days)` / `fetch_layer(join_name,
  cache_dir, bbox)`: fresh cache wins (no request); transport errors are
  raised and **never cached as data**; HTTP 429 raises immediately (stop
  signal, no retry).
- TTL: subsurface bulk **365 d** (annual, per P4-016); WFS pulls use
  `count=100` (max 100 features/req, parameters3.md §5.3), EPSG:4326 GeoJSON.

## Per-param wiring (all honest shapes = per-parcel class join or a named leg)

| Param | Wired leg (this ingestion) | Legs honestly missing (EI OLE, named not faked) |
|---|---|---|
| P4-016 engineering geology | karst/turvas/alvar/kaitseala class join → 70/55/35/30/20 bands, kaitseala caps at 50 | geotechnical borehole truth (EGT licence scale caveat in every reason) |
| P4-017 water + sewer | vesi/kanal join → 85/60/55/45; liitumiskohustus caps 40, kaitseala-piirang 30, halb seire 35 | Tallinna Vesi per-parcel feed (manual check), private-well quality (officially unknown) |
| P4-054 quarry buffer | inside leviala → 25; ≤ 2 km coarse vertex proxy → 45; further → NULL (not quiet) | blast timetable (dated negative); leviala ≠ active mine |

Never a gradient: exact containment joins only; degenerate polygons match
nothing; unknown enum/flag values fail closed to NULL; a single vertex can
never set a "median"-style claim (presence-only scoring).
