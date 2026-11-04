"""Verify Arch package version and application CLI remain synchronized.

A pre-release package must never silently claim a final stable version in the
package file while the executable identifies itself as a beta/RC (or vice versa).
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class VersionConsistencyTests(unittest.TestCase):
    def test_cli_and_arch_package_version_consistent(self):
        bash = (ROOT / "appinstall").read_text()
        pkgbuild = (ROOT / "PKGBUILD").read_text()
        version = re.search(r'^VERSION="([^"]+)"$', bash, re.MULTILINE)
        pkgver = re.search(r'^pkgver=([A-Za-z0-9_.]+)$', pkgbuild, re.MULTILINE)
        self.assertIsNotNone(version)
        self.assertIsNotNone(pkgver)
        parts = re.fullmatch(
            r'(\d+\.\d+\.\d+)(?:-(beta|rc)\.(\d+))?', version.group(1))
        self.assertIsNotNone(parts)
        expected = parts.group(1) + (parts.group(2) or '') + (parts.group(3) or '')
        self.assertEqual(pkgver.group(1), expected)

    def test_prerelease_notes_and_published_beta_manifest_are_distinct(self):
        bash = (ROOT / "appinstall").read_text()
        version = re.search(r'^VERSION="([^"]+)"$', bash, re.MULTILINE).group(1)
        notes = (ROOT / "RELEASE_NOTES.md").read_text()
        self.assertIn(version, notes.splitlines()[0])
        # The historic beta package's checksum is NOT the checksum of an RC build.
        beta_manifest = (ROOT / "PACKAGE_CHECKSUM.md").read_text()
        historical_versions = re.findall(
            r'\b\d+\.\d+\.\d+(?:-(?:beta|rc)\.\d+)?\b',
            beta_manifest.splitlines()[0])
        self.assertIn('1.0.0-beta.1', historical_versions)
        if version != '1.0.0-beta.1':
            # Version equality must be exact: "1.0.0" is naturally a
            # substring of the preserved historical "1.0.0-beta.1".
            self.assertNotIn(version, historical_versions)


if __name__ == "__main__":
    unittest.main()
