"""EELIS real-data verdict (issue #517): three polygon layers, live or honest-empty.

Buyer report: all three EELIS layers (raiealad, niiduelupaigad,
kaitsealad) read empty. Verified 2026-09-16: the builder snapshot
/tmp/hf-488-snap/eelis/eelis-areas.json holds exactly 3 zones, ALL
explicitly fictitious ("Pirita joeoru maastikukaitseala (fiktiivne)",
"Fixture niit (fiktiivne)", "Fixture raie (fiktiivne)"). Nothing is
installed in the default snapshot, so users see honest-empty -- but
there was no real-data path check and no guard against installing
the fiction.

RE-VERDICT (2026-09-16, polite: 7 tiny WFS metadata/hits requests
with a labelled one-off UA, paced >= 5 s, bodies <= ~1 kB, no
scrape, no bulk pull; HTTP 429 never seen):
* GetFeature resultType=hits over the Tallinn BBOX
  (lat 59.35-59.65, lon 24.55-24.95) -> HTTP 200 on all three
  layers (liveness re-confirmed today).
* Per-layer Tallinn counts stand per the 2026-09-13 verified pull
  plan in dims_p4_eelis.py (PULL_PLAN, same BBOX): kr_kaitseala 33,
  niidud 44, kaadamisalad 1. The real harvest path (fetch_eelis_
  snapshot -> batch_eelis_poly.py -> eelis-areas.json sidecar) is
  therefore OPEN and serving real polygons; the empty map is a
  missing-harvest state, not a missing-source state.
* The flood table (kr_yleujutusohuga_ala) stays OUT here -- owned
  by the #487 floodzone overlay (docs/overturn_flood.md).

Verdict: REAL HARVEST, not honest-empty. This module is the
install-time guard plus the dated coverage record:
* scrub_fictitious / installable_sidecar: pure offline gate. A
  candidate sidecar holding ANY fictitious zone is refused (never
  installed); an empty candidate stays honest-empty; only a
  non-empty fiction-free candidate is installable. Transport
  errors are never data -- there is no network in this module at
  all (the pull lives in dims_p4_eelis.fetch_eelis_snapshot).
* coverage_note / verdict_summary: dated, sourced legend-ready
  strings (layer counts + verdict date), so the map never prints
  an undated claim.

Style mirrors services/scoring/dims_overturn_flood.py (#239: dated
verdict, Estonian EI OLE NULLs, no sibling imports -- a future
central hook may import this module alongside dims_p4_eelis, and
importing it here would turn that into a cycle, batch B3 / PR #100
precedent). No shared files touched: 3 new files only.

HONESTY (AGENTS.md 7.2): every verdict string says its date and
source; every refusal says EI OLE and names the cause; distances
are untouched (this module scores nothing -- it gates installs).
"""

from typing import Dict, List, Optional, Tuple

#: Hunt date (2026-09-16) -- the day the re-verdict probes above ran.
VERDICT_DATE = "2026-09-16"

#: Re-check the three WFS layer counts no later than this date
#: (6-month cadence, #239 precedent).
RECHECK_AFTER = "2027-03-16"

#: Public EELIS WFS (liveness re-confirmed 2026-09-16: HTTP 200
#: hits on all three layers; see docstring).
EELIS_WFS_URL = "https://gsavalik.envir.ee/geoserver/eelis/ows"

#: Tallinn BBOX (lat_min, lon_min, lat_max, lon_max) shared with
#: dims_p4_eelis.TALLINN_BBOX -- the window the counts hold in.
TALLINN_BBOX = (59.35, 24.55, 59.65, 24.95)

#: (map layer, WFS layer, Tallinn count, count date). Counts per the
#: 2026-09-13 verified pull plan (dims_p4_eelis.PULL_PLAN, same
#: BBOX); liveness re-confirmed 2026-09-16.
VERDICT_LAYERS = (
    ("eeliskaitse", "eelis:kr_kaitseala", 33, "2026-09-13"),
    ("eelisniit", "eelis:niidud", 44, "2026-09-13"),
    ("eelisraie", "eelis:kaadamisalad", 1, "2026-09-13"),
)

#: Source label printed on every installable sidecar + legend.
SOURCE_LABEL = (
    "Keskkonnaagentuuri EELIS WFS (võtmeta, loetud %s)" % VERDICT_DATE
)

#: Name fragments marking a zone row fictitious (case-insensitive,
#: matched against nimi/name/zone_id). Fails closed on anything
#: plausibly fiction (Estonian "fiktiivne" + English test/demo
#: spellings); reserve passthrough for genuinely real register
#: names. Real EELIS register names never carry these markers.
FICTITIOUS_MARKERS = frozenset({
    "fiktiivne", "fiktiiv", "fixture", "demo", "test-",
    "testzone", "naidis", "näidis", "example", "placeholder",
    "vale-", "(vale)",
})


def _zone_text(zone: dict) -> str:
    """Searchable text of a zone row (nimi + name + zone_id)."""
    if not isinstance(zone, dict):
        return ""
    parts = [zone.get("nimi"), zone.get("name"), zone.get("zone_id")]
    return " ".join(str(p) for p in parts if isinstance(p, str))


def is_fictitious(zone: dict) -> bool:
    """True when a zone row is plausibly fictitious (never installed).

    Case-insensitive marker match over the row's name fields. A
    non-dict row reads as fictitious (fail closed: an unparseable
    row is never a real zone).
    """
    if not isinstance(zone, dict):
        return True
    text = _zone_text(zone).lower()
    return any(m.lower() in text for m in FICTITIOUS_MARKERS)


def scrub_fictitious(zones: list) -> Tuple[List[dict], int]:
    """Split a candidate sidecar zone list into (clean, dropped_n).

    Pure, offline. Fictitious rows are dropped, never faked into
    real ones; the dropped count is returned so the installer can
    log the refusal. Non-list input is unknown, never installable:
    None reads as ([], 0); any other non-list shape reads as
    ([], 1) -- fail closed, never installed.
    """
    if not isinstance(zones, list):
        return ([], 0 if zones is None else 1)
    clean: List[dict] = []
    dropped = 0
    for zone in zones:
        if is_fictitious(zone):
            dropped += 1
        elif isinstance(zone, dict):
            clean.append(zone)
        else:
            dropped += 1
    return (clean, dropped)


def installable_sidecar(zones: list) -> Tuple[bool, str]:
    """Install gate for a candidate eelis-areas.json zone list.

    Returns (installable, Estonian reason). Fiction -> refused;
    empty/unknown -> honest-empty (never installed as data);
    non-empty fiction-free -> installable with dated source.
    """
    if not isinstance(zones, list) or not zones:
        return (False, "EI OLE: tõmmis puudub -- kiht jääb ausalt "
                "tühjaks, kuni elus tõmmis paigaldatakse "
                "(allikas: %s)" % SOURCE_LABEL)
    clean, dropped = scrub_fictitious(zones)
    if dropped:
        return (False, "EI OLE: %d fiktiivset tsooni eemaldatud -- "
                "fiktiivseid tsoone EI paigaldata elusasse "
                "tõmmisesse (kontrollitud %s)" % (dropped, VERDICT_DATE))
    return (True, "paigaldatav: %d tõelist tsooni (%s)"
            % (len(clean), SOURCE_LABEL))


def coverage_note() -> str:
    """Dated per-layer coverage sentence (legend/docs-ready)."""
    bits = ["%s %d kirjet Tallinna aknas (loetud %s)" % (wfs, n, d)
            for _, wfs, n, d in VERDICT_LAYERS]
    return ("EELIS tõmmis %s: %s. "
            "Korduskontroll hiljemalt %s."
            % (VERDICT_DATE, "; ".join(bits), RECHECK_AFTER))


def verdict_summary() -> str:
    """Full dated verdict text (docs-ready, one paragraph per fact)."""
    lines = [
        "EELIS tõeliste andmete otsus (issue #517, %s):" % VERDICT_DATE,
        "Tallinna aknas leidub %s (33+44+1 kirjet, seisuga "
        "2026-09-13; elusus kinnitatud %s) -- "
        "tühi kaart on paigaldamata tõmmis, mitte puuduv allikas."
        % (" + ".join(w for _, w, _, _ in VERDICT_LAYERS), VERDICT_DATE),
        "Ehitaja tõmmis (/tmp/hf-488-snap, 3 tsooni) on KÕIK "
        "fiktiivne -- fiktiivseid tsoone EI paigaldata elusasse "
        "tõmmisesse (scrub_fictitious valvur, testidega).",
        "Korduskontroll hiljemalt %s." % RECHECK_AFTER,
    ]
    return "\n".join(lines)


#: Dim-key registry surface (no scores -- this module gates
#: installs; the P4-015/P4-024/P4-030 scores stay in dims_p4_eelis).
VERDICT_DIMS = ("eelis_realdata_verdict",)
