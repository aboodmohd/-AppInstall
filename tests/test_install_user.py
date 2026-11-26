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
                "if [ \"$1\" = \"-Qq\" ] && [ \"$2\" = \"abood-appinstall\" ]; then\n"
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

    def run_other_package_manager(self, command, installed):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bindir = root / 'bin'
            bindir.mkdir()
            # Stub native manager with a fixed package-installed status. The
            # source installer must not change native packages or run Python
            # registration when a system AppInstall copy exists.
            if command == 'dpkg-query':
                script = ('#!/bin/sh\n'
                          'if [ "$1" = "-W" ] && [ "$3" = "abood-appinstall" ]; then\n'
                          f'  [ {1 if installed else 0} -eq 1 ] || exit 1\n'
                          '  printf "install ok installed\\n"; exit 0\n'
                          'fi\nexit 1\n')
            else:
                script = ('#!/bin/sh\n'
                          'if [ "$1" = "-q" ] && [ "$2" = "abood-appinstall" ]; then\n'
                          f'  exit {0 if installed else 1}\n'
                          'fi\nexit 1\n')
            native = bindir / command
            native.write_text(script)
            native.chmod(0o755)
            # Stubs shadow the real host managers (if installed).
            for name in ('pacman', 'dpkg-query', 'rpm'):
                if name != command:
                    stub = bindir / name
                    stub.write_text('#!/bin/sh\nexit 1\n')
                    stub.chmod(0o755)
            python = bindir / 'python3'
            python.write_text('#!/bin/sh\nprintf "SOURCE_REGISTRATION_INVOKED\\n"\n')
            python.chmod(0o755)
            env = os.environ.copy()
            env.update(HOME=str(root), PATH=str(bindir) + ':/usr/bin:/bin')
            return subprocess.run(
                ['bash', str(SCRIPT)], cwd=ROOT, stdin=subprocess.DEVNULL,
                capture_output=True, text=True, env=env, timeout=10)

    def test_dpkg_source_install_never_shadows_native_package(self):
        result = self.run_other_package_manager('dpkg-query', installed=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('installed through dpkg', result.stderr)
        self.assertNotIn('SOURCE_REGISTRATION_INVOKED', result.stdout)

    def test_rpm_source_install_never_shadows_native_package(self):
        result = self.run_other_package_manager('rpm', installed=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('installed through rpm', result.stderr)
        self.assertNotIn('SOURCE_REGISTRATION_INVOKED', result.stdout)

    def test_non_native_source_install_still_works(self):
        for manager in ('dpkg-query', 'rpm'):
            with self.subTest(manager=manager):
                result = self.run_other_package_manager(manager, installed=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('SOURCE_REGISTRATION_INVOKED', result.stdout)

    def test_old_python_is_rejected_with_actionable_message(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bindir = root/'bin'
            bindir.mkdir()
            for name in ('pacman', 'dpkg-query', 'rpm'):
                stub = bindir/name
                stub.write_text('#!/bin/sh\nexit 1\n')
                stub.chmod(0o755)
            python = bindir/'python3'
            python.write_text('#!/bin/sh\ncase "$*" in *version_info*) exit 1;; esac\nprintf "SOURCE_REGISTRATION_INVOKED\\n"\n')
            python.chmod(0o755)
            env = os.environ.copy()
            env.update(HOME=str(root), PATH=str(bindir)+':/usr/bin:/bin')
            result = subprocess.run(['bash', str(SCRIPT)], cwd=ROOT,
                                    stdin=subprocess.DEVNULL, capture_output=True,
                                    text=True, env=env, timeout=10)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn('Python 3.9 or newer', result.stderr)
            self.assertNotIn('SOURCE_REGISTRATION_INVOKED', result.stdout)

    def test_no_existing_pacman_install_runs_source_registration(self):
        result = self.run_script(package_installed=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SOURCE_REGISTRATION_INVOKED", result.stdout)


if __name__ == "__main__":
    unittest.main()
