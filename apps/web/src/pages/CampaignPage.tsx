import {
  AlertCircle,
  AlertTriangle,
  Bookmark,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Copy,
  Download,
  ExternalLink,
  Image as ImageIcon,
  Layers,
  RefreshCw,
  RotateCcw,
  Send,
  Sliders,
} from "lucide-react";
import type React from "react";
import { useState } from "react";
import { Link } from "react-router";
import { useGenerateCampaign, useGenerateImage, useRefineConcept } from "@/api/generated";
import type { Concept } from "@/api/model";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useBrand } from "@/context/BrandContext";

const CHANNELS = ["Instagram", "LinkedIn", "Outdoor / Billboard", "Pinterest", "Email Newsletter"];

const PRESET_MOODS = [
  "Serene & Warm",
  "Vibrant & Bold",
  "Earthy Minimalism",
  "Playful & Contemporary",
];

interface GeneratedImageState {
  [conceptIndex: number]: {
    url?: string;
    loading: boolean;
    error?: string;
  };
}

export const CampaignPage: React.FC = () => {
  const { selectedDocumentId, loadSampleBrand, isLoadingSample } = useBrand();

  const [product, setProduct] = useState("");
  const [audience, setAudience] = useState("");
  const [channel, setChannel] = useState(CHANNELS[0] || "Instagram");
  const [mood, setMood] = useState(PRESET_MOODS[0] || "Serene & Warm");
  const [referenceExamples, setReferenceExamples] = useState("");
  const [showReferenceExamples, setShowReferenceExamples] = useState(false);

  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [brandRulesUsed, setBrandRulesUsed] = useState<string[]>([]);
  const [traceUrl, setTraceUrl] = useState<string | null>(null);

  const [expandedPromptIndex, setExpandedPromptIndex] = useState<number | null>(null);
  const [imageStates, setImageStates] = useState<GeneratedImageState>({});
  const [copiedPromptIndex, setCopiedPromptIndex] = useState<number | null>(null);
  const [showHowItWasMade, setShowHowItWasMade] = useState(false);

  const [activeRefineIndex, setActiveRefineIndex] = useState<number | null>(null);
  const [refineInstruction, setRefineInstruction] = useState("");
  const [refiningIndex, setRefiningIndex] = useState<number | null>(null);
  const [aspectRatios, setAspectRatios] = useState<Record<number, string>>({});

  const campaignMutation = useGenerateCampaign();
  const imageMutation = useGenerateImage();
  const refineMutation = useRefineConcept();

  const handleRefineSubmit = async (concept: Concept, index: number) => {
    if (!selectedDocumentId || !refineInstruction.trim()) return;

    setRefiningIndex(index);
    try {
      const updatedConcept = await refineMutation.mutateAsync({
        data: {
          document_id: selectedDocumentId,
          concept,
          instruction: refineInstruction.trim(),
        },
      });

      setConcepts((prev) => {
        const next = [...prev];
        next[index] = updatedConcept;
        return next;
      });

      // Clear image for this revised concept since visual prompt was updated
      setImageStates((prev) => {
        const next = { ...prev };
        delete next[index];
        return next;
      });

      setActiveRefineIndex(null);
      setRefineInstruction("");
    } catch (err) {
      console.error("Failed to refine concept:", err);
    } finally {
      setRefiningIndex(null);
    }
  };

  const handleGenerateCampaign = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDocumentId || !product.trim() || !audience.trim()) return;

    try {
      const res = await campaignMutation.mutateAsync({
        data: {
          document_id: selectedDocumentId,
          brief: {
            product: product.trim(),
            audience: audience.trim(),
            channel: channel || "Instagram",
            mood: mood || "Serene & Warm",
            reference_examples: referenceExamples.trim() || undefined,
          },
        },
      });

      setConcepts(res.concepts || []);
      setBrandRulesUsed(res.brand_rules_used || []);
      setTraceUrl(res.trace_url || null);
      setImageStates({});
    } catch (err) {
      console.error("Failed to generate campaign:", err);
    }
  };

  const handleGenerateImage = async (concept: Concept, index: number) => {
    setImageStates((prev) => ({
      ...prev,
      [index]: { loading: true, error: undefined },
    }));

    const ratio = aspectRatios[index] || "1:1";
    // Extract dynamic negative prompt if brand rules mention prohibited elements or donts
    const dynamicRestrictions = (concept.brand_rules_used || [])
      .filter((r) => /don't|no |never|prohibit|avoid/i.test(r))
      .join(", ");

    try {
      const res = await imageMutation.mutateAsync({
        data: {
          image_prompt: concept.image_prompt,
          concept_title: concept.title,
          aspect_ratio: ratio,
          negative_prompt: dynamicRestrictions || undefined,
          concept_json: {
            caption: concept.caption,
            hashtags: concept.hashtags,
            visual_direction: concept.visual_direction,
            brand_rules_used: concept.brand_rules_used,
            aspect_ratio: ratio,
          },
        },
      });

      setImageStates((prev) => ({
        ...prev,
        [index]: { loading: false, url: res.url },
      }));
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error
          ?.message || "Failed to generate image asset.";
      setImageStates((prev) => ({
        ...prev,
        [index]: { loading: false, error: msg },
      }));
    }
  };

  const handleCopyPrompt = (promptText: string, index: number) => {
    navigator.clipboard.writeText(promptText);
    setCopiedPromptIndex(index);
    setTimeout(() => setCopiedPromptIndex(null), 2000);
  };

  return (
    <div className="w-full flex flex-col gap-8 animate-in fade-in duration-200">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-foreground">Campaign Director</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Synthesize 3 distinct, on-brand creative concepts from your brief with generated visual
          assets.
        </p>
      </div>

      {/* No Document Warning */}
      {!selectedDocumentId && (
        <div className="p-4 rounded-card bg-surface border border-border flex items-center justify-between gap-3 shadow-xs">
          <div className="flex items-center gap-3">
            <BookOpen className="w-5 h-5 text-foreground/80 shrink-0" />
            <p className="text-xs text-muted-foreground">
              Please select or load a brand guideline to generate grounded concepts.
            </p>
          </div>
          <Button
            variant="default"
            size="sm"
            onClick={() => loadSampleBrand()}
            disabled={isLoadingSample}
          >
            <Bookmark className="w-3.5 h-3.5 mr-1.5" />
            {isLoadingSample ? "Loading..." : "Use sample brand"}
          </Button>
        </div>
      )}

      {/* Campaign Brief Form Card */}
      <div className="p-6 sm:p-7 rounded-card bg-surface border border-border shadow-xs">
        <form onSubmit={handleGenerateCampaign} className="flex flex-col gap-5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Product / Service */}
            <div className="flex flex-col gap-1.5">
              <label htmlFor="product" className="text-xs font-semibold text-foreground">
                Product or Initiative
              </label>
              <input
                id="product"
                type="text"
                required
                value={product}
                onChange={(e) => setProduct(e.target.value)}
                placeholder="e.g. Handcrafted Ceramic Teapot Collection"
                className="w-full px-3.5 py-2.5 rounded-lg border border-border bg-surface text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>

            {/* Target Audience */}
            <div className="flex flex-col gap-1.5">
              <label htmlFor="audience" className="text-xs font-semibold text-foreground">
                Target Audience
              </label>
              <input
                id="audience"
                type="text"
                required
                value={audience}
                onChange={(e) => setAudience(e.target.value)}
                placeholder="e.g. Design-conscious urban homeowners"
                className="w-full px-3.5 py-2.5 rounded-lg border border-border bg-surface text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Channel Select */}
            <div className="flex flex-col gap-1.5">
              <label htmlFor="channel" className="text-xs font-semibold text-foreground">
                Primary Marketing Channel
              </label>
              <select
                id="channel"
                value={channel}
                onChange={(e) => setChannel(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-lg border border-border bg-surface text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {CHANNELS.map((ch) => (
                  <option key={ch} value={ch}>
                    {ch}
                  </option>
                ))}
              </select>
            </div>

            {/* Desired Mood */}
            <fieldset className="flex flex-col gap-1.5 border-none p-0 m-0">
              <legend className="text-xs font-semibold text-foreground mb-1.5">Desired Mood</legend>
              <div className="flex flex-wrap gap-2">
                {PRESET_MOODS.map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setMood(m)}
                    className={`
                      px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors
                      ${mood === m ? "bg-foreground text-background font-semibold shadow-xs" : "bg-surface-user text-muted-foreground border-border hover:text-foreground"}
                    `}
                    aria-pressed={mood === m}
                  >
                    {m}
                  </button>
                ))}
              </div>
            </fieldset>
          </div>

          {/* Optional Golden Voice Calibration Accordion */}
          <div className="pt-2 border-t border-border/60">
            <button
              type="button"
              onClick={() => setShowReferenceExamples(!showReferenceExamples)}
              className="flex items-center gap-2 text-xs font-semibold text-muted-foreground hover:text-foreground transition-colors"
            >
              <BookOpen className="w-3.5 h-3.5 text-foreground/80" />
              <span>Brand Voice References / Past Golden Copy (Optional)</span>
              {showReferenceExamples ? (
                <ChevronUp className="w-3.5 h-3.5 ml-auto" />
              ) : (
                <ChevronDown className="w-3.5 h-3.5 ml-auto" />
              )}
            </button>

            {showReferenceExamples && (
              <div className="mt-2.5 flex flex-col gap-1.5 animate-in fade-in duration-150">
                <p className="text-[11px] text-muted-foreground">
                  Paste past winning captions, slogans, or approved copy snippets to calibrate
                  sentence rhythm and vocabulary.
                </p>
                <textarea
                  rows={3}
                  value={referenceExamples}
                  onChange={(e) => setReferenceExamples(e.target.value)}
                  placeholder="e.g. 'Thoughtfully designed for quiet moments at home. Grounded in craft, made to last a lifetime.'"
                  className="w-full px-3.5 py-2 rounded-lg border border-border bg-surface text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            )}
          </div>

          <Button
            type="submit"
            disabled={
              !selectedDocumentId ||
              !product.trim() ||
              !audience.trim() ||
              campaignMutation.isPending
            }
            className="w-full md:w-auto self-start mt-2"
          >
            <Layers className="w-4 h-4 mr-2" />
            {campaignMutation.isPending
              ? "Directing 3 on-brand concepts..."
              : "Generate 3 concepts"}
          </Button>

          {campaignMutation.isError && (
            <div
              role="alert"
              className="p-3 rounded-md bg-danger/10 border border-danger/20 text-xs text-danger flex items-center gap-2"
            >
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>Failed to generate campaign concepts. Daily quota may have been reached.</span>
            </div>
          )}
        </form>
      </div>

      {/* Concepts Responsive Grid */}
      {concepts.length > 0 && (
        <div className="flex flex-col gap-6">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-lg text-foreground">Creative Directions</h3>
            <span className="text-xs text-muted-foreground">3 concepts generated</span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
            {concepts.map((concept, index) => {
              const imgState = imageStates[index];
              const isPromptExpanded = expandedPromptIndex === index;

              return (
                <div
                  key={concept.title}
                  className="p-6 rounded-card bg-surface border border-border shadow-xs flex flex-col justify-between gap-5 transition-all hover:border-foreground/20 hover:shadow-sm"
                >
                  <div className="flex flex-col gap-3">
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-[11px] font-bold text-foreground/90 uppercase tracking-wider">
                        Concept 0{index + 1}
                      </span>
                      <button
                        type="button"
                        onClick={() => {
                          if (activeRefineIndex === index) {
                            setActiveRefineIndex(null);
                          } else {
                            setActiveRefineIndex(index);
                            setRefineInstruction("");
                          }
                        }}
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-medium border transition-colors ${
                          activeRefineIndex === index
                            ? "bg-foreground text-background font-semibold"
                            : "border-border bg-foreground/5 hover:bg-foreground/10 text-muted-foreground hover:text-foreground"
                        }`}
                        title="Refine this concept with creative feedback"
                      >
                        <Sliders className="w-3 h-3" />
                        <span>Refine</span>
                      </button>
                    </div>

                    {activeRefineIndex === index && (
                      <div className="p-2.5 rounded-xl bg-surface-user border border-border/80 flex flex-col gap-2 animate-in fade-in duration-150">
                        <label
                          htmlFor={`refine-${index}`}
                          className="text-[10px] font-semibold text-muted-foreground"
                        >
                          Creative Direction / Revision:
                        </label>
                        <div className="flex gap-1.5">
                          <input
                            id={`refine-${index}`}
                            type="text"
                            value={refineInstruction}
                            onChange={(e) => setRefineInstruction(e.target.value)}
                            placeholder="e.g. 'Punchier hook for TikTok' or 'More warm lighting'"
                            className="w-full px-2.5 py-1.5 text-xs rounded-lg bg-surface border border-border text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                            onKeyDown={(e) => {
                              if (e.key === "Enter" && !e.shiftKey) {
                                e.preventDefault();
                                handleRefineSubmit(concept, index);
                              }
                            }}
                          />
                          <Button
                            type="button"
                            size="sm"
                            disabled={!refineInstruction.trim() || refiningIndex === index}
                            onClick={() => handleRefineSubmit(concept, index)}
                            className="px-2.5 h-8 text-xs shrink-0"
                          >
                            {refiningIndex === index ? (
                              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <Send className="w-3.5 h-3.5" />
                            )}
                          </Button>
                        </div>
                      </div>
                    )}

                    <h4 className="text-base font-bold text-foreground leading-snug">
                      {concept.title}
                    </h4>

                    <p className="text-xs text-foreground/85 leading-relaxed bg-surface-user p-3 rounded-lg border border-border/40">
                      "{concept.caption}"
                    </p>

                    {/* Hashtags */}
                    <div className="flex flex-wrap gap-1.5">
                      {concept.hashtags?.map((tag) => (
                        <span
                          key={tag}
                          className="text-[10px] text-foreground font-medium bg-white/[0.06] border border-white/10 px-2 py-0.5 rounded-full"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>

                    {/* Visual Art Direction */}
                    <div className="text-xs text-muted-foreground pt-1">
                      <strong className="text-foreground block mb-0.5">Art Direction:</strong>
                      {concept.visual_direction}
                    </div>

                    {/* Brand Rules Incorporated */}
                    {concept.brand_rules_used && concept.brand_rules_used.length > 0 && (
                      <div className="pt-2 border-t border-border/80">
                        <span className="text-[11px] font-semibold text-muted-foreground block mb-1">
                          Brand rules applied:
                        </span>
                        <div className="flex flex-wrap gap-1">
                          {concept.brand_rules_used.map((rule) => (
                            <Badge key={rule} variant="quote" className="text-[10px] py-0">
                              {rule}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Brand Compliance Scorecard */}
                    {concept.compliance_checks && concept.compliance_checks.length > 0 && (
                      <div className="pt-2 border-t border-border/80 flex flex-col gap-1.5">
                        <span className="text-[11px] font-semibold text-muted-foreground block">
                          Compliance scorecard:
                        </span>
                        <div className="flex flex-col gap-1">
                          {concept.compliance_checks.map((check, cIdx) => (
                            <div
                              key={cIdx}
                              className={`flex items-start gap-1.5 p-1.5 rounded-md text-[11px] border ${
                                check.passed
                                  ? "bg-emerald-500/5 border-emerald-500/20 text-emerald-950 dark:text-emerald-300"
                                  : "bg-amber-500/5 border-amber-500/20 text-amber-950 dark:text-amber-300"
                              }`}
                            >
                              {check.passed ? (
                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 mt-0.5 shrink-0" />
                              ) : (
                                <AlertCircle className="w-3.5 h-3.5 text-amber-500 mt-0.5 shrink-0" />
                              )}
                              <div className="leading-tight">
                                <span className="font-semibold mr-1">{check.category}:</span>
                                <span className="opacity-90">{check.detail}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Collapsible Image Prompt Section */}
                    <div className="pt-2 border-t border-border/80">
                      <button
                        type="button"
                        onClick={() => setExpandedPromptIndex(isPromptExpanded ? null : index)}
                        className="w-full flex items-center justify-between text-xs text-muted-foreground hover:text-foreground font-medium"
                      >
                        <span>Stable Diffusion prompt</span>
                        {isPromptExpanded ? (
                          <ChevronUp className="w-3.5 h-3.5" />
                        ) : (
                          <ChevronDown className="w-3.5 h-3.5" />
                        )}
                      </button>

                      {isPromptExpanded && (
                        <div className="mt-2 p-2.5 rounded-md bg-surface-user border border-border text-[11px] text-foreground font-mono leading-relaxed relative">
                          <p>{concept.image_prompt}</p>
                          <button
                            type="button"
                            onClick={() => handleCopyPrompt(concept.image_prompt, index)}
                            className="mt-2 inline-flex items-center gap-1 text-[10px] text-foreground hover:underline"
                          >
                            {copiedPromptIndex === index ? (
                              <>
                                <Check className="w-3 h-3 text-success-icon" />
                                <span>Copied prompt</span>
                              </>
                            ) : (
                              <>
                                <Copy className="w-3 h-3" />
                                <span>Copy prompt</span>
                              </>
                            )}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Image Generation Section */}
                  <div className="pt-4 border-t border-border flex flex-col gap-3">
                    {(() => {
                      const ratio = aspectRatios[index] || "1:1";
                      const aspectClass =
                        ratio === "9:16"
                          ? "aspect-[9/16]"
                          : ratio === "16:9"
                            ? "aspect-[16/9]"
                            : "aspect-square";
                      const dimensionsLabel =
                        ratio === "9:16" ? "576x1024" : ratio === "16:9" ? "1024x576" : "1024x1024";

                      if (imgState?.loading) {
                        return (
                          <div className="flex flex-col items-center gap-2">
                            <Skeleton className={`w-full ${aspectClass} rounded-lg`} />
                            <span className="text-xs text-muted-foreground animate-pulse">
                              Synthesizing {dimensionsLabel} asset...
                            </span>
                          </div>
                        );
                      }

                      if (imgState?.url) {
                        return (
                          <div className="flex flex-col gap-2">
                            <img
                              src={imgState.url}
                              alt={concept.title}
                              className={`w-full ${aspectClass} object-cover rounded-lg shadow-sm border border-border`}
                              decoding="async"
                              fetchPriority="high"
                            />
                            <div className="flex items-center justify-between pt-1">
                              <a
                                href={imgState.url}
                                target="_blank"
                                download={`brandmuse-${concept.title.toLowerCase().replace(/\s+/g, "-")}.png`}
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1.5 text-xs text-foreground font-medium hover:underline transition-colors"
                              >
                                <Download className="w-3.5 h-3.5" />
                                <span>Download</span>
                              </a>
                              <Link
                                to="/gallery"
                                className="text-xs text-foreground hover:underline"
                              >
                                View in Gallery
                              </Link>
                            </div>
                          </div>
                        );
                      }

                      return (
                        <>
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-[11px] font-semibold text-muted-foreground">
                              Aspect ratio:
                            </span>
                            <div className="flex items-center gap-1 p-0.5 rounded-lg bg-surface-user border border-border">
                              {(["1:1", "9:16", "16:9"] as const).map((r) => {
                                const active = ratio === r;
                                return (
                                  <button
                                    key={r}
                                    type="button"
                                    onClick={() =>
                                      setAspectRatios((prev) => ({ ...prev, [index]: r }))
                                    }
                                    className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
                                      active
                                        ? "bg-foreground text-background font-semibold shadow-xs"
                                        : "text-muted-foreground hover:text-foreground"
                                    }`}
                                    title={
                                      r === "1:1"
                                        ? "1:1 Square (Feed)"
                                        : r === "9:16"
                                          ? "9:16 Vertical (Stories / Reels / TikTok)"
                                          : "16:9 Landscape (Hero / Banner)"
                                    }
                                  >
                                    {r}
                                  </button>
                                );
                              })}
                            </div>
                          </div>

                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => handleGenerateImage(concept, index)}
                            className="w-full"
                          >
                            <ImageIcon className="w-4 h-4 mr-2 text-foreground" />
                            Generate image asset
                          </Button>
                          {imgState?.error && (
                            <div className="flex items-center justify-between text-[11px] text-danger p-2 bg-danger/10 rounded-md">
                              <span>{imgState.error}</span>
                              <button
                                type="button"
                                onClick={() => handleGenerateImage(concept, index)}
                                className="p-1 hover:underline flex items-center gap-1"
                              >
                                <RotateCcw className="w-3 h-3" />
                                Retry
                              </button>
                            </div>
                          )}
                        </>
                      );
                    })()}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Collapsible "How this was made" section */}
          <div className="p-4 rounded-card bg-surface-user border border-border">
            <button
              type="button"
              onClick={() => setShowHowItWasMade(!showHowItWasMade)}
              className="w-full flex items-center justify-between text-xs font-semibold text-foreground"
            >
              <span>How this was made (RAG Grounding & Traces)</span>
              {showHowItWasMade ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
            </button>

            {showHowItWasMade && (
              <div className="mt-4 pt-3 border-t border-border/80 flex flex-col gap-3 text-xs text-muted-foreground">
                <p>
                  Concepts are synthesized using 3 concurrent hybrid queries (copy tone, photography
                  lighting, and brand prohibitions) fused with Reciprocal Rank Fusion.
                </p>

                {brandRulesUsed.length > 0 && (
                  <div>
                    <strong className="text-foreground block mb-1">Aggregated Brand Rules:</strong>
                    <ul className="list-disc pl-5 space-y-1">
                      {brandRulesUsed.map((rule) => (
                        <li key={rule}>{rule}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {traceUrl && (
                  <div className="pt-2">
                    <a
                      href={traceUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 font-medium text-foreground hover:underline"
                    >
                      <span>Inspect audit trace in Langfuse</span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
