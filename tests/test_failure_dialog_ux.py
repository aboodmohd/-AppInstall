"""Regression tests for failed DEB/RPM validation and its error wording.

Avoid creating another QApplication in the full unittest discovery process:
PySide6 may crash during interpreter shutdown when Qt object lifetimes overlap.
The manual KDE/Wayland screenshot test verifies actual rendered contrast.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import container_ui
except ImportError:
    container_ui = None


@unittest.skipIf(container_ui is None, "PySide6 is optional")
class FailureContextTests(unittest.TestCase):
    def test_corrupt_deb_rpm_are_validation_failures(self):
        for filename in ("corrupt-preview-test.deb", "corrupt-preview-test.rpm"):
            with self.subTest(filename=filename):
                name, headline = container_ui.failure_context(
                    ["/tmp/" + filename], None
                )
                self.assertEqual(name, filename)
                self.assertEqual(headline, "Package validation failed")

    def test_other_operations_keep_original_failure_context(self):
        self.assertEqual(
            container_ui.failure_context(["/tmp/hello.rpm"], {"name": "hello"}),
            ("hello", None),
        )
        self.assertEqual(
            container_ui.failure_context(["--remove", "rpm:hello"], None),
            ("Container operation", None),
        )

    def test_failure_dialog_uses_readable_category_palette(self):
        code = (ROOT / "result_ui.py").read_text(encoding="utf-8")
        self.assertIn("kind.setStyleSheet('color: palette(window-text);')", code)
        self.assertIn("kind.setObjectName('failure-category')", code)
        self.assertNotIn("kind.setStyleSheet('color: palette(mid);')", code)

    def test_failure_dialog_preserves_title_and_copyable_details(self):
        code = (ROOT / "result_ui.py").read_text(encoding="utf-8")
        self.assertIn(
            "title = QLabel(headline if headline is not None else name+' could not be installed')",
            code,
        )
        self.assertIn("title.setObjectName('failure-headline')", code)
        self.assertIn(
            "self.details = (name+'\\n'+category+'\\n'+explanation+'\\n'+technical).strip()",
            code,
        )


if __name__ == "__main__":
    unittest.main()
