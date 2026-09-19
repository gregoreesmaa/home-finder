"""hf-pole read API: serve latest built harvest tables over the LAN.

Read-only. Every dataset is a file under built/ written by the cron
harvesters; this API adds freshness headers and honest 503s (never faked
data). UI / snapshot builder fetch from here instead of polling sources.

Run on the pole (see ~/hf-pole/README.md):
    ~/hf-pole/venv/bin/python -m uvicorn api:app --app-dir ~/hf-pole \
        --host 0.0.0.0 --port 8001
"""

import datetime
import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

BUILT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "built")

DATASETS = {
    "delay": "delay/delay-corridors.json",
    "fixit": "fixit/fixit-points.json",
    "medre": "medre/medre-points.json",
    "poi": "poi/poi-points.json",
    "mobile": "osm/derived-mobile.json",
    "datex-restrictions": "datex-restrictions/table.json",
    "datex-srti": "datex-srti/table.json",
    "datex-weather": "datex-weather/table.json",
    "datex-counters": "datex-counters/table.json",
    "datex-cameras": "datex-cameras/table.json",
    "datex-truckpark": "datex-truckpark/table.json",
    # SKIS-HOOK (#692): seasonal groomed ski tracks (honest 503
    # off-season until the first in-season operator-verified drop).
    "skis": "skis/table.json",
    # VIIRS-HOOK (#719): annual brightness-proxy grid (honest 503
    # until the first keyless GIBS build).
    "viirs": "viirs/grid.json",
    # OUTAGE-HOOK (#729): 5-min live-outage sidecar (honest 503 until
    # the first operator pull; stale sidecars never serve — the map
    # route enforces the TTL, not this registry).
    "outage": "outage/table.json",
}

app = FastAPI(title="hf-pole")

#: Point-table datasets where an empty payload is a linkage report, not
#: servable data (issue #765: medre Step-1 writes points [] with
#: linkage 0 until the Step-2 ADS join fills it). Listed datasets are
#: not-ready until the named key holds a non-empty list. Unlisted
#: datasets keep file-existence readiness (honest-empty serves, e.g.
#: outage with zero live rows, fixit paaste precedent).
NONEMPTY_JSON_KEYS = {"medre": "points"}


def _has_payload(name: str, path: str) -> bool:
    """True unless the dataset needs a non-empty JSON key it lacks."""
    key = NONEMPTY_JSON_KEYS.get(name)
    if key is None:
        return True
    try:
        with open(path, encoding="utf-8") as f:
            body = json.load(f)
    except (OSError, ValueError):
        return False
    return isinstance(body.get(key), list) and len(body[key]) > 0


def _info(name: str, rel: str) -> dict:
    path = os.path.join(BUILT_DIR, rel)
    if not os.path.isfile(path):
        return {"name": name, "ready": False, "path": rel}
    if not _has_payload(name, path):
        return {"name": name, "ready": False, "path": rel,
                "reason": "empty payload, harvester pending"}
    st = os.stat(path)
    return {
        "name": name,
        "ready": True,
        "path": rel,
        "bytes": st.st_size,
        "built_at": datetime.datetime.fromtimestamp(
            st.st_mtime, tz=datetime.timezone.utc
        ).isoformat(),
    }


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "datasets": {n: _info(n, r)["ready"] for n, r in DATASETS.items()},
    }


@app.get("/v1/datasets")
def datasets() -> dict:
    return {"datasets": [_info(n, r) for n, r in DATASETS.items()]}


@app.get("/v1/{name}")
def dataset(name: str):
    if name not in DATASETS:
        raise HTTPException(status_code=404, detail="unknown dataset")
    info = _info(name, DATASETS[name])
    if not info["ready"]:
        raise HTTPException(
            status_code=503, detail="not built yet, harvester pending"
        )
    return FileResponse(
        os.path.join(BUILT_DIR, DATASETS[name]),
        media_type="application/json",
        headers={"X-Pole-Built-At": info["built_at"]},
    )
