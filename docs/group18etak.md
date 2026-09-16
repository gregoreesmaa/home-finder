# ETAK measured-geometry upgrade verdict (issue #552)

Closes #552 — measured land-cover/water/relief legs from ETAK maakate +
hüdrograafia + pinnamood. One ETAK family → one issue, three legs
(upgrades, not new questions).

Code: `services/scoring/dims_group18etak.py` (3 scored upgrade dims +
1 licence-gated NULL); tests:
`services/scoring/tests/test_dims_group18etak.py` (hermetic, fixture
artefacts, no network).

## 1. Polite probe (2026-09-16, UA `home-finder-idea-probe/1.0`)

8 pulls total, `--max-time 30`, 2 s pacing, no retries, 429 = stop
(none seen). Raw bodies: `/tmp/hf552-*` (one-off PR record, not
committed):

| Check | Observed | Meaning |
|---|---|---|
| `geoserver/etak/wfs?service=WFS&request=GetCapabilities` → HTTP 200, 147 052 B, ~0.10 s | **OPEN.** 39 feature types incl. `e_306_margala_a` (märgala), `e_302_ou_a` (õued), `e_202_seisuveekogu_a` (seisuveekogu), `e_203_vooluveekogu_a/j` (vooluveekogu), `e_204_kaldajoon_j`, `e_206_truup_j` (truubid), `e_102_nolv_j` (nõlvad), `e_103_pinnavorm_j/p`, `e_101_kivi_p` | All three themes served, no key |
| `…DescribeFeatureType&typeName=e_306_margala_a` → HTTP 200, 2555 B | `kood/kood_tekst, tyyp/tyyp_tekst, puis/puis_tekst, muutmisaeg, geom_muutmisaeg` | Wetland class + woodiness + per-tile vintage |
| `…DescribeFeatureType&typeName=e_202_seisuveekogu_a` → HTTP 200, 2885 B | `+ nimetus, kkr_kood, kpo_seos` | Named waters with registry codes |
| `…DescribeFeatureType&typeName=e_102_nolv_j` → HTTP 200, 2862 B | `+ kaldaastang/kaldaastang_tekst` | Scarp flag on slopes |
| `…GetFeature&typeName=e_306_margala_a&count=1` → HTTP 200 | `numberMatched="54929"`, sample tyyp `Soovik`, `muutmisaeg 2018-01-23`, `geom 2009-07-29`, CRS EPSG:3301 | 54 929 wetlands nationwide; DAILY feed, survey vintages vary by tile |
| `…GetFeature&typeName=e_202_seisuveekogu_a&count=1` → HTTP 200 | `numberMatched="122109"` | 122 109 standing waters nationwide |
| `…GetFeature&typeName=e_102_nolv_j&count=1` → HTTP 200 | `numberMatched="21745"` | 21 745 mapped slopes/scarps nationwide |
| `…GetFeature&typeName=e_306_margala_a&resultType=hits&bbox=6580000,530000,6600000,560000,EPSG::3301` → HTTP 200 | `numberMatched="178"` (bbox axis order N,E — first E,N attempt returned 0, corrected) | Live discrimination in the buyer area |

CRS: EPSG:3301 throughout (sample geometries `srsName
urn:ogc:def:crs:EPSG::3301`). Vintage/update: DAILY WFS vs per-tile
survey vintages — vintage in every reason, never mixed silently.
Licences: CC BY 4.0 for maakate/hüdrograafia (catalogue claim);
**pinnamood licence unstated → verify-or-close for that leg only**
(`dim_etal_relief` always NULL, stated in code + reason).

## 2. Per-leg old→new justification table

| Leg | Old proxy rule | New measured rule (this module) | Evidence |
|---|---|---|---|
| Dampness (p405/p468/p479 cousins) | OSM-tag dampness/daylight proxies | `wetland.inside` + tyyp: madalsoo/raba → 25, soovik/õõtsik → 35, other → 30; ≤50 m → 55, ≤150 m → 70; else NULL | 54 929 polygons with tyyp split; 178 in Tallinn bbox |
| Drainage (p50 open-water hinnang) | open-water hinnang | `water.inside` → 30; ≤30 m → 50; ≤100 m → 65; else NULL; name/kind in reason | 122 109 standing waters + named flow network + truubid type present |
| Impervious/green (p181/p63) | impervious/green proxies | `yard.klass`: eraõued/tootmisõued → 45, haljasala → 70, muu → 60; outside → NULL | `e_302_ou_a` courtyard class served |
| Runoff (slope/ditch) | runoff flag proxy | **GATED NULL** — pinnamood licence unverified | 21 745 slopes served but unscored until licence proof |

Where ETAK contradicts OSM, ETAK wins; reasons carry the vintage +
"mõõdetud … OSM asemel ETAK" marker. Absolute 0–100 kept; NULL where
ETAK has no feature (never zero).

## 3. Pre/post discrimination (fixture windows, clearly synthetic)

`histogram()` + `test_upgrade_discriminates_on_fixture_windows`:
12-lot windows, edges [50, 150] m to wetland — old proxy bins by tag
presence; measured metres spread Tallinn `[5,4,3]` vs rural `[0,0,12]`.
Synthetic illustration only — the real Tallinn+rural histograms run in
the bulk job once it owns the WFS harvest (helper + edges ship here).

## 4. Judgment calls for the reviewer

1. Water bands stay distance-only (old p50 edges stand; width/type
   re-justifies in the reason until the bulk job measures widths).
2. No ETAK transport/buildings legs here (#536 + G18 own them).
3. No re-labelling of ETAK classes into new buyer questions (upgrade
   only; #546 CHM is the vertical sibling — coordinated, not merged).
4. No shared-file edits: 3 new files only.
5. Bbox axis-order trap documented above (N,E for EPSG:3301 on this
   server) so the bulk job does not repeat the empty-bbox mistake.

## 5. DoD evidence

```text
python3 -m pytest services/scoring/tests/test_dims_group18etak.py -q
# → 11 passed (observed 2026-09-16, worktree 552-etak-measure)
python3 -m pytest services/scoring/tests -q
# → full suite green, no regressions (see PR checks)
```
