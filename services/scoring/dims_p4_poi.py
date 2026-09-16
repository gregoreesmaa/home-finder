"""POI cross-check + amenity upgrade from huvipunktid WFS (issue #549).

Two outputs: (1) an OSM-vs-register agreement audit (pure, runs on
caller-supplied counts — this alone justifies the issue); (2) honest
proximity dims for long-tail types with no dedicated issue.

Source: Maa- ja Ruumiamet huvipunktide andmebaas (meta-register over
national source registers, "vahekiht" intermediate layer), MONTHLY,
all-Estonia.

Probe (2026-09-16, UA home-finder-idea-probe/1.0, single
GetCapabilities pull — the type-bounded feature pull belongs to the
licence-day bulk job):
https://gsavalik.envir.ee/geoserver/huvipunkt/wfs?service=WFS&request=GetCapabilities
-> HTTP 200, 191 963 B, ~0.09 s. 98 feature types (huvipunkt:*,
vendored below as observed capability inventory — type NAMES only, no
points), CRS EPSG:3301, updateSequence 1980. No licence statement in
the capabilities and NONE in the catalogue → hard gate holds.

Licence gate OPENED 2026-09-16 (issue #612, re-probe with UA
home-finder-research): the SAME GetCapabilities body carries the
licence in ServiceIdentification/Abstract — "Kui konkreetse kihi
juures ei ole märgitud teisiti, siis teenuse kaudu saadud andmetele
kohaldub Maa- ja Ruumiameti avatud ruumiandmete litsents
(https://geoportaal.maaamet.ee/avaandmete-litsents). Andmeid võib
kasutada mistahes kõlbelisel eesmärgil." Fees/AccessConstraints read
"puudub"; no per-layer override is stated for the three long-tail
types. The portal catalogue page itself is a JS shell (no readable
licence field), so the capabilities Abstract is the dated evidence.
LICENCE_OK = True from this re-probe on; the long-tail proximity
dims score live, stamping the open licence in every reason. The
agreement audit stays pure maths and always runs.

Dedicated-source split (LOAD-BEARING, enforced by test — never
double-score): where a dedicated register issue exists, it wins and
huvipunktid stays out:

| huvipunkt type | Owner | This module |
|---|---|---|
| perearst (+ haigla/kiirabi/tervisekaubad? no — see right) | #532 medre/GP | EXCLUDED: perearst |
| haridusasutus | #530 EHIS | EXCLUDED |
| spordihoone/staadion/ujula/tenniseplats/supluskoht | #531 sports | EXCLUDED |
| ohtlik_ettevote | #527 Seveso | EXCLUDED |
| varjumiskoht (+ paastekomando) | #528 shelters | EXCLUDED: varjumiskoht |
| raamatukogu / post / tervisekaubad (apteek-ish) | no dedicated issue | LONG-TAIL dims here |
| toitlustus / parkla / bussipeatus... | OSM Groups 11/15 | audit only (OSM legs stay primary) |

Freshness caveat (LOAD-BEARING): monthly intermediate layer over
source registers of varying vintage — per-type staleness table
belongs to the licence-day bulk job (first pulls record per-type
update stamps); reasons always say "vahekiht".

Shape: walk-graph bands ≤300/600/1000 m, absolute 0-100,
NULL-beyond (no POI within 1000 m -> None, never "no amenity" as a
score — thin register mapping, p52 floor precedent).

Style: pure functions. No network, no cache. No WEIGHTS / livability /
layers / registry edits (joint precedent).
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Licence gate (OPENED 2026-09-16, issue #612): the WFS
#: GetCapabilities Abstract applies the Maa- ja Ruumiamet open
#: spatial-data licence unless a layer says otherwise (no override
#: for the long-tail types). Reasons stamp it, never bare trust.
LICENCE_OK = True
LICENCE_NOTE = ("Maa- ja Ruumiamet avatud ruumiandmete litsents "
                "(geoportaal.maaamet.ee/avaandmete-litsents)")
#: Freshness marker in every reason (monthly intermediate layer).
VAHEKIHT = "vahekiht (lähteregistrite koondkiht)"

#: 98 feature-type names observed live 2026-09-16 (GetCapabilities).
#: Capability inventory (names only), NOT vendored POI points.
HUVIPUNKT_TYPES = frozenset({
    "administratiivkeskus", "arihoone", "autonoomne_tankla",
    "bussipeatus", "bussiterminal", "eestiterviserada_j",
    "golfivaljak", "haigla", "haridusasutus", "hoolekanne", "hudrant",
    "huvipunkt", "jaahall", "jaatmejaam", "kaitsetahis", "kalmistu",
    "kea_kylastustaristu", "kea_matkarada_j", "kiirabi", "kino",
    "kirik", "kontserdimaja", "kultuurikeskus", "kultuurilugu",
    "kutusehoid", "kylastus_allikas", "kylastus_infotahvel",
    "kylastus_jalgrattarada", "kylastus_liiklusmark",
    "kylastus_lokkekoht", "kylastus_manguvaljak", "kylastus_matkarada",
    "kylastus_metsamaja", "kylastus_parkla", "kylastus_puhkekoht",
    "kylastus_purre", "kylastus_randumissild", "kylastus_suunaviit",
    "kylastus_teabepunkt", "kylastus_telkimisplats", "kylastus_tokkepuu",
    "kylastus_vaatetorn", "kylastus_wc", "lasketiir", "lennuterminal",
    "lennuvali", "loodusobjekt", "maaratlemata_peatus",
    "maesuusasport", "majutus", "muu_sportimiskoht", "muuseum",
    "ohtlik_ettevote", "ooklubi", "paastekomando", "pangaautomaat",
    "pangakontor", "parkla", "perearst", "piirivalve", "politsei",
    "post", "raamatukogu", "rajatis", "ratsaspordikoht", "religioon",
    "riigiasutus", "rmk_kylastustaristu", "rmk_matkarada_j",
    "rmk_matkatee_j", "rmk_rattarada_j", "rongipeatus",
    "rongiterminal", "sadam", "sadamaterminal", "sild",
    "spordi_abirajatis", "spordihoone", "staadion", "supluskoht",
    "suusahuppemagi", "tankla", "teater", "tehnikaspordi_rada",
    "tenniseplats", "tervisekaubad", "toitlustus", "trammipeatus",
    "trollipeatus", "tunnel", "uhiselamu", "ujula", "valisesindus",
    "valispallivaljak", "varjumiskoht", "veekogu", "veevotukoht",
    "velodroom",
})

#: Types owned by dedicated register issues — never scored here.
DEDICATED_SPLIT = {
    "perearst": "#532",
    "haridusasutus": "#530",
    "spordihoone": "#531",
    "staadion": "#531",
    "ujula": "#531",
    "tenniseplats": "#531",
    "supluskoht": "#531",
    "ohtlik_ettevote": "#527",
    "varjumiskoht": "#528",
    "paastekomando": "#528",
}
#: Long-tail types with dense coverage and NO dedicated issue.
LONG_TAIL = ("raamatukogu", "post", "tervisekaubad")


def _band(value: Optional[float], bands: List[Tuple[float, int]]) -> Optional[int]:
    """First score whose threshold covers the value; None stays None."""
    if value is None:
        return None
    for limit, pts in bands:
        if value <= limit:
            return pts
    return bands[-1][1]


# ---------------------------------------------------------------------------
# (1) Agreement audit: OSM count vs register count per type (always live).
# ---------------------------------------------------------------------------

def agreement_audit(rows: List[dict]) -> List[dict]:
    """Per-type OSM-vs-register agreement rows (pure).

    Input rows: {"type", "osm_n", "reg_n"} (Harjumaa counts, caller
    supplied). Output adds "ratio" (reg/osm, None when osm_n == 0) and
    "verdict": "register-rikkam" (ratio >= 1.5), "sarnane"
    (0.67 <= ratio < 1.5), "osm-rikkam" (ratio < 0.67), or
    "võrdlus puudub" when either count is missing.
    """
    out = []
    for r in rows:
        t = r.get("type", "?")
        o, g = r.get("osm_n"), r.get("reg_n")
        if not isinstance(o, (int, float)) or not isinstance(g, (int, float)):
            out.append({"type": t, "osm_n": o, "reg_n": g,
                        "ratio": None, "verdict": "võrdlus puudub"})
            continue
        ratio = (g / o) if o > 0 else None
        if ratio is None:
            verdict = "võrdlus puudub"
        elif ratio >= 1.5:
            verdict = "register-rikkam"
        elif ratio >= 0.67:
            verdict = "sarnane"
        else:
            verdict = "osm-rikkam"
        out.append({"type": t, "osm_n": o, "reg_n": g,
                    "ratio": None if ratio is None else round(ratio, 2),
                    "verdict": verdict})
    return out


# ---------------------------------------------------------------------------
# (2) Long-tail proximity dims (gated: NULL until licence clears).
# ---------------------------------------------------------------------------

def _score_dist(dist_m: Optional[float]) -> Optional[int]:
    """Pure walk bands; None beyond 1000 m (NULL-beyond)."""
    if dist_m is None or dist_m < 0:
        return None
    if dist_m > 1000:
        return None
    return _band(dist_m, [(300, 85), (600, 70), (1000, 55)])


def _poi_dim(poi_type: str, origin: Optional[Tuple[float, float]],
             dist_m: Optional[float]) -> Score:
    if poi_type in DEDICATED_SPLIT:
        return None, ("%s: eraldiregistri küsimus (%s võidab) – "
                      "topeltarvestust pole" % (poi_type,
                                                DEDICATED_SPLIT[poi_type]))
    if not LICENCE_OK:
        return None, ("%s: %s (%s)" % (poi_type, LICENCE_NOTE, VAHEKIHT))
    if not origin or dist_m is None:
        return None, ("%s info puudub" % poi_type)
    s = _score_dist(dist_m)
    if s is None:
        return None, ("%s 1000 m raadiuses registris puudub – "
                      "kaardistus võib olla lünklik (%s)" % (poi_type, VAHEKIHT))
    return s, ("%s %d m (%s, %s, %s)"
               % (poi_type, int(round(dist_m)), VAHEKIHT, "register",
                  LICENCE_NOTE))


def dim_poi_library(origin: Optional[Tuple[float, float]],
                    dist_m: Optional[float]) -> Score:
    """Long-tail: raamatukogu proximity (no dedicated issue)."""
    return _poi_dim("raamatukogu", origin, dist_m)


def dim_poi_post(origin: Optional[Tuple[float, float]],
                 dist_m: Optional[float]) -> Score:
    """Long-tail: post proximity (no dedicated issue)."""
    return _poi_dim("post", origin, dist_m)


def dim_poi_pharmacy(origin: Optional[Tuple[float, float]],
                     dist_m: Optional[float]) -> Score:
    """Long-tail: tervisekaubad (apteek-ish) proximity."""
    return _poi_dim("tervisekaubad", origin, dist_m)


#: Registry for the central weight-rebalance follow-up: (dims key, param id).
POI_DIMS = (
    ("poi_library", "p4-poi-raamatukogu", dim_poi_library),
    ("poi_post", "p4-poi-post", dim_poi_post),
    ("poi_pharmacy", "p4-poi-tervisekaubad", dim_poi_pharmacy),
)


#: Honest Estonian web labels for licence-day (never rendered while gated).
LAYER_META = {
    "poi_library": {
        "param": "p4-poi-raamatukogu",
        "title": "Raamatukogu (registri-hinnang, litsents ootel)",
        "good": "roheline = raamatukogu jalutuskäigus",
        "bad": "punane = raamatukogu kaugel",
        "source": "huvipunktid WFS (litsents kinnitamata; vahekiht)",
    },
    "poi_post": {
        "param": "p4-poi-post",
        "title": "Post (registri-hinnang, litsents ootel)",
        "good": "roheline = post jalutuskäigus",
        "bad": "punane = post kaugel",
        "source": "huvipunktid WFS (litsents kinnitamata; vahekiht)",
    },
    "poi_pharmacy": {
        "param": "p4-poi-tervisekaubad",
        "title": "Tervisekaubad (registri-hinnang, litsents ootel)",
        "good": "roheline = pood jalutuskäigus",
        "bad": "punane = pood kaugel",
        "source": "huvipunktid WFS (litsents kinnitamata; vahekiht)",
    },
}
