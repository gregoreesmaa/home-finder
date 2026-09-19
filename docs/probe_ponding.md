# Probe: cloudburst ponding (#706) — verdict 2026-09-19

**Verdict:** dated negative. No keyless machine-readable cloudburst ponding map found; guessed city catalogue URLs are absent and no WMS/WFS layer references surfaced.

**Method (polite, /tmp only):** single catalogue GETs with UA `home-finder-research/0.1`, `--max-time 20`, 429 = stop. Raw bodies in `/tmp/hf706_*`, never committed.
- `GET tallinn.ee/et/sademete-vesi` → 404 (only unrelated nav hit for "pilvelohkuja": a building-history article).
- `GET tallinn.ee/et/kliima` → 404 (same nav false positive; no sademevesi/uputus/PDF/WMS/WFS/GeoJSON refs).

**What would overturn:** a keyless WMS/WFS/GeoJSON URL with modelled cloudburst ponding depths + licence allowing redistribution. Then file a scoped build issue (sidecar + dims + layer) and reference this probe.
