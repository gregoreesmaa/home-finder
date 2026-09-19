# Probe: VIIRS night-lights tiles for Tallinn (#699) — verdict 2026-09-19

**Verdict:** dated positive. Keyless VIIRS night-lights tiles exist via NASA GIBS WMTS (`VIIRS_Black_Marble`); EOG direct downloads are login-walled (keyful) and not needed.

**Method (polite, /tmp only):** single GETs with UA `home-finder-research/0.1`, `--max-time 20`, 429 = stop. Raw bodies in `/tmp/hf699_*`, never committed.
- `GET gibs.earthdata.nasa.gov/wmts/epsg3857/best/1.0.0/WMTSCapabilities.xml` → 200 (5.8 MB; first attempt timed out once, single retry 200 — transient).
- Caps list keyless layer `VIIRS_Black_Marble` (annual composite, global incl. Tallinn) with tile template `.../VIIRS_Black_Marble/default/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.png`.
- `GET .../VIIRS_Black_Marble/default/default/GoogleMapsCompatible_Level8/8/75/145.png` (Tallinn z8) → 200, 55 KB PNG 256×256, no login.
- `GET eogdata.mines.edu/products/vnl/` → 200 (catalogue page); download dir `.../wwwdata/downloads/dnb_profiles_deliver_licorr/` → 302 to `eogauth.mines.edu/.../openid-connect/auth` (OAuth login) → keyful.
- `GET eogdata.mines.edu` annual GeoTIFF links exist but sit behind the same login wall.

**What follows:** scoped build issue #719 (GIBS tile sampling sidecar + dims + layer). Tiles are visualization PNGs (not numeric radiance), so the build must derive scores from tile brightness.
