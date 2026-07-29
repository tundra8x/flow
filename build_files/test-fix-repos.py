#!/usr/bin/python3
"""Tests fix-repos.py against .repo fixtures, without a container build.

Every bug caught here is a 20-minute CI cycle saved. Two of these tests exist
because the corresponding bug already reached CI once.
"""

import os
import platform
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "fix-repos.py")


def run(repo_dir, os_release, expect_rc=0):
    env = dict(os.environ, REPO_DIR=repo_dir, FLOW_OS_RELEASE=os_release)
    result = subprocess.run(
        [sys.executable, SCRIPT], env=env, capture_output=True, text=True
    )
    if result.returncode != expect_rc:
        sys.exit(
            f"FAIL: expected rc={expect_rc}, got {result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result.stdout + result.stderr


def check(condition, message):
    if not condition:
        sys.exit(f"FAIL: {message}")


with tempfile.TemporaryDirectory() as work:
    repo_dir = os.path.join(work, "repos")
    keys = os.path.join(work, "keys")
    os.makedirs(repo_dir)
    os.makedirs(keys)

    os_release = os.path.join(work, "os-release")
    with open(os_release, "w") as handle:
        handle.write('NAME="Flow"\nID=bazzite\nVERSION_ID=44\n')

    arch = platform.machine()

    # The key Fedora repos actually use, once variables are expanded.
    fedora_key = os.path.join(keys, f"RPM-GPG-KEY-fedora-44-{arch}")
    with open(fedora_key, "w") as handle:
        handle.write("key\n")

    # --- Fixture 1: the regression that broke the build -----------------------
    # gpgkey with dnf variables. A literal existence check marks this missing
    # and disables every core Fedora repo, producing "no enabled repositories".
    with open(os.path.join(repo_dir, "fedora.repo"), "w") as handle:
        handle.write(
            "[fedora]\n"
            "name=Fedora\n"
            "enabled=1\n"
            f"gpgkey=file://{keys}/RPM-GPG-KEY-fedora-$releasever-$basearch\n"
            "\n"
            "[fedora-braces]\n"
            "name=Fedora braces\n"
            "enabled=1\n"
            f"gpgkey=file://{keys}/RPM-GPG-KEY-fedora-${{releasever}}-${{basearch}}\n"
        )

    # --- Fixture 2: the genuinely broken repo we are here to fix ---------------
    with open(os.path.join(repo_dir, "terra.repo"), "w") as handle:
        handle.write(
            "[terra]\n"
            "name=Terra\n"
            "enabled=1\n"
            f"gpgkey=file://{fedora_key}\n"
            "\n"
            "[terra-mesa]\n"
            "name=Terra Mesa\n"
            "enabled=1\n"
            "gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-terra44-mesa\n"
        )

    # --- Fixture 3: unresolvable variable, and a remote key -------------------
    with open(os.path.join(repo_dir, "other.repo"), "w") as handle:
        handle.write(
            "[mystery]\n"
            "name=Unknown variable\n"
            "enabled=1\n"
            "gpgkey=file:///etc/pki/rpm-gpg/KEY-$somethingelse\n"
            "\n"
            "[remote]\n"
            "name=Remote key\n"
            "enabled=1\n"
            "gpgkey=https://example.invalid/KEY\n"
        )

    out = run(repo_dir, os_release)

    fedora = open(os.path.join(repo_dir, "fedora.repo")).read()
    check("enabled=0" not in fedora,
          "expanded $releasever/$basearch keys exist - must NOT be disabled")
    print("ok  expands $releasever/$basearch (and ${...}) before checking")

    terra = open(os.path.join(repo_dir, "terra.repo")).read()
    healthy, mesa = terra.split("[terra-mesa]")
    check("enabled=1" in healthy, "healthy repo sharing the file must stay enabled")
    check("enabled=0" in mesa, "terra-mesa should have been disabled")
    check("gpgkey=" in mesa, "gpgkey must be preserved, not stripped")
    check("gpgcheck=0" not in terra, "must never weaken signature checking")
    print("ok  disables the genuinely-missing key, spares its neighbour")

    other = open(os.path.join(repo_dir, "other.repo")).read()
    check("enabled=0" not in other,
          "unresolvable variables and remote keys must be left alone")
    print("ok  leaves unresolvable and remote gpgkeys untouched")

    check("terra-mesa" in out, "must report what it disabled")
    check("1 repo(s)" in out, f"should disable exactly one repo, got: {out!r}")
    print("ok  disables exactly one repo and reports it")

    # --- Fixture 4: the safety guard -----------------------------------------
    # If the audit would leave nothing enabled, that is a bug in the audit.
    guard_dir = os.path.join(work, "guard")
    os.makedirs(guard_dir)
    with open(os.path.join(guard_dir, "all.repo"), "w") as handle:
        handle.write(
            "[only-one]\n"
            "name=The only repo\n"
            "enabled=1\n"
            "gpgkey=file:///definitely/not/here\n"
        )

    guard_out = run(guard_dir, os_release, expect_rc=1)
    check("leaving none enabled" in guard_out, "guard must explain itself")
    untouched = open(os.path.join(guard_dir, "all.repo")).read()
    check("enabled=1" in untouched, "guard must refuse to write, not write then fail")
    print("ok  refuses to disable every repo, and writes nothing when it refuses")

    # --- Idempotence ----------------------------------------------------------
    before = open(os.path.join(repo_dir, "terra.repo")).read()
    run(repo_dir, os_release)
    after = open(os.path.join(repo_dir, "terra.repo")).read()
    check(before == after, "second run must not change the file again")
    print("ok  idempotent across repeated runs")

print()
print("All repo-fix tests passed.")
