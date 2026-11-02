"""Keep PKGBUILD local-source checksums aligned with checked-in files."""
import hashlib
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PackageIntegrityTests(unittest.TestCase):
    def test_local_source_b2sums(self):
        script = (ROOT / "PKGBUILD").read_text()
        sources_match = re.search(r"source=\(([\s\S]*?)\)\s*b2sums=", script)
        sums_match = re.search(r"b2sums=\(([\s\S]*?)\)\s*package\(\)", script)
        self.assertIsNotNone(sources_match)
        self.assertIsNotNone(sums_match)
        filenames = re.findall(r"'([^']+)'", sources_match.group(1))
        digests = re.findall(r"'([0-9a-f]{128})'", sums_match.group(1))
        self.assertTrue(filenames)
        self.assertEqual(len(filenames), len(digests))
        for filename, expected in zip(filenames, digests):
            with self.subTest(source=filename):
                path = ROOT / filename
                self.assertTrue(path.is_file(), f"Missing source: {filename}")
                self.assertEqual(hashlib.blake2b(path.read_bytes()).hexdigest(), expected)


if __name__ == "__main__":
    unittest.main()
