import React, { useState, useRef, useEffect } from "react";
import { Link } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import {
  ShieldCheck,
  ShieldAlert,
  Sparkles,
  Palette,
  Type,
  ListChecks,
  CheckCircle2,
  XCircle,
  Info,
  Copy,
  Check,
  RefreshCw,
  Bookmark,
  FileText,
  Radio,
  AlertCircle,
  X,
} from "lucide-react";
import { useBrand } from "@/context/BrandContext";
import {
  useGetOntologyApiDocumentsDocumentIdOntologyGet,
  useExtractOntologyApiDocumentsDocumentIdOntologyExtractPost,
  useCertifyOntologyApiDocumentsDocumentIdOntologyCertifyPost,
  getGetOntologyApiDocumentsDocumentIdOntologyGetQueryKey,
} from "@/api/generated";
import { ColorToken } from "@/api/model/colorToken";
import { TypographyToken } from "@/api/model/typographyToken";
import { BrandRuleItem } from "@/api/model/brandRuleItem";
import { ChannelRule } from "@/api/model/channelRule";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

type ActiveTab = "overview" | "colors" | "typography" | "rules" | "channels";
type RuleTypeFilter = "all" | "do" | "dont" | "guideline";
type RuleCategoryFilter =
  | "all"
  | "logo"
  | "color"
  | "typography"
  | "imagery"
  | "tone_of_voice"
  | "channel_restriction";

export const OntologyPage: React.FC = () => {
  const {
    selectedDocumentId,
    selectedDocument,
    documents,
    setSelectedDocumentId,
    loadSampleBrand,
    isLoadingSample,
  } = useBrand();

  const queryClient = useQueryClient();
  const dialogRef = useRef<HTMLDialogElement>(null);

  const [activeTab, setActiveTab] = useState<ActiveTab>("overview");
  const [ruleTypeFilter, setRuleTypeFilter] = useState<RuleTypeFilter>("all");
  const [ruleCategoryFilter, setRuleCategoryFilter] = useState<RuleCategoryFilter>("all");
  const [copiedHex, setCopiedHex] = useState<string | null>(null);
  const [certifierName, setCertifierName] = useState("Brand Director");
  const [certifyAcknowledged, setCertifyAcknowledged] = useState(true);
  const [statusNotification, setStatusNotification] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  // Fetch ontology for selected document
  const {
    data: ontologyResponse,
    isLoading: isLoadingOntology,
    isError: isOntologyError,
  } = useGetOntologyApiDocumentsDocumentIdOntologyGet(selectedDocumentId || "", {
    query: {
      enabled: Boolean(selectedDocumentId),
      retry: false,
    },
  });

  const extractMutation = useExtractOntologyApiDocumentsDocumentIdOntologyExtractPost();
  const certifyMutation = useCertifyOntologyApiDocumentsDocumentIdOntologyCertifyPost();

  const ontologyData = ontologyResponse?.ontology;
  const isCertified = Boolean(ontologyResponse?.is_certified);

  // Clear copied hex after 2 seconds
  useEffect(() => {
    if (!copiedHex) return;
    const timer = setTimeout(() => setCopiedHex(null), 2000);
    return () => clearTimeout(timer);
  }, [copiedHex]);

  // Copy to clipboard helper
  const handleCopyHex = async (hex: string) => {
    try {
      await navigator.clipboard.writeText(hex);
      setCopiedHex(hex);
    } catch {
      // Fallback
      setCopiedHex(hex);
    }
  };

  // Trigger AI Ontology Extraction
  const handleExtract = async () => {
    if (!selectedDocumentId) return;
    setStatusNotification(null);
    try {
      await extractMutation.mutateAsync({ documentId: selectedDocumentId });
      await queryClient.invalidateQueries({
        queryKey: getGetOntologyApiDocumentsDocumentIdOntologyGetQueryKey(selectedDocumentId),
      });
      setStatusNotification({
        type: "success",
        message: "Brand ontology extracted successfully from guideline document!",
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to extract ontology.";
      setStatusNotification({
        type: "error",
        message: msg,
      });
    }
  };

  // Open Certification Dialog
  const openCertifyModal = () => {
    if (dialogRef.current) {
      dialogRef.current.showModal();
    }
  };

  // Close Certification Dialog
  const closeCertifyModal = () => {
    if (dialogRef.current) {
      dialogRef.current.close();
    }
  };

  // Submit Certification
  const handleCertifySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDocumentId) return;
    try {
      await certifyMutation.mutateAsync({
        documentId: selectedDocumentId,
        data: {
          certified_by: certifierName.trim() || "Brand Director",
        },
      });
      await queryClient.invalidateQueries({
        queryKey: getGetOntologyApiDocumentsDocumentIdOntologyGetQueryKey(selectedDocumentId),
      });
      closeCertifyModal();
      setStatusNotification({
        type: "success",
        message:
          "Brand rules certified successfully! Rules are now strictly enforced in Ask & Campaign generation.",
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to certify ontology.";
      setStatusNotification({
        type: "error",
        message: msg,
      });
    }
  };

  // Filter DOs & DONTs
  const rawRules: BrandRuleItem[] = ontologyData?.rules || [];
  const filteredRules = rawRules.filter((r) => {
    const matchesType = ruleTypeFilter === "all" || r.type === ruleTypeFilter;
    const matchesCategory = ruleCategoryFilter === "all" || r.category === ruleCategoryFilter;
    return matchesType && matchesCategory;
  });

  const colors: ColorToken[] = ontologyData?.colors || [];
  const typography: TypographyToken[] = ontologyData?.typography || [];
  const channelRules: ChannelRule[] = ontologyData?.channel_rules || [];
  const identity = ontologyData?.identity;

  // Counts
  const doCount = rawRules.filter((r) => r.type === "do").length;
  const dontCount = rawRules.filter((r) => r.type === "dont").length;
  const guidelineCount = rawRules.filter((r) => r.type === "guideline").length;

  // Format date helper
  const formattedCertifiedDate = ontologyResponse?.certified_at
    ? new Date(ontologyResponse.certified_at).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : null;

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 flex flex-col gap-8">
      {/* Hidden Live Region for Screen Readers */}
      <div role="status" aria-live="polite" className="sr-only">
        {copiedHex ? `Hex code ${copiedHex} copied to clipboard` : ""}
        {statusNotification ? statusNotification.message : ""}
      </div>

      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="p-1.5 rounded-lg bg-white/10 text-foreground shrink-0">
              <ShieldCheck className="w-5 h-5" aria-hidden="true" />
            </span>
            <span className="text-xs font-semibold uppercase tracking-wider text-foreground">
              Deterministic Brand Intelligence
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground">
            Brand Rules &amp; Design Ontology
          </h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
            Authoritative brand identity tokens, color palettes, typography specifications, and
            atomic DOs/DONTs extracted from your brand guidelines.
          </p>
        </div>

        {/* Brand Document Switcher Pill */}
        <div className="flex items-center gap-2 self-start md:self-auto bg-surface border border-border rounded-lg p-1.5 shadow-xs">
          <FileText className="w-4 h-4 text-muted-foreground ml-1" aria-hidden="true" />
          <select
            value={selectedDocumentId || ""}
            onChange={(e) => setSelectedDocumentId(e.target.value || null)}
            className="bg-transparent text-xs font-medium text-foreground pr-2 focus:outline-none focus:ring-1 focus:ring-ring rounded cursor-pointer"
            aria-label="Select active brand document"
          >
            {documents.length === 0 && <option value="">No brand documents</option>}
            {documents.map((doc) => (
              <option key={doc.id} value={doc.id}>
                {doc.filename} {doc.is_sample ? "(Sample)" : ""}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Global Status Notification Banner */}
      {statusNotification && (
        <div
          role="status"
          aria-atomic="true"
          className={`p-4 rounded-xl border flex items-start justify-between gap-3 animate-in fade-in duration-150 ${
            statusNotification.type === "success"
              ? "bg-emerald-50 border-emerald-200 text-emerald-900 dark:bg-emerald-950/40 dark:border-emerald-800 dark:text-emerald-200"
              : "bg-rose-50 border-rose-200 text-rose-900 dark:bg-rose-950/40 dark:border-rose-800 dark:text-rose-200"
          }`}
        >
          <div className="flex items-center gap-2.5">
            {statusNotification.type === "success" ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400 shrink-0" />
            ) : (
              <AlertCircle className="w-5 h-5 text-rose-600 dark:text-rose-400 shrink-0" />
            )}
            <p className="text-xs sm:text-sm font-medium">{statusNotification.message}</p>
          </div>
          <button
            type="button"
            onClick={() => setStatusNotification(null)}
            className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-black/5 dark:hover:bg-white/10"
            aria-label="Dismiss notification"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Case 1: No Document Selected */}
      {!selectedDocumentId && (
        <div className="p-10 rounded-card bg-surface border border-border text-center flex flex-col items-center justify-center gap-4 shadow-card">
          <div className="p-3 rounded-full bg-surface-user text-muted-foreground">
            <ShieldAlert className="w-8 h-8" aria-hidden="true" />
          </div>
          <div className="max-w-md">
            <h2 className="text-lg font-semibold text-foreground">No Brand Guideline Selected</h2>
            <p className="text-xs text-muted-foreground mt-1">
              Select an uploaded brand guideline document or explore the interactive demo with our
              free sample brand.
            </p>
          </div>
          <div className="flex items-center gap-3 mt-2">
            <Button
              variant="default"
              size="sm"
              onClick={() => loadSampleBrand()}
              disabled={isLoadingSample}
              className="gap-2"
            >
              <Bookmark className="w-4 h-4" aria-hidden="true" />
              {isLoadingSample ? "Loading demo..." : "Load Sample Brand"}
            </Button>
            <Link to="/documents">
              <Button variant="outline" size="sm">
                Upload New PDF
              </Button>
            </Link>
          </div>
        </div>
      )}

      {/* Case 2: Loading State */}
      {selectedDocumentId && isLoadingOntology && (
        <div className="flex flex-col gap-6">
          <div className="p-6 rounded-card bg-surface border border-border flex flex-col gap-4">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Skeleton className="h-28 rounded-xl" />
            <Skeleton className="h-28 rounded-xl" />
            <Skeleton className="h-28 rounded-xl" />
            <Skeleton className="h-28 rounded-xl" />
          </div>
        </div>
      )}

      {/* Case 3: Document Selected, but Ontology Not Extracted Yet (404 / Empty) */}
      {selectedDocumentId && !isLoadingOntology && (!ontologyData || isOntologyError) && (
        <div className="p-8 sm:p-12 rounded-card bg-surface border border-dashed border-border text-center flex flex-col items-center justify-center gap-5 shadow-sm">
          <div className="p-4 rounded-2xl bg-white/10 text-foreground">
            <Sparkles className="w-8 h-8" aria-hidden="true" />
          </div>
          <div className="max-w-lg">
            <h2 className="text-lg sm:text-xl font-semibold text-foreground">
              Extract Brand Rules from &ldquo;{selectedDocument?.filename}&rdquo;
            </h2>
            <p className="text-xs sm:text-sm text-muted-foreground mt-1.5 leading-relaxed">
              BrandMuse can parse the indexed PDF pages to automatically extract design tokens,
              exact hex color codes, typography hierarchy, channel constraints, and authoritative
              DOs &amp; DONTs.
            </p>
          </div>
          <Button
            variant="default"
            size="lg"
            onClick={handleExtract}
            disabled={extractMutation.isPending}
            className="gap-2.5 mt-2"
          >
            <Sparkles className="w-4 h-4" aria-hidden="true" />
            {extractMutation.isPending
              ? "Extracting Brand Ontology with AI..."
              : "Extract Brand Rules Now"}
          </Button>
        </div>
      )}

      {/* Case 4: Extracted Ontology Loaded */}
      {selectedDocumentId && !isLoadingOntology && ontologyData && (
        <div className="flex flex-col gap-8">
          {/* Certification Status Banner */}
          <div
            className={`p-5 sm:p-6 rounded-card border shadow-xs transition-colors flex flex-col md:flex-row items-start md:items-center justify-between gap-5 ${
              isCertified
                ? "bg-emerald-500/5 border-emerald-500/20 text-emerald-950 dark:text-emerald-100"
                : "bg-amber-500/5 border-amber-500/20 text-amber-950 dark:text-amber-100"
            }`}
          >
            <div className="flex items-start gap-3.5">
              <div
                className={`p-2.5 rounded-xl shrink-0 ${
                  isCertified
                    ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                    : "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300"
                }`}
              >
                {isCertified ? (
                  <ShieldCheck className="w-6 h-6" aria-hidden="true" />
                ) : (
                  <ShieldAlert className="w-6 h-6" aria-hidden="true" />
                )}
              </div>

              <div>
                <div className="flex items-center gap-2">
                  <span
                    role="status"
                    aria-atomic="true"
                    className="inline-flex items-center gap-1.5 text-xs font-semibold"
                  >
                    <Badge variant={isCertified ? "success" : "warning"}>
                      {isCertified ? "Certified Guidelines" : "Draft Guidelines (Uncertified)"}
                    </Badge>
                  </span>
                  {isCertified && formattedCertifiedDate && (
                    <span className="text-xs text-muted-foreground hidden sm:inline">
                      Certified on {formattedCertifiedDate}
                    </span>
                  )}
                </div>

                <p className="text-xs sm:text-sm text-muted-foreground mt-1 max-w-2xl leading-normal">
                  {isCertified
                    ? `Certified by ${
                        ontologyResponse.certified_by || "Brand Director"
                      }. These rules are actively injected into the grounding prompt for Ask and Campaign generation.`
                    : "These rules were extracted automatically by AI and are currently in Draft status. Complete Human-in-the-Loop review and certify them to make them authoritative."}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2.5 self-end md:self-center shrink-0">
              <Button
                variant="outline"
                size="sm"
                onClick={handleExtract}
                disabled={extractMutation.isPending}
                className="gap-1.5 text-xs"
                title="Re-run LLM extraction across guideline pages"
              >
                <RefreshCw
                  className={`w-3.5 h-3.5 ${extractMutation.isPending ? "animate-spin" : ""}`}
                  aria-hidden="true"
                />
                Re-extract
              </Button>

              <Button
                variant={isCertified ? "secondary" : "success"}
                size="sm"
                onClick={openCertifyModal}
                className="gap-2 text-xs font-medium"
              >
                <ShieldCheck className="w-4 h-4" aria-hidden="true" />
                {isCertified ? "Re-certify" : "Certify Guidelines"}
              </Button>
            </div>
          </div>

          {/* Brand Identity Showcase Card */}
          {identity && (
            <div className="p-6 sm:p-7 rounded-card bg-surface/90 dark:bg-[#141418]/80 backdrop-blur-xl border border-border dark:border-white/10 shadow-card flex flex-col gap-5">
              <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2 border-b border-border pb-4">
                <div>
                  <span className="text-[11px] font-bold text-foreground/80 tracking-wider uppercase">
                    Brand Core
                  </span>
                  <h2 className="text-xl sm:text-2xl font-bold text-foreground mt-0.5">
                    {identity.brand_name}
                  </h2>
                </div>
                {identity.tagline && (
                  <p className="text-sm italic text-muted-foreground max-w-md sm:text-right">
                    &ldquo;{identity.tagline}&rdquo;
                  </p>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {identity.mission_or_purpose && (
                  <div className="flex flex-col gap-1.5">
                    <span className="text-xs font-semibold text-foreground uppercase tracking-wide">
                      Mission &amp; Purpose
                    </span>
                    <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
                      {identity.mission_or_purpose}
                    </p>
                  </div>
                )}

                {identity.target_audience && (
                  <div className="flex flex-col gap-1.5">
                    <span className="text-xs font-semibold text-foreground uppercase tracking-wide">
                      Target Audience
                    </span>
                    <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
                      {identity.target_audience}
                    </p>
                  </div>
                )}
              </div>

              {identity.tone_attributes && identity.tone_attributes.length > 0 && (
                <div className="pt-3 border-t border-border flex flex-wrap items-center gap-2">
                  <span className="text-xs font-semibold text-foreground mr-1">
                    Tone of Voice:
                  </span>
                  {identity.tone_attributes.map((tone) => (
                    <Badge key={tone} variant="quote" className="text-xs py-0.5 px-3">
                      {tone}
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Navigation Tabs Bar */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 border-b border-border pb-3">
            <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-1">
              <button
                type="button"
                onClick={() => setActiveTab("overview")}
                aria-pressed={activeTab === "overview"}
                className={`px-3.5 py-1.5 rounded-full text-xs font-medium transition-all ${
                  activeTab === "overview"
                    ? "bg-foreground text-background shadow-xs"
                    : "text-muted-foreground hover:text-foreground hover:bg-surface-user"
                }`}
              >
                All Sections
              </button>

              <button
                type="button"
                onClick={() => setActiveTab("colors")}
                aria-pressed={activeTab === "colors"}
                className={`px-3.5 py-1.5 rounded-full text-xs font-medium flex items-center gap-1.5 transition-all ${
                  activeTab === "colors"
                    ? "bg-foreground text-background shadow-xs"
                    : "text-muted-foreground hover:text-foreground hover:bg-surface-user"
                }`}
              >
                <Palette className="w-3.5 h-3.5" aria-hidden="true" />
                Colors ({colors.length})
              </button>

              <button
                type="button"
                onClick={() => setActiveTab("typography")}
                aria-pressed={activeTab === "typography"}
                className={`px-3.5 py-1.5 rounded-full text-xs font-medium flex items-center gap-1.5 transition-all ${
                  activeTab === "typography"
                    ? "bg-foreground text-background shadow-xs"
                    : "text-muted-foreground hover:text-foreground hover:bg-surface-user"
                }`}
              >
                <Type className="w-3.5 h-3.5" aria-hidden="true" />
                Typography ({typography.length})
              </button>

              <button
                type="button"
                onClick={() => setActiveTab("rules")}
                aria-pressed={activeTab === "rules"}
                className={`px-3.5 py-1.5 rounded-full text-xs font-medium flex items-center gap-1.5 transition-all ${
                  activeTab === "rules"
                    ? "bg-foreground text-background shadow-xs"
                    : "text-muted-foreground hover:text-foreground hover:bg-surface-user"
                }`}
              >
                <ListChecks className="w-3.5 h-3.5" aria-hidden="true" />
                DOs &amp; DONTs ({rawRules.length})
              </button>

              <button
                type="button"
                onClick={() => setActiveTab("channels")}
                aria-pressed={activeTab === "channels"}
                className={`px-3.5 py-1.5 rounded-full text-xs font-medium flex items-center gap-1.5 transition-all ${
                  activeTab === "channels"
                    ? "bg-foreground text-background shadow-xs"
                    : "text-muted-foreground hover:text-foreground hover:bg-surface-user"
                }`}
              >
                <Radio className="w-3.5 h-3.5" aria-hidden="true" />
                Channels ({channelRules.length})
              </button>
            </div>
          </div>

          {/* Section 1: Colors & Palettes */}
          {(activeTab === "overview" || activeTab === "colors") && (
            <section aria-labelledby="colors-heading" className="flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 id="colors-heading" className="font-semibold text-lg text-foreground flex items-center gap-2">
                    <Palette className="w-5 h-5 text-foreground" aria-hidden="true" />
                    Color Palette &amp; Tokens
                  </h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Official color tokens extracted with hex codes and usage restrictions.
                  </p>
                </div>
                <Badge variant="outline" className="text-xs">
                  {colors.length} {colors.length === 1 ? "color" : "colors"}
                </Badge>
              </div>

              {colors.length === 0 ? (
                <div className="p-6 rounded-card bg-surface border border-border text-center text-xs text-muted-foreground">
                  No color definitions extracted.
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                  {colors.map((color, index) => {
                    const isCopied = copiedHex === color.hex;
                    return (
                      <div
                        key={`${color.name}-${index}`}
                        className="rounded-xl bg-surface border border-border shadow-xs overflow-hidden flex flex-col justify-between hover:border-border/80 transition-all group"
                      >
                        {/* Visual Swatch */}
                        <div
                          className="h-24 w-full relative transition-transform duration-200 group-hover:scale-[1.02]"
                          style={{ backgroundColor: color.hex }}
                          title={`Color swatch: ${color.name} (${color.hex})`}
                        >
                          {color.page && (
                            <span className="absolute top-2 right-2 text-[10px] font-mono px-1.5 py-0.5 rounded bg-black/40 text-white backdrop-blur-xs">
                              p. {color.page}
                            </span>
                          )}
                        </div>

                        {/* Content */}
                        <div className="p-4 flex flex-col gap-2.5">
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <h4 className="font-semibold text-sm text-foreground leading-tight">
                                {color.name}
                              </h4>
                              {color.role && (
                                <span className="inline-block text-[11px] font-medium text-muted-foreground mt-0.5 capitalize">
                                  {color.role}
                                </span>
                              )}
                            </div>

                            <button
                              type="button"
                              onClick={() => handleCopyHex(color.hex)}
                              className="px-2 py-1 rounded bg-surface-user hover:bg-quote text-[11px] font-mono text-foreground flex items-center gap-1 transition-colors border border-border/60"
                              title="Click to copy Hex code"
                              aria-label={`Copy hex code ${color.hex}`}
                            >
                              {isCopied ? (
                                <>
                                  <Check className="w-3 h-3 text-success-text" />
                                  <span className="text-success-text font-sans">Copied!</span>
                                </>
                              ) : (
                                <>
                                  <Copy className="w-3 h-3 text-muted-foreground" />
                                  <span>{color.hex}</span>
                                </>
                              )}
                            </button>
                          </div>

                          {color.usage_notes && (
                            <p className="text-xs text-muted-foreground border-t border-border pt-2 leading-relaxed">
                              {color.usage_notes}
                            </p>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          )}

          {/* Section 2: Typography Standards */}
          {(activeTab === "overview" || activeTab === "typography") && (
            <section aria-labelledby="typography-heading" className="flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 id="typography-heading" className="font-semibold text-lg text-foreground flex items-center gap-2">
                    <Type className="w-5 h-5 text-foreground" aria-hidden="true" />
                    Typography System
                  </h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Font families, permitted hierarchy roles, and formatting rules.
                  </p>
                </div>
                <Badge variant="outline" className="text-xs">
                  {typography.length} {typography.length === 1 ? "family" : "families"}
                </Badge>
              </div>

              {typography.length === 0 ? (
                <div className="p-6 rounded-card bg-surface border border-border text-center text-xs text-muted-foreground">
                  No typography rules extracted.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {typography.map((font, index) => (
                    <div
                      key={`${font.font_family}-${index}`}
                      className="p-5 rounded-xl bg-surface border border-border shadow-xs flex flex-col justify-between gap-4"
                    >
                      <div className="flex flex-col gap-2">
                        <div className="flex items-center justify-between gap-2">
                          <Badge variant="quote" className="capitalize text-[11px]">
                            {font.role?.replace("_", " ") || "Primary"}
                          </Badge>
                          {font.page && (
                            <span className="text-[11px] font-mono text-muted-foreground">
                              p. {font.page}
                            </span>
                          )}
                        </div>

                        <div>
                          <h4 className="font-bold text-lg text-foreground tracking-tight">
                            {font.font_family}
                          </h4>
                          <p className="text-sm text-muted-foreground font-serif italic mt-0.5">
                            The quick brown fox jumps over the lazy dog.
                          </p>
                        </div>
                      </div>

                      <div className="flex flex-col gap-2 border-t border-border pt-3">
                        {font.weights && font.weights.length > 0 && (
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="text-[11px] font-medium text-muted-foreground">
                              Weights:
                            </span>
                            {font.weights.map((w) => (
                              <span
                                key={w}
                                className="text-[10px] px-2 py-0.5 rounded bg-surface-user text-foreground border border-border"
                              >
                                {w}
                              </span>
                            ))}
                          </div>
                        )}

                        {font.usage_notes && (
                          <p className="text-xs text-muted-foreground leading-relaxed">
                            {font.usage_notes}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}

          {/* Section 3: DOs & DONTs Catalog */}
          {(activeTab === "overview" || activeTab === "rules") && (
            <section aria-labelledby="rules-heading" className="flex flex-col gap-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <h3 id="rules-heading" className="font-semibold text-lg text-foreground flex items-center gap-2">
                    <ListChecks className="w-5 h-5 text-foreground" aria-hidden="true" />
                    Brand DOs &amp; DONTs
                  </h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Atomic constraints and prohibitions for logos, colors, imagery, and copywriting.
                  </p>
                </div>

                {/* Counters summary */}
                <div className="flex items-center gap-2 text-xs">
                  <Badge variant="success" className="gap-1">
                    <CheckCircle2 className="w-3 h-3" />
                    {doCount} DOs
                  </Badge>
                  <Badge variant="destructive" className="gap-1">
                    <XCircle className="w-3 h-3" />
                    {dontCount} DONTs
                  </Badge>
                  {guidelineCount > 0 && (
                    <Badge variant="quote" className="gap-1">
                      <Info className="w-3 h-3" />
                      {guidelineCount} Guidelines
                    </Badge>
                  )}
                </div>
              </div>

              {/* Filters Toolbar */}
              <div className="p-3 rounded-xl bg-surface border border-border flex flex-col md:flex-row items-start md:items-center justify-between gap-3 shadow-2xs">
                {/* Type Filter */}
                <div className="flex items-center gap-1">
                  <span className="text-xs font-semibold text-muted-foreground mr-1.5">Type:</span>
                  {(["all", "do", "dont", "guideline"] as RuleTypeFilter[]).map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setRuleTypeFilter(t)}
                      aria-pressed={ruleTypeFilter === t}
                      className={`px-2.5 py-1 rounded-md text-xs font-medium capitalize transition-colors ${
                        ruleTypeFilter === t
                          ? "bg-foreground text-background"
                          : "text-muted-foreground hover:text-foreground hover:bg-surface-user"
                      }`}
                    >
                      {t}
                    </button>
                  ))}
                </div>

                {/* Category Filter */}
                <div className="flex items-center gap-1 overflow-x-auto no-scrollbar w-full md:w-auto">
                  <span className="text-xs font-semibold text-muted-foreground mr-1.5 shrink-0">
                    Category:
                  </span>
                  {(
                    [
                      "all",
                      "logo",
                      "color",
                      "typography",
                      "imagery",
                      "tone_of_voice",
                      "channel_restriction",
                    ] as RuleCategoryFilter[]
                  ).map((cat) => (
                    <button
                      key={cat}
                      type="button"
                      onClick={() => setRuleCategoryFilter(cat)}
                      aria-pressed={ruleCategoryFilter === cat}
                      className={`px-2.5 py-1 rounded-md text-xs font-medium capitalize shrink-0 transition-colors ${
                        ruleCategoryFilter === cat
                          ? "bg-foreground text-background"
                          : "text-muted-foreground hover:text-foreground hover:bg-surface-user"
                      }`}
                    >
                      {cat.replace("_", " ")}
                    </button>
                  ))}
                </div>
              </div>

              {/* Rules List */}
              {filteredRules.length === 0 ? (
                <div className="p-8 rounded-card bg-surface border border-border text-center text-xs text-muted-foreground">
                  No rules match the selected filters.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                  {filteredRules.map((item, index) => {
                    const isDo = item.type === "do";
                    const isDont = item.type === "dont";

                    return (
                      <div
                        key={`${item.rule}-${index}`}
                        className={`p-4 rounded-xl border flex flex-col justify-between gap-3 shadow-2xs transition-all ${
                          isDo
                            ? "bg-emerald-500/[0.03] border-emerald-500/25 dark:bg-emerald-950/20"
                            : isDont
                            ? "bg-rose-500/[0.03] border-rose-500/25 dark:bg-rose-950/20"
                            : "bg-surface border-border"
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <div
                            className={`p-1.5 rounded-lg shrink-0 mt-0.5 ${
                              isDo
                                ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                                : isDont
                                ? "bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300"
                                : "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
                            }`}
                          >
                            {isDo ? (
                              <CheckCircle2 className="w-4 h-4" aria-hidden="true" />
                            ) : isDont ? (
                              <XCircle className="w-4 h-4" aria-hidden="true" />
                            ) : (
                              <Info className="w-4 h-4" aria-hidden="true" />
                            )}
                          </div>

                          <div className="flex flex-col gap-1">
                            <p className="text-xs sm:text-sm font-semibold text-foreground leading-snug">
                              {item.rule}
                            </p>
                            {item.reasoning && (
                              <p className="text-xs text-muted-foreground leading-relaxed">
                                {item.reasoning}
                              </p>
                            )}
                          </div>
                        </div>

                        <div className="flex items-center justify-between border-t border-border/60 pt-2 text-[11px] text-muted-foreground">
                          <Badge variant="outline" className="text-[10px] capitalize">
                            {item.category.replace("_", " ")}
                          </Badge>
                          {item.page && (
                            <span className="font-mono text-[10px]">p. {item.page}</span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          )}

          {/* Section 4: Channel Restrictions */}
          {(activeTab === "overview" || activeTab === "channels") && (
            <section aria-labelledby="channels-heading" className="flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 id="channels-heading" className="font-semibold text-lg text-foreground flex items-center gap-2">
                    <Radio className="w-5 h-5 text-foreground" aria-hidden="true" />
                    Channel-Specific Requirements
                  </h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Platform-specific guidelines for Instagram, Packaging, Billboard, and Email.
                  </p>
                </div>
                <Badge variant="outline" className="text-xs">
                  {channelRules.length} {channelRules.length === 1 ? "channel" : "channels"}
                </Badge>
              </div>

              {channelRules.length === 0 ? (
                <div className="p-6 rounded-card bg-surface border border-border text-center text-xs text-muted-foreground">
                  No channel-specific constraints extracted.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {channelRules.map((channel, index) => (
                    <div
                      key={`${channel.channel}-${index}`}
                      className="p-5 rounded-xl bg-surface border border-border shadow-xs flex flex-col gap-4"
                    >
                      <div className="flex items-center justify-between border-b border-border pb-3">
                        <h4 className="font-bold text-base text-foreground flex items-center gap-2">
                          <Radio className="w-4 h-4 text-foreground" aria-hidden="true" />
                          {channel.channel}
                        </h4>
                        <Badge variant="quote" className="text-[11px]">
                          Channel Specs
                        </Badge>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        {/* Channel DOs */}
                        <div className="flex flex-col gap-2">
                          <span className="text-xs font-semibold text-emerald-700 dark:text-emerald-400 flex items-center gap-1.5">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            Channel DOs
                          </span>
                          {!channel.dos || channel.dos.length === 0 ? (
                            <p className="text-xs text-muted-foreground italic">None specified</p>
                          ) : (
                            <ul className="space-y-1.5 text-xs text-foreground">
                              {channel.dos.map((item, i) => (
                                <li key={i} className="flex items-start gap-1.5 leading-snug">
                                  <span className="text-emerald-600 font-bold">•</span>
                                  <span>{item}</span>
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>

                        {/* Channel DONTs */}
                        <div className="flex flex-col gap-2">
                          <span className="text-xs font-semibold text-rose-700 dark:text-rose-400 flex items-center gap-1.5">
                            <XCircle className="w-3.5 h-3.5" />
                            Channel DONTs
                          </span>
                          {!channel.donts || channel.donts.length === 0 ? (
                            <p className="text-xs text-muted-foreground italic">None specified</p>
                          ) : (
                            <ul className="space-y-1.5 text-xs text-foreground">
                              {channel.donts.map((item, i) => (
                                <li key={i} className="flex items-start gap-1.5 leading-snug">
                                  <span className="text-rose-600 font-bold">•</span>
                                  <span>{item}</span>
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}
        </div>
      )}

      {/* Human-in-the-Loop Certification Native Dialog (Modern Web Guidance Compliant) */}
      <dialog
        ref={dialogRef}
        aria-labelledby="certify-dialog-title"
        aria-describedby="certify-dialog-desc"
        className="rounded-card bg-surface text-foreground border border-border p-6 shadow-2xl max-w-lg w-[calc(100vw-2rem)] mx-auto my-auto backdrop:bg-black/50 backdrop:backdrop-blur-sm"
      >
        <form onSubmit={handleCertifySubmit} className="flex flex-col gap-5">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <span className="p-2 rounded-xl bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                <ShieldCheck className="w-5 h-5" aria-hidden="true" />
              </span>
              <div>
                <h2 id="certify-dialog-title" className="font-bold text-lg text-foreground leading-tight">
                  Certify Brand Ontology
                </h2>
                <p id="certify-dialog-desc" className="text-xs text-muted-foreground mt-0.5">
                  Human-in-the-Loop approval for authoritative AI grounding.
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={closeCertifyModal}
              className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-surface-user"
              aria-label="Close certification dialog"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="p-4 rounded-xl bg-surface-user border border-border text-xs text-muted-foreground space-y-2">
            <p className="font-medium text-foreground">
              By certifying, you lock this ontology as the authoritative brand source:
            </p>
            <ul className="list-disc pl-4 space-y-1">
              <li>
                Colors: <strong>{colors.length}</strong> tokens verified
              </li>
              <li>
                Typography: <strong>{typography.length}</strong> font hierarchies approved
              </li>
              <li>
                Rules: <strong>{rawRules.length}</strong> DOs &amp; DONTs enforced
              </li>
              <li>
                Ask &amp; Campaign agents will strictly reference these constraints in prompt
                context.
              </li>
            </ul>
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="certifier-name" className="text-xs font-semibold text-foreground">
              Certifier Name / Role:
            </label>
            <input
              id="certifier-name"
              type="text"
              required
              value={certifierName}
              onChange={(e) => setCertifierName(e.target.value)}
              placeholder="e.g. Brand Director, Creative Lead"
              className="px-3.5 py-2 rounded-lg bg-surface border border-border text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          <div className="flex items-center gap-2 pt-1">
            <input
              id="certify-ack"
              type="checkbox"
              required
              checked={certifyAcknowledged}
              onChange={(e) => setCertifyAcknowledged(e.target.checked)}
              className="w-4 h-4 rounded text-foreground focus:ring-white/30 border-border"
            />
            <label htmlFor="certify-ack" className="text-xs text-muted-foreground cursor-pointer">
              I have reviewed these extracted rules and approve them for production creative use.
            </label>
          </div>

          <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-border">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={closeCertifyModal}
              autoFocus
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="success"
              size="sm"
              disabled={certifyMutation.isPending || !certifyAcknowledged}
              className="gap-2"
            >
              <ShieldCheck className="w-4 h-4" aria-hidden="true" />
              {certifyMutation.isPending ? "Certifying..." : "Confirm & Certify"}
            </Button>
          </div>
        </form>
      </dialog>
    </div>
  );
};
