import type React from "react";
import { useEffect, useRef } from "react";
import { useSearchParams } from "react-router";
import { useGetHealth, useListDocuments, useLoadSampleBrand } from "@/api/generated";
import type { DocumentResponse } from "@/api/model";
import { prefetchPrimaryRoutesIdle } from "@/lib/routePrefetch";
import { useBrandStore } from "@/store/useBrandStore";

export const BrandSync: React.FC = () => {
  const [searchParams] = useSearchParams();
  const setDocuments = useBrandStore((s) => s.setDocuments);
  const setIsLoadingDocuments = useBrandStore((s) => s.setIsLoadingDocuments);
  const setServerStatus = useBrandStore((s) => s.setServerStatus);
  const setRefetchHealth = useBrandStore((s) => s.setRefetchHealth);
  const setRefetchDocuments = useBrandStore((s) => s.setRefetchDocuments);
  const setLoadSampleBrandFn = useBrandStore((s) => s.setLoadSampleBrandFn);
  const setIsLoadingSample = useBrandStore((s) => s.setIsLoadingSample);
  const setSelectedDocumentId = useBrandStore((s) => s.setSelectedDocumentId);

  // Preload lazy route chunks during browser idle time for instant tab switches
  useEffect(() => {
    return prefetchPrimaryRoutesIdle();
  }, []);

  // Sync URL searchParam 'doc' changes into store
  const lastParamRef = useRef<string | null>(null);
  useEffect(() => {
    const docFromUrl = searchParams.get("doc");
    if (docFromUrl && docFromUrl !== lastParamRef.current) {
      lastParamRef.current = docFromUrl;
      const currentId = useBrandStore.getState().selectedDocumentId;
      if (docFromUrl !== currentId) {
        setSelectedDocumentId(docFromUrl);
      }
    }
  }, [searchParams, setSelectedDocumentId]);

  // Background health ping to wake up sleeping container (cold start)
  const {
    data: healthData,
    isLoading: isHealthLoading,
    isFetching: isHealthFetching,
    isError: isHealthError,
    refetch: refetchHealthQuery,
  } = useGetHealth({
    query: {
      retry: 3,
      retryDelay: 3000,
      staleTime: 60_000,
      refetchOnWindowFocus: false,
    },
  });

  useEffect(() => {
    setRefetchHealth(() => {
      void refetchHealthQuery();
    });
  }, [refetchHealthQuery, setRefetchHealth]);

  // Track if backend is taking longer than 2s to wake up
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    if (isHealthLoading || isHealthFetching) {
      timer = setTimeout(() => {
        setServerStatus({ warmingUp: true });
      }, 2000);
    } else {
      setServerStatus({ warmingUp: false });
    }
    return () => clearTimeout(timer);
  }, [isHealthLoading, isHealthFetching, setServerStatus]);

  // Sync health status
  useEffect(() => {
    setServerStatus({
      healthy: healthData?.status === "ok",
      offline: isHealthError && !isHealthFetching,
    });
  }, [healthData, isHealthError, isHealthFetching, setServerStatus]);

  // List documents query
  const {
    data: documentsData,
    isLoading: isLoadingDocs,
    refetch: refetchDocs,
  } = useListDocuments();

  useEffect(() => {
    setIsLoadingDocuments(isLoadingDocs);
  }, [isLoadingDocs, setIsLoadingDocuments]);

  useEffect(() => {
    if (documentsData?.documents) {
      setDocuments(documentsData.documents);
    }
  }, [documentsData, setDocuments]);

  useEffect(() => {
    setRefetchDocuments(() => {
      refetchDocs();
    });
  }, [refetchDocs, setRefetchDocuments]);

  // Sample brand mutation: destructure stable mutateAsync to prevent Zustand cascade re-renders
  const { mutateAsync: loadSampleAsync, isPending: isSamplePending } = useLoadSampleBrand();

  useEffect(() => {
    setIsLoadingSample(isSamplePending);
  }, [isSamplePending, setIsLoadingSample]);

  useEffect(() => {
    const handleLoadSampleBrand = async (): Promise<DocumentResponse | undefined> => {
      try {
        const result = await loadSampleAsync();
        const refetchRes = await refetchDocs();
        const docs = refetchRes.data?.documents || [];
        if (result?.document?.id) {
          setSelectedDocumentId(result.document.id);
        } else if (docs.length > 0) {
          const sample = docs.find((d) => d.is_sample) || docs[0];
          if (sample) setSelectedDocumentId(sample.id);
        }
        return result?.document;
      } catch (err) {
        console.error("Failed to load sample brand:", err);
        throw err;
      }
    };
    setLoadSampleBrandFn(handleLoadSampleBrand);
  }, [loadSampleAsync, refetchDocs, setSelectedDocumentId, setLoadSampleBrandFn]);

  return null;
};
