import type { QueryClient } from "@tanstack/react-query";
import {
  getGetGalleryQueryOptions,
  getGetOntologyApiDocumentsDocumentIdOntologyGetQueryOptions,
} from "@/api/generated";

export const routeImporters = {
  "/ask": () => import("@/pages/AskPage"),
  "/rules": () => import("@/pages/OntologyPage"),
  "/campaign": () => import("@/pages/CampaignPage"),
  "/gallery": () => import("@/pages/GalleryPage"),
  "/documents": () => import("@/pages/DocumentsPage"),
  "/health": () => import("@/pages/HealthCheckPage"),
} as const;

export type PrefetchableRoute = keyof typeof routeImporters;

const prefetchedRoutes = new Set<string>();

/** Preload a route's lazy JS chunk once. */
export function prefetchRoute(path: string): void {
  if (!(path in routeImporters) || prefetchedRoutes.has(path)) {
    return;
  }
  prefetchedRoutes.add(path);
  const importer = routeImporters[path as PrefetchableRoute];
  void importer().catch(() => {
    prefetchedRoutes.delete(path);
  });
}

/** Prefetch primary tab chunks during browser idle time after initial render. */
export function prefetchPrimaryRoutesIdle(): () => void {
  const primaryTabs: PrefetchableRoute[] = [
    "/ask",
    "/rules",
    "/campaign",
    "/gallery",
    "/documents",
  ];

  const run = () => {
    primaryTabs.forEach((path) => {
      prefetchRoute(path);
    });
  };

  if (typeof window !== "undefined" && "requestIdleCallback" in window) {
    const idleId = window.requestIdleCallback(run, { timeout: 1500 });
    return () => window.cancelIdleCallback(idleId);
  }

  const timer = setTimeout(run, 400);
  return () => clearTimeout(timer);
}

/** Prefetch route API queries on explicit user intent (hover/focus). */
export function prefetchRouteData(
  queryClient: QueryClient,
  path: string,
  selectedDocumentId: string | null
): void {
  if (path === "/rules" && selectedDocumentId) {
    void queryClient.prefetchQuery(
      getGetOntologyApiDocumentsDocumentIdOntologyGetQueryOptions(selectedDocumentId)
    );
  } else if (path === "/gallery") {
    void queryClient.prefetchQuery(getGetGalleryQueryOptions({ limit: 24, offset: 0 }));
  }
}
