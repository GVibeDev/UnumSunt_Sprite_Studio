from __future__ import annotations

import argparse
import importlib.metadata as metadata
import json
from pathlib import Path
import re
import shutil
import sys

PACKAGE_CANDIDATES = (
    "PySide6",
    "PySide6_Essentials",
    "PySide6_Addons",
    "shiboken6",
    "opencv-python",
    "numpy",
    "Pillow",
    "PyInstaller",
)
REQUIRED_PACKAGES = {"PySide6", "shiboken6", "opencv-python", "numpy", "Pillow", "PyInstaller"}
LICENSE_NAMES = {
    "license",
    "license.txt",
    "license.md",
    "copying",
    "copying.txt",
    "notice",
    "notice.txt",
    "copyright",
}


def _safe_component(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._+-]+", "_", value).strip("._") or "unknown"


def _looks_like_license(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    return path.name.lower() in LICENSE_NAMES or "licenses" in parts or "license" in path.name.lower() or "copying" in path.name.lower() or "notice" in path.name.lower()


def _copy_distribution_licenses(dist: metadata.Distribution, target: Path) -> list[str]:
    copied: list[str] = []
    for item in dist.files or []:
        rel = Path(str(item))
        if not _looks_like_license(rel):
            continue
        source = Path(dist.locate_file(item))
        if not source.is_file():
            continue
        # Flatten into a package-specific directory while preserving enough of the
        # original path to distinguish multiple notices.
        relative_name = "__".join(_safe_component(part) for part in rel.parts[-4:])
        destination = target / relative_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(destination.name)
    return sorted(set(copied))


def _copy_python_license(target: Path) -> list[str]:
    candidates = []
    for root in {Path(sys.base_prefix), Path(sys.prefix)}:
        for name in ("LICENSE.txt", "LICENSE", "LICENSE.rst"):
            candidates.append(root / name)
    copied: list[str] = []
    for source in candidates:
        if source.is_file():
            destination = target / "CPython" / source.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied.append(str(destination.relative_to(target)))
            break
    return copied


def collect(output: Path) -> dict:
    if output.exists():
        shutil.rmtree(output)
    third_party = output / "THIRD_PARTY_LICENSES"
    third_party.mkdir(parents=True, exist_ok=True)

    inventory: dict = {
        "schema": "unum-sunt-third-party-license-inventory-v1",
        "python": {
            "version": sys.version.split()[0],
            "executable": sys.executable,
            "license_files": _copy_python_license(third_party),
        },
        "packages": [],
        "missing_required_packages": [],
        "packages_without_discovered_license_files": [],
    }

    for name in PACKAGE_CANDIDATES:
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            if name in REQUIRED_PACKAGES:
                inventory["missing_required_packages"].append(name)
            continue

        canonical = dist.metadata.get("Name") or name
        version = dist.version
        package_dir = third_party / f"{_safe_component(canonical)}-{_safe_component(version)}"
        package_dir.mkdir(parents=True, exist_ok=True)
        copied = _copy_distribution_licenses(dist, package_dir)
        license_metadata = (dist.metadata.get("License-Expression") or dist.metadata.get("License") or "").strip()
        inventory["packages"].append(
            {
                "name": canonical,
                "version": version,
                "license_metadata": license_metadata[:2000],
                "license_files": copied,
            }
        )
        if not copied:
            inventory["packages_without_discovered_license_files"].append(canonical)

    output.mkdir(parents=True, exist_ok=True)
    (output / "INVENTORY.json").write_text(json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "README.txt").write_text(
        "This directory was generated from the exact Python build environment used for the Windows Core.\n"
        "It preserves license/notice files discovered in the relevant installed distributions.\n"
        "See ../THIRD_PARTY_NOTICES.txt in the installed application for project-level context.\n",
        encoding="utf-8",
    )
    return inventory


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="build/legal")
    args = parser.parse_args()
    inventory = collect(Path(args.output).resolve())
    missing = inventory["missing_required_packages"]
    if missing:
        print("Missing required build packages: " + ", ".join(missing), file=sys.stderr)
        return 2
    print(f"Collected license metadata for {len(inventory['packages'])} packages into {args.output}")
    if inventory["packages_without_discovered_license_files"]:
        print("WARNING: no explicit license files discovered for: " + ", ".join(inventory["packages_without_discovered_license_files"]))
    if not inventory["python"]["license_files"]:
        print("WARNING: CPython LICENSE file not found under the active interpreter prefix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
