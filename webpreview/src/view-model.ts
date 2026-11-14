/**
 * The list's behaviour, with no DOM in sight.
 *
 * These are the same semantics as the QML preview's AppModel: search
 * matches the name or the key, the format and status filters are exact,
 * and favorites float to the top of whichever order was chosen.
 */
import type { AppRecord, FilterState, SortKey } from './types.js';

export function matchesSearch(app: AppRecord, query: string): boolean {
  const text = query.trim().toLowerCase();
  if (!text) {
    return true;
  }
  return (
    app.name.toLowerCase().includes(text) ||
    app.key.toLowerCase().includes(text)
  );
}

function byName(app: AppRecord): string {
  return app.name.toLowerCase();
}

function byLastLaunch(app: AppRecord): string {
  return app.lastLaunch;
}

function bySize(app: AppRecord): number | null {
  return app.sizeBytes;
}

function compareBy(sort: SortKey): (a: AppRecord, b: AppRecord) => number {
  switch (sort) {
    case 'name-desc':
      return (a, b) => byName(b).localeCompare(byName(a));
    case 'recent':
      return (a, b) => {
        const left = byLastLaunch(a);
        const right = byLastLaunch(b);
        if (left === right) {
          return 0;
        }
        return left < right ? 1 : -1;
      };
    case 'size':
      return (a, b) => {
        const left = bySize(a);
        const right = bySize(b);
        if (left === null && right === null) {
          return 0;
        }
        if (left === null) {
          return 1;
        }
        if (right === null) {
          return -1;
        }
        return right - left;
      };
    case 'name-asc':
    default:
      return (a, b) => byName(a).localeCompare(byName(b));
  }
}

/** Sort, then float favorites to the top. */
export function sortApps(apps: AppRecord[], sort: SortKey): AppRecord[] {
  const ordered = [...apps].sort(compareBy(sort));
  const favorites = ordered.filter((app) => app.favorite);
  const rest = ordered.filter((app) => !app.favorite);
  return [...favorites, ...rest];
}

/** Apply search, format and status filters, then sort. */
export function applyFilters(
  apps: AppRecord[],
  filters: FilterState,
): AppRecord[] {
  const matching = apps.filter((app) => {
    if (filters.format !== 'all' && app.format !== filters.format) {
      return false;
    }
    if (filters.status !== 'all' && app.status !== filters.status) {
      return false;
    }
    return matchesSearch(app, filters.search);
  });
  return sortApps(matching, filters.sort);
}

/** The count shown next to the filters. */
export function describeCount(count: number): string {
  return count === 1 ? '1 application' : `${count} applications`;
}
