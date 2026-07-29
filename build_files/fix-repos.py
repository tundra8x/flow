#!/usr/bin/python3
"""Disable dnf repos whose GPG key file is missing from the image.

Why this exists
---------------
The anaconda-iso build depsolves packages for the installer using the repos
defined inside the image. Bazzite ships repo definitions that point at GPG key
files which are not present, e.g.:

    Failed to retrieve GPG key for repo 'terra-mesa':
    Couldn't open file /etc/pki/rpm-gpg/RPM-GPG-KEY-terra44-mesa

Any such repo is already unusable - dnf cannot verify packages from it - but it
is enabled, so depsolve tries it and the whole ISO build dies.

We disable those repos rather than setting gpgcheck=0 or deleting the gpgkey
line. Both of those would "fix" the build by turning off signature verification
on a repo we ship to users, which is not a trade worth making for an OS someone
is going to install. Disabling an already-broken repo loses nothing: Flow
updates as a whole image via bootc, not by pulling from these repos.

This audits rather than hardcoding 'terra-mesa', so the next renamed key does
not cost another 20-minute build cycle to discover.

REPO_DIR is overridable for testing. See test-fix-repos.py.
"""

import glob
import os
import re
import sys

SECTION_RE = re.compile(r"^\s*\[(?P<name>.+?)\]\s*$")
GPGKEY_RE = re.compile(r"^\s*gpgkey\s*=\s*(?P<value>.*)$", re.IGNORECASE)
ENABLED_RE = re.compile(r"^\s*enabled\s*=", re.IGNORECASE)


def missing_keys(body):
    """File-based gpgkey paths referenced by these lines that do not exist."""
    missing = []
    for line in body:
        match = GPGKEY_RE.match(line)
        if not match:
            continue
        for token in match.group("value").split():
            if token.startswith("file://"):
                path = token[len("file://"):]
                if not os.path.exists(path):
                    missing.append(path)
    return missing


def parse_sections(lines):
    """Split a .repo file into (preamble, [(name, [body lines])])."""
    preamble, sections = [], []
    for line in lines:
        match = SECTION_RE.match(line)
        if match:
            sections.append((match.group("name"), [line]))
        elif sections:
            sections[-1][1].append(line)
        else:
            preamble.append(line)
    return preamble, sections


def disable(body):
    """Force enabled=0 in a section body, replacing or inserting as needed."""
    out, replaced = [], False
    for line in body:
        if ENABLED_RE.match(line) and not replaced:
            out.append("enabled=0")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.insert(1, "enabled=0")  # straight after the [section] header
    return out


def main():
    repo_dir = os.environ.get("REPO_DIR", "/etc/yum.repos.d")
    disabled = []

    for path in sorted(glob.glob(os.path.join(repo_dir, "*.repo"))):
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()

        preamble, sections = parse_sections(lines)
        touched = False
        rebuilt = []

        for name, body in sections:
            gone = missing_keys(body)
            if gone:
                body = disable(body)
                touched = True
                disabled.append((os.path.basename(path), name, gone))
            rebuilt.append(body)

        if touched:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(preamble + [l for b in rebuilt for l in b]) + "\n")

    if disabled:
        print(f"Disabled {len(disabled)} repo(s) with missing GPG keys:")
        for filename, name, gone in disabled:
            print(f"  {filename} [{name}] -> missing {', '.join(gone)}")
    else:
        print("No repos reference missing GPG keys.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
