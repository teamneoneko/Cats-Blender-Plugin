#!/usr/bin/env python3
"""Vendor a release of MMD Tools into Cats Blender Plugin.

MMD Tools (https://github.com/MMD-Blender/blender_mmd_tools) is bundled inside
Cats as the ``mmd_tools_local`` sub-package. Upstream ships it as a standalone
Blender extension; we cannot drop it in unchanged because:

  * Its operator id-names live in the global ``mmd_tools.*`` namespace, which
    would collide with a separately installed copy of the official MMD Tools.
    We move them to ``mmd_tools_local.*``.
  * It ships its own ``blender_manifest.toml`` (and reads its version from it).
    A nested manifest confuses Blender's extension scanner, so we strip it and
    hard-code the version instead.
  * Its Python-dependency wheels (opencc) belong in *Cats'* manifest, not a
    nested one, so we lift them out into the repo-root ``wheels/`` folder.

Everything else is a mechanical, deterministic transform, so updating is a
one-command operation instead of a manual porting session:

    python scripts/vendor_mmd_tools.py 4.5.14

Pass ``--src <dir>`` to vendor from an already-extracted release folder instead
of downloading. The script is intentionally dependency-free (std-lib only).

The rename rule is a single dot-anchored replacement: ``mmd_tools.`` ->
``mmd_tools_local.``. This is safe because it only ever matches operator
references (``bl_idname``, ``bpy.ops.mmd_tools.*``, ``layout.operator(...)``,
keymap items). Data-interop keys stored on .blend files -- ``mmd_tools_version``,
``mmd_tools_rigid_track``, the bare ``"mmd_tools"`` bone-collection property --
use an underscore or nothing after ``mmd_tools`` and are deliberately left
untouched so models stay compatible with the official MMD Tools.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.request
import zipfile

REPO = "MMD-Blender/blender_mmd_tools"
PACKAGE = "mmd_tools_local"

# Files/dirs never copied into the vendored package.
EXCLUDE_DIRS = {"__pycache__", ".vscode", ".venv", ".git"}
EXCLUDE_NAMES = {"blender_manifest.toml"}
EXCLUDE_EXTS = {".pyc", ".pyo"}

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def log(msg: str = "") -> None:
    print(msg, flush=True)


def fetch_release_zip(version: str, dest_dir: str) -> str:
    """Download the release .zip asset for ``v<version>`` and extract it.

    Returns the directory containing the extension (the folder holding
    ``__init__.py`` / ``blender_manifest.toml``).
    """
    api = f"https://api.github.com/repos/{REPO}/releases/tags/v{version}"
    log(f"Querying {api}")
    req = urllib.request.Request(api, headers={"User-Agent": "cats-vendor"})
    with urllib.request.urlopen(req) as resp:
        release = json.load(resp)

    assets = [a for a in release.get("assets", []) if a["name"].endswith(".zip")]
    if not assets:
        raise SystemExit(f"No .zip asset found on release v{version}")
    asset = assets[0]
    url = asset["browser_download_url"]
    zip_path = os.path.join(dest_dir, asset["name"])
    log(f"Downloading {asset['name']} ({asset['size']} bytes)")
    req = urllib.request.Request(url, headers={"User-Agent": "cats-vendor"})
    with urllib.request.urlopen(req) as resp, open(zip_path, "wb") as f:
        shutil.copyfileobj(resp, f)

    extract_dir = os.path.join(dest_dir, "extracted")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)
    return find_package_root(extract_dir)


def find_package_root(root: str) -> str:
    """Locate the folder containing the extension's __init__.py + manifest."""
    for dirpath, _dirnames, filenames in os.walk(root):
        if "__init__.py" in filenames and "blender_manifest.toml" in filenames:
            return dirpath
    raise SystemExit(f"Could not find extension root under {root}")


def read_manifest(src: str) -> dict:
    manifest_path = os.path.join(src, "blender_manifest.toml")
    with open(manifest_path, "rb") as f:
        try:
            import tomllib

            return tomllib.load(f)
        except ModuleNotFoundError:  # pragma: no cover - py<3.11 fallback
            pass
    # Minimal fallback parser for the fields we use.
    text = open(manifest_path, encoding="utf-8").read()
    version = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    wheels = re.findall(r'"(\./wheels/[^"]+)"', text)
    return {"version": version.group(1) if version else "", "wheels": wheels}


def check_absolute_imports(src: str) -> list[str]:
    """Warn about absolute ``import mmd_tools`` that the sub-package model can't
    satisfy. Upstream currently uses only relative imports; a regression here
    would need the script (or a patch) to relativize them."""
    offenders = []
    pattern = re.compile(r"^\s*(?:from|import)\s+mmd_tools(?![_.\w])", re.M)
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for name in filenames:
            if not name.endswith(".py"):
                continue
            path = os.path.join(dirpath, name)
            text = open(path, encoding="utf-8").read()
            if pattern.search(text):
                offenders.append(os.path.relpath(path, src))
    return offenders


def transform_python(text: str, is_init: bool, version: str) -> str:
    # Operator namespace: mmd_tools.<x> -> mmd_tools_local.<x>. Dot-anchored so
    # interop keys like mmd_tools_version / "mmd_tools" are left alone.
    text = text.replace("mmd_tools.", f"{PACKAGE}.")

    if is_init:
        # Upstream reads its version from the (now stripped) manifest. Replace
        # that block with a hard-coded constant.
        block = re.compile(
            r'with open\(os\.path\.join\(PACKAGE_PATH, "blender_manifest\.toml"\).*?'
            r'MMD_TOOLS_VERSION\s*=\s*manifest\["version"\]',
            re.S,
        )
        replacement = (
            "# Vendored into Cats Blender Plugin -- version hard-coded because\n"
            "# the upstream blender_manifest.toml is stripped during vendoring.\n"
            f'MMD_TOOLS_VERSION = "{version}"'
        )
        text, n = block.subn(replacement, text)
        if n == 0 and 'MMD_TOOLS_VERSION = "' not in text:
            raise SystemExit(
                "Could not patch version block in __init__.py -- upstream layout "
                "changed; update vendor_mmd_tools.py."
            )
    return text


def vendor(src: str, version: str) -> None:
    manifest = read_manifest(src)
    manifest_version = manifest.get("version", "")
    if manifest_version and version and manifest_version != version:
        log(f"WARNING: requested {version} but manifest says {manifest_version}")
    version = manifest_version or version

    offenders = check_absolute_imports(src)
    if offenders:
        log("WARNING: absolute 'import mmd_tools' found (sub-package model needs")
        log("         relative imports). Files:")
        for f in offenders:
            log(f"           {f}")

    dest = os.path.join(REPO_ROOT, PACKAGE)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    os.makedirs(dest)

    py_count = 0
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        rel = os.path.relpath(dirpath, src)
        # 'wheels/' is lifted into the repo-root wheels/ dir, not vendored.
        if rel == "wheels" or rel.startswith("wheels" + os.sep):
            continue
        out_dir = os.path.join(dest, rel) if rel != "." else dest
        os.makedirs(out_dir, exist_ok=True)
        for name in filenames:
            if name in EXCLUDE_NAMES or os.path.splitext(name)[1] in EXCLUDE_EXTS:
                continue
            src_file = os.path.join(dirpath, name)
            out_file = os.path.join(out_dir, name)
            if name.endswith(".py"):
                text = open(src_file, encoding="utf-8").read()
                text = transform_python(text, is_init=(rel == "." and name == "__init__.py"), version=version)
                with open(out_file, "w", encoding="utf-8", newline="\n") as f:
                    f.write(text)
                py_count += 1
            else:
                shutil.copy2(src_file, out_file)

    wheels = lift_wheels(src)

    log("")
    log(f"Vendored MMD Tools {version} -> {os.path.relpath(dest, REPO_ROOT)}/")
    log(f"  Python files transformed: {py_count}")
    log(f"  Wheels lifted to wheels/: {len(wheels)}")
    if wheels:
        log("")
        log("Add/verify this in the Cats root blender_manifest.toml:")
        log("wheels = [")
        for w in wheels:
            log(f'  "./wheels/{w}",')
        log("]")


def lift_wheels(src: str) -> list[str]:
    wheels_src = os.path.join(src, "wheels")
    if not os.path.isdir(wheels_src):
        return []
    wheels_dst = os.path.join(REPO_ROOT, "wheels")
    os.makedirs(wheels_dst, exist_ok=True)
    lifted = []
    for name in sorted(os.listdir(wheels_src)):
        if name.endswith(".whl"):
            shutil.copy2(os.path.join(wheels_src, name), os.path.join(wheels_dst, name))
            lifted.append(name)
    return lifted


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(description="Vendor MMD Tools into Cats.")
    parser.add_argument("version", help="Release version, e.g. 4.5.14")
    parser.add_argument(
        "--src",
        help="Vendor from an already-extracted release folder instead of downloading.",
    )
    args = parser.parse_args(argv)

    if args.src:
        src = find_package_root(args.src) if not os.path.exists(
            os.path.join(args.src, "blender_manifest.toml")
        ) else args.src
        vendor(src, args.version)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            src = fetch_release_zip(args.version, tmp)
            vendor(src, args.version)


if __name__ == "__main__":
    main(sys.argv[1:])
