"""P4 Sentinel-2 dim (issue #305 demo only): Copernicus Sentinel-2 verdict.

Demo (#305): the Copernicus Sentinel-2 source via P4-030 Satellite
change delta (NDVI/construction year-delta, Tallinn tiles) end-to-end
in Tallinn - the Sentinel-2 NDVI year-delta leg (per-listing coarse
change flag from joined two-vintage NDVI rows). Single-param demo:
P4-030 is the only param naming this source, so there is no coverage
follow-up issue; P4-030's sibling legs are already scored where they
live (see SIBLING OVERLAP).

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #305: Sentinel-2 pixel bulk on the native Copernicus Data Space
needs a registered account + S3 credentials, so the dim stays NULL).
Polite evidence, 5 requests attempted (4 served) with a labelled
one-off user-agent `home-finder s2 openness-check #305 (one-off,
single GETs, no retry; contact via GitHub home-finder)`,
`--max-time 25`, metadata + visible-text scope reads only (no pixel
download, no auth, no account creation), raw bodies cached at
/tmp/hf-s2-probe/ (one-off PR record, never committed):
* GET https://dataspace.copernicus.eu/ -> HTTP 200 (114006 bytes,
  visible text names APIs/STAC/download but the data path below is
  what matters; portal reachability, not data).
* GET .../stac/v1/collections/sentinel-2-l2a -> HTTP 200 (25596
  bytes): the Sentinel-2 L2A collection metadata IS openly readable
  (orthorectified surface reflectance, scene classification + AOT/WV
  maps), and it declares its own access schemes: `auth:schemes`
  openIdConnect at identity.dataspace.copernicus.eu plus `s3`, with
  `storage:schemes` cdse-s3 on https://eodata.dataspace.copernicus.eu
  ("including how to get credentials").
* GET .../collections/sentinel-2-l2a/items?bbox=24.55,59.35,24.95,59.65
  &limit=1 -> HTTP 200 (72050 bytes): catalogue search IS open - it
  names today's Tallinn scene S2B_MSIL2A_20260913T095029_N0512_R079_
  T35VLG_20260913T133543 (2026-09-13T09:50:29Z) with 47 assets, every
  pixel asset an s3://eodata/Sentinel-2/MSI/L2A/... href. Metadata
  names the scene; it does not measure it.
* GET https://documentation.dataspace.copernicus.eu/APIs/S3.html ->
  HTTP 200 (197233 bytes): "To generate the necessary credentials,
  you must have a registered account on dataspace.copernicus.eu ...
  log in with the Copernicus Data Space Ecosystem account for which
  the keys are to be generated" (temporary S3 credentials via the
  S3 keys manager API). Keyed bulk by construction.
* GET https://catalogue.dataspace.copernicus.eu/odata/v1/Products?
  $top=1&$filter=contains(Name,'S2') -> timeout after 25 s, 0 bytes
  (transport note, not data; the verdict does not rely on OData -
  STAC + the S3 docs above carry it).

So the dim returns None for EVERY input including missing origin:
a per-listing NDVI year-delta needs two keyed pixel pulls plus
raster math (red/NIR bands B04/B08, cloud masking, vintage
differencing) behind that registered account, and painting a coarse
"disappearing grove / new neighbour" flag from a one-off hand-read
of open STAC metadata - which carries no reflectance values at all -
would be fake precision (OTA PR #131 precedent). Creating an
account or minting credentials to pull pixels is exactly what this
demo refuses (per #305: no account creation, no credential use).
The reason says "hinnang" (estimate) and "EI OLE" and points at the
concrete buyer-side checks (Maa-ameti aerofoto aastakäikude võrdlus,
raieload, kohapealne kvartali vaatlus, scored EELIS-raie cousin
below) - never a faked change flag.

SIBLING OVERLAP (read first, not edited): the EELIS P4-030 leg is
already scored where it lives - this module owns ONLY the
Sentinel-2 NDVI leg and never re-scores it:
* EELIS felling slice - dims_p4_eelis dim_rohemuutus_eelis
  (key rohemuutus_eelis, kaadamisala join within 500 m).
The remaining P4-030 legs (Maa-amet aerial vintages, Keskkonnaameti
raieload, EHR ehitusload, jäätmejaama/prügila teated) are sibling /
future legs, likewise untouched and not faked here.

Style mirrors services/scoring/dims_p4_insurers.py (#286): the
scorer is pure and offline-tested - (origin, pois) ->
(Optional[int 0..100], Estonian reason). Network lives only in
livability.fetch_pois; this module adds no network calls, no
Overpass fragment, and no tag mapping: there is no honest snapshot
tag to query for a keyed Sentinel-2 pixel vintage, so there is
nothing for the live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152). In
practice this verdict module needs no helpers at all - the single
dim reports its missing Sentinel-2 leg directly.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Single-param demo, no coverage issue: P4-030 is the only param
  naming this source (parameters4.md P4-030 source (1) "Copernicus
  Sentinel-2 NDVI year-delta Tallinn tiles"), so one module, one
  test file, one verdict note - no second file importing a pipeline
  that does not exist. The coarse-flag shape the param wants is
  already carried for the register leg by the scored EELIS cousin
  (kaadamisala hit flags within 500 m); there is no unflagged
  residual for this leg to own without pixels.
* STAC metadata is not a measurement: the openly readable
  collection + item records were deliberately NOT turned into a
  proxy score (scene-exists-over-Tallinn would score every listing
  identically while claiming a greenness delta). The reason says
  this plainly instead of hiding the open-metadata/keyed-pixels
  split.
* The check stopped at metadata + docs level on purpose: one
  Tallinn scene record plus the S3 credential wording carries the
  verdict for the source family - pixel pulls all need the same
  registered-account keys by construction, and pulling them would
  add gigabytes, not information. The OData timeout was left as a
  transport note (no retry, AGENTS.md section 7.4).
* (origin, pois) signature instead of a join signature: with the
  dated-negative verdict there is no ingestion and hence no join
  input - the dim reports the pixel-bulk gap for any listing, the
  same shape as the insurers dated-negative NULL.

Integration (deliberately NOT done here): this dim needs no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change - existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-030: documented no-map Sentinel-2-leg NULL (OTA PR #131
# precedent). Copernicus pixel bulk needs a registered account + S3
# credentials (2026-09-13 dated-negative verdict above); the scorer
# reports the gap with concrete buyer-side checks instead of a faked
# change flag.
# ---------------------------------------------------------------------------

def dim_rohemuutus_s2(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """P4-030: NULL - Sentinel-2 NDVI bulk is keyed (no map)."""
    return None, ("Satelliidi rohemuutuse hinnang eeldaks Sentinel-2 pikslite "
                  "hulgi-allalaadimist (EI OLE võtmeta teed: Copernicus Data "
                  "Space S3-pilv nõuab registreeritud kontot ja S3-võtmeid, "
                  "kontrollitud 2026-09-13 - STAC-kataloog nimetab vaid "
                  "tänase Tallinna stseeni, metaandmed ei ole NDVI-mõõt) - "
                  "võrdle Maa-ameti aerofoto aastakäike ja raielube, vaata "
                  "kvartal kohapeal üle; numbriline P4-030-leg on juba "
                  "liidestatud (EELIS-raie dims_p4_eelis-is "
                  "dim_rohemuutus_eelis) - ära feigi")


P4_S2_DIMS = (
    ("rohemuutus_s2", "P4-030", dim_rohemuutus_s2),
)


def score_p4_s2(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """The P4 Sentinel-2 dim for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_S2_DIMS). The value
    is None by design - keyed pixel bulk with no pollable feed,
    never a faked change flag."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_S2_DIMS}
