#!/usr/bin/env python3
"""Detect or install the draw.io desktop CLI for diagram export.

Usage:
    python ensure_drawio.py              # auto-detect or prompt to install
    python ensure_drawio.py --check      # exit 0 if found, 1 if not (no install)
    python ensure_drawio.py --version    # print installed version
    python ensure_drawio.py --list       # list available releases

Prints the resolved binary path to stdout on success.
All interactive prompts go to stderr so stdout is safe to capture.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional

# ── Constants ────────────────────────────────────────────────────────────────

GITHUB_API_RELEASES = "https://api.github.com/repos/jgraph/drawio-desktop/releases"
INSTALL_DIR = Path.home() / ".claude" / "tools" / "drawio"

# Known install locations per platform (checked in order)
KNOWN_PATHS: dict[str, list[str]] = {
    "windows": [
        r"C:\Program Files\draw.io\draw.io.exe",
        r"D:\Program Files\draw.io\draw.io.exe",
        r"C:\Program Files (x86)\draw.io\draw.io.exe",
    ],
    "darwin": [
        "/Applications/draw.io.app/Contents/MacOS/draw.io",
    ],
    "linux": [],  # typically on PATH via snap/apt/flatpak
}


# ── Platform detection ───────────────────────────────────────────────────────

def detect_platform() -> tuple[str, str]:
    """Return (os_name, arch) normalized for asset matching.

    os_name: 'windows' | 'darwin' | 'linux'
    arch:    'x64' | 'arm64' | 'ia32'
    """
    system = platform.system().lower()
    if system == "windows":
        os_name = "windows"
    elif system == "darwin":
        os_name = "darwin"
    else:
        os_name = "linux"

    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        arch = "x64"
    elif machine in ("aarch64", "arm64"):
        arch = "arm64"
    elif machine in ("i386", "i686", "x86"):
        arch = "ia32"
    else:
        arch = "x64"  # fallback

    return os_name, arch


# ── Binary discovery ─────────────────────────────────────────────────────────

def find_on_path() -> Optional[Path]:
    """Check if drawio/draw.io is on PATH."""
    for name in ("drawio", "draw.io"):
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def find_in_known_paths(os_name: str) -> Optional[Path]:
    """Check platform-specific known install locations."""
    for p in KNOWN_PATHS.get(os_name, []):
        path = Path(p)
        if path.is_file():
            return path
    return None


def find_in_install_dir(os_name: str) -> Optional[Path]:
    """Check our own managed install directory."""
    if not INSTALL_DIR.is_dir():
        return None

    if os_name == "windows":
        candidate = INSTALL_DIR / "draw.io.exe"
    elif os_name == "darwin":
        candidate = INSTALL_DIR / "draw.io.app" / "Contents" / "MacOS" / "draw.io"
    else:
        # Linux AppImage — find any AppImage file
        for f in INSTALL_DIR.iterdir():
            if f.name.endswith(".AppImage") and f.is_file():
                return f
        return None

    return candidate if candidate.is_file() else None


def find_drawio() -> Optional[Path]:
    """Try all discovery methods, return first hit."""
    os_name, _ = detect_platform()

    # 1. Our managed install (highest priority — known-good)
    result = find_in_install_dir(os_name)
    if result:
        return result

    # 2. System PATH
    result = find_on_path()
    if result:
        return result

    # 3. Known install locations
    result = find_in_known_paths(os_name)
    if result:
        return result

    return None


# ── Version detection ────────────────────────────────────────────────────────

def get_installed_version(binary: Path) -> Optional[str]:
    """Get version string from draw.io binary."""
    try:
        result = subprocess.run(
            [str(binary), "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        output = (result.stdout or result.stderr).strip()
        # Output is typically just the version number like "29.6.1"
        for line in output.splitlines():
            line = line.strip()
            if line and line[0].isdigit():
                return line
        return output if output else None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


# ── GitHub releases ──────────────────────────────────────────────────────────

def fetch_releases(limit: int = 10) -> list[dict]:
    """Fetch recent releases from GitHub API."""
    url = f"{GITHUB_API_RELEASES}?per_page={limit}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def pick_asset(release: dict, os_name: str, arch: str) -> Optional[dict]:
    """Select the best portable asset for the given platform and architecture."""
    assets = release.get("assets", [])
    candidates = []

    for asset in assets:
        name = asset["name"].lower()

        if os_name == "windows":
            # Prefer the zip (portable), not installer/msi
            if arch == "arm64":
                if "arm64" in name and "no-installer" in name:
                    candidates.append((0, asset))  # highest priority
                elif "arm64" in name and name.endswith(".zip"):
                    candidates.append((1, asset))
            elif arch == "ia32":
                if "ia32" in name and "32bit" in name and name.endswith(".exe"):
                    candidates.append((0, asset))
            else:  # x64
                # draw.io-VERSION-windows.zip is the x64 portable zip
                if name.endswith("-windows.zip"):
                    candidates.append((0, asset))

        elif os_name == "darwin":
            # Prefer zip over dmg (easier to extract programmatically)
            if arch == "arm64":
                if "arm64" in name and name.endswith(".zip") and "blockmap" not in name:
                    candidates.append((0, asset))
                elif "universal" in name and name.endswith(".dmg") and "blockmap" not in name:
                    candidates.append((2, asset))
            else:  # x64
                if "x64" in name and name.endswith(".zip") and "blockmap" not in name:
                    candidates.append((0, asset))
                elif "universal" in name and name.endswith(".dmg") and "blockmap" not in name:
                    candidates.append((2, asset))

        elif os_name == "linux":
            # AppImage is the portable option
            if arch == "arm64":
                if "arm64" in name and name.endswith(".appimage"):
                    candidates.append((0, asset))
            else:  # x64
                if "x86_64" in name and name.endswith(".appimage"):
                    candidates.append((0, asset))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


# ── Download and install ─────────────────────────────────────────────────────

def download_file(url: str, dest: Path, name: str = "") -> None:
    """Download a file with progress reporting to stderr."""
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=300) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        dest.parent.mkdir(parents=True, exist_ok=True)

        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = downloaded * 100 // total
                    mb = downloaded / (1024 * 1024)
                    total_mb = total / (1024 * 1024)
                    print(
                        f"\r  Downloading {name}: {mb:.1f}/{total_mb:.1f} MB ({pct}%)",
                        end="",
                        file=sys.stderr,
                    )
        print(file=sys.stderr)


def install_drawio(release: dict, os_name: str, arch: str) -> Path:
    """Download and install the portable draw.io for the current platform.

    Returns the path to the binary.
    """
    asset = pick_asset(release, os_name, arch)
    if not asset:
        print(f"Error: no suitable asset found for {os_name}/{arch}", file=sys.stderr)
        sys.exit(1)

    asset_name = asset["name"]
    download_url = asset["browser_download_url"]

    # Clean install dir
    if INSTALL_DIR.exists():
        shutil.rmtree(INSTALL_DIR)
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / asset_name
        download_file(download_url, tmp_path, asset_name)

        if asset_name.lower().endswith(".zip"):
            print("  Extracting...", file=sys.stderr)
            with zipfile.ZipFile(tmp_path) as zf:
                zf.extractall(INSTALL_DIR)

        elif asset_name.lower().endswith(".appimage"):
            dest = INSTALL_DIR / asset_name
            shutil.copy2(tmp_path, dest)
            dest.chmod(dest.stat().st_mode | stat.S_IEXEC)

        elif asset_name.lower().endswith(".exe"):
            # Windows ARM no-installer single exe
            dest = INSTALL_DIR / "draw.io.exe"
            shutil.copy2(tmp_path, dest)

        elif asset_name.lower().endswith(".dmg"):
            print(
                "  Note: DMG downloaded. Please mount and copy draw.io.app manually to:",
                file=sys.stderr,
            )
            print(f"    {INSTALL_DIR}", file=sys.stderr)
            dest = INSTALL_DIR / asset_name
            shutil.copy2(tmp_path, dest)

    # Write a version marker
    version = release.get("tag_name", "unknown").lstrip("v")
    (INSTALL_DIR / ".version").write_text(version)

    binary = find_in_install_dir(os_name)
    if not binary:
        print(f"Error: installed but could not locate binary in {INSTALL_DIR}", file=sys.stderr)
        sys.exit(1)

    return binary


# ── Interactive prompts (all on stderr) ──────────────────────────────────────

def prompt_choice(question: str, options: list[str], default: int = 0) -> int:
    """Prompt the user to pick from a list. Returns 0-based index."""
    print(f"\n{question}", file=sys.stderr)
    for i, opt in enumerate(options):
        marker = " (default)" if i == default else ""
        print(f"  [{i + 1}] {opt}{marker}", file=sys.stderr)

    while True:
        try:
            raw = input(f"  Choice [1-{len(options)}, default={default + 1}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print(file=sys.stderr)
            sys.exit(1)
        if not raw:
            return default
        try:
            choice = int(raw) - 1
            if 0 <= choice < len(options):
                return choice
        except ValueError:
            pass
        print(f"  Please enter a number between 1 and {len(options)}.", file=sys.stderr)


def prompt_install() -> Path:
    """Interactive flow: pick a release, download, install."""
    print("Fetching available releases...", file=sys.stderr)
    releases = fetch_releases(limit=10)
    if not releases:
        print("Error: could not fetch releases from GitHub.", file=sys.stderr)
        sys.exit(1)

    os_name, arch = detect_platform()

    # Filter to releases that have a suitable asset
    viable = []
    for r in releases:
        if pick_asset(r, os_name, arch):
            tag = r["tag_name"]
            prerelease = " (pre-release)" if r.get("prerelease") else ""
            viable.append((r, f"{tag}{prerelease}"))
        if len(viable) >= 5:
            break

    if not viable:
        print(f"Error: no compatible releases found for {os_name}/{arch}.", file=sys.stderr)
        sys.exit(1)

    options = [label for _, label in viable]
    idx = prompt_choice(
        f"Which draw.io version to install? (platform: {os_name}/{arch})",
        options,
        default=0,
    )

    release = viable[idx][0]
    asset = pick_asset(release, os_name, arch)
    print(
        f"\nInstalling draw.io {release['tag_name']} ({asset['name']})...",
        file=sys.stderr,
    )
    print(f"  Target: {INSTALL_DIR}", file=sys.stderr)

    return install_drawio(release, os_name, arch)


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Ensure draw.io desktop CLI is available.")
    parser.add_argument("--check", action="store_true", help="Check only, don't install")
    parser.add_argument("--version", action="store_true", help="Print installed version")
    parser.add_argument("--list", action="store_true", help="List available releases")
    args = parser.parse_args()

    if args.list:
        releases = fetch_releases(limit=10)
        os_name, arch = detect_platform()
        for r in releases:
            tag = r["tag_name"]
            pre = " (pre-release)" if r.get("prerelease") else ""
            asset = pick_asset(r, os_name, arch)
            compat = f" -> {asset['name']}" if asset else " (no compatible asset)"
            print(f"  {tag}{pre}{compat}", file=sys.stderr)
        return

    # Try to find existing installation
    binary = find_drawio()

    if args.version:
        if binary:
            ver = get_installed_version(binary)
            print(ver or "unknown")
        else:
            print("not installed", file=sys.stderr)
            sys.exit(1)
        return

    if binary:
        print(f"draw.io found: {binary}", file=sys.stderr)
        # stdout: just the path (for capture)
        print(str(binary))
        return

    if args.check:
        print("draw.io not found.", file=sys.stderr)
        sys.exit(1)

    # Not found — interactive install
    print("draw.io desktop CLI not found on this system.", file=sys.stderr)
    binary = prompt_install()
    print(f"\ndraw.io installed: {binary}", file=sys.stderr)
    print(str(binary))


if __name__ == "__main__":
    main()
