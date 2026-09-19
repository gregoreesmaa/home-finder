# Probe: RIK KU financials reachability (#697) — verdict 2026-09-19

**Verdict:** dated negative. No keyless bulk korteriühistu (KÜ) financials reachable via the `avaandmed.rik.ee` catalogue; no filing scraping was attempted (out of scope).

**Method (polite, /tmp only):** single GETs with UA `home-finder-research/0.1`, `--max-time 20`, 429 = stop. Raw bodies in `/tmp/hf697_*`, never committed.
- `GET avaandmed.rik.ee/` → 200 with empty body (`Content-Length: 0`).
- `GET avaandmed.rik.ee/api/3/action/package_search?q=korteriühistu` → 404 (`The requested URL /api/3/action/package_search was not found` — no CKAN API).
- `GET avaandmed.rik.ee/andmed` → 302 → `adr.rik.ee/andmed/` → 404 (`Lehekülge ei leitud!`, Avalik dokumendiregister).
- `GET adr.rik.ee/` → 200 (public document register app, interactive search only, Cloudflare challenge script — no bulk CSV/JSON export).

**What would overturn:** a keyless catalogue URL with licensed machine-readable KÜ renovation-fund/debt data, licence allowing redistribution. Then file a scoped build issue (sidecar + dims + layer) and reference this probe. Filing-level scraping stays out of scope.
