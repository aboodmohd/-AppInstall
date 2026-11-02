"""Source installer must not silently shadow an existing pacman installation."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "install-user.sh"


class SourceInstallerConflictTests(unittest.TestCase):
    def run_script(self, package_installed):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bindir = root / "bin"
            bindir.mkdir()
            pacman = bindir / "pacman"
            pacman.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = \"-Qq\" ] && [ \"$2\" = \"appinstall\" ]; then\n"
                f"  exit {0 if package_installed else 1}\n"
                "fi\nexit 1\n"
            )
            python = bindir / "python3"
            python.write_text("#!/bin/sh\nprintf 'SOURCE_REGISTRATION_INVOKED\\n'\n")
            for executable in (pacman, python):
                executable.chmod(0o755)
            env = os.environ.copy()
            env.update(HOME=str(root), PATH=str(bindir) + ":/usr/bin:/bin")
            return subprocess.run(
                ["bash", str(SCRIPT)],
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                env=env,
                timeout=10,
            )

    def test_shell_syntax(self):
        result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_existing_pacman_install_refuses_noninteractive_shadow(self):
        result = self.run_script(package_installed=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("already installed through pacman", result.stderr)
        self.assertNotIn("SOURCE_REGISTRATION_INVOKED", result.stdout)

    def test_no_existing_pacman_install_runs_source_registration(self):
        result = self.run_script(package_installed=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SOURCE_REGISTRATION_INVOKED", result.stdout)


if __name__ == "__main__":
    unittest.main()
