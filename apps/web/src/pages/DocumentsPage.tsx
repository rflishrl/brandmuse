import React, { useState, useRef } from "react";
import { Link } from "react-router";
import {
  UploadCloud,
  FileText,
  CheckCircle,
  Bookmark,
  AlertCircle,
  Calendar,
  Layers,
  Check,
  ShieldCheck,
} from "lucide-react";
import { useBrand } from "@/context/BrandContext";
import { useUploadDocument } from "@/api/generated";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export const DocumentsPage: React.FC = () => {
  const {
    documents,
    selectedDocumentId,
    setSelectedDocumentId,
    loadSampleBrand,
    isLoadingSample,
    refetchDocuments,
  } = useBrand();

  const [dragActive, setDragActive] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const uploadMutation = useUploadDocument();

  const handleFileProcess = async (file: File) => {
    setErrorMessage(null);

    // Client-side validations
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setErrorMessage("Please upload a valid PDF document.");
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      setErrorMessage("File exceeds 10 MB limit. Please upload a smaller guideline PDF.");
      return;
    }

    try {
      setUploadStatus("Uploading PDF bytes...");
      const result = await uploadMutation.mutateAsync({
        data: { file: file as unknown as string },
      });

      setUploadStatus("Indexing pages and computing embeddings...");
      await refetchDocuments();
      if (result.document?.id) {
        setSelectedDocumentId(result.document.id);
      }
      setUploadStatus(null);
    } catch (err: unknown) {
      setUploadStatus(null);
      const msg = (err as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message;
      setErrorMessage(msg || "Failed to process and index PDF. Please verify it is a valid PDF under 40 pages.");
    }
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

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileProcess(e.dataTransfer.files[0]);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileProcess(e.target.files[0]);
    }
  };

  return (
    <div className="w-full flex flex-col gap-8 animate-in fade-in duration-200">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-foreground">
            Brand Guidelines
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Upload custom PDFs or load the verified sample guideline for Instant RAG Q&A.
          </p>
        </div>

        <Button
          variant="outline"
          onClick={() => loadSampleBrand()}
          disabled={isLoadingSample}
          className="shrink-0"
        >
          <Bookmark className="w-4 h-4 mr-2 text-foreground" />
          {isLoadingSample ? "Loading sample..." : "Use sample brand"}
        </Button>
      </div>

      {/* Upload Drop Zone Card */}
      <div
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        className={`
          relative border-2 border-dashed rounded-card p-8 flex flex-col items-center justify-center text-center transition-all duration-200 bg-surface/90 dark:bg-[#141418]/80 backdrop-blur-xl shadow-xs
          ${dragActive ? "border-white/40 bg-white/5" : "border-border hover:border-white/20"}
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
          <div className="mt-4 flex items-center gap-2 text-xs text-foreground font-medium animate-pulse">
            <Layers className="w-4 h-4 animate-spin" />
            <span>{uploadStatus}</span>
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
          <div role="alert" className="mt-4 p-3 rounded-md bg-danger/10 border border-danger/20 flex items-center gap-2 text-xs text-danger">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}
      </div>

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
                    p-5 rounded-card bg-surface/90 dark:bg-[#141418]/80 backdrop-blur-xl border transition-all duration-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-xs
                    ${isActive ? "border-white/30 ring-1 ring-white/20 bg-surface/90" : "border-border hover:border-border/80"}
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
                            <ShieldCheck className="w-3.5 h-3.5 text-foreground" aria-hidden="true" />
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
