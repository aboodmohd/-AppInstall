"""Regression coverage for KDE dark-theme review-dialog text.

Qt palette(mid) describes a midtone for borders/shadows; on Breeze Dark it
can make package subtitles and security notices nearly invisible. Use the
ordinary window-text role instead for all text that conveys information.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PreviewContrastTests(unittest.TestCase):
    def test_package_review_uses_readable_window_text(self):
        source = (ROOT / "confirm.py").read_text(encoding="utf-8")
        self.assertIn("subtitle.setStyleSheet('color: palette(window-text);')", source)
        self.assertIn("key.setStyleSheet('color: palette(window-text);')", source)
        self.assertIn("notice.setStyleSheet('color: palette(window-text);')", source)
        self.assertNotIn("color: palette(mid);", source)

    def test_container_review_and_status_use_readable_window_text(self):
        source = (ROOT / "container_ui.py").read_text(encoding="utf-8")
        self.assertIn("self.subtitle.setStyleSheet('color: palette(window-text);')", source)
        self.assertIn("self.stage_label.setStyleSheet('color: palette(window-text); font-weight: 600;')", source)
        self.assertNotIn("color: palette(mid);", source)


if __name__ == "__main__":
    unittest.main()
