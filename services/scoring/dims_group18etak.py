"""Measured ETAK land-cover/water/relief legs (issue #552).

Upgrades the OSM-tag proxy legs with measured ETAK geometries: actual
wetland under/near the plot (dampness), actual water width/flow
(drainage), actual courtyard/green classes (impervious/green exposure),
micro-slopes and ditches (runoff). Buyer questions and band shapes stay
unless evidence moves them — only the legs get metres instead of tags.

Sources (probed 2026-09-16, UA ``home-finder-idea-probe/1.0``):
WFS ``https://gsavalik.envir.ee/geoserver/etak/wfs`` — HTTP 200,
39 feature types, no key, no 429. Headline types: ``e_306_margala_a``
(wetland polygons, 54 929 nationwide, 178 in the Tallinn bbox),
``e_202_seisuveekogu_a`` (standing waters, 122 109 nationwide),
``e_102_nolv_j`` (slopes/scarps, 21 745 nationwide). CRS EPSG:3301;
attributes carry ``tyyp/tyyp_tekst`` (e.g. Soovik), ``nimetus`` for
waters, ``kaldaastang`` for scarps, plus ``muutmisaeg``/``geom_muutmisaeg``
per tile (sample: 2018-01-23 / 2009-07-29 — DAILY feed, survey vintages
vary by tile). Licence: CC BY 4.0 for maakate/hüdrograafia (catalogue
claim); pinnamood licence unstated → that leg is verify-or-close gated
(always NULL, stated in code + docs).

Where ETAK contradicts OSM, ETAK wins and the discrepancy is logged in
the reason (never a silent overwrite).

Style mirrors ``dims_group18chm``: pure scorers,
(origin, etak) -> (Optional[int 0..100], Estonian reason). No network
here — the bulk job turns WFS features into the per-listing ``etak``
artefact the scorers join against. Transport errors are never cached as
data (there is no cache here at all).

Artefact shape: {"vintage", "wetland", "water", "yard", "relief"}.
``wetland`` = {"inside", "near_m", "tyyp"}; ``water`` = {"inside",
"near_m", "name", "kind"}; ``yard`` = {"inside", "klass"}; ``relief``
is accepted but never scored (licence gate). None / missing theme ->
NULL (never zero — NULL where ETAK has no feature).

Judgment calls (reviewable):
* Wetland bands follow the tyyp split: madalsoo/raba (wettest) 25,
  soovik/õõtsik 35, other/unknown 30; near bands 50/150 m mirror the
  old dampness proxies (reviewer call per leg stands).
* Water bands are distance-only (inside 30, ≤30 m 50, ≤100 m 65):
  width/type re-justifies the band in the reason but does not move the
  edge — the old p50 edges stand until the bulk job measures widths.
* Yard classes: eraõued/tootmisõued 45 (impervious), haljasala 70
  (green), muu kõlvik 60. Courtyard class confirms impervious exposure;
  it does not re-label the buyer question.
* Pinnamood (nõlv/pinnavorm/kivi) never scores here: licence unstated,
  so ``dim_etal_relief`` returns NULL with the gate reason. If the
  licence is proven, this is the leg to graduate (schema + counts ship
  in docs/group18etak.md).
* Vintage is stated in every scored reason (tiles vary — years never mix
  silently); unknown vintages still score but say "tundmatu vintage".

Integration (deliberately NOT done here): the bulk job + any
livability / layers / registry edits stay a joint change (per-batch
hook edits break every sibling). No WEIGHTS / livability / layers edits.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Licence + publisher (catalogue claim for maakate/hüdrograafia).
ETAK_LICENCE = "CC BY 4.0 (Maa- ja Ruumiamet)"
#: CRS observed live (sample geometries srsName).
ETAK_CRS = "EPSG:3301"
#: WFS endpoint observed live 2026-09-16.
ETAK_WFS = "https://gsavalik.envir.ee/geoserver/etak/wfs"
#: Wettest wetland types (tyyp_tekst, case-insensitive substring).
WETTEST = ("madalsoo", "raba")
#: Mid wetland types.
MID_WET = ("soovik", "õõtsik")
#: Impervious courtyard classes (klass, case-insensitive substring).
IMPERVIOUS_YARD = ("eraõued", "eraued", "tootmisõued", "tootmisoued")


def check_vintage(vintage: object) -> bool:
    """True when the artefact vintage is a usable timestamp or year."""
    if not isinstance(vintage, str) or not vintage.strip():
        return False
    v = vintage.strip()
    if len(v) == 4 and v.isdigit() and 2000 <= int(v) <= 2026:
        return True
    return len(v) >= 10 and v[4] == "-" and v[:4].isdigit()


def _vintage_note(etak: dict) -> str:
    v = etak.get("vintage")
    if check_vintage(v):
        return "ETAK %s" % v
    return "ETAK tundmatu vintage (%s)" % ("puudub" if v is None else v)


def _theme(etak: Optional[dict], key: str) -> Optional[dict]:
    if not isinstance(etak, dict):
        return None
    sub = etak.get(key)
    return sub if isinstance(sub, dict) else None


def histogram(values: List[float], edges: List[float]) -> List[int]:
    """Bin counts for edges (pure helper for the pre/post upgrade check)."""
    counts = [0] * (len(edges) + 1)
    for v in values:
        placed = False
        for i, e in enumerate(edges):
            if v <= e:
                counts[i] += 1
                placed = True
                break
        if not placed:
            counts[-1] += 1
    return counts


# ---------------------------------------------------------------------------
# Measured legs (absolute 0-100 kept; NULL where ETAK has no feature).
# ---------------------------------------------------------------------------

def dim_etal_wetland(origin: Optional[Tuple[float, float]],
                     etak: Optional[dict]) -> Score:
    """Wetland-class containment → dampness band (p405/p468/p479 cousins)."""
    if not origin:
        return None, "ETAK andmed puuduvad – niiskuse hinnangut pole"
    sub = _theme(etak, "wetland")
    if sub is None:
        return None, "ETAK märgala puudub – niiskuse hinnangut pole"
    assert etak is not None
    tag = _vintage_note(etak)
    tyyp = sub.get("tyyp") if isinstance(sub.get("tyyp"), str) else ""
    inside = sub.get("inside") is True
    near = sub.get("near_m")
    near = float(near) if isinstance(near, (int, float)) and near >= 0 else None
    if inside:
        low = tyyp.lower()
        if any(w in low for w in WETTEST):
            s = 25
        elif any(w in low for w in MID_WET):
            s = 35
        else:
            s = 30
        return s, ("märgala %s sees (%s, mõõdetud; OSM asemel ETAK)"
                   % (tyyp or "teadmata klass", tag))
    if near is not None:
        if near <= 50:
            return 55, ("märgala %.0f m (%s, mõõdetud)" % (near, tag))
        if near <= 150:
            return 70, ("märgala %.0f m (%s, mõõdetud)" % (near, tag))
    return None, ("märgala kaugel/puudub – NULL, mitte null (%s)" % tag)


def dim_etal_water(origin: Optional[Tuple[float, float]],
                   etak: Optional[dict]) -> Score:
    """Water width/type → drainage band re-justification (p50 cousin)."""
    if not origin:
        return None, "ETAK andmed puuduvad – drenaaži hinnangut pole"
    sub = _theme(etak, "water")
    if sub is None:
        return None, "ETAK veekogu puudub – drenaaži hinnangut pole"
    assert etak is not None
    tag = _vintage_note(etak)
    name = sub.get("name") if isinstance(sub.get("name"), str) else ""
    kind = sub.get("kind") if isinstance(sub.get("kind"), str) else ""
    label = name or kind or "veekogu"
    inside = sub.get("inside") is True
    near = sub.get("near_m")
    near = float(near) if isinstance(near, (int, float)) and near >= 0 else None
    if inside:
        return 30, ("%s sees (%s, mõõdetud; OSM asemel ETAK)" % (label, tag))
    if near is not None:
        if near <= 30:
            return 50, ("%s %.0f m (%s, mõõdetud)" % (label, near, tag))
        if near <= 100:
            return 65, ("%s %.0f m (%s, mõõdetud)" % (label, near, tag))
    return None, ("veekogu kaugel/puudub – NULL, mitte null (%s)" % tag)


def dim_etal_yard(origin: Optional[Tuple[float, float]],
                  etak: Optional[dict]) -> Score:
    """Courtyard class → impervious/green confirmation (p181/p63 cousins)."""
    if not origin:
        return None, "ETAK andmed puuduvad – õue hinnangut pole"
    sub = _theme(etak, "yard")
    if sub is None:
        return None, "ETAK õueklass puudub – õue hinnangut pole"
    assert etak is not None
    tag = _vintage_note(etak)
    klass = sub.get("klass") if isinstance(sub.get("klass"), str) else ""
    inside = sub.get("inside") is True
    if not inside:
        return None, ("õu kaugel/puudub – NULL, mitte null (%s)" % tag)
    low = klass.lower()
    if any(w in low for w in IMPERVIOUS_YARD):
        return 45, ("õu %s (kõvakate, %s, mõõdetud)" % (klass or "?", tag))
    if "haljas" in low:
        return 70, ("õu %s (haljas, %s, mõõdetud)" % (klass or "?", tag))
    return 60, ("õu %s (%s, mõõdetud)" % (klass or "muu kõlvik", tag))


def dim_etal_relief(origin: Optional[Tuple[float, float]],
                    etak: Optional[dict]) -> Score:
    """Micro-slope/ditch runoff flag — LICENCE-GATED, always NULL."""
    return None, ("pinnamood (nõlv/pinnavorm) litsents tõestamata – "
                  "EI OLE hinnangut (verify-or-close)")


DIMS = {
    "wetland": ("ETAK märgala → niiskus", dim_etal_wetland),
    "water": ("ETAK veekogu → drenaaž", dim_etal_water),
    "yard": ("ETAK õu → kõvakate/haljas", dim_etal_yard),
    "relief": ("ETAK pinnamood → äravool (litsentsi-gated)", dim_etal_relief),
}

LAYER_META = {
    "source": "ETAK maakate + hüdrograafia (WFS gsavalik.envir.ee/geoserver/etak)",
    "licence": ETAK_LICENCE,
    "crs": ETAK_CRS,
    "wfs": ETAK_WFS,
    "shape": "measured-geometry legs inside existing shapes (upgrade only)",
}


def score_etak(origin: Optional[Tuple[float, float]],
               etak: Optional[dict]) -> Dict[str, Score]:
    """Score every ETAK leg (pure; NULL where the theme is missing)."""
    return {key: fn(origin, etak) for key, (_, fn) in DIMS.items()}
