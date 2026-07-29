#!/usr/bin/python3
"""Tests fix-repos.py against .repo fixtures, without a container build.

Every test here exists because the corresponding bug reached CI at least once.
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
    fedora_key = os.path.join(keys, f"RPM-GPG-KEY-fedora-44-{arch}")
    with open(fedora_key, "w") as handle:
        handle.write("key\n")

    # --- Regression 1: dnf variables in gpgkey paths -------------------------
    # Comparing these literally condemned every core Fedora repo.
    with open(os.path.join(repo_dir, "fedora.repo"), "w") as handle:
        handle.write(
            "[fedora]\nname=Fedora\nenabled=1\n"
            f"gpgkey=file://{keys}/RPM-GPG-KEY-fedora-$releasever-$basearch\n"
            "\n"
            "[fedora-braces]\nname=Braces\nenabled=1\n"
            f"gpgkey=file://{keys}/RPM-GPG-KEY-fedora-${{releasever}}-${{basearch}}\n"
        )

    # --- Regression 2: the real culprit, which ships DISABLED -----------------
    # bootc-image-builder reads it regardless, so enabled=0 was never a fix.
    # It must actually be removed.
    with open(os.path.join(repo_dir, "terra.repo"), "w") as handle:
        handle.write(
            "[terra]\nname=Terra\nenabled=1\n"
            f"gpgkey=file://{fedora_key}\n"
            "\n"
            "[terra-mesa]\nname=Terra Mesa\nenabled=0\n"
            "gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-terra44-mesa\n"
        )

    # --- Untouchables: unresolvable variables, and remote keys ---------------
    with open(os.path.join(repo_dir, "other.repo"), "w") as handle:
        handle.write(
            "[mystery]\nname=Unknown var\nenabled=1\n"
            "gpgkey=file:///etc/pki/rpm-gpg/KEY-$somethingelse\n"
            "\n"
            "[remote]\nname=Remote\nenabled=1\n"
            "gpgkey=https://example.invalid/KEY\n"
        )

    # --- A file where every section is broken: the file should go ------------
    with open(os.path.join(repo_dir, "allbad.repo"), "w") as handle:
        handle.write(
            "[bad-one]\nname=Bad one\nenabled=1\n"
            "gpgkey=file:///nope/KEY-one\n"
            "\n"
            "[bad-two]\nname=Bad two\nenabled=0\n"
            "gpgkey=file:///nope/KEY-two\n"
        )

    out = run(repo_dir, os_release)

    fedora = open(os.path.join(repo_dir, "fedora.repo")).read()
    check("[fedora]" in fedora and "[fedora-braces]" in fedora,
          "repos whose expanded keys exist must survive")
    print("ok  expands $releasever/$basearch (and ${...}) before judging")

    terra = open(os.path.join(repo_dir, "terra.repo")).read()
    check("[terra-mesa]" not in terra,
          "terra-mesa must be REMOVED, not merely disabled")
    check("RPM-GPG-KEY-terra44-mesa" not in terra,
          "the broken section's lines must all be gone")
    check("[terra]" in terra, "the healthy repo sharing the file must survive")
    check("gpgcheck=0" not in terra, "must never weaken signature checking")
    print("ok  removes a broken repo that ships disabled, spares its neighbour")

    other = open(os.path.join(repo_dir, "other.repo")).read()
    check("[mystery]" in other and "[remote]" in other,
          "unresolvable and remote gpgkeys must be left alone")
    print("ok  leaves unresolvable and remote gpgkeys untouched")

    check(not os.path.exists(os.path.join(repo_dir, "allbad.repo")),
          "a file whose every section is broken should be removed entirely")
    print("ok  deletes a repo file when all of its sections are broken")

    check("Removed 3 broken repo(s)" in out, f"expected 3 removals, got: {out!r}")
    check("terra-mesa" in out, "must report what it removed")
    print("ok  removes exactly the broken repos and reports them")

    # --- Guard: never remove everything --------------------------------------
    guard_dir = os.path.join(work, "guard")
    os.makedirs(guard_dir)
    with open(os.path.join(guard_dir, "all.repo"), "w") as handle:
        handle.write("[only]\nname=Only repo\nenabled=1\n"
                     "gpgkey=file:///definitely/not/here\n")

    guard_out = run(guard_dir, os_release, expect_rc=1)
    check("leaving none" in guard_out, "guard must explain itself")
    check(os.path.exists(os.path.join(guard_dir, "all.repo")),
          "guard must refuse to write, not write and then complain")
    check("[only]" in open(os.path.join(guard_dir, "all.repo")).read(),
          "the file must be untouched when the guard trips")
    print("ok  refuses to remove every repo, and writes nothing when it refuses")

    # --- Idempotence ----------------------------------------------------------
    before = open(os.path.join(repo_dir, "terra.repo")).read()
    run(repo_dir, os_release)
    after = open(os.path.join(repo_dir, "terra.repo")).read()
    check(before == after, "second run must not change anything further")
    print("ok  idempotent across repeated runs")

print()
print("All repo-fix tests passed.")
