import React, { useState, useRef, useEffect } from "react";
import { Link } from "react-router";
import {
  Send,
  Square,
  Copy,
  Check,
  CheckCircle2,
  ChevronRight,
  ExternalLink,
  Plus,
  User,
  Sparkles,
  BookOpen,
} from "lucide-react";
import { useBrand } from "@/context/BrandContext";
import { BrandMuseOrb } from "@/components/BrandMuseOrb";
import { DemoLimitsBanner } from "@/components/DemoLimitsBanner";
import { SourcesDrawer } from "@/components/SourcesDrawer";
import { Button } from "@/components/ui/button";
import { getSessionId } from "@/lib/session";
import { CitationItem } from "@/types/chat";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  citations?: CitationItem[];
  traceUrl?: string | null;
  quotedText?: string;
}

const SUGGESTED_PROMPTS = [
  "What is our brand tone of voice?",
  "Which primary and secondary colors can I use?",
  "What visual elements should we strictly avoid?",
  "What are our photography and lighting guidelines?",
];

export const AskPage: React.FC = () => {
  const { selectedDocumentId, selectedDocument, loadSampleBrand, isLoadingSample } = useBrand();

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeSources, setActiveSources] = useState<{
    citations: CitationItem[];
    traceUrl?: string | null;
  } | null>(null);

  const [copiedId, setCopiedId] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isStreaming]);

  // Auto-resize textarea (modern-web-guidance fallback when field-sizing: content is unsupported)
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    if (textareaRef.current && typeof CSS !== "undefined" && !CSS.supports("field-sizing", "content")) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
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
      ? lastAssistantMessage.content.slice(0, 100) + (lastAssistantMessage.content.length > 100 ? "..." : "")
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
            m.id === assistantMessageId
              ? { ...m, content: `Error: ${errMessage}` }
              : m
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
            if (nextLine && nextLine.startsWith("data: ")) {
              const tokenText = nextLine.slice(6);
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMessageId
                    ? { ...m, content: m.content + tokenText }
                    : m
                )
              );
            }
          } else if (line.startsWith("event: done")) {
            const nextLine = lines[++i];
            if (nextLine && nextLine.startsWith("data: ")) {
              try {
                const doneData = JSON.parse(nextLine.slice(6));
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMessageId
                      ? {
                          ...m,
                          citations: doneData.citations,
                          traceUrl: doneData.trace_url,
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
            if (nextLine && nextLine.startsWith("data: ")) {
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
      // Guard against premature submit during IME character composition per modern-web-guidance
      if (e.nativeEvent.isComposing || e.keyCode === 229) {
        return;
      }
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="w-full flex flex-col gap-6 animate-in fade-in duration-200">
      {/* Active Document Indicator / Prompt to Load */}
      {!selectedDocumentId && (
        <div className="p-4 rounded-card bg-surface border border-border shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <BookOpen className="w-5 h-5 text-ring shrink-0" aria-hidden="true" />
            <div>
              <p className="text-sm font-semibold text-foreground">No Brand Guideline Selected</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Load our fictional "Aura Living" guideline or upload your own PDF to start chatting.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button
              variant="default"
              size="sm"
              onClick={() => loadSampleBrand()}
              disabled={isLoadingSample}
            >
              <Sparkles className="w-3.5 h-3.5 mr-1.5" />
              {isLoadingSample ? "Loading sample..." : "Use sample brand"}
            </Button>
            <Button variant="outline" size="sm" asChild>
              <Link to="/documents">Upload PDF</Link>
            </Button>
          </div>
        </div>
      )}

      {/* Date Divider */}
      <div className="flex items-center gap-3 my-1">
        <div className="flex-1 h-px bg-border" />
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Today
        </span>
        <div className="flex-1 h-px bg-border" />
      </div>

      {/* Message List */}
      <div
        className="flex flex-col gap-6 min-h-[340px]"
        aria-live="polite"
        role="log"
        aria-label="Brand guideline conversation history"
      >
        {messages.length === 0 ? (
          /* Empty State */
          <div className="flex flex-col items-center justify-center py-12 text-center gap-4">
            <BrandMuseOrb size={48} />
            <div className="max-w-md">
              <h2 className="text-xl font-bold tracking-tight text-foreground">
                Ask about {selectedDocument?.filename || "your brand"}
              </h2>
              <p className="text-sm text-muted-foreground mt-1">
                Grounded strictly in verified guideline pages with exact page citations and audit traces.
              </p>
            </div>

            {/* Suggested Prompt Chips */}
            <div className="flex flex-wrap justify-center gap-2 max-w-lg mt-3">
              {SUGGESTED_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => handleSubmit(prompt)}
                  disabled={!selectedDocumentId}
                  className="px-3.5 py-2 rounded-full text-xs font-medium bg-surface text-foreground border border-border shadow-xs hover:border-ring hover:bg-surface-user transition-colors disabled:opacity-50"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* Conversation Stream */
          messages.map((msg) => {
            if (msg.role === "user") {
              return (
                <div key={msg.id} className="flex flex-col items-end gap-1.5 max-w-[85%] self-end">
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground px-1">
                    <span>You</span>
                    <User className="w-3.5 h-3.5" aria-hidden="true" />
                  </div>

                  <div className="p-4 rounded-card bg-surface-user border border-border shadow-xs text-sm text-foreground">
                    {msg.quotedText && (
                      <div className="mb-2 px-3 py-1.5 rounded-md bg-quote border-l-2 border-ring text-xs text-muted-foreground italic">
                        "{msg.quotedText}"
                      </div>
                    )}
                    <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                    <span className="block text-right text-[11px] text-muted-foreground mt-2">
                      {msg.timestamp}
                    </span>
                  </div>
                </div>
              );
            }

            // Assistant Message Card
            return (
              <div key={msg.id} className="flex flex-col items-start gap-1.5 max-w-[92%] self-start">
                <div className="flex items-center gap-2 text-xs font-semibold text-foreground px-1">
                  <BrandMuseOrb size={18} />
                  <span>BrandMuse</span>
                </div>

                <div className="w-full p-5 rounded-card bg-surface shadow-md text-sm text-foreground relative">
                  {msg.content ? (
                    <p className="whitespace-pre-wrap leading-relaxed">
                      {msg.content}
                      {isStreaming && msg.id === messages[messages.length - 1]?.id && (
                        <span className="inline-block w-2 h-4 ml-1 bg-ring animate-pulse align-middle" />
                      )}
                    </p>
                  ) : (
                    <div className="flex items-center gap-2 text-muted-foreground text-xs py-2">
                      <span className="inline-block w-2 h-4 bg-ring animate-pulse" />
                      <span>Reviewing brand guideline chunks...</span>
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
                        className="inline-flex items-center gap-1.5 font-medium text-muted-foreground hover:text-foreground transition-colors group"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5 text-success-icon" aria-hidden="true" />
                        <span className="italic">
                          Sources: {Array.from(new Set(msg.citations.map((c) => `p. ${c.page}`))).join(", ")}
                        </span>
                        <ChevronRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                      </button>

                      {msg.traceUrl && (
                        <a
                          href={msg.traceUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-[11px] text-ring hover:underline"
                        >
                          <span>Trace</span>
                          <ExternalLink className="w-3 h-3" aria-hidden="true" />
                        </a>
                      )}
                    </div>
                  )}

                  <span className="block text-right text-[11px] text-muted-foreground mt-2">
                    {msg.timestamp}
                  </span>
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
              </div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Stop Generating Button */}
      {isStreaming && (
        <div className="flex justify-center -mb-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleStopStreaming}
            className="shadow-sm rounded-full bg-surface"
          >
            <Square className="w-3 h-3 mr-1.5 fill-current" />
            Stop generating
          </Button>
        </div>
      )}

      {/* Demo Limits Banner */}
      <DemoLimitsBanner />

      {/* Input Bar (Pill-shaped Container, Radius 28px) */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSubmit();
        }}
        className="sticky bottom-4 z-10 w-full"
      >
        <div className="flex items-center gap-2 p-2 px-3 rounded-full bg-surface border border-border shadow-lg focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/20 transition-all">
          <Button
            variant="ghost"
            size="icon"
            className="rounded-full shrink-0 h-9 w-9 text-muted-foreground hover:text-foreground"
            asChild
            title="Manage guidelines"
            aria-label="Switch or upload brand guidelines"
          >
            <Link to="/documents">
              <Plus className="w-4 h-4" />
            </Link>
          </Button>

          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder={
              selectedDocument
                ? `Ask about ${selectedDocument.filename}...`
                : "Select a guideline above to ask questions..."
            }
            disabled={!selectedDocumentId || isStreaming}
            className="field-sizing-content flex-1 min-h-[38px] max-h-[160px] bg-transparent resize-none border-none outline-none text-sm text-foreground placeholder:text-muted-foreground px-1 py-1.5 leading-relaxed"
            aria-label="Ask about brand guidelines"
          />

          <Button
            type="submit"
            size="icon"
            disabled={!input.trim() || isStreaming || !selectedDocumentId}
            className="rounded-full shrink-0 h-9 w-9"
            aria-label="Send message"
          >
            <Send className="w-4 h-4" />
          </Button>
        </div>
      </form>

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
