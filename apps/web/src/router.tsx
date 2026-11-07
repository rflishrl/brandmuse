import { createBrowserRouter, Navigate, Outlet } from "react-router";
import { AppShell } from "@/components/layout/AppShell";
import { BrandProvider } from "@/context/BrandContext";
import { AskPage } from "@/pages/AskPage";
import { CampaignPage } from "@/pages/CampaignPage";
import { DocumentsPage } from "@/pages/DocumentsPage";
import { GalleryPage } from "@/pages/GalleryPage";
import { HealthCheckPage } from "@/pages/HealthCheckPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { OntologyPage } from "@/pages/OntologyPage";

const RootLayout = () => (
  <BrandProvider>
    <AppShell>
      <Outlet />
    </AppShell>
  </BrandProvider>
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
