"""Phase 5: source-aware AppStream identities and metadata normalization."""
import unittest
from unittest.mock import patch

import catalog_metadata as meta


EXACT = """<?xml version="1.0"?>
<components version="1.0">
 <component type="desktop-application">
  <id>org.gimp.GIMP</id>
  <pkgname>gimp</pkgname>
  <name>GNU Image Manipulation Program</name>
  <summary>Create images and edit photographs</summary>
  <developer_name>GIMP Team</developer_name>
  <project_license>GPL-3.0-or-later</project_license>
  <url type="homepage">https://www.gimp.org/</url>
  <categories><category>Graphics</category><category>2DGraphics</category></categories>
  <icon type="remote">https://appstream.debian.org/media/pool/org/gimp/GIMP/icon.png</icon>
 </component>
</components>"""


class NormalizationTests(unittest.TestCase):
    def test_same_package_name_is_distinct_for_every_source(self):
        values = [meta.normalize({"source": source, "appId": "gimp", "name": "GIMP"})
                  for source in ("DEB", "RPM", "AppImage")]
        self.assertEqual(len({v["providerKey"] for v in values}), 3)
        self.assertEqual(values[0]["providerKey"], "deb:gimp")
        self.assertEqual(values[1]["providerKey"], "rpm:gimp")
        self.assertEqual(values[2]["providerKey"], "appimage:gimp")
        flatpak = meta.normalize({
            "source": "Flatpak", "appId": "org.gimp.GIMP", "name": "GIMP"})
        self.assertEqual(flatpak["providerKey"], "flatpak:org.gimp.GIMP")

    def test_normalize_dedupes_within_source_without_merging_sources(self):
        rows = [
            {"source": "DEB", "appId": "gimp"},
            {"source": "DEB", "appId": "gimp"},
            {"source": "RPM", "appId": "gimp"},
        ]
        self.assertEqual([x["providerKey"] for x in meta.normalize_rows(rows)],
                         ["deb:gimp", "rpm:gimp"])

    def test_untrusted_ids_are_rejected(self):
        for source, name in (
            ("DEB", "--remove"), ("RPM", "../root"), ("AppImage", "../escape"),
            ("Flatpak", "a/b"), ("OTHER", "gimp"), ("DEB", ""),
        ):
            with self.subTest(name=name), self.assertRaises(ValueError):
                meta.qualified_id(source, name)

    def test_optional_missing_metadata_is_not_fabricated(self):
        value = meta.normalize({
            "source": "DEB", "appId": "gimp", "summary": "  An editor  "})
        self.assertEqual(value["name"], "gimp")
        self.assertEqual(value["summary"], "An editor")
        for field in ("developer", "version", "license", "homepage", "componentId"):
            self.assertEqual(value[field], "")

    def test_remote_homepage_requires_https_no_credentials(self):
        for homepage in ("http://example.org", "javascript:alert(1)",
                         "https://user:pass@example.org/",
                         "file:///etc/passwd"):
            self.assertEqual(meta.normalize({
                "source": "Flatpak", "appId": "org.example.App",
                "homepage": homepage})["homepage"], "")
        self.assertEqual(meta.normalize({
            "source": "Flatpak", "appId": "org.example.App",
            "homepage": "https://example.org/app"})["homepage"],
            "https://example.org/app")


class AppStreamTests(unittest.TestCase):
    def test_exact_packagename_maps_authoritative_metadata(self):
        data = meta.parse_appstream_xml(EXACT, "gimp", "DEB")
        self.assertEqual(data["name"], "GNU Image Manipulation Program")
        self.assertEqual(data["summary"], "Create images and edit photographs")
        self.assertEqual(data["developer"], "GIMP Team")
        self.assertEqual(data["category"], "Graphics")
        self.assertEqual(data["license"], "GPL-3.0-or-later")
        self.assertEqual(data["homepage"], "https://www.gimp.org/")
        self.assertEqual(data["componentId"], "org.gimp.GIMP")
        self.assertIn("appstream.debian.org", data["iconUrl"])

    def test_fedora_does_not_claim_debian_component_by_name(self):
        self.assertEqual(meta.parse_appstream_xml(
            EXACT, "gimp-data", "RPM"), {})
        self.assertEqual(meta.parse_appstream_xml(
            EXACT, "gimp", "Flatpak"), {})

    def test_multiple_components_per_package_are_ambiguous(self):
        other = """<component><id>org.example.Other</id>
<name>Other</name><pkgname>gimp</pkgname></component>"""
        content = EXACT.replace("</components>", other + "</components>")
        self.assertEqual(meta.parse_appstream_xml(content, "gimp", "DEB"), {})

    def test_malicious_or_oversized_xml_cannot_enrich(self):
        docs = [
            '<!DOCTYPE x [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
            '<component><pkgname>gimp</pkgname><name>&x;</name></component>',
            "<component>" + "a" * (meta.MAX_XML_BYTES + 1) + "</component>",
            "<component><id>bad</id>",
            "<not-a-component><pkgname>gimp</pkgname></not-a-component>",
        ]
        for blob in docs:
            with self.subTest(prefix=blob[:20]):
                self.assertEqual(meta.parse_appstream_xml(blob, "gimp", "DEB"), {})

    def test_ambiguous_relevance_search_never_crossmaps_other_package(self):
        search = ("Identifier: org.gimp.GIMP [desktop-application]\n"
                  "Identifier: org.other.App [desktop-application]\n")
        def query(kind, args, timeout=0):
            self.assertEqual(kind, "rpm")
            self.assertEqual(args[0], "appstreamcli")
            if args[-2:] == ["search", "gimp"]:
                return search
            if args[-2:] == ["dump", "org.gimp.GIMP"]:
                return EXACT.replace("<pkgname>gimp</pkgname>",
                                     "<pkgname>otherpkg</pkgname>")
            if args[-2:] == ["dump", "org.other.App"]:
                return EXACT.replace("<id>org.gimp.GIMP</id>",
                                     "<id>org.other.App</id>")
            raise AssertionError(args)
        with patch.object(meta.repository_catalog, "_run", side_effect=query) as run:
            rows = meta.repo_enrichment("rpm", [{"appId": "gimp"}])
        self.assertEqual(rows["gimp"]["componentId"], "org.other.App")
        self.assertEqual(run.call_count, 3)

    def test_missing_appstream_cli_fails_soft_without_creating_container(self):
        with patch.object(meta.repository_catalog, "_run",
                          side_effect=RuntimeError("appstreamcli not found")) as run:
            self.assertEqual(meta.repo_enrichment(
                "deb", [{"appId": "gimp"}, {"appId": "inkscape"}]), {})
        self.assertEqual(run.call_count, 1)

    def test_nonvisual_packages_are_not_queried(self):
        with patch.object(meta.repository_catalog, "_run") as run:
            self.assertEqual(meta.repo_enrichment(
                "rpm", [{"appId": "libgimp-3"}, {"appId": "gimp-data"}]), {})
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
