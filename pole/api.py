"""hf-pole read API: serve latest built harvest tables over the LAN.

Read-only. Every dataset is a file under built/ written by the cron
harvesters; this API adds freshness headers and honest 503s (never faked
data). UI / snapshot builder fetch from here instead of polling sources.

Run on the pole (see ~/hf-pole/README.md):
    ~/hf-pole/venv/bin/python -m uvicorn api:app --app-dir ~/hf-pole \
        --host 0.0.0.0 --port 8001
"""

import datetime
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
}

app = FastAPI(title="hf-pole")


def _info(name: str, rel: str) -> dict:
    path = os.path.join(BUILT_DIR, rel)
    if not os.path.isfile(path):
        return {"name": name, "ready": False, "path": rel}
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
