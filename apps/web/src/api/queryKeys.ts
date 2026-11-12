/**
 * Centralized, type-safe Query Key Factory for BrandMuse.
 * Following TanStack Query best practices for predictable caching and hierarchical invalidation.
 */
export const queryKeys = {
  health: {
    all: ["/api/health"] as const,
  },
  documents: {
    all: ["/api/documents"] as const,
    list: () => [...queryKeys.documents.all] as const,
    detail: (id: string) => [...queryKeys.documents.all, id] as const,
    ontology: (id: string) => [...queryKeys.documents.all, id, "ontology"] as const,
  },
  gallery: {
    all: ["/api/images/gallery"] as const,
  },
} as const;

export type QueryKeys = typeof queryKeys;
