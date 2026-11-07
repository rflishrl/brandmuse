import React, { useEffect } from "react";
import { X, ExternalLink, CheckCircle2, BookOpen } from "lucide-react";
import { CitationItem } from "@/types/chat";
import { Badge } from "@/components/ui/badge";

interface SourcesDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  citations: CitationItem[];
  traceUrl?: string | null;
}

export const SourcesDrawer: React.FC<SourcesDrawerProps> = ({
  isOpen,
  onClose,
  citations,
  traceUrl,
}) => {
  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden" role="dialog" aria-modal="true" aria-labelledby="sources-drawer-title">
      {/* Backdrop with modern-web scroll containment */}
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-sm transition-opacity overflow-hidden [overscroll-behavior:contain]"
        onClick={onClose}
        aria-hidden="true"
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md bg-surface border-l border-border shadow-xl flex flex-col justify-between animate-in slide-in-from-right duration-200">
          {/* Header */}
          <div className="p-5 border-b border-border flex items-center justify-between">
            <div className="flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-foreground/80" aria-hidden="true" />
              <div>
                <h3 id="sources-drawer-title" className="font-semibold text-base text-foreground">
                  Retrieved Guideline Sources
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {citations.length} chunk{citations.length === 1 ? "" : "s"} fused with Reciprocal Rank Fusion
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-surface-user transition-colors"
              aria-label="Close sources panel"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Body: Citations List with overscroll containment */}
          <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-4 [overscroll-behavior:contain]">
            {citations.map((cite, idx) => (
              <div
                key={`${cite.chunk_index}-${idx}`}
                className="p-4 rounded-card bg-surface-user border border-border flex flex-col gap-2.5 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Badge variant="quote" className="font-semibold text-xs">
                      Page {cite.page}
                    </Badge>
                    <span className="text-[11px] text-muted-foreground">
                      Chunk #{cite.chunk_index}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 text-[11px] text-success-text font-medium">
                    <CheckCircle2 className="w-3.5 h-3.5 text-success-icon" aria-hidden="true" />
                    <span>RRF {(cite.rrf_score * 100).toFixed(2)}</span>
                  </div>
                </div>

                <p className="text-xs text-foreground leading-relaxed italic bg-surface p-3 rounded-lg border border-border/60">
                  "{cite.snippet}"
                </p>

                {/* Score breakdown chips */}
                <div className="flex flex-wrap items-center gap-2 text-[10px] text-muted-foreground pt-1">
                  {cite.vector_score !== null && cite.vector_score !== undefined && (
                    <span className="bg-surface px-2 py-0.5 rounded border border-border">
                      Vector Cosine: {cite.vector_score.toFixed(3)}
                    </span>
                  )}
                  {cite.keyword_score !== null && cite.keyword_score !== undefined && (
                    <span className="bg-surface px-2 py-0.5 rounded border border-border">
                      Keyword Rank: {cite.keyword_score.toFixed(3)}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Footer: Langfuse Trace Link */}
          {traceUrl && (
            <div className="p-4 border-t border-border bg-surface-user flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Auditability Trace</span>
              <a
                href={traceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-xs font-medium text-foreground hover:underline"
              >
                <span>View trace in Langfuse</span>
                <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
