/** The loopback API the Python backend exposes. */
import type { Snapshot } from './types.js';

export class PreviewApi {
  private readonly token: string;

  constructor(token: string) {
    this.token = token;
  }

  /** The token travels in the URL fragment, so it is never sent to the
   * server as part of the request line. */
  static tokenFromLocation(hash: string): string {
    const raw = hash.startsWith('#') ? hash.slice(1) : hash;
    for (const part of raw.split('&')) {
      const [name, value] = part.split('=');
      if (name === 'token' && value) {
        return decodeURIComponent(value);
      }
    }
    return '';
  }

  private async request<T>(path: string, body?: unknown): Promise<T> {
    const response = await fetch(path, {
      method: body === undefined ? 'GET' : 'POST',
      headers: {
        'X-AppInstall-Token': this.token,
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!response.ok) {
      throw new Error(`${path} failed: ${response.status}`);
    }
    return (await response.json()) as T;
  }

  state(): Promise<Snapshot> {
    return this.request<Snapshot>('/api/state');
  }

  async setFavorite(key: string, favorite: boolean): Promise<string[]> {
    const result = await this.request<{ favorites: string[] }>('/api/favorite', {
      key,
      favorite,
    });
    return result.favorites;
  }

  async setTheme(theme: string): Promise<string> {
    const result = await this.request<{ theme: string }>('/api/theme', { theme });
    return result.theme;
  }
}
