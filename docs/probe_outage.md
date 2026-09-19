# Probe: Elektrilevi outage map (#689) — verdict 2026-09-19

**Verdict:** dated positive. The rikkekaart app exposes a keyless live outage JSON endpoint.

**Method (polite, /tmp only):** single GETs with UA `home-finder-research/0.1`, `--max-time 20`, 429 = stop. Raw bodies in `/tmp/hf689_*`, never committed.
- `GET rikkekaart.elektrilevi.ee/` → 200, 22 KB shell (RequireJS `scripts/main.js`, refs `geoserver-api/`).
- `GET .../scripts/main.js` → 200, 603 KB config/bundle: endpoints `geoserver-api/GetApplicationData`, `GetObjectsByTiles?zoom=&tiles=`, `GetNetworkObjects(Table)`, `content/StaticObjects`.
- `GET .../geoserver-api/GetApplicationData` → 200, 129 629 B `application/json`, no login. Double-encoded JSON: top-level `scopes.p.{areas, dynareas, outages}`; 99 areas including `Harju maakond` (`fc:1 fcc:1 uc:96 ucc:5766`) and `Lääne-Harju vald` — live counters at probe time.

**What follows:** scoped build issue #729 (polite cached pull + Tallinn/Harju extraction + dims + layer). Field semantics (`fc` vs `uc` etc.) to be pinned from `main.js` during the build.
