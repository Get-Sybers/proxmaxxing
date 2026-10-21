"""ansible-standards §2/§3/§13 pin check.
Fails (exit 1) unless:
- every galaxy.yml dependency has a requirements.yml entry pinned to one
    exact X.Y.Z that lies inside the galaxy.yml bound;
- every requirements.yml collection pin is exact (no ranges, '*', 'latest'),
    and every git-sourced one points at a tag or full commit SHA, never a
    branch; with --resolve-git the ref is checked with `git ls-remote`;
- meta/runtime.yml declares one requires_ansible floor, and every role's
    meta/main.yml min_ansible_version agrees with it;
- no role meta/main.yml dependency carries its own version literal.
Usage: scripts/check_pins.py [--resolve-git] [--root DIR]
Needs: pyyaml, packaging (pinned in .pre-commit-config.yaml).
"""
from __future__ import annotations
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path
import yaml
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version
EXACT = re.compile(r"^\d+\.\d+\.\d+$")
TAG = re.compile(r"^v?\d+\.\d+\.\d+$")
SHA = re.compile(r"^[0-9a-f]{40}$")
GIT_URL = re.compile(r"^(git\+)?(https?://|git@|ssh://)")
errors: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)
    print(f"check_pins: {msg}", file=sys.stderr)


def load(path: Path) -> dict:
    if not path.is_file():
        err(f"{path}: missing")
        return {}
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data if isinstance(data, dict) else {}


def floor_of(spec: SpecifierSet) -> Version | None:
    floors = [Version(s.version) for s in spec if s.operator in (">=", "==", "~=")]
    return min(floors) if floors else None


def check_requirements(root: Path, resolve_git: bool) -> dict[str, str]:
    """Return {fqcn: exact_version} for Galaxy-sourced collections."""
    req = load(root / "requirements.yml")
    pins: dict[str, str] = {}
    collections = req.get("collections") or []
    if not isinstance(collections, list):
        err("requirements.yml: 'collections' must be a list")
        return pins
    for entry in collections:
        if isinstance(entry, str):
            err(f"requirements.yml: '{entry}' has no version pin (bare string entry)")
            continue
        name = str(entry.get("name", ""))
        version = entry.get("version")
        kind = entry.get("type") or ("git" if GIT_URL.match(name) or name.endswith(".git") else "galaxy")
        if version is None:
            err(f"requirements.yml: {name} has no 'version' (standards §2: exact pins only)")
            continue
        version = str(version)
        if kind == "git":
            if SHA.match(version):
                if resolve_git:
                    check_git_sha(name, version)
            elif TAG.match(version):
                if resolve_git:
                    check_git_tag(name, version)
            else:
                err(f"requirements.yml: {name} version '{version}' is a branch or range; pin a tag or commit SHA")
            continue
        if kind != "galaxy":
            err(f"requirements.yml: {name} type '{kind}' is not sanctioned (galaxy or git only, §25)")
            continue
        if not EXACT.match(version):
            err(f"requirements.yml: {name} version '{version}' is not an exact X.Y.Z")
            continue
        pins[name] = version
    return pins


def git_url(name: str) -> str:
    url = name[4:] if name.startswith("git+") else name
    return url.split("#", 1)[0]


def check_git_tag(name: str, tag: str) -> None:
    url = git_url(name)
    out = subprocess.run(
        ["git", "ls-remote", "--tags", "--refs", url, f"refs/tags/{tag}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0 or not out.stdout.strip():
        err(f"requirements.yml: tag {tag} not found at {url} ({out.stderr.strip() or 'no such ref'})")


def check_git_sha(name: str, sha: str) -> None:
    url = git_url(name)
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "init", "-q", tmp], check=True)
        out = subprocess.run(
            ["git", "-C", tmp, "fetch", "--quiet", "--depth", "1", url, sha],
            capture_output=True,
            text=True,
            check=False,
        )
    if out.returncode != 0:
        err(f"requirements.yml: commit {sha} not fetchable from {url} ({out.stderr.strip()})")


def check_galaxy(root: Path, pins: dict[str, str]) -> None:
    galaxy = load(root / "galaxy.yml")
    deps = galaxy.get("dependencies") or {}
    if not isinstance(deps, dict):
        err("galaxy.yml: 'dependencies' must be a mapping")
        return
    for fqcn, spec_text in deps.items():
        spec_text = str(spec_text)
        if spec_text.strip() in ("*", ""):
            err(f"galaxy.yml: {fqcn} is unbounded ('*'); use >=x.y.z,<next-major (§2)")
            continue
        try:
            spec = SpecifierSet(spec_text)
        except InvalidSpecifier:
            err(f"galaxy.yml: {fqcn} spec '{spec_text}' is not a valid specifier")
            continue
        if not any(s.operator == "<" for s in spec):
            err(f"galaxy.yml: {fqcn} spec '{spec_text}' has no upper bound (<next-major)")
        pin = pins.get(fqcn)
        if pin is None:
            err(f"requirements.yml: no exact pin for galaxy.yml dependency {fqcn}")
            continue
        if not spec.contains(Version(pin), prereleases=False):
            err(f"requirements.yml: {fqcn} pin {pin} is outside the galaxy.yml bound '{spec_text}'")
    for fqcn in pins:
        if fqcn not in deps:
            print(f"check_pins: note: {fqcn} is pinned but not a galaxy.yml dependency (test-only?)", file=sys.stderr)


def check_runtime_and_roles(root: Path) -> None:
    runtime = load(root / "meta" / "runtime.yml")
    spec_text = str(runtime.get("requires_ansible", "")).strip()
    if not spec_text:
        err("meta/runtime.yml: requires_ansible is missing")
        return
    try:
        spec = SpecifierSet(spec_text)
    except InvalidSpecifier:
        err(f"meta/runtime.yml: requires_ansible '{spec_text}' is not a valid specifier")
        return
    floor = floor_of(spec)
    if floor is None:
        err(f"meta/runtime.yml: requires_ansible '{spec_text}' has no floor (>=x.y.z)")
        return
    for meta in sorted(root.glob("roles/*/meta/main.yml")):
        data = load(meta)
        info = data.get("galaxy_info") or {}
        mav = str(info.get("min_ansible_version", "")).strip()
        if not mav:
            err(f"{meta}: galaxy_info.min_ansible_version missing (§2/§3)")
        else:
            try:
                if Version(mav) != floor:
                    err(f"{meta}: min_ansible_version {mav} != requires_ansible floor {floor}")
            except InvalidVersion:
                err(f"{meta}: min_ansible_version '{mav}' is not a version")
        if "dependencies" not in data:
            err(f"{meta}: explicit 'dependencies:' list required, even if empty (§3)")
            continue
        for dep in data.get("dependencies") or []:
            if isinstance(dep, dict) and "version" in dep:
                err(f"{meta}: dependency {dep.get('role') or dep.get('name')} carries a version literal; pin in requirements.yml (§2)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--resolve-git", action="store_true", help="verify git refs with git ls-remote / fetch")
    parser.add_argument("--root", default=".", help="collection root (default: .)")
    args = parser.parse_args()
    root = Path(args.root)
    pins = check_requirements(root, args.resolve_git)
    check_galaxy(root, pins)
    check_runtime_and_roles(root)
    if errors:
        print(f"check_pins: FAIL ({len(errors)} problem(s))", file=sys.stderr)
        return 1
    print("check_pins: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
