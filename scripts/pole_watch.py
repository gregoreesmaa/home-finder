#!/usr/bin/env python3
"""Mac-side harvest-pole watcher (issue #806).

Polls the pole read API through the existing ssh tunnel (POLE_BASE_URL,
default http://127.0.0.1:18001) and turns pole problems into GitHub
issues — rate-limited, one open issue per failure mode, auto-closed on
recovery. Pole-side filing was rejected: the token stays on the Mac and
uses the operator's existing `gh` auth, so no new secrets exist
anywhere (pole README documents zero install beyond `gh auth login`).

Failure classes (keys in brackets):
  [sync-behind]        deployed_sha != green-main (pole-release tag when
                       it exists, else origin/main) AND deployed_at older
                       than STALE_AFTER_S (sync runs hourly: <=1 h lag
                       is normal, >2 h is reportable).
  [sync-failing]       last pole-sync.sh run exited nonzero.
  [wrapper-<job>]      cron wrapper's last recorded exit nonzero.
  [stale-<dataset>]    built table older than its serve TTL (/v1/errors
                       age_s vs ttl_s; skis has no TTL, never flags).
  [guard-restarts]     unexpected API death recorded by pole-guard.sh.
  [never-built-<ds>]   honest 503 for longer than FIRST_BUILD_GRACE_S.
  [regression-<ds>]    dataset flipped ready -> 503.

Noise control (issue judgment calls):
  - State classes need 2 consecutive failing polls (15-min cron: ~30
    min debounce) before filing, so one 429/transient never files.
  - Transport errors (tunnel down, pole unreachable) are NEVER issues
    and never data: exit 2 with a message, file nothing.
  - At most MAX_FILES_PER_RUN new issues per run; existing open issues
    get update comments, never duplicates.

Usage (Mac cron, every 15 min)::
    */15 * * * * HF_POLE_WATCH=1 POLE_BASE_URL=http://127.0.0.1:18001 \
        python3 ~/home-finder/scripts/pole_watch.py >>/tmp/pole-watch.log 2>&1

Without HF_POLE_WATCH=1 (or with --dry-run) this only reports what it
WOULD do — the default is safe to run anywhere. Live issue ops run
explicitly-flagged only (AGENTS.md section 7 hermetic default)::

    HF_POLE_WATCH=1 python3 scripts/pole_watch.py
"""

import datetime
import json
import os
import subprocess
import sys
import urllib.request

BASE = os.environ.get("POLE_BASE_URL", "http://127.0.0.1:18001")
REPO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
STATE_PATH = os.environ.get(
    "HF_POLE_WATCH_STATE",
    os.path.join(os.path.expanduser("~"), ".hf-pole-watch", "state.json"))
LABEL = "pole-watch"
TAG = "pole-release"

STALE_AFTER_S = 2 * 3600          # sync is hourly: >2 h behind is stale
FIRST_BUILD_GRACE_S = 7 * 86400   # honest 503 tolerated for 7 d
GUARD_WINDOW_S = 24 * 3600        # guard restarts watched over trailing 24 h
MAX_FILES_PER_RUN = 5
REQUIRED_FAILS = 2                # consecutive failing polls before filing


class Unreachable(Exception):
    """Transport down: pole/tunnel unreachable — never an issue."""


def _get(path, timeout=20):
    url = BASE.rstrip("/") + path
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001 — any transport failure is "down"
        raise Unreachable("%s: %s" % (path, e))


def poll():
    """Fetch /health + /v1/errors; raises Unreachable on transport failure."""
    return _get("/health"), _get("/v1/errors")


def expected_sha(repo_dir=REPO_DIR):
    """Green-main SHA: pole-release tag when it exists, else origin/main."""
    for ref in ("refs/tags/%s" % TAG, "refs/heads/main"):
        try:
            out = subprocess.run(
                ["git", "ls-remote", "origin", ref], cwd=repo_dir,
                capture_output=True, text=True, timeout=60)
        except Exception:  # noqa: BLE001 — git down: skip staleness, no issue
            return None
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.split()[0]
    return None


def _parse_ts(value):
    try:
        dt = datetime.datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def evaluate(health, errors, exp_sha, now, state):
    """Pure policy: map pole facts onto alert keys with evidence.

    Returns (alerts, state_updates). alerts: key -> evidence dict with
    title/body. Debounce counters live in state['fails'] (consecutive
    failing polls per key); a key is actionable when its counter after
    this poll reaches REQUIRED_FAILS. Healthy keys reset to 0.
    """
    alerts = {}
    fails = state.get("fails", {})
    seen = state.get("seen_503_since", {})
    ever_ready = state.get("ever_ready", {})

    def failing(key, title, body):
        n = fails.get(key, 0) + 1
        fails[key] = n
        if n >= REQUIRED_FAILS:
            alerts[key] = {"title": "[pole-watch] " + key + " " + title,
                           "body": body}

    def healthy(key):
        fails[key] = 0

    deployed_sha = (health or {}).get("deployed_sha")
    deployed_at = _parse_ts((health or {}).get("deployed_at"))
    if exp_sha and deployed_sha != exp_sha:
        age_ok = (deployed_at is not None
                  and (now - deployed_at).total_seconds() <= STALE_AFTER_S)
        if not age_ok:
            failing("sync-behind",
                    "pole behind green-main",
                    "deployed_sha=%s deployed_at=%s expected=%s\n"
                    "Sync runs hourly; lag >2 h means pole-sync.sh is not "
                    "landing green-main. Operator: "
                    "ssh pole '~/hf-pole/bin/pole-sync.sh --check' + "
                    "tail ~/hf-pole/logs/pole-sync.log" %
                    (deployed_sha, (health or {}).get("deployed_at"),
                     exp_sha))
        else:
            healthy("sync-behind")
    else:
        healthy("sync-behind")

    sync = (errors or {}).get("sync") or {}
    if sync.get("rc", 0) != 0:
        failing("sync-failing", "pole auto-sync failing",
                "last sync rc=%s at=%s sha=%s\nOperator: "
                "ssh pole 'tail ~/hf-pole/logs/pole-sync.log'" %
                (sync.get("rc"), sync.get("at"), sync.get("sha")))
    else:
        healthy("sync-failing")

    for job, rec in sorted(((errors or {}).get("wrappers") or {}).items()):
        key = "wrapper-" + job
        if isinstance(rec, dict) and rec.get("rc", 0) != 0:
            failing(key, "wrapper failing (rc=%s)" % rec.get("rc"),
                    "job=%s rc=%s at=%s\nTransient 429s self-heal; this "
                    "fired on %d consecutive polls. Operator: "
                    "ssh pole 'tail ~/hf-pole/logs/%s.log'" %
                    (job, rec.get("rc"), rec.get("at"),
                     fails.get(key, REQUIRED_FAILS), job))
        else:
            healthy(key)

    for ds in (errors or {}).get("datasets", []):
        name = ds.get("name")
        if ds.get("stale"):
            failing("stale-" + name, "table past TTL",
                    "dataset=%s built_at=%s age_s=%.0f ttl_s=%s\nTable is "
                    "older than its serve TTL on %d consecutive polls — "
                    "the harvester is not landing builds." %
                    (name, ds.get("built_at"), ds.get("age_s") or -1,
                     ds.get("ttl_s"), fails.get("stale-" + name,
                                                REQUIRED_FAILS)))
        else:
            healthy("stale-" + name)
        if ds.get("ready"):
            ever_ready[name] = True
            seen.pop(name, None)
            healthy("never-built-" + name)
            healthy("regression-" + name)
        elif ever_ready.get(name):
            failing("regression-" + name, "serving dataset went 503",
                    "dataset=%s served before, now honest-503 on %d "
                    "consecutive polls — regression, not first build." %
                    (name, fails.get("regression-" + name,
                                     REQUIRED_FAILS)))
            healthy("never-built-" + name)
        else:
            first = seen.get(name)
            if first is None:
                seen[name] = now.isoformat()
                fails["never-built-" + name] = 0
            else:
                first_dt = _parse_ts(first) or now
                if (now - first_dt).total_seconds() > FIRST_BUILD_GRACE_S:
                    failing("never-built-" + name,
                            "never built past first-build grace",
                            "dataset=%s honest-503 since %s (>7 d) — "
                            "harvester never landed its first build." %
                            (name, first))
                healthy("regression-" + name)

    return alerts, {"fails": fails, "seen_503_since": seen,
                    "ever_ready": ever_ready}


class Gh:
    """Issue ops through the gh CLI (operator's own auth — no new token)."""

    def __init__(self, dry_run):
        self.dry_run = dry_run
        self.actions = []

    def _run(self, args):
        if self.dry_run:
            return ""
        out = subprocess.run(["gh"] + args, capture_output=True, text=True,
                             timeout=120)
        if out.returncode != 0:
            raise RuntimeError("gh %s failed: %s" % (args[0], out.stderr))
        return out.stdout

    def ensure_label(self):
        try:
            self._run(["label", "create", LABEL, "--description",
                       "harvest-pole watcher alerts (auto-filed, auto-closed)",
                       "--color", "1d76db"])
        except RuntimeError:
            pass  # label exists or API hiccup — listing still works

    def open_issues(self):
        try:
            raw = self._run(["issue", "list", "--label", LABEL,
                             "--state", "open", "--json", "number,title",
                             "--limit", "100"])
        except RuntimeError:
            return []
        if self.dry_run or not raw.strip():
            return []
        try:
            return json.loads(raw)
        except ValueError:
            return []

    def file(self, title, body):
        self.actions.append(("file", title))
        if self.dry_run:
            return None
        out = self._run(["issue", "create", "--title", title, "--body", body,
                         "--label", LABEL])
        return out.strip().splitlines()[-1] if out.strip() else ""

    def comment(self, number, body):
        self.actions.append(("comment", number))
        if not self.dry_run:
            self._run(["issue", "comment", str(number), "--body", body])

    def close(self, number, body):
        self.actions.append(("close", number))
        if not self.dry_run:
            self._run(["issue", "close", str(number), "--reason", "completed"])
            self.comment(number, body)


def _match_key(issues, key):
    marker = "[pole-watch] " + key + " "
    for issue in issues:
        if marker in issue.get("title", ""):
            return issue["number"]
    return None


def reconcile(alerts, errors, now, state, gh):
    """File/update/close per key. Returns action descriptions for the log."""
    gh.ensure_label()
    open_issues = gh.open_issues()
    done = []
    filed = 0
    for key in sorted(alerts):
        ev = alerts[key]
        num = _match_key(open_issues, key)
        if num is None and filed < MAX_FILES_PER_RUN:
            ref = gh.file(ev["title"], ev["body"] + "\n\npole time: %s" %
                          now.isoformat())
            filed += 1
            done.append("file %s%s" % (key, " -> %s" % ref if ref else ""))
        elif num is not None:
            gh.comment(num, "Still failing at %s:\n\n%s" %
                       (now.isoformat(), ev["body"]))
            done.append("update #%d %s" % (num, key))
        else:
            done.append("defer %s (burst cap)" % key)
    # Recovery: open issue whose key is healthy closes itself.
    alert_keys = set(alerts)
    for issue in open_issues:
        title = issue.get("title", "")
        if not title.startswith("[pole-watch] "):
            continue
        key = title[len("[pole-watch] "):].split(" ")[0]
        if key not in alert_keys and not key.startswith("guard-"):
            gh.close(issue["number"],
                     "Recovered at %s — closing." % now.isoformat())
            done.append("close #%d %s (recovered)" % (issue["number"], key))
    # Guard restarts are events, not states: notify once per new restart.
    restarts = (errors or {}).get("guard_restarts", [])
    fresh = [r for r in restarts
             if isinstance(r, dict) and _parse_ts(r.get("at")) is not None
             and (now - _parse_ts(r.get("at"))).total_seconds()
             <= GUARD_WINDOW_S
             and r.get("at", "") > state.get("last_guard_seen", "")]
    if fresh:
        key = "guard-restarts"
        num = _match_key(open_issues, key)
        body = ("%d unexpected API death(s) in trailing 24 h (latest %s). "
                "Deploy restarts go through pole-sync and never appear "
                "here — these are real crashes. Operator: "
                "ssh pole 'tail ~/hf-pole/logs/api.log'" %
                (len(fresh), fresh[-1].get("at")))
        if num is None and filed < MAX_FILES_PER_RUN:
            ref = gh.file("[pole-watch] " + key + " pole API died",
                          body)
            done.append("file %s%s" % (key, " -> %s" % ref if ref else ""))
        elif num is not None:
            gh.comment(num, body)
            done.append("update #%d %s" % (num, key))
        state["last_guard_seen"] = max(r.get("at", "") for r in fresh)
    # Guard recovery: window clean and an issue is open.
    if not [r for r in restarts
            if isinstance(r, dict) and _parse_ts(r.get("at")) is not None
            and (now - _parse_ts(r.get("at"))).total_seconds()
            <= GUARD_WINDOW_S]:
        num = _match_key(open_issues, "guard-restarts")
        if num is not None:
            gh.close(num, "No guard restarts in trailing 24 h at %s — "
                          "closing." % now.isoformat())
            done.append("close #%d guard-restarts (recovered)" % num)
    return done


def load_state(path=STATE_PATH):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(state, path=STATE_PATH):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, sort_keys=True)
    except OSError as e:
        print("watch: state not saved (%s)" % e)


def main(argv=None):
    argv = argv or sys.argv[1:]
    dry_run = ("--dry-run" in argv or
               os.environ.get("HF_POLE_WATCH") != "1")
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    try:
        health, errors = poll()
    except Unreachable as e:
        # Transport down is never an issue and never data.
        print("watch: pole unreachable (%s) — no issues filed" % e)
        return 2
    exp_sha = expected_sha()
    if exp_sha is None:
        print("watch: origin unreachable — staleness check skipped")
    state = load_state()
    alerts, updates = evaluate(health, errors, exp_sha, now, state)
    state.update(updates)
    gh = Gh(dry_run=dry_run)
    done = reconcile(alerts, errors, now, state, gh)
    save_state(state)
    mode = "dry-run" if dry_run else "live"
    print("watch [%s]: %d alert(s): %s" %
          (mode, len(alerts), sorted(alerts) or "none"))
    for line in done:
        print("watch [%s]: %s" % (mode, line))
    return 0


if __name__ == "__main__":
    sys.exit(main())
