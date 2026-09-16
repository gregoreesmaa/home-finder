"""EHR open-data API backfill (issue #537): the missing bulk for #234.

docs/overturn_ehr.md (#234, COMPLETED) ships the per-code bulk pipeline
(``fetch_ehr_bulk``, quarterly TTL, per-``ehr_code`` dims) WITHOUT
backfill — empty URL raises ValueError, scorers proven on fixtures only.
This module finds the backfill URL the pipeline was built for, or
produces the evidence that none is anonymously reachable.

Polite probe (2026-09-16, custom UA, single GETs, no 429 seen):
* ``https://swaggerui.ehr.ee/`` -> HTTP 200 text/html, 691 B — a React
  shell ("E-ehituse API services in Openapi format", AGENTS.md §7.7: a
  shell is a lead, never a verdict — dug in below).
* Bundle ``/static/js/main.0f7bd159.js`` -> HTTP 200
  application/javascript, 1400550 B, read statically. It embeds **43
  OpenAPI specs**, including ``avaandmed.yaml`` (EHR Avaandmete API
  v1.7.1, "REST API EHR avaandmete jaoks") and ``avaandmed2.yaml``.
* Avaandmed chunk (``/static/js/511.9788c904.chunk.js`` via
  asset-manifest.json, HTTP 200, 10898 B): servers
  ``https://devkluster.ehr.ee/api/av/v1`` (dev),
  ``http://testkluster.ehr.ee/api/av/v1`` (test),
  ``http://livekluster.ehr.ee/api/av/v1`` (production). Paths include
  GET ``/alus/reports`` (public-report metadata), GET
  ``/reports/{report_code}``, GET ``/info/reports/{eh_ehitised,
  eh_ehitis_osad, hoone_energia_margised, ehitis_aadres, katastriyksus,
  ...}`` (16 report keys), GET ``/params/...``, GET ``/version``.
  Report CREATION is POST with an email body — not anonymous, never
  attempted (AGENTS.md §5: no auth attempts, no personal data).
* Anonymous reachability (the acceptance question):
  ``https://livekluster.ehr.ee/api/av/v1/version`` -> HTTP 404
  "default backend - 404"; ``.../api/av/v1/alus/reports`` -> HTTP 404
  "default backend - 404". Plain-http ``.../version`` -> 301
  (cloudflare) back to the unrouted https path. The documented live
  base is UNROUTED — not key-gated, not per-owner: nothing anonymous
  answers there at all.
* The infoportal guide (``/ui/ehr/v1/infoportal/info``) answers
  HTTP 200 — the gated path stays email/portal-placed, same as #234.

VERDICT (dated negative, doubles as the re-probe record for #234): NO
anonymous per-``ehr_code`` query is reachable, so no viable backfill —
this issue closes as a documented no-map with probe evidence. The
harvester below ships behind the existing ``fetch_ehr_bulk`` contract
for the day the route is restored; the energy-label leg ships as
SCHEMA PROOF ONLY (report key ``hoone_energia_margised`` confirmed in
the spec's ``/info/reports`` namespace — bands second, not here).

What stays untouched: ``dims_p4_ehr.py``, ``dims_group02*.py``,
``dims_overturn_ehr.py``, ``docs/overturn_ehr.md`` wiring — this module
only fills ``EHR_BULK_URL``-shaped gaps; no band changes. No
E-ehitus procedural scraping; no area-gradient maps from building
attributes (G2 precedent #136: building attributes are not place
fields). CC BY-SA attribution.

Style mirrors services/scoring/dims_overturn_ehr.py (#234): polite
(single GET, file cache, TTL), transport errors RAISE and are never
cached, HTTP 429 propagates (stop signal). Helpers are local copies (no
sibling imports — same cycle precedent as PR #100).
"""

import io
import os
import time
import urllib.request
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Discovered interface (read statically from the swagger bundle 2026-09-16).
# ---------------------------------------------------------------------------

#: The swagger shell (React app listing the specs — a lead, not data).
SWAGGER_UI_URL = "https://swaggerui.ehr.ee/"

#: Avaandmete API version embedded in the bundle (avaandmed.yaml).
AV_API_VERSION = "1.7.1"

#: Documented servers (spec v1.7.1). Dated-negative 2026-09-16: the live
#: base answers 404 "default backend" on /version and /alus/reports —
#: kept as provenance constants, NOT working fetch targets.
AV_SERVERS = {
    "dev": "https://devkluster.ehr.ee/api/av/v1",
    "test": "http://testkluster.ehr.ee/api/av/v1",
    "live": "http://livekluster.ehr.ee/api/av/v1",
}

#: /info/reports keys from the embedded spec (data reports; the energy
#: labels live here too — see ENERGY_REPORT_KEY).
AV_REPORT_KEYS = (
    "andmete_esitaja",
    "eh_ehitis_osad",
    "eh_ehitised",
    "eh_tehna",
    "ehitis_aadres",
    "ehitis_kaos",
    "ehitis_katastriyksus",
    "ehitise_ruumikuju",
    "hoone_energia_margised",
    "katastriyksus",
    "kl_element",
    "kl_kasutusotstarbed",
    "kl_tehna",
    "sa_ehitis",
    "sa_ehitis_osa",
    "sp_punkt",
)

#: Energy-label leg, schema proof only: the bulk report key exists in
#: the spec — per-label bands wait on a reachable harvest (second leg,
#: not this module).
ENERGY_REPORT_KEY = "hoone_energia_margised"

#: Quarterly bulk per parameters3.md §5.2 (same contract as
#: dims_overturn_ehr.fetch_ehr_bulk: on-demand cache TTL 30 days).
AV_TTL_DAYS = 30

USER_AGENT = ("home-finder EHR avaandmed ingest (polite quarterly bulk, "
              "single GET, file cache; contact via GitHub home-finder)")


def _cache_path(cache_dir: str, name: str) -> str:
    """Cache file for one named avaandmed report (flat dir, no subdirs)."""
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in name)
    return os.path.join(cache_dir, "ehr-av-%s.json" % safe)


def cache_is_fresh(path: str, ttl_days: int = AV_TTL_DAYS,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_days."""
    try:
        age_days = ((now if now is not None else time.time())
                    - os.path.getmtime(path)) / 86400.0
    except OSError:
        return False
    return age_days < ttl_days


def av_report_url(base_url: str, report_code: str) -> str:
    """Build the anonymous GET URL for one /info/reports key.

    Raises ValueError on an empty base (no anonymous bulk URL is
    verified — same contract as fetch_ehr_bulk) or an unknown report
    key (guessing keys would fake interface knowledge).
    """
    if not base_url:
        raise ValueError(
            "EHR avaandmete baas-URL puudub: anonüümset liidest pole "
            "kinnitatud (dated negative 2026-09-16) — anna ette "
            "värava baas-URL või kasuta vahemälu")
    if report_code not in AV_REPORT_KEYS:
        raise ValueError(
            "Tundmatu EHR avaandmete raport (%s) — EI OLE liidest: "
            "võtmed on pärit spetsifikatsioonist v%s"
            % (report_code, AV_API_VERSION))
    return base_url.rstrip("/") + "/info/reports/" + report_code


def fetch_av_report(report_code: str, base_url: Optional[str],
                    cache_dir: str = "/tmp/hf-cache",
                    ttl_days: int = AV_TTL_DAYS) -> str:
    """Fetch one avaandmed report politely (single GET, cached, TTL-stated).

    Returns cached text when fresh; otherwise one GET with a polite
    User-Agent and a 30 s timeout. ``base_url`` is the maintainer-placed
    route (no anonymous bulk URL is verified — dated negative, see
    docstring), so an empty base raises ValueError instead of guessing
    an endpoint. Transport errors RAISE (never cached as data, AGENTS.md
    §7.2); HTTP errors raise too — an error body is never written to the
    cache. HTTP 429 propagates (stop signal, AGENTS.md §7.4). Tests never
    call this with a remote URL.
    """
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir, report_code)
    if cache_is_fresh(path, ttl_days):
        with io.open(path, encoding="utf-8") as f:
            return f.read()
    url = av_report_url(base_url or "", report_code)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        body = resp.read()
    text = body.decode("utf-8")
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return text


#: Backfill capability owned by this module (per-code join stays with
#: dims_overturn_ehr; the energy leg is schema-proof only).
EHR_BACKFILL_REPORTS: Dict[str, str] = {
    "buildings": "eh_ehitised",
    "building_parts": "eh_ehitis_osad",
    "energy_labels": ENERGY_REPORT_KEY,
}
