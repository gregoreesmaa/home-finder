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
    assert len(lines) >= 17, "crontab lost lines (%d)" % len(lines)
    missing = [ln for ln in lines
               if not os.path.isfile(os.path.join(
                   BIN_DIR, ln.split("hf-pole/bin/")[1].split()[0]))]
    assert not missing, "crontab names missing wrappers: %s" % missing


def test_requirements_pins_api_runtime():
    with open(os.path.join(POLE_DIR, "requirements.txt"),
              encoding="utf-8") as f:
        reqs = f.read()
    assert "fastapi==" in reqs and "uvicorn==" in reqs


def test_bootstrap_manifest_names_existing_sources():
    with open(os.path.join(POLE_DIR, "bootstrap.sh"),
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


def test_no_secrets_in_replica():
    bad = []
    for root, _, files in os.walk(POLE_DIR):
        if "tests" in root:
            continue
        for fn in files:
            if fn.endswith((".key", ".token")) or "state/" in root:
                bad.append(os.path.join(root, fn))
    assert not bad, "secrets in replica: %s" % bad
