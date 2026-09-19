# Probe: per-operator 5G coverage polygons (#691) — verdict 2026-09-19

**Verdict:** dated negative. No keyless Telia/Elisa/Tele2/TJA 5G coverage polygons or WMS found on the polite static surface.

**Method (polite, /tmp only):** single GETs with UA `home-finder-research/0.1`, `--max-time 20`, 429 = stop. Raw bodies in `/tmp/hf691_*`, never committed.
- `GET www.telia.ee/era/abi-ja-tugi/leviala` → 404 (282 KB JS shell); `GET www.telia.ee/leviala` → 404.
- `GET www.elisa.ee/leviala/` → 404.
- `GET www.tele2.ee/leviala` → 301 → `tele2.ee/leviala` → 200, 270 KB Next.js CMS page. Map is one JS-driven `data-content-type="network_outage"` widget (center 58.66N 24.95E); zero `<iframe>`, zero WMS/GeoJSON/API/endpoint refs in static HTML and in the 170 KB `__NEXT_DATA__` payload. Data endpoint (if keyless) lives inside a JS chunk — beyond polite probe budget.
- `GET ttja.ee/` → 200; only WMS refs are the generic Maa-amet base map (`teenus.maaamet.ee/ows/wms-valitsusportaal`); 5G page is regulatory text.
- `GET ttja.ee/.../netikaart` → 200; its "Interaktiivne kaart" is an unrelated Rail Baltica ArcGIS viewer (`gis.railbaltica.org`), not coverage.

**What would overturn:** a keyless operator coverage WMS/GeoJSON, or a TTJA coverage layer, appearing in a page shell or a documented endpoint. Then file a scoped build issue (sidecar + dims + layer) and reference this probe.
