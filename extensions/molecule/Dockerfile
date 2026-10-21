# get_sybers.cluster — shared Tier-A molecule substrate.
#
# Why Debian and not an OCI/LXC base: these roles automate the Proxmox VE HOST,
# which is Debian. Tier A does not try to be a PVE node (a container cannot be
# one); it is a hermetic Debian userspace in which the host-side logic that does
# NOT need a live PVE/Ceph/Ludus/PocketBase — argument validation, assertions,
# report-mode, and idempotent local file edits against committed fixtures — runs
# in CI. Anything that needs real PVE lives in the Tier-B scenarios
# (CONFORM_PVE=1, molecule default driver, managed:false). See docs/04 §9.
#
# Pinned by digest so every run (CI and local) builds the exact same base; raise
# it deliberately when refreshing the substrate. trixie == Debian 13, the PVE 9
# host OS family. Slim + no systemd: molecule drives the container over the
# docker connection plugin, not ssh/init, so there is nothing for an init to do.
#
# This file is shared by every scenario via `dockerfile: ../Dockerfile` in
# extensions/molecule/config.yml. molecule-docker renders it through Jinja before
# building, so it deliberately contains no Jinja delimiters anywhere (not even in
# a comment) and no COPY (the build context is the per-scenario directory, which
# is irrelevant here).
FROM docker.io/library/debian:trixie-slim@sha256:918311b7b6c4c6f68b232ba516584925f6c78ad82b6fd534b98979df6438e483

# A molecule-managed container needs: python3 (ansible's target interpreter),
# python3-apt (so the apt module is idempotent rather than shelling out),
# sudo (become), plus the handful of host tools the roles call out to for real
# work against fixtures (unzip for packer plugins, iproute2/procps for fact
# gathering, rsync for file sync, ca-certificates for any https fixture fetch).
# DEBIAN_FRONTEND keeps apt non-interactive; the cache is cleared in-layer.
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-apt \
        python3-yaml \
        sudo \
        unzip \
        iproute2 \
        procps \
        rsync \
        ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Molecule's docker connection execs as root, so become is a no-op escalation;
# wire passwordless sudo anyway so a scenario that drops to a non-root
# become_user still works. No systemd, no ssh, no entrypoint — the scenario's
# `command: sleep infinity` (config.yml) keeps the container alive for exec.
RUN printf 'Defaults:root !requiretty\n' > /etc/sudoers.d/molecule \
    && chmod 0440 /etc/sudoers.d/molecule
