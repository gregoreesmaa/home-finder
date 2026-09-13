# Overturn hunt log — Maa-amet WFS: G3 parcels/KKIS/maardlad + G4 p76/p229/p364 partials (issue #235)

> Polite WFS harvest for Group 3 (parameters3.md §5.3) folded in Group 4
> partials by data source (parameters3.md §5.4).
> Probed 2026-09-13 (11 polite GETs total, labelled research user-agent
> `home-finder-research/0.1 (... issue 235)`, paced ≥ 3 s, `count ≤ 100`
> per parameters3.md §5.3, raw bodies at `/tmp/hf-235-maa-wfs/`, never
> committed). **Verdict: 7 per-parcel dims FLIP to honest joins, the
> 03B/C/D/E remainder stays NULL (dated negative).** The test-pinned dims
> live in `services/scoring/dims_overturn_maa.py`, pinned by
> `services/scoring/tests/test_dims_overturn_maa.py`.
> Re-check the dated negatives no later than **2027-03-13**.

## Verdict

| Param | Verdict | Shape (all per-parcel joins, never gradients) |
|---|---|---|
| p29 lot size | **FLIP** | `kataster:ky_kehtiv.pindala` vs the G03 Tallinn band (same band as `dim_lot_size`, cadastre source named) |
| p68 soil | **FLIP (weak)** | `veeveeb:mullad_boniteet.mullaklass` ∈ {hea→65, halb→45}; fertility, not bearing — capped, 2017 vintage in the reason |
| p71 easements | **FLIP** | public KKIS polygon hit count: 0→70 (capped, generalised layer), 1–2→60, 3+→40; rule text thin (`reegel` None live), so count, never depth |
| p75 boundaries | **FLIP (weak hint)** | recorded valid `eKataster:moodistuspunktid` markers ≥2→65 / 0–1→45; RECORDED, never found — on-site check stays |
| p76 mineral/water/timber rights | **FLIP (weak)** | leviala inside→50, near ≤2 km (vertex proxy, labelled jäme)→60, far→NULL; deposits nearby, never this parcel's severance |
| p229 severance | **FLIP (suspicion only)** | inside leviala→45 KAHTLUS, outside→NULL (no near-band — severance is a deed fact; RIK extract stays named) |
| p364 ground lease | **FLIP (hint)** | `ky_kehtiv.omvorm`: Eraomand→70 (capped), Riigi/Munitsipaalomand→50 + hoonestus-check, unknown→NULL |
| p183/p184/p201/p228/p251/p254/p256/p258/p273/p277/p331/p337/p339/p397/p400 | **STAY NULL** | no joinable layer in the 1091-name search; `EHITUSGEOLOOGIA_ALA_*` is a study-area register, not a parcel class |

No-map gradients stay invalid throughout: every flipped shape is a
per-parcel fact (nomap.md §3 G3/G4 reasoning unchanged — an area heatmap
of lease suspicion or marker counts would still be fake precision).

## Openness evidence (one polite round, 2026-09-13)

| Check | Observed | Meaning |
|---|---|---|
| `GetCapabilities` (`gsavalik.envir.ee/geoserver/wfs`) | 200, 1 345 735 B, 1091 unique `<Name>` layers (same byte count as the independent #248 probe — corroborated) | endpoint open, no auth, no key |
| `DescribeFeatureType kataster:ky_kehtiv` | 3 943 B; fields `tunnus, pindala, omvorm, siht1/2/3, haritav/rohumaa/mets/ouemaa/muumaa, maks_hind, l_aadress, registr, marked, ...` | p29 + p364 field contract verified |
| `GetFeature ky_kehtiv count=3` (Tallinn bbox) | 3 features, e.g. `65301:001:0453 / 1008 m² / Eraomand / ELAMUMAA / Aasa tn 1c` | live parcel records serve GeoJSON |
| `GetFeature ky_kehtiv count=100` (city-centre bbox) | 100 features; `omvorm` = Eraomand 69 / Munitsipaalomand 27 / Riigiomand 2 / NULL 2; `siht1` = ELAMUMAA 37 / TRANSPORDIMAA 28 / ARIMAA 22 / ... | **p364 domain verified — the field exists** (issue acceptance); mixed ownership makes the hint discriminate |
| `DescribeFeatureType kataster:ky_omandivorm` | same parcel fields incl. `omvorm` | second ownership leg confirmed |
| `DescribeFeatureType kitsendus_suunatud:kma_avalik_asjaoigus` | 2 461 B; fields `nimi, klass, voond_liik_id_vaartus, reegel, ulatus, ...` (+ 17-sibling `kma_avalik_*` family, `kpo_avalik_*`, `kmakitsendused` mirrors) | p71 join contract verified |
| `GetFeature kma_avalik_asjaoigus count=5` | 5 features, e.g. `Odra tänav kasutusõiguse ala / TKTV / Piiratud asjaõigusega ala`; `reegel` None, `ulatus` '0' | restrictions serve; rule-text leg thin → count shape, not depth |
| `DescribeFeatureType + GetFeature count=2 eKataster:moodistuspunktid` | fields `piiripunkti_nr, punkti_liik, piirimark_paigaldus, kehtiv/kehtetu, ...`; live `piirinael` markers (`paigaldus: taastatud piirimärk`, `ankur: true`) | p75 recorded-marker hint grounded |
| `DescribeFeatureType + GetFeature veeveeb:mullad_boniteet` | fields `mullaklass` (+ objectid/sys_id/versioon); live Polygons | p68 join contract verified |
| `GetFeature mullad_boniteet count=100` (Tallinn bbox) | 100 features; `mullaklass` = hea 58 / halb 42; `versioon` ≡ 2017-03-03 | **p68 domain verified; vintage dated** (in every reason) |
| `DescribeFeatureType maaamet:EHITUSGEOLOOGIA_ALA_LIIK` | fields `ID/VIIT/NIMI/AASTA/SIFFER/AUTOR/LIIK/STAADIUM/MAX_SYGAV/...` | study-area register (who dug where), NOT a parcel soil class → 03B/C/D/E negative stands |
| maardlad layers | NOT re-pulled (politeness) — cited from `docs/p4_maa_subsurface.md` (GetCapabilities + DescribeFeatureType evidence for `maavarad_gbmv_levialad/leiukohad`, 2026-09-13) | same endpoint, own cache subdir here |

Total: 11 live GETs (1 caps + 5 DescribeFeatureType + 5 GetFeature, all
`count ≤ 100`), paced ≥ 3 s, one 429-free round. No scraping, no auth,
no bulk download.

## Near-miss proxies considered and refused

- **p29 as area gradient**: the cadastre area is the listing's OWN lot —
  painting neighbouring lots' sizes as a heatmap is the G3 fantasy
  nomap.md already refuses. Per-parcel join only.
- **KKIS rule text as depth** (`reegel`): None in every live sample —
  scoring "severity" off empty rule text would be fake precision. Count
  only.
- **Survey markers as found**: the layer records installation state
  (`taastatud piirimärk`), not findability — a nail under new asphalt
  still counts as "kirjas". Hence cap 65 + on-site check, never higher.
- **Bonitet as bearing capacity**: fertility classes say nothing about
  piles vs pads — hea caps at 65, and the EGT class (P4-016) stays named.
- **Distance-to-deposit as severance gradient**: refused — p229 has NO
  near-band by construction; distance to a polygon is not a deed.
- **omvorm as lease verdict**: municipal land is OFTEN, not always,
  hoonestus-leased — 50 is suspicion with the RIK check, never a verdict.

## What stays open (overturn path, not wired here)

A parcel soil bearing-capacity class appears on WFS (then p68 upgrades
from bonitet), KKIS rule texts populate (then p71 scores depth), or a
03B/C/D/E layer (water table, geothermal, septic, riparian) appears in
the caps search → re-open #235 and propose the join. Shared/group files
(`dims_group03*.py`, `dims_group04.py`, sibling P4 maa modules,
`livability.py`, WEIGHTS, `docs/nomap.md`) are deliberately untouched —
the final docs-index PR updates nomap.md. Overlap boundaries for the
rebalance follow-up: P4-004 owns closing-block, p71 owns use-burden;
P4-054 owns blast/truck noise, p76/p229 own rights hints; P4-016 owns
the EGT class, p68 owns bonitet; G03 owns the listing-record p29, this
module owns the cadastre p29 leg (same band — they cannot disagree).

## Addendum — harvest run #491: parcel/KKIS polygons for the map (2026-09-13)

Group B verify-first follow-up (issue #491): the per-parcel joins above
needed a map shape, so a second polite round ran the same day (5 GETs
total: 1 × DescribeFeatureType + 4 × GetFeature, labelled research
user-agent `home-finder-research/0.1 (... issue 491)`, paced ≥ 3 s,
`count ≤ 100`, raw bodies at `/tmp/hf-491-maa-parcel/`, never committed;
**zero HTTP 429** — no stop triggered).

| Pull (Tallinn bbox 24.5/59.35/24.9/59.5 unless noted) | Observed | Meaning |
|---|---|---|
| `GetFeature kataster:ky_kehtiv count=5` (city bbox) | 5 features, 4 800 B | parcels serve GeoJSON, field contract unchanged |
| `GetFeature kataster:ky_kehtiv count=100` (Kesklinn window 24.74–24.76 / 59.428–59.438) | 100/100 Polygon, `omvorm` = Eraomand 54 / Munitsipaalomand 42 / Riigiomand 2 / **Avalik-õiguslik omand 2** (new fourth class vs #235), `siht1` = ARIMAA 36 / TRANSPORDIMAA 26 / ELAMUMAA 19 / … | **map sample fixed**: 100 parcels, paint classes era/muni/riik/muu (fourth class folds to muu — 2/100 is noise, raw omvorm rides along) |
| `GetFeature kma_avalik_asjaoigus count=10` (same window) | 10 features (TKTV, `reegel` None throughout — thin rule leg confirmed again), 11 rings | KKIS touch join is join-proven but thin: centroid-only containment hits **0/100** (meter-scale strips miss centroids); coarse touch join (centroid OR any vertex either way) hits **5/100** (2×1, 3×2) — ships as `kkis` hint count, never depth |
| `GetFeature maaamet:maavarad_gbmv_levialad count=10` (city bbox) | 10 levialad (Väo kihistu perspektiivne ala, Harku, … — all at the city edges), **0 touching the parcel window** | harvest TALLY only: deposit polygons as a buyer layer is a second question for a follow-up; p76/p229 scorer dims untouched |

Map verdict: **`maaparcel` (p364 ships twice)** — the 100-parcel sample
paints as an omandivorm-class choropleth (register facts, never
suspicion scores; outside the window = teadmata, mitte tühi), wired by
`scripts/build/batch_maaparcel_kataster.py` →
`<snap>/maa/parcel-areas.json` → `/api/layers/maaparcel/areas`
(issue #491; floodzone #487 precedent). The #235 scorer dims, TTLs, and
re-check date (2027-03-13) are unchanged — this run doubles as the first
scheduled re-probe: endpoint still open, field contracts unchanged,
fourth omvorm class noted.
