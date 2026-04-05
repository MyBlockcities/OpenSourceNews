/**
 * Central API URL + optional Bearer auth for split deployments
 * (static UI on one host, Flask API on another).
 *
 * - VITE_API_BASE_URL: e.g. https://opensourcenews-api-production.up.railway.app (no trailing slash)
 * - VITE_API_BEARER_TOKEN: optional; only if the API has OPEN_SOURCE_NEWS_API_KEY set.
 *   Note: tokens in Vite builds are visible in the browser bundle — prefer an edge/reverse proxy
 *   that injects Authorization server-side for production.
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

const browserBearer = import.meta.env.VITE_API_BEARER_TOKEN || '';

export function apiFetch(path: string, init?: RequestInit): Promise<Response> {
    const headers = new Headers(init?.headers);
    if (browserBearer && !headers.has('Authorization')) {
        headers.set('Authorization', `Bearer ${browserBearer}`);
    }
    return fetch(apiUrl(path), { ...init, headers });
}
