"""Flood Harju-coverage verdict (issue #518): KAUR sidecar vs Harju water.

Buyer report: flood-risk layer reads empty in Tallinn. Verified
2026-09-16: the KAUR sidecar holds 2 REAL zones (Mullutu-Suurlaht,
Suur-Emajõgi -- both outside Harjumaa, per the issue evidence), so
Tallinn reads honest-empty, correctly but uselessly.

HARJU PROBE (2026-09-16, polite: 2 tiny WFS hits requests with a
labelled one-off UA, paced, ~1 kB bodies, no scrape, no bulk pull;
HTTP 429 never seen):
* GetFeature resultType=hits on eelis:kr_yleujutusohuga_ala over
  the Harju-county BBOX (lat 58.9-59.7, lon 23.3-25.6 -- covers the
  Pirita river catchment AND the Tallinn coast) ->
  numberMatched="0", timeStamp 2026-09-16T02:40Z.
So the open EELIS flood register carries ZERO polygons for every
Harju water body: Pirita river, Tallinn coast, and all. Tallinn
stays honest-empty -- there is nothing to install, and nothing is
invented.

Family note (per the #518 review comment): the open layer's rows
carry the single constant tyyp "Suurte üleujutusohuga siseveekogu"
(inland water-body objects -- dims_overturn_flood.py). Whether the
andmed-eesti mirror's coastal-flood family covers the Tallinn
coast could not be checked from this repo (no local mirror copy);
the per-stretch family table below records the open register as
covering NEITHER family in Harju, and the coastal mirror as OPEN
(next probe, not probed here).

Verdict: DOCUMENTED COVERAGE GAP (no Harju harvest exists). This
module is the gap record plus the legend-ready copy:
* coverage_legend: pure offline builder -- echoes ONLY zone names
  present in the sidecar input (never invented), then states the
  Harju/Tallinn gap with the verdict date. Unknown/unlabelled rows
  are skipped, never presented as coverage.
* probe_harju_hits: one polite hits-count read for the 2027
  re-check (stubbed in tests; transport errors -> None, cached
  nothing -- errors are never data).

Style mirrors services/scoring/dims_overturn_flood.py (#239: dated
verdict, Estonian EI OLE NULLs, no sibling imports -- a future
central hook may import this module alongside it, and importing it
here would turn that into a cycle, batch B3 / PR #100 precedent).
No shared files touched: 3 new files only (wiring the legend copy
into layers_flood.ts stays an explicit follow-up).
"""

import re
import urllib.request
from typing import Dict, List, Optional, Tuple

#: Hunt date (2026-09-16) -- the day the Harju probe above ran.
VERDICT_DATE = "2026-09-16"

#: Re-check the Harju BBOX hits (riverine family? coastal mirror?)
#: no later than this date (6-month cadence, #239 precedent).
RECHECK_AFTER = "2027-03-16"

#: Verified open WFS base (2026-09-16: Harju hits HTTP 200).
WFS_BASE = "https://gsavalik.envir.ee/geoserver/eelis/ows"

#: The single open flood polygon layer (object register; Harju
#: numberMatched=0 on VERDICT_DATE).
FLOOD_LAYER = "eelis:kr_yleujutusohuga_ala"

#: Harju-county pull window (lat_min, lon_min, lat_max, lon_max,
#: EPSG:4326): covers the Pirita river catchment and the Tallinn
#: coast in one polite hits query.
HARJU_BBOX = (58.9, 23.3, 59.7, 25.6)

#: Identifying user agent for the polite re-check (one tiny hits
#: query, no scrape).
HARJU_UA = "home-finder flood-harju re-check (max 1 hits query, no scrape)"

#: Real sidecar zones known 2026-09-16 (issue evidence; both outside
#: Harjumaa). Echoed by the legend builder ONLY when present in its
#: input -- never asserted from this constant alone.
KNOWN_ZONES = (
    "Mullutu-Suurlaht kogu kalda ulatuses",
    "Suur-Emajõgi koos vanajõgedega kogu ulatuses",
)


def _hits_url() -> str:
    """WFS hits-count URL for the flood layer over HARJU_BBOX."""
    lat0, lon0, lat1, lon1 = HARJU_BBOX
    return (
        "%s?service=WFS&version=2.0.0&request=GetFeature"
        "&typeNames=%s&bbox=%s,%s,%s,%s,"
        "urn:ogc:def:crs:EPSG::4326&resultType=hits&count=1"
        % (WFS_BASE, FLOOD_LAYER, lat0, lon0, lat1, lon1)
    )


def probe_harju_hits(opener=None) -> Optional[int]:
    """Polite Harju hits-count read. Returns numberMatched or None.

    One tiny GET with HARJU_UA and a 30 s timeout; the body is never
    stored (a count is not data). Transport errors, non-200 status
    and unparseable bodies all read as None (unknown) -- errors are
    never a zero. Tests stub the opener; production re-checks call
    this at most once per run.
    """
    open_url = opener or urllib.request.urlopen
    try:
        req = urllib.request.Request(_hits_url(),
                                     headers={"User-Agent": HARJU_UA})
        with open_url(req, timeout=30) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                return None
            body = resp.read()
        if isinstance(body, bytes):
            body = body.decode("utf-8", "replace")
        match = re.search(r'numberMatched="(\d+)"', body)
        return int(match.group(1)) if match else None
    except Exception:
        return None


def _zone_name(zone: dict) -> Optional[str]:
    """Real zone name from a sidecar row, or None when unusable."""
    if not isinstance(zone, dict):
        return None
    for key in ("nimi", "name", "veekogu"):
        value = zone.get(key)
        if isinstance(value, str) and value.strip():
            text = value.strip()
            lowered = text.lower()
            if "fiktiiv" in lowered or "fixture" in lowered:
                return None
            return text
    return None


def coverage_legend(zones: list) -> str:
    """Legend-ready coverage note (Estonian, dated).

    Pure, offline. Names ONLY zones present in the input (echoed,
    never invented); unlabelled/fictitious rows are skipped, never
    presented as coverage. Always states the Harju/Tallinn gap with
    the verdict date -- Tallinn stays honest-empty until a real
    Harju polygon lands in the sidecar.
    """
    names: List[str] = []
    if isinstance(zones, list):
        for zone in zones:
            name = _zone_name(zone)
            if name is not None and name not in names:
                names.append(name)
    if names:
        covered = "kattes: %s" % "; ".join(names)
    else:
        covered = "kattes: EI OLE -- registris pole ühtki tsooni"
    return ("%s (seisuga %s). Harjumaal (sh Pirita jõgi ja Tallinna "
            "rannik) EI OLE avatud registris ühtki polügooni "
            "(kontrollitud %s): Tallinn on ausalt tühi, mitte kuiv. "
            "Korduskontroll hiljemalt %s."
            % (covered, VERDICT_DATE, VERDICT_DATE, RECHECK_AFTER))


def harju_verdict() -> str:
    """Full dated verdict text (docs-ready)."""
    return "\n".join([
        "Üleujutuse Harju-katvuse otsus (issue #518, %s):" % VERDICT_DATE,
        "Avatud EELIS register (eelis:kr_yleujutusohuga_ala) annab "
        "Harju maakonna aknas (58.9-59.7, 23.3-25.6: Pirita jõgi + "
        "Tallinna rannik) numberMatched=0 -- Pirita jõe ega Tallinna "
        "ranniku jaoks pole selles allikaperes katvust.",
        "Külgfaili 2 tõelist tsooni (%s) on mõlemad väljaspool "
        "Harjumaad: Tallinn jääb ausalt tühjaks, tsoone EI "
        "leiutata." % "; ".join(KNOWN_ZONES),
        "Ranniku-üleujutuse peegelpere (andmed-eesti) on LAHTINE: "
        "selle repo paikset koopiat pole, järgmine uuring.",
        "Korduskontroll hiljemalt %s." % RECHECK_AFTER,
    ])


#: Dim-key registry surface (no scores -- this module records the
#: gap; the p112 join shape stays in dims_overturn_flood).
VERDICT_DIMS = ("flood_harju_verdict",)
