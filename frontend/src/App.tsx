import { BrowserRouter, Routes, Route } from "react-router-dom";
import { WalletProvider } from "./context/WalletContext";
import ErrorBoundary from "./components/ErrorBoundary";
import AppLayout from "./components/AppLayout";
import { routes } from "./routes";

export default function App() {
  return (
    <WalletProvider>
      <BrowserRouter>
        {/* The boundary wraps the routes rather than sitting inside them, so a
            page that throws during render surfaces the recoverable fallback
            instead of white-screening the tab. */}
        <ErrorBoundary>
          <Routes>
            {/* A pathless layout route: every page renders inside the shared
                shell, and `routes.tsx` stays the only place a path is written
                down. */}
            <Route element={<AppLayout />}>
              {routes.map((route) => (
                <Route key={route.path} path={route.path} element={route.element} />
              ))}
            </Route>
          </Routes>
        </ErrorBoundary>
      </BrowserRouter>
    </WalletProvider>
  );
}
