"""Decide which CI lanes a change needs (docs/04 §1).

Prints GitHub Actions outputs, one ``key=value`` per line:

  heavy=true|false   run the collection gate (ansible-lint, pins, sanity, changelog, build)
  scenarios=<json>   the molecule scenarios the change can affect
  lanes=<json>       those scenarios split into balanced lanes ([] when none)

On a pull request the files changed between the base and head commits decide.
On every other event (push to main, the nightly schedule, workflow_dispatch)
everything runs. When the diff cannot be computed, everything runs: the only
safe failure mode is "too much".

Scenario selection keeps no hand-written table. A scenario is affected when a
file under it changed, or when a role it drives changed — the roles are found
by scanning the scenario's playbooks for ``get_sybers.cluster.<role>``
references and following the same references through those roles' task files
(so a change to ``cluster_preflight`` selects every scenario that includes the
admission gate). A change to anything
every scenario shares — the molecule base config and Dockerfile, the collection
metadata, the pins, this script, the workflow — selects every scenario. Docs,
changelog fragments, the container runner and the community files never need
the heavy gates.

The collection is the repository root (no monorepo subdirectory), so every
path below is repository-relative with no prefix.

Usage: python3 scripts/molecule_lanes.py --event pull_request --base <sha> --head <sha> [--lanes 4]
       python3 scripts/molecule_lanes.py --event push
Needs: python3 and git only.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

COLLECTION = Path(__file__).resolve().parent.parent
REPO = COLLECTION
ROLE_REF = re.compile(r"get_sybers\.cluster\.([a-z][a-z0-9_]*)")

# A change under any of these (repo-relative; a trailing slash means a tree)
# affects every scenario.
SHARED = (
    "extensions/molecule/config.yml",
    "extensions/molecule/Dockerfile",
    "plugins/",
    "meta/",
    "galaxy.yml",
    "requirements.yml",
    "test-requirements.txt",
    "ansible.cfg",
    "scripts/molecule_lanes.py",
    ".github/workflows/ci.yml",
)
# A change that only touches these never needs the heavy gates.
LIGHT = re.compile(r"(\.md$|^doc/|^docs/|^container/|^changelogs/fragments/|^(AUTHORS|MAINTAINERS)$)")


def scenarios() -> list[str]:
    root = COLLECTION / "extensions" / "molecule"
    return sorted(p.parent.name for p in root.glob("*/molecule.yml"))


def refs_in(paths) -> set[str]:
    found: set[str] = set()
    for path in paths:
        try:
            found.update(ROLE_REF.findall(path.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            continue
    return found


def role_graph() -> tuple[set[str], dict[str, set[str]]]:
    roles = {p.name for p in (COLLECTION / "roles").iterdir() if p.is_dir()}
    graph = {}
    for role in roles:
        graph[role] = {r for r in refs_in((COLLECTION / "roles" / role).rglob("*.yml")) if r in roles and r != role}
    return roles, graph


def closure(start: set[str], graph: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    stack = list(start)
    while stack:
        role = stack.pop()
        if role in seen:
            continue
        seen.add(role)
        stack.extend(graph.get(role, ()))
    return seen


def scenario_roles(name: str, roles: set[str], graph: dict[str, set[str]]) -> set[str]:
    direct = {r for r in refs_in((COLLECTION / "extensions" / "molecule" / name).rglob("*.yml")) if r in roles}
    return closure(direct, graph)


def changed_files(base: str, head: str) -> list[str] | None:
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", f"{base}...{head}"],
            cwd=REPO, check=True, capture_output=True, text=True,
        ).stdout
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"molecule_lanes: cannot diff {base}...{head} ({exc}); running everything", file=sys.stderr)
        return None
    return [line.strip() for line in out.splitlines() if line.strip()]


def touches(changed: list[str], prefix: str) -> bool:
    if prefix.endswith("/"):
        return any(f.startswith(prefix) for f in changed)
    return prefix in changed


def plan(changed: list[str] | None) -> tuple[bool, list[str]]:
    every = scenarios()
    if changed is None:
        return True, every
    heavy = any(not LIGHT.search(f) for f in changed)
    if any(touches(changed, p) for p in SHARED):
        return True, every
    roles, graph = role_graph()
    changed_roles = {f.split("/")[1] for f in changed if f.startswith("roles/") and f.count("/") >= 2}
    picked = [
        s for s in every
        if touches(changed, f"extensions/molecule/{s}/") or scenario_roles(s, roles, graph) & changed_roles
    ]
    return heavy or bool(picked), picked


def lanes_of(names: list[str], count: int) -> list[list[str]]:
    count = max(1, min(count, len(names))) if names else 0
    return [names[i::count] for i in range(count)] if count else []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--event", required=True, help="the GitHub event name")
    parser.add_argument("--base", default="", help="base commit (pull_request only)")
    parser.add_argument("--head", default="", help="head commit (pull_request only)")
    parser.add_argument("--lanes", type=int, default=4, help="how many parallel molecule lanes at most")
    args = parser.parse_args()
    changed = changed_files(args.base, args.head) if args.event == "pull_request" and args.base and args.head else None
    heavy, picked = plan(changed)
    if changed is not None:
        print(f"molecule_lanes: {len(changed)} changed file(s); heavy={heavy}; scenarios={picked or 'none'}", file=sys.stderr)
    print(f"heavy={'true' if heavy else 'false'}")
    print(f"scenarios={json.dumps(picked)}")
    print(f"lanes={json.dumps(lanes_of(picked, args.lanes))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
