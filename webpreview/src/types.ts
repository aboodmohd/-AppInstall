/** Shared shapes for the My Applications web preview. */

export type Tone = 'success' | 'warning' | 'danger' | 'neutral';

export type AppStatus =
  | 'installed'
  | 'needs-repair'
  | 'missing'
  | 'stale'
  | 'corrupted'
  | 'unknown';

export type AppFormat = 'appimage' | 'flatpak' | 'deb' | 'rpm' | 'unknown';

export type SortKey = 'name-asc' | 'name-desc' | 'recent' | 'size';

/** One inventory row, shaped by the Python backend. */
export interface AppRecord {
  key: string;
  name: string;
  format: AppFormat;
  formatLabel: string;
  version: string;
  container: string;
  sizeText: string;
  sizeBytes: number | null;
  status: AppStatus;
  statusLabel: string;
  statusTone: Tone;
  problems: string;
  favorite: boolean;
  iconUrl: string;
  initial: string;
  lastLaunch: string;
  description: string;
}

/** Everything the user can narrow the list by. */
export interface FilterState {
  search: string;
  format: AppFormat | 'all';
  status: AppStatus | 'all';
  sort: SortKey;
}

export interface Snapshot {
  ready: boolean;
  error: string;
  theme: 'auto' | 'light' | 'dark';
  favorites: string[];
  counts: Record<string, number>;
  apps: AppRecord[];
}

export const DEFAULT_FILTERS: FilterState = {
  search: '',
  format: 'all',
  status: 'all',
  sort: 'name-asc',
};
