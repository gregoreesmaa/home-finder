"""Hermetic watcher tests (issue #806): policy + issue reconciliation.

No network, no `gh`, no Pi: evaluate()/reconcile() run against fixture
dicts with a FakeGh. The live watcher run stays explicitly-flagged
(HF_POLE_WATCH=1 against the real tunnel, like the presence sweep).
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

import pole_watch as w  # noqa: E402

NOW = datetime.datetime(2026, 9, 20, 12, 0, 0,
                        tzinfo=datetime.timezone.utc)


def _errors(**kw):
    body = {"deployed_sha": "abc", "deployed_at": "2026-09-20T11:00:00+00:00",
            "guard_restarts": [], "wrappers": {}, "sync": {"rc": 0},
            "datasets": []}
    body.update(kw)
    return body


def _health(**kw):
    body = {"ok": True, "datasets": {},
            "deployed_sha": "abc",
            "deployed_at": "2026-09-20T11:00:00+00:00"}
    body.update(kw)
    return body


class FakeGh:
    def __init__(self, open_issues=None):
        self.open = list(open_issues or [])
        self.actions = []
        self.next_number = 900

    def ensure_label(self):
        pass

    def open_issues(self):
        return list(self.open)

    def file(self, title, body):
        self.next_number += 1
        self.open.append({"number": self.next_number, "title": title})
        self.actions.append(("file", title))
        return "#%d" % self.next_number

    def comment(self, number, body):
        self.actions.append(("comment", number))

    def close(self, number, body):
        self.actions.append(("close", number))
        self.open = [i for i in self.open if i["number"] != number]


def _two_polls(health, errors, exp_sha="abc", state=None):
    state = state or {}
    alerts1, upd1 = w.evaluate(health, errors, exp_sha, NOW, state)
    state.update(upd1)
    alerts2, upd2 = w.evaluate(health, errors, exp_sha, NOW, state)
    state.update(upd2)
    return alerts1, alerts2, state


def test_healthy_pole_files_nothing():
    errs = _errors(datasets=[{"name": "poi", "ready": True,
                              "built_at": "2026-09-20T11:00:00+00:00",
                              "age_s": 3600, "ttl_s": 5184000,
                              "stale": False}])
    a1, a2, _ = _two_polls(_health(), errs)
    assert a1 == {} and a2 == {}
    gh = FakeGh()
    assert w.reconcile(a2, errs, NOW, {}, gh) == []
    assert gh.actions == []


def test_debounce_files_on_second_poll_then_updates():
    errs = _errors(wrappers={"outage": {"job": "outage", "rc": 1,
                                        "at": "2026-09-20T11:00:00+00:00"}})
    a1, a2, state = _two_polls(_health(), errs)
    assert a1 == {}  # first sighting: debounce, no file
    assert set(a2) == {"wrapper-outage"}
    gh = FakeGh()
    done = w.reconcile(a2, errs, NOW, state, gh)
    assert done == ["file wrapper-outage -> #901"]
    # Third poll: same open issue gets a comment, never a duplicate.
    a3, upd = w.evaluate(_health(), errs, "abc", NOW, state)
    state.update(upd)
    done = w.reconcile(a3, errs, NOW, state, gh)
    assert done == ["update #901 wrapper-outage"]
    assert [a for a in gh.actions if a[0] == "file"] == [("file", gh.open[0]["title"])]


def test_recovery_closes_issue():
    gh = FakeGh(open_issues=[{"number": 901,
                               "title": "[pole-watch] wrapper-outage failing"}])
    errs = _errors(wrappers={"outage": {"job": "outage", "rc": 0,
                                        "at": "2026-09-20T12:00:00+00:00"}})
    alerts, upd = w.evaluate(_health(), errs, "abc", NOW, {})
    assert alerts == {}
    done = w.reconcile(alerts, errs, NOW, upd, gh)
    assert done == ["close #901 wrapper-outage (recovered)"]


def test_sync_behind_only_when_old():
    errs = _errors()
    old = _health(deployed_sha="old",
                  deployed_at="2026-09-20T08:00:00+00:00")  # 4 h ago
    _, a2, _ = _two_polls(old, errs, exp_sha="new")
    assert set(a2) == {"sync-behind"}
    fresh = _health(deployed_sha="old",
                    deployed_at="2026-09-20T11:30:00+00:00")  # 30 min ago
    _, a2, _ = _two_polls(fresh, errs, exp_sha="new")
    assert a2 == {}  # hourly sync in flight: lag <= 2 h is normal
    _, a2, _ = _two_polls(old, errs, exp_sha="old")
    assert a2 == {}  # deployed == expected: never stale


def test_sync_failing_and_stale_table():
    errs = _errors(
        sync={"rc": 2, "at": "2026-09-20T11:00:00+00:00", "sha": "abc",
              "ref": "x"},
        datasets=[{"name": "outage", "ready": True,
                   "built_at": "2026-09-20T10:00:00+00:00",
                   "age_s": 7200, "ttl_s": 300, "stale": True}])
    _, a2, _ = _two_polls(_health(), errs)
    assert set(a2) == {"sync-failing", "stale-outage"}


def test_guard_restart_files_once_per_event():
    errs = _errors(guard_restarts=[
        {"at": "2026-09-20T11:00:00+00:00", "event": "guard-restart"}])
    alerts, upd = w.evaluate(_health(), errs, "abc", NOW, {})
    assert alerts == {}  # guard is event-based, not state-debounced
    gh = FakeGh()
    done = w.reconcile(alerts, errs, NOW, upd, gh)
    assert done == ["file guard-restarts -> #901"]
    # Same restart seen again: no duplicate (last_guard_seen advanced).
    alerts, upd2 = w.evaluate(_health(), errs, "abc", NOW, upd)
    upd.update(upd2)
    done = w.reconcile(alerts, errs, NOW, upd, gh)
    assert done == []
    # Window clean + issue open: recovery closes it.
    clean = _errors()
    done = w.reconcile({}, clean, NOW, upd2, gh)
    assert done == ["close #901 guard-restarts (recovered)"]


def test_never_built_grace_and_regression():
    ds = {"name": "sheds", "ready": False, "built_at": None,
          "age_s": None, "ttl_s": 604800, "stale": False}
    errs = _errors(datasets=[ds])
    state = {}
    alerts, upd = w.evaluate(_health(), errs, "abc", NOW, state)
    state.update(upd)
    assert alerts == {}  # first sighting starts the 7 d grace clock
    old = dict(state)
    old["seen_503_since"] = {
        "sheds": "2026-09-10T12:00:00+00:00"}  # 10 d of honest 503
    old["fails"] = {}
    alerts, _ = w.evaluate(_health(), errs, "abc", NOW, old)
    assert alerts == {}  # grace expired but debounce needs 2 polls
    alerts, _ = w.evaluate(_health(), errs, "abc", NOW, old)
    assert set(alerts) == {"never-built-sheds"}
    # Regression: served before, 503 now.
    reg = dict(state)
    reg["ever_ready"] = {"sheds": True}
    reg["fails"] = {}
    a1, _ = w.evaluate(_health(), errs, "abc", NOW, reg)
    assert a1 == {}
    a2, _ = w.evaluate(_health(), errs, "abc", NOW, reg)
    assert set(a2) == {"regression-sheds"}


def test_burst_cap_and_transport_never_files(monkeypatch):
    errs = _errors(
        sync={"rc": 1, "at": "2026-09-20T11:00:00+00:00"},
        wrappers={("job%d" % i): {"job": "job%d" % i, "rc": 1,
                                  "at": "2026-09-20T11:00:00+00:00"}
                  for i in range(8)})
    state = {"fails": {}}
    w.evaluate(_health(), errs, "abc", NOW, state)
    alerts, upd = w.evaluate(_health(), errs, "abc", NOW, state)
    assert len(alerts) == 9
    gh = FakeGh()
    done = w.reconcile(alerts, errs, NOW, upd, gh)
    files = [d for d in done if d.startswith("file ")]
    defers = [d for d in done if d.startswith("defer ")]
    assert len(files) == w.MAX_FILES_PER_RUN
    assert len(defers) == 9 - w.MAX_FILES_PER_RUN
    # Transport down: exit 2, zero issue ops.
    monkeypatch.setattr(w, "BASE", "http://127.0.0.1:9")
    assert w.main(["--dry-run"]) == 2
