#!/usr/bin/python3
"""Tests fix-repos.py against .repo fixtures, without a container build.

Each bug caught here is a 20-minute CI cycle saved.
"""

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "fix-repos.py")


def run(repo_dir):
    env = dict(os.environ, REPO_DIR=repo_dir)
    result = subprocess.run(
        [sys.executable, SCRIPT], env=env, capture_output=True, text=True
    )
    if result.returncode != 0:
        sys.exit(f"FAIL: script exited {result.returncode}\n{result.stderr}")
    return result.stdout


def check(condition, message):
    if not condition:
        sys.exit(f"FAIL: {message}")


with tempfile.TemporaryDirectory() as work:
    repo_dir = os.path.join(work, "repos")
    os.makedirs(repo_dir)
    present_key = os.path.join(work, "RPM-GPG-KEY-present")
    with open(present_key, "w") as handle:
        handle.write("key\n")

    # The real failure: Bazzite's terra-mesa, alongside a healthy repo in the
    # same file that must be left completely alone.
    with open(os.path.join(repo_dir, "terra.repo"), "w") as handle:
        handle.write(
            "[terra]\n"
            "name=Terra\n"
            "baseurl=https://example.invalid/terra\n"
            "enabled=1\n"
            f"gpgkey=file://{present_key}\n"
            "\n"
            "[terra-mesa]\n"
            "name=Terra Mesa\n"
            "baseurl=https://example.invalid/mesa\n"
            "enabled=1\n"
            "gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-terra44-mesa\n"
        )

    # A repo with no enabled= line at all - the disable must be inserted.
    with open(os.path.join(repo_dir, "noenabled.repo"), "w") as handle:
        handle.write(
            "[broken]\n"
            "name=Broken\n"
            "gpgkey=file:///nonexistent/KEY\n"
        )

    # Remote keys must never be touched: we cannot check them and they work.
    with open(os.path.join(repo_dir, "remote.repo"), "w") as handle:
        handle.write(
            "[remote]\n"
            "name=Remote\n"
            "enabled=1\n"
            "gpgkey=https://example.invalid/KEY\n"
        )

    out = run(repo_dir)

    terra = open(os.path.join(repo_dir, "terra.repo")).read()
    healthy, mesa = terra.split("[terra-mesa]")
    check("enabled=1" in healthy, "healthy repo in a shared file must stay enabled")
    check("enabled=0" in mesa, "terra-mesa should have been disabled")
    check("gpgkey=" in mesa, "gpgkey must be preserved, not stripped")
    check("gpgcheck=0" not in terra, "must never weaken signature checking")
    print("ok  disables the broken repo, leaves its healthy neighbour alone")

    noenabled = open(os.path.join(repo_dir, "noenabled.repo")).read()
    check("enabled=0" in noenabled, "enabled=0 must be inserted when absent")
    check(noenabled.index("[broken]") < noenabled.index("enabled=0"),
          "enabled=0 must land inside the section, after its header")
    print("ok  inserts enabled=0 when the section has none")

    remote = open(os.path.join(repo_dir, "remote.repo")).read()
    check("enabled=1" in remote, "repos with remote gpgkeys must be untouched")
    print("ok  ignores repos whose gpgkey is remote")

    check("terra-mesa" in out and "broken" in out, "must report what it disabled")
    check("remote" not in out.replace("repo(s)", ""), "must not report untouched repos")
    print("ok  reports exactly what it changed")

    # Idempotence: every rebuild re-runs this.
    before = open(os.path.join(repo_dir, "terra.repo")).read()
    run(repo_dir)
    after = open(os.path.join(repo_dir, "terra.repo")).read()
    check(before == after, "second run must not change the file again")
    print("ok  idempotent across repeated runs")

print()
print("All repo-fix tests passed.")
