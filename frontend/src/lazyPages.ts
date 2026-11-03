import { lazy } from "react";

// Pages are split into their own chunks and fetched on navigation, so the
// initial bundle only carries the shell plus whichever route is actually
// opened. The upload, dataset and verification views pull in the heaviest
// dependencies — Stellar SDK, Merkle proof rendering, CSV/XML parsing — none of
// which a first paint needs.
//
// These wrappers live apart from the route table in `routes.tsx` because
// `react-refresh/only-export-components` reads a `lazy()` call as a component
// definition. `routes.tsx` exports a table and a type and no components at all,
// so a module that both declared components and exported only data could never
// be hot-updated — which is precisely what the rule reports. Here every export
// is a component, so the rule is satisfied and editing a page swaps it without
// discarding the route table.
//
// `routes.tsx` imports these rather than wrapping the imports itself, so the
// chunk boundaries are still declared in exactly one place.
export const DashboardPage = lazy(() => import("./pages/DashboardPage"));
export const UploadPage = lazy(() => import("./pages/UploadPage"));
export const DatasetListPage = lazy(() => import("./pages/DatasetListPage"));
export const DatasetDetailPage = lazy(() => import("./pages/DatasetDetailPage"));
export const VerifyPage = lazy(() => import("./pages/VerifyPage"));
export const SettingsPage = lazy(() => import("./pages/SettingsPage"));
