"""P4 NOAA VIIRS nighttime-lights radiance per-listing dim (issue #325 demo).

Params (this module only — the VIIRS SLICE of the param; sibling
slices are owned elsewhere and untouched):
* P4-035 December darkness: the NOAA VIIRS radiance Tallinn-tiles
  slice (source (2), batch 3, demo in #325). Disjoint from the
  Tallinna lamp-inventory/kaart per-street slice
  (dims_p4_veebi.dim_december_darkness_veebi), the Ilmateenistus
  December sun-hours baseline slice
  (dims_p4_ilm.dim_december_darkness), the Maa-amet LiDAR/DEM
  courtyard-shading slice (dims_p4_maa_lidar.dim_darkness_shading),
  the EHR orientation/floor/window-area slice
  (dims_p4_ehr.dim_darkness), and the OSM lit=yes honest-proxy
  slice (dims_p4_osm.dim_darkness) — their own demos, not this
  source. This source feeds only P4-035, so there is no follow-up
  coverage issue (single-param, like #262/#295/#318).

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #325): the EOG annual VIIRS (VNL) composites are NOT
anonymously pollable — product pages are open, tile downloads sit
behind an interactive login. Polite evidence, 3 tiny requests
total (labelled one-off user-agent, 25 s timeout, no retries,
paced >= 3 s; headers + visible-text/link scope read only, no
scraping, no auth, no account creation, no tile download — large
rasters stay on the server), raw bodies cached at
/tmp/hf-viirs-probe/ (TTL: one-off check, kept for the PR record,
never committed):
* https://eogdata.mines.edu/products/vnl/ ("VIIRS Nighttime
  Light") -> HTTP 200, 53 967 B — the product landing page is
  open and links the annual v10/v20/v21/v22 series plus one
  legacy v20 global tile URL; nav carries a register/accounts
  link (../register/).
* https://eogdata.mines.edu/nighttime_light/annual/v22/ (current
  annual series dir) -> HTTP 302 to eogauth.mines.edu Keycloak
  (openid-connect auth, client eogdata-new-apache): directory +
  tile downloads require an EOG account login.
* HEAD https://eogdata.mines.edu/nighttime_light/annual/v20/2020/
  VNL_v2_npp_2020_global_vcmslcfg_c202102150000.lit_mask.tif.gz
  (the legacy direct tile URL the landing page advertises) ->
  HTTP 302 to the same eogauth Keycloak login: even the old
  direct links are gated, headers only, zero raster bytes
  fetched.
So the dim returns None for EVERY input including missing
origin: a darkness gradient painted from a login-walled global
raster the poller may not hold credentials for — or from a
hand-read radiance value — would be fake precision (OTA PR #131
precedent). A daily cron must not carry interactive OIDC
credentials, and minting an account to scrape around the gate
would be exactly the impolite automation this repo refuses
(AGENTS.md sections 5 and 7.4 — the 302 is a stop signal, not a
retry dare). The reason says "hinnang" (estimate) and "EI OLE"
and points at the concrete buyer-side check (detsembri-kohapealne
15:30 jalutuskäik) plus the slices that DO score — never a faked
radiance number.

Style mirrors services/scoring/dims_p4_reklaam.py (#318, the
closest sibling: same single-param dated-negative NULL shape)
and dims_group20a.py (#212): the scorer is pure and
offline-tested — (origin, pois) -> (Optional[int 0..100],
Estonian reason). Network lives only in livability.fetch_pois;
this module adds no network calls, no Overpass fragment, and no
tag mapping: there is no honest snapshot tag to query for a
listing's night-sky radiance, so there is nothing for the live
path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Single-param module with no ingestion function: unlike the
  Maa-amet sibling legs (downloadable LiDAR/tehingud files to
  parse), there is no anonymously fetchable VIIRS tile to fetch,
  parse, or cache — the only artefact of the demo is this
  dated-negative verdict plus its doc note. Fetching nothing is
  the polite choice, stated not hidden (reklaam #318 precedent).
* Overlap boundary with dims_p4_veebi (READ before writing, not
  edited): the veebi module's dim_december_darkness_veebi already
  names "VIIRS-sisend" as one of its two missing legs under the
  `december_darkness` key. This module owns ONLY the radiance-tile
  leg under the distinct `viirs_radiance` key and names the veebi
  leg as a sibling slice — no double-scoring, no shared-file
  edits, no key collision (separate registries; distinct keys
  anyway).
* No Black Marble / NCEI mirror hedge: NASA LAADS annual
  composites need an Earthdata login token and NCEI DNB months
  are not the annual product parameters4.md names — swapping a
  login wall for another login wall, or a monthly product for
  the annual one, would not change the verdict, so no extra
  probes were spent (polite-automation precedent, AGENTS.md
  section 7.4).
* No scored "bright-city hinnang" off the open landing page: the
  page advertises products, it does not publish a per-Tallinn
  radiance value — arithmetic on missing inputs is fake
  precision, not a darkness hinnang.

Integration (deliberately NOT done here): this dim needs no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-035 (VIIRS slice): documented login-walled radiance-tile NULL
# (OTA PR #131 precedent). EOG annual VNL downloads 302 to Keycloak
# login for current and legacy URLs alike; the scorer reports the
# gap with the concrete buyer-side check instead of a faked number.
# ---------------------------------------------------------------------------

def dim_viirs_radiance(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """P4-035: NULL — VIIRS ööradiant (EOG tiles) on logini taga."""
    return None, ("VIIRS ööradiant (NOAA annual tiles Tallinna kohal) on "
                  "korteri-hinnang (EI OLE anonüümselt loetavat "
                  "radiance-voogu): EOG aastakomposiidid (v22 jooksva "
                  "seeriani, sh vana v20 otseviit) suunavad 302-ga "
                  "Keycloak-sisselogimisse — päevane cron ei kanna "
                  "interaktiivseid volitusi — külasta detsembris kell "
                  "15:30 kohapeal ja vaata lambikaardi-slice'i "
                  "dims_p4_veebi-st, päikesetundide-slice'i dims_p4_ilm-st, "
                  "varjutuse-slice'i dims_p4_maa_lidar-ist, akna-slice'i "
                  "dims_p4_ehr-ist ja lit-slice'i dims_p4_osm-ist, "
                  "ära feigi olematut radiantsinumbrit")


P4_VIIRS_DIMS = (
    ("viirs_radiance", "P4-035", dim_viirs_radiance),
)


def score_p4_viirs(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """The P4 VIIRS dim for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_VIIRS_DIMS). The
    value is None by design — login-walled source, never a
    faked per-listing radiance."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_VIIRS_DIMS}
