"""Night-noise score from existing OSM nightlife density (issue #695).

No new source, no new pull: bars/pubs/nightclubs/casinos are already
parsed in the Group 9 OSM dims (dims_group09.GROUP09_POI_KIND maps
amenity=bar|pub|nightclub|casino -> "nightlife"; amenity=cinema is
deliberately EXCLUDED — seated culture, not late-night nuisance).
This module scores DENSITY bands where Group 9 scores NEAREST distance:
more late-night venues near the flat = noisier = LOWER score (pinned).

Grounding (local held extract /private/tmp/estonia-260914.osm.pbf,
probed 2026-09-19 with osmium tags-filter + 300 m neighbour count):
* Tallinn: 203 venues (bar 116, pub 43, nightclub 18, casino 26);
* densest (Vanalinn): ~67 venues within 300 m of each other;
* quiet streets: 1-2 within 300 m.
Bands below put Vanalinn at the floor and lone venues near the top.

Style mirrors livability.py / dims_group09.py: pure function,
Estonian reasons, None when there is no data (never a faked number).
The caller counts venues in its window (300 m per the probe) and
passes the kinds in — this module does no fetching and adds no
Overpass fragment (the Group 9 fragment already fetches these tags).

Standalone on purpose (no import of dims_group09/livability): NULL-free
tiny module; keeps a future central hook cycle-free (same precedent as
dims_group01a.py).
"""

from typing import Dict, List, Optional, Tuple

#: Raw OSM amenity values + the grouped "nightlife" kind the Group 9
#: plumbing already emits. Cinema deliberately absent (see header).
NIGHTLIFE_KINDS = frozenset({"bar", "pub", "nightclub", "casino", "nightlife"})

Score = Tuple[int, str]  # (score 0..100, Estonian reason)


def _is_nightlife(item) -> bool:
    """Kind string or {"kind": ...} POI dict -> late-night venue or not."""
    kind = item.get("kind") if isinstance(item, dict) else item
    return kind in NIGHTLIFE_KINDS


def night_noise(pois: Optional[List]) -> Optional[Score]:
    """Per-area night-noise 0..100 from nightlife density (existing OSM only).

    pois: venue kinds (or {"kind": ...} dicts) already counted in the
    caller's window. Noisier = LOWER score. Empty/None -> None
    (no data, never faked quiet).
    """
    if not pois:
        return None
    n = sum(1 for p in pois if _is_nightlife(p))
    if n <= 0:
        return 85, "Lähikonnas kaardistatud ööelu-kohti pole (müraproksi: vaikne)"
    if n <= 2:
        return 80, "Ööelu-müra proksi: %d ööelu-kohta lähedal (hinnang: rahulik)" % n
    if n <= 5:
        return 65, "Ööelu-müra proksi: %d ööelu-kohta lähedal (hinnang: elav)" % n
    if n <= 10:
        return 50, "Ööelu-müra proksi: %d ööelu-kohta lähedal (hinnang: lärmakas)" % n
    if n <= 20:
        return 35, "Ööelu-müra proksi: %d ööelu-kohta lähedal (hinnang: väga lärmakas)" % n
    return 20, "Ööelu-müra proksi: %d ööelu-kohta lähedal (hinnang: Vanalinna-tasemel melu)" % n
