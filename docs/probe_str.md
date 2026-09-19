# Probe: InsideAirbnb Tallinn coverage (#696) — verdict 2026-09-19

**Verdict:** dated negative. No Tallinn dump on the InsideAirbnb city list; nearest covered city is Riga.

**Method (polite, /tmp only):** single GET with UA `home-finder-research/0.1`, `--max-time 20`, 429 = stop. Raw body in `/tmp/hf696_*`, never committed.
- `GET insideairbnb.com/get-the-data/` (city-list page only) → 200, 572 KB static HTML.
- `grep -ci tallinn` → 0; `grep -ci estonia` → 0.
- Nearest coverage: `Riga, Riga, Latvia` present (11 Riga + 7 latvia mentions).

**What would overturn:** a Tallinn entry appearing on the InsideAirbnb city list with downloadable `listings.csv.gz`. Then file a scoped build issue (sidecar + dims + layer) and reference this probe.
