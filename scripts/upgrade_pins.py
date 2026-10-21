"""ansible-standards §13 `upgrade`: raise every requirements.yml pin to the
highest release its bound allows, editing the file in place and keeping its
comments.
- Galaxy collections: versions come from the Galaxy v3 API; the ceiling is
    the galaxy.yml bound for that dependency, or ">=current,<next-major" when
    galaxy.yml does not list it (test-only collections).
- git collections: the newest tag (same v-prefix style, same major).
Exit 0 whether or not anything changed; the caller diffs the file. Run
`scripts/check_pins.py` (or `make conform`) afterwards.
Usage: scripts/upgrade_pins.py [--root DIR] [--dry-run]
Needs: pyyaml, packaging.
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
import yaml
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version
GALAXY = "https://galaxy.ansible.com"
TAG = re.compile(r"^(v?)(\d+\.\d+\.\d+)$")


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data if isinstance(data, dict) else {}


def galaxy_versions(fqcn: str, server: str) -> list[Version]:
    ns, name = fqcn.split(".", 1)
    url = f"{server.rstrip('/')}/api/v3/plugin/ansible/content/published/collections/index/{ns}/{name}/versions/?limit=100"
    found: list[Version] = []
    while url:
        with urllib.request.urlopen(url, timeout=30) as resp:
            page = json.load(resp)
        for item in page.get("data", []):
            try:
                found.append(Version(item["version"]))
            except (InvalidVersion, KeyError):
                continue
        nxt = (page.get("links") or {}).get("next")
        url = f"{server.rstrip('/')}{nxt}" if nxt and nxt.startswith("/") else nxt
    return found


def git_tags(url: str) -> list[tuple[str, Version]]:
    out = subprocess.run(["git", "ls-remote", "--tags", "--refs", url], capture_output=True, text=True, check=True)
    tags: list[tuple[str, Version]] = []
    for line in out.stdout.splitlines():
        ref = line.split("\t", 1)[1].removeprefix("refs/tags/")
        m = TAG.match(ref)
        if m:
            tags.append((ref, Version(m.group(2))))
    return tags


def best(versions: list[Version], spec: SpecifierSet) -> Version | None:
    allowed = [v for v in versions if not v.is_prerelease and spec.contains(v)]
    return max(allowed) if allowed else None


def same_major(current: Version) -> SpecifierSet:
    return SpecifierSet(f">={current},<{current.major + 1}.0.0")


def rewrite(path: Path, updates: dict[str, str]) -> None:
    """Replace `version:` lines inside the entries named in updates, keeping comments."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    current: str | None = None
    out: list[str] = []
    for line in lines:
        m = re.match(r"^\s*-\s+name:\s*(\S+)\s*$", line)
        if m:
            current = m.group(1).strip("'\"")
        v = re.match(r"^(\s*)version:\s*(\S+)\s*$", line)
        if v and current in updates:
            line = f"{v.group(1)}version: {updates[current]}\n"
        out.append(line)
    path.write_text("".join(out), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=".")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = Path(args.root)
    galaxy = load(root / "galaxy.yml")
    bounds = {k: str(v) for k, v in (galaxy.get("dependencies") or {}).items()}
    req_path = root / "requirements.yml"
    req = load(req_path)
    updates: dict[str, str] = {}
    for entry in req.get("collections") or []:
        if not isinstance(entry, dict) or "version" not in entry:
            continue
        name = str(entry["name"])
        current_text = str(entry["version"])
        kind = entry.get("type") or ("git" if name.endswith(".git") or "://" in name else "galaxy")
        if kind == "git":
            m = TAG.match(current_text)
            if not m:
                print(f"upgrade_pins: {name}: '{current_text}' is not a tag; left alone", file=sys.stderr)
                continue
            prefix, current = m.group(1), Version(m.group(2))
            versions = [v for ref, v in git_tags(name[4:] if name.startswith("git+") else name) if ref.startswith(prefix)]
            candidate = best(versions, same_major(current))
            if candidate and candidate > current:
                updates[name] = f"{prefix}{candidate}"
            continue
        try:
            current = Version(current_text)
        except InvalidVersion:
            print(f"upgrade_pins: {name}: '{current_text}' is not a version; left alone", file=sys.stderr)
            continue
        try:
            spec = SpecifierSet(bounds[name]) if name in bounds else same_major(current)
        except InvalidSpecifier:
            print(f"upgrade_pins: {name}: galaxy.yml bound '{bounds[name]}' invalid; left alone", file=sys.stderr)
            continue
        candidate = best(galaxy_versions(name, str(entry.get("source") or GALAXY)), spec)
        if candidate and candidate > current:
            updates[name] = str(candidate)
    if not updates:
        print("upgrade_pins: everything is at the ceiling")
        return 0
    for name, version in updates.items():
        print(f"upgrade_pins: {name} -> {version}")
    if not args.dry_run:
        rewrite(req_path, updates)
    return 0


if __name__ == "__main__":
    sys.exit(main())
