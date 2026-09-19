# Probe: lamp-level lighting (#707) — verdict 2026-09-19

**Verdict:** dated negative. No keyless machine-readable lamp-location layer found; the city map is a JS app shell with no static layer references.

**Method (polite, /tmp only):** single catalogue GETs with UA `home-finder-research/0.1`, `--max-time 20`, 429 = stop. Raw bodies in `/tmp/hf707_*`, never committed.
- `GET geohub.tallinn.ee/arcgis/rest/services?f=json` → DNS NX (host absent).
- `GET geoportaal.tallinn.ee/` → DNS NX (host absent).
- `GET kaart.tallinn.ee/` → 200 (Experience Builder shell; no valgus/lamp/WMS/WFS layer refs in markup).

**What would overturn:** a keyless WMS/WFS/GeoJSON URL with street-lamp point locations + licence allowing redistribution. Then file a scoped build issue (sidecar + dims + layer) and reference this probe.
