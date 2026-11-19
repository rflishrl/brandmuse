import { lazy, Suspense } from "react";
import { createBrowserRouter, Navigate, Outlet } from "react-router";
import { BrandSync } from "@/components/BrandSync";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { AppShell } from "@/components/layout/AppShell";
import { CachedTabStage } from "@/components/layout/CachedTabStage";
import { PageLoadingFallback } from "@/components/layout/PageLoadingFallback";
import { Toaster } from "@/components/ui/sonner";
import { routeImporters } from "@/lib/routePrefetch";

// Non-tab routes stay standard lazy routes
const HealthCheckPage = lazy(routeImporters["/health"]);
const NotFoundPage = lazy(() => import("@/pages/NotFoundPage"));

const RootLayout = () => (
  <ErrorBoundary>
    <BrandSync />
    <AppShell>
      <ErrorBoundary>
        <CachedTabStage />
        <Suspense fallback={<PageLoadingFallback />}>
          <Outlet />
        </Suspense>
      </ErrorBoundary>
    </AppShell>
    <Toaster />
  </ErrorBoundary>
);

export const router = createBrowserRouter([
  {
    path: "/",
    element: <RootLayout />,
    children: [
      {
        index: true,
        element: <Navigate to="/ask" replace />,
      },
      {
        path: "ask",
        element: null,
      },
      {
        path: "rules",
        element: null,
      },
      {
        path: "ontology",
        element: <Navigate to="/rules" replace />,
      },
      {
        path: "campaign",
        element: null,
      },
      {
        path: "gallery",
        element: null,
      },
      {
        path: "documents",
        element: null,
      },
      {
        path: "health",
        element: <HealthCheckPage />,
      },
      {
        path: "*",
        element: <NotFoundPage />,
      },
    ],
  },
]);
