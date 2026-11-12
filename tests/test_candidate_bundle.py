"""Regression checks for the non-publishing release candidate evidence generator."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "ci_candidate_bundle", ROOT / "tools" / "ci_candidate_bundle.py"
)
bundle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bundle)


class CandidateBundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.package = self.root / "appinstall-1.0.0-1-any.pkg.tar.zst"
        self.package.write_bytes(b"disposable-test-only")
        self.sums = self.root / "SHA256SUMS"
        self.digest = hashlib.sha256(self.package.read_bytes()).hexdigest()
        self.sums.write_text(
            self.digest + "  " + self.package.name + "\n", encoding="utf-8"
        )

    def test_exact_archive_checksum_passes(self):
        self.assertEqual(
            self.digest, bundle.verify_checksum(self.package, self.sums)
        )

    def test_corrupted_archive_is_rejected(self):
        self.package.write_bytes(b"disposable-test-only-corrupted")
        with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
            bundle.verify_checksum(self.package, self.sums)

    def test_other_archive_filename_is_rejected(self):
        self.sums.write_text(
            self.digest + "  other.pkg.tar.zst\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "exact archive filename"):
            bundle.verify_checksum(self.package, self.sums)

    def test_multiple_manifest_lines_are_rejected(self):
        self.sums.write_text(
            self.sums.read_text() * 2, encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "exactly one"):
            bundle.verify_checksum(self.package, self.sums)

    def test_pr_merge_checkout_records_distinct_pr_head(self):
        kind, head = bundle.classify_provenance(
            "pull_request", "a" * 40, "b" * 40
        )
        self.assertEqual("PR_TEST_ONLY", kind)
        self.assertEqual("b" * 40, head)

    def test_push_candidate_has_no_pr_head(self):
        kind, head = bundle.classify_provenance(
            "push", "a" * 40, ""
        )
        self.assertEqual("PUSH_CI_TEST_ONLY", kind)
        self.assertIsNone(head)

    def test_invalid_github_event_sha_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "GITHUB_SHA"):
            bundle.classify_provenance("push", "invalid", "")

    def test_pr_without_head_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "complete PR branch head"):
            bundle.classify_provenance("pull_request", "a" * 40, "")

    def test_non_pr_cannot_claim_pr_head(self):
        with self.assertRaisesRegex(ValueError, "unexpectedly includes"):
            bundle.classify_provenance("push", "a" * 40, "b" * 40)

    def test_unknown_event_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unexpected CI event"):
            bundle.classify_provenance("release", "a" * 40, "")

    def test_candidate_report_keeps_manual_checks_pending(self):
        evidence = {
            "source_commit": "a" * 40,
            "ci_event": "pull_request",
            "candidate_classification": "PR_TEST_ONLY",
            "pull_request_head_commit": "b" * 40,
            "workflow_url": "https://github.com/aboodmohd/-AppInstall/actions/runs/123",
            "package_filename": self.package.name,
            "sha256": self.digest,
            "package_version": "1.1.0-1",
            "generated_utc": "2026-11-04T12:00:00+00:00",
        }
        report = bundle.build_report(evidence)
        self.assertIn("NO-GO", report)
        self.assertIn("# AppInstall 1.1.0 — disposable release candidate evidence", report)
        self.assertIn("Stable 1.1.0 publication approval", report)
        self.assertIn("Install from URL", report)
        self.assertNotIn("# AppInstall 1.0 —", report)
        self.assertIn("CachyOS", report)
        self.assertIn("PENDING", report)
        self.assertIn("publication approval", report)
        self.assertIn("PR_TEST_ONLY", report)
        self.assertIn("temporary", report)
        self.assertIn("b" * 40, report)
        self.assertNotIn("| APPROVED |", report)


if __name__ == "__main__":
    unittest.main()
