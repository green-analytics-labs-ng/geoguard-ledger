import { Suspense } from "react";
import { Link, Outlet } from "react-router-dom";
import WalletConnector from "./WalletConnector";

/**
 * Shown while the current route's chunk is being fetched.
 *
 * `role="status"` with `aria-live="polite"` announces the wait to screen
 * readers rather than silently swapping the content in.
 */
function RouteLoadingFallback() {
  return (
    <div role="status" aria-live="polite" className="p-8 text-center text-sm text-gray-500">
      Loading…
    </div>
  );
}

/**
 * The navigation, in the order the routes are declared.
 *
 * Every page used to draw its own nav — a link back to the dashboard, plus a
 * wallet connector on the four pages that anchored anything — so the header
 * changed shape as you navigated and each page had to remember to render it.
 * There is one header now, owned here.
 */
const NAV_ITEMS = [
  { to: "/", label: "Dashboard" },
  { to: "/upload", label: "Upload" },
  { to: "/datasets", label: "Datasets" },
  { to: "/verify", label: "Verify" },
  { to: "/settings", label: "Settings" },
];

/**
 * The shell every route renders inside.
 *
 * The brand is a link rather than a heading: each page owns its own `<h1>`, so
 * putting the application name in a heading here would give every screen two
 * and say nothing about the screen you are on.
 */
export default function AppLayout() {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
          <Link to="/" className="text-lg font-bold text-stellar">
            GeoGuard Ledger
          </Link>

          <nav aria-label="Main" className="flex flex-wrap items-center gap-4 text-sm">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className="text-gray-600 hover:text-stellar transition-colors"
              >
                {item.label}
              </Link>
            ))}
          </nav>

          {/* Anchoring needs a wallet on four of the five pages, so the control
              belongs in the shell rather than in whichever page remembered it. */}
          <WalletConnector compact />
        </div>
      </header>

      <main className="flex-1">
        {/* Inside the shell rather than above it, so navigating to a route
            whose chunk has not been downloaded swaps the page and leaves the
            header where it is. */}
        <Suspense fallback={<RouteLoadingFallback />}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  );
}
