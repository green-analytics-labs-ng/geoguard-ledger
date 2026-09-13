import { Suspense } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { WalletProvider } from "./context/WalletContext";
import ErrorBoundary from "./components/ErrorBoundary";
import { routes } from "./routes";

// Shown while a lazily-loaded route chunk is fetched. `role="status"` with
// `aria-live="polite"` announces the wait to screen readers rather than
// silently swapping the content in.
function RouteLoadingFallback() {
  return (
    <div role="status" aria-live="polite" className="p-8 text-center text-sm text-gray-500">
      Loading…
    </div>
  );
}

export default function App() {
  return (
    <WalletProvider>
      <BrowserRouter>
        {/* Suspense sits inside the error boundary so a chunk that fails to
            download surfaces the recoverable fallback instead of white-screening. */}
        <ErrorBoundary>
          <Suspense fallback={<RouteLoadingFallback />}>
            <Routes>
              {routes.map((route) => (
                <Route key={route.path} path={route.path} element={route.element} />
              ))}
            </Routes>
          </Suspense>
        </ErrorBoundary>
      </BrowserRouter>
    </WalletProvider>
  );
}
