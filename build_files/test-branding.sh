#!/bin/bash
# Tests branding.sh against os-release fixtures, without a container build.
#
# Point of this: the branding step is the entire deliverable of Phase 0, and a
# silent failure in it produces an image that boots and says "Fedora". Run this
# before pushing.
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

# --- Fixture 1: a realistic Fedora Atomic / Bazzite os-release ---------------
cat >"${WORK}/full" <<'EOF'
NAME="Fedora Linux"
VERSION="44.20260101.0 (Kinoite)"
ID=fedora
VERSION_ID=44
PLATFORM_ID="platform:f44"
PRETTY_NAME="Fedora Linux 44.20260101.0 (Kinoite)"
ANSI_COLOR="0;38;2;60;110;180"
LOGO=fedora-logo-icon
HOME_URL="https://fedoraproject.org/"
DOCUMENTATION_URL="https://docs.fedoraproject.org/"
SUPPORT_URL="https://ask.fedoraproject.org/"
BUG_REPORT_URL="https://bugzilla.redhat.com/"
VARIANT="Kinoite"
VARIANT_ID=kinoite
EOF

OS_RELEASE="${WORK}/full" "${HERE}/branding.sh" >/dev/null

# shellcheck source=/dev/null
name="$(. "${WORK}/full" && printf '%s' "${NAME}")"
# shellcheck source=/dev/null
pretty="$(. "${WORK}/full" && printf '%s' "${PRETTY_NAME}")"
# shellcheck source=/dev/null
variant="$(. "${WORK}/full" && printf '%s' "${VARIANT}")"
# shellcheck source=/dev/null
id="$(. "${WORK}/full" && printf '%s' "${ID}")"
# shellcheck source=/dev/null
vid="$(. "${WORK}/full" && printf '%s' "${VERSION_ID}")"

[ "${name}" = "Flow" ] || fail "NAME was '${name}'"
[ "${pretty}" = "Flow" ] || fail "PRETTY_NAME was '${pretty}'"
[ "${variant}" = "Flow" ] || fail "VARIANT was '${variant}'"
[ "${id}" = "fedora" ] || fail "ID should stay 'fedora', was '${id}'"
[ "${vid}" = "44" ] || fail "VERSION_ID should be inherited, was '${vid}'"
echo "ok  replaces existing keys, inherits VERSION_ID, leaves ID alone"

# --- Fixture 2: base image that omits the keys we brand ----------------------
# This is the regression that a plain `sed -i` would silently pass.
cat >"${WORK}/sparse" <<'EOF'
NAME="Fedora Linux"
ID=fedora
VERSION_ID=44
PRETTY_NAME="Fedora Linux 44"
EOF

OS_RELEASE="${WORK}/sparse" "${HERE}/branding.sh" >/dev/null

# shellcheck source=/dev/null
svariant="$(. "${WORK}/sparse" && printf '%s' "${VARIANT}")"
# shellcheck source=/dev/null
svid="$(. "${WORK}/sparse" && printf '%s' "${VARIANT_ID}")"
# shellcheck source=/dev/null
ssupport="$(. "${WORK}/sparse" && printf '%s' "${SUPPORT_URL}")"

[ "${svariant}" = "Flow" ] || fail "VARIANT not appended, was '${svariant}'"
[ "${svid}" = "flow" ] || fail "VARIANT_ID not appended, was '${svid}'"
[ "${ssupport}" = "https://github.com/tundra8x/flow/issues" ] \
    || fail "SUPPORT_URL not appended, was '${ssupport}'"
echo "ok  appends keys the base image does not set"

# --- Fixture 3: idempotence -------------------------------------------------
# Rebuilds re-run this. Running twice must not duplicate keys.
OS_RELEASE="${WORK}/full" "${HERE}/branding.sh" >/dev/null
count="$(grep -c '^NAME=' "${WORK}/full")"
[ "${count}" -eq 1 ] || fail "NAME duplicated ${count} times after second run"
echo "ok  idempotent across repeated runs"

echo
echo "All branding tests passed."
