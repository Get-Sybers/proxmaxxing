"""Make every registered ISO discoverable under the name packer/Proxmox expects.
WHY THIS EXISTS (
----------------------
`iso_download_pve = true` (repo rule 9) makes PROXMOX fetch `iso_url` — and
Proxmox looks for the URL-derived BASENAME in its ISO storage. If the file is
present under a different name, Proxmox cannot see it and re-downloads the
whole image from the internet.
That is not hypothetical. On 2026-08-06 the win10 template's ISO was on the
node the entire time as `d731b3f758e61d53033aa8a67d3d8a3050aa1122.iso`, byte
for byte the right image, while Proxmox spent **53+ minutes** re-fetching
5.5 GB at ~1.4 Mbps because it wanted `19045.2006.220908-0225...iso`. Ludus
gave up and flipped the template to NOT BUILT with no log anywhere, so it
presented as a silent build failure. After hardlinking the existing file under
the expected name the same step took **16 seconds**.
The registry already knows BOTH halves of the mapping — `source_url` (hence the
name Proxmox will look for) and `current_names` (what is actually on disk).
Nothing joined them up. This does.
WHAT IT DOES
------------
For every registry entry: if the URL-derived basename is missing from the ISO
directory but a `current_names` file is present, VERIFY that file's sha256
against the registry's `iso_checksum` and hardlink it under the expected name.
Hardlink, not copy — same inode, no extra disk.
The checksum is the identity (rule 9), so it is verified before linking, never
assumed from the filename or the size. Size is only a cheap pre-filter to avoid
hashing an obviously wrong file.
Dry-run by default; `--apply` makes changes. Cannot-check is a FAILURE, never a
pass (the
a checksum mismatch all exit non-zero.
"""
from __future__ import annotations
import argparse
import hashlib
import os
import sys
from pathlib import Path
try:
    import yaml
except ImportError:
    print("FATAL: PyYAML is required to read the ISO registry", file=sys.stderr)
    sys.exit(1)
DEFAULT_REGISTRY = (
    Path(__file__).resolve().parents[3]
    / "meta/iso-inventory.yml"
)
DEFAULT_ISO_DIR = Path("/var/lib/vz/template/iso")
CHUNK = 8 * 1024 * 1024


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def registry_entries(registry: Path) -> list[dict]:
    try:
        data = yaml.safe_load(registry.read_text())
    except Exception as exc:
        print(f"FATAL: cannot read the ISO registry {registry}: {exc}", file=sys.stderr)
        sys.exit(1)
    if isinstance(data, list):
        return [e for e in data if isinstance(e, dict)]
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list) and any(isinstance(e, dict) for e in value):
                return [e for e in value if isinstance(e, dict)]
    print(f"FATAL: {registry} contains no recognisable list of ISO entries", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--iso-dir", type=Path, default=DEFAULT_ISO_DIR)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="create the hardlinks (default: report only)",
    )
    args = parser.parse_args()
    if not args.iso_dir.is_dir():
        print(f"FATAL: ISO directory {args.iso_dir} is not readable — cannot check, so this is a failure, not a pass", file=sys.stderr)
        return 1
    entries = registry_entries(args.registry)
    if not entries:
        print("FATAL: registry parsed but held zero entries — refusing to report success on nothing", file=sys.stderr)
        return 1
    checked = linked = already = skipped = 0
    problems: list[str] = []
    todo: list[str] = []
    for entry in entries:
        source_url = entry.get("source_url")
        checksum = str(entry.get("iso_checksum") or "")
        if not source_url or not checksum.startswith("sha256:"):
            skipped += 1
            continue
        expected = args.iso_dir / os.path.basename(str(source_url))
        checked += 1
        if expected.exists():
            already += 1
            continue
        wanted = checksum.split("sha256:", 1)[1].strip()
        size = entry.get("size_bytes")
        candidate = None
        for name in entry.get("current_names") or []:
            path = args.iso_dir / str(name)
            if not path.is_file():
                continue
            if size and path.stat().st_size != int(size):
                continue
            candidate = path
            break
        if candidate is None:
            skipped += 1
            continue
        actual = sha256_of(candidate)
        if actual != wanted:
            problems.append(
                f"{candidate.name}: sha256 {actual} does not match the registry's {wanted} "
                f"— NOT linked (the checksum is the identity, rule 9)"
            )
            continue
        if args.apply:
            os.link(candidate, expected)
            linked += 1
            print(f"linked {expected.name} -> {candidate.name} (verified sha256 {wanted[:16]}...)")
        else:
            todo.append(f"{expected.name} <- {candidate.name} (verified sha256 {wanted[:16]}...)")
    print(
        f"\nISO links: {checked} registered ISO(s) checked against {args.iso_dir} — "
        f"{already} already discoverable, {linked} linked, {len(todo)} needing a link, "
        f"{skipped} not present/insufficiently described"
    )
    for line in todo:
        print(f"  WOULD LINK {line}")
    if todo and not args.apply:
        print("\nRe-run with --apply to create these links (hardlinks: same inode, no extra disk).")
    for line in problems:
        print(f"  MISMATCH {line}", file=sys.stderr)
    if problems:
        print(f"\nFAILED: {len(problems)} registered ISO(s) do not match their recorded checksum", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
