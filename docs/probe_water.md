# Probe: Tallinna Vesi quality/hardness zones (#694) — verdict 2026-09-19

**Verdict:** dated negative. No keyless hardness/quality zones per district found.

**Method (polite, /tmp only):** single GETs with UA `home-finder-research/0.1`, `--max-time 20`, 429 = stop. Raw bodies in `/tmp/hf694_*`, never committed.
- `GET tallinnavesi.ee/` → 200 (363 KB).
- `GET tallinnavesi.ee/veetarbijale/joogivee-kvaliteet` → 200 (429 KB Next.js page): `Vee karedus` accordion is a generic city-wide hardness-scale explainer (0–0,5 mmol/l Pehme …); sampling points listed with Google-Maps links (`maps.app.goo.gl`), spread across service area but with no per-district zone values.
- No machine-readable export: no CSV/XLS/JSON dataset, no `/api/`, WMS/WFS/GeoJSON links (only Lottie animation JSON blobs); sole data-ish link is `tehniline.tallinnavesi.ee/...-tehnilised-nouded` (technical requirements, not zones).

**What would overturn:** a keyless URL with per-district hardness/quality zone values (CSV/JSON/WMS), licence allowing redistribution. Then file a scoped build issue (sidecar + dims + layer) and reference this probe.
