"""Guardrails for the real-filesystem acceptance script.

These tests never fill a filesystem. They only verify that the acceptance
probe refuses accidental invocation on a normal directory or host.
"""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

TOOL = Path(__file__).resolve().parents[1] / "tools/real_tmpfs_gate.py"
spec = importlib.util.spec_from_file_location("real_tmpfs_gate", TOOL)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class RealFilesystemGateSafetyTests(unittest.TestCase):
    def test_rejects_normal_user_session(self):
        with tempfile.TemporaryDirectory(prefix="appinstall-probe-") as temp:
            with patch.dict(os.environ, {"GITHUB_ACTIONS": "false",
                                         "RUNNER_TEMP": temp}):
                with self.assertRaisesRegex(RuntimeError, "outside GitHub Actions"):
                    probe.require_disposable_tmpfs(temp)

    def test_rejects_runner_temp_not_mounted(self):
        with tempfile.TemporaryDirectory(prefix="appinstall-probe-") as temp:
            folder = Path(temp) / "not-a-mount"
            folder.mkdir()
            with patch.dict(os.environ, {"GITHUB_ACTIONS": "true",
                                         "RUNNER_TEMP": temp}):
                with self.assertRaisesRegex(RuntimeError, "not an independent"):
                    probe.require_disposable_tmpfs(folder)

    def test_rejects_runner_root_and_external_path(self):
        with tempfile.TemporaryDirectory(prefix="appinstall-probe-") as temp:
            with patch.dict(os.environ, {"GITHUB_ACTIONS": "true",
                                         "RUNNER_TEMP": temp}):
                for unsafe in (temp, "/"):
                    with self.subTest(unsafe=unsafe):
                        with self.assertRaisesRegex(RuntimeError, "child of RUNNER_TEMP"):
                            probe.require_disposable_tmpfs(unsafe)
