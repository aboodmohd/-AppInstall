"""Release version consistency across the Arch, Debian, and Fedora build inputs.

These tests are source-only; they don't install packages or alter the host.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ThreeFormatReleaseVersionTests(unittest.TestCase):
    def test_cli_version_matches_single_pkgbuilder_source(self):
        pkg = (ROOT / "PKGBUILD").read_text()
        app = (ROOT / "appinstall").read_text()
        pkg_version = re.search(r"^pkgver=([0-9][A-Za-z0-9.]+)$", pkg, re.M)
        cli_version = re.search(r'^VERSION="([^"]+)"$', app, re.M)
        self.assertIsNotNone(pkg_version)
        self.assertIsNotNone(cli_version)
        self.assertEqual(pkg_version.group(1), cli_version.group(1))

    def test_deb_and_rpm_builders_share_pkgbuilder_version(self):
        deb = (ROOT / "tools/build_deb.sh").read_text()
        rpm = (ROOT / "tools/build_rpm.sh").read_text()
        spec = (ROOT / "packaging/appinstall.spec.in").read_text()
        for builder in (deb, rpm):
            self.assertIn('source "$srcdir/PKGBUILD"' if builder == deb
                          else 'source "$root/PKGBUILD"', builder)
            self.assertIn('package', builder)
        self.assertIn('Version:        @VERSION@', spec)
        self.assertIn('Release:        @RELEASE@', spec)
        self.assertIn('BuildArch:      noarch', spec)

    def test_installer_selects_all_three_native_formats(self):
        installer = (ROOT / "install.sh").read_text()
        for name in ('"arch"', '"debian"', '"fedora"'):
            self.assertIn(name + ': r"appinstall', installer)
        self.assertIn('SUPPORTED_IDS="arch cachyos fedora"', installer)
        self.assertIn('rpm -qp --qf', installer)
        self.assertIn('run_root dnf', installer)
