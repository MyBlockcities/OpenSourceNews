/**
 * Central API URL + optional Bearer auth for split deployments
 * (static UI on one host, Flask API on another).
 *
 * - VITE_API_BASE_URL: e.g. https://opensourcenews-api-production.up.railway.app (no trailing slash)
 * - VITE_API_BEARER_TOKEN: private/dev escape hatch only.
 *   Tokens in Vite builds are visible in the browser bundle. Production should prefer
 *   public read endpoints or a same-origin server/edge proxy that injects Authorization.
 * - VITE_ALLOW_BROWSER_BEARER_TOKEN=1: required before VITE_API_BEARER_TOKEN is used.
 */

export function getApiBase(): string {
    return (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
}

/** Absolute URL for JSON/API routes (paths starting with /api/...). */
export function apiUrl(path: string): string {
    if (!path.startsWith('/')) {
        throw new Error(`apiUrl: path must start with /, got ${path}`);
    }
    return `${getApiBase()}${path}`;
}

const browserBearer =
    import.meta.env.VITE_ALLOW_BROWSER_BEARER_TOKEN === '1'
        ? import.meta.env.VITE_API_BEARER_TOKEN || ''
        : '';

export function apiFetch(path: string, init?: RequestInit): Promise<Response> {
    const headers = new Headers(init?.headers);
    if (browserBearer && !headers.has('Authorization')) {
        headers.set('Authorization', `Bearer ${browserBearer}`);
    }
    return fetch(apiUrl(path), { ...init, headers });
}
