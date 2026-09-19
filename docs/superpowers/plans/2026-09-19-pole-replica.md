# Pole replica (issue #767) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `pole/` in the repo fully rebuilds a fresh harvest Pi from repo sources plus operator keys.

**Architecture:** `pole/bin/` holds verbatim wrapper copies (no repo counterpart exists); `harvesters/`+`dims/` are NOT duplicated — `pole/bootstrap.sh` syncs them from `scripts/build/` + `services/scoring/` by glob, and `pole/tests/test_replica.py` fails if any wrapper-referenced module is missing from the repo. `pole/crontab.txt` + `pole/requirements.txt` pin cadence and runtime.

**Tech Stack:** sh (bootstrap, wrappers), pytest (drift test), cron, python venv.

**Spec:** issue #767 (bin/ 17 wrappers + guard/start; harvesters 21 files; dims 12 files; api.py already in repo; secrets/data/venv excluded).

## Global Constraints

- One issue per worktree/PR (AGENTS.md §3) — this plan runs in `.worktrees/767-pole-replica`, branch `767-pole-replica`.
- Hermetic tests: no network, no Pi in unit runs.
- No secrets in the repo, ever — bootstrap prints a key checklist instead of creating key files.
- Pi paths live ONLY in `pole/bin/` + `pole/bootstrap.sh` via `$HOME`/`$POLE` (never hardcoded `/home/gregor`).
- Small diffs: no harvester/dims logic changes in this PR.

---

## File structure

- Copy verbatim from Pi (`/tmp/pole-ref/bin/`, fetched 2026-09-19): `pole/bin/pole-guard.sh`, `pole/bin/pole-start.sh`, `pole/bin/run-datex-cameras.sh`, `pole/bin/run-datex-counters.sh`, `pole/bin/run-datex-restrictions.sh`, `pole/bin/run-datex-srti.sh`, `pole/bin/run-datex-truckpark.sh`, `pole/bin/run-datex-weather.sh`, `pole/bin/run-delay-build.sh`, `pole/bin/run-delay-pull.sh`, `pole/bin/run-fixit.sh`, `pole/bin/run-medre.sh`, `pole/bin/run-mobile.sh`, `pole/bin/run-outage.sh`, `pole/bin/run-poi.sh`, `pole/bin/run-prune.sh`, `pole/bin/run-viirs.sh` (17 files, no `.bak` files).
- Create: `pole/crontab.txt` (17 lines, fetched verbatim — starts `@reboot $HOME/hf-pole/bin/pole-start.sh`, ends `23 4 15 1 * $HOME/hf-pole/bin/run-viirs.sh >>$HOME/hf-pole/logs/viirs.log 2>&1`).
- Create: `pole/requirements.txt` (19 pins from Pi `pip freeze`: annotated-doc==0.0.5, annotated-types==0.8.0, anyio==4.15.1, click==8.5.0, fastapi==0.141.1, h11==0.16.0, httptools==0.8.0, idna==3.20, pydantic==2.13.5, pydantic_core==2.46.5, python-dotenv==1.2.3, PyYAML==6.0.3, starlette==1.6.0, typing-inspection==0.4.4, typing_extensions==4.16.0, uvicorn==0.53.0, uvloop==0.22.1, watchfiles==1.2.0, websockets==17.1).
- Create: `pole/tests/test_replica.py` (drift test — full code in Task 2).
- Create: `pole/bootstrap.sh` (idempotent Pi setup — full code in Task 3).
- Create: `pole/README.md` (operator setup guide — sections in Task 4).
- Modify: none.

---

### Task 1: Drift test first (TDD)

**Files:**
- Create: `pole/tests/test_replica.py`
- Test: `pole/tests/test_replica.py`

**Interfaces:**
- Consumes: `pole/bin/*.sh`, `pole/crontab.txt`, `pole/requirements.txt`, `scripts/build/batch_*.py`, `services/scoring/dims_*.py` (all by path, read-only).
- Produces: 6 green tests proving the replica is complete and secret-free.

- [ ] **Step 1: Write the test**

```python
"""Replica drift test (issue #767): pole/ rebuilds the Pi from repo sources.

Hermetic: reads repo files only, no network, no Pi.
"""

import os
import re

import pytest

POLE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BIN_DIR = os.path.join(POLE_DIR, "bin")
REPO_ROOT = os.path.join(POLE_DIR, "..", "..")
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


def test_no_secrets_in_replica():
    bad = []
    for root, _, files in os.walk(POLE_DIR):
        if "tests" in root:
            continue
        for fn in files:
            if fn.endswith((".key", ".token")) or "state/" in root:
                bad.append(os.path.join(root, fn))
    assert not bad, "secrets in replica: %s" % bad
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest pole/tests/test_replica.py -q`
Expected: FAIL (collection error — `pole/bin/` does not exist yet).

- [ ] **Step 3: Copy the replica files (Task 2 below), then re-run**

Run: `python3 -m pytest pole/tests/test_replica.py -q`
Expected: 6 PASS.

### Task 2: Copy bin/, crontab.txt, requirements.txt

**Files:**
- Create: `pole/bin/*.sh` (17 files), `pole/crontab.txt`, `pole/requirements.txt`

**Interfaces:**
- Consumes: `/tmp/pole-ref/bin/*.sh`, `/tmp/pole-ref/crontab.txt` (fetched verbatim 2026-09-19, `.bak` files excluded by the fetch glob).
- Produces: byte-faithful replica files the drift test checks.

- [ ] **Step 1: Copy wrappers**

```bash
mkdir -p pole/bin
cp /tmp/pole-ref/bin/*.sh pole/bin/
ls pole/bin | wc -l   # expect 17
```

- [ ] **Step 2: Write crontab.txt** — verbatim content of `/tmp/pole-ref/crontab.txt` (17 lines, `$HOME`-based, no host-specific paths).

- [ ] **Step 3: Write requirements.txt** — the 19 pins listed in this plan's File structure section.

- [ ] **Step 4: Fidelity check** — every `pole/bin/*.sh` byte-identical to the Pi source:

```bash
for f in pole/bin/*.sh; do
  diff -q "$f" "/tmp/pole-ref/bin/$(basename $f)" || echo "DRIFT: $f"
done
```

- [ ] **Step 5: Run drift test green**

Run: `python3 -m pytest pole/tests/test_api.py pole/tests/test_replica.py -q`
Expected: all PASS (8 existing + 6 new).

### Task 3: bootstrap.sh (idempotent new-Pi setup)

**Files:**
- Create: `pole/bootstrap.sh`

**Interfaces:**
- Consumes: repo checkout path `$1` (default `$HOME/home-finder`); writes only under `$HOME/hf-pole`.
- Produces: executable bootstrap; `--dry-run` prints actions without changing anything.

- [ ] **Step 1: Write the script**

```sh
#!/bin/sh
# pole/bootstrap.sh — materialize ~/hf-pole on a fresh Pi from this repo.
# Idempotent: safe to re-run (re-syncs harvesters/dims/api, keeps cache).
# Usage: ./pole/bootstrap.sh [REPO_DIR] [--dry-run]
# Operator keys (state/datex.key, state/tomtom.key, state/opencellid.token)
# and static vintages (state/*.zip) are NEVER in the repo — install by hand
# (scp from the previous pole), then enable the cron lines that need them.
set -eu
REPO="${1:-$HOME/home-finder}"
DRY=""
[ "${2:-}" = "--dry-run" ] && DRY=echo
POLE="$HOME/hf-pole"
run() { if [ -n "$DRY" ]; then echo "+ $*"; else "$@"; fi }
run mkdir -p "$POLE"/bin "$POLE"/harvesters "$POLE"/dims \
  "$POLE"/cache "$POLE"/built "$POLE"/state "$POLE"/logs
run python3 -m venv "$POLE/venv"
run "$POLE/venv/bin/pip" install -q -r "$REPO/pole/requirements.txt"
for f in "$REPO"/scripts/build/batch_*.py; do
  case "$f" in *test_*) continue;; esac
  run cp "$f" "$POLE/harvesters/"
done
run cp "$REPO"/services/scoring/dims_*.py "$POLE/dims/"
run cp "$REPO/pole/api.py" "$POLE/api.py"
run cp "$REPO"/pole/bin/*.sh "$POLE/bin/"
run chmod +x "$POLE"/bin/*.sh
run crontab "$REPO/pole/crontab.txt"
if [ -z "$DRY" ]; then cat <<'EOF'
TODO operator (by hand, never committed):
  1. scp state/datex.key state/tomtom.key state/opencellid.token state/*.zip from the previous pole into ~/hf-pole/state/
  2. crontab -l (verify 17 lines); sudo reboot (verify API + tunnel after boot)
  3. curl 127.0.0.1:8001/health (expect honest 503s until first pulls land)
EOF
fi
```

- [ ] **Step 2: Syntax + dry-run proof**

Run: `bash -n pole/bootstrap.sh && sh pole/bootstrap.sh /tmp/fake-repo --dry-run | head -8`
Expected: no syntax errors; `+ mkdir ...`, `+ python3 -m venv ...` lines printed, nothing created.

### Task 4: pole/README.md operator guide

**Files:**
- Create: `pole/README.md`

**Interfaces:**
- Consumes: Pi `~/hf-pole/README.md` layout/cadence facts (verified 2026-09-19).
- Produces: setup guide with sections: Layout (repo-holds vs pole-holds table), Fresh-Pi setup (clone, bootstrap, keys, reboot, health check), Re-sync after repo changes (which dirs to re-copy), Adding a dataset (wrapper + cron + api.py + drift test), Secrets (never committed), Tunnel note (Mac LaunchAgent, POLE_BASE_URL).

- [ ] **Step 1: Write the guide** (all section content above, no TBDs).
- [ ] **Step 2: Commit everything**

```bash
git add pole/ docs/superpowers/plans/2026-09-19-pole-replica.md
git commit -m "Pole replica in repo: bin + crontab + bootstrap + drift test (Closes #767)"
```

### Task 5: Verify, PR, review, merge, pole touch-up

- [ ] **Step 1: Full verification**

```bash
python3 -m pytest pole/tests/ -q                      # 14 pass
python3 -m pytest services/scoring/tests -q            # no regressions
npm run lint                                           # clean
grep -rni "key\|token\|secret\|passwd" pole/bin pole/*.sh pole/*.txt pole/README.md | grep -vi "keyed\|keyboard" || echo NO-SECRETS
bash -n pole/bin/*.sh pole/bootstrap.sh && echo SYNTAX-OK
```

- [ ] **Step 2: Push + open PR** (`Closes #767`, DoD evidence pasted).
- [ ] **Step 3: Fresh no-context review** (subagent, must re-run drift test from clean checkout) → APPROVE.
- [ ] **Step 4: CI green → squash-merge → delete worktree.**
- [ ] **Step 5: Pole touch-up (ops, no repo change):** fix stale Pi README line `hourly run-delay-build.sh (+7 d raw prune)` → `(never pruned; gather-only)` via sed; verify `built/` sizes sane.

---

## Self-review

1. **Spec coverage:** bin/ copies (Task 2) ✓; harvesters/dims via bootstrap glob + drift test instead of duplicates (Tasks 2–3) ✓; crontab.txt (Task 2) ✓; requirements.txt (Task 2) ✓; bootstrap.sh (Task 3) ✓; README (Task 4) ✓; no-secrets test (Task 1, `test_no_secrets_in_replica`) ✓; DoD evidence in PR (Task 5) ✓.
2. **Placeholder scan:** bootstrap heredoc prints concrete operator steps; README sections enumerated with content sources; no TBD/TODO-in-code (the operator TODO is printed output, intentional).
3. **Type consistency:** test reads `pole/bin/`, `pole/crontab.txt`, `pole/requirements.txt`, `pole/bootstrap.sh` — all created in Tasks 2–3 before the green run in Task 2 Step 5 / Task 5. `test_wrappers_reference_existing_dims` reads `bootstrap.sh`, so Task 3 must land before the final green run — ordering noted.

