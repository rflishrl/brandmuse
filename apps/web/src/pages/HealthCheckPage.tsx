import { AlertTriangle, CheckCircle2, Cpu, Database, RefreshCw, ShieldCheck } from "lucide-react";
import type React from "react";
import { useEffect, useState } from "react";
import { useGetHealth } from "@/api/generated";
import { Button } from "@/components/ui/button";
import { getSessionId } from "@/lib/session";

export const HealthCheckPage: React.FC = () => {
  const { data, isLoading, isError, error, refetch, isFetching } = useGetHealth({
    query: {
      retry: 3,
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 10000),
    },
  });

  const [wakeUpNotice, setWakeUpNotice] = useState(false);
  const sessionId = getSessionId();

  // Show waking up notice if request takes > 5s
  useEffect(() => {
    let timer: NodeJS.Timeout | number;
    if (isLoading || isFetching) {
      timer = setTimeout(() => {
        setWakeUpNotice(true);
      }, 5000);
    } else {
      setWakeUpNotice(false);
    }
    return () => clearTimeout(timer);
  }, [isLoading, isFetching]);

  return (
    <div className="flex flex-col gap-6 animate-in fade-in duration-300">
      {/* Title Header */}
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-foreground bg-white/10 px-2.5 py-1 rounded-full">
            Phase 1 Foundation
          </span>
        </div>
        <h2 className="text-2xl font-bold tracking-tight mt-1">System Health & API Contract</h2>
        <p className="text-sm text-muted-foreground">
          Live verification of the FastAPI backend, PostgreSQL database, and typed Orval TanStack
          Query client.
        </p>
      </div>

      {/* Sleeping server / wake up banner */}
      {wakeUpNotice && (
        <div
          role="status"
          className="p-4 rounded-card bg-surface-user border border-border flex items-start gap-3 text-sm text-foreground"
        >
          <RefreshCw className="w-5 h-5 text-foreground animate-spin shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-foreground">Server is waking up</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Connecting to the backend service. This can take up to a minute on free/starter tiers.
            </p>
          </div>
        </div>
      )}

      {/* Main Status Card */}
      <div className="rounded-card bg-surface p-6 shadow-card border border-border flex flex-col gap-6">
        <div className="flex items-center justify-between pb-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div
              className={`w-3.5 h-3.5 rounded-full ${
                data?.status === "ok"
                  ? "bg-success-icon"
                  : isLoading
                    ? "bg-amber-400 animate-pulse"
                    : "bg-danger"
              }`}
            />
            <div>
              <span className="font-semibold text-base">Backend Status</span>
              <p className="text-xs text-muted-foreground">
                {isLoading
                  ? "Querying /api/health..."
                  : data?.status === "ok"
                    ? "Online and healthy"
                    : "Connection issue"}
              </p>
            </div>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isFetching}
            aria-label="Refresh health check"
            className="gap-2"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </Button>
        </div>

        {/* Loading Skeleton State */}
        {isLoading && (
          <div className="flex flex-col gap-4 animate-pulse">
            <div className="h-10 bg-surface-user rounded-md w-full" />
            <div className="h-10 bg-surface-user rounded-md w-3/4" />
          </div>
        )}

        {/* Error State */}
        {isError && (
          <div className="p-4 rounded-md bg-danger/10 border border-danger/30 text-danger text-sm flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Unable to reach API backend</p>
              <p className="text-xs mt-1 text-danger/90">
                {error instanceof Error
                  ? error.message
                  : "Ensure the FastAPI server is running on port 8000."}
              </p>
            </div>
          </div>
        )}

        {/* Success Data Display */}
        {data && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Database status */}
            <div className="p-4 rounded-xl bg-surface-user flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Database className="w-4 h-4 text-muted-foreground" />
                <span className="text-xs font-medium text-foreground">PostgreSQL</span>
              </div>
              <span className="inline-flex items-center gap-1.5 text-xs font-medium text-success-text">
                <CheckCircle2 className="w-3.5 h-3.5 text-success-icon" />
                {data.database}
              </span>
            </div>

            {/* AI Providers */}
            <div className="p-4 rounded-xl bg-surface-user flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Cpu className="w-4 h-4 text-muted-foreground" />
                <span className="text-xs font-medium text-foreground">LLM Provider</span>
              </div>
              <span className="text-xs font-medium capitalize text-foreground bg-surface px-2 py-0.5 rounded border border-border">
                {data.providers?.llm || "openai"}
              </span>
            </div>

            <div className="p-4 rounded-xl bg-surface-user flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Cpu className="w-4 h-4 text-muted-foreground" />
                <span className="text-xs font-medium text-foreground">Embeddings</span>
              </div>
              <span className="text-xs font-medium capitalize text-foreground bg-surface px-2 py-0.5 rounded border border-border">
                {data.providers?.embeddings || "openai"}
              </span>
            </div>

            <div className="p-4 rounded-xl bg-surface-user flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Cpu className="w-4 h-4 text-muted-foreground" />
                <span className="text-xs font-medium text-foreground">Image Gen</span>
              </div>
              <span className="text-xs font-medium capitalize text-foreground bg-surface px-2 py-0.5 rounded border border-border">
                {data.providers?.image || "stability"}
              </span>
            </div>
          </div>
        )}

        {/* Session ID Information */}
        <div className="pt-4 border-t border-border flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-foreground/80" />
            <span>Client Session (UUID isolation):</span>
          </div>
          <code className="bg-surface-user px-2 py-1 rounded text-[11px] font-mono text-foreground select-all break-all">
            {sessionId}
          </code>
        </div>
      </div>
    </div>
  );
};

export default HealthCheckPage;
