# Probe: Paljassaare odor footprint (#710) — verdict 2026-09-19

**Verdict:** dated negative. No keyless machine-readable odor-footprint zone map found; the footprint lives inside EIA PDFs only.

**Method (polite, /tmp only):** docs search + single catalogue GETs with UA `home-finder-research/0.1`, `--max-time 20`, 429 = stop. Raw bodies in `/tmp/hf710_*`, never committed.

**What would overturn:** a keyless WMS/GeoJSON/SHP URL with odor zones over Pohja-Tallinn + licence allowing redistribution. Then file a scoped build issue (sidecar + dims + layer) and reference this probe.
