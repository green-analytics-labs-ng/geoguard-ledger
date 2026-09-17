import { splitMessage } from "../utils/errors";

interface ErrorBannerProps {
  message: string;
  /** Extra classes for the caller's layout, e.g. a bottom margin. */
  className?: string;
}

/**
 * Red notice for a failed request.
 *
 * Backend errors sometimes name a URL the user has to visit to resolve the
 * problem — Friendbot's faucet, for an unfunded Testnet account — so URLs are
 * rendered as links rather than left as text to copy out by hand.
 */
export default function ErrorBanner({ message, className = "" }: ErrorBannerProps) {
  return (
    <div
      role="alert"
      className={`bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-sm ${className}`.trim()}
    >
      {splitMessage(message).map((segment, index) =>
        segment.isUrl ? (
          <a
            key={index}
            href={segment.text}
            target="_blank"
            rel="noreferrer"
            className="underline break-all"
          >
            {segment.text}
          </a>
        ) : (
          segment.text
        ),
      )}
    </div>
  );
}
