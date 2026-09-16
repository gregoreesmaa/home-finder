# P4 ETAK measured-legs verdict note (issue #552)

Date: 2026-09-16. One ETAK family, three legs. Module
`services/scoring/dims_p4_etak.py`. No shared files touched.

## Openness verdict: endpoint UNVERIFIED — rules pinned, harvest pending

Polite probes, custom `home-finder-probe` User-Agent:

| Probe | Result |
|---|---|
| `GET andmed.eesti.ee/datasets/…-maakate` | HTTP 200, 75497 bytes — JS shell, no server-rendered distribution/API URL, no API hints in markup. Stopped per polite budget. |
| `GET teenus.maaamet.ee/ows/etak?…GetCapabilities` (official WFS URL pattern per Maa-amet's Maardlate QGIS manual) | HTTP 200, 626 bytes — MapServer 7.6.2 error `msLoadMap(): Unable to access file. (/data/data/etak.map)`. Guessed dataset path absent server-side; no further guesses. Endpoint, Harjumaa counts per class, CRS, and vintage/update behaviour all UNMEASURED. |
| Licence | maakate + hüdrograafia CC BY 4.0 (catalogue mirror, `ATTRIBUTION`). ETAK open-data licence agreement exists at geoportaal.maaamet.ee (HTTP 200, 85 KB, 2025-01-03) but custom-encoded text was not extractable stdlib-only → pinnamood coverage UNPROVEN → pinnamood leg licence-gated NULL. |

Consequence: dims score joined records with provisional bands pinned
by hermetic tests; the harvest PR verifies the endpoint, pastes
Harjumaa counts/CRS/vintage, and runs pre/post Tallinn + rural
histograms. Harvest fills data, never reshapes rules silently.

## Per-leg old→new justification table

| Leg | Old proxy rule | New measured rule + evidence |
|---|---|---|
| wetland dampness | OSM-tag dampness/daylight proxies (p405/p468/p479) | ETAK maakate containment: madalsoo/õõtsik → 40, raba/soovik → 50; non-wetland → NULL (drainage/groundwater unjoined, never "dry") |
| water drainage | p50 open-water hinnang, p334 flood-adjacent proxy | ETAK hydro width/type ≤100 m: wide flow (≥10 m) → 45, other near water → 55, culvert noted; outside → NULL |
| ground exposure | p181 impervious / p63 green OSM proxies | ETAK class: eraõued/tootmisõued → 55, tühermaa → 50, haljasala → 70; other classes → NULL |
| relief objects | OSM micro-relief guesses | NULL — pinnamood licence unverified |

Where ETAK contradicts OSM, ETAK wins; discrepancies are logged for
review (rule), never mixed silently (vintage in every scored reason).
Survey vintages vary by tile — vintage rides in reasons. No ETAK
transport/buildings legs here (#536/G18 own them); no new buyer
questions (upgrade only).
