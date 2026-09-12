"""Group 9b-noise extra sources (issue #131): wind turbines, quarries,
motorsport tracks and shooting ranges for the lowspec (p408) layer.

Stdlib only. Offline, snapshot-only (NO network): all vectors come from
the local 2026-09-12 snapshot one-time PBF exports below. Pure logic +
snapshot readers live at module top so unit tests stay hermetic; the
full-county build runs only via the documented experiment command.

HONESTY (load-bearing, AGENTS.md section 7.2): these are OSM PROXIMITY
points for heavy outdoor low-frequency/rumble sources — titles, legends
and sources keep saying "proksi (hinnang)", never dBA. A mapped source
nearby reads exposed (low score); in-bbox absence stays the quiet
evidence. What the snapshot does NOT support is deliberately excluded:

* man_made=windmill (184 nodes + 16 ways: heritage Dutch-type mills
  such as Kotlandi/Sutlepa/Leedri tuulik, building=yes/ruins) — silent
  monuments, not noise. The filter is generator:source=wind ONLY.
* Rooftop solar (power=generator + generator:source=solar, 2756
  features), diesel/biofuel/gas backup gensets (12) and small hydro (7):
  silent or intermittent indoor/emergency plant, not area noise.
* Indoor shooting (sport=shooting nodes in sports halls / "laskekeskus",
  42 nodes + 4 ways mixed indoor/outdoor): tags cannot tell indoor from
  outdoor, so only military=range polygons (4, outdoor by definition)
  are included.
* Mineshafts/adits (0 mapped), leisure=shooting_ground (0 mapped),
  sport=motorsport (0 mapped): nothing to include.
* Nightlife (283 pts, nuisance/p162) and heavy highways (3320 ways) are
  owned by sibling layers — not duplicated here.

Model (locked 2026-09-12, issue #131): the four classes join the
lowspec (p408) source set ONLY, scored with the unchanged lowspec half
(500 m, calm = 100*d/(d+500)). Rationale, per class:

* wind (53 power=generator + generator:source=wind NODES, 0 ways, 0
  relations — node-only extraction is complete here, verified by osmium
  fileinfo; the 4 site=wind_farm relations group the same nodes, so
  relations are skipped to avoid twins): turbine aerodynamic/gearbox
  hum is the canonical neighbour low-frequency complaint.
* quarry (landuse=quarry, 78 area assemblies: 74 closed ways +
  4 relations; 74 closed-way LineString twins + 12 member rings
  (farmyard/water/forest holes pulled in for relation completeness,
  6 as polygons + 6 as rings) dropped): blasting + crusher + truck
  rumble.
* motorsport (sport=motocross/karting, 37 track areas + 16 open
  centreline ways + 3 nodes = 56 source objects; 36 closed-way twins
  and 12 untagged member points (traffic_calming humps, start/finish
  dots pulled in by tags-filter) dropped): engine rumble.
* range (military=range, 4 polygons incl. Manniku; 4 closed-way twins
  dropped): live-fire rumble.

Vibration (p234) is deliberately UNCHANGED (rail + heavy roads, half
300 m): none of the four classes is a continuous ground-borne source,
so adding them there would fake the physics. This grows the p234/p408
split the buyer review asked about: r(vibration, lowspec) = 0.983 on
the current masters (5.8% of county cells differ by >10 pts); the new
lowspec-only sources add rural exposure pockets vibration honestly
does not see.

Node-vs-way mapping (osmium, harjumaa-260911.osm.pbf — fileinfo counts
include member nodes pulled in for way/relation completeness, so TRUE
counts below are tagged objects from OPL/export):

* wind: 53 tagged nodes, 0 ways, 0 relations.
* quarry: 78 tagged areas (74 closed ways + 4 relations); export
  emits 84 MultiPolygons (78 quarry + 6 member holes with
  non-quarry tags) + 80 closed LineStrings (74 area twins + 6
  member rings).
* motorsport: 53 tagged ways (40 motocross + 13 karting) + 3 tagged
  nodes; export emits 37 MultiPolygons (closed circuits assembled) +
  52 LineStrings (36 closed twins + 16 genuinely open) + 15 Points
  (3 tagged + 12 untagged members).
* range: 4 tagged ways; export emits 4 MultiPolygons + 4 closed twins.

One-time PBF exports (snapshot dir inputs, NOT committed — same pattern
as batch_genv_exposure.py derived-heavyroads.geojson; run once, then
the readers below consume the files offline):

  S=~/hf-data/2026-09-12/osm
  osmium tags-filter $S/harjumaa-260911.osm.pbf \\
      nwr/generator:source=wind \\
      -o /tmp/n-wind.pbf --overwrite
  osmium export /tmp/n-wind.pbf -o $S/derived-wind.geojson --overwrite
  osmium tags-filter $S/harjumaa-260911.osm.pbf nwr/landuse=quarry \\
      -o /tmp/n-quarry.pbf --overwrite
  osmium export /tmp/n-quarry.pbf -o $S/derived-quarry.geojson --overwrite
  osmium tags-filter $S/harjumaa-260911.osm.pbf nwr/sport=motocross \\
      nwr/sport=karting nwr/sport=motorsport \\
      -o /tmp/n-moto.pbf --overwrite
  osmium export /tmp/n-moto.pbf -o $S/derived-motorsport.geojson --overwrite
  osmium tags-filter $S/harjumaa-260911.osm.pbf nwr/military=range \\
      -o /tmp/n-range.pbf --overwrite
  osmium export /tmp/n-range.pbf -o $S/derived-range.geojson --overwrite

Experiment (needs the snapshot dir, NOT committed — measures the hook
effect on a Tallinn + Pakri test bbox, outputs to /tmp only):

  python3 /tmp/exp_lowspec_hook.py   # see docs/noise-vibration-lowspec.md

HOOK (exact, for whoever merges this alongside the in-flight
scripts/build/batch_genv_exposure.py — this module is intentionally
additive so it does NOT edit that file):

  build_all: read the four classes via lowspec_extra_points(snap) and
    extend the lowspec Dijkstra source cells:
      d_low = dijkstra_km(grid, cells_of_points(grid,
          heavy_pts + rail_pts + ind_pts + extra_pts))
    where extra_pts = sum(lowspec_extra_points(snap).values(), []).
  write_points: extend the lowspec payload with the same union:
      dedupe_cells(heavy_pts + rail_pts + ind_pts + extra_pts).
  Overpass live path: splice GROUP09B_EXTRA_FRAGMENT (see
    services/scoring/dims_group09b.py) — nwr/ everywhere, matching the
    PR #118 rule (quarries/tracks/ranges are way-mapped areas).
"""

import json
import math
import os

# ---------------------------------------------------------------------------
# Small local geometry helpers (same conventions as batch_genv_exposure.py;
# local copies so this module never couples to that file's in-flight edits).
# ---------------------------------------------------------------------------

LON_KM = 57.29
LAT_KM = 110.57

def _hav_km(lon1, lat1, lon2, lat2):
    """Equirectangular km (same 57.29/110.57 constants as walk_graph)."""
    return math.hypot((lon2 - lon1) * LON_KM, (lat2 - lat1) * LAT_KM)

#: Genuine motorsport sport values (leisure=track athletics/cycling and
#: the pulled-in traffic_calming/raceway member dots never match).
MOTO_SPORTS = ("motocross", "karting", "motorsport")


def _first(value):
    """First ;-separated tag value, else ''."""
    if not isinstance(value, str):
        return ""
    return value.split(";")[0].strip()


def _need(snap, *parts):
    p = os.path.join(snap, *parts)
    if not os.path.exists(p):
        raise SystemExit(
            "missing %s — run the one-time osmium exports in this "
            "module's docstring (snapshot-only, no network)" % p)
    return p


def _densify_line(coords, step_km=0.05):
    pts = []
    for i, (lon, lat) in enumerate(coords):
        pts.append((lon, lat))
        if i == 0:
            continue
        plon, plat = coords[i - 1]
        d = _hav_km(plon, plat, lon, lat)
        if d > step_km:
            n = int(d / step_km)
            for k in range(1, n):
                t = k / n
                pts.append((plon + (lon - plon) * t, plat + (lat - plat) * t))
    return pts


def _is_closed(coords):
    return len(coords) > 1 and coords[0] == coords[-1]


def _ring_sample(ring, keep=50):
    """Stride-sample an outer ring (mirrors read_amenity_geoms)."""
    return [(c[0], c[1]) for c in ring[:: max(1, len(ring) // keep)]]


# ---------------------------------------------------------------------------
# Snapshot readers: exported FeatureCollections -> point lists.
# ---------------------------------------------------------------------------

def _iter_features(snap, filename):
    """Yield (properties, geomtype, coordinates) for one derived file."""
    with open(_need(snap, "osm", filename), encoding="utf-8") as f:
        d = json.load(f)
    feats = d["features"] if isinstance(d, dict) else d
    for feat in feats:
        if not isinstance(feat, dict):
            continue
        g = feat.get("geometry") or {}
        yield (feat.get("properties") or {}, g.get("type"),
               g.get("coordinates"))


def read_wind_points(snap):
    """53 turbine nodes (node-mapped; relations group the same nodes)."""
    pts = []
    n = 0
    for props, gtype, coords in _iter_features(snap, "derived-wind.geojson"):
        n += 1
        if _first(props.get("generator:source")) != "wind":
            continue
        if gtype == "Point" and coords:
            pts.append((coords[0], coords[1]))
        elif gtype == "LineString" and coords:
            # Future-proofing: a way-mapped turbine row reads as its
            # midpoint (0 observed 2026-09-12 — all 53 are nodes).
            mid = coords[len(coords) // 2]
            pts.append((mid[0], mid[1]))
    return pts, {"features": n, "kept": len(pts)}


def read_quarry_points(snap):
    """84 quarry areas -> outer-ring samples (closed twins dropped)."""
    pts = []
    feats = twins = members = 0
    for props, gtype, coords in _iter_features(
            snap, "derived-quarry.geojson"):
        feats += 1
        if _first(props.get("landuse")) != "quarry":
            # Inner holes / member ways (farmyard, water, forest rings
            # pulled in for relation completeness) — not quarries.
            members += 1
            continue
        if gtype == "MultiPolygon" and coords:
            for poly in coords:
                if poly:
                    pts.extend(_ring_sample(poly[0]))
        elif gtype == "Polygon" and coords:
            pts.extend(_ring_sample(coords[0]))
        elif gtype == "Point" and coords:
            pts.append((coords[0], coords[1]))
        elif gtype == "LineString" and coords:
            if _is_closed(coords):
                twins += 1  # area twin of the same closed way, skip
            else:
                pts.extend(_densify_line([(c[0], c[1]) for c in coords]))
    return pts, {"features": feats, "kept": len(pts), "twins": twins,
                 "members": members}


def read_moto_points(snap):
    """37 track areas + 16 open centrelines + 3 nodes (twins/members out)."""
    pts = []
    feats = twins = members = 0
    for props, gtype, coords in _iter_features(
            snap, "derived-motorsport.geojson"):
        feats += 1
        if _first(props.get("sport")) not in MOTO_SPORTS:
            members += 1  # untagged way members (humps, start dots)
            continue
        if gtype == "MultiPolygon" and coords:
            for poly in coords:
                if poly:
                    pts.extend(_ring_sample(poly[0]))
        elif gtype == "Polygon" and coords:
            pts.extend(_ring_sample(coords[0]))
        elif gtype == "Point" and coords:
            pts.append((coords[0], coords[1]))
        elif gtype == "LineString" and coords:
            if _is_closed(coords):
                twins += 1
            else:
                pts.extend(_densify_line([(c[0], c[1]) for c in coords]))
    return pts, {"features": feats, "kept": len(pts), "twins": twins,
                 "members": members}


def read_range_points(snap):
    """4 military range polygons -> outer-ring samples (twins dropped)."""
    pts = []
    feats = twins = 0
    for props, gtype, coords in _iter_features(
            snap, "derived-range.geojson"):
        feats += 1
        if _first(props.get("military")) != "range":
            continue
        if gtype == "MultiPolygon" and coords:
            for poly in coords:
                if poly:
                    pts.extend(_ring_sample(poly[0]))
        elif gtype == "Polygon" and coords:
            pts.extend(_ring_sample(coords[0]))
        elif gtype == "Point" and coords:
            pts.append((coords[0], coords[1]))
        elif gtype == "LineString" and coords:
            if _is_closed(coords):
                twins += 1
            else:
                pts.extend(_densify_line([(c[0], c[1]) for c in coords]))
    return pts, {"features": feats, "kept": len(pts), "twins": twins}


#: Reader registry: class -> (derived file, reader). Order is stable for
#: logging and for the deterministic overlay union in the HOOK below.
EXTRA_READERS = (
    ("wind", read_wind_points),
    ("quarry", read_quarry_points),
    ("moto", read_moto_points),
    ("range", read_range_points),
)


def lowspec_extra_points(snap):
    """{class: [(lon, lat)]} for the lowspec hook + per-class stats."""
    out, stats = {}, {}
    for name, reader in EXTRA_READERS:
        pts, st = reader(snap)
        out[name] = pts
        stats[name] = st
    return out, stats
