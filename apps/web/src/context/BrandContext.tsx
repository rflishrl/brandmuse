import type React from "react";
import type { DocumentResponse } from "@/api/model";
import { BrandSync } from "@/components/BrandSync";
import { useBrandStore } from "@/store/useBrandStore";

export interface BrandContextType {
  selectedDocumentId: string | null;
  selectedDocument: DocumentResponse | null;
  documents: DocumentResponse[];
  isLoadingDocuments: boolean;
  setSelectedDocumentId: (id: string | null) => void;
  loadSampleBrand: () => Promise<DocumentResponse | undefined>;
  isLoadingSample: boolean;
  refetchDocuments: () => void;
  isServerWarmingUp: boolean;
  isServerHealthy: boolean;
  isServerOffline: boolean;
}

/**
 * Compatibility hook for existing components.
 * For optimal performance, prefer subscribing to individual slices directly via useBrandStore.
 */
export const useBrand = (): BrandContextType => {
  const selectedDocumentId = useBrandStore((s) => s.selectedDocumentId);
  const selectedDocument = useBrandStore((s) => s.selectedDocument);
  const documents = useBrandStore((s) => s.documents);
  const isLoadingDocuments = useBrandStore((s) => s.isLoadingDocuments);
  const setSelectedDocumentId = useBrandStore((s) => s.setSelectedDocumentId);
  const loadSampleBrand = useBrandStore((s) => s.loadSampleBrand);
  const isLoadingSample = useBrandStore((s) => s.isLoadingSample);
  const refetchDocuments = useBrandStore((s) => s.refetchDocuments);
  const isServerWarmingUp = useBrandStore((s) => s.isServerWarmingUp);
  const isServerHealthy = useBrandStore((s) => s.isServerHealthy);
  const isServerOffline = useBrandStore((s) => s.isServerOffline);

  return {
    selectedDocumentId,
    selectedDocument,
    documents,
    isLoadingDocuments,
    setSelectedDocumentId,
    loadSampleBrand,
    isLoadingSample,
    refetchDocuments,
    isServerWarmingUp,
    isServerHealthy,
    isServerOffline,
  };
};

/**
 * BrandProvider mounts the synchronization bridge.
 */
export const BrandProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <>
      <BrandSync />
      {children}
    </>
  );
};
