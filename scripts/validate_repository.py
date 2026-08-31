#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import plistlib
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IGNORED_PARTS = {".git", ".venv", "node_modules", "__pycache__"}
ACTION_PIN = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)")
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
SOURCE_REVISION = "1803940623da0ba648084b5ba0b1265b2b854ae4"
CC_LICENSE_SHA256 = "fd3a263fe19ed8faa9068b43abaebafc02c77897b0c6fc09abc04bb592e5f16e"
DEPRECATED_REPOSITORY_NAME = "Remote-SSH" + "-Tunnel"


def repository_files() -> list[Path]:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required for repository validation")
    completed = subprocess.run(  # noqa: S603 - executable is resolved; arguments are fixed.
        [git, "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [
        ROOT / relative.decode()
        for relative in completed.stdout.split(b"\0")
        if relative and not any(part in IGNORED_PARTS for part in Path(relative.decode()).parts)
    ]


def check_required_files(errors: list[str]) -> None:
    required = [
        "LICENSE",
        "README.md",
        "SECURITY.md",
        "THIRD_PARTY_NOTICES.md",
        "package-lock.json",
        "pyproject.toml",
        ".github/workflows/ci.yml",
        ".github/workflows/codeql.yml",
        ".github/workflows/secret-scan.yml",
        "assets/vscode-interface/LICENSE",
        "assets/vscode-interface/SOURCE.json",
    ]
    for relative in required:
        if not (ROOT / relative).is_file():
            errors.append(f"missing required file: {relative}")


def check_json(errors: list[str]) -> None:
    for path in repository_files():
        if path.suffix == ".json":
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                errors.append(f"invalid JSON: {path.relative_to(ROOT)}: {error}")


def check_action_pins(errors: list[str]) -> None:
    for path in (ROOT / ".github/workflows").glob("*.yml"):
        for line_number, line in enumerate(path.read_text().splitlines(), start=1):
            match = ACTION_PIN.match(line)
            if not match:
                continue
            reference = match.group(1)
            if reference.startswith("./") or reference.startswith("docker://"):
                continue
            if "@" not in reference or not FULL_SHA.fullmatch(reference.rsplit("@", 1)[1]):
                errors.append(
                    f"mutable action reference: {path.relative_to(ROOT)}:{line_number}: {reference}"
                )


def check_attribution_boundary(errors: list[str]) -> None:
    source_path = ROOT / "assets/vscode-interface/SOURCE.json"
    license_path = ROOT / "assets/vscode-interface/LICENSE"
    try:
        source = json.loads(source_path.read_text())
    except (OSError, json.JSONDecodeError):
        return

    if source.get("source_revision") != SOURCE_REVISION:
        errors.append("VS Code asset source revision is not the approved pinned commit")
    if source.get("license") != "CC-BY-4.0" or source.get("modified") is not True:
        errors.append("VS Code asset attribution must declare CC-BY-4.0 and modifications")
    if license_path.is_file():
        digest = hashlib.sha256(license_path.read_bytes()).hexdigest()
        if digest != CC_LICENSE_SHA256:
            errors.append("CC-BY-4.0 license does not match the pinned upstream license")

    forbidden_suffixes = {".vsix", ".exe", ".dll", ".dylib", ".so", ".node"}
    asset_root = ROOT / "assets/vscode-interface"
    for path in asset_root.rglob("*"):
        if path.is_symlink():
            errors.append(f"symlink is not allowed in attributed assets: {path.relative_to(ROOT)}")
        if path.is_file() and path.suffix.lower() in forbidden_suffixes:
            errors.append(f"binary is not allowed in attributed assets: {path.relative_to(ROOT)}")


def check_repository_sanitation(errors: list[str]) -> None:
    forbidden_names = {".DS_Store", ".env"}
    private_path = re.compile(r"/(?:Users|home)/(?!CHANGE_ME(?:/|$))[^/\s]+/")
    token_pattern = re.compile(r"(?:ghp|github_pat)_[A-Za-z0-9_]{20,}")

    for path in repository_files():
        relative = path.relative_to(ROOT)
        if path.name in forbidden_names:
            errors.append(f"private/generated file is tracked: {relative}")
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"unexpected binary file: {relative}")
            continue
        if token_pattern.search(text):
            errors.append(f"token-shaped value found: {relative}")
        if DEPRECATED_REPOSITORY_NAME in text:
            errors.append(f"deprecated repository name found: {relative}")
        if private_path.search(text):
            errors.append(f"private absolute path found: {relative}")
        if ("you" + "tube") in text.lower():
            errors.append(f"unrelated project reference found: {relative}")


def check_runtime_contract(errors: list[str]) -> None:
    package = json.loads((ROOT / "package.json").read_text())
    lock = json.loads((ROOT / "package-lock.json").read_text())
    if package.get("version") != "0.1.0" or lock.get("version") != "0.1.0":
        errors.append("package.json and package-lock.json versions must match 0.1.0")
    if package.get("overrides", {}).get("uuid") != "11.1.1":
        errors.append("the audited uuid compatibility override is missing")

    relay = (ROOT / "src/relay/config.js").read_text()
    if 'export const LOOPBACK_HOST = "127.0.0.1";' not in relay:
        errors.append("relay loopback invariant is missing")

    binary = ROOT / "bin/remote-ssh-tunnel-relay.js"
    if binary.is_file() and not binary.stat().st_mode & stat.S_IXUSR:
        errors.append("relay executable is not marked executable")

    requirement = (ROOT / "requirements.txt").read_text().strip()
    pyproject = (ROOT / "pyproject.toml").read_text()
    pinned = re.search(r'"((?:msgpack==)[0-9][0-9.]*)"', pyproject)
    if pinned is None or requirement != pinned.group(1):
        errors.append("requirements.txt must pin the same msgpack version as pyproject.toml")


def check_plist(errors: list[str]) -> None:
    path = ROOT / "deploy/launchd/com.remote-ssh-tunnel.relay.plist.example"
    try:
        with path.open("rb") as stream:
            plistlib.load(stream)
    except (OSError, plistlib.InvalidFileException) as error:
        errors.append(f"invalid launchd plist: {error}")


def main() -> int:
    errors: list[str] = []
    check_required_files(errors)
    check_json(errors)
    check_action_pins(errors)
    check_attribution_boundary(errors)
    check_repository_sanitation(errors)
    check_runtime_contract(errors)
    check_plist(errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("repository validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
