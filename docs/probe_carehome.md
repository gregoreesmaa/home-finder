# Probe: care-home provider list (#709) — verdict 2026-09-19

**Verdict:** dated negative. No keyless machine-readable care-home provider list found; the MTR register is interactive HTML search only.

**Method (polite, /tmp only):** single catalogue GETs with UA `home-finder-research/0.1`, `--max-time 20`, 429 = stop. Raw bodies in `/tmp/hf709_*`, never committed.
- `GET terviseamet.ee/et/tegevusload-hoolekandeteenused` → 404 (guessed catalogue URL absent).
- `GET mtr.ttja.ee/juriidiline_isik` → 200 (HTML search app; login + form queries, no bulk CSV/JSON export).
- `GET avaandmed.eesti.ee/api/3/action/package_search?q=hoolekande` → 301→404 (portal API path moved).

**What would overturn:** a keyless CSV/JSON/WFS URL with licensed care-home providers + addresses, licence allowing redistribution. Then file a scoped build issue (sidecar + dims + layer) and reference this probe.
