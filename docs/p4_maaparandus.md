# P4 maaparandus verdict note (issue #551)

Date: 2026-09-16. Scope: drainage-duty + wetness joins from the
maaparandus GIS WFS (MSR register mirror). Module
`services/scoring/dims_p4_maaparandus.py`. No shared files touched.

## Openness verdict: OPEN — licence gate passes

Polite probes, custom `home-finder-probe` User-Agent:

| Probe | Result |
|---|---|
| `GET gsavalik.envir.ee/geoserver/pta/wfs?…GetCapabilities` | HTTP 200, 117048 bytes. 5 layers: `pta:msr_vork` (reguleeriva võrgu alad), `pta:msr_eesvool`, `pta:msr_riigieesvoolud` (state-maintained joint outflows), `pta:kehtetu_maaparandussysteem` (invalid systems), `pta:mpy_tegevuspiirkond` (co-op areas). Default CRS EPSG:3301 (+3857, +4326). Fees NONE, AccessConstraints NONE. |
| Licence (in the capabilities) | **CC-BY 4.0**, attribution to Kliimaministeerium as source, unless a layer states its own terms. Gate passes — ingestion allowed with attribution (`ATTRIBUTION`). Informative-data disclaimer noted (no guarantee). |
| `DescribeFeatureType pta:msr_vork` | HTTP 200, 2342 bytes. Attributes: `ms_kood` (13-digit system code), `ehitise_kood/nimi`, `nahtuse_liik` + `nahtuse_seletus_lyhi`, `vihm`, `pind_ha`, `aasta`, `vork_id`, `ms_url` (MSR link), timestamps. **No `seisund`/status attribute**; `nahtuse_liik` semantics unproven without value samples (out of probe budget). |
| `GetFeature resultType=hits`, Harjumaa bbox | `numberMatched="1916"` regulating-network areas (lat-lon axis order; the lon-lat order hits zero — axis-order artefact documented in `build_hits_url`). |

## Status-attribute finding (duty leg closes as NULL)

The duty leg needs a maintained-vs-derelict status to score duty; the
schema has none with proven semantics. `dim_drainage_duty` therefore
always returns NULL: with an `ms_kood` it names the code + the
MSR-register check; without a join it names the missing join. Reasons
point at the register, never assert duty. Overturn: value samples of
`nahtuse_liik` proving maintained/derelict semantics (harvest PR).

## Honest-shape table (per-parcel joins, never gradients)

| State | Shape |
|---|---|
| No joined WFS pull | NULL (`EI OLE`) |
| Inside `msr_vork` | 55 capped hinnang, `ms_kood` + status-unknown + MSR check named |
| Inside `kehtetu_maaparandussysteem` | 40 measured risk flag (wins over the inside band) |
| Outside network, eesvool ≤100 m | 45 dampness flag ("lähedus ei ole märg krunt") |
| Outside everything | NULL — never "dry" |

Split vs neighbours (reviewer note): #543 owns restriction *zones*;
p50 owns open-water proximity; `p4_maa_subsurface` owns
karst/peat/groundwater. This module owns *infrastructure* containment
+ the duty-side NULL. Harvest weekly at most; transport errors raise,
never cached; 429 propagates.
