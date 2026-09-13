# P4 maa-kataster — openness verdict + demo/coverage note (issues #245, #329)

> Verdict date: 2026-09-13 (all probes single polite fetches, cached
> `/tmp/hf-p4-maa-kataster/`, 3 s pacing, contact UA in headers).
> Code: `services/scoring/dims_p4_maa_kataster.py` (demo P4-004 + 3 coverage
> params); tests: `services/scoring/tests/test_dims_p4_maa_kataster.py`
> (hermetic, synthetic fixtures, no network).

## Verdict

| Source | Result | Evidence (2026-09-13) |
|---|---|---|
| Maa-amet **kataster map apps** (Maainfo / Kitsendused listings + descriptions, geoportaal.maaamet.ee) | **OPEN** | `kaardirakendused-p2.html` HTTP 200 (129 110 B); Kitsendused description HTTP 200 (63 930 B); Maainfo description HTTP 200 (989 603 B). |
| **KKIS public viewer** (kitsendused.kataster.ee, "Kitsenduste infosüsteem") | **OPEN, generalised — dated partial-negative for bulk detail** | Root HTTP 200 (24 538 B). But the Kitsendused description states: *"Vastavalt looduskaitseseaduse § 53 ei näidata I ja II kat. kaitseobjekte avalikus rakenduses. Logides sisse https://kitsendused.kataster.ee/ maaomaniku rollis on võimalik tutvuda kõigi piirangutega enda maatükil."* Full per-parcel detail needs owner login. |
| RIK **e-Kinnistusraamat** per-parcel depth (keelumärge/hüpoteek detail) | **RESTRICTED — dated negative for open bulk** | Tasuline / access-controlled register; no open per-parcel deed feed. Hence the P4-004/P4-020 weak-good cap (70). |
| **TPR** (tpr.tallinn.ee, P4-006) | **OPEN** | Root HTTP 200 (83 331 B, JS-shell SPA as expected). |
| **Ametlikud Teadaanded** (P4-020) | **OPEN** | Root HTTP 200 (92 326 B), public search UI + "Andmete taaskasutamine" (data-reuse) menu. |
| Tallinna **tasulise parkimise** deep URL (guessed, P4-013) | **404 — dated negative for that URL only** | Guessed `/et/parkimine/tasulise-parkimise-alad` → 404 ("Lehekülge ei leitud"); the Parkimine section itself exists in the nav. Zone polygons come from the live määrus lookup, never from the guessed link. |
| Legacy endpoints | **Retired — dated negatives** | `kaart.maaamet.ee/wms/kataster?...GetCapabilities` → 403 ("You don't have permission to access /wms/kataster"); `xgis.maaamet.ee/xgis2/page/app/kataster` → 200 "See link pole enam saadaval" (X-GIS2 retired, agency now Maa- ja Ruumiamet). Use the geoportal app menu, not these URLs. |
| `kkis.envir.ee` (guessed host) | **DNS NX — dated negative for that host** | `Could not resolve host`; the live viewer is kitsendused.kataster.ee. |

Consequence (honest shape): the per-parcel join (katastritunnus → KKIS
restrictions / TPR buffer / parking zone / AT notices) is implemented and
fixture-proven, but **production joins stay NULL** wherever the parcel is
unknown, the snapshot is missing, or the detail is owner-login-only — with
an Estonian reason naming the check (Maainfo/KKIS päring, notari kontroll,
TPR snapshot, parkimise määrus, AT otsing). Re-probe quarterly; a newly
opened bulk flips the verdict without code changes (ingestion already
caches with TTL).

Scope guard: Maa-amet WFS for parameters3 G3 params is overturn issue
#235's territory — this module touches no `dims_group03*.py` or other
shared/group files.

## Pull policy (polite, cached, TTL-stated)

- One request per source per run; `User-Agent: home-finder-research/0.1`
  (polite kataster/KKIS harvest; issue 245); 25 s timeout; 3 s pacing.
- `fetch_cached(url, cache_dir, name, ttl_days)`: fresh cache wins (no
  request); transport errors are raised and **never cached as data**; HTTP 429
  raises immediately (stop signal, no retry).
- TTLs: kataster geometry **91 d** (quarterly), KKIS restrictions **30 d**,
  TPR pipeline **7 d** (weekly), parking zones **365 d** (regulation-driven),
  AT notices **7 d** (polite weekly pull of a daily feed).

## Per-param wiring (all honest shapes = per-parcel join)

| Param | Wired leg (this ingestion) | Legs honestly missing (EI OLE, named not faked) |
|---|---|---|
| P4-004 kinnistus-süva | KKIS arest/keelumärge → 25; lone hüpoteek → 55; clean public layer → capped 70 | RIK tasuline extract detail; owner-login restriction detail |
| P4-006 naaber-planeering | TPR `menetluses`/`algatatud` ≤ 500 m → 45; only `kehtestatud` → 65; empty buffer → 70, always snapshot-dated | plans beyond the snapshot ("no plans exist" never claimed) |
| P4-013 parkimine+hoov | zone A −20 / B −10 / C −5 from 70; roomy courtyard (≥ 0.3) +10 (cap 85) | zone unknown → NULL even with courtyard known; missing courtyard named in reason |
| P4-020 enforcement | active pankrot/täitemenetlus → 20; historical AT only → 55; clean check → capped 70 | Creditinfo scores, unpublished detail |

Never a gradient: no distance weighting, no interpolation, exact-parcel
joins only; `plans=None` means "no TPR snapshot" (NULL), never "empty
buffer" (pass `[]`); ambiguity (P4-004 cap, P4-020 cap) never pushes the
steal sort above 70.

Layer #491 (`maaparcel` overlay, p364 ships twice) consumes the #235
verdict (`docs/overturn_maa.md` + #491 harvest addendum +
`services/scoring/dims_overturn_maa.py`): the map sidecar
`maa/parcel-areas.json` (offline build via
`scripts/build/batch_maaparcel_kataster.py` off the cached WFS GeoJSON)
carries the same 100-parcel Kesklinn sample the scorer joins —
omandivorm-class fills only (register facts, never suspicion scores),
outside stays unknown. The P4-004 closing-block leg above is untouched
(distinct question off the same source family, no shared helper).
