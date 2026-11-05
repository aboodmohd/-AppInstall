"""Pure-text diagnostics summary regressions (no Qt event loop required)."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from diagnostics_core import diagnostic_details


class DiagnosticsSummaryTests(unittest.TestCase):
    def test_recent_attempt_without_error_preserves_historical_failure(self):
        old = dict(
            started='2026-11-05T09:30:00+00:00', status='failed',
            error=dict(category='executable', detail='The executable does not exist.'),
            log='/tmp/old.log',
        )
        recent = dict(
            started='2026-11-05T09:33:40+00:00',
            status='detached_or_exited_unverified',
            error=None, log='/tmp/recent.log',
        )
        summary = diagnostic_details(dict(
            name='Recovery Test Fixture', desktop='/tmp/test.desktop',
            last=recent, last_error=old,
        ))
        self.assertIn('Latest attempt status: detached_or_exited_unverified', summary)
        self.assertIn('Latest attempt error: No error detected;', summary)
        self.assertIn('Most recent recorded failure: executable — The executable does not exist.', summary)
        self.assertIn('(at 2026-11-05T09:30:00+00:00)', summary)
        self.assertIn('Latest attempt log: /tmp/recent.log', summary)
        self.assertNotIn('Latest attempt error: The executable does not exist.', summary)
        self.assertIn('may still be unusable', summary)

    def test_latest_attempt_failure_is_shown_in_both_fields(self):
        failed = dict(
            started='2026-11-05T09:30:00+00:00', status='failed',
            error=dict(category='dependency', detail='Missing shared library.'),
            log='/tmp/failure.log',
        )
        summary = diagnostic_details(dict(
            name='App', desktop='/tmp/app.desktop', last=failed, last_error=failed,
        ))
        self.assertIn('Latest attempt error: Missing shared library.', summary)
        self.assertIn('Most recent recorded failure: dependency — Missing shared library.', summary)

    def test_no_history_does_not_claim_any_launch(self):
        summary = diagnostic_details(dict(
            name='Never Launched', desktop='/tmp/new.desktop',
            last=None, last_error=None,
        ))
        self.assertIn('Latest attempt: Never', summary)
        self.assertIn('Latest attempt status: Never launched', summary)
        self.assertIn('Latest attempt error: No launch recorded.', summary)
        self.assertIn('Most recent recorded failure: None recorded.', summary)
        self.assertIn('Latest attempt log: No launch logs yet.', summary)


if __name__ == '__main__':
    unittest.main()
