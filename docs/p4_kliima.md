# P4 kliima verdict note (issues #319 demo + #378 coverage)

Date: 2026-09-13. Scope: P4-010 (demo) plus the 1 coverage param in
#378, both consuming the Tallinna kliimakava source
(`services/scoring/dims_p4_kliima.py`). The sibling legs that score
stay where they live — untouched (EIS register in `dims_p4_eis.py`,
EHR mirror in `dims_p4_ehr.py`, Päästeamet rule join in
`dims_p4_paaste.py`, KAUR cross-check in `dims_p4_kaur.py`).

## Openness verdict: dated negative (strategy pages + PDFs, no feed)

Polite probes, one GET/HEAD each, `home-finder-kliima-verification`
User-Agent, `--max-time 20/25`, 2 s pacing, cached to
/tmp/hf-kliima-probe (one-off PR record, never committed),
2026-09-13 ~UTC:

| Probe | Result |
|---|---|
| `GET tallinn.ee/en/strateegia/climate-neutral-…-2030` | HTTP 200, 49135 bytes, ~4224 visible chars — SECAP 2030 storefront; 0 for csv / geojson / wfs / andmestik / masinloetav / download |
| `GET tallinn.ee/et/strateegia/tallinna-kliimakava` | HTTP 200, 43090 bytes, ~3357 visible chars — "kliimaneutraalsus aastaks 2050" human page; same zero sweep; only data-ish link is one more /et/media/ PDF |
| `HEAD tallinn.ee/et/media/309750` | HTTP 200, application/pdf — SECAP 2030 publication (human document, not a feed) |
| `HEAD tallinn.ee/et/media/310541` | HTTP 200, application/pdf — second kliimakava publication (human document, not a feed) |
| `GET andmed.eesti.ee/dataset?q=kliimakava` | HTTP 200, 75497 bytes, 12 visible chars ("Teabevärav" JS shell) — no server-rendered dataset |
| `GET tallinn.ee/avaandmed/` | HTTP 301 → `andmed.eesti.ee/datasets?ih=tallinna-linnavalitsus` → HTTP 200, same 75497-byte JS shell |

No machine-readable per-linnaosa renovation-target table and no
heating-transition zone layer verified on 2026-09-13 — dated
negative keeps this verdict. Consequence, kept honestly in code:

- No fetch/parse helpers are staged: unused ingestion would be fake
  progress, and downloading + parsing the PDFs would be scraping
  publications, not polling a feed.
- Both dims return NULL for every input with an Estonian reason.
  No target table = no district gradient = NULLs until a feed is
  joined. That is the honest shape, not a gap to paper over.

## Honest-shape table (kliimakava legs only)

| Param | Kliimakava slice | Shape when joined | When missing |
|---|---|---|---|
| P4-010 grant (demo) | renoveerimiseesmärgid per linnaosa (source 6 of 6) | per-building dim: district-target pressure | NULL → EIS register + KÜ |
| P4-059 wood-burning (coverage) | heating-transition zones (source 5 of 6) | per-parcel rule join: transition-zone table | NULL → EHR heating type + Päästeamet/Keskkonnaamet notices |

## Pairing rationale (why these legs, why NULL)

- P4-010: the kliimakava leg is district-target *pressure* (does the
  city push renovation in this linnaosa), not the grant *status* —
  the register stays scored in `dims_p4_eis`, the energy-class
  mirror in `dims_p4_ehr`, the KÜ-toetused leg NULL in
  `dims_p4_komun`. Scoring a building's grant odds off a district
  ambition paragraph would be fake precision.
- P4-059: the kliimakava leg is the *transition-zone table* (which
  parcels move off solid fuel when), not the enforceable rule — the
  rule join stays scored in `dims_p4_paaste` (keelatud→20 /
  piiratud→50 / lubatud→75), the monitoring cross-check in
  `dims_p4_kaur`, the notices legs NULL in `dims_p4_kesk` /
  `dims_p4_komun`. Same split-slice precedent as P4-020 (ATA
  notices vs bureau scores).
- Registry keys (`kliima_renovation_targets`, `kliima_heating_zones`)
  are prefixed so they cannot collide with the sibling P4-010 /
  P4-059 keys (`eis_grant_status`, `burn_restriction`,
  `kesk_woodburning_zones`, `woodburning_zones`, …).

## TTL

One-off check 2026-09-13 (nothing cached, nothing consumed).
Re-check annually or when a machine-readable kliimakava table
appears (linnaosa-target CSV, transition-zone WFS/GeoJSON, or a
Teabevärav dataset). Strategy horizon 2030, neutrality 2050.
