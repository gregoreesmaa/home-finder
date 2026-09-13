# Parameter layers — how every parameters3.md parameter is implemented

`parameters3.md` catalogs **500 parameters** (§5, 20 groups; §8 verification
index). This document is the implementation registry: **every one of the 500
is implemented on `main`**, either as a map layer or as a documented
no-map verdict with a scorer dimension. No parameter is guessed, faked, or
left without an owner.

Live maps: `/layers` (dev: `npm run dev --workspace @home-finder/web`).
Data: local snapshot `2026-09-12` (`~/hf-data/2026-09-12`). No live
Overpass/API calls in the map path.

## 1. The three implementation kinds

Every parameter gets exactly one verdict, following AGENTS.md §7 (Evidence
before claims, Honest systems over fake precision, Zero synthetic guessing):

| Kind | Meaning | Where |
|---|---|---|
| **Map layer** | Green = good, red = bad, measured along the real Harjumaa footpath network (or an honestly-labelled Euclidean/proxy kernel). Scores absolute 0–100. | `apps/web/lib/layers*.ts` (`paramIds`), raster masters in the snapshot |
| **Honest proxy** (`hinnang`) | A map layer where the title, legend and source say it is a proximity/estimate proxy — never measured registry data. Used where no registry data exists in the snapshot but an OSM signal honestly discriminates. | Same registry, `(hinnang)`/`(proksi, hinnang)` titles |
| **Documented no-map** | No gradient map ships (OTA PR #131 precedent: a map that cannot honestly discriminate misleads). The verdict file documents WHY with snapshot evidence, points at the nearest shipped map if one exists, and the parameter ships as a **scorer dim**: a pure hermetic function `(origin, pois) -> (score | None, Estonian reason)` in `services/scoring/dims_*.py`. Per-deal, per-parcel, legal, macro-series, forensic and subjective params live here — they describe a deal, a parcel, a person or a workbench, not a place. | `GROUP*_NO_MAP` verdicts + `dims_*.py` |

Batch convention (see `apps/web/lib/layers_group03b.ts`, issue #152): each
batch is self-contained — one `layers_group*.ts` verdict registry, one
`dims_*.py` scorer module, one test file per side, **zero shared-file
edits** (`*_HOOK` marker states the no-wiring contract). Reasons are in
Estonian; NULL dims carry `hinnang` + `EI OLE` markers pinned by tests.

## 2. Counts (machine-verified)

```
owned: 500
missing: 0 []
```

Audit command (run from repo root; `origin/main` or any commit):

```bash
python3 -c "
import subprocess, re
files = subprocess.run(['git','ls-tree','-r','--name-only','origin/main',
  '--','apps/web/lib/'], capture_output=True, text=True).stdout.splitlines()
ts = [f for f in files if f.endswith('.ts') and '.test.' not in f]
owned = set()
for f in ts:
    c = subprocess.run(['git','show','origin/main:'+f],
      capture_output=True, text=True).stdout
    for m in re.findall(r'ALL_PARAMS\s*=\s*\[([^\]]*)\]', c):
        owned |= {int(n) for n in re.findall(r'\d+', m) if 1 <= int(n) <= 500}
    for m in re.findall(r'PARAM_IDS[^=]*=\s*\{([^}]*)\}', c):
        owned |= {int(n) for n in re.findall(r':\s*(\d+)', m) if 1 <= int(n) <= 500}
    for m in re.findall(r'paramIds:\s*\[([^\]]*)\]', c):
        owned |= {int(n) for n in re.findall(r'\d+', m) if 1 <= int(n) <= 500}
pys = subprocess.run(['git','ls-tree','-r','--name-only','origin/main',
  '--','services/scoring/'], capture_output=True, text=True).stdout.splitlines()
for f in [f for f in pys if f.endswith('.py') and '/tests/' not in f and 'dims_' in f]:
    c = subprocess.run(['git','show','origin/main:'+f],
      capture_output=True, text=True).stdout
    owned |= {int(m) for m in
      re.findall(r'^[\s*#\"\']*[\*\-]\s*p(\d{1,3})\b', c, re.M) if 1 <= int(m) <= 500}
print('owned:', len(owned))
print('missing:', sorted(set(range(1, 501)) - owned))
"
```

Split (same method, `paramIds` values only): **94 map-layer params**,
**406 documented no-map + scorer dim**. Map layers never render unknown as
zero: null encodes 255 and renders red (red = bad *or* honestly-unknown).

## 3. Group reconciliation (parameters3.md §5 → implementation)

| Group | Params | Map layers (paramIds) | No-map + dims | Batch files |
|---|---|---|---|---|
| 1 Listing portals (40) | 40 | — | 40: per-listing facts, no area signal | `layers_group01a/b` + `dims_group01a/b` (#202, #203) |
| 2 EHR registry (9) | 9 | 196 | 21, 30, 33, 35, 48, 79, 154, 495 | `layers_group02/02b` + `dims_group02/02b` (#136, #137) |
| 3 Cadastre (22) | 22 | 50, 332, 340 | 19 incl. 29, 68, 71, 75 | `layers_group03/03b/03c/03d/03e` (#151–#155) |
| 4 Title/legal (17) | 17 | — | 17: per-parcel registry facts | `layers_group04` + `dims_group04` (#204) |
| 5 Plans (27) | 27 | 42, 44, 106, 146, 223, 224, 225, 230, 381, 485 | 17 | `layers_group05a–05f` (#161–#166) |
| 6 Heritage (12) | 12 | 72, 352, 353, 356 | 8 | `layers_group06/06b` (#138, #139) |
| 7 Env health (20) | 20 | 61, 62, 189, 202, 227, 257, 409, 450 | 12 | `layers_group07/07b/07c/07d` (#140–#143) |
| 8 Climate/flood (16) | 16 | 69, 255, 333, 334, 336, 447 | 10 | `layers_group08a–08d` (#167–#170) |
| 9 Noise (8) | 8 | 16, 138, 162, 234, 301, 408, 445, 493 (proxies) | — | `layers_group09` + `layers_genv` (#104, #124) |
| 10 Utilities (18) | 18 | 215 | 17 incl. 51, 53, 54, 262, 265 (dims; map masters on local-wip-savepoint, not yet merged) | `layers_group10rest` + `dims_group10/10b/10c/10rest` (#105, #107, #121, #171) |
| 11 OSM amenities (24) | 24 | 23: 14, 19, 20, 84, 86–89, 101–103, 108, 124, 169, 190, 313, 338, 346, 419, 442, 462, 466, 470 | 317 (no-map) | `layers.ts` core + `layers_batch1` + `layers_group11c/d` + dims (#98, #134, #135) |
| 12 Transit (5) | 5 | 15, 125, 343 | 11, 17 (commute dims, no layer) | core + `layers_batch4` + `dims_group12`/`dims_batch6` (#99, #126, #133) |
| 13 Logistics (5) | 5 | 141, 220, 270, 282, 342 | — (all five ship; 220/270 via batch6 mobility proxies) | `layers_batch4/6` + `dims_group13` (#99, #126, #133) |
| 14 Safety (5) | 5 | 13, 78, 315, 335, 467 (proxies) | — | `layers_batch5` (#102) |
| 15 Education (5) | 5 | 12, 123, 130, 314, 386 | — | core + `layers_group15` + `layers_batch6` (#116, #133) |
| 16 Macro/finance (44) | 44 | — | 44: market-wide series / deal facts, not place-varying | `layers_group16a/b` + `dims_group16a/b` (#205, #206) |
| 17 HOA (22) | 22 | 187, 245, 311, 312, 469 | 17 incl. p3, p4 | `layers_group17a/b/c/rest` (#177, #178, #196, #207) |
| 18 Spatial sim (29) | 29 | 7: 34, 63, 181, 305, 405, 468, 479 | 22 (scorer dims: solar/shade/traffic/vegetation proxies + no-map verdicts) | `layers_group18resta/b/c` + `layers_genv` + `dims_group18*` (#113, #122–#124, #172, #173, #197) |
| 19 Inspection (134) | 134 | — | 134: forensic facts needing presence/meters | `layers_group19a–19d` + `dims_group19a–19d` (#208–#211) |
| 20 Subjective (38) | 38 | — | 38: buyer-profile inputs, never area scores | `layers_group20a/b` + `dims_group20a/b` (#212, #213) |
| **Total** | **500** | **94** | **406** | **§4** |
