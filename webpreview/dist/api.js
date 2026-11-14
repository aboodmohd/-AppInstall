export class PreviewApi {
    constructor(token) {
        this.token = token;
    }
    /** The token travels in the URL fragment, so it is never sent to the
     * server as part of the request line. */
    static tokenFromLocation(hash) {
        const raw = hash.startsWith('#') ? hash.slice(1) : hash;
        for (const part of raw.split('&')) {
            const [name, value] = part.split('=');
            if (name === 'token' && value) {
                return decodeURIComponent(value);
            }
        }
        return '';
    }
    async request(path, body) {
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
        return (await response.json());
    }
    state() {
        return this.request('/api/state');
    }
    async setFavorite(key, favorite) {
        const result = await this.request('/api/favorite', {
            key,
            favorite,
        });
        return result.favorites;
    }
    async setTheme(theme) {
        const result = await this.request('/api/theme', { theme });
        return result.theme;
    }
}
