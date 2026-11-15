/** The list's behaviour, tested without a browser. */
import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  applyFilters,
  describeCount,
  matchesSearch,
  sortApps,
} from '../src/view-model.ts';
import type { AppRecord, FilterState } from '../src/types.ts';

function app(overrides: Partial<AppRecord> = {}): AppRecord {
  return {
    key: 'appimage:Example',
    name: 'Example',
    format: 'appimage',
    formatLabel: 'AppImage',
    version: '1.0.0',
    container: '',
    sizeText: '10 MB',
    sizeBytes: 10 * 1024 * 1024,
    status: 'installed',
    statusLabel: 'Installed',
    statusTone: 'success',
    problems: '',
    favorite: false,
    iconUrl: '',
    initial: 'E',
    lastLaunch: '2026-01-01T10:00:00',
    description: '',
    ...overrides,
  };
}

const filters = (overrides: Partial<FilterState> = {}): FilterState => ({
  search: '',
  format: 'all',
  status: 'all',
  sort: 'name-asc',
  ...overrides,
});

test('search matches the name or the key, case-insensitively', () => {
  const target = app({ name: 'Code Editor', key: 'appimage:code-editor' });
  assert.equal(matchesSearch(target, ''), true);
  assert.equal(matchesSearch(target, '  '), true);
  assert.equal(matchesSearch(target, 'editor'), true);
  assert.equal(matchesSearch(target, 'EDITOR'), true);
  assert.equal(matchesSearch(target, 'appimage:'), true);
  assert.equal(matchesSearch(target, 'photoshop'), false);
});

test('the format filter keeps only that format', () => {
  const apps = [
    app({ key: 'a', name: 'Alpha', format: 'appimage' }),
    app({ key: 'b', name: 'Beta', format: 'flatpak' }),
  ];
  const result = applyFilters(apps, filters({ format: 'flatpak' }));
  assert.deepEqual(
    result.map((entry) => entry.name),
    ['Beta'],
  );
});

test('the status filter keeps only that status', () => {
  const apps = [
    app({ key: 'a', name: 'Alpha', status: 'installed' }),
    app({ key: 'b', name: 'Beta', status: 'missing' }),
  ];
  const result = applyFilters(apps, filters({ status: 'missing' }));
  assert.deepEqual(
    result.map((entry) => entry.name),
    ['Beta'],
  );
});

test('filters and search combine', () => {
  const apps = [
    app({ key: 'a', name: 'Alpha Editor', format: 'appimage' }),
    app({ key: 'b', name: 'Beta Editor', format: 'flatpak' }),
    app({ key: 'c', name: 'Gamma', format: 'appimage' }),
  ];
  const result = applyFilters(
    apps,
    filters({ search: 'editor', format: 'appimage' }),
  );
  assert.deepEqual(
    result.map((entry) => entry.name),
    ['Alpha Editor'],
  );
});

test('sorting by name works in both directions', () => {
  const apps = [
    app({ key: 'a', name: 'Beta' }),
    app({ key: 'b', name: 'alpha' }),
    app({ key: 'c', name: 'Gamma' }),
  ];
  assert.deepEqual(
    sortApps(apps, 'name-asc').map((entry) => entry.name),
    ['alpha', 'Beta', 'Gamma'],
  );
  assert.deepEqual(
    sortApps(apps, 'name-desc').map((entry) => entry.name),
    ['Gamma', 'Beta', 'alpha'],
  );
});

test('sorting by last launch puts the newest first', () => {
  const apps = [
    app({ key: 'a', name: 'Older', lastLaunch: '2026-01-01T10:00:00' }),
    app({ key: 'b', name: 'Newer', lastLaunch: '2026-03-01T10:00:00' }),
    app({ key: 'c', name: 'Never', lastLaunch: '' }),
  ];
  assert.deepEqual(
    sortApps(apps, 'recent').map((entry) => entry.name),
    ['Newer', 'Older', 'Never'],
  );
});

test('sorting by size puts the largest first and unknown sizes last', () => {
  const apps = [
    app({ key: 'a', name: 'Small', sizeBytes: 1024 }),
    app({ key: 'b', name: 'Large', sizeBytes: 4096 }),
    app({ key: 'c', name: 'Unknown', sizeBytes: null }),
  ];
  assert.deepEqual(
    sortApps(apps, 'size').map((entry) => entry.name),
    ['Large', 'Small', 'Unknown'],
  );
});

test('favorites float to the top of the chosen order', () => {
  const apps = [
    app({ key: 'a', name: 'Alpha' }),
    app({ key: 'b', name: 'Bravo', favorite: true }),
    app({ key: 'c', name: 'Charlie', favorite: true }),
  ];
  assert.deepEqual(
    sortApps(apps, 'name-asc').map((entry) => entry.name),
    ['Bravo', 'Charlie', 'Alpha'],
  );
  assert.deepEqual(
    sortApps(apps, 'name-desc').map((entry) => entry.name),
    ['Charlie', 'Bravo', 'Alpha'],
  );
});

test('the count reads like a sentence', () => {
  assert.equal(describeCount(0), '0 applications');
  assert.equal(describeCount(1), '1 application');
  assert.equal(describeCount(6), '6 applications');
});
