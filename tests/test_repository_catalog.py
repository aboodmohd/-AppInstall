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

    def test_browse_deb_returns_real_filtered_apps_without_a_query(self):
        payload = ("gimp - GNU Image Manipulation Program\n"
                   "inkscape - vector graphics editor\n"
                   "libgimp-3.0-0 - libraries for GIMP\n"
                   "gimp-data - Data files for GIMP\n"
                   "evince - document viewer\n"
                   "gimp-help-de - documentation for GIMP\n"
                   "inkscape - duplicate\n")
        with patch.object(catalog, "ready", return_value=True), \
             patch.object(catalog, "_run", return_value=payload) as cmd:
            results = catalog.browse("deb")
        self.assertEqual({r["appId"] for r in results},
                         {"gimp", "inkscape", "evince"})
        self.assertTrue(all(row["source"] == "DEB" for row in results))
        call = cmd.call_args
        self.assertEqual(call.args[0], "deb")
        self.assertEqual(call.args[1][:2], ["apt-cache", "search"])
        self.assertIn("browser", call.args[1][2])
        self.assertNotIn("gimp", call.args[1][2])

    def test_browse_rpm_selects_gui_desktop_file_providers(self):
        payload = ("gimp\tImage editor\t3.0\tx86_64\n"
                   "evince\tDocument viewer\t47\tnoarch\n"
                   "libpaint\tShared library\t1\tx86_64\n")
        with patch.object(catalog, "ready", return_value=True), \
             patch.object(catalog, "_run", return_value=payload) as cmd:
            rows = catalog.browse("rpm")
        self.assertEqual({r["appId"] for r in rows}, {"gimp", "evince"})
        self.assertEqual(rows[0]["source"], "RPM")
        self.assertIn("--file=/usr/share/applications/*.desktop",
                      cmd.call_args.args[1])

    def test_rpm_browse_falls_back_when_filelists_are_missing(self):
        payload = "firefox\tWeb browser\t145\tx86_64\n"
        with patch.object(catalog, "ready", return_value=True), \
             patch.object(catalog, "_run",
                          side_effect=[RuntimeError("missing filelists"), payload]) as cmd:
            result = catalog.browse("rpm")
        self.assertEqual([row["appId"] for row in result], ["firefox"])
        self.assertEqual(cmd.call_count, 2)
        self.assertIn("*browser*", cmd.call_args.args[1])

    def test_dnf5_queryformat_has_literal_record_separator_for_all_operations(self):
        # DNF5 does NOT append a newline for each queryformat-rendered record.
        result = "gimp\tImage editor\t3.0\tx86_64\nfirefox\tWeb browser\t145\tx86_64\n"
        with patch.object(catalog, "ready", return_value=True), \
             patch.object(catalog, "_run", return_value=result) as runner:
            rows = catalog.browse("rpm")
            self.assertEqual({r["appId"] for r in rows}, {"gimp", "firefox"})
            self.assertTrue(runner.call_args.args[1][4].endswith("\\n"))
            # Test the actual literal DNF5 escape, not a Python newline.
            self.assertNotIn("\n", runner.call_args.args[1][4])

            catalog.search("rpm", "gimp")
            args = runner.call_args.args[1]
            self.assertTrue(args[4].endswith("\\n"))
            self.assertEqual([r["appId"] for r in catalog._rows("rpm", result)],
                             ["gimp", "firefox"])

        metadata = "gimp\t3.0-1\tx86_64\tImage editor\n"
        with patch.object(catalog, "_run", return_value=metadata) as runner, \
             patch.object(catalog.platform, "machine", return_value="x86_64"):
            info = catalog.package_info("rpm", "gimp")
            self.assertEqual(info["name"], "gimp")
            self.assertTrue(runner.call_args.args[1][4].endswith("\\n"))

    def test_rpm_browse_falls_back_when_desktop_query_is_nonempty_but_unparseable(self):
        rows = "firefox\tWeb browser\t145\tx86_64\n"
        with patch.object(catalog, "ready", return_value=True), \
             patch.object(catalog, "_run",
                          side_effect=["unparseable records", rows]) as runner:
            results = catalog.browse("rpm")
        self.assertEqual([row["appId"] for row in results], ["firefox"])
        self.assertEqual(runner.call_count, 2)

    def test_browse_never_creates_a_container_just_to_list_packages(self):
        with patch.object(catalog, "ready", return_value=False), \
             patch.object(container_backend, "Engine") as engine:
            for kind in ("deb", "rpm"):
                with self.subTest(kind=kind), self.assertRaises(catalog.CatalogNotReady):
                    catalog.browse(kind)
        engine.assert_not_called()

    def test_browse_ranks_before_limiting_to_240(self):
        payload = "".join(f"tool-{i:04d} - graphical interface utility\n"
                          for i in range(400))
        with patch.object(catalog, "ready", return_value=True), \
             patch.object(catalog, "_run", return_value=payload):
            results = catalog.browse("deb")
        self.assertEqual(len(results), catalog.SEARCH_LIMIT)
        self.assertEqual(len({r["appId"] for r in results}), catalog.SEARCH_LIMIT)

    def test_prepare_requires_explicit_call_and_closes_engine(self):
        engine = Mock()
        with patch.object(catalog.backend, "Engine", return_value=engine), \
             patch.object(catalog, "ready", return_value=True):
            catalog.prepare("deb")
        engine.ensure.assert_called_once()
        engine.enter.assert_called_once_with(unittest.mock.ANY,
                                              ["sudo", "apt-get", "update"])
        engine.close.assert_called_once()



class RepositoryIconTests(unittest.TestCase):
    """App artwork is optional and cannot affect package search or install."""

    ICON = "https://appstream.debian.org/media/pool/org/gimp/GIMP/abcd/icons/128x128/gimp_gimp.png"

    def setUp(self):
        catalog._debian_appstream_icon.cache_clear()

    def tearDown(self):
        catalog._debian_appstream_icon.cache_clear()

    def test_html_parser_extracts_genuine_debian_appstream_icon(self):
        html = ('<html><body><img alt="Icon" '
                'src="/media/pool/org/gimp/GIMP/abcd/icons/128x128/gimp_gimp.png">'
                '</body></html>').encode()

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def geturl(self):
                return "https://appstream.debian.org/trixie/main/metainfo/gimp.html"

            def read(self, count):
                return html[:count]

        with patch.object(catalog.urllib.request, "build_opener") as opener:
            opener.return_value.open.return_value = Response()
            url = catalog._debian_appstream_icon("gimp")
        self.assertEqual(url, self.ICON)
        sent = opener.return_value.open.call_args.args[0]
        self.assertEqual(sent.full_url,
                         "https://appstream.debian.org/trixie/main/metainfo/gimp.html")

    def test_untrusted_icon_sources_and_unsafe_paths_are_rejected(self):
        bad = [
            "https://evil.invalid/media/pool/icons/128x128/a.png",
            "https://appstream.debian.org.evil.invalid/media/pool/icons/a.png",
            "http://appstream.debian.org/media/pool/icons/a.png",
            "/media/pool/../../etc/passwd/icons/a.png",
            "/media/pool/icons/a.svg",
            "file:///etc/passwd",
            "/media/pool/icons/a.png?token=1",
        ]
        for src in bad:
            with self.subTest(src=src):
                self.assertEqual(catalog._trusted_icon_url(src), "")

    def test_dependency_and_non_gui_package_names_never_request_artwork(self):
        for name in ("gimp-data", "libgimp-3.0-0", "gir1.2-gimp-3.0",
                     "gimp-help-de", "gimp-common", "gimp-doc", "fonts-noto-color-emoji"):
            with self.subTest(name=name):
                self.assertFalse(catalog._is_visual_package(name))
        self.assertTrue(catalog._is_visual_package("gimp"))
        self.assertTrue(catalog._is_visual_package("libreoffice"))
        with patch.object(catalog.urllib.request, "build_opener") as opener:
            self.assertEqual(catalog._debian_appstream_icon("gimp-data"), "")
        opener.assert_not_called()

    def test_icons_for_results_only_enriches_eligible_unique_names(self):
        rows = [
            {"appId": "gimp"}, {"appId": "gimp-data"},
            {"appId": "libgimp-3.0-0"}, {"appId": "gimp"},
        ]
        with patch.object(catalog, "_debian_appstream_icon",
                          side_effect=lambda name: self.ICON if name == "gimp" else "") as icon:
            mapped = catalog.icons_for_results(rows)
        self.assertEqual(mapped, {"gimp": self.ICON})
        icon.assert_called_once_with("gimp")

    def test_metadata_failure_only_affects_icons_not_search(self):
        class Oversize:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def geturl(self):
                return "https://appstream.debian.org/trixie/main/metainfo/gimp.html"

            def read(self, count):
                return b"x" * count

        with patch.object(catalog.urllib.request, "build_opener") as opener:
            opener.return_value.open.return_value = Oversize()
            self.assertEqual(catalog._debian_appstream_icon("gimp"), "")



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
