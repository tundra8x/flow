#!/bin/bash
# Flow OS image build.
#
# Runs inside the container build. Everything Flow adds on top of Bazzite
# happens here, or is laid down verbatim from system_files/.

set -euxo pipefail

# Contents of system_files/ get copied onto / as-is.
cp -avf "/ctx/system_files"/. /

# Flow identity: os-release branding. Self-verifying; fails the build if the
# image would come out unbranded.
/ctx/branding.sh

# Bazzite ships repos pointing at GPG keys that are absent from the image. They
# are already unusable, but being enabled they abort the anaconda-iso build
# during depsolve. Disable them (rather than weakening gpgcheck) before the
# image is sealed. Invoked via python3 explicitly so this does not depend on
# the exec bit surviving a checkout.
python3 /ctx/fix-repos.py

### Packages ------------------------------------------------------------------
# Nothing yet. Phase 0 is the pipeline and the name; the shell, the tuning, and
# the library land in later phases. Resisting the urge to install things here is
# the whole point of having phases.
