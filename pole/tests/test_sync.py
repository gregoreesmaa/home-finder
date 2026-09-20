"""Sync/sidecar behavior tests (issue #806): wrap-run.sh + pole-sync.sh.

Hermetic: local file:// git repos, fake HOME, shims for crontab/venv —
no network, no Pi, no touch of the real checkout.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess

POLE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BIN_DIR = os.path.join(POLE_DIR, "bin")


def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                          **kw)


def _manifest_lists():
    body = open(os.path.join(POLE_DIR, "manifest.sh"),
                encoding="utf-8").read()
    harvesters = re.search(r'HARVESTERS="([^"]+)"', body).group(1).split()
    dims = re.search(r'DIMS="([^"]+)"', body).group(1).split()
    return harvesters, dims


def _hash_tree(root):
    out = {}
    for dirpath, _, files in os.walk(root):
        for fn in files:
            p = os.path.join(dirpath, fn)
            with open(p, "rb") as f:
                out[os.path.relpath(p, root)] = hashlib.sha256(
                    f.read()).hexdigest()
    return out


def test_wrap_run_records_exit_and_passthrough(tmp_path):
    env = dict(os.environ, POLE=str(tmp_path / "pole"), HOME=str(tmp_path))
    wrap = os.path.join(BIN_DIR, "wrap-run.sh")
    r = _run(["sh", wrap, "ok-job", "true"], env=env)
    assert r.returncode == 0
    r = _run(["sh", wrap, "fail-job", "false"], env=env)
    assert r.returncode == 1
    ok = json.loads((tmp_path / "pole" / "state" / "wrapper-status"
                     / "ok-job.json").read_text(encoding="utf-8"))
    bad = json.loads((tmp_path / "pole" / "state" / "wrapper-status"
                      / "fail-job.json").read_text(encoding="utf-8"))
    assert ok["rc"] == 0 and ok["job"] == "ok-job" and ok["at"]
    assert bad["rc"] == 1 and bad["job"] == "fail-job"


def test_wrap_run_sanitizes_job_and_never_fails(tmp_path):
    env = dict(os.environ, POLE=str(tmp_path / "pole"), HOME=str(tmp_path))
    wrap = os.path.join(BIN_DIR, "wrap-run.sh")
    r = _run(["sh", wrap, "../evil", "true"], env=env)
    assert r.returncode == 0  # command rc preserved, name sanitized
    status_dir = tmp_path / "pole" / "state" / "wrapper-status"
    assert (status_dir / "unknown.json").is_file()
    assert not (tmp_path / "pole" / "state" / "evil.json").exists()
    # Unwritable POLE: recording fails silently, exit code still passes.
    env2 = dict(env, POLE="/proc/definitely-not-here")
    r = _run(["sh", wrap, "x", "sh", "-c", "exit 7"], env=env2)
    assert r.returncode == 7


def _fake_repo_with_origin(tmp_path):
    """(repo, origin_bare): file:// remote, one commit, clone checked out."""
    harvesters, dims = _manifest_lists()
    src = tmp_path / "src"
    (src / "scripts" / "build").mkdir(parents=True)
    (src / "services" / "scoring").mkdir(parents=True)
    (src / "pole" / "bin").mkdir(parents=True)
    shutil.copy(os.path.join(POLE_DIR, "manifest.sh"), src / "pole")
    for m in harvesters:
        (src / "scripts" / "build" / (m + ".py")).write_text(
            "# stub %s\n" % m, encoding="utf-8")
    for m in dims:
        (src / "services" / "scoring" / (m + ".py")).write_text(
            "# stub %s\n" % m, encoding="utf-8")
    (src / "pole" / "api.py").write_text("# api v1\n", encoding="utf-8")
    for fn in os.listdir(BIN_DIR):
        shutil.copy(os.path.join(BIN_DIR, fn), src / "pole" / "bin")
    (src / "pole" / "requirements.txt").write_text("fastapi==0.1\n",
                                                   encoding="utf-8")
    (src / "pole" / "crontab.txt").write_text(
        "* * * * * $HOME/hf-pole/bin/wrap-run.sh x "
        "$HOME/hf-pole/bin/run-poi.sh\n", encoding="utf-8")
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    _run(["git", "init", "-q", "-b", "main", str(src)], env=env, check=True)
    _run(["git", "-C", str(src), "add", "-A"], env=env, check=True)
    _run(["git", "-C", str(src), "commit", "-qm", "v1"], env=env, check=True)
    origin = tmp_path / "origin.git"
    _run(["git", "init", "-q", "--bare", str(origin)], check=True)
    _run(["git", "-C", str(src), "remote", "add", "origin", str(origin)],
         check=True)
    _run(["git", "-C", str(src), "push", "-q", "origin", "main"], check=True)
    repo = tmp_path / "repo"
    _run(["git", "clone", "-q", str(origin), str(repo)], check=True)
    return repo, origin, env


def test_sync_check_and_dry_run(tmp_path):
    repo, origin, env = _fake_repo_with_origin(tmp_path)
    sync = os.path.join(BIN_DIR, "pole-sync.sh")
    base_env = dict(os.environ, POLE=str(tmp_path / "pole"),
                    HOME=str(tmp_path))
    target = _run(["git", "-C", str(repo), "rev-parse",
                   "refs/remotes/origin/main"],
                  check=True).stdout.strip()
    # Behind: --check exits 1, --dry-run plans without changing anything.
    r = _run(["sh", sync, str(repo), "--check"], env=base_env)
    assert r.returncode == 1 and target in r.stdout
    assert "deployed: none" in r.stdout
    r = _run(["sh", sync, str(repo), "--dry-run"], env=base_env)
    assert r.returncode == 0 and target in r.stdout
    assert not (tmp_path / "pole").exists()
    # In sync: --check exits 0.
    (tmp_path / "pole" / "state").mkdir(parents=True)
    (tmp_path / "pole" / "state" / "deployed-sha.txt").write_text(
        target + "\n", encoding="utf-8")
    r = _run(["sh", sync, str(repo), "--check"], env=base_env)
    assert r.returncode == 0
    r = _run(["sh", sync, str(repo)], env=base_env)
    assert r.returncode == 0 and "in sync" in r.stdout


def test_sync_deploys_code_and_keeps_data(tmp_path):
    repo, origin, env = _fake_repo_with_origin(tmp_path)
    # v2 on origin (new api.py) while the clone + pole sit on v1.
    src = tmp_path / "src"
    (src / "pole" / "api.py").write_text("# api v2\n", encoding="utf-8")
    _run(["git", "-C", str(src), "add", "-A"], env=env, check=True)
    _run(["git", "-C", str(src), "commit", "-qm", "v2"], env=env, check=True)
    _run(["git", "-C", str(src), "push", "-q", "origin", "main"], check=True)
    target = _run(["git", "-C", str(src), "rev-parse", "HEAD"],
                  check=True).stdout.strip()

    pole = tmp_path / "pole"
    (pole / "harvesters").mkdir(parents=True)
    (pole / "harvesters" / "stale.py").write_text("# old\n",
                                                  encoding="utf-8")
    (pole / "dims").mkdir()
    (pole / "bin").mkdir()
    (pole / "api.py").write_text("# api v1\n", encoding="utf-8")
    (pole / "cache" / "delay").mkdir(parents=True)
    (pole / "cache" / "delay" / "raw.json").write_text('{"n":1}',
                                                       encoding="utf-8")
    (pole / "built" / "fixit").mkdir(parents=True)
    (pole / "built" / "fixit" / "fixit-points.json").write_text('{"n":2}',
                                                                encoding="utf-8")
    (pole / "state").mkdir()
    (pole / "state" / "tomtom.key").write_text("SECRET-KEY",
                                               encoding="utf-8")
    (pole / "logs").mkdir()
    (pole / "logs" / "api.log").write_text("old log\n", encoding="utf-8")
    # api.log is append-only operational output (the deploy restart
    # adds lines) — excluded from the byte-compare, asserted present.
    before_data = _hash_tree(pole / "cache")
    before_data.update({"built/" + k: v
                        for k, v in _hash_tree(pole / "built").items()})
    before_data.update({"logs/" + k: v
                        for k, v in _hash_tree(pole / "logs").items()
                        if k != "api.log"})
    before_key = (pole / "state" / "tomtom.key").read_text(encoding="utf-8")

    # Shims: crontab recorder + fake venv (pip/python exit 0, no network).
    shims = tmp_path / "shims"
    shims.mkdir()
    (shims / "crontab").write_text(
        '#!/bin/sh\necho "crontab $*" >> "$SHIM_LOG"\n', encoding="utf-8")
    venv_bin = pole / "venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "pip").write_text('#!/bin/sh\nexit 0\n', encoding="utf-8")
    (venv_bin / "python").write_text('#!/bin/sh\nexit 0\n', encoding="utf-8")
    for p in (shims / "crontab", venv_bin / "pip", venv_bin / "python"):
        p.chmod(0o755)
    shim_log = tmp_path / "shim.log"
    run_env = dict(os.environ, POLE=str(pole), HOME=str(tmp_path),
                   PATH=str(shims) + ":" + os.environ["PATH"],
                   SHIM_LOG=str(shim_log))

    r = _run(["sh", os.path.join(BIN_DIR, "pole-sync.sh"), str(repo)],
             env=run_env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "deployed" in r.stdout
    # Code landed, deployment recorded.
    assert (pole / "api.py").read_text(encoding="utf-8") == "# api v2\n"
    assert (pole / "state" / "deployed-sha.txt").read_text(
        encoding="utf-8").strip() == target
    assert (pole / "state" / "deployed-at.txt").read_text(
        encoding="utf-8").strip()
    sync_status = json.loads((pole / "state" / "sync-status.json").read_text(
        encoding="utf-8"))
    assert sync_status["rc"] == 0 and sync_status["sha"] == target
    assert (pole / "state" / "api.pid").read_text(
        encoding="utf-8").strip().isdigit()
    backups = list((pole / "state" / "code-backup").glob("sync-*.tgz"))
    assert len(backups) == 1  # previous code restorable
    assert "crontab" in shim_log.read_text(encoding="utf-8")
    # Data + keys untouched.
    after_data = _hash_tree(pole / "cache")
    after_data.update({"built/" + k: v
                       for k, v in _hash_tree(pole / "built").items()})
    after_data.update({"logs/" + k: v
                       for k, v in _hash_tree(pole / "logs").items()
                       if k != "api.log"})
    assert after_data == before_data
    assert (pole / "state" / "tomtom.key").read_text(
        encoding="utf-8") == before_key


def test_sync_script_contains_no_data_paths():
    # Static guard: uncommented sync lines never name data dirs, and the
    # only rm touches the code-backup prune (data dirs are never deleted).
    body = open(os.path.join(BIN_DIR, "pole-sync.sh"),
                encoding="utf-8").read()
    # Strip full-line and trailing comments (no '#' inside sync
    # string literals — verified by the grep below failing loudly).
    code = "\n".join(ln.split("#")[0] for ln in body.splitlines())
    assert "cache" not in code
    assert "built" not in code
    for ln in code.splitlines():
        if "rm -f" in ln:
            assert "BACKUP_DIR" in ln or 'rm -f "$old"' in ln, ln
