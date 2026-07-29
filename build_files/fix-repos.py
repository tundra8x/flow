#!/usr/bin/python3
"""Disable dnf repos whose GPG key file is genuinely missing from the image.

Why this exists
---------------
The anaconda-iso build depsolves packages for the installer using the repos
defined inside the image. Bazzite ships repo definitions pointing at GPG key
files that are not present, e.g.:

    Failed to retrieve GPG key for repo 'terra-mesa':
    Couldn't open file /etc/pki/rpm-gpg/RPM-GPG-KEY-terra44-mesa

Such a repo is already unusable - dnf cannot verify packages from it - but it is
enabled, so depsolve consults it and the ISO build dies.

We disable those repos rather than setting gpgcheck=0 or deleting the gpgkey
line. Both of those would "fix" the build by disabling signature verification on
a repo shipped to people installing Flow, which is not a trade worth making.
Disabling an already-broken repo costs nothing: Flow updates as a whole image
via bootc, not by pulling from these repos.

Two hard-won rules, both from a build that failed
------------------------------------------------
1. gpgkey paths contain dnf variables ($releasever, $basearch). Checking them
   literally marks every core Fedora repo as missing. Expand first, and if a
   path still holds an unknown variable, leave the repo alone - an unverifiable
   path is not evidence of a broken repo.

2. Never disable every repo. A first version disabled 19 of them and the build
   died with "There are no enabled repositories". If this script would leave
   nothing enabled, it is wrong, and it fails loudly instead of shipping a
   broken image.

REPO_DIR is overridable for testing. See test-fix-repos.py.
"""

import glob
import os
import platform
import re
import sys

SECTION_RE = re.compile(r"^\s*\[(?P<name>.+?)\]\s*$")
GPGKEY_RE = re.compile(r"^\s*gpgkey\s*=\s*(?P<value>.*)$", re.IGNORECASE)
ENABLED_RE = re.compile(r"^\s*enabled\s*=\s*(?P<value>\S+)", re.IGNORECASE)
VARIABLE_RE = re.compile(r"\$\{?\w+\}?")


def dnf_variables(os_release="/usr/lib/os-release"):
    """The dnf variables we can resolve, mirroring how dnf expands them."""
    releasever = ""
    try:
        with open(os_release, encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("VERSION_ID="):
                    releasever = line.split("=", 1)[1].strip().strip('"')
                    break
    except OSError:
        pass
    return {"releasever": releasever, "basearch": platform.machine()}


def expand(path, variables):
    """Expand $var and ${var}. Returns None if anything stays unresolved."""
    def substitute(match):
        name = match.group(0).lstrip("$").strip("{}")
        return variables.get(name) or match.group(0)

    expanded = VARIABLE_RE.sub(substitute, path)
    return None if VARIABLE_RE.search(expanded) else expanded


def missing_keys(body, variables):
    """file:// gpgkey paths in these lines that resolve and do not exist.

    Paths we cannot fully resolve are skipped: we will not disable a repo on a
    guess.
    """
    missing = []
    for line in body:
        match = GPGKEY_RE.match(line)
        if not match:
            continue
        for token in match.group("value").split():
            if not token.startswith("file://"):
                continue  # remote key; nothing we can check here
            resolved = expand(token[len("file://"):], variables)
            if resolved and not os.path.exists(resolved):
                missing.append(resolved)
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


def is_enabled(body):
    for line in body:
        match = ENABLED_RE.match(line)
        if match:
            return match.group("value") not in ("0", "False", "false", "no")
    return True  # dnf treats a repo with no enabled= as enabled


def disable(body):
    """Force enabled=0, replacing the existing line or inserting after [name]."""
    out, replaced = [], False
    for line in body:
        if ENABLED_RE.match(line) and not replaced:
            out.append("enabled=0")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.insert(1, "enabled=0")
    return out


def main():
    repo_dir = os.environ.get("REPO_DIR", "/etc/yum.repos.d")
    os_release = os.environ.get("FLOW_OS_RELEASE", "/usr/lib/os-release")
    variables = dnf_variables(os_release)
    print(f"dnf variables: releasever={variables['releasever']!r} "
          f"basearch={variables['basearch']!r}")

    files, disabled, still_enabled = [], [], 0

    for path in sorted(glob.glob(os.path.join(repo_dir, "*.repo"))):
        with open(path, encoding="utf-8") as handle:
            preamble, sections = parse_sections(handle.read().splitlines())

        rebuilt, touched = [], False
        for name, body in sections:
            gone = missing_keys(body, variables)
            if gone and is_enabled(body):
                body = disable(body)
                touched = True
                disabled.append((os.path.basename(path), name, gone))
            elif is_enabled(body):
                still_enabled += 1
            rebuilt.append(body)

        files.append((path, preamble, rebuilt, touched))

    # Guard: disabling everything is never the right answer. Fail before
    # writing, so a bad audit cannot produce a broken image.
    if disabled and still_enabled == 0:
        print(
            f"ERROR: would disable {len(disabled)} repo(s) leaving none enabled.\n"
            "       That is a bug in this audit, not a broken image. "
            "Refusing to write.",
            file=sys.stderr,
        )
        for filename, name, gone in disabled:
            print(f"  would disable {filename} [{name}] -> {', '.join(gone)}",
                  file=sys.stderr)
        return 1

    for path, preamble, rebuilt, touched in files:
        if touched:
            body = [line for section in rebuilt for line in section]
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(preamble + body) + "\n")

    if disabled:
        print(f"Disabled {len(disabled)} repo(s) with missing GPG keys "
              f"({still_enabled} left enabled):")
        for filename, name, gone in disabled:
            print(f"  {filename} [{name}] -> missing {', '.join(gone)}")
    else:
        print(f"No repos reference missing GPG keys ({still_enabled} enabled).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
