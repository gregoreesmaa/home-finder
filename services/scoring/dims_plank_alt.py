"""PLANK/TPR alternative-source verdict (issue #519): NULL formally kept.

Buyer report: designated-use polygons show nothing; the route
header documents a dated NULL (PLANK WFS gone, TPR has no bulk).
Honest but useless.

ALTERNATIVE-SOURCE PROBE (2026-09-16, polite: 2 tiny metadata
requests with a labelled one-off UA, short timeouts, no scrape,
no bulk pull, no form submissions; HTTP 429 never seen):
* GET https://geoportaal.maaamet.ee/est/Teenused/Avalik-WMS-
  teenus-p65.html (Maa-amet public-WMS docs page) -> names the AKS
  OGC endpoint https://aks.geoportaal.ee/aks-ogc as the current
  public WMS service.
* GET aks.geoportaal.ee/aks-ogc?service=wms&version=1.3.0&
  request=GetCapabilities -> HTTP 200, 151 251 B. Enumerated
  <Name> layers: ads_* (address), knr_* (cadastre base), poi_*
  (points of interest) families ONLY -- zero planning layers: no
  planeering/detailplaneering/kehtiv/Katerina/TPR/sihtotstarbe
  layer name in the whole document.
So the Maa-amet public WMS is a DATED NEGATIVE as a
designated-use source: it serves addresses, cadastre and POIs,
never planning decrees. Together with the standing sibling
verdicts (PLANK WFS 301 -> E-ehitus SPA, no GetCapabilities
document; TPR Angular SPA shell with no bulk link -- both
verified 2026-09-13 in dims_p4_plank.py / dims_p4_tpr.py), no
open per-parcel designated-use bulk exists today.

Verdict: FORMALLY ACCEPT THE NULL + improved empty UX copy
(issue branch 2). This module ships the review-ready copy:
* empty_ux_copy: Estonian title/body/source strings explaining
  what is missing and why (PLANK endpoint gone into the E-ehitus
  platform; TPR a human register with no bulk; Maa-amet WMS
  verified 2026-09-16 to carry no planning family; the deed stays
  in the paid register). No invented polygons under any
  circumstance -- there is no polygon builder here at all.
* probe_aks_capabilities / has_planning_layer: the one-query 2027
  re-check (stubbed in tests; transport errors -> None, cached
  nothing -- errors are never data).

Next step left open (documented, not probed): the planeeringud.ee
E-ehitus SPA bundle per AGENTS.md 7.7, and the Katerina WMS /
municipal kehtivad-planeeringud mirror entries (no local mirror
copy in this repo to resolve their URLs from).

Style mirrors services/scoring/dims_p4_plank.py (#251: dated
negative as an explicit code path, Estonian EI OLE NULLs, no
sibling imports -- a future central hook may import this module
alongside it, and importing it here would turn that into a cycle,
batch B3 / PR #100 precedent). No shared files touched: 3 new
files only (wiring the copy into the planktpr overlay stays an
explicit follow-up).
"""

import re
import urllib.request
from typing import Dict, List, Optional, Tuple

#: Hunt date (2026-09-16) -- the day the AKS probe above ran.
VERDICT_DATE = "2026-09-16"

#: Re-check the AKS capabilities (planning family?) and the
#: E-ehitus SPA bundle no later than this date (6-month cadence,
#: #239 precedent).
RECHECK_AFTER = "2027-03-16"

#: Maa-amet public WMS docs page (probed 2026-09-16: names the AKS
#: endpoint below as the current public WMS service).
AKS_DOCS_URL = ("https://geoportaal.maaamet.ee/est/Teenused/"
                "Avalik-WMS-teenus-p65.html")

#: Maa-amet AKS OGC endpoint (probed 2026-09-16: HTTP 200,
#: 151 251 B GetCapabilities, no planning layer).
AKS_WMS_URL = "https://aks.geoportaal.ee/aks-ogc"

#: Identifying user agent for the polite re-check (one tiny
#: GetCapabilities query, no scrape).
AKS_UA = "home-finder plank-alt re-check (max 1 GetCapabilities, no scrape)"

#: Layer-name fragments that would mark a planning/designated-use
#: family (case-insensitive). Absent from the whole 2026-09-16
#: capabilities document.
PLANNING_MARKERS = frozenset({
    "planeer", "detailpl", "kehtiv", "katerina", "tpr",
    "sihtotstar", "plank",
})

#: Layer families the AKS capabilities DO serve (2026-09-16):
#: addresses, cadastre base, points of interest -- never decrees.
AKS_SERVED_FAMILIES = ("ads_* (aadress)", "knr_* (kataster)",
                       "poi_* (huvipunktid)")


def _capabilities_url() -> str:
    """AKS WMS GetCapabilities URL (version 1.3.0)."""
    return (AKS_WMS_URL + "?service=wms&version=1.3.0"
            "&request=GetCapabilities")


def probe_aks_capabilities(opener=None) -> Optional[List[str]]:
    """Polite AKS layer-name read. Returns sorted <Name>s or None.

    One tiny GET with AKS_UA and a 30 s timeout; the document is
    never stored (a layer list is not data). Transport errors,
    non-200 status and bodies without <Name> entries all read as
    None (unknown) -- errors are never an empty service. Tests stub
    the opener; production re-checks call this at most once.
    """
    open_url = opener or urllib.request.urlopen
    try:
        req = urllib.request.Request(_capabilities_url(),
                                     headers={"User-Agent": AKS_UA})
        with open_url(req, timeout=30) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                return None
            body = resp.read()
        if isinstance(body, bytes):
            body = body.decode("utf-8", "replace")
        names = sorted(set(re.findall(r"<Name>([^<]+)</Name>", body)))
        return names or None
    except Exception:
        return None


def has_planning_layer(names: list) -> bool:
    """True when a layer-name list carries a planning family.

    Pure, offline. Case-insensitive marker scan; unknown input is
    False (unknown, never a planning feed). Fails closed toward
    the NULL: only a marker hit flips the verdict.
    """
    if not isinstance(names, list):
        return False
    return any(isinstance(n, str) and any(m in n.lower()
                                          for m in PLANNING_MARKERS)
               for n in names)


def empty_ux_copy() -> Dict[str, str]:
    """Improved empty-UX copy (Estonian, dated) -- wiring-ready.

    Explains what is missing and why, instead of a blank map.
    Pinned by test: names PLANK + TPR + AKS, says EI OLE, carries
    the verdict date, and ships ZERO polygons.
    """
    return {
        "title": "Sihtotstarve (planeeringu teave puudub)",
        "body": ("EI OLE: krundi sihtotstarbe polügoone pole avatud "
                 "allikas saada (seisuga %s). PLANK WFS on läinud "
                 "E-ehituse platvormi (vana GeoServeri otsapunkt "
                 "enam WFS-i ei teeninda); Tallinna planeeringute "
                 "register (TPR) on inimloetav veebiregister ilma "
                 "avatud hulgiväljundita; Maa-ameti avalik WMS "
                 "(AKS) teenindab ainult aadressi-, katastri- ja "
                 "huvipunktikihte, mitte planeeringuid "
                 "(kontrollitud %s). Tühi kaart tähendab teadmatust, "
                 "mitte piirangute puudumist; kinnistusraamatu "
                 "teave jääb tasulisse registrisse."
                 % (VERDICT_DATE, VERDICT_DATE)),
        "source": ("PLANK/TPR/MAA-amet: avatud hulgi-päring EI OLE "
                   "(otsus %s, korduskontroll hiljemalt %s)"
                   % (VERDICT_DATE, RECHECK_AFTER)),
        "polygons": "",
    }


def null_verdict() -> str:
    """Formal NULL acceptance text (docs-ready)."""
    return "\n".join([
        "PLANK/TPR tühja kihi otsus (issue #519, %s):" % VERDICT_DATE,
        "Ühtki avatud krundipõhist sihtotstarbe hulgi-allikat ei "
        "leidu: PLANK WFS on läinud (301 E-ehituse SPA-sse), TPR-il "
        "pole hulgi-väljundit, Maa-ameti AKS WMS-is pole "
        "planeeringuperet (151 kB GetCapabilities, ainult "
        "ads/knr/poi). NULL võetakse ametlikult vastu: polügoone EI "
        "leiutata mitte mingil juhul.",
        "Tühi UX selgitab puudumist (empty_ux_copy, testidega); "
        "juhtmestik planktpr-kihti on eraldi järeltegevus.",
        "Järgmine samm: planeeringud.ee E-ehituse SPA pakett "
        "(AGENTS.md 7.7) + Katerina WMS / KOV kehtivate "
        "planeeringute peeglikirjed. Korduskontroll hiljemalt %s."
        % RECHECK_AFTER,
    ])


#: Dim-key registry surface (no scores -- this module keeps the
#: NULL; p47/p74/p274 shapes stay in dims_overturn_planktpr).
VERDICT_DIMS = ("plank_alt_verdict",)
