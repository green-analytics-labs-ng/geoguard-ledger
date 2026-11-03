import type { ReactNode } from "react";
import {
  DashboardPage,
  DatasetDetailPage,
  DatasetListPage,
  SettingsPage,
  UploadPage,
  VerifyPage,
} from "./lazyPages";

export interface RouteDef {
  path: string;
  element: ReactNode;
}

// Single source of truth for client-side routes. Consumed by App.tsx so the
// route table lives in one place instead of being inlined in the component tree.
//
// The page components themselves come from `lazyPages.ts`: this module is data,
// and a data module that also declared the components would be a module Fast
// Refresh cannot update.
export const routes: RouteDef[] = [
  { path: "/", element: <DashboardPage /> },
  { path: "/upload", element: <UploadPage /> },
  { path: "/datasets", element: <DatasetListPage /> },
  { path: "/datasets/:id", element: <DatasetDetailPage /> },
  { path: "/verify", element: <VerifyPage /> },
  { path: "/settings", element: <SettingsPage /> },
];
