#!/bin/bash
# Tests branding.sh against os-release fixtures, without a container build.
#
# Point of this: branding is the entire deliverable of Phase 0, and it runs
# inside a 20-minute CI build. Every bug caught here is a build cycle saved.
#
#   ./build_files/test-branding.sh

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

# Read a key out of a fixture file.
key() {
    # shellcheck source=/dev/null
    (. "$1" && printf '%s' "${!2-}")
}

# --- Fixture 1: real Bazzite ------------------------------------------------
# These are the actual values from ghcr.io/ublue-os/bazzite:stable, taken from
# the CI log of run 30423864042. Note ID=bazzite, NOT fedora - an earlier
# branding.sh asserted ID=fedora and failed the build on a correct image.
cat >"${WORK}/bazzite" <<'EOF'
NAME="Bazzite"
VERSION="44.20260728 (Bazzite)"
ID=bazzite
ID_LIKE="fedora"
VERSION_ID=44
PRETTY_NAME="Bazzite 44"
ANSI_COLOR="0;38;2;60;110;180"
LOGO=bazzite-logo-icon
HOME_URL="https://bazzite.gg"
DOCUMENTATION_URL="https://docs.bazzite.gg"
SUPPORT_URL="https://discord.bazzite.gg"
BUG_REPORT_URL="https://github.com/ublue-os/bazzite/issues"
VARIANT="Bazzite"
VARIANT_ID=bazzite
DEFAULT_HOSTNAME="bazzite"
EOF

OS_RELEASE="${WORK}/bazzite" "${HERE}/branding.sh" >/dev/null

[ "$(key "${WORK}/bazzite" NAME)" = "Flow" ]        || fail "NAME not branded"
[ "$(key "${WORK}/bazzite" PRETTY_NAME)" = "Flow" ] || fail "PRETTY_NAME not branded"
[ "$(key "${WORK}/bazzite" VARIANT)" = "Flow" ]     || fail "VARIANT not branded"
[ "$(key "${WORK}/bazzite" VARIANT_ID)" = "flow" ]  || fail "VARIANT_ID not branded"
[ "$(key "${WORK}/bazzite" ID)" = "bazzite" ] \
    || fail "ID must be left alone, was '$(key "${WORK}/bazzite" ID)'"
[ "$(key "${WORK}/bazzite" VERSION_ID)" = "44" ] \
    || fail "VERSION_ID must be inherited"
[ "$(key "${WORK}/bazzite" ID_LIKE)" = "fedora" ] \
    || fail "ID_LIKE must be left alone"
echo "ok  real Bazzite: brands name, leaves ID/ID_LIKE/VERSION_ID alone"

# --- Fixture 2: plain Fedora ------------------------------------------------
# Guards the other direction: branding must not hardcode 'bazzite' either, in
# case we ever rebase onto Fedora Atomic or Aurora directly.
cat >"${WORK}/fedora" <<'EOF'
NAME="Fedora Linux"
ID=fedora
VERSION_ID=44
PRETTY_NAME="Fedora Linux 44 (Kinoite)"
VARIANT="Kinoite"
VARIANT_ID=kinoite
EOF

OS_RELEASE="${WORK}/fedora" "${HERE}/branding.sh" >/dev/null

[ "$(key "${WORK}/fedora" NAME)" = "Flow" ]  || fail "NAME not branded on fedora"
[ "$(key "${WORK}/fedora" ID)" = "fedora" ]  || fail "ID must be left alone on fedora"
echo "ok  plain Fedora: same behaviour, ID preserved"

# --- Fixture 3: base that omits the keys we brand ---------------------------
# The regression a plain `sed -i` would silently pass.
cat >"${WORK}/sparse" <<'EOF'
NAME="Some Base"
ID=somebase
VERSION_ID=1
PRETTY_NAME="Some Base 1"
EOF

OS_RELEASE="${WORK}/sparse" "${HERE}/branding.sh" >/dev/null

[ "$(key "${WORK}/sparse" VARIANT)" = "Flow" ]   || fail "VARIANT not appended"
[ "$(key "${WORK}/sparse" VARIANT_ID)" = "flow" ] || fail "VARIANT_ID not appended"
[ "$(key "${WORK}/sparse" SUPPORT_URL)" = "https://github.com/tundra8x/flow/issues" ] \
    || fail "SUPPORT_URL not appended"
[ "$(key "${WORK}/sparse" ID)" = "somebase" ]    || fail "ID must be left alone"
echo "ok  sparse base: appends keys the base does not set"

# --- Fixture 4: idempotence -------------------------------------------------
# Every rebuild re-runs this. Twice must equal once.
OS_RELEASE="${WORK}/bazzite" "${HERE}/branding.sh" >/dev/null
count="$(grep -c '^NAME=' "${WORK}/bazzite")"
[ "${count}" -eq 1 ] || fail "NAME duplicated ${count} times after second run"
[ "$(key "${WORK}/bazzite" ID)" = "bazzite" ] || fail "ID drifted on second run"
echo "ok  idempotent across repeated runs"

echo
echo "All branding tests passed."
