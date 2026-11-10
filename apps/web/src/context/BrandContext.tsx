import type React from "react";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useSearchParams } from "react-router";
import { useGetHealth, useListDocuments, useLoadSampleBrand } from "@/api/generated";
import type { DocumentResponse } from "@/api/model";

const STORAGE_KEY = "brandmuse:selected_document_id";

interface BrandContextType {
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

const BrandContext = createContext<BrandContextType | undefined>(undefined);

export const BrandProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedId, setSelectedId] = useState<string | null>(() => {
    const fromUrl = searchParams.get("doc");
    if (fromUrl) return fromUrl;
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch {
      return null;
    }
  });

  const [isServerWarmingUp, setIsServerWarmingUp] = useState(false);

  // Background health ping to wake up sleeping container (Hugging Face Spaces cold start)
  const {
    data: healthData,
    isLoading: isHealthLoading,
    isFetching: isHealthFetching,
    isError: isHealthError,
  } = useGetHealth({
    query: {
      retry: 3,
      retryDelay: 3000,
      staleTime: 60_000,
      refetchOnWindowFocus: false,
    },
  });

  // Track if backend is taking longer than 2s to wake up
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    if (isHealthLoading || isHealthFetching) {
      timer = setTimeout(() => {
        setIsServerWarmingUp(true);
      }, 2000);
    } else {
      setIsServerWarmingUp(false);
    }
    return () => clearTimeout(timer);
  }, [isHealthLoading, isHealthFetching]);

  const {
    data: documentsData,
    isLoading: isLoadingDocuments,
    refetch: refetchDocuments,
  } = useListDocuments();

  const documents = documentsData?.documents || [];

  const sampleBrandMutation = useLoadSampleBrand();

  // Keep localStorage and URL query in sync
  const setDocument = useCallback(
    (id: string | null) => {
      setSelectedId(id);
      try {
        if (id) {
          localStorage.setItem(STORAGE_KEY, id);
        } else {
          localStorage.removeItem(STORAGE_KEY);
        }
      } catch {
        // Ignore localStorage error
      }

      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (id) {
            next.set("doc", id);
          } else {
            next.delete("doc");
          }
          return next;
        },
        { replace: true }
      );
    },
    [setSearchParams]
  );

  // Auto-select sample document if none is selected
  useEffect(() => {
    if (!selectedId && documents.length > 0) {
      const sample = documents.find((d) => d.is_sample) || documents[0];
      if (sample) {
        setDocument(sample.id);
      }
    }
  }, [selectedId, documents, setDocument]);

  const selectedDocument = documents.find((d) => d.id === selectedId) || null;

  const handleLoadSampleBrand = async (): Promise<DocumentResponse | undefined> => {
    try {
      const result = await sampleBrandMutation.mutateAsync();
      await refetchDocuments();
      if (result?.document?.id) {
        setDocument(result.document.id);
      }
      return result?.document;
    } catch (err) {
      console.error("Failed to load sample brand:", err);
      return undefined;
    }
  };

  return (
    <BrandContext.Provider
      value={{
        selectedDocumentId: selectedId,
        selectedDocument,
        documents,
        isLoadingDocuments,
        setSelectedDocumentId: setDocument,
        loadSampleBrand: handleLoadSampleBrand,
        isLoadingSample: sampleBrandMutation.isPending,
        refetchDocuments,
        isServerWarmingUp,
        isServerHealthy: healthData?.status === "healthy",
        isServerOffline: isHealthError && !isHealthFetching,
      }}
    >
      {children}
    </BrandContext.Provider>
  );
};

export const useBrand = (): BrandContextType => {
  const context = useContext(BrandContext);
  if (!context) {
    throw new Error("useBrand must be used within a BrandProvider");
  }
  return context;
};
