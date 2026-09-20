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

#: Pole bookkeeping written by bin/pole-sync.sh + bin/pole-guard.sh +
#: bin/wrap-run.sh (issue #806). Absent in the repo checkout (CI, dev) —
#: every reader below treats missing files as "unknown", never as data.
STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state")

#: Serve-parity freshness TTL per dataset, seconds (issue #806). Pinned
#: mirrors: datex values == DATEX_TTL_S in apps/web/lib/layers_datex.ts,
#: outage/reliability == OUTAGE_TTL_S/OUTAGE_RELIABILITY_TTL_S in
#: apps/web/lib/layers_p4_outage.ts, sheds/incidents == SHED_TTL_S /
#: INCIDENTS_TTL_S. The rest derive from the pole cron cadence at ~2x
#: the interval (delay builds hourly, fixit/medre daily, mobile weekly,
#: poi monthly, viirs yearly + margin). skis is seasonal with no cron
#: (docs/p4_skis.md) and has no TTL — it is never stale-flagged.
DATASET_TTL_S = {
    "delay": 2 * 3600,
    "fixit": 2 * 86400,
    "medre": 2 * 86400,
    "poi": 60 * 86400,
    "mobile": 14 * 86400,
    "datex-restrictions": 24 * 3600,
    "datex-srti": 6 * 3600,
    "datex-weather": 1 * 3600,
    "datex-counters": 1 * 3600,
    "datex-cameras": 1 * 3600,
    "datex-truckpark": 30 * 86400,
    "skis": None,
    "viirs": 400 * 86400,
    "outage": 300,
    "outage-reliability": 86400,
    "sheds": 7 * 86400,
    "incidents": 6 * 3600,
}

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
    # OUTAGE-RELIABILITY-HOOK (#780): 28-day observed-reliability
    # table built from the rolling observation log by the same 5-min
    # wrapper (honest 503 until the first build; freshness enforced
    # by the map route, not this registry).
    "outage-reliability": "outage/reliability.json",
    # TOMTOM-HOOK (#782): weekly commute-shed table (polygons +
    # counts, 7-day TTL) + 6-hourly incident table (incidents +
    # fetched_at + counts, 6-hour TTL), both keyed pulls served from
    # the built tables (honest 503s until the first keyed builds;
    # freshness enforced by the map routes, not this registry).
    "sheds": "tomtom-sheds/table.json",
    "incidents": "tomtom-incidents/table.json",
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


def _read_state_text(name: str) -> "str | None":
    """One-line state file, stripped — None when absent (repo/CI)."""
    try:
        with open(os.path.join(STATE_DIR, name), encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def _deployed() -> dict:
    """Deployed code identity written by bin/pole-sync.sh (issue #806)."""
    return {
        "deployed_sha": _read_state_text("deployed-sha.txt"),
        "deployed_at": _read_state_text("deployed-at.txt"),
    }


def _guard_restarts(limit: int = 20) -> list:
    """Recent unexpected API deaths recorded by bin/pole-guard.sh."""
    path = os.path.join(STATE_DIR, "guard-restarts.jsonl")
    try:
        with open(path, encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
    except OSError:
        return []
    out = []
    for ln in lines[-limit:]:
        try:
            out.append(json.loads(ln))
        except ValueError:
            continue
    return out


def _wrapper_status() -> dict:
    """Last exit per cron job recorded by bin/wrap-run.sh."""
    status_dir = os.path.join(STATE_DIR, "wrapper-status")
    try:
        names = sorted(os.listdir(status_dir))
    except OSError:
        return {}
    out = {}
    for fn in names:
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(status_dir, fn),
                      encoding="utf-8") as f:
                body = json.load(f)
        except (OSError, ValueError):
            continue
        if isinstance(body, dict) and "rc" in body:
            out[fn[: -len(".json")]] = body
    return out


def _sync_status() -> "dict | None":
    """Last auto-sync result written by bin/pole-sync.sh."""
    path = os.path.join(STATE_DIR, "sync-status.json")
    try:
        with open(path, encoding="utf-8") as f:
            body = json.load(f)
    except (OSError, ValueError):
        return None
    return body if isinstance(body, dict) else None


def _dataset_freshness(now: datetime.datetime) -> list:
    """Per-dataset age vs TTL for the watcher (issue #806)."""
    rows = []
    for name, rel in DATASETS.items():
        info = _info(name, rel)
        ttl = DATASET_TTL_S.get(name)
        age_s = None
        if info["ready"]:
            try:
                built = datetime.datetime.fromisoformat(info["built_at"])
                age_s = max(0.0, (now - built).total_seconds())
            except (ValueError, KeyError):
                age_s = None
        rows.append({
            "name": name,
            "ready": info["ready"],
            "built_at": info.get("built_at"),
            "age_s": age_s,
            "ttl_s": ttl,
            "stale": bool(info["ready"] and ttl is not None
                          and age_s is not None and age_s > ttl),
        })
    return rows


@app.get("/health")
def health() -> dict:
    body = {
        "ok": True,
        "datasets": {n: _info(n, r)["ready"] for n, r in DATASETS.items()},
    }
    body.update(_deployed())
    return body


@app.get("/v1/errors")
def errors() -> dict:
    """Machine-readable failure evidence for the Mac-side watcher.

    Read-only roll-up of Pi-local bookkeeping (issue #806): unexpected
    API deaths, last cron-wrapper exits, last auto-sync result, and
    per-dataset age-vs-TTL. Missing state (fresh pole, repo checkout)
    yields empty lists / nulls — never faked data.
    """
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    body = _deployed()
    body.update({
        "guard_restarts": _guard_restarts(),
        "wrappers": _wrapper_status(),
        "sync": _sync_status(),
        "datasets": _dataset_freshness(now),
    })
    return body


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
