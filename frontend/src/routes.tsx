import type { ReactNode } from "react";
import DashboardPage from "./pages/DashboardPage";
import UploadPage from "./pages/UploadPage";
import DatasetListPage from "./pages/DatasetListPage";
import DatasetDetailPage from "./pages/DatasetDetailPage";
import VerifyPage from "./pages/VerifyPage";
import SettingsPage from "./pages/SettingsPage";

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
