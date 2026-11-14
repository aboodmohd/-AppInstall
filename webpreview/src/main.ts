/** Bootstrap: read the backend state, wire the controls, render the list. */
import { PreviewApi } from './api.js';
import { AppListView, Dropdown } from './render.js';
import { DEFAULT_FILTERS } from './types.js';
import type { AppRecord, FilterState, Snapshot } from './types.js';
import { applyFilters } from './view-model.js';

declare global {
  interface Window {
    webkit?: {
      messageHandlers?: Record<string, { postMessage: (message: string) => void }>;
    };
    __appinstall?: {
      benchSearch: (query: string) => Promise<number>;
      state: () => Snapshot;
    };
  }
}

function host(message: string): void {
  const handler = window.webkit?.messageHandlers?.appinstall;
  if (handler) {
    handler.postMessage(message);
  }
}

function requireElement<T extends HTMLElement>(id: string): T {
  const node = document.getElementById(id);
  if (!node) {
    throw new Error(`missing element #${id}`);
  }
  return node as T;
}

function systemPrefersDark(): boolean {
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

/** Run a callback after the next frame has been painted.
 *
 * The animation frame callback runs before the paint; a timer queued
 * from it runs after the frame is on screen. The benchmark reports the
 * painted moment, so it can be compared with the QML preview's
 * afterRendering signal.
 */
function afterPaint(callback: () => void): void {
  requestAnimationFrame(() => {
    window.setTimeout(callback, 0);
  });
}

async function main(): Promise<void> {
  const api = new PreviewApi(PreviewApi.tokenFromLocation(window.location.hash));

  const search = requireElement<HTMLInputElement>('search');
  const list = requireElement<HTMLUListElement>('app-list');
  const empty = requireElement<HTMLElement>('empty');
  const count = requireElement<HTMLElement>('count');
  const error = requireElement<HTMLElement>('error');

  let snapshot: Snapshot = {
    ready: false,
    error: '',
    theme: 'auto',
    favorites: [],
    counts: {},
    apps: [],
  };
  let apps: AppRecord[] = [];
  let filters: FilterState = { ...DEFAULT_FILTERS };
  let themeChoice = 'auto';

  const view = new AppListView(list, empty, count);

  function applyTheme(): void {
    const effective =
      themeChoice === 'auto'
        ? systemPrefersDark()
          ? 'dark'
          : 'light'
        : themeChoice;
    document.documentElement.dataset.theme = effective;
    document.documentElement.dataset.themeChoice = themeChoice;
  }

  function render(): void {
    const filtered =
      filters.search.trim() !== '' ||
      filters.format !== 'all' ||
      filters.status !== 'all';
    empty.textContent = filtered
      ? 'No applications match these filters.'
      : 'No applications yet. Install one and it will show up here.';
    view.render(applyFilters(apps, filters));
  }

  function setFavorites(keys: string[]): void {
    const wanted = new Set(keys);
    for (const app of apps) {
      app.favorite = wanted.has(app.key);
    }
  }

  // ── the state, with a short wait for the inventory to land ─────────

  for (let attempt = 0; attempt < 100; attempt += 1) {
    snapshot = await api.state();
    if (snapshot.ready) {
      break;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 150));
  }

  apps = snapshot.apps;
  themeChoice = snapshot.theme;
  applyTheme();
  window
    .matchMedia('(prefers-color-scheme: dark)')
    .addEventListener('change', () => {
      if (themeChoice === 'auto') {
        applyTheme();
      }
    });

  if (snapshot.error) {
    error.hidden = false;
    error.textContent = snapshot.error;
  }

  // ── controls ───────────────────────────────────────────────────────

  new Dropdown(requireElement('status-menu'), 'all', (value) => {
    filters = { ...filters, status: value as FilterState['status'] };
    render();
  });

  new Dropdown(requireElement('sort-menu'), filters.sort, (value) => {
    filters = { ...filters, sort: value as FilterState['sort'] };
    render();
  });

  new Dropdown(requireElement('theme-menu'), themeChoice, (value) => {
    themeChoice = value;
    applyTheme();
    void api.setTheme(value).catch(() => undefined);
  });

  for (const chip of document.querySelectorAll<HTMLButtonElement>('.chip')) {
    chip.addEventListener('click', () => {
      filters = { ...filters, format: chip.dataset.format as FilterState['format'] };
      for (const other of document.querySelectorAll<HTMLButtonElement>('.chip')) {
        const active = other === chip;
        other.setAttribute('aria-pressed', active ? 'true' : 'false');
        other.classList.toggle('chip--active', active);
      }
      render();
    });
  }

  search.addEventListener('input', () => {
    filters = { ...filters, search: search.value };
    render();
  });
  search.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && search.value !== '') {
      event.preventDefault();
      search.value = '';
      filters = { ...filters, search: '' };
      render();
    }
  });

  list.addEventListener('click', (event) => {
    const button = (event.target as HTMLElement).closest<HTMLButtonElement>(
      '.favorite',
    );
    if (!button) {
      return;
    }
    const key = button.closest<HTMLLIElement>('.app-row')?.dataset.key;
    if (!key) {
      return;
    }
    const app = apps.find((candidate) => candidate.key === key);
    if (!app) {
      return;
    }
    const next = !app.favorite;
    app.favorite = next;
    render();
    void api
      .setFavorite(key, next)
      .then(setFavorites)
      .catch(() => {
        app.favorite = !next;
        render();
      });
  });

  render();

  // The first painted frame is the readiness signal for the smoke test
  // and the benchmark harness.
  afterPaint(() => {
    host('ready:' + String(apps.length));
  });

  window.__appinstall = {
    state: () => snapshot,
    benchSearch: (query: string) => {
      const started = performance.now();
      search.value = query;
      filters = { ...filters, search: query };
      render();
      return new Promise<number>((resolve) => {
        afterPaint(() => {
          const elapsed = performance.now() - started;
          host(`bench:${elapsed.toFixed(2)}`);
          resolve(elapsed);
        });
      });
    },
  };
}

void main().catch((error: unknown) => {
  const banner = document.getElementById('error');
  if (banner) {
    banner.hidden = false;
    banner.textContent =
      error instanceof Error ? error.message : String(error);
  }
  host('error');
});
