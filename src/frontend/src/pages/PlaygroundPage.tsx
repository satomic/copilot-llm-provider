import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import Layout from "@/components/layout/Layout";
import ChatMessage from "@/components/chat/ChatMessage";
import ChatInput from "@/components/chat/ChatInput";
import ModelSelector from "@/components/common/ModelSelector";
import { useModels } from "@/hooks/useModels";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/contexts/I18nContext";
import { chatCompletionStream } from "@/services/api";
import { renderMarkdown } from "@/utils/markdown";
import type { ChatMessage as ChatMessageType } from "@/types/api";

interface DisplayMessage {
  message: ChatMessageType;
  timestamp: Date;
}

// ---------------------------------------------------------------------------
// Compare mode types
// ---------------------------------------------------------------------------

interface CompareColumn {
  modelId: string;
  messages: DisplayMessage[];
  isStreaming: boolean;
  error: string | null;
}

// A small chevron-down SVG used in custom selects
function ChevronDown({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className={className}>
      <path fillRule="evenodd" d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function PlaygroundPage() {
  const { token } = useAuth();
  const { t } = useI18n();
  const { models, loading: modelsLoading, error: modelsError } = useModels();

  // Normal mode state
  const [selectedModel, setSelectedModel] = useState("");
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);

  // Parameters
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(2048);
  const [showParams, setShowParams] = useState(false);

  // Compare mode state
  const [compareMode, setCompareMode] = useState(false);
  const [compareColumns, setCompareColumns] = useState<CompareColumn[]>([]);
  const [sharedInput, setSharedInput] = useState<DisplayMessage[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef(false);
  const compareEndRefs = useRef<Record<number, HTMLDivElement | null>>({});

  // Auto-select first model when models load
  useEffect(() => {
    if (models.length > 0 && !selectedModel) {
      setSelectedModel(models[0].id);
    }
  }, [models, selectedModel]);

  // Auto-scroll in normal mode
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-scroll in compare mode
  useEffect(() => {
    Object.values(compareEndRefs.current).forEach((el) =>
      el?.scrollIntoView({ behavior: "smooth" })
    );
  }, [compareColumns]);

  // Initialize compare columns when entering compare mode
  const handleToggleCompare = useCallback(() => {
    if (!compareMode) {
      // Enter compare mode — start with 2 columns
      const ids = models.slice(0, 2).map((m) => m.id);
      setCompareColumns(
        ids.map((id) => ({ modelId: id, messages: [], isStreaming: false, error: null }))
      );
      setSharedInput([]);
    }
    setCompareMode((prev) => !prev);
  }, [compareMode, models]);

  const addCompareColumn = useCallback(() => {
    const usedIds = new Set(compareColumns.map((c) => c.modelId));
    const next = models.find((m) => !usedIds.has(m.id));
    if (!next) return;
    setCompareColumns((prev) => [
      ...prev,
      { modelId: next.id, messages: [...sharedInput], isStreaming: false, error: null },
    ]);
  }, [compareColumns, models, sharedInput]);

  const removeCompareColumn = useCallback((idx: number) => {
    setCompareColumns((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  const setCompareModel = useCallback((idx: number, modelId: string) => {
    setCompareColumns((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], modelId };
      return next;
    });
  }, []);

  // ===== Normal mode send =====
  const handleSend = useCallback(
    async (content: string) => {
      if (!selectedModel || isStreaming) return;

      setStreamError(null);
      abortRef.current = false;

      const userMsg: DisplayMessage = {
        message: { role: "user", content },
        timestamp: new Date(),
      };

      const newMessages = [...messages, userMsg];
      setMessages(newMessages);

      const assistantMsg: DisplayMessage = {
        message: { role: "assistant", content: "" },
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setIsStreaming(true);

      try {
        const apiMessages = newMessages.map((m) => m.message);

        await chatCompletionStream(
          token,
          {
            model: selectedModel,
            messages: apiMessages,
            temperature,
            max_tokens: maxTokens,
          },
          (chunk) => {
            if (abortRef.current) return;
            const delta = chunk.choices[0]?.delta?.content;
            if (delta) {
              setMessages((prev) => {
                const updated = [...prev];
                const lastIdx = updated.length - 1;
                updated[lastIdx] = {
                  ...updated[lastIdx],
                  message: {
                    ...updated[lastIdx].message,
                    content: updated[lastIdx].message.content + delta,
                  },
                };
                return updated;
              });
            }
          },
          () => {
            setIsStreaming(false);
          }
        );
      } catch (err) {
        setIsStreaming(false);
        const errorMessage = err instanceof Error ? err.message : "An unknown error occurred";
        setStreamError(errorMessage);
        setMessages((prev) => {
          const updated = [...prev];
          if (updated.length > 0 && updated[updated.length - 1].message.content === "") {
            updated.pop();
          }
          return updated;
        });
      }
    },
    [selectedModel, isStreaming, messages, token, temperature, maxTokens]
  );

  // ===== Compare mode send =====
  const handleCompareSend = useCallback(
    async (content: string) => {
      const anyStreaming = compareColumns.some((c) => c.isStreaming);
      if (anyStreaming || compareColumns.length === 0) return;

      const userMsg: DisplayMessage = {
        message: { role: "user", content },
        timestamp: new Date(),
      };

      const newShared = [...sharedInput, userMsg];
      setSharedInput(newShared);

      // Add user message + empty assistant to each column
      setCompareColumns((prev) =>
        prev.map((col) => ({
          ...col,
          messages: [
            ...col.messages,
            userMsg,
            { message: { role: "assistant", content: "" }, timestamp: new Date() },
          ],
          isStreaming: true,
          error: null,
        }))
      );

      // Fire streaming for each column in parallel
      const apiMessages = newShared.map((m) => m.message);

      compareColumns.forEach((col, idx) => {
        chatCompletionStream(
          token,
          {
            model: col.modelId,
            messages: apiMessages,
            temperature,
            max_tokens: maxTokens,
          },
          (chunk) => {
            const delta = chunk.choices[0]?.delta?.content;
            if (delta) {
              setCompareColumns((prev) => {
                const next = [...prev];
                if (!next[idx]) return prev;
                const msgs = [...next[idx].messages];
                const lastIdx = msgs.length - 1;
                msgs[lastIdx] = {
                  ...msgs[lastIdx],
                  message: {
                    ...msgs[lastIdx].message,
                    content: msgs[lastIdx].message.content + delta,
                  },
                };
                next[idx] = { ...next[idx], messages: msgs };
                return next;
              });
            }
          },
          () => {
            setCompareColumns((prev) => {
              const next = [...prev];
              if (!next[idx]) return prev;
              next[idx] = { ...next[idx], isStreaming: false };
              return next;
            });
          }
        ).catch((err) => {
          const errorMessage = err instanceof Error ? err.message : "Unknown error";
          setCompareColumns((prev) => {
            const next = [...prev];
            if (!next[idx]) return prev;
            // Remove empty assistant message on error
            const msgs = [...next[idx].messages];
            if (msgs.length > 0 && msgs[msgs.length - 1].message.content === "") {
              msgs.pop();
            }
            next[idx] = { ...next[idx], isStreaming: false, error: errorMessage, messages: msgs };
            return next;
          });
        });
      });
    },
    [compareColumns, sharedInput, token, temperature, maxTokens]
  );

  const handleClear = useCallback(() => {
    abortRef.current = true;
    if (compareMode) {
      setCompareColumns((prev) =>
        prev.map((col) => ({ ...col, messages: [], isStreaming: false, error: null }))
      );
      setSharedInput([]);
    } else {
      setMessages([]);
      setStreamError(null);
      setIsStreaming(false);
    }
  }, [compareMode]);

  const anyCompareStreaming = useMemo(
    () => compareColumns.some((c) => c.isStreaming),
    [compareColumns]
  );

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <Layout title={t("playground.title")}>
      <div className="flex h-[calc(100vh-3rem)] overflow-hidden">
        {/* Main chat area */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Toolbar */}
          <div className="flex items-center gap-2 px-4 py-2.5 border-b border-edge bg-surface">
            {!compareMode && (
              <div className="w-56">
                <ModelSelector
                  models={models}
                  selectedModel={selectedModel}
                  onSelect={setSelectedModel}
                  loading={modelsLoading}
                  error={modelsError}
                />
              </div>
            )}

            {/* Compare toggle */}
            <button
              onClick={handleToggleCompare}
              className={`px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors ${
                compareMode
                  ? "bg-accent text-white"
                  : "text-fg-secondary hover:text-fg hover:bg-overlay border border-edge"
              }`}
            >
              <span className="flex items-center gap-1.5">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
                  <path d="M15.98 1.804a1 1 0 0 0-1.96 0l-.24 1.192a1 1 0 0 1-.784.785l-1.192.238a1 1 0 0 0 0 1.962l1.192.238a1 1 0 0 1 .785.785l.238 1.192a1 1 0 0 0 1.962 0l.238-1.192a1 1 0 0 1 .785-.785l1.192-.238a1 1 0 0 0 0-1.962l-1.192-.238a1 1 0 0 1-.785-.785l-.238-1.192ZM6.949 5.684a1 1 0 0 0-1.898 0l-.683 2.051a1 1 0 0 1-.633.633l-2.051.683a1 1 0 0 0 0 1.898l2.051.684a1 1 0 0 1 .633.632l.683 2.051a1 1 0 0 0 1.898 0l.683-2.051a1 1 0 0 1 .633-.633l2.051-.683a1 1 0 0 0 0-1.898l-2.051-.683a1 1 0 0 1-.633-.633L6.95 5.684ZM13.949 13.684a1 1 0 0 0-1.898 0l-.184.551a1 1 0 0 1-.632.633l-.551.183a1 1 0 0 0 0 1.898l.551.183a1 1 0 0 1 .633.633l.183.551a1 1 0 0 0 1.898 0l.184-.551a1 1 0 0 1 .632-.633l.551-.183a1 1 0 0 0 0-1.898l-.551-.184a1 1 0 0 1-.633-.632l-.183-.551Z" />
                </svg>
                {t("playground.compareMode")}
              </span>
            </button>

            <button
              onClick={() => setShowParams((prev) => !prev)}
              className={`px-2.5 py-1.5 rounded-md text-xs font-medium lg:hidden ${
                showParams
                  ? "bg-accent/10 text-accent"
                  : "text-fg-secondary hover:text-fg hover:bg-overlay"
              }`}
            >
              {t("playground.params")}
            </button>

            <div className="flex-1" />

            <button
              onClick={handleClear}
              className="text-xs text-fg-secondary hover:text-fg px-2.5 py-1.5 rounded-md
                hover:bg-overlay"
            >
              {t("playground.clearChat")}
            </button>
          </div>

          {/* ============ COMPARE MODE ============ */}
          {compareMode ? (
            <div className="flex-1 flex flex-col min-h-0">
              {/* Model selectors row */}
              <div className="flex items-center gap-2 px-4 py-2 border-b border-edge bg-surface/50 overflow-x-auto">
                {compareColumns.map((col, idx) => (
                  <div key={idx} className="flex items-center gap-1.5 shrink-0">
                    <div className="relative">
                      <select
                        value={col.modelId}
                        onChange={(e) => setCompareModel(idx, e.target.value)}
                        disabled={col.isStreaming}
                        className="bg-canvas border border-edge text-fg rounded-md pl-2.5 pr-7 py-1 text-xs
                          focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent
                          disabled:opacity-50 appearance-none cursor-pointer"
                      >
                        {models.map((m) => (
                          <option key={m.id} value={m.id}>{m.id}</option>
                        ))}
                      </select>
                      <ChevronDown className="pointer-events-none absolute right-1.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-fg-muted" />
                    </div>
                    {compareColumns.length > 2 && (
                      <button
                        onClick={() => removeCompareColumn(idx)}
                        className="text-[10px] text-fg-muted hover:text-danger px-1"
                        title={t("playground.removeModel")}
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
                          <path d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.75.75 0 1 1 1.06 1.06L9.06 8l3.22 3.22a.75.75 0 1 1-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 0 1-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z" />
                        </svg>
                      </button>
                    )}
                    {idx < compareColumns.length - 1 && (
                      <div className="w-px h-5 bg-edge mx-1" />
                    )}
                  </div>
                ))}
                {compareColumns.length < models.length && compareColumns.length < 4 && (
                  <button
                    onClick={addCompareColumn}
                    className="text-xs text-accent hover:text-accent-hover px-2 py-1 rounded-md
                      border border-dashed border-accent/30 hover:border-accent/60 shrink-0"
                  >
                    + {t("playground.addModel")}
                  </button>
                )}
              </div>

              {/* Split panels */}
              <div className="flex-1 flex min-h-0 divide-x divide-edge">
                {compareColumns.map((col, idx) => (
                  <div key={idx} className="flex-1 flex flex-col min-w-0 min-h-0">
                    {/* Column header */}
                    <div className="px-3 py-1.5 border-b border-edge bg-canvas/50 shrink-0">
                      <span className="text-[11px] font-semibold text-fg truncate block">{col.modelId}</span>
                    </div>
                    {/* Messages */}
                    <div className="flex-1 overflow-y-auto p-3 space-y-2">
                      {col.messages.length === 0 ? (
                        <div className="flex items-center justify-center h-full text-xs text-fg-muted">
                          {t("playground.noResponse")}
                        </div>
                      ) : (
                        col.messages.map((msg, mIdx) => {
                          if (msg.message.role === "assistant" && !msg.message.content) return null;
                          const isUser = msg.message.role === "user";
                          return (
                            <div key={mIdx} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
                              <div className="max-w-[90%]">
                                {isUser ? (
                                  <div className="rounded-2xl rounded-br-sm px-3 py-2 text-xs leading-relaxed whitespace-pre-wrap break-words bg-accent text-white">
                                    {msg.message.content}
                                  </div>
                                ) : (
                                  <div
                                    className="rounded-2xl rounded-bl-sm px-3 py-2 text-xs leading-relaxed break-words bg-surface text-fg border border-edge"
                                    dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.message.content) }}
                                  />
                                )}
                              </div>
                            </div>
                          );
                        })
                      )}
                      {col.isStreaming && (
                        <div className="flex items-center gap-1.5 text-fg-muted text-[11px] ml-2">
                          <span className="w-1 h-1 bg-accent rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                          <span className="w-1 h-1 bg-accent rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                          <span className="w-1 h-1 bg-accent rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                        </div>
                      )}
                      {col.error && (
                        <div className="bg-danger/8 border border-danger/20 text-danger text-[11px] rounded-md px-2.5 py-1.5">
                          {col.error}
                        </div>
                      )}
                      <div ref={(el) => { compareEndRefs.current[idx] = el; }} />
                    </div>
                  </div>
                ))}
              </div>

              {/* Shared input */}
              <ChatInput
                onSend={handleCompareSend}
                disabled={anyCompareStreaming || compareColumns.length === 0}
              />
            </div>
          ) : (
            /* ============ NORMAL MODE ============ */
            <>
              {/* Messages area */}
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {messages.length === 0 ? (
                  <div className="flex items-center justify-center h-full">
                    <div className="text-center">
                      <div className="w-12 h-12 rounded-lg bg-overlay border border-edge flex items-center justify-center mx-auto mb-3">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-6 h-6 text-fg-muted">
                          <path fillRule="evenodd" d="M10 3c-4.31 0-8 3.033-8 7 0 2.024.978 3.825 2.499 5.085a3.478 3.478 0 0 1-.522 1.756.75.75 0 0 0 .584 1.143 5.976 5.976 0 0 0 3.243-1.053c.7.196 1.44.302 2.196.302 4.31 0 8-3.033 8-7s-3.69-7-8-7Z" clipRule="evenodd" />
                        </svg>
                      </div>
                      <h3 className="text-fg-secondary text-sm font-medium mb-0.5">{t("playground.startConvo")}</h3>
                      <p className="text-fg-muted text-xs">
                        {t("playground.startConvoDesc")}
                      </p>
                    </div>
                  </div>
                ) : (
                  <>
                    {messages.map((msg, idx) =>
                      msg.message.role === "assistant" && !msg.message.content ? null : (
                        <ChatMessage
                          key={idx}
                          message={msg.message}
                          timestamp={msg.timestamp}
                        />
                      )
                    )}
                    {isStreaming && (
                      <div className="flex items-center gap-2 text-fg-muted text-xs ml-4 mb-3">
                        <div className="flex gap-1">
                          <span className="w-1.5 h-1.5 bg-accent rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                          <span className="w-1.5 h-1.5 bg-accent rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                          <span className="w-1.5 h-1.5 bg-accent rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                        </div>
                        {t("playground.streaming")}
                      </div>
                    )}
                    <div ref={messagesEndRef} />
                  </>
                )}

                {streamError && (
                  <div className="mx-4 mb-3 bg-danger/8 border border-danger/20 text-danger text-xs rounded-md px-3 py-2.5">
                    {streamError}
                  </div>
                )}
              </div>

              {/* Input area */}
              <ChatInput onSend={handleSend} disabled={isStreaming || !selectedModel} />
            </>
          )}
        </div>

        {/* Parameters sidebar */}
        <div
          className={`w-64 bg-surface border-l border-edge flex-shrink-0 overflow-y-auto p-4 space-y-5
            ${showParams ? "block" : "hidden"} lg:block`}
        >
          <h3 className="text-[11px] font-semibold text-fg-muted uppercase tracking-wider">
            {t("playground.params")}
          </h3>

          {/* Temperature */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs text-fg-secondary">{t("playground.temperature")}</label>
              <span className="text-xs text-fg font-mono">{temperature.toFixed(1)}</span>
            </div>
            <input
              type="range"
              min="0"
              max="2"
              step="0.1"
              value={temperature}
              onChange={(e) => setTemperature(parseFloat(e.target.value))}
              className="w-full h-1 bg-overlay rounded-full appearance-none cursor-pointer
                [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5
                [&::-webkit-slider-thumb]:h-3.5 [&::-webkit-slider-thumb]:bg-accent
                [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer
                [&::-webkit-slider-thumb]:hover:bg-accent-hover"
            />
            <div className="flex justify-between text-[10px] text-fg-muted mt-1">
              <span>{t("playground.precise")}</span>
              <span>{t("playground.creative")}</span>
            </div>
          </div>

          {/* Max tokens */}
          <div>
            <label className="text-xs text-fg-secondary block mb-1.5">{t("playground.maxTokens")}</label>
            <input
              type="number"
              min="1"
              max="128000"
              value={maxTokens}
              onChange={(e) => {
                const val = parseInt(e.target.value, 10);
                if (!isNaN(val) && val > 0) setMaxTokens(val);
              }}
              className="w-full bg-canvas border border-edge text-fg rounded-md px-3 py-1.5
                text-xs focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent"
            />
          </div>

          {/* Model info */}
          {!compareMode && (
            <div>
              <h4 className="text-[11px] text-fg-muted uppercase tracking-wide mb-1.5">{t("playground.currentModel")}</h4>
              <div className="bg-overlay border border-edge rounded-md px-3 py-1.5 text-xs text-fg truncate">
                {selectedModel || t("playground.noneSelected")}
              </div>
            </div>
          )}

          {/* Message count */}
          <div>
            <h4 className="text-[11px] text-fg-muted uppercase tracking-wide mb-1.5">{t("playground.messages")}</h4>
            <div className="text-xs text-fg-secondary">
              {compareMode ? sharedInput.length : messages.length} {t("playground.messagesInContext")}
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}
