# Probe: Ookla open speedtest tiles for Tallinn (#693) — verdict 2026-09-19

**Verdict:** dated positive. Keyless quarterly fixed-broadband speed tiles exist in the `ookla-open-data` S3 bucket (years 2019–2026, latest 2026-Q2), CC BY-NC-SA 4.0.

**Method (polite, /tmp only):** single GETs with UA `home-finder-research/0.1`, `--max-time 20`, 429 = stop. Raw bodies in `/tmp/hf693_*`, never committed.
- `GET registry.opendata.aws/speedtest-global-performance/` → 200, 9244 B (confirms bucket `s3://ookla-open-data/`, license CC BY-NC-SA 4.0).
- `GET ookla-open-data.s3.amazonaws.com/?list-type=2&prefix=shapefiles/performance/type%3Dfixed/` → 200, keyless XML listing, year prefixes 2019–2026.
- `GET ...&prefix=.../year%3D2026/` → 200, quarters 1–2.
- `GET ...&prefix=.../quarter%3D2/` → 200, `2026-04-01_performance_fixed_tiles.zip` (342 651 784 B).
- `HEAD .../2026-04-01_performance_fixed_tiles.zip` → 200, Last-Modified 2026-08-19.
- Zip body NOT downloaded (343 MB — out of polite probe budget by design; the URL pattern + HEAD is the evidence).

**What follows:** scoped build issue #725 (quarterly cached pull + Tallinn-bbox tile extraction + dims + layer). License is non-commercial — the build must check repo policy before ingesting.
