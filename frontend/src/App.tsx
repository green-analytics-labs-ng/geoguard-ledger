import { BrowserRouter, Routes, Route } from "react-router-dom";
import { WalletProvider } from "./context/WalletContext";
import ErrorBoundary from "./components/ErrorBoundary";
import { routes } from "./routes";

export default function App() {
  return (
    <WalletProvider>
      <BrowserRouter>
        <ErrorBoundary>
          <Routes>
            {routes.map((route) => (
              <Route key={route.path} path={route.path} element={route.element} />
            ))}
          </Routes>
        </ErrorBoundary>
      </BrowserRouter>
    </WalletProvider>
  );
}
