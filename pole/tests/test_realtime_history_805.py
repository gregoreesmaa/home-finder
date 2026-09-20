"""Realtime history policy pins (issue #805).

Hermetic: imports harvester/dims modules for their TTL/quota
constants only (no pulls), reads wrapper/doc sources as text, and
executes wrapper failure/success paths against stub harvesters under
a fake HOME (no network, no keys, no Pi).

The #805 decision: DATEX x6 + TomTom x2 stay SHORT-TERM-CACHE
window tables (ToS re-check 2026-09-20, see
docs/realtime_history_805.md) — no observation logs for those
feeds, while the outage/delay history precedents stay intact.
"""

import importlib
import os
import subprocess
import sys

import pytest

POLE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BIN_DIR = os.path.join(POLE_DIR, "bin")
REPO_ROOT = os.path.join(POLE_DIR, "..")
BUILD_DIR = os.path.join(REPO_ROOT, "scripts", "build")
SCORING_DIR = os.path.join(REPO_ROOT, "services", "scoring")

# Module -> (ttl attr, expected ttl_s, quota attr, expected quota).
# Short-term-cache pins: the #805 no-store verdict REQUIRES these
# caps to stay short — a lengthened TTL here is a ToS breach, not a
# tuning change.
DATEX_NO_STORE = {
    "batch_datex_restrictions": ("TTL_S", 24 * 3600,
                                 "QUOTA_MAX_CALLS", 4),
    "batch_datex_srti": ("TTL_S", 6 * 3600, "QUOTA_MAX_CALLS", 32),
    "batch_datex_weather": ("TTL_S", 3600, "QUOTA_MAX_CALLS", 50),
    "batch_datex_counters": ("TTL_S", 3600, "QUOTA_MAX_CALLS", 50),
    "batch_datex_cameras": ("TTL_S", 3600, "QUOTA_MAX_CALLS", 50),
    "batch_datex_truckpark": ("TTL_S", 30 * 24 * 3600,
                              "QUOTA_MAX_CALLS", 4),
}

# TomTom windows keep their caps in the dims modules (imported by the
# harvesters): incidents 6 h / 2 calls, sheds 7 d / 20 calls.
TOMTOM_NO_STORE = {
    "dims_tomtom_incidents": ("INCIDENTS_TTL_S", 6 * 3600,
                              "INCIDENTS_MAX_CALLS", 2),
    "dims_tomtom_isochrones": ("SHED_TTL_S", 7 * 24 * 3600,
                               "SHED_MAX_CALLS", 20),
}

#: (wrapper, key file, harvester) for every #805 window-only feed.
NO_STORE_WRAPPERS = [
    ("run-datex-restrictions.sh", "datex.key",
     "batch_datex_restrictions.py"),
    ("run-datex-srti.sh", "datex.key", "batch_datex_srti.py"),
    ("run-datex-weather.sh", "datex.key", "batch_datex_weather.py"),
    ("run-datex-counters.sh", "datex.key", "batch_datex_counters.py"),
    ("run-datex-cameras.sh", "datex.key", "batch_datex_cameras.py"),
    ("run-datex-truckpark.sh", "datex.key", "batch_datex_truckpark.py"),
    ("run-tomtom-incidents.sh", "tomtom.key",
     "batch_tomtom_incidents.py"),
    ("run-tomtom-sheds.sh", "tomtom.key",
     "batch_tomtom_isochrones.py"),
]


def _read_wrapper(name):
    with open(os.path.join(BIN_DIR, name), encoding="utf-8") as f:
        return f.read()


@pytest.mark.parametrize("module,expected", sorted(DATEX_NO_STORE.items()))
def test_datex_harvesters_keep_short_term_caps(module, expected):
    if BUILD_DIR not in sys.path:
        sys.path.insert(0, BUILD_DIR)
    mod = importlib.import_module(module)
    ttl_attr, ttl, quota_attr, quota = expected
    assert getattr(mod, ttl_attr) == ttl, \
        "%s.%s changed (ToS short-term-cache pin)" % (module, ttl_attr)
    assert getattr(mod, quota_attr) == quota
    assert getattr(mod, ttl_attr) <= 30 * 24 * 3600, \
        "%s window exceeds no-store bound" % module


@pytest.mark.parametrize("module,expected",
                         sorted(TOMTOM_NO_STORE.items()))
def test_tomtom_windows_keep_short_term_caps(module, expected):
    if SCORING_DIR not in sys.path:
        sys.path.insert(0, SCORING_DIR)
    mod = importlib.import_module(module)
    ttl_attr, ttl, quota_attr, quota = expected
    assert getattr(mod, ttl_attr) == ttl, \
        "%s.%s changed (ToS short-term-cache pin)" % (module, ttl_attr)
    assert getattr(mod, quota_attr) == quota
    assert getattr(mod, ttl_attr) <= 30 * 24 * 3600, \
        "%s window exceeds no-store bound" % module


@pytest.mark.parametrize("wrapper, _key, _harv",
                         NO_STORE_WRAPPERS,
                         ids=[w[0] for w in NO_STORE_WRAPPERS])
def test_no_store_wrappers_keep_no_history_path(wrapper, _key, _harv):
    # A window-only wrapper must never grow an observation log: the
    # replace (tmp+mv) pattern is the whole contract.
    body = _read_wrapper(wrapper)
    assert "observations" not in body, \
        "%s gained a history path (ToS no-store)" % wrapper
    assert "--build-reliability" not in body
    assert 'mv "$OUT.tmp" "$OUT"' in body, \
        "%s lost the atomic window-replace pattern" % wrapper


def test_history_precedents_intact():
    # #805 converts nothing away: outage append-only log + reliability
    # build (#780/#801) and the delay gather-only rule stay as-is.
    outage = _read_wrapper("run-outage.sh")
    assert "cache/outage/observations.jsonl" in outage
    assert "--build-reliability" in outage
    with open(os.path.join(BUILD_DIR, "batch_outage.py"),
              encoding="utf-8") as f:
        assert "--build-reliability" in f.read()
    delay_build = _read_wrapper("run-delay-build.sh")
    assert "NEVER delete" in delay_build
    prune = _read_wrapper("run-prune.sh")
    assert "NEVER deletes gathered data" in prune


def _fake_pole(tmp_path, key_name, harvester_name, stub_body):
    """Materialize a fake $HOME/hf-pole with a stub harvester."""
    pole = tmp_path / "hf-pole"
    (pole / "state").mkdir(parents=True)
    (pole / "state" / key_name).write_text("test-only fake key",
                                           encoding="utf-8")
    (pole / "harvesters").mkdir(parents=True)
    (pole / "harvesters" / harvester_name).write_text(
        stub_body, encoding="utf-8")
    (pole / "cache").mkdir(parents=True)
    (pole / "built").mkdir(parents=True)
    env = dict(os.environ, HOME=str(tmp_path))
    return pole, env


FAIL_STUB = "import sys; sys.stderr.write('stub pull failed'); sys.exit(1)\n"
OK_STUB = "print('{\"counts\": {\"total\": 0}, \"stub\": true}')\n"

FAIL_CASES = [t for t in NO_STORE_WRAPPERS
              if t[0] in ("run-datex-restrictions.sh",
                          "run-datex-srti.sh",
                          "run-tomtom-incidents.sh",
                          "run-tomtom-sheds.sh")]


@pytest.mark.parametrize("wrapper,key,harvester", FAIL_CASES,
                         ids=[w[0] for w in FAIL_CASES])
def test_failed_wrapper_run_leaves_built_table_untouched(
        tmp_path, wrapper, key, harvester):
    # Outage-wrapper pattern for window tables: a failed pull must
    # leave the previous table in place (never writes failure as
    # data) and must not litter tmp files.
    pole, env = _fake_pole(tmp_path, key, harvester, FAIL_STUB)
    out_rel = {
        "run-datex-restrictions.sh": "built/datex-restrictions/table.json",
        "run-datex-srti.sh": "built/datex-srti/table.json",
        "run-tomtom-incidents.sh": "built/tomtom-incidents/table.json",
        "run-tomtom-sheds.sh": "built/tomtom-sheds/table.json",
    }[wrapper]
    out = pole / out_rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('{"previous": true}', encoding="utf-8")
    proc = subprocess.run(["sh", os.path.join(BIN_DIR, wrapper)],
                          env=env, capture_output=True, text=True,
                          timeout=60)
    assert proc.returncode != 0, \
        "%s swallowed a harvester failure" % wrapper
    assert out.read_text(encoding="utf-8") == '{"previous": true}', \
        "%s clobbered the window table on failure" % wrapper
    assert not os.path.exists(str(out) + ".tmp"), \
        "%s left a tmp file behind" % wrapper


def test_successful_wrapper_run_replaces_window_table(tmp_path):
    # The flip side: a healthy pull replaces the window table (the
    # documented overwrite for no-store feeds — history lives
    # nowhere, the window is the contract).
    pole, env = _fake_pole(tmp_path, "datex.key",
                           "batch_datex_restrictions.py", OK_STUB)
    out = pole / "built" / "datex-restrictions" / "table.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('{"previous": true}', encoding="utf-8")
    proc = subprocess.run(
        ["sh", os.path.join(BIN_DIR, "run-datex-restrictions.sh")],
        env=env, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    body = out.read_text(encoding="utf-8")
    assert '"stub": true' in body
    assert "previous" not in body
