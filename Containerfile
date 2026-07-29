# Flow OS
#
# The whole operating system is defined by this file. CI builds it into a
# bootable OCI image and an installable ISO; nothing is ever assembled by hand
# on a live machine.

# Build scripts and overlay files, referenced without landing in the final image.
FROM scratch AS ctx
COPY build_files /
COPY system_files /system_files

# Base: Bazzite (Fedora Atomic plus the full Linux gaming stack - Proton, Mesa,
# gamescope, GameMode, controller and handheld support). Flow inherits all of
# that and layers its own identity, shell, and tuning on top.
#
# Deliberately unpinned for now so the first builds always start from a base
# that definitely exists. Once CI is green, pin to a digest and let Renovate
# bump it, which makes builds reproducible:
#   FROM ghcr.io/ublue-os/bazzite:stable@sha256:<digest>
FROM ghcr.io/ublue-os/bazzite:stable

### MODIFICATIONS
## Everything Flow adds lives in build_files/build.sh and system_files/.
RUN --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/log \
    --mount=type=tmpfs,dst=/tmp \
    /ctx/build.sh

### LINTING
## Verify final image and contents are correct.
RUN bootc container lint
