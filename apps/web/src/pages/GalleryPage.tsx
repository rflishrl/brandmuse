import {
  AlertTriangle,
  Calendar,
  Check,
  Copy,
  Download,
  ExternalLink,
  Image as ImageIcon,
  Loader2,
  Megaphone,
  RotateCcw,
  X,
} from "lucide-react";
import type React from "react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { useGetGallery } from "@/api/generated";
import type { GenerationItem } from "@/api/model";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/sonner";

const PAGE_SIZE = 24;

function getAspectDimensions(conceptJson?: Record<string, unknown>): { w: number; h: number } {
  const ratio = typeof conceptJson?.aspect_ratio === "string" ? conceptJson.aspect_ratio : "1:1";
  if (ratio === "9:16") return { w: 576, h: 1024 };
  if (ratio === "16:9") return { w: 1024, h: 576 };
  return { w: 1024, h: 1024 };
}

function getDownloadMeta(url: string): { ext: string; label: string } {
  const cleanUrl = url.split("?")[0]?.toLowerCase() ?? "";
  if (cleanUrl.endsWith(".png")) {
    return {
      ext: "png",
      label: "Download PNG",
    };
  }
  return {
    ext: "webp",
    label: "Download WebP",
  };
}

interface GalleryCardProps {
  gen: GenerationItem;
  idx: number;
  onSelect: (gen: GenerationItem) => void;
}

const GalleryCard: React.FC<GalleryCardProps> = ({ gen, idx, onSelect }) => {
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageError, setImageError] = useState(false);

  const displaySrc = gen.thumbnail_url || gen.image_url;
  const formattedDate = new Date(gen.created_at).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <button
      type="button"
      onClick={() => onSelect(gen)}
      className="group relative rounded-card overflow-hidden bg-surface border border-border shadow-xs hover:border-foreground/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-foreground transition-all cursor-pointer flex flex-col text-left w-full"
    >
      <div className="aspect-square w-full relative overflow-hidden bg-surface-user">
        {!imageLoaded && !imageError && (
          <Skeleton className="absolute inset-0 w-full h-full rounded-none" />
        )}

        {imageError ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center p-4 text-center bg-surface-user text-muted-foreground gap-2">
            <ImageIcon className="w-8 h-8 opacity-40" aria-hidden="true" />
            <span className="text-xs">Gambar tidak dapat dimuat</span>
          </div>
        ) : (
          <img
            src={displaySrc}
            alt={gen.concept_title}
            width={480}
            height={480}
            onLoad={() => setImageLoaded(true)}
            onError={() => setImageError(true)}
            className={`w-full h-full object-cover group-hover:scale-105 transition-all duration-300 ${
              imageLoaded ? "opacity-100" : "opacity-0"
            }`}
            loading={idx === 0 ? undefined : "lazy"}
            fetchPriority={idx === 0 ? "high" : undefined}
            decoding="async"
          />
        )}
      </div>

      <div className="p-4 flex flex-col gap-1 w-full">
        <h4 className="font-semibold text-sm text-foreground truncate group-hover:text-foreground/90 transition-colors">
          {gen.concept_title}
        </h4>
        <div className="flex items-center justify-between text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1">
            <Calendar className="w-3 h-3" aria-hidden="true" />
            {formattedDate}
          </span>
          <span className="capitalize font-mono text-[10px] px-1.5 py-0.5 rounded bg-surface-user border border-border/60">
            {gen.provider}
          </span>
        </div>
      </div>
    </button>
  );
};

export const GalleryPage: React.FC = () => {
  const [offset, setOffset] = useState(0);
  const [generations, setGenerations] = useState<GenerationItem[]>([]);

  const { data, isLoading, isFetching, isError, error, refetch } = useGetGallery({
    limit: PAGE_SIZE,
    offset,
  });

  useEffect(() => {
    if (!data?.generations) return;
    if (offset === 0) {
      setGenerations(data.generations);
    } else {
      setGenerations((prev) => {
        const seen = new Set(prev.map((item) => item.id));
        const nextItems = data.generations?.filter((item) => !seen.has(item.id)) ?? [];
        return [...prev, ...nextItems];
      });
    }
  }, [data, offset]);

  const hasMore = Boolean(data?.has_more);

  const [activeLightboxItem, setActiveLightboxItem] = useState<GenerationItem | null>(null);
  const [copiedUrl, setCopiedUrl] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);

  const handleCopyUrl = (url: string) => {
    navigator.clipboard.writeText(url);
    setCopiedUrl(true);
    toast.success("URL gambar berhasil disalin ke clipboard!");
    setTimeout(() => setCopiedUrl(false), 2000);
  };

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (activeLightboxItem) {
      if (!dialog.open) {
        dialog.showModal();
      }
    } else if (dialog.open) {
      dialog.close();
    }
  }, [activeLightboxItem]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    const handleCancel = (e: Event) => {
      e.preventDefault();
      setActiveLightboxItem(null);
    };

    const handleClose = () => {
      setActiveLightboxItem(null);
    };

    dialog.addEventListener("cancel", handleCancel);
    dialog.addEventListener("close", handleClose);
    return () => {
      dialog.removeEventListener("cancel", handleCancel);
      dialog.removeEventListener("close", handleClose);
    };
  }, []);

  const lightboxDims = activeLightboxItem
    ? getAspectDimensions(activeLightboxItem.concept_json)
    : { w: 1024, h: 1024 };
  const downloadMeta = activeLightboxItem
    ? getDownloadMeta(activeLightboxItem.image_url)
    : { ext: "webp", label: "Download WebP" };

  return (
    <div className="w-full flex flex-col gap-8 animate-in fade-in duration-200">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-foreground">Asset Gallery</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Permanent visual assets generated during your active creative session.
          </p>
        </div>

        <Button variant="default" asChild className="shrink-0 min-h-[44px]">
          <Link to="/campaign">
            <Megaphone className="w-4 h-4 mr-2" aria-hidden="true" />
            Create Campaign
          </Link>
        </Button>
      </div>

      {/* Grid, Error, or Empty State */}
      {isLoading && generations.length === 0 ? (
        <div
          role="status"
          className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6"
          aria-busy="true"
          aria-label="Loading asset gallery"
        >
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="aspect-square rounded-card bg-surface-user border border-border/50 dark:bg-white/[0.04] animate-pulse"
            />
          ))}
        </div>
      ) : isError && generations.length === 0 ? (
        <div
          role="alert"
          aria-live="polite"
          className="p-10 rounded-card bg-surface border border-danger/25 text-center flex flex-col items-center justify-center gap-3 shadow-xs"
        >
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
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            className="gap-2 mt-1 min-h-[44px]"
          >
            <RotateCcw className="w-3.5 h-3.5" aria-hidden="true" />
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
          <Button variant="default" size="sm" asChild className="mt-2 min-h-[44px]">
            <Link to="/campaign">Go to Campaign Director</Link>
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {generations.map((gen, idx) => (
              <GalleryCard
                key={gen.id}
                gen={gen}
                idx={idx}
                onSelect={(item) => setActiveLightboxItem(item)}
              />
            ))}
          </div>

          {hasMore && (
            <div className="flex justify-center pt-2">
              <Button
                variant="outline"
                onClick={() => setOffset((prev) => prev + PAGE_SIZE)}
                disabled={isFetching}
                className="min-h-[44px] px-6"
              >
                {isFetching ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" aria-hidden="true" />
                    <span>Loading more...</span>
                  </>
                ) : (
                  <span>Load more assets</span>
                )}
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Accessible Native Lightbox Modal Dialog */}
      {activeLightboxItem && (
        <dialog
          ref={dialogRef}
          aria-labelledby="lightbox-title"
          {...({ closedby: "any" } as Record<string, string>)}
          className="p-0 rounded-2xl bg-surface/95 dark:bg-[#141418]/95 backdrop-blur-2xl text-foreground border border-border dark:border-white/15 shadow-2xl max-w-4xl w-[calc(100vw-2rem)] max-h-[90vh] mx-auto my-auto backdrop:bg-black/80 backdrop:backdrop-blur-sm overflow-hidden animate-in zoom-in-95 duration-200"
          onClick={(e) => {
            const dialog = dialogRef.current;
            if (!dialog || e.target !== dialog) return;
            if (!("closedBy" in HTMLDialogElement.prototype)) {
              const rect = dialog.getBoundingClientRect();
              const isInside =
                rect.top <= e.clientY &&
                e.clientY <= rect.top + rect.height &&
                rect.left <= e.clientX &&
                e.clientX <= rect.left + rect.width;
              if (!isInside) {
                setActiveLightboxItem(null);
              }
            }
          }}
        >
          <div className="flex flex-col md:flex-row h-full max-h-[90vh]">
            {/* Image container */}
            <div className="flex-1 bg-black flex items-center justify-center min-h-[300px] max-h-[60vh] md:max-h-full">
              <img
                src={activeLightboxItem.image_url}
                alt={activeLightboxItem.concept_title}
                width={lightboxDims.w}
                height={lightboxDims.h}
                className="w-full h-full object-contain"
                decoding="async"
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
                    className="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-surface-user transition-colors cursor-pointer"
                    aria-label="Close image lightbox"
                  >
                    <X className="w-5 h-5" aria-hidden="true" />
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
                <Button variant="default" className="w-full min-h-[44px]" asChild>
                  <a
                    href={activeLightboxItem.image_url}
                    download={`brandmuse-${activeLightboxItem.concept_title.toLowerCase().replace(/\s+/g, "-")}.${downloadMeta.ext}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <Download className="w-4 h-4 mr-2" aria-hidden="true" />
                    {downloadMeta.label}
                  </a>
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleCopyUrl(activeLightboxItem.image_url)}
                  className="w-full gap-2 text-xs min-h-[44px]"
                >
                  {copiedUrl ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-success-icon" aria-hidden="true" />
                      <span>URL Disalin!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" aria-hidden="true" />
                      <span>Salin URL Gambar</span>
                    </>
                  )}
                </Button>

                <a
                  href={activeLightboxItem.image_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-center text-xs text-foreground hover:underline flex items-center justify-center gap-1 py-2 min-h-[44px]"
                >
                  <span>Open raw image URL</span>
                  <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
                </a>
              </div>
            </div>
          </div>
        </dialog>
      )}
    </div>
  );
};

export default GalleryPage;
