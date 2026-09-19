# Probe: LKF claim stats (#708) — verdict 2026-09-19

**Verdict:** dated negative. No keyless machine-readable sub-county claim stats found; LKF publishes statistics as PDFs only.

**Method (polite, /tmp only):** single catalogue GET with UA `home-finder-research/0.1`, `--max-time 20`, 429 = stop. Raw body in `/tmp/hf708_*`, never committed.
- `GET lkf.ee/et/statistika` → 200 (page links quarterly-review and accident PDFs only; no CSV/XLSX/JSON links, no county/municipality breakdown).

**What would overturn:** a keyless CSV/JSON/API URL with claim/accident stats at county or finer granularity + licence allowing redistribution. Then file a scoped build issue (sidecar + dims + layer) and reference this probe.
