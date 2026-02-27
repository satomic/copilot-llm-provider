import { useState, useRef, useEffect, useCallback } from "react";
import Layout from "@/components/layout/Layout";
import ChatMessage from "@/components/chat/ChatMessage";
import ChatInput from "@/components/chat/ChatInput";
import ModelSelector from "@/components/common/ModelSelector";
import { useModels } from "@/hooks/useModels";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/contexts/I18nContext";
import { chatCompletionStream } from "@/services/api";
import type { ChatMessage as ChatMessageType } from "@/types/api";

interface DisplayMessage {
  message: ChatMessageType;
  timestamp: Date;
}

/**
 * Interactive chat playground with streaming support.
 * Supports model selection, parameter tuning, and real-time token display.
 */
export default function PlaygroundPage() {
  const { apiKey } = useAuth();
  const { t } = useI18n();
  const { models, loading: modelsLoading, error: modelsError } = useModels();

  const [selectedModel, setSelectedModel] = useState("");
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);

  // Parameters
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(2048);
  const [showParams, setShowParams] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef(false);

  // Auto-select first model when models load
  useEffect(() => {
    if (models.length > 0 && !selectedModel) {
      setSelectedModel(models[0].id);
    }
  }, [models, selectedModel]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = useCallback(
    async (content: string) => {
      if (!selectedModel || isStreaming) return;

      setStreamError(null);
      abortRef.current = false;

      // Add user message
      const userMsg: DisplayMessage = {
        message: { role: "user", content },
        timestamp: new Date(),
      };

      // Prepare conversation history for the API
      const newMessages = [...messages, userMsg];
      setMessages(newMessages);

      // Add empty assistant message that will be streamed into
      const assistantMsg: DisplayMessage = {
        message: { role: "assistant", content: "" },
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setIsStreaming(true);

      try {
        const apiMessages = newMessages.map((m) => m.message);

        await chatCompletionStream(
          apiKey,
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
        // Remove the empty assistant message on error
        setMessages((prev) => {
          const updated = [...prev];
          if (updated.length > 0 && updated[updated.length - 1].message.content === "") {
            updated.pop();
          }
          return updated;
        });
      }
    },
    [selectedModel, isStreaming, messages, apiKey, temperature, maxTokens]
  );

  const handleClear = useCallback(() => {
    abortRef.current = true;
    setMessages([]);
    setStreamError(null);
    setIsStreaming(false);
  }, []);

  return (
    <Layout title={t("playground.title")}>
      <div className="flex h-[calc(100vh-3rem)] overflow-hidden">
        {/* Main chat area */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Toolbar */}
          <div className="flex items-center gap-2 px-4 py-2.5 border-b border-edge bg-surface">
            <div className="w-56">
              <ModelSelector
                models={models}
                selectedModel={selectedModel}
                onSelect={setSelectedModel}
                loading={modelsLoading}
                error={modelsError}
              />
            </div>

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

          {/* Messages area */}
          <div className="flex-1 overflow-y-auto p-4">
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
                {messages.map((msg, idx) => (
                  <ChatMessage
                    key={idx}
                    message={msg.message}
                    timestamp={msg.timestamp}
                  />
                ))}
                {/* Streaming indicator */}
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

            {/* Error display */}
            {streamError && (
              <div className="mx-4 mb-3 bg-danger/8 border border-danger/20 text-danger text-xs rounded-md px-3 py-2.5">
                {streamError}
              </div>
            )}
          </div>

          {/* Input area */}
          <ChatInput onSend={handleSend} disabled={isStreaming || !selectedModel} />
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
          <div>
            <h4 className="text-[11px] text-fg-muted uppercase tracking-wide mb-1.5">{t("playground.currentModel")}</h4>
            <div className="bg-overlay border border-edge rounded-md px-3 py-1.5 text-xs text-fg truncate">
              {selectedModel || t("playground.noneSelected")}
            </div>
          </div>

          {/* Message count */}
          <div>
            <h4 className="text-[11px] text-fg-muted uppercase tracking-wide mb-1.5">{t("playground.messages")}</h4>
            <div className="text-xs text-fg-secondary">{messages.length} {t("playground.messagesInContext")}</div>
          </div>
        </div>
      </div>
    </Layout>
  );
}
