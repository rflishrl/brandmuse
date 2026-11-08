import {
  AlertTriangle,
  Calendar,
  Download,
  ExternalLink,
  Image as ImageIcon,
  Megaphone,
  RotateCcw,
  X,
} from "lucide-react";
import type React from "react";
import { useEffect, useState } from "react";
import { Link } from "react-router";
import { useGetGallery } from "@/api/generated";
import type { GenerationItem } from "@/api/model";
import { Button } from "@/components/ui/button";

export const GalleryPage: React.FC = () => {
  const { data, isLoading, isError, error, refetch } = useGetGallery();
  const generations = data?.generations || [];

  const [activeLightboxItem, setActiveLightboxItem] = useState<GenerationItem | null>(null);

  // Close lightbox on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && activeLightboxItem) {
        setActiveLightboxItem(null);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeLightboxItem]);

  return (
    <div className="w-full flex flex-col gap-8 animate-in fade-in duration-200">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-foreground">Asset Gallery</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Permanent Stable Diffusion assets generated during your active creative session.
          </p>
        </div>

        <Button variant="default" asChild className="shrink-0">
          <Link to="/campaign">
            <Megaphone className="w-4 h-4 mr-2" />
            Create Campaign
          </Link>
        </Button>
      </div>

      {/* Grid, Error, or Empty State */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="aspect-square rounded-card bg-surface-user border border-border/50 dark:bg-white/[0.04] animate-pulse"
            />
          ))}
        </div>
      ) : isError ? (
        <div className="p-10 rounded-card bg-surface border border-danger/25 text-center flex flex-col items-center justify-center gap-3 shadow-xs">
          <div className="w-10 h-10 rounded-full bg-danger/10 flex items-center justify-center text-danger">
            <AlertTriangle className="w-5 h-5" aria-hidden="true" />
          </div>
          <div className="max-w-md">
            <h3 className="font-semibold text-sm text-foreground">Failed to load asset gallery</h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              {(error as { message?: string })?.message ||
                "Could not retrieve session images. Please check your network connection."}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={() => refetch()} className="gap-2 mt-1">
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Retry</span>
          </Button>
        </div>
      ) : generations.length === 0 ? (
        <div className="p-12 rounded-card bg-surface border border-border text-center flex flex-col items-center justify-center gap-4 shadow-xs">
          <div className="w-12 h-12 rounded-full bg-surface-user flex items-center justify-center text-muted-foreground">
            <ImageIcon className="w-6 h-6" aria-hidden="true" />
          </div>
          <div className="max-w-sm">
            <h3 className="font-bold text-base text-foreground">No images generated yet</h3>
            <p className="text-xs text-muted-foreground mt-1">
              Generate 3 on-brand campaign concepts and click "Generate image asset" to populate
              your permanent gallery.
            </p>
          </div>
          <Button variant="default" size="sm" asChild className="mt-2">
            <Link to="/campaign">Go to Campaign Director</Link>
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {generations.map((gen, idx) => {
            const formattedDate = new Date(gen.created_at).toLocaleDateString(undefined, {
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            });

            return (
              <div
                key={gen.id}
                onClick={() => setActiveLightboxItem(gen)}
                className="group relative rounded-card overflow-hidden bg-surface/90 dark:bg-[#141418]/80 border border-border dark:border-white/10 shadow-card hover:border-white/20 transition-all cursor-pointer flex flex-col"
              >
                <div className="aspect-square w-full overflow-hidden bg-surface-user">
                  <img
                    src={gen.image_url}
                    alt={gen.concept_title}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    loading={idx === 0 ? undefined : "lazy"}
                    fetchPriority={idx === 0 ? "high" : undefined}
                    decoding="async"
                  />
                </div>

                <div className="p-4 flex flex-col gap-1">
                  <h4 className="font-semibold text-sm text-foreground truncate group-hover:text-white transition-colors">
                    {gen.concept_title}
                  </h4>
                  <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3 h-3" />
                      {formattedDate}
                    </span>
                    <span className="capitalize">{gen.provider}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Accessible Lightbox Modal */}
      {activeLightboxItem && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 md:p-8"
          role="dialog"
          aria-modal="true"
          aria-labelledby="lightbox-title"
        >
          {/* Backdrop with overscroll containment */}
          <div
            className="fixed inset-0 bg-black/75 backdrop-blur-sm transition-opacity overflow-hidden [overscroll-behavior:contain]"
            onClick={() => setActiveLightboxItem(null)}
            aria-hidden="true"
          />

          <div className="relative z-10 w-full max-w-4xl max-h-[90vh] bg-surface/95 dark:bg-[#141418]/95 backdrop-blur-2xl rounded-card border border-border dark:border-white/15 shadow-2xl flex flex-col md:flex-row overflow-hidden [overscroll-behavior:contain] animate-in zoom-in-95 duration-200">
            {/* Image container */}
            <div className="flex-1 bg-black flex items-center justify-center min-h-[300px] max-h-[60vh] md:max-h-full">
              <img
                src={activeLightboxItem.image_url}
                alt={activeLightboxItem.concept_title}
                className="w-full h-full object-contain"
                decoding="async"
                fetchPriority="high"
              />
            </div>

            {/* Sidebar metadata inside lightbox */}
            <div className="w-full md:w-[320px] p-6 bg-surface flex flex-col justify-between border-t md:border-t-0 md:border-l border-border shrink-0">
              <div className="flex flex-col gap-4">
                <div className="flex items-start justify-between gap-2">
                  <h3
                    id="lightbox-title"
                    className="font-bold text-lg text-foreground leading-snug"
                  >
                    {activeLightboxItem.concept_title}
                  </h3>
                  <button
                    type="button"
                    onClick={() => setActiveLightboxItem(null)}
                    className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-surface-user transition-colors"
                    aria-label="Close image lightbox"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>

                {typeof activeLightboxItem.concept_json?.caption === "string" && (
                  <div className="text-xs text-foreground/85 bg-surface-user p-3 rounded-lg border border-border/50 italic leading-relaxed">
                    "{activeLightboxItem.concept_json.caption}"
                  </div>
                )}

                <div className="flex flex-col gap-1.5 text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">Generation Details</span>
                  <span>Provider: {activeLightboxItem.provider}</span>
                  <span>Created: {new Date(activeLightboxItem.created_at).toLocaleString()}</span>
                </div>
              </div>

              <div className="flex flex-col gap-2 pt-6">
                <Button variant="default" className="w-full" asChild>
                  <a
                    href={activeLightboxItem.image_url}
                    download={`brandmuse-${activeLightboxItem.concept_title.toLowerCase().replace(/\s+/g, "-")}.png`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <Download className="w-4 h-4 mr-2" />
                    Download PNG
                  </a>
                </Button>
                <a
                  href={activeLightboxItem.image_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-center text-xs text-foreground hover:underline flex items-center justify-center gap-1 py-1"
                >
                  <span>Open raw image URL</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
