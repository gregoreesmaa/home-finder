"""Live pole presence sweep (issue #802): every servable pole dataset is
present with data — 200-with-data or honest-503-with-reason.

EXPLICITLY-FLAGGED INTEGRATION, NEVER UNIT (AGENTS.md section 7
hermetic default): skipped unless HF_PRESENCE_SWEEP=1, so plain
``python3 -m pytest pole/tests/ -q`` stays hermetic. Run against the
harvest pole (Pi or the compose tunnel)::

    HF_PRESENCE_SWEEP=1 POLE_BASE_URL=http://127.0.0.1:18001 \
        python3 -m pytest pole/tests/test_presence_sweep.py -q -s

Contract per dataset (GET /v1/<name>, names enumerated live from
api.DATASETS so a new dataset joins the sweep automatically):
- 200 + parseable JSON + X-Pole-Built-At header -> data (serving).
- 503 with a "not built yet" detail -> honest-empty-with-reason
  (harvester pending, never faked data).
- anything else (500/404/other, 200 without freshness, unparseable
  body, health/readiness mismatch) FAILS the sweep.

Fixtures only (AGENTS.md section 5): this file reads live state, it
writes nothing and commits nothing.
"""

import json
import os
import urllib.request
import urllib.error

import pytest

import sys as _sys

_sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import api  # noqa: E402

RUN = os.environ.get("HF_PRESENCE_SWEEP") == "1"
BASE = os.environ.get("POLE_BASE_URL", "http://127.0.0.1:18001")

needs_sweep = pytest.mark.skipif(
    not RUN, reason="live presence sweep: set HF_PRESENCE_SWEEP=1 (never unit)")


def _get(path):
    url = BASE.rstrip("/") + path
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            return res.status, dict(res.headers), res.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()
    except Exception as e:  # transport down: pole unreachable, not data
        return -1, {}, str(e).encode("utf-8")


@needs_sweep
def test_every_dataset_serves_or_honestly_waits():
    names = sorted(api.DATASETS)
    assert names, "pole DATASETS registry is empty"
    rows = []
    failures = []
    for name in names:
        status, headers, raw = _get("/v1/" + name)
        built = headers.get("X-Pole-Built-At") or headers.get("x-pole-built-at")
        if status == 200:
            try:
                json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                failures.append("%s: 200 with unparseable body" % name)
                rows.append((name, status, "FAIL", "unparseable body"))
                continue
            if not built:
                failures.append("%s: 200 without X-Pole-Built-At freshness" % name)
                rows.append((name, status, "FAIL", "no freshness header"))
                continue
            rows.append((name, status, "data", "built %s" % built))
        elif status == 503:
            try:
                detail = json.loads(raw.decode("utf-8")).get("detail", "")
            except (ValueError, UnicodeDecodeError):
                detail = ""
            if "not built yet" not in str(detail):
                failures.append("%s: 503 without honest reason (%r)" % (name, detail))
                rows.append((name, status, "FAIL", "reasonless 503"))
                continue
            rows.append((name, status, "honest-empty", str(detail)[:80]))
        else:
            failures.append("%s: HTTP %s (demo-by-outage / 500-by-config)" % (name, status))
            rows.append((name, status, "FAIL", raw[:120].decode("utf-8", "replace")))

    print("\npole presence sweep vs %s (%d datasets):" % (BASE, len(names)))
    print("dataset | status | verdict | detail")
    for name, status, verdict, detail in rows:
        print("%s | %s | %s | %s" % (name, status, verdict, detail))
    data = sum(1 for r in rows if r[2] == "data")
    empty = sum(1 for r in rows if r[2] == "honest-empty")
    print("summary: %d data, %d honest-empty, %d FAIL" % (data, empty, len(failures)))
    assert not failures, "presence sweep failures: %s" % failures


@needs_sweep
def test_health_matches_serving_state():
    status, _, raw = _get("/health")
    assert status == 200, "health unreachable: HTTP %s" % status
    body = json.loads(raw.decode("utf-8"))
    assert body.get("ok") is True
    for name in sorted(api.DATASETS):
        dstatus, _, _ = _get("/v1/" + name)
        ready = body["datasets"][name]
        if dstatus == 200:
            assert ready is True, "%s serves 200 but health says not-ready" % name
        elif dstatus == 503:
            assert ready is False, "%s honest-503 but health says ready" % name
