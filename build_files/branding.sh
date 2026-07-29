#!/bin/bash
# Flow identity.
#
# os-release is rewritten in place rather than replaced with a static file, so
# Flow keeps inheriting VERSION_ID, PLATFORM_ID and friends from the base image
# on every rebase. A static copy would go stale silently at the next Fedora bump
# and we'd ship an image claiming to be a Fedora version it isn't.
#
# OS_RELEASE is overridable so this can be run against a fixture outside a
# container build. See build_files/test-branding.sh.

set -euo pipefail

OS_RELEASE="${OS_RELEASE:-/usr/lib/os-release}"

FLOW_URL="https://github.com/tundra8x/flow"
FLOW_ISSUES="${FLOW_URL}/issues"

# Replace the key if the base image sets it, append it if it doesn't.
# The append half matters: a plain `sed -i s/...` silently no-ops on a missing
# key, and we'd ship an unbranded image with no error to notice.
set_os_release_key() {
    local key="$1"
    local value="$2"
    if grep -q "^${key}=" "${OS_RELEASE}"; then
        sed -i "s|^${key}=.*|${key}=${value}|" "${OS_RELEASE}"
    else
        printf '%s=%s\n' "${key}" "${value}" >>"${OS_RELEASE}"
    fi
}

set_os_release_key NAME '"Flow"'
set_os_release_key PRETTY_NAME '"Flow"'
set_os_release_key VARIANT '"Flow"'
set_os_release_key VARIANT_ID 'flow'
set_os_release_key HOME_URL "\"${FLOW_URL}\""
set_os_release_key DOCUMENTATION_URL "\"${FLOW_URL}\""
set_os_release_key SUPPORT_URL "\"${FLOW_ISSUES}\""
set_os_release_key BUG_REPORT_URL "\"${FLOW_ISSUES}\""

# ID stays "fedora" on purpose. dnf, rpm, Steam's installer, GPU driver scripts,
# and a lot of third-party software branch on it; changing it breaks them for
# zero user-visible gain. Branding belongs in NAME/PRETTY_NAME/VARIANT, which is
# what desktop UIs actually display.

### Verify --------------------------------------------------------------------
# Fail here rather than discovering an unbranded image after burning it to USB.

echo "--- Flow os-release ---"
grep -E '^(NAME|PRETTY_NAME|VARIANT|VARIANT_ID|ID|VERSION_ID)=' "${OS_RELEASE}"

# shellcheck source=/dev/null
branded_name="$(. "${OS_RELEASE}" && printf '%s' "${NAME}")"
# shellcheck source=/dev/null
branded_pretty="$(. "${OS_RELEASE}" && printf '%s' "${PRETTY_NAME}")"
# shellcheck source=/dev/null
branded_id="$(. "${OS_RELEASE}" && printf '%s' "${ID}")"

test "${branded_name}" = "Flow"
test "${branded_pretty}" = "Flow"
test "${branded_id}" = "fedora"

echo "Flow branding applied."
