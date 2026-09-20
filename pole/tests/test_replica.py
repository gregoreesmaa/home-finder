"""Replica drift test (issue #767): pole/ rebuilds the Pi from repo sources.

Hermetic: reads repo files only, no network, no Pi.
"""

import os
import re

POLE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BIN_DIR = os.path.join(POLE_DIR, "bin")
REPO_ROOT = os.path.join(POLE_DIR, "..")
BUILD_DIR = os.path.join(REPO_ROOT, "scripts", "build")
SCORING_DIR = os.path.join(REPO_ROOT, "services", "scoring")

BATCH_RE = re.compile(r"batch_[a-z0-9_]+")
DIMS_RE = re.compile(r"dims_[a-z0-9_]+")


def _wrappers():
    out = {}
    for fn in sorted(os.listdir(BIN_DIR)):
        if fn.endswith(".sh"):
            with open(os.path.join(BIN_DIR, fn), encoding="utf-8") as f:
                out[fn] = f.read()
    return out


def test_wrappers_reference_existing_harvesters():
    missing = []
    for fn, body in _wrappers().items():
        for mod in sorted(set(BATCH_RE.findall(body))):
            if not os.path.isfile(os.path.join(BUILD_DIR, mod + ".py")):
                missing.append("%s -> %s.py" % (fn, mod))
    assert not missing, "wrappers reference missing harvesters: %s" % missing


def test_wrappers_reference_existing_dims():
    bodies = "\n".join(_wrappers().values())
    with open(os.path.join(POLE_DIR, "bootstrap.sh"),
              encoding="utf-8") as f:
        bodies += "\n" + f.read()
    missing = []
    for mod in sorted(set(DIMS_RE.findall(bodies))):
        if not os.path.isfile(os.path.join(SCORING_DIR, mod + ".py")):
            missing.append(mod + ".py")
    assert not missing, "missing dims modules: %s" % missing


def test_crontab_names_existing_wrappers():
    with open(os.path.join(POLE_DIR, "crontab.txt"),
              encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip() and "hf-pole/bin/" in ln]
    assert len(lines) >= 20, "crontab lost lines (%d)" % len(lines)
    missing = [ln for ln in lines
               if not os.path.isfile(os.path.join(
                   BIN_DIR, ln.split("hf-pole/bin/")[1].split()[0]))]
    assert not missing, "crontab names missing wrappers: %s" % missing


def test_crontab_wraps_wrappers_with_exit_recorder():
    # Issue #806: every cron run- wrapper goes through wrap-run.sh so
    # its exit lands in state/wrapper-status/ for GET /v1/errors.
    with open(os.path.join(POLE_DIR, "crontab.txt"),
              encoding="utf-8") as f:
        lines = [ln.strip() for ln in f
                 if ln.strip() and not ln.strip().startswith("#")]
    run_lines = [ln for ln in lines if "run-" in ln and ".sh" in ln]
    assert len(run_lines) == 17, "wrapped wrapper lines changed: %d" % len(
        run_lines)
    for ln in run_lines:
        m = re.search(r"wrap-run\.sh (\S+) .*hf-pole/bin/(run-\S+\.sh)",
                      ln)
        assert m, "wrapper line bypasses wrap-run.sh: %s" % ln
        job, wrapper = m.group(1), m.group(2)
        assert os.path.isfile(os.path.join(BIN_DIR, wrapper)), wrapper
        assert job == wrapper[len("run-"): -len(".sh")], \
            "job name %s does not match %s" % (job, wrapper)
    # run-skis.sh is the seasonal hand-run exception (no cron, docs).
    assert os.path.isfile(os.path.join(BIN_DIR, "wrap-run.sh"))
    assert os.path.isfile(os.path.join(BIN_DIR, "run-skis.sh"))


def test_crontab_has_hourly_sync():
    # Issue #806: pole-sync.sh lands green-main without operator action.
    with open(os.path.join(POLE_DIR, "crontab.txt"),
              encoding="utf-8") as f:
        body = f.read()
    assert re.search(r"^\S+ \* \* \* \* \$HOME/hf-pole/bin/pole-sync\.sh",
                     body, re.M) or \
        "hf-pole/bin/pole-sync.sh" in body, "hourly pole-sync line missing"
    assert os.path.isfile(os.path.join(BIN_DIR, "pole-sync.sh"))


def test_requirements_pins_api_runtime():
    with open(os.path.join(POLE_DIR, "requirements.txt"),
              encoding="utf-8") as f:
        reqs = f.read()
    assert "fastapi==" in reqs and "uvicorn==" in reqs


def test_manifest_names_existing_sources():
    # Issue #806: inventory single-sourced in pole/manifest.sh.
    with open(os.path.join(POLE_DIR, "manifest.sh"),
              encoding="utf-8") as f:
        body = f.read()
    harvesters = re.search(r'HARVESTERS="([^"]+)"', body).group(1).split()
    dims = re.search(r'DIMS="([^"]+)"', body).group(1).split()
    assert len(harvesters) == 21, "harvester manifest changed: %d" % len(
        harvesters)
    assert len(dims) == 12, "dims manifest changed: %d" % len(dims)
    missing = [
        m + ".py" for m in harvesters
        if not os.path.isfile(os.path.join(BUILD_DIR, m + ".py"))
    ] + [
        m + ".py" for m in dims
        if not os.path.isfile(os.path.join(SCORING_DIR, m + ".py"))
    ]
    assert not missing, "manifest names missing sources: %s" % missing


def test_bootstrap_and_sync_share_manifest():
    # Issue #806: setup and auto-sync deploy the same files — both
    # source pole/manifest.sh instead of carrying their own lists.
    for name in ("bootstrap.sh", "bin/pole-sync.sh"):
        with open(os.path.join(POLE_DIR, name), encoding="utf-8") as f:
            body = f.read()
        assert "manifest.sh" in body, "%s does not source manifest" % name
        assert "HARVESTERS=" not in body and "DIMS=" not in body, \
            "%s carries its own inventory" % name


def test_guard_records_restarts_for_errors_endpoint():
    # Issue #806: unexpected API deaths are machine-readable via
    # GET /v1/errors (guard-restarts.jsonl), not just a log line.
    with open(os.path.join(BIN_DIR, "pole-guard.sh"),
              encoding="utf-8") as f:
        body = f.read()
    assert "guard-restarts.jsonl" in body


def test_api_exposes_deployment_and_errors():
    # Issue #806: /health carries deployed_sha/at, /v1/errors carries
    # the watcher evidence (guard restarts, wrapper exits, sync, TTLs).
    with open(os.path.join(POLE_DIR, "api.py"), encoding="utf-8") as f:
        body = f.read()
    for token in ('"/health"', '"/v1/errors"', "deployed_sha",
                  "deployed_at", "guard_restarts", "DATASET_TTL_S"):
        assert token in body, "api.py missing %s" % token


def test_watcher_uses_existing_auth_only():
    # Issue #806: the Mac watcher files via the operator's `gh` auth —
    # no token env, no secret files. Allow-list the env it may read.
    watcher = os.path.join(REPO_ROOT, "scripts", "pole_watch.py")
    assert os.path.isfile(watcher), "scripts/pole_watch.py missing"
    with open(watcher, encoding="utf-8") as f:
        body = f.read()
    env_names = set(re.findall(r'os\.environ\.get\("([A-Z_0-9]+)"', body))
    assert env_names <= {"POLE_BASE_URL", "HF_POLE_WATCH",
                         "HF_POLE_WATCH_STATE"}, env_names
    assert "ghp_" not in body


def test_no_secrets_in_replica():
    bad = []
    for root, _, files in os.walk(POLE_DIR):
        if "tests" in root:
            continue
        for fn in files:
            if fn.endswith((".key", ".token")) or "state/" in root:
                bad.append(os.path.join(root, fn))
    assert not bad, "secrets in replica: %s" % bad
