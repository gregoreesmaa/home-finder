# Probe: keyless Elering network geography (#698) — verdict 2026-09-19

**Verdict:** dated negative. No keyless machine-readable Elering HV network geography found.

**Method (polite, /tmp only):** single GETs with UA `home-finder-research/0.1`, `--max-time 20`, 429 = stop. Raw bodies in `/tmp/hf698_*`, never committed.
- `GET kaardirakendus.elering.ee/` → DNS failure (curl exit 6, Could not resolve host) from probe network. Recorded honestly; a second-network confirmation will be run at review.
- `GET www.elering.ee/en/grid` → 301 → `elering.ee/en/grid` → 404 (page absent).
- `GET elering.ee/en/connection-capacity-application-e-gridmap` → 200 (interactive connection-application page; links to `mtv.elering.ee/login-view`, no bulk CSV/JSON/WMS export).
- `GET avaandmed.eesti.ee/api/3/action/package_search?q=elering` → 301 → `andmed.eesti.ee/...` → 404 (`Cannot GET /3/action/package_search` — portal API path moved).

**What would overturn:** a keyless CSV/JSON/WMS/WFS URL with Elering HV lines/substations geography, licence allowing redistribution. Then file a scoped build issue (sidecar + dims + layer) and reference this probe.
