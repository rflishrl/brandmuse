import { lazy, Suspense } from "react";
import { createBrowserRouter, Navigate, Outlet } from "react-router";
import { BrandSync } from "@/components/BrandSync";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { AppShell } from "@/components/layout/AppShell";
import { PageLoadingFallback } from "@/components/layout/PageLoadingFallback";
import { Toaster } from "@/components/ui/sonner";

// Code-split route components via React.lazy
const AskPage = lazy(() => import("@/pages/AskPage"));
const OntologyPage = lazy(() => import("@/pages/OntologyPage"));
const CampaignPage = lazy(() => import("@/pages/CampaignPage"));
const GalleryPage = lazy(() => import("@/pages/GalleryPage"));
const DocumentsPage = lazy(() => import("@/pages/DocumentsPage"));
const HealthCheckPage = lazy(() => import("@/pages/HealthCheckPage"));
const NotFoundPage = lazy(() => import("@/pages/NotFoundPage"));

const RootLayout = () => (
  <ErrorBoundary>
    <BrandSync />
    <AppShell>
      <ErrorBoundary>
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
        element: <AskPage />,
      },
      {
        path: "rules",
        element: <OntologyPage />,
      },
      {
        path: "ontology",
        element: <Navigate to="/rules" replace />,
      },
      {
        path: "campaign",
        element: <CampaignPage />,
      },
      {
        path: "gallery",
        element: <GalleryPage />,
      },
      {
        path: "documents",
        element: <DocumentsPage />,
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
