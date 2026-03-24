"""Tests for ensure_drawio.py — platform detection, asset selection, and binary discovery."""
from __future__ import annotations

import json
import stat
import sys
import zipfile
from pathlib import Path
from unittest import mock

import pytest

# Add parent dir to path so we can import the module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ensure_drawio


# ── Platform detection ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "system, machine, expected",
    [
        ("Windows", "AMD64", ("windows", "x64")),
        ("Windows", "x86_64", ("windows", "x64")),
        ("Windows", "ARM64", ("windows", "arm64")),
        ("Darwin", "x86_64", ("darwin", "x64")),
        ("Darwin", "arm64", ("darwin", "arm64")),
        ("Linux", "x86_64", ("linux", "x64")),
        ("Linux", "aarch64", ("linux", "arm64")),
        ("Linux", "i686", ("linux", "ia32")),
        ("Linux", "riscv64", ("linux", "x64")),  # unknown arch falls back to x64
    ],
)
def test_detect_platform(system, machine, expected):
    with mock.patch("platform.system", return_value=system), \
         mock.patch("platform.machine", return_value=machine):
        assert ensure_drawio.detect_platform() == expected


# ── Asset selection ──────────────────────────────────────────────────────────

# Minimal mock release with representative asset names
MOCK_ASSETS = [
    {"name": "draw.io-29.6.1-windows-installer.exe", "browser_download_url": "https://example.com/installer.exe"},
    {"name": "draw.io-29.6.1-windows-installer.exe.blockmap", "browser_download_url": "https://example.com/installer.blockmap"},
    {"name": "draw.io-29.6.1-windows.zip", "browser_download_url": "https://example.com/windows.zip"},
    {"name": "draw.io-29.6.1.msi", "browser_download_url": "https://example.com/installer.msi"},
    {"name": "draw.io-arm64-29.6.1-windows-arm64-no-installer.exe", "browser_download_url": "https://example.com/arm64-no-installer.exe"},
    {"name": "draw.io-arm64-29.6.1-windows-arm64-installer.exe", "browser_download_url": "https://example.com/arm64-installer.exe"},
    {"name": "draw.io-arm64-29.6.1.dmg", "browser_download_url": "https://example.com/arm64.dmg"},
    {"name": "draw.io-arm64-29.6.1.dmg.blockmap", "browser_download_url": "https://example.com/arm64.dmg.blockmap"},
    {"name": "draw.io-arm64-29.6.1.zip", "browser_download_url": "https://example.com/arm64-mac.zip"},
    {"name": "draw.io-arm64-29.6.1.zip.blockmap", "browser_download_url": "https://example.com/arm64-mac.zip.blockmap"},
    {"name": "draw.io-x64-29.6.1.dmg", "browser_download_url": "https://example.com/x64.dmg"},
    {"name": "draw.io-x64-29.6.1.dmg.blockmap", "browser_download_url": "https://example.com/x64.dmg.blockmap"},
    {"name": "draw.io-x64-29.6.1.zip", "browser_download_url": "https://example.com/x64-mac.zip"},
    {"name": "draw.io-x64-29.6.1.zip.blockmap", "browser_download_url": "https://example.com/x64-mac.zip.blockmap"},
    {"name": "draw.io-universal-29.6.1.dmg", "browser_download_url": "https://example.com/universal.dmg"},
    {"name": "draw.io-universal-29.6.1.dmg.blockmap", "browser_download_url": "https://example.com/universal.dmg.blockmap"},
    {"name": "drawio-x86_64-29.6.1.AppImage", "browser_download_url": "https://example.com/x86_64.AppImage"},
    {"name": "drawio-arm64-29.6.1.AppImage", "browser_download_url": "https://example.com/arm64.AppImage"},
    {"name": "drawio-amd64-29.6.1.deb", "browser_download_url": "https://example.com/amd64.deb"},
    {"name": "drawio-x86_64-29.6.1.rpm", "browser_download_url": "https://example.com/x86_64.rpm"},
]

MOCK_RELEASE = {"tag_name": "v29.6.1", "prerelease": False, "assets": MOCK_ASSETS}


class TestPickAsset:
    def test_windows_x64_picks_zip(self):
        asset = ensure_drawio.pick_asset(MOCK_RELEASE, "windows", "x64")
        assert asset is not None
        assert asset["name"] == "draw.io-29.6.1-windows.zip"

    def test_windows_arm64_picks_no_installer(self):
        asset = ensure_drawio.pick_asset(MOCK_RELEASE, "windows", "arm64")
        assert asset is not None
        assert asset["name"] == "draw.io-arm64-29.6.1-windows-arm64-no-installer.exe"

    def test_darwin_x64_picks_zip(self):
        asset = ensure_drawio.pick_asset(MOCK_RELEASE, "darwin", "x64")
        assert asset is not None
        assert asset["name"] == "draw.io-x64-29.6.1.zip"

    def test_darwin_arm64_picks_zip(self):
        asset = ensure_drawio.pick_asset(MOCK_RELEASE, "darwin", "arm64")
        assert asset is not None
        assert asset["name"] == "draw.io-arm64-29.6.1.zip"

    def test_linux_x64_picks_appimage(self):
        asset = ensure_drawio.pick_asset(MOCK_RELEASE, "linux", "x64")
        assert asset is not None
        assert asset["name"] == "drawio-x86_64-29.6.1.AppImage"

    def test_linux_arm64_picks_appimage(self):
        asset = ensure_drawio.pick_asset(MOCK_RELEASE, "linux", "arm64")
        assert asset is not None
        assert asset["name"] == "drawio-arm64-29.6.1.AppImage"

    def test_no_asset_for_unknown_platform(self):
        asset = ensure_drawio.pick_asset(MOCK_RELEASE, "freebsd", "x64")
        assert asset is None

    def test_empty_release_returns_none(self):
        asset = ensure_drawio.pick_asset({"assets": []}, "windows", "x64")
        assert asset is None

    def test_windows_ia32_picks_32bit(self):
        asset = ensure_drawio.pick_asset(MOCK_RELEASE, "windows", "ia32")
        # ia32 expects the 32bit installer exe (only option for 32-bit)
        assert asset is None or "32bit" in asset["name"]


# ── Binary discovery ─────────────────────────────────────────────────────────


class TestFindOnPath:
    def test_found(self):
        with mock.patch("shutil.which", side_effect=lambda n: "/usr/bin/drawio" if n == "drawio" else None):
            result = ensure_drawio.find_on_path()
            assert result == Path("/usr/bin/drawio")

    def test_found_draw_dot_io(self):
        with mock.patch("shutil.which", side_effect=lambda n: "/usr/bin/draw.io" if n == "draw.io" else None):
            result = ensure_drawio.find_on_path()
            assert result == Path("/usr/bin/draw.io")

    def test_not_found(self):
        with mock.patch("shutil.which", return_value=None):
            result = ensure_drawio.find_on_path()
            assert result is None


class TestFindInKnownPaths:
    def test_windows_found(self, tmp_path):
        fake_exe = tmp_path / "draw.io.exe"
        fake_exe.touch()
        with mock.patch.dict(ensure_drawio.KNOWN_PATHS, {"windows": [str(fake_exe)]}):
            result = ensure_drawio.find_in_known_paths("windows")
            assert result == fake_exe

    def test_not_found(self):
        with mock.patch.dict(ensure_drawio.KNOWN_PATHS, {"windows": ["/nonexistent/draw.io.exe"]}):
            result = ensure_drawio.find_in_known_paths("windows")
            assert result is None


class TestFindInInstallDir:
    def test_windows_found(self, tmp_path):
        exe = tmp_path / "draw.io.exe"
        exe.touch()
        with mock.patch.object(ensure_drawio, "INSTALL_DIR", tmp_path):
            result = ensure_drawio.find_in_install_dir("windows")
            assert result == exe

    def test_darwin_found(self, tmp_path):
        app_binary = tmp_path / "draw.io.app" / "Contents" / "MacOS" / "draw.io"
        app_binary.parent.mkdir(parents=True)
        app_binary.touch()
        with mock.patch.object(ensure_drawio, "INSTALL_DIR", tmp_path):
            result = ensure_drawio.find_in_install_dir("darwin")
            assert result == app_binary

    def test_linux_appimage_found(self, tmp_path):
        appimage = tmp_path / "drawio-x86_64-29.6.1.AppImage"
        appimage.touch()
        with mock.patch.object(ensure_drawio, "INSTALL_DIR", tmp_path):
            result = ensure_drawio.find_in_install_dir("linux")
            assert result == appimage

    def test_empty_dir(self, tmp_path):
        with mock.patch.object(ensure_drawio, "INSTALL_DIR", tmp_path):
            result = ensure_drawio.find_in_install_dir("windows")
            assert result is None

    def test_nonexistent_dir(self):
        with mock.patch.object(ensure_drawio, "INSTALL_DIR", Path("/nonexistent")):
            result = ensure_drawio.find_in_install_dir("windows")
            assert result is None


class TestFindDrawio:
    """Integration test for the full discovery chain."""

    def test_prefers_install_dir_over_path(self, tmp_path):
        managed = tmp_path / "managed" / "draw.io.exe"
        managed.parent.mkdir()
        managed.touch()
        with mock.patch.object(ensure_drawio, "INSTALL_DIR", managed.parent), \
             mock.patch("platform.system", return_value="Windows"), \
             mock.patch("platform.machine", return_value="AMD64"), \
             mock.patch("shutil.which", return_value="/usr/bin/drawio"):
            result = ensure_drawio.find_drawio()
            assert result == managed

    def test_falls_back_to_path(self, tmp_path):
        with mock.patch.object(ensure_drawio, "INSTALL_DIR", tmp_path / "empty"), \
             mock.patch("platform.system", return_value="Linux"), \
             mock.patch("platform.machine", return_value="x86_64"), \
             mock.patch("shutil.which", return_value="/usr/bin/drawio"):
            result = ensure_drawio.find_drawio()
            assert result == Path("/usr/bin/drawio")


# ── Install flow ─────────────────────────────────────────────────────────────


class TestInstallWindows:
    """Test that Windows zip extraction works correctly."""

    def test_install_zip(self, tmp_path):
        install_dir = tmp_path / "install"
        # Create a fake zip with draw.io.exe inside
        zip_content_dir = tmp_path / "zip_content"
        zip_content_dir.mkdir()
        (zip_content_dir / "draw.io.exe").write_bytes(b"fake-exe")
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(zip_content_dir / "draw.io.exe", "draw.io.exe")

        # Mock the download to just copy our test zip
        def mock_download(url, dest, name=""):
            import shutil
            shutil.copy2(zip_path, dest)

        with mock.patch.object(ensure_drawio, "INSTALL_DIR", install_dir), \
             mock.patch.object(ensure_drawio, "download_file", mock_download):
            release = {
                "tag_name": "v29.6.1",
                "assets": [{"name": "draw.io-29.6.1-windows.zip", "browser_download_url": "https://example.com/test.zip"}],
            }
            result = ensure_drawio.install_drawio(release, "windows", "x64")
            assert result.name == "draw.io.exe"
            assert result.is_file()
            assert (install_dir / ".version").read_text() == "29.6.1"


class TestInstallLinux:
    """Test that Linux AppImage installation works correctly."""

    def test_install_appimage(self, tmp_path):
        install_dir = tmp_path / "install"
        appimage_src = tmp_path / "drawio.AppImage"
        appimage_src.write_bytes(b"fake-appimage")

        def mock_download(url, dest, name=""):
            import shutil
            shutil.copy2(appimage_src, dest)

        with mock.patch.object(ensure_drawio, "INSTALL_DIR", install_dir), \
             mock.patch.object(ensure_drawio, "download_file", mock_download):
            release = {
                "tag_name": "v29.6.1",
                "assets": [{"name": "drawio-x86_64-29.6.1.AppImage", "browser_download_url": "https://example.com/test.AppImage"}],
            }
            result = ensure_drawio.install_drawio(release, "linux", "x64")
            assert result.name == "drawio-x86_64-29.6.1.AppImage"
            assert result.is_file()
            if sys.platform != "win32":
                assert result.stat().st_mode & stat.S_IEXEC  # executable bit set


class TestInstallMacOS:
    """Test that macOS zip extraction works correctly."""

    def test_install_zip_with_app_bundle(self, tmp_path):
        install_dir = tmp_path / "install"
        # Create a fake zip with .app bundle structure
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            app_path = "draw.io.app/Contents/MacOS/draw.io"
            zf.writestr(app_path, "fake-binary")

        def mock_download(url, dest, name=""):
            import shutil
            shutil.copy2(zip_path, dest)

        with mock.patch.object(ensure_drawio, "INSTALL_DIR", install_dir), \
             mock.patch.object(ensure_drawio, "download_file", mock_download):
            release = {
                "tag_name": "v29.6.1",
                "assets": [{"name": "draw.io-arm64-29.6.1.zip", "browser_download_url": "https://example.com/test.zip"}],
            }
            result = ensure_drawio.install_drawio(release, "darwin", "arm64")
            assert result.name == "draw.io"
            assert "draw.io.app" in str(result)
            assert result.is_file()


# ── Version detection ────────────────────────────────────────────────────────


class TestGetInstalledVersion:
    def test_parses_version_number(self):
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(stdout="29.6.1\n", stderr="")
            ver = ensure_drawio.get_installed_version(Path("/usr/bin/drawio"))
            assert ver == "29.6.1"

    def test_handles_multiline_output(self):
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(stdout="draw.io\n29.6.1\n", stderr="")
            ver = ensure_drawio.get_installed_version(Path("/usr/bin/drawio"))
            assert ver == "29.6.1"

    def test_handles_timeout(self):
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 15)):
            ver = ensure_drawio.get_installed_version(Path("/usr/bin/drawio"))
            assert ver is None

    def test_handles_missing_binary(self):
        with mock.patch("subprocess.run", side_effect=FileNotFoundError):
            ver = ensure_drawio.get_installed_version(Path("/nonexistent/drawio"))
            assert ver is None


# ── CLI argument handling ────────────────────────────────────────────────────


class TestMainCheck:
    def test_check_found(self, tmp_path, capsys):
        exe = tmp_path / "draw.io.exe"
        exe.touch()
        with mock.patch.object(ensure_drawio, "find_drawio", return_value=exe), \
             mock.patch("sys.argv", ["ensure_drawio.py", "--check"]):
            ensure_drawio.main()
            captured = capsys.readouterr()
            assert str(exe) in captured.out

    def test_check_not_found(self):
        with mock.patch.object(ensure_drawio, "find_drawio", return_value=None), \
             mock.patch("sys.argv", ["ensure_drawio.py", "--check"]):
            with pytest.raises(SystemExit, match="1"):
                ensure_drawio.main()


import subprocess  # noqa: E402 (needed for TestGetInstalledVersion)
