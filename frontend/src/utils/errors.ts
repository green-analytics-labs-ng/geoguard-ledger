/** Helpers for turning an API failure into something the user can act on. */

/** Matches absolute http(s) URLs — the only things we render as links. */
const URL_PATTERN = /(https?:\/\/[^\s<>"']+)/g;

/** A run of message text, flagged when it is a URL that should be clickable. */
export interface MessageSegment {
  text: string;
  isUrl: boolean;
}

/**
 * Prefer the backend's `detail` message over axios's generic status text.
 *
 * FastAPI puts the actionable half of a failure in `detail` — the Friendbot
 * link for an unfunded Testnet account, for instance — while axios's own
 * `message` is only "Request failed with status code 400". Preferring `detail`
 * is what lets those instructions reach the user at all.
 */
export function apiErrorMessage(err: unknown, fallback: string): string {
  if (typeof err === "object" && err !== null) {
    const response = (err as { response?: { data?: { detail?: unknown } } }).response;
    const detail = response?.data?.detail;
    if (typeof detail === "string" && detail.length > 0) return detail;
  }
  return err instanceof Error ? err.message : fallback;
}

/**
 * Split a message into text and URL runs.
 *
 * `String.split` with a capturing group interleaves the captured separators, so
 * the URL runs land at odd indices. Naming that here keeps the caller from
 * having to know it.
 */
export function splitMessage(message: string): MessageSegment[] {
  return message.split(URL_PATTERN).map((text, index) => ({
    text,
    isUrl: index % 2 === 1,
  }));
}
