"""Phase 6: categories are provider-backed; Featured never invents rankings."""
import unittest
import catalog_browse as browse


class BrowseTests(unittest.TestCase):
    @staticmethod
    def row(name, category="", source="Flatpak"):
        return {"appId": name, "name": name, "category": category,
                "source": source, "providerKey": source.lower() + ":" + name}

    def test_category_aliases_and_missing_values(self):
        for raw, expected in (
            ("Network", "Internet"), ("Graphics;2DGraphics", "Graphics"),
            ("AudioVideo", "Multimedia"), ("IDE", "Development"),
            ("ArcadeGame", "Games"), ("Office", "Office"),
            ("debian 13", "Other"), ("Fedora 44", "Other"),
            ("", "Other"), ("UnknownExternalCategory", "Other"),
        ):
            with self.subTest(raw=raw):
                self.assertEqual(browse.category_for(self.row("app", raw)), expected)

    def test_categories_filter_only_loaded_rows_preserving_identity(self):
        rows = [self.row("a", "Game"), self.row("b", "Network"),
                self.row("c", "Game"), self.row("d")]
        self.assertEqual(browse.categories_for(rows),
                         ["All", "Internet", "Games", "Other"])
        games = browse.filtered_rows(rows, "Games")
        self.assertEqual([r["appId"] for r in games], ["a", "c"])
        self.assertIs(games[0], rows[0])
        self.assertEqual(browse.filtered_rows(rows, "All"), rows)
        self.assertEqual(browse.filtered_rows(rows, "NoCategory"), [])

    def test_featured_only_from_ranked_live_flathub_browse(self):
        rows = [self.row(f"org.example.App{i}", "Graphics") for i in range(9)]
        self.assertEqual(browse.featured_rows(rows, "Flatpak"), rows[:6])
        for source, query in (("Flatpak", "gimp"), ("AppImage", ""),
                              ("DEB", ""), ("RPM", "")):
            self.assertEqual(browse.featured_rows(rows, source, query), [])
        self.assertEqual(browse.featured_rows(rows, "Flatpak", limit=0), [])

    def test_featured_does_not_mix_source_ids_or_duplicate(self):
        first = self.row("org.example.App")
        duplicate = dict(first)
        rpm = self.row("org.example.App", source="RPM")
        self.assertEqual(browse.featured_rows([first, duplicate, rpm], "Flatpak"),
                         [first])


if __name__ == "__main__":
    unittest.main()
