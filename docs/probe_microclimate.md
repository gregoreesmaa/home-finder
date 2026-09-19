# Probe: modelled microclimate heat-island grid for Tallinn (#661) — verdict 2026-09-19

**Verdict:** dated negative. No open, keyless, licensed modelled microclimate grid covering Tallinn was found; the honest coarse signal stays the 3-station normals cells (Harku/Pakri/Kuusiku, never interpolated).

**Method (polite, /tmp only):** single GETs with UA `home-finder-research/0.1`, `--max-time 20`, 429 = stop, plus documentation inspection.
- VITO's published UrbClim city list: Almada, Antwerp, Barcelona, Berlin, Bern, Bilbao, Brussels, Delhi, Ghent, Hasselt, London, Paris, Prague, Rome, Skopje, Tilburg, Vienna — no Tallinn.
- The 100-European-cities UrbClim archive (100 m, via Copernicus C3S) is distributed through the Climate Data Store, which requires an account → keyful, not usable.
- `www.urbclim.eu/` and `uhi.yale.edu/` did not resolve on this network (curl exit 6, single-network DNS evidence — needs review-time second-network confirmation).

**No-interpolation guard:** `services/scoring/dims_p4_kliima_stations.py` (resolved real normals module — no `dims_kliima_normals` exists) assigns each listing to exactly one nearest station cell and states `interpolatsiooni pole` in scored reasons; `tests/test_probe_microclimate.py` pins this.

**What would overturn:** a keyless modelled grid (UrbClim-style, LCZ, or Copernicus-derived) with an open licence covering Tallinn. Then file a scoped build issue (sidecar + dims + layer) and reference this probe.
