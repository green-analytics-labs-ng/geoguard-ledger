/**
 * Storage for the API key attached to write requests.
 *
 * The key is the shared secret configured on the backend via `API_KEYS`. It is
 * entered on the Settings page and kept in `localStorage` so it survives
 * reloads; the API client reads it per request (see `client.ts`), so changing
 * it takes effect immediately. It is not a Stellar secret and never signs
 * anything.
 */

const STORAGE_KEY = "geoguard.apiKey";

export function getApiKey(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? "";
  } catch {
    // Storage can be unavailable (private mode, disabled cookies). Treat that
    // as "no key configured" rather than breaking every API call.
    return "";
  }
}

export function setApiKey(key: string): void {
  const trimmed = key.trim();
  if (trimmed) {
    localStorage.setItem(STORAGE_KEY, trimmed);
  } else {
    localStorage.removeItem(STORAGE_KEY);
  }
}

export function clearApiKey(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export function hasApiKey(): boolean {
  return getApiKey().length > 0;
}
