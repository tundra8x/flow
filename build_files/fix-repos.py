#!/usr/bin/python3
"""Remove dnf repo definitions whose GPG key file is missing from the image.

Why this exists
---------------
bootc-image-builder depsolves packages for the Anaconda installer using the repo
definitions inside the image. Bazzite ships definitions pointing at GPG key files
that are not present, and the ISO build dies:

    Failed to retrieve GPG key for repo 'terra-mesa':
    Couldn't open file /etc/pki/rpm-gpg/RPM-GPG-KEY-terra44-mesa

Three things learned the expensive way, each from a failed build
---------------------------------------------------------------
1. gpgkey paths contain dnf variables ($releasever, $basearch). Comparing them
   literally marks every core Fedora repo as missing. Expand first; if a path
   still holds an unknown variable, leave the repo alone, because an
   unverifiable path is not evidence of a broken repo.

2. Never touch every repo. An early version disabled 19 and the build died with
   "There are no enabled repositories". If this would remove everything, that is
   a bug here, not a broken image, so it fails loudly and writes nothing.

3. **Removing beats disabling.** terra-mesa already ships as enabled=0 and
   bootc-image-builder consults it regardless, so setting enabled=0 changes
   nothing. The definition has to actually go.

We remove rather than setting gpgcheck=0 or stripping the gpgkey line: those
"fix" the build by turning off signature verification on a repo shipped to
people installing Flow. Nothing is lost by dropping an already-unusable repo,
since Flow updates as a whole image via bootc.

REPO_DIR / FLOW_OS_RELEASE are overridable for testing. See test-fix-repos.py.
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


def dnf_variables(os_release):
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


def key_status(body, variables):
    """(missing paths, unresolvable paths) for file:// gpgkeys in a section."""
    missing, unresolvable = [], []
    for line in body:
        match = GPGKEY_RE.match(line)
        if not match:
            continue
        for token in match.group("value").split():
            if not token.startswith("file://"):
                continue  # remote key; not ours to verify
            raw = token[len("file://"):]
            resolved = expand(raw, variables)
            if resolved is None:
                unresolvable.append(raw)
            elif not os.path.exists(resolved):
                missing.append(resolved)
    return missing, unresolvable


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


def main():
    repo_dir = os.environ.get("REPO_DIR", "/etc/yum.repos.d")
    os_release = os.environ.get("FLOW_OS_RELEASE", "/usr/lib/os-release")
    variables = dnf_variables(os_release)

    print("--- repo audit ---")
    print(f"dnf variables: releasever={variables['releasever']!r} "
          f"basearch={variables['basearch']!r}")

    plans, doomed, survivors = [], [], 0

    for path in sorted(glob.glob(os.path.join(repo_dir, "*.repo"))):
        with open(path, encoding="utf-8") as handle:
            preamble, sections = parse_sections(handle.read().splitlines())

        keep, dropped = [], False
        for name, body in sections:
            missing, unresolvable = key_status(body, variables)
            state = "enabled" if is_enabled(body) else "disabled"

            if missing:
                verdict = f"REMOVE (missing {', '.join(missing)})"
                doomed.append((os.path.basename(path), name))
                dropped = True
            else:
                verdict = "keep"
                if unresolvable:
                    verdict += f" (unresolvable: {', '.join(unresolvable)})"
                keep.append((name, body))
                survivors += 1

            print(f"  {os.path.basename(path)} [{name}] {state} -> {verdict}")

        plans.append((path, preamble, keep, dropped))

    # Removing everything is always a bug here, never a correct outcome.
    if doomed and survivors == 0:
        print(f"\nERROR: would remove all {len(doomed)} repo(s), leaving none.\n"
              "       That is a bug in this audit, not a broken image. "
              "Refusing to write.", file=sys.stderr)
        return 1

    for path, preamble, keep, dropped in plans:
        if not dropped:
            continue
        if keep:
            body = [line for _, section in keep for line in section]
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(preamble + body) + "\n")
        else:
            os.remove(path)  # every section was broken; the file is now noise

    print()
    if doomed:
        print(f"Removed {len(doomed)} broken repo(s), {survivors} remain:")
        for filename, name in doomed:
            print(f"  {filename} [{name}]")
    else:
        print(f"No repos reference missing GPG keys ({survivors} present).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
