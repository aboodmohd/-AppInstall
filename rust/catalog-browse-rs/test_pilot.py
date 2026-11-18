"""Run explicitly against an MCP-built extension and generated shadow."""

import json
from pathlib import Path
import sys
import unittest

CRATE = Path(__file__).resolve().parent
sys.path[:0] = [str(CRATE.parent.parent), str(CRATE / "python"), str(CRATE / "shadow")]

import catalog_browse as original
import catalog_browse_rs as native
import catalog_browse_shadow as shadow


class CatalogBrowsePilot(unittest.TestCase):
    def test_all_aliases_and_codepoint_boundary(self):
        for expected, aliases in original._ALIASES.items():
            for alias in aliases:
                with self.subTest(alias=alias):
                    self.assertEqual(native.category_for({"category": alias}), expected)
        for width in (135, 136):
            row = {"category": "😀" * width + ";Game"}
            self.assertEqual(native.category_for(row), original.category_for(row))

    def test_native_returns_the_same_objects_without_serializing_rows(self):
        first = {"providerKey": "flatpak:A", "category": "Game", "opaque": object()}
        first["cycle"] = first
        duplicate = dict(first)
        rpm = {"providerKey": "flatpak:B", "category": "Network", "source": "RPM"}
        last = {"providerKey": "flatpak:C", "category": "Game"}
        rows = [None, first, duplicate, rpm, last, first]
        for selected, positions in (("All", range(6)), ("Games", (1, 2, 4, 5))):
            with self.subTest(selected=selected):
                actual = native.filtered_rows(iter(rows), selected)
                self.assertIsNot(actual, rows)
                self.assertEqual(len(actual), len(positions))
                for row, index in zip(actual, positions, strict=True):
                    self.assertIs(row, rows[index])
        featured = native.featured_rows(iter(rows), "Flatpak", limit=1.5)
        self.assertEqual(len(featured), 2)
        self.assertIs(featured[0], first)
        self.assertIs(featured[1], last)

    def test_featured_stops_consuming_the_iterator_at_the_limit(self):
        first = {"providerKey": "flatpak:A"}

        def rows():
            yield first
            self.fail("read past the requested limit")

        self.assertIs(native.featured_rows(rows(), "Flatpak", limit=1)[0], first)
        self.assertEqual(native.featured_rows(None, "RPM"), [])
        self.assertEqual(native.featured_rows(None, "Flatpak", query=None), [])

    def test_generated_shadow_replays_successes_and_returns_python_rows(self):
        count = 0
        for line in (CRATE / "cases.jsonl").read_text().splitlines():
            case = json.loads(line)
            if "ok" not in case:
                continue  # The MCP diff compares recorded exceptions.
            getattr(shadow, case["fn"])(*map(decode, case["args"]))
            count += 1
        first = {"providerKey": "flatpak:A", "category": "Game"}
        self.assertIs(shadow.filtered_rows([first], "Games")[0], first)
        self.assertIs(shadow.featured_rows([first], "Flatpak")[0], first)
        self.assertEqual(shadow.stats, {"calls": count + 2, "mismatches": 0})


def decode(value):
    if isinstance(value, list):
        return [decode(item) for item in value]
    if isinstance(value, dict):
        if value.keys() == {"$int"}:
            return int(value["$int"])
        if value.keys() == {"$num"}:
            return float(value["$num"])
        if value.keys() == {"$float"}:
            return float(value["$float"])
        if value.keys() == {"$tuple"}:
            return tuple(map(decode, value["$tuple"]))
        return {key: decode(item) for key, item in value.items()}
    return value


if __name__ == "__main__":
    unittest.main()
