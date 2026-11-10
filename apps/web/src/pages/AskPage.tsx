import {
  ArrowUpRight,
  Bookmark,
  BookOpen,
  Check,
  ChevronDown,
  Copy,
  Download,
  HelpCircle,
  Image as ImageIcon,
  Lightbulb,
  Palette,
  Plus,
  ShieldCheck,
  SlidersHorizontal,
  Square,
  Trash2,
  Upload,
  User,
} from "lucide-react";
import type React from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { BrandMuseOrb } from "@/components/BrandMuseOrb";
import { DemoLimitsBanner } from "@/components/DemoLimitsBanner";
import { SourcesDrawer } from "@/components/SourcesDrawer";
import { Button } from "@/components/ui/button";
import { useBrand } from "@/context/BrandContext";
import { getSessionId } from "@/lib/session";
import type { CitationItem } from "@/types/chat";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  citations?: CitationItem[];
  traceUrl?: string | null;
  quotedText?: string;
  suggestedFollowUps?: string[];
}

const QUICK_STARTERS = [
  {
    label: "Generate ideas",
    icon: Lightbulb,
    to: "/campaign",
    prompt: null,
  },
  {
    label: "Brand rules & tokens",
    icon: Palette,
    to: "/rules",
    prompt: null,
  },
  {
    label: "Visual gallery",
    icon: ImageIcon,
    to: "/gallery",
    prompt: null,
  },
  {
    label: "Ask brand questions",
    icon: HelpCircle,
    to: null,
    prompt: "What is our official brand tone of voice and core philosophy?",
  },
];

const SUGGESTED_PROMPTS = [
  "What is our brand tone of voice?",
  "Which primary and secondary colors can I use?",
  "What visual elements should we strictly avoid?",
  "What are our typography and font hierarchy rules?",
];

type ExecutionMode = "auto" | "strict" | "creative";

export const AskPage: React.FC = () => {
  const { selectedDocumentId, selectedDocument, loadSampleBrand, isLoadingSample } = useBrand();

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [executionMode, setExecutionMode] = useState<ExecutionMode>("auto");
  const [showModeDropdown, setShowModeDropdown] = useState(false);
  const [activeSources, setActiveSources] = useState<{
    citations: CitationItem[];
    traceUrl?: string | null;
  } | null>(null);

  const [copiedId, setCopiedId] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const modeDropdownRef = useRef<HTMLDivElement>(null);

  // Close mode selector dropdown on click outside or Escape key
  useEffect(() => {
    if (!showModeDropdown) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (modeDropdownRef.current && !modeDropdownRef.current.contains(e.target as Node)) {
        setShowModeDropdown(false);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setShowModeDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [showModeDropdown]);

  // Listen to New Chat action from sidebar
  useEffect(() => {
    const handleNewChat = () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      setMessages([]);
      setInput("");
      setIsStreaming(false);
    };
    window.addEventListener("brandmuse:new-chat", handleNewChat);
    return () => window.removeEventListener("brandmuse:new-chat", handleNewChat);
  }, []);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  const exportChatAsMarkdown = () => {
    if (messages.length === 0) return;

    let md = `# BrandMuse Research Transcript\n\n`;
    md += `**Brand Guideline:** ${selectedDocument?.filename || "Aura Living"}\n`;
    md += `**Date:** ${new Date().toLocaleDateString(undefined, { dateStyle: "long" })}\n\n`;
    md += `---\n\n`;

    messages.forEach((msg) => {
      if (msg.role === "user") {
        md += `### User\n${msg.content}\n\n`;
      } else {
        md += `### BrandMuse Assistant\n${msg.content}\n\n`;
        if (msg.citations && msg.citations.length > 0) {
          md += `**Citations:**\n`;
          msg.citations.forEach((c) => {
            md += `- [Page ${c.page}] ${c.snippet.trim()}\n`;
          });
          md += `\n`;
        }
      }
    });

    const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const name = (selectedDocument?.filename || "brand")
      .toLowerCase()
      .replace(/\.pdf$/i, "")
      .replace(/\s+/g, "-");
    a.href = url;
    a.download = `brandmuse-transcript-${name}-${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleClearChat = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setMessages([]);
    setInput("");
    setIsStreaming(false);
  };

  useEffect(() => {
    if (messages.length > 0 || isStreaming) {
      scrollToBottom();
    }
  }, [messages.length, isStreaming, scrollToBottom]);

  // Auto-resize textarea
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    if (
      textareaRef.current &&
      typeof CSS !== "undefined" &&
      !CSS.supports("field-sizing", "content")
    ) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  };

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleStopStreaming = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsStreaming(false);
    }
  };

  const handleSubmit = async (textToSend?: string) => {
    const text = (textToSend || input).trim();
    if (!text || isStreaming || !selectedDocumentId) return;

    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    const userMessageId = `user-${Date.now()}`;
    const assistantMessageId = `assistant-${Date.now()}`;
    const now = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    // Find previous assistant message to quote if relevant
    const lastAssistantMessage = [...messages].reverse().find((m) => m.role === "assistant");
    const quotedSnippet = lastAssistantMessage
      ? lastAssistantMessage.content.slice(0, 100) +
        (lastAssistantMessage.content.length > 100 ? "..." : "")
      : undefined;

    const userMessage: Message = {
      id: userMessageId,
      role: "user",
      content: text,
      timestamp: now,
      quotedText: quotedSnippet,
    };

    const assistantPlaceholder: Message = {
      id: assistantMessageId,
      role: "assistant",
      content: "",
      timestamp: now,
    };

    setMessages((prev) => [...prev, userMessage, assistantPlaceholder]);
    setIsStreaming(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    const historyPayload = messages.slice(-8).map((m) => ({
      role: m.role,
      content: m.content,
    }));

    try {
      const baseUrl = import.meta.env.VITE_API_URL || "";
      const response = await fetch(`${baseUrl}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Session-Id": getSessionId(),
        },
        body: JSON.stringify({
          document_id: selectedDocumentId,
          message: text,
          history: historyPayload,
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const errMessage = errorData.error?.message || `HTTP ${response.status} error`;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMessageId ? { ...m, content: `Error: ${errMessage}` } : m
          )
        );
        setIsStreaming(false);
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No readable stream received.");

      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (let i = 0; i < lines.length; i++) {
          const line = lines[i];
          if (!line) continue;
          if (line.startsWith("event: token")) {
            const nextLine = lines[++i];
            if (nextLine?.startsWith("data: ")) {
              const rawData = nextLine.slice(6);
              let tokenText = rawData;
              try {
                const parsed = JSON.parse(rawData);
                if (typeof parsed?.token === "string") {
                  tokenText = parsed.token;
                }
              } catch {
                // Fallback to raw string if not JSON
              }
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMessageId ? { ...m, content: m.content + tokenText } : m
                )
              );
            }
          } else if (line.startsWith("event: done")) {
            const nextLine = lines[++i];
            if (nextLine?.startsWith("data: ")) {
              try {
                const doneData = JSON.parse(nextLine.slice(6));
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMessageId
                      ? {
                          ...m,
                          citations: doneData.citations,
                          traceUrl: doneData.trace_url,
                          suggestedFollowUps: doneData.suggested_follow_ups,
                        }
                      : m
                  )
                );
              } catch {
                // Ignore JSON parse error
              }
            }
          } else if (line.startsWith("event: error")) {
            const nextLine = lines[++i];
            if (nextLine?.startsWith("data: ")) {
              try {
                const errData = JSON.parse(nextLine.slice(6));
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMessageId
                      ? {
                          ...m,
                          content:
                            m.content +
                            `\n\n[Generation stopped: ${errData.error?.message || "Error"}]`,
                        }
                      : m
                  )
                );
              } catch {
                // Ignore parse error
              }
            }
          }
        }
      }
    } catch (err: unknown) {
      if ((err as Error)?.name === "AbortError") {
        // Stream aborted by user
      } else {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMessageId
              ? {
                  ...m,
                  content:
                    m.content ||
                    "Could not complete the request. Please check that the backend is running.",
                }
              : m
          )
        );
      }
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      // Guard against premature submit during IME composition per modern-web-guidance
      if (e.nativeEvent.isComposing || e.keyCode === 229) {
        return;
      }
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="w-full flex flex-col gap-8 animate-in fade-in duration-300 relative">
      {/* Active Guideline Top Status Pill */}
      {selectedDocument && (
        <div className="flex items-center justify-between gap-3 text-xs">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-foreground/[0.04] border border-border dark:border-white/10 backdrop-blur-md">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="font-medium text-foreground">{selectedDocument.filename}</span>
            <span className="text-muted-foreground">• {selectedDocument.page_count} pages</span>
          </div>

          <div className="flex items-center gap-2">
            {messages.length > 0 && (
              <>
                <button
                  type="button"
                  onClick={exportChatAsMarkdown}
                  className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1.5 transition-colors px-3 py-1.5 rounded-full bg-foreground/[0.03] hover:bg-foreground/[0.06] border border-border dark:border-white/10"
                  title="Export chat transcript as Markdown"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Export Chat</span>
                </button>
                <button
                  type="button"
                  onClick={handleClearChat}
                  className="text-xs text-muted-foreground hover:text-danger flex items-center gap-1.5 transition-colors px-3 py-1.5 rounded-full bg-foreground/[0.03] hover:bg-danger/10 border border-border dark:border-white/10"
                  title="Clear conversation history"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Clear</span>
                </button>
              </>
            )}

            <Link
              to="/rules"
              className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1.5 transition-colors px-3 py-1.5 rounded-full bg-foreground/[0.03] hover:bg-foreground/[0.06] border border-border dark:border-white/10"
            >
              <ShieldCheck className="w-3.5 h-3.5 text-foreground/80" />
              <span>View Brand Rules</span>
            </Link>
          </div>
        </div>
      )}

      {/* STATE 1: Empty Hero State (Behance AI Assistant SaaS Style) */}
      {messages.length === 0 ? (
        <div className="relative flex flex-col items-center justify-center py-10 md:py-16 text-center gap-7 overflow-visible">
          {/* Ethereal Aurora Light Beam */}
          <div className="aurora-beam" aria-hidden="true" />

          {/* Central AI Mark */}
          <div className="relative z-10 flex flex-col items-center gap-4">
            <BrandMuseOrb size={54} animate />
            <div className="max-w-xl">
              <h1 className="text-3xl sm:text-4xl md:text-5xl font-normal tracking-tight text-foreground">
                Ask anything about your brand.
              </h1>
              <p className="text-xs sm:text-sm text-muted-foreground mt-2 max-w-md mx-auto">
                {selectedDocument ? (
                  <>
                    Grounded strictly in{" "}
                    <span className="text-foreground font-medium">{selectedDocument.filename}</span>{" "}
                    with exact page citations and audit traces.
                  </>
                ) : (
                  "Select or upload a brand guideline to begin."
                )}
              </p>

              {/* Integrated Brand Starter Pills */}
              {!selectedDocumentId && (
                <div className="flex items-center justify-center gap-2.5 mt-4">
                  <button
                    type="button"
                    onClick={() => loadSampleBrand()}
                    disabled={isLoadingSample}
                    className="glass-pill inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-medium text-foreground border border-border dark:border-white/15 dark:bg-white/[0.06] dark:hover:bg-white/[0.12] transition-all shadow-xs hover:shadow-sm hover:scale-105 active:scale-95 hover:border-foreground/30 dark:hover:border-white/30 cursor-pointer disabled:opacity-50"
                  >
                    <Bookmark className="w-3.5 h-3.5 text-foreground dark:text-white" />
                    <span>{isLoadingSample ? "Loading demo..." : "Load Aura Living (Demo)"}</span>
                  </button>
                  <Link
                    to="/documents"
                    className="glass-pill inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-medium text-muted-foreground hover:text-foreground border border-border dark:border-white/15 dark:bg-white/[0.04] dark:hover:bg-white/[0.10] transition-all shadow-xs hover:shadow-sm hover:scale-105 active:scale-95 hover:border-foreground/30 dark:hover:border-white/30 cursor-pointer"
                  >
                    <Upload className="w-3.5 h-3.5" />
                    <span>Upload PDF</span>
                  </Link>
                </div>
              )}
            </div>
          </div>

          {/* Floating Glass Prompt Capsule (Hero Input) */}
          <div className="relative z-10 w-full max-w-2xl mx-auto">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSubmit();
              }}
              className="glass-capsule rounded-3xl p-4 sm:p-5 flex flex-col gap-3 transition-all focus-within:border-foreground/30 focus-within:ring-2 focus-within:ring-foreground/10"
            >
              <textarea
                ref={textareaRef}
                rows={2}
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                placeholder="What do you want to know?"
                disabled={!selectedDocumentId || isStreaming}
                className="field-sizing-content w-full bg-transparent resize-none border-none outline-none text-base text-foreground placeholder:text-muted-foreground leading-relaxed max-h-[160px]"
                aria-label="Ask about brand guidelines"
              />

              {/* Bottom Capsule Controls */}
              <div className="flex items-center justify-between pt-1 border-t border-border/60 dark:border-white/[0.08]">
                {/* Mode Selector Pill with Hover & Click State */}
                <div className="relative" ref={modeDropdownRef}>
                  <button
                    type="button"
                    onClick={() => setShowModeDropdown(!showModeDropdown)}
                    className={`
                      flex items-center gap-1.5 px-3.5 py-1.5 min-h-[36px] rounded-full text-xs font-medium transition-all duration-200 shadow-xs
                      cursor-pointer select-none
                      border border-border dark:border-white/15
                      hover:scale-105 active:scale-95
                      ${
                        showModeDropdown
                          ? "bg-foreground/10 text-foreground ring-2 ring-foreground/20 border-foreground/30 dark:bg-white/15 dark:text-white dark:border-white/30"
                          : "bg-surface/80 hover:bg-surface text-foreground hover:border-foreground/30 dark:bg-white/[0.06] dark:hover:bg-white/[0.12] dark:hover:border-white/30"
                      }
                    `}
                    aria-haspopup="listbox"
                    aria-expanded={showModeDropdown}
                    title="Select AI execution mode"
                  >
                    <SlidersHorizontal className="w-3 h-3 text-foreground dark:text-white" />
                    <span className="capitalize">{executionMode}</span>
                    <ChevronDown
                      className={`w-3 h-3 text-muted-foreground ml-0.5 transition-transform duration-200 ${
                        showModeDropdown ? "rotate-180" : ""
                      }`}
                    />
                  </button>

                  {showModeDropdown && (
                    <div
                      className="absolute left-0 bottom-full mb-2 w-52 rounded-2xl bg-surface/95 dark:bg-[#141418]/95 border border-border dark:border-white/15 shadow-2xl p-1.5 z-30 flex flex-col gap-1 backdrop-blur-xl animate-in fade-in zoom-in-95 duration-150"
                      role="listbox"
                      aria-label="Execution mode options"
                    >
                      <button
                        type="button"
                        onClick={() => {
                          setExecutionMode("auto");
                          setShowModeDropdown(false);
                        }}
                        className={`px-3 py-2 rounded-xl text-xs text-left flex items-center justify-between transition-all duration-150 hover:scale-[1.02] active:scale-[0.98] cursor-pointer ${
                          executionMode === "auto"
                            ? "bg-foreground/10 dark:bg-white/10 font-semibold text-foreground dark:text-white border border-foreground/15 dark:border-white/20"
                            : "text-muted-foreground hover:bg-foreground/5 dark:hover:bg-white/5 hover:text-foreground"
                        }`}
                        role="option"
                        aria-selected={executionMode === "auto"}
                      >
                        <div className="flex flex-col">
                          <span className="font-medium text-foreground">Auto (Balanced)</span>
                          <span className="text-[10px] text-muted-foreground">
                            Standard guideline reasoning
                          </span>
                        </div>
                        {executionMode === "auto" && (
                          <Check className="w-3.5 h-3.5 text-foreground shrink-0" />
                        )}
                      </button>

                      <button
                        type="button"
                        onClick={() => {
                          setExecutionMode("strict");
                          setShowModeDropdown(false);
                        }}
                        className={`px-3 py-2 rounded-xl text-xs text-left flex items-center justify-between transition-all duration-150 hover:scale-[1.02] active:scale-[0.98] cursor-pointer ${
                          executionMode === "strict"
                            ? "bg-foreground/10 dark:bg-white/10 font-semibold text-foreground dark:text-white border border-foreground/15 dark:border-white/20"
                            : "text-muted-foreground hover:bg-foreground/5 dark:hover:bg-white/5 hover:text-foreground"
                        }`}
                        role="option"
                        aria-selected={executionMode === "strict"}
                      >
                        <div className="flex flex-col">
                          <span className="font-medium text-foreground">Strict Rules Only</span>
                          <span className="text-[10px] text-muted-foreground">
                            Strict guideline matching
                          </span>
                        </div>
                        {executionMode === "strict" && (
                          <Check className="w-3.5 h-3.5 text-foreground shrink-0" />
                        )}
                      </button>
                    </div>
                  )}
                </div>

                {/* Right Action Tools Matching Behance with Hover & Click State */}
                <div className="flex items-center gap-2">
                  <Link
                    to="/documents"
                    className="p-2.5 min-w-[36px] min-h-[36px] flex items-center justify-center rounded-xl text-muted-foreground hover:text-foreground hover:bg-foreground/[0.06] hover:scale-110 active:scale-95 transition-all cursor-pointer"
                    title="Upload or manage brand PDFs"
                    aria-label="Manage documents"
                  >
                    <Plus className="w-4 h-4" />
                  </Link>

                  <button
                    type="submit"
                    disabled={!input.trim() || isStreaming || !selectedDocumentId}
                    className="w-9 h-9 rounded-xl bg-foreground text-background hover:opacity-90 disabled:opacity-25 flex items-center justify-center transition-all shadow-xs hover:scale-110 active:scale-90 shrink-0 cursor-pointer"
                    aria-label="Send query"
                  >
                    <ArrowUpRight className="w-4 h-4 text-background stroke-[2.5]" />
                  </button>
                </div>
              </div>
            </form>

            {/* Behance Quick Action Starters Row */}
            <div className="flex flex-wrap items-center justify-center gap-2.5 mt-5">
              {QUICK_STARTERS.map((item) => {
                const Icon = item.icon;
                if (item.to) {
                  return (
                    <Link
                      key={item.label}
                      to={item.to}
                      className="glass-pill px-4 py-2 rounded-full text-xs font-medium text-foreground flex items-center gap-2 shadow-xs group"
                    >
                      <Icon className="w-3.5 h-3.5 text-muted-foreground group-hover:text-foreground transition-colors" />
                      <span>{item.label}</span>
                    </Link>
                  );
                }
                return (
                  <button
                    key={item.label}
                    type="button"
                    onClick={() => {
                      if (item.prompt) handleSubmit(item.prompt);
                    }}
                    disabled={!selectedDocumentId}
                    className="glass-pill px-4 py-2 rounded-full text-xs font-medium text-foreground flex items-center gap-2 shadow-xs group disabled:opacity-40"
                  >
                    <Icon className="w-3.5 h-3.5 text-muted-foreground group-hover:text-foreground transition-colors" />
                    <span>{item.label}</span>
                  </button>
                );
              })}
            </div>

            {/* Suggested Prompt Chips */}
            <div className="flex flex-wrap justify-center gap-2 max-w-lg mx-auto mt-4">
              {SUGGESTED_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => handleSubmit(prompt)}
                  disabled={!selectedDocumentId}
                  className="px-3 py-1.5 rounded-full text-[11px] font-medium text-muted-foreground hover:text-foreground bg-foreground/[0.03] hover:bg-foreground/[0.07] border border-border dark:border-white/5 transition-all disabled:opacity-40"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : (
        /* STATE 2: Active Conversation Stream */
        <div className="flex flex-col gap-6">
          {/* Messages Log */}
          <div
            className="flex flex-col gap-6 min-h-[380px]"
            aria-live="polite"
            role="log"
            aria-label="Brand guideline conversation history"
          >
            {messages.map((msg) => {
              if (msg.role === "user") {
                return (
                  <div
                    key={msg.id}
                    className="flex flex-col items-end gap-1.5 max-w-[85%] sm:max-w-[75%] self-end animate-in fade-in duration-200"
                  >
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground px-1">
                      <span>You</span>
                      <User className="w-3.5 h-3.5" aria-hidden="true" />
                    </div>

                    <div className="p-4 rounded-2xl bg-surface-user border border-border text-sm text-foreground shadow-xs">
                      {msg.quotedText && (
                        <div className="mb-2 px-3 py-1.5 rounded-md bg-quote border-l-2 border-ring text-xs text-muted-foreground italic">
                          &ldquo;{msg.quotedText}&rdquo;
                        </div>
                      )}
                      <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                      <span className="block text-right text-[10px] text-muted-foreground mt-2 font-mono">
                        {msg.timestamp}
                      </span>
                    </div>
                  </div>
                );
              }

              // Assistant Message Card
              return (
                <div
                  key={msg.id}
                  className="flex flex-col items-start gap-1.5 max-w-[95%] sm:max-w-[85%] self-start animate-in fade-in duration-200"
                >
                  <div className="flex items-center gap-2 text-xs font-semibold text-foreground px-1">
                    <BrandMuseOrb size={18} />
                    <span>BrandMuse</span>
                  </div>

                  <div className="w-full p-5 sm:p-6 rounded-2xl bg-surface border border-border shadow-xs text-sm text-foreground relative">
                    {msg.content ? (
                      <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                    ) : (
                      <div className="flex items-center gap-2 text-muted-foreground text-xs py-2">
                        <span className="inline-block w-2 h-4 bg-foreground animate-pulse" />
                        <span>Searching brand guidelines and fusing ranks...</span>
                      </div>
                    )}

                    {/* Sources row & citations */}
                    {msg.citations && msg.citations.length > 0 && (
                      <div className="mt-4 pt-3 border-t border-border flex flex-wrap items-center justify-between gap-2 text-xs">
                        <button
                          type="button"
                          onClick={() =>
                            setActiveSources({
                              citations: msg.citations || [],
                              traceUrl: msg.traceUrl,
                            })
                          }
                          className="inline-flex items-center gap-1.5 font-medium text-foreground hover:underline"
                        >
                          <BookOpen className="w-3.5 h-3.5" />
                          <span>
                            {msg.citations.length} guideline source
                            {msg.citations.length === 1 ? "" : "s"}
                          </span>
                        </button>

                        <div className="flex items-center gap-1.5 flex-wrap">
                          {msg.citations.slice(0, 4).map((c, i) => (
                            <span
                              key={i}
                              className="px-2 py-0.5 rounded bg-surface-user border border-border font-mono text-[10px] text-muted-foreground"
                            >
                              p. {c.page}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Actions row: Copy Button */}
                  {msg.content && (
                    <div className="flex items-center gap-2 px-1">
                      <button
                        type="button"
                        onClick={() => handleCopy(msg.id, msg.content)}
                        className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors py-1 px-2 rounded-md hover:bg-surface-user"
                        aria-label="Copy answer to clipboard"
                      >
                        {copiedId === msg.id ? (
                          <>
                            <Check className="w-3.5 h-3.5 text-success-icon" />
                            <span>Copied</span>
                          </>
                        ) : (
                          <>
                            <Copy className="w-3.5 h-3.5" />
                            <span>Copy</span>
                          </>
                        )}
                      </button>
                    </div>
                  )}

                  {/* Contextual Follow-Up Suggestions (Dynamic Chips) */}
                  {msg.suggestedFollowUps && msg.suggestedFollowUps.length > 0 && !isStreaming && (
                    <div className="flex flex-wrap items-center gap-1.5 mt-1 px-1">
                      <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider block w-full mb-0.5">
                        Suggested follow-ups:
                      </span>
                      {msg.suggestedFollowUps.map((question, qIdx) => (
                        <button
                          key={qIdx}
                          type="button"
                          onClick={() => handleSubmit(question)}
                          className="glass-pill rounded-full text-xs px-3 py-1 font-medium text-foreground/80 hover:text-foreground transition-all hover:scale-[1.02] active:scale-[0.98]"
                        >
                          {question}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
            <div ref={messagesEndRef} />
          </div>

          {/* Stop Generating Button */}
          {isStreaming && (
            <div className="flex justify-center -mb-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleStopStreaming}
                className="shadow-xs rounded-full bg-surface border border-border"
              >
                <Square className="w-3 h-3 mr-1.5 fill-current" />
                Stop generating
              </Button>
            </div>
          )}

          {/* Sticky Bottom Floating Glass Prompt Capsule */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSubmit();
            }}
            className="sticky bottom-4 z-20 w-full"
          >
            <div className="glass-capsule rounded-2xl p-2.5 px-4 flex items-center gap-3 shadow-2xl focus-within:border-foreground/20 transition-all">
              <Link
                to="/documents"
                className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-foreground/[0.06] transition-colors"
                title="Manage guidelines"
                aria-label="Switch or upload brand guidelines"
              >
                <Plus className="w-4 h-4" />
              </Link>

              <textarea
                ref={textareaRef}
                rows={1}
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                placeholder={
                  selectedDocument
                    ? `Ask about ${selectedDocument.filename}...`
                    : "Select a guideline above..."
                }
                disabled={!selectedDocumentId || isStreaming}
                className="field-sizing-content flex-1 min-h-[38px] max-h-[160px] bg-transparent resize-none border-none outline-none text-sm text-foreground placeholder:text-muted-foreground leading-relaxed"
                aria-label="Ask about brand guidelines"
              />

              <button
                type="submit"
                disabled={!input.trim() || isStreaming || !selectedDocumentId}
                className="w-8 h-8 rounded-xl bg-foreground text-background hover:opacity-90 disabled:opacity-20 flex items-center justify-center transition-all shrink-0 shadow-xs hover:scale-105 active:scale-95"
                aria-label="Send message"
              >
                <ArrowUpRight className="w-4 h-4 text-background stroke-[2.5]" />
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Demo Limits Banner */}
      <DemoLimitsBanner />

      {/* Sources Drawer Panel */}
      <SourcesDrawer
        isOpen={Boolean(activeSources)}
        onClose={() => setActiveSources(null)}
        citations={activeSources?.citations || []}
        traceUrl={activeSources?.traceUrl}
      />
    </div>
  );
};

export default AskPage;
