# P4 VIIRS verdict note — nighttime-lights radiance (P4-035 slice)

> Dated-negative verdict for issue #325 (demo, single-param).
> Checked 2026-09-13. The one param is a documented login-walled
> NULL dim (OTA PR #131 precedent); the scorer lives in
> `services/scoring/dims_p4_viirs.py`, pinned by
> `services/scoring/tests/test_dims_p4_viirs.py`.

## Verdict

**No anonymously pollable tile — the single dim stays NULL with
an Estonian reason.** The EOG VIIRS Nighttime Light product pages
are open, but the annual (VNL) composite downloads — current v22
series and the legacy v20 direct tile URL alike — 302-redirect to
the eogauth Keycloak login. A polite daily poller must not carry
interactive OIDC credentials and must not mint an account to
scrape around the gate, so there is no ingestion to cache, no TTL
to state beyond this one-off check, and no honest per-listing
radiance to join. A darkness gradient painted from a raster the
pipeline may not fetch would be fake precision.

## Openness evidence (one polite round, 2026-09-13, headers/small scope only)

3 tiny requests total (labelled one-off user-agent
`home-finder-openness-probe issue-325 one-off`, 25 s timeout, no
retries, paced ≥ 3 s, headers + visible-text/link scope read
only, no account creation, zero raster bytes fetched — large
annual GeoTIFFs stay on the server). Raw bodies:
`/tmp/hf-viirs-probe/` (one-off PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://eogdata.mines.edu/products/vnl/` ("VIIRS Nighttime Light") → 200, 53967 B | Open landing page; links annual v10/v20/v21/v22 series + one legacy v20 global tile URL; nav has register/accounts link | Product info is public, downloads are not |
| `https://eogdata.mines.edu/nighttime_light/annual/v22/` → 302 to `eogauth.mines.edu` Keycloak (`openid-connect/auth`, client `eogdata-new-apache`), 484 B | Current annual series dir requires EOG account login | No anonymous tile listing or fetch |
| `HEAD .../annual/v20/2020/VNL_v2_npp_2020_global_vcmslcfg_c202102150000.lit_mask.tif.gz` → 302 to the same Keycloak login, 0 B | Even the advertised legacy direct tile URL is gated; headers only | Whole annual archive behind the same wall |

Judgment call: probing stopped at the gate on purpose — no
account creation, no credential-carrying fetcher, no Black
Marble/LAADS hedge (another login wall, not the annual product
parameters4.md names), no tile download. The 302 is a stop
signal, not a retry dare (AGENTS.md §§5, 7.4).

## Sibling slices (owned elsewhere, untouched)

- **P4-035 lamp-inventory/kaart per-street slice:**
  `dims_p4_veebi.dim_december_darkness_veebi` (READ before
  writing; that module already names the VIIRS input gap under
  its own `december_darkness` key — this module owns ONLY the
  radiance-tile leg under the distinct `viirs_radiance` key).
- **P4-035 December sun-hours baseline slice:**
  `dims_p4_ilm.dim_december_darkness`.
- **P4-035 LiDAR/DEM courtyard-shading slice:**
  `dims_p4_maa_lidar.dim_darkness_shading`.
- **P4-035 EHR orientation/floor/window-area slice:**
  `dims_p4_ehr.dim_darkness`.
- **P4-035 OSM lit=yes honest-proxy slice:**
  `dims_p4_osm.dim_darkness`.

This source feeds only P4-035, so there is no follow-up coverage
issue (single-param, like #262/#295/#318).

## What stays open (overturn path, not wired here)

EOG (or a mirror) serves the annual VNL tiles — ideally a
Tallinn bbox — over anonymous HTTPS with stable URLs → re-open
#325, build the polite cached ingestion (annual TTL per
parameters4.md P4-035, Range/bbox reads only, never full-globe
rasters into the repo), and graduate `viirs_radiance` to a
per-listing join. Until then the buyer-side check is:
detsembri-kohapealne 15:30 jalutuskäik plus the slices that
score (veebi/ilm/lidar/ehr/osm, named in the reason).
