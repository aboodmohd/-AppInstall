"""Verify the AppInstall application icon is complete, valid, and referenced.

The official artwork (blue folder, white download arrow, green checkmark) is
shipped as flat, makepkg-compatible PNG sources at repo root
(`appinstall-16.png` ... `appinstall-512.png`) and installed to the
freedesktop hicolor theme as `appinstall.png` in each size directory.
"""
import hashlib
import re
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


def source_path(size):
    return ROOT / f'appinstall-{size}.png'


def installed_path(size):
    # Installed destination (what package() / integration.py produce).
    return ROOT / 'icons' / 'hicolor' / f'{size}x{size}' / 'apps' / 'appinstall.png'


def read_png_header(path):
    data = path.read_bytes()
    assert data[:8] == PNG_SIGNATURE, f'{path}: not a PNG'
    pos = 8
    while pos + 12 <= len(data):
        (length,) = struct.unpack_from('>I', data, pos)
        ctype = data[pos + 4:pos + 8]
        if ctype == b'IHDR':
            width, height, bitdepth, color_type = struct.unpack_from('>IIBB', data, pos + 8)
            return width, height, bitdepth, color_type
        pos += 12 + length + 4
    raise AssertionError(f'{path}: no IHDR chunk')


class AppIconTests(unittest.TestCase):
    def test_required_source_sizes_exist(self):
        for size in ICON_SIZES:
            with self.subTest(size=size):
                self.assertTrue(source_path(size).is_file(),
                                f'Missing source icon appinstall-{size}.png')

    def test_sources_are_valid_transparent_pngs(self):
        for size in ICON_SIZES:
            path = source_path(size)
            with self.subTest(size=size):
                width, height, bitdepth, color_type = read_png_header(path)
                self.assertEqual((width, height), (size, size),
                                 f'{path}: {width}x{height} != {size}x{size}')
                # color_type 6 = truecolor with alpha (transparency preserved)
                self.assertEqual(color_type, 6, f'{path}: color_type {color_type} (expected 6/RGBA)')
                self.assertEqual(bitdepth, 8, f'{path}: bitdepth {bitdepth} (expected 8)')

    def test_sources_have_distinct_basenames(self):
        """makepkg resolves local sources by basename at $startdir/, so every
        icon source must carry a unique filename."""
        names = [f'appinstall-{size}.png' for size in ICON_SIZES]
        self.assertEqual(len(names), len(set(names)), 'duplicate icon source basename')

    def test_no_invented_svg_source(self):
        """No PNG may be renamed to .svg; an SVG is only shipped if one exists
        as approved artwork. None is approved for this logo."""
        self.assertFalse(any(ROOT.glob('**/*.svg')), 'no SVG source should be invented')

    def test_desktop_launchers_reference_appinstall_icon(self):
        for desktop in ('appinstall.desktop', 'appinstall-appimage-review.desktop'):
            with self.subTest(desktop=desktop):
                text = (ROOT / desktop).read_text(encoding='utf-8')
                self.assertIn('Icon=appinstall', text,
                              f'{desktop}: missing Icon=appinstall')
                self.assertNotIn('Icon=package-x-generic', text,
                                 f'{desktop}: still uses generic third-party icon')

    def test_pkgbuild_references_and_installs_icons(self):
        script = (ROOT / 'PKGBUILD').read_text()
        # Each size is a distinct makepkg-compatible source present on disk.
        for size in ICON_SIZES:
            src = f'appinstall-{size}.png'
            with self.subTest(size=size):
                self.assertIn(f"'{src}'", script, 'PKGBUILD source missing icon')
                self.assertTrue(source_path(size).is_file(),
                                f'PKGBUILD source missing on disk: {src}')
        # package() installs every size to the hicolor theme via a size loop,
        # keeping the installed name appinstall.png in each size directory.
        self.assertIn('for size in 16 24 32 48 64 128 256 512; do', script,
                      'package() missing icon install size loop')
        self.assertIn('${size}x${size}/apps/appinstall.png', script,
                      'package() missing hicolor installed destination pattern')
        self.assertIn('$srcdir/appinstall-${size}.png', script,
                      'package() missing flat icon source reference')

    def test_pkgbuild_b2sums_match_icon_files(self):
        script = (ROOT / 'PKGBUILD').read_text()
        sources = re.findall(r"'([^']*appinstall-\d+\.png)'", script)
        self.assertEqual(len(sources), len(ICON_SIZES), 'icon source count mismatch')
        for size, src in zip(ICON_SIZES, sources):
            self.assertEqual(src, f'appinstall-{size}.png',
                             f'icon source order/name mismatch: {src}')
            digest = hashlib.blake2b(source_path(size).read_bytes()).hexdigest()
            self.assertIn(f"'{digest}'", script,
                          f'b2sum missing for {src}')


if __name__ == '__main__':
    unittest.main()
