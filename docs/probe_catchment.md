# Probe: school catchment polygons (#705) — verdict 2026-09-19

**Verdict:** dated negative. No keyless machine-readable assigned-school catchment polygons found; guessed city catalogue URLs are absent and no WMS/WFS layer references surfaced.

**Method (polite, /tmp only):** single catalogue GETs with UA `home-finder-research/0.1`, `--max-time 20`, 429 = stop. Raw bodies in `/tmp/hf705_*`, never committed.
- `GET tallinn.ee/et/koolide-tegevuspiirkonnad` → 404.
- `GET tallinn.ee/et/elukohajargne-kool` → 404 (no tegevuspiirkond/PDF/XLSX/CSV/WMS/WFS/GeoJSON refs).

**Combination with #687:** if school point/address data lands via #687, catchments could be derived (nearest-school Voronoi) or revisited when the city publishes tegevuspiirkond address lists; this probe stays negative until a keyless polygon or address-list source appears.

**What would overturn:** a keyless WMS/WFS/GeoJSON URL with assigned-school zones, or a machine-readable per-school address list + licence allowing redistribution. Then file a scoped build issue (sidecar + dims + layer) and reference this probe.
