"""P4 measured land-cover/water/relief legs from ETAK (issue #552).

Three measured upgrades for legs that today run on OSM-tag proxies:
actual wetland under/near the plot (dampness, mosquitoes, building
limits), actual water width/flow (drainage + flood-adjacent honesty),
actual courtyard/green/wasteland classes (impervious/green exposure),
micro-slopes and ditches (runoff direction). Buyer questions and band
shapes stay unless evidence moves them — ETAK wins over OSM on
geometry, and discrepancies are logged for review, never silently
mixed. #546 (CHM heights) is the vertical sibling (height vs.
footprint class) — coordinate, don't merge. No ETAK
transport/buildings legs here (owned via #536 + G18 work).

OPENNESS VERDICT (polite probes, 2026-09-16, custom UA, /tmp/hf552_*):
* https://andmed.eesti.ee/datasets/eesti-topograafia-andmekogu-maakate
  -> HTTP 200, 75497 bytes, Angular JS shell with no server-rendered
  distribution/API URL and no API hints in markup. Bundle dig stopped
  per the polite budget.
* https://teenus.maaamet.ee/ows/etak?service=WFS&...GetCapabilities
  (official Maa-amet WFS URL pattern per the Maardlate QGIS manual)
  -> HTTP 200, 626 bytes, MapServer 7.6.2 error
  "msLoadMap(): Unable to access file. (/data/data/etak.map)" — the
  guessed dataset path does not exist server-side. No further guesses
  per the probe budget: the WFS endpoint is UNVERIFIED, so Harjumaa
  feature counts per class, CRS, and vintage/update behaviour are
  unmeasured (documented below as harvest-PR work).
* Licence: maakate + hudrograafia are CC BY 4.0 per the issue
  catalogue mirror (attribution kept below). The ETAK open-data
  licence agreement EXISTS at geoportaal.maaamet.ee (HTTP 200, 85 KB,
  Maa- ja Ruumiamet, 2025-01-03) but its custom-encoded text could not
  be extracted with stdlib-only tooling — coverage of pinnamood is
  therefore UNPROVEN and the pinnamood leg stays licence-gated NULL
  per the issue contract.

HONESTY (AGENTS.md 7.2): absolute 0-100 kept; NULL where ETAK has no
feature (never zero); vintage rides in every scored reason, never
mixed silently. Every dim scores ONLY joined records; with no join
all return NULL. Bands below are provisional: live pre/post
histograms (Tallinn + rural) are pending the harvest PR that verifies
the endpoint — the rules are pinned by hermetic fixture tests now so
the harvest can only fill data, never reshape silently.

Style mirrors dims_p4_maaparandus.py (#551, closest probe precedent):
pure (parcel, join) -> Score, Estonian reasons, hermetic fixtures.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Licence state per ETAK theme (see module docstring).
LICENCE_BY_THEME = {
    "maakate": "CC-BY-4.0",
    "hudrograafia": "CC-BY-4.0",
    "pinnamood": "UNVERIFIED",
}

ATTRIBUTION = ("Allikas: Maa- ja Ruumiamet, Eesti topograafia "
               "andmekogu ETAK (CC BY 4.0, maakate/hüdrograafia)")

#: Wetland kõlvikud -> dampness band (wetter class = stronger flag).
WETLAND_SCORE = {
    "madalsoo": 40,
    "õõtsik": 40,
    "raba": 50,
    "soovik": 50,
}

#: Courtyard/green/wasteland classes -> exposure confirmation.
GROUND_SCORE = {
    "eraõued": 55,
    "tootmisõued": 55,
    "tühermaa": 50,
    "haljasala": 70,
}

#: Near-water drainage band (m) and wide-flow threshold (m).
WATER_BAND_M = 100.0
WIDE_FLOW_M = 10.0


def _vintage(join: Optional[dict], key: str) -> str:
    if join and join.get(key) and join[key].get("vintage"):
        return " (ETAK seis %s)" % join[key]["vintage"]
    return " (ETAK seis teadmata)"


def dim_wetland_dampness(origin: Optional[Tuple[float, float]],
                         join: Optional[dict]) -> Score:
    """Dampness band from ETAK maakate wetland-class containment.

    join: None, or {"maakate": {"klass" (str|None), "vintage" (str|None)}}.
    Only wetland containment scores; measured non-wetland is still not
    dryness proof (drainage/groundwater unjoined) -> NULL.
    """
    if join is None or not join.get("maakate"):
        return (None, "Märgalaseos puudub (hinnang EI OLE): "
                "ETAK-maakatte väljavõtet ei ole liidetud.")
    klass = (join["maakate"] or {}).get("klass")
    tag = _vintage(join, "maakate")
    if klass in WETLAND_SCORE:
        return (WETLAND_SCORE[klass],
                "Krunt märgalal (%s, hinnang)%s: niiskus-, sääse- ja "
                "ehituspiirangu risk — OSM-i asemel mõõdetud kõlvik."
                % (klass, tag))
    if klass is None:
        return (None, "Märgalaseos puudub (hinnang EI OLE): ETAK-alal "
                "kõlvikut ei ole — see ei ole kuivuse tõend.")
    return (None, "Mõõdetud kõlvik %s ei ole märgala (hinnang EI OLE): "
            "kuivendus/põhjavesi on liitmata, see ei ole kuivuse tõend%s."
            % (klass, tag))


def dim_water_drainage(origin: Optional[Tuple[float, float]],
                       join: Optional[dict]) -> Score:
    """Drainage re-justification from ETAK hüdrograafia width/flow.

    join: None, or {"hydro": {"veetüüp" (str|None), "laius_m" (float|None),
    "kaugus_m" (float|None), "truup" (bool), "vintage" (str|None)}}.
    """
    if join is None or not join.get("hydro"):
        return (None, "Veekoguseos puudub (hinnang EI OLE): "
                "ETAK-hüdrograafia väljavõtet ei ole liidetud.")
    hydro = join["hydro"] or {}
    tag = _vintage(join, "hydro")
    dist = hydro.get("kaugus_m")
    if dist is None or dist > WATER_BAND_M:
        return (None, "Lähikonnas (%dm) ETAK-veekogu ei ole (hinnang "
                "EI OLE): see ei ole kuivuse tõend%s."
                % (int(WATER_BAND_M), tag))
    width = hydro.get("laius_m")
    wtype = hydro.get("veetüüp") or "teadmata veetüüp"
    truup = " reguleeritud truubiga" if hydro.get("truup") else ""
    if wtype == "vooluvesi" and width is not None and width >= WIDE_FLOW_M:
        return (45, "Lai vooluvesi (%.0fm, %dm, hinnang)%s%s: "
                "kuivendus- ja suurvee-kõrvalmõju — mõõdetud laius, "
                "OSM-i asemel." % (width, int(dist), truup, tag))
    return (55, "%s %dm kaugusel (hinnang)%s%s: veekogu lähedus, "
            "mõõdetud ETAK-geomeetria%s."
            % (wtype, int(dist), truup, tag, ""))


def dim_ground_exposure(origin: Optional[Tuple[float, float]],
                        join: Optional[dict]) -> Score:
    """Impervious/green confirmation from ETAK courtyard classes.

    join: None, or {"maakate": {"klass" (str|None), "vintage" (str|None)}}.
    Upgrades the p181/p63 OSM proxies; shapes unchanged.
    """
    if join is None or not join.get("maakate"):
        return (None, "Õueala seos puudub (hinnang EI OLE): "
                "ETAK-maakatte väljavõtet ei ole liidetud.")
    klass = (join["maakate"] or {}).get("klass")
    tag = _vintage(join, "maakate")
    if klass in GROUND_SCORE:
        return (GROUND_SCORE[klass],
                "Mõõdetud kõlvik %s (hinnang)%s: OSM-ligikaudsuse "
                "asemel ETAK-klass." % (klass, tag))
    return (None, "Kõlvik %s ei ole õue-/haljas-/tühermaa klass "
            "(hinnang EI OLE)%s." % (klass or "teadmata", tag))


def dim_relief_objects(origin: Optional[Tuple[float, float]],
                       join: Optional[dict]) -> Score:
    """Pinnamood micro-relief leg: licence-gated NULL (licence unverified)."""
    return (None, "Pinnamoe seos puudub (hinnang EI OLE): ETAK-pinnamoe "
            "litsents on tõendamata — nõlvade/aukude/kraavide "
            "lähimõju hindamata, kontrolli geoportaalist.")


P4_ETAK_DIMS = {
    "wetland_dampness": ("Märgala-niiskus (ETAK)", dim_wetland_dampness),
    "water_drainage": ("Veekogu-kuivendus (ETAK)", dim_water_drainage),
    "ground_exposure": ("Õueala-kate (ETAK)", dim_ground_exposure),
    "relief_objects": ("Pinnamood (NULL)", dim_relief_objects),
}

P4_ETAK_PARAM_IDS = {"wetland_dampness": 552, "water_drainage": 552,
                     "ground_exposure": 552, "relief_objects": 552}


def score_p4_etak(origin: Optional[Tuple[float, float]],
                  join: Optional[dict]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """Roll up the ETAK dims; NULL dims contribute no reasons."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for key in ("wetland_dampness", "water_drainage", "ground_exposure"):
        value, reason = P4_ETAK_DIMS[key][1](origin, join)
        dims[key] = value
        if value is not None:
            reasons.append(reason)
    dims["relief_objects"] = None
    return dims, reasons
