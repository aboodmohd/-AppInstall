#!/usr/bin/env python3
"""Regenerate the PKGBUILD b2sums array from its source list.

Every local source in the recipe is checksummed with b2sum, the same
tool makepkg uses. Run this after changing the source list or any
listed file.
"""
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKGBUILD = ROOT / 'PKGBUILD'


def main():
    script = PKGBUILD.read_text()
    sources_match = re.search(r"source=\(([\s\S]*?)\)\s*b2sums=", script)
    if not sources_match:
        raise SystemExit('could not read the source list')
    filenames = re.findall(r"'([^']+)'", sources_match.group(1))
    digests = []
    for name in filenames:
        path = ROOT / name
        if not path.is_file():
            raise SystemExit('missing source: ' + name)
        digests.append(hashlib.blake2b(path.read_bytes()).hexdigest())

    start = script.index('b2sums=(')
    end = script.index(')', start) + 1
    array = 'b2sums=(\n' + ''.join(
        "        '" + digest + "'\n" for digest in digests) + ')'
    PKGBUILD.write_text(script[:start] + array + script[end:])
    print('rewrote ' + str(len(digests)) + ' checksums')


if __name__ == '__main__':
    main()
