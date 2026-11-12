import {
  AlertCircle,
  Bookmark,
  Calendar,
  Check,
  CheckCircle,
  FileText,
  Layers,
  ShieldCheck,
  UploadCloud,
} from "lucide-react";
import type React from "react";
import { useRef, useState } from "react";
import { Link } from "react-router";
import { useUploadDocument } from "@/api/generated";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/sonner";
import { inspectPdfPreflight, type PdfPreflightResult } from "@/lib/pdfPreflight";
import { useBrandStore } from "@/store/useBrandStore";

export const DocumentsPage: React.FC = () => {
  const documents = useBrandStore((s) => s.documents);
  const selectedDocumentId = useBrandStore((s) => s.selectedDocumentId);
  const setSelectedDocumentId = useBrandStore((s) => s.setSelectedDocumentId);
  const loadSampleBrand = useBrandStore((s) => s.loadSampleBrand);
  const isLoadingSample = useBrandStore((s) => s.isLoadingSample);
  const refetchDocuments = useBrandStore((s) => s.refetchDocuments);

  const [dragActive, setDragActive] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [preflightInfo, setPreflightInfo] = useState<PdfPreflightResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const uploadMutation = useUploadDocument();

  const handleFileProcess = async (file: File) => {
    setErrorMessage(null);
    setPreflightInfo(null);

    // Initial filename check
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      const msg = "Please upload a valid PDF document.";
      setErrorMessage(msg);
      toast.error(msg);
      return;
    }

    try {
      // 1. Client-Side Binary Pre-Flight Inspection (< 15ms)
      setUploadStatus("Running client-side pre-flight check...");
      const preflight = await inspectPdfPreflight(file);

      if (!preflight.isValid) {
        setUploadStatus(null);
        const err = preflight.errorReason || "Document failed pre-flight inspection.";
        setErrorMessage(err);
        toast.error(err);
        return;
      }

      setPreflightInfo(preflight);
      setUploadStatus(
        `Pre-flight verified (v${preflight.version}, ${preflight.pageCount} pages, ~${preflight.estimatedTokens.toLocaleString()} tokens). Uploading...`
      );

      // 2. Dispatch upload to backend
      const result = await uploadMutation.mutateAsync({
        data: { file: file as unknown as string },
      });

      setUploadStatus("Indexing pages and computing embeddings...");
      await refetchDocuments();
      if (result.document?.id) {
        setSelectedDocumentId(result.document.id);
      }
      setUploadStatus(null);
      toast.success(`Dokumen "${file.name}" berhasil diunggah dan diekstrak!`);
    } catch (err: unknown) {
      setUploadStatus(null);
      const msg =
        err instanceof Error
          ? err.message
          : "Failed to process and index PDF. Please verify it is a valid PDF under 40 pages.";
      setErrorMessage(msg);
      toast.error(msg);
    }
  };

  const handleLoadSample = async () => {
    toast.promise(loadSampleBrand(), {
      loading: "Memuat sample brand...",
      success: "Sample brand berhasil dimuat!",
      error: "Gagal memuat sample brand",
    });
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files?.[0]) {
      handleFileProcess(e.dataTransfer.files[0]);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      handleFileProcess(e.target.files[0]);
    }
  };

  return (
    <div className="w-full flex flex-col gap-8 animate-in fade-in duration-200">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-foreground">Brand Guidelines</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Upload custom PDFs or load the verified sample guideline for Instant RAG Q&A.
          </p>
        </div>

        <Button
          variant="outline"
          onClick={handleLoadSample}
          disabled={isLoadingSample}
          className="shrink-0"
        >
          <Bookmark className="w-4 h-4 mr-2 text-foreground" />
          {isLoadingSample ? "Loading sample..." : "Use sample brand"}
        </Button>
      </div>

      {/* Upload Drop Zone Card */}
      <section
        aria-label="PDF guideline dropzone"
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        className={`
          relative border-2 border-dashed rounded-card p-8 flex flex-col items-center justify-center text-center transition-all duration-200 bg-surface shadow-xs
          ${dragActive ? "border-foreground/40 bg-foreground/5" : "border-border hover:border-foreground/20"}
        `}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,application/pdf"
          className="hidden"
          onChange={handleFileInputChange}
          aria-label="Upload PDF guideline"
        />

        <div className="w-12 h-12 rounded-full bg-surface-user flex items-center justify-center mb-4 text-foreground">
          <UploadCloud className="w-6 h-6" aria-hidden="true" />
        </div>

        <h3 className="font-semibold text-base text-foreground">
          {uploadStatus ? "Processing PDF..." : "Drag and drop your brand guideline PDF"}
        </h3>
        <p className="text-xs text-muted-foreground mt-1 max-w-sm">
          Strict limit: 10 MB and up to 40 pages. Text is parsed securely with zero OCR overhead.
        </p>

        {uploadStatus ? (
          <div className="mt-4 flex flex-col items-center gap-2">
            <div className="flex items-center gap-2 text-xs text-foreground font-medium animate-pulse">
              <Layers className="w-4 h-4 animate-spin" />
              <span>{uploadStatus}</span>
            </div>
            {preflightInfo && (
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-xs mt-1">
                <CheckCircle className="w-3.5 h-3.5 shrink-0" />
                <span>
                  Pre-flight: PDF {preflightInfo.version} • {preflightInfo.pageCount} pages • ~
                  {preflightInfo.estimatedTokens.toLocaleString()} tokens
                </span>
              </div>
            )}
          </div>
        ) : (
          <Button
            variant="default"
            size="sm"
            onClick={() => fileInputRef.current?.click()}
            className="mt-5"
            disabled={uploadMutation.isPending}
          >
            Browse files
          </Button>
        )}

        {errorMessage && (
          <div
            role="alert"
            aria-live="assertive"
            className="mt-4 p-3.5 rounded-xl bg-danger/10 border border-danger/30 flex items-start gap-3 text-xs text-danger max-w-md text-left"
          >
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
            <div className="flex-1 flex flex-col gap-0.5">
              <span className="font-semibold text-danger">Upload Failed</span>
              <span className="text-danger/90 leading-relaxed">{errorMessage}</span>
            </div>
            <button
              type="button"
              onClick={() => setErrorMessage(null)}
              className="p-1 rounded-md text-danger/70 hover:text-danger hover:bg-danger/10 transition-colors"
              aria-label="Dismiss error notice"
            >
              ✕
            </button>
          </div>
        )}
      </section>

      {/* Document Library List */}
      <div className="flex flex-col gap-4">
        <h3 className="font-semibold text-base text-foreground">Guideline Library</h3>

        {documents.length === 0 ? (
          <div className="p-8 rounded-card bg-surface border border-border text-center text-muted-foreground text-sm">
            No brand guidelines uploaded yet. Click "Use sample brand" or upload a PDF above.
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3">
            {documents.map((doc) => {
              const isActive = doc.id === selectedDocumentId;
              const formattedDate = new Date(doc.created_at).toLocaleDateString(undefined, {
                year: "numeric",
                month: "short",
                day: "numeric",
              });

              return (
                <div
                  key={doc.id}
                  className={`
                    p-5 rounded-card bg-surface border transition-all duration-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-xs
                    ${isActive ? "border-foreground/30 ring-1 ring-foreground/20" : "border-border hover:border-foreground/20"}
                  `}
                >
                  <div className="flex items-start sm:items-center gap-3">
                    <div className="p-2.5 rounded-lg bg-surface-user text-foreground shrink-0">
                      <FileText className="w-5 h-5" aria-hidden="true" />
                    </div>

                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="font-medium text-sm text-foreground">{doc.filename}</h4>
                        {doc.is_sample && (
                          <Badge variant="quote" className="text-[10px]">
                            Sample
                          </Badge>
                        )}
                        {isActive && (
                          <Badge variant="success" className="text-[10px] gap-1">
                            <Check className="w-3 h-3" />
                            Active
                          </Badge>
                        )}
                      </div>

                      <div className="flex items-center gap-4 text-xs text-muted-foreground mt-1.5">
                        <span className="flex items-center gap-1">
                          <Layers className="w-3.5 h-3.5" aria-hidden="true" />
                          {doc.page_count} {doc.page_count === 1 ? "page" : "pages"}
                        </span>
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3.5 h-3.5" aria-hidden="true" />
                          {formattedDate}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 self-end sm:self-center">
                    {isActive ? (
                      <div className="flex items-center gap-2">
                        <Link to="/rules">
                          <Button variant="outline" size="sm" className="gap-1.5 text-xs">
                            <ShieldCheck
                              className="w-3.5 h-3.5 text-foreground"
                              aria-hidden="true"
                            />
                            Brand Rules
                          </Button>
                        </Link>
                        <span className="text-xs font-medium text-success-text flex items-center gap-1 px-3 py-1.5">
                          <CheckCircle className="w-4 h-4 text-success-icon" />
                          Selected
                        </span>
                      </div>
                    ) : (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setSelectedDocumentId(doc.id)}
                      >
                        Select brand
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default DocumentsPage;
