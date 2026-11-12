import { create } from "zustand";
import type { DocumentResponse } from "@/api/model";

const STORAGE_KEY = "brandmuse:selected_document_id";

function getInitialSelectedId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const fromUrl = new URLSearchParams(window.location.search).get("doc");
    if (fromUrl) return fromUrl;
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export interface BrandState {
  selectedDocumentId: string | null;
  selectedDocument: DocumentResponse | null;
  documents: DocumentResponse[];
  isLoadingDocuments: boolean;
  isLoadingSample: boolean;
  isServerWarmingUp: boolean;
  isServerHealthy: boolean;
  isServerOffline: boolean;
}

export interface BrandActions {
  setSelectedDocumentId: (id: string | null) => void;
  setDocuments: (documents: DocumentResponse[]) => void;
  setIsLoadingDocuments: (loading: boolean) => void;
  setIsLoadingSample: (loading: boolean) => void;
  setServerStatus: (status: { warmingUp?: boolean; healthy?: boolean; offline?: boolean }) => void;
  setRefetchDocuments: (fn: () => void) => void;
  setLoadSampleBrandFn: (fn: () => Promise<DocumentResponse | undefined>) => void;
  refetchDocuments: () => void;
  loadSampleBrand: () => Promise<DocumentResponse | undefined>;
}

export type BrandStore = BrandState & BrandActions;

export const useBrandStore = create<BrandStore>()((set, get) => ({
  selectedDocumentId: getInitialSelectedId(),
  selectedDocument: null,
  documents: [],
  isLoadingDocuments: true,
  isLoadingSample: false,
  isServerWarmingUp: false,
  isServerHealthy: false,
  isServerOffline: false,

  setSelectedDocumentId: (id: string | null) => {
    const { documents } = get();
    const doc = documents.find((d) => d.id === id) || null;
    set({ selectedDocumentId: id, selectedDocument: doc });

    try {
      if (id) {
        localStorage.setItem(STORAGE_KEY, id);
      } else {
        localStorage.removeItem(STORAGE_KEY);
      }
    } catch {
      // Ignore localStorage access restrictions
    }

    try {
      const url = new URL(window.location.href);
      if (id) {
        url.searchParams.set("doc", id);
      } else {
        url.searchParams.delete("doc");
      }
      window.history.replaceState(null, "", url.toString());
    } catch {
      // Ignore URL manipulation failures
    }
  },

  setDocuments: (documents: DocumentResponse[]) => {
    const currentId = get().selectedDocumentId;
    let effectiveId = currentId;

    // Auto-select sample document or first available document if none selected
    if (!effectiveId && documents.length > 0) {
      const sample = documents.find((d) => d.is_sample) || documents[0];
      if (sample) {
        effectiveId = sample.id;
        try {
          localStorage.setItem(STORAGE_KEY, sample.id);
        } catch {
          // Ignore localStorage errors
        }
      }
    }

    const doc = documents.find((d) => d.id === effectiveId) || null;
    set({
      documents,
      selectedDocumentId: effectiveId,
      selectedDocument: doc,
    });
  },

  setIsLoadingDocuments: (isLoadingDocuments: boolean) => set({ isLoadingDocuments }),

  setIsLoadingSample: (isLoadingSample: boolean) => set({ isLoadingSample }),

  setServerStatus: (status) =>
    set((state) => ({
      isServerWarmingUp:
        status.warmingUp !== undefined ? status.warmingUp : state.isServerWarmingUp,
      isServerHealthy: status.healthy !== undefined ? status.healthy : state.isServerHealthy,
      isServerOffline: status.offline !== undefined ? status.offline : state.isServerOffline,
    })),

  setRefetchDocuments: (fn: () => void) => {
    set({ refetchDocuments: fn });
  },

  refetchDocuments: () => {
    // Registered by sync component
  },

  setLoadSampleBrandFn: (fn: () => Promise<DocumentResponse | undefined>) => {
    set({ loadSampleBrand: fn });
  },

  loadSampleBrand: async () => {
    return undefined;
  },
}));
