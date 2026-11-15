#!/usr/bin/env python3
"""Compare the WebView preview with the QML preview.

Both previews are measured against the same inventory, in the same
environment, with the same queries. The harness seeds a temporary
AppInstall registry, runs each preview's own benchmark runner, and
prints a table:

    target    startup      search (median)   idle RSS     idle PSS
    webview   1082.9 ms    15.0 ms          366.0 MiB    235.1 MiB
    qml        520.3 ms     2.1 ms          120.4 MiB    118.9 MiB

Use --json to print the raw numbers instead.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# A fixed inventory: the same rows for both previews, so the comparison
# is about the rendering stack and not about the data.
APPS = (
    ('appimage:alpha', 'Alpha Image Editor', 'appimage', '2.4.1'),
    ('appimage:bravo', 'Bravo Code Studio', 'appimage', '1.9.0'),
    ('appimage:charlie', 'Charlie Notes', 'appimage', '0.8.3'),
    ('flatpak:delta', 'Delta Music Player', 'flatpak', '3.2.0'),
    ('flatpak:echo', 'Echo Video Editor', 'flatpak', '1.4.7'),
    ('flatpak:foxtrot', 'Foxtrot Browser', 'flatpak', '124.0'),
    ('deb:golf', 'Golf Terminal', 'deb', '0.109'),
    ('deb:hotel', 'Hotel Mail', 'deb', '4.2.1'),
    ('rpm:india', 'India Drawing', 'rpm', '1.6.2'),
    ('rpm:juliet', 'Juliet Journal', 'rpm', '2.0.0'),
)


def seed_inventory(root):
    """Write a fixed set of AppInstall records and return the data dir."""
    data = Path(root) / 'data'
    registry = data / 'appinstall'
    registry.mkdir(parents=True, exist_ok=True)
    records = {}
    for key, name, kind, version in APPS:
        records[key] = {
            'kind': kind,
            'name': name,
            'version': version,
            'status': 'installed',
            'description': name + ' — benchmark fixture',
        }
    (registry / 'launchers.json').write_text(json.dumps(records, indent=2))
    return data


def run_benchmark(command, environment, timeout=180):
    """Run one preview's benchmark runner and return its numbers."""
    result = subprocess.run(command, env=environment, capture_output=True,
                            text=True, timeout=timeout)
    for line in result.stdout.splitlines():
        if line.startswith('BENCH '):
            return json.loads(line[len('BENCH '):])
    sys.stderr.write(result.stdout)
    sys.stderr.write(result.stderr)
    raise SystemExit('no benchmark result from: ' + ' '.join(command))


def median(values):
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def aggregate(runs):
    """The median of every metric across repeated runs."""
    if not runs:
        return {}
    result = dict(runs[0])
    result['startup_ms'] = round(median([r['startup_ms'] for r in runs]), 1)
    result['rss_bytes'] = int(median([r['rss_bytes'] for r in runs]))
    result['pss_bytes'] = int(median([r['pss_bytes'] for r in runs]))
    result['apps'] = runs[0]['apps']
    # Every run measures the same queries, so the median run's timings
    # stand for the whole set.
    representative = min(runs, key=lambda r: abs(
        r['startup_ms'] - result['startup_ms']))
    result['search_ms'] = representative['search_ms']
    result['runs'] = len(runs)
    return result


def mib(value):
    return value / (1024.0 * 1024.0)


def print_table(results):
    print()
    print('| target    | startup     | search (median) | idle RSS    | idle PSS    |')
    print('|-----------|-------------|-----------------|-------------|-------------|')
    for name in ('webview', 'qml'):
        result = results.get(name)
        if not result:
            continue
        print('| {0:<9} | {1:>9.1f} ms | {2:>13.2f} ms | {3:>9.1f} MiB | '
              '{4:>9.1f} MiB |'.format(
                  name,
                  result['startup_ms'],
                  median(result['search_ms']),
                  mib(result['rss_bytes']),
                  mib(result['pss_bytes'])))
    print()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Compare the WebView and QML My Applications previews')
    parser.add_argument('--qml-checkout', default=str(ROOT),
                        help='path to a checkout that contains manager_qml.py')
    parser.add_argument('--webview-checkout', default=str(ROOT),
                        help='path to this checkout (the WebView preview)')
    parser.add_argument('--json', action='store_true',
                        help='print the raw numbers as JSON')
    parser.add_argument('--repeat', type=int, default=3,
                        help='how many times to run each preview')
    parser.add_argument('--skip-webview', action='store_true')
    parser.add_argument('--skip-qml', action='store_true')
    args = parser.parse_args(argv)

    workspace = tempfile.mkdtemp(prefix='appinstall-bench-')
    try:
        data = seed_inventory(workspace)
        environment = dict(os.environ)
        environment['XDG_DATA_HOME'] = str(data)
        environment['XDG_STATE_HOME'] = str(Path(workspace) / 'state')
        environment.setdefault('APPINSTALL_DISABLE_UPDATE_TIMER', '1')

        results = {}
        if not args.skip_webview:
            webview = Path(args.webview_checkout).resolve()
            runs = [run_benchmark(
                [sys.executable, str(webview / 'manager_web.py'), '--bench'],
                environment) for _ in range(max(1, args.repeat))]
            results['webview'] = aggregate(runs)
        if not args.skip_qml:
            runs = [run_benchmark(
                [sys.executable, str(Path(__file__).parent / 'bench_qml.py'),
                 '--qml-checkout', args.qml_checkout],
                environment) for _ in range(max(1, args.repeat))]
            results['qml'] = aggregate(runs)
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_table(results)
    return 0


if __name__ == '__main__':
    sys.exit(main())
