#!/usr/bin/env bash
# Run get_sybers.cluster inside the Apple `container` controller image.
#
#   ./run.sh                                   # interactive shell in the image
#   ./run.sh ansible-playbook playbooks/cluster-ceph-diagnose.yml -i inventory/
#   ./run.sh ansible-playbook playbooks/cluster-storage-net.yml  -i inventory/ --check
#   ./run.sh ansible-lint playbooks/            # the image doubles as a linter
#   ./run.sh ansible -m ping all -i inventory/  # connectivity smoke test
#
# Env knobs:
#   SKIP_BUILD=1   skip the (layer-cached) build step
#   ANSIBLE_IMAGE  image tag to build/run (default get-sybers-ansible:latest)
# PROXMOX_* / ANSIBLE_* set in your shell are forwarded in.
set -euo pipefail

IMAGE="${ANSIBLE_IMAGE:-get-sybers-ansible:latest}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANSIBLE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)" # the collection root (build context)

if ! command -v container > /dev/null 2>&1; then
  cat >&2 << 'EOF'
error: Apple `container` is not installed or not on PATH.
Install it from https://github.com/apple/container/releases, then run:
  container system start
EOF
  exit 127
fi

# The API server must be up before build/run; harmless if already running.
container system start > /dev/null 2>&1 || true

# Build is layer-cached, so this is near-instant once the base is built. Context
# is the collection root so the Containerfile can COPY requirements.yml from
# the single source of pins.
if [[ ${SKIP_BUILD:-0} != "1" ]]; then
  container build -t "$IMAGE" -f "$SCRIPT_DIR/Containerfile" "$ANSIBLE_DIR" >&2
fi

# Assemble one args array (never empty, so "${run_args[@]}" is safe under `set -u`
# on macOS's stock bash 3.2). ~/.ssh is mounted read-only: your keys and existing
# known_hosts are used as-is. These nodes are already in your known_hosts (you
# SSH to them), so host-key checking stays ON with nothing to write; a brand-new
# host needs one `ssh` from the Mac first, or ANSIBLE_HOST_KEY_CHECKING=false.
run_args=(run --rm)
if [[ -t 0 && -t 1 ]]; then
  run_args+=(-it)
fi
run_args+=(--volume "$ANSIBLE_DIR":/work/collection)
run_args+=(--mount "type=bind,source=$HOME/.ssh,target=/root/.ssh,readonly")
run_args+=(--workdir /work/collection)

# Forward only the credential/config env vars that are actually set, so an unset
# one is never passed as an empty override.
for v in PROXMOX_HOST PROXMOX_USER PROXMOX_TOKEN_ID PROXMOX_TOKEN_SECRET PROXMOX_PASSWORD \
  ANSIBLE_HOST_KEY_CHECKING ANSIBLE_SSH_ARGS ANSIBLE_VERBOSITY; do
  if [[ -n ${!v:-} ]]; then
    run_args+=(-e "$v")
  fi
done

run_args+=("$IMAGE")
if [[ $# -gt 0 ]]; then
  run_args+=("$@")
else
  run_args+=(/bin/bash)
fi

exec container "${run_args[@]}"
