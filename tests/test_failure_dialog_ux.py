"""Regression checks for invalid DEB/RPM failure wording and readable error text."""
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QLabel
    import container_ui
    import result_ui
except ImportError:
    container_ui = None
    result_ui = None


@unittest.skipIf(container_ui is None or result_ui is None, "PySide6 is optional")
class FailureDialogUXTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_invalid_archive_is_named_as_validation_failure(self):
        for filename in ("corrupt-preview-test.deb", "corrupt-preview-test.rpm"):
            with self.subTest(filename=filename):
                name, headline = container_ui.failure_context(
                    ["/tmp/" + filename], None
                )
                self.assertEqual(name, filename)
                self.assertEqual(headline, "Package validation failed")

    def test_install_failure_keeps_existing_context(self):
        self.assertEqual(
            container_ui.failure_context(["/tmp/hello.rpm"], {"name": "hello"}),
            ("hello", None),
        )
        self.assertEqual(
            container_ui.failure_context(["--remove", "rpm:hello"], None),
            ("Container operation", None),
        )

    def test_validation_error_title_details_and_dark_contrast(self):
        dialog = result_ui.FailureDialog(
            "corrupt-preview-test.rpm",
            "Package or compatibility problem",
            technical="Truncated RPM header",
            headline="Package validation failed",
        )
        title = dialog.findChild(QLabel, "failure-headline")
        category = dialog.findChild(QLabel, "failure-category")
        self.assertIsNotNone(title)
        self.assertIsNotNone(category)
        self.assertEqual(title.text(), "Package validation failed")
        self.assertIn("Problem type: Package or compatibility problem", category.text())
        self.assertIn("palette(window-text)", category.styleSheet())
        self.assertIn("corrupt-preview-test.rpm", dialog.details)
        self.assertIn("Truncated RPM header", dialog.details)
        dialog.close()

    def test_ordinary_install_error_still_names_package(self):
        dialog = result_ui.FailureDialog(
            "example", "Package or compatibility problem", technical="failed"
        )
        self.assertEqual(
            dialog.findChild(QLabel, "failure-headline").text(),
            "example could not be installed",
        )
        dialog.close()


if __name__ == "__main__":
    unittest.main()
