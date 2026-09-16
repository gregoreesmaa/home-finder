# P4 POI meta-register verdict: audit SHIPS, layers GATED (issue #549)

Closes #549 — huvipunktid WFS cross-check + long-tail amenity upgrade.

Code: `services/scoring/dims_p4_poi.py` (agreement audit + 3 gated
long-tail dims); tests:
`services/scoring/tests/test_dims_p4_poi.py` (hermetic, fixture
counts/distances, no network).

## 1. Polite probe (2026-09-16, UA `home-finder-idea-probe/1.0`)

GetCapabilities only (no feature pull — per-type pulls belong to the
licence-day bulk job):

| Check | Result |
|---|---|
| URL | `https://gsavalik.envir.ee/geoserver/huvipunkt/wfs?service=WFS&request=GetCapabilities` |
| Result | **OPEN.** HTTP 200, 191 963 B, ~0.09 s. No 429, no key. |
| Feature types | **98** `huvipunkt:*` (full inventory in `HUVIPUNKT_TYPES`, names only — no points vendored): perearst/haigla/kiirabi, haridusasutus, raamatukogu, muuseum/teater/kino, ujula/supluskoht/spordihoone/staadion/tenniseplats, toitlustus, buss/rong/tramm/troll-peatused + terminalid, parkla, politsei/paastekomando, **ohtlik_ettevote**, **varjumiskoht**, hudrant/veevotukoht, kalmistu/kirik, sadam, matkarajad/terviserajad, post/pank, tervisekaubad… |
| CRS | EPSG:3301. updateSequence 1980. |
| Licence | **NONE confirmed** (no statement in capabilities; none in catalogue). **Gate holds: counts only, no points.** |

Harjumaa counts for 10 key types, per-type update stamps and CRS
validation of actual features need GetFeature pulls — deferred to the
licence-day job (single-probe budget spent; `agreement_audit()` ships
here so the job feeds counts straight into it).

## 2. Agreement-audit table: SHIPPED as a pure function

`agreement_audit()` maps caller-supplied {type, osm_n, reg_n} rows to
{verdict: register-rikkam / sarnane / osm-rikkam / võrdlus puudub} at
ratio edges 1.5 / 0.67 (pinned by test). The Harjumaa count table
itself is NOT pasted here — no feature pull was made, and inventing
counts would be fake precision. First bulk-job run pastes it into
this doc.

## 3. Long-tail shortlist (≥3, dense, no dedicated issue)

`raamatukogu` (libraries), `post` (post), `tervisekaubad`
(pharmacy-ish) — all in the observed 98, none owned by
#527/#528/#530/#531/#532. Walk bands ≤300/600/1000 m, NULL-beyond.
Dedicated split enforced by test (`DEDICATED_SPLIT`: perearst→#532,
haridusasutus→#530, spordihoone/staadion/ujula/tenniseplats/
supluskoht→#531, ohtlik_ettevote→#527, varjumiskoht/paastekomando→#528
— scored dims refuse these types with a "topeltarvestust pole"
reason).

## 4. Staleness note

Monthly intermediate layer ("vahekiht") over source registers of
varying vintage — every reason says so. Per-type staleness table is
licence-day work (first pulls record per-type stamps).

## 5. DoD evidence

```text
python3 -m pytest services/scoring/tests/test_dims_p4_poi.py -q
# → 9 passed (observed 2026-09-16, worktree 549-poi-register)
python3 -m pytest services/scoring/tests -q
# → full suite green, no regressions (see PR checks)
```
