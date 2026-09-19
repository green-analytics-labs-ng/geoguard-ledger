import { lazy, type ReactNode } from "react";

// Pages are split into their own chunks and fetched on navigation, so the
// initial bundle only carries the shell plus whichever route is actually
// opened. The upload, dataset and verification views pull in the heaviest
// dependencies — Stellar SDK, Merkle proof rendering, CSV/XML parsing — none of
// which a first paint needs.
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const UploadPage = lazy(() => import("./pages/UploadPage"));
const DatasetListPage = lazy(() => import("./pages/DatasetListPage"));
const DatasetDetailPage = lazy(() => import("./pages/DatasetDetailPage"));
const VerifyPage = lazy(() => import("./pages/VerifyPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));

// React Router v6 keeps v7's behavioural changes behind opt-in flags, and warns
// on every render that they are unset. Turning them on now means the eventual
// major upgrade is a version bump rather than a behaviour change nobody has
// tested: `v7_startTransition` stops a navigation from blocking paint, and
// `v7_relativeSplatPath` fixes the route a relative link resolves against.
//
// Shared with the tests, which build their own router, so the flags under test
// are the flags that ship.
export const ROUTER_FUTURE_FLAGS = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const;

export interface RouteDef {
  path: string;
  element: ReactNode;
}

// Single source of truth for client-side routes. Consumed by App.tsx so the
// route table lives in one place instead of being inlined in the component tree.
export const routes: RouteDef[] = [
  { path: "/", element: <DashboardPage /> },
  { path: "/upload", element: <UploadPage /> },
  { path: "/datasets", element: <DatasetListPage /> },
  { path: "/datasets/:id", element: <DatasetDetailPage /> },
  { path: "/verify", element: <VerifyPage /> },
  { path: "/settings", element: <SettingsPage /> },
];
