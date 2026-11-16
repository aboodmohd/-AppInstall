"""Native DEB/RPM discovery: mocked package tools, no containers or network."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import container_backend
import repository_catalog as catalog


class RepositoryCatalogTests(unittest.TestCase):
    def test_package_names_cannot_be_shell_options_or_paths(self):
        for bad in ("", "-y", "--install", ";rm", "foo;bar",
                    "../foo", "foo/bar", "foo\nbar", "foo*",
                    "$(touch /tmp/a)", "a" * 200, None):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                catalog.validate_name(bad)
        self.assertEqual(catalog.validate_name("fonts-noto-color-emoji"),
                         "fonts-noto-color-emoji")

    def test_unprepared_repository_never_creates_containers_for_search(self):
        with patch.object(catalog, "ready", return_value=False), \
             patch.object(container_backend, "Engine") as engine:
            with self.assertRaises(catalog.CatalogNotReady):
                catalog.search("deb", "gimp")
            with self.assertRaises(catalog.CatalogNotReady):
                catalog.search("rpm", "gimp")
        engine.assert_not_called()

    def test_search_deb_produces_real_package_rows(self):
        output = ("gimp - GNU Image Manipulation Program\n"
                  "gimp-help-en - English documentation\n"
                  "gimp - duplicate ignored\n"
                  "bad/package - malicious name\n")
        with patch.object(catalog, "ready", return_value=True), \
             patch.object(catalog, "_run", return_value=output) as run:
            rows = catalog.search("deb", "gimp")
        self.assertEqual([r["appId"] for r in rows], ["gimp", "gimp-help-en"])
        self.assertEqual(rows[0]["source"], "DEB")
        self.assertEqual(rows[0]["category"], "Debian 13")
        self.assertEqual(rows[0]["summary"], "GNU Image Manipulation Program")
        self.assertEqual(run.call_args.args[1][:3], ["apt-cache", "search", "--names-only"])

    def test_search_rejects_regex_and_glob_injection(self):
        with patch.object(catalog, "ready", return_value=True), \
             patch.object(catalog, "_run") as query:
            for term in ("gimp.*", "gimp[0]", "$(touch /tmp/a)", "--x", "\nfoo"):
                with self.subTest(term=term), self.assertRaises(ValueError):
                    catalog.search("rpm", term)
        query.assert_not_called()

    def test_fedora_search_filters_arch_and_duplicates(self):
        output = ("gimp\tImage editor\t3.2\tx86_64\n"
                  "gimp\tduplicate\t3.1\tx86_64\n"
                  "gimp-help\tDocs\t3.2\tnoarch\n"
                  "gimp-32\tUnsupported\t3.2\ti686\n")
        with patch.object(catalog, "ready", return_value=True), \
             patch.object(catalog, "_run", return_value=output) as query:
            rows = catalog.search("rpm", "gimp")
        self.assertEqual([r["appId"] for r in rows], ["gimp", "gimp-help"])
        self.assertEqual(rows[0]["source"], "RPM")
        self.assertEqual(rows[0]["version"], "3.2")
        self.assertIn("repoquery", query.call_args.args[1])

    def test_deb_metadata_requires_exact_package_identity_and_arch(self):
        metadata = ("Package: gimp\nVersion: 3.0.4\nArchitecture: amd64\n"
                    "Description: editor\nDepends: libc6\nMaintainer: Debian Team\n\n")
        with patch.object(catalog, "_run", return_value=metadata), \
             patch.object(catalog.platform, "machine", return_value="x86_64"):
            result = catalog.package_info("deb", "gimp")
        self.assertEqual(result["install_method"], "repository")
        self.assertEqual(result["version"], "3.0.4")
        self.assertEqual(result["container"], "debian-apps")
        self.assertNotIn("file", result)
        bad = metadata.replace("Architecture: amd64", "Architecture: arm64")
        with patch.object(catalog, "_run", return_value=bad), \
             patch.object(catalog.platform, "machine", return_value="x86_64"):
            with self.assertRaisesRegex(RuntimeError, "incompatible"):
                catalog.package_info("deb", "gimp")

    def test_rpm_metadata_is_exact_package_and_arch(self):
        response = ("gimp-devel\t3.2-4\tx86_64\tWrong match\n"
                    "gimp\t3.2-4\tx86_64\tImage editor\n")
        with patch.object(catalog, "_run", return_value=response), \
             patch.object(catalog.platform, "machine", return_value="x86_64"):
            result = catalog.package_info("rpm", "gimp")
        self.assertEqual(result["version"], "3.2-4")
        self.assertEqual(result["description"], "Image editor")
        self.assertEqual(result["container"], "fedora-apps")

    def test_prepare_requires_explicit_call_and_closes_engine(self):
        engine = Mock()
        with patch.object(catalog.backend, "Engine", return_value=engine), \
             patch.object(catalog, "ready", return_value=True):
            catalog.prepare("deb")
        engine.ensure.assert_called_once()
        engine.enter.assert_called_once_with(unittest.mock.ANY,
                                              ["sudo", "apt-get", "update"])
        engine.close.assert_called_once()


class RepositoryBackendTests(unittest.TestCase):
    def info(self):
        return {"kind": "deb", "name": "gimp", "version": "3.0",
                "architecture": "amd64", "install_method": "repository",
                "container": "debian-apps",
                "image": "docker.io/library/debian:13",
                "description": "Image editor"}

    def test_transaction_must_review_matching_repository_metadata(self):
        engine = object.__new__(container_backend.Engine)
        engine.ensure = Mock()
        engine.enter = Mock(return_value=b"Install gimp and 2 dependencies")
        engine._checked_repository_info = Mock()
        output = engine.transaction_repository(self.info())
        self.assertIn("Install gimp", output)
        self.assertIn("--simulate", engine.enter.call_args.args[1])
        engine._checked_repository_info.assert_called_once()

    def test_repository_installs_use_package_name_and_registry_not_files(self):
        engine = object.__new__(container_backend.Engine)
        engine.registry = {}
        engine.ensure = Mock()
        engine._checked_repository_info = Mock()
        engine.enter = Mock(side_effect=[b"installed", b""])
        engine.visible_entries = Mock(return_value=[])
        engine.save = Mock()
        record = engine.install_repository(self.info(), lambda entries: None)
        self.assertEqual(record["status"], "installed")
        self.assertEqual(record["install_method"], "repository")
        self.assertEqual(engine.registry["deb:gimp"]["status"], "installed")
        install_argv = engine.enter.call_args_list[0].args[1]
        self.assertEqual(install_argv[-1], "gimp")
        self.assertIn("apt-get", install_argv)
        self.assertNotIn("sh", install_argv)

    def test_repository_package_must_match_reviewed_version(self):
        engine = object.__new__(container_backend.Engine)
        from repository_catalog import package_info
        with patch("repository_catalog.package_info",
                   return_value={**self.info(), "version": "4.0"}):
            with self.assertRaisesRegex(RuntimeError, "changed"):
                engine._checked_repository_info(self.info())


if __name__ == "__main__":
    unittest.main()
