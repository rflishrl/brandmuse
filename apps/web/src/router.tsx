import { createBrowserRouter } from "react-router";
import { AppShell } from "@/components/layout/AppShell";
import { HealthCheckPage } from "@/pages/HealthCheckPage";
import { NotFoundPage } from "@/pages/NotFoundPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: (
      <AppShell>
        <HealthCheckPage />
      </AppShell>
    ),
  },
  {
    path: "/ask",
    element: (
      <AppShell>
        <HealthCheckPage />
      </AppShell>
    ),
  },
  {
    path: "/campaign",
    element: (
      <AppShell>
        <HealthCheckPage />
      </AppShell>
    ),
  },
  {
    path: "/gallery",
    element: (
      <AppShell>
        <HealthCheckPage />
      </AppShell>
    ),
  },
  {
    path: "/documents",
    element: (
      <AppShell>
        <HealthCheckPage />
      </AppShell>
    ),
  },
  {
    path: "*",
    element: (
      <AppShell>
        <NotFoundPage />
      </AppShell>
    ),
  },
]);
