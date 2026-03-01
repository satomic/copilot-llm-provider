import { useState, useEffect, useCallback, useRef } from "react";
import Layout from "@/components/layout/Layout";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/contexts/I18nContext";
import { renderMarkdown } from "@/utils/markdown";

interface SessionSummary {
  id: string;
  timestamp: number;
  model: string;
  api_format: string;
  stream: boolean;
  duration_ms: number;
  status: string;
  message_count: number;
  response_preview: string;
  api_key_alias?: string | null;
  github_token_alias?: string | null;
  first_message?: string;
}

interface SessionDetail {
  id: string;
  timestamp: number;
  model: string;
  api_format: string;
  messages: { role: string; content: string }[];
  response_content: string;
  stream: boolean;
  duration_ms: number;
  status: string;
  error_message?: string;
  client_ip?: string;
}

interface FilterOptions {
  models: string[];
  aliases: string[];
  token_aliases: string[];
}

function authHeaders(token: string): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

export default function SessionsPage() {
  const { token } = useAuth();
  const { t } = useI18n();

  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [offset, setOffset] = useState(0);
  const [selectedSession, setSelectedSession] = useState<SessionDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const limit = 20;

  // Filters
  const [filterOptions, setFilterOptions] = useState<FilterOptions>({ models: [], aliases: [], token_aliases: [] });
  const [filterModel, setFilterModel] = useState<string>("");
  const [filterAlias, setFilterAlias] = useState<string>("");
  const [filterToken, setFilterToken] = useState<string>("");

  // Continue-chat state
  const [chatInput, setChatInput] = useState("");
  const [sending, setSending] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [extraMessages, setExtraMessages] = useState<{ role: string; content: string }[]>([]);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Selection state for batch operations
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [selectMode, setSelectMode] = useState(false);
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(null);
  const [confirmingBatch, setConfirmingBatch] = useState(false);

  // Resizable panel width
  const [listWidth, setListWidth] = useState(440);
  const isDragging = useRef(false);
  const startX = useRef(0);
  const startWidth = useRef(0);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    isDragging.current = true;
    startX.current = e.clientX;
    startWidth.current = listWidth;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, [listWidth]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging.current) return;
      const delta = e.clientX - startX.current;
      const newWidth = Math.max(240, Math.min(600, startWidth.current + delta));
      setListWidth(newWidth);
    };
    const handleMouseUp = () => {
      isDragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, []);

  // Fetch filter options on mount
  useEffect(() => {
    fetch("/api/sessions/filter-options", { headers: authHeaders(token) })
      .then((r) => r.json())
      .then((data) => setFilterOptions(data))
      .catch(() => {});
  }, [token]);

  const fetchSessions = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
    });
    if (filterModel) params.set("model", filterModel);
    if (filterAlias) params.set("api_key_alias", filterAlias);
    if (filterToken) params.set("github_token_alias", filterToken);

    fetch(`/api/sessions?${params}`, {
      headers: authHeaders(token),
    })
      .then((r) => r.json())
      .then((data) => {
        setSessions(data.sessions || []);
        setTotal(data.total || 0);
      })
      .catch(() => setSessions([]))
      .finally(() => setLoading(false));
  }, [token, offset, filterModel, filterAlias, filterToken]);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  // Reset offset when filters change
  useEffect(() => {
    setOffset(0);
  }, [filterModel, filterAlias, filterToken]);

  const viewSession = useCallback(
    (id: string) => {
      setDetailLoading(true);
      setExtraMessages([]);
      setStreamingContent("");
      setChatInput("");
      fetch(`/api/sessions/${id}`, { headers: authHeaders(token) })
        .then((r) => r.json())
        .then((data) => setSelectedSession(data))
        .catch(() => setSelectedSession(null))
        .finally(() => setDetailLoading(false));
    },
    [token]
  );

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [extraMessages, streamingContent, selectedSession]);

  const handleSendMessage = useCallback(async () => {
    if (!chatInput.trim() || !selectedSession || sending) return;

    const userMsg = chatInput.trim();
    setChatInput("");
    setSending(true);
    setStreamingContent("");

    setExtraMessages((prev) => [...prev, { role: "user", content: userMsg }]);

    const sessionId = selectedSession.id;

    try {
      const response = await fetch(`/api/sessions/${sessionId}/continue`, {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({ message: userMsg }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";
      let fullContent = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed === "") continue;

          if (trimmed.startsWith("event: session_id")) {
            continue;
          }

          if (trimmed.startsWith("data: ")) {
            const payload = trimmed.slice(6);
            if (payload === "[DONE]") continue;
            fullContent += payload;
            setStreamingContent(fullContent);
          }
        }
      }

      setStreamingContent("");
      setExtraMessages([]);
      const updated = await fetch(`/api/sessions/${sessionId}`, {
        headers: authHeaders(token),
      }).then((r) => r.json());
      setSelectedSession(updated);
      fetchSessions();
    } catch (err) {
      setExtraMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${err instanceof Error ? err.message : "Unknown error"}` },
      ]);
    } finally {
      setSending(false);
    }
  }, [chatInput, selectedSession, sending, token, fetchSessions]);

  const toggleSelectAll = useCallback(() => {
    if (selectedIds.size === sessions.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(sessions.map((s) => s.id)));
    }
  }, [sessions, selectedIds.size]);

  const handleDeleteSingle = useCallback(
    async (id: string, e: React.MouseEvent) => {
      e.stopPropagation();
      if (confirmingDeleteId !== id) {
        setConfirmingDeleteId(id);
        return;
      }
      setConfirmingDeleteId(null);
      try {
        await fetch(`/api/sessions/${id}`, {
          method: "DELETE",
          headers: authHeaders(token),
        });
        if (selectedSession?.id === id) setSelectedSession(null);
        setSelectedIds((prev) => {
          const next = new Set(prev);
          next.delete(id);
          return next;
        });
        fetchSessions();
      } catch { /* ignore */ }
    },
    [token, selectedSession, fetchSessions, confirmingDeleteId]
  );

  const handleDeleteBatch = useCallback(async () => {
    if (selectedIds.size === 0) return;
    if (!confirmingBatch) {
      setConfirmingBatch(true);
      return;
    }
    setConfirmingBatch(false);
    try {
      await fetch("/api/sessions/batch-delete", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({ ids: Array.from(selectedIds) }),
      });
      if (selectedSession && selectedIds.has(selectedSession.id)) {
        setSelectedSession(null);
      }
      setSelectedIds(new Set());
      setSelectMode(false);
      fetchSessions();
    } catch { /* ignore */ }
  }, [selectedIds, token, selectedSession, fetchSessions, confirmingBatch]);

  const formatTime = (ts: number) => {
    const d = new Date(ts * 1000);
    return d.toLocaleString();
  };

  const buildConversation = (): { role: string; content: string }[] => {
    if (!selectedSession) return [];
    const msgs = [...selectedSession.messages];
    if (selectedSession.response_content) {
      msgs.push({ role: "assistant", content: selectedSession.response_content });
    }
    return [...msgs, ...extraMessages];
  };

  const conversation = buildConversation();

  // Build session title: "[token] alias: first_message"
  const sessionTitle = (s: SessionSummary): string => {
    const parts: string[] = [];
    if (s.github_token_alias) parts.push(`[${s.github_token_alias}]`);
    if (s.api_key_alias) parts.push(`${s.api_key_alias}:`);
    const msg = s.first_message || s.response_preview || "...";
    parts.push(msg);
    return parts.join(" ");
  };

  return (
    <Layout title={t("sessions.title")}>
      <div className="flex h-[calc(100vh-3rem)] overflow-hidden">
        {/* Session list — resizable */}
        <div
          className="border-r border-edge flex flex-col shrink-0"
          style={{ width: `${listWidth}px` }}
        >
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-edge bg-surface">
            <h3 className="text-sm font-semibold text-fg">{t("sessions.records")}</h3>
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  setSelectMode((prev) => !prev);
                  if (selectMode) setSelectedIds(new Set());
                }}
                className={`text-xs px-1.5 py-0.5 rounded ${
                  selectMode
                    ? "bg-accent/10 text-accent"
                    : "text-fg-muted hover:text-fg"
                }`}
                title={selectMode ? t("sessions.deselectAll") : "Select"}
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
                  <path d="M3.5 2A1.5 1.5 0 0 0 2 3.5v9A1.5 1.5 0 0 0 3.5 14h9a1.5 1.5 0 0 0 1.5-1.5v-9A1.5 1.5 0 0 0 12.5 2h-9ZM6.75 5.22a.75.75 0 0 1 1.06 0l2.22 2.22a.75.75 0 0 1 0 1.06l-2.22 2.22a.75.75 0 0 1-1.06-1.06L8.44 8 6.75 6.28a.75.75 0 0 1 0-1.06Z" />
                </svg>
              </button>
              <button
                onClick={fetchSessions}
                className="text-xs text-accent hover:text-accent-hover"
              >
                {t("dashboard.refresh")}
              </button>
            </div>
          </div>

          {/* Filters */}
          {(filterOptions.models.length > 0 || filterOptions.aliases.length > 0 || filterOptions.token_aliases.length > 0) && (
            <div className="flex items-center gap-2 px-4 py-2 border-b border-edge bg-surface/50">
              {filterOptions.models.length > 0 && (
                <div className="relative flex-1 min-w-0">
                  <select
                    value={filterModel}
                    onChange={(e) => setFilterModel(e.target.value)}
                    className="w-full text-[11px] bg-canvas border border-edge rounded-md pl-2 pr-6 py-1 text-fg
                      focus:outline-none focus:ring-1 focus:ring-accent appearance-none cursor-pointer truncate"
                  >
                    <option value="">{t("sessions.filterModel")}: {t("sessions.filterAll")}</option>
                    {filterOptions.models.map((m) => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"
                    className="pointer-events-none absolute right-1.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-fg-muted">
                    <path fillRule="evenodd" d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
                  </svg>
                </div>
              )}
              {filterOptions.aliases.length > 0 && (
                <div className="relative flex-1 min-w-0">
                  <select
                    value={filterAlias}
                    onChange={(e) => setFilterAlias(e.target.value)}
                    className="w-full text-[11px] bg-canvas border border-edge rounded-md pl-2 pr-6 py-1 text-fg
                      focus:outline-none focus:ring-1 focus:ring-accent appearance-none cursor-pointer truncate"
                  >
                    <option value="">{t("sessions.filterAlias")}: {t("sessions.filterAll")}</option>
                    {filterOptions.aliases.map((a) => (
                      <option key={a} value={a}>{a}</option>
                    ))}
                  </select>
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"
                    className="pointer-events-none absolute right-1.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-fg-muted">
                    <path fillRule="evenodd" d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
                  </svg>
                </div>
              )}
              {filterOptions.token_aliases.length > 0 && (
                <div className="relative flex-1 min-w-0">
                  <select
                    value={filterToken}
                    onChange={(e) => setFilterToken(e.target.value)}
                    className="w-full text-[11px] bg-canvas border border-edge rounded-md pl-2 pr-6 py-1 text-fg
                      focus:outline-none focus:ring-1 focus:ring-accent appearance-none cursor-pointer truncate"
                  >
                    <option value="">{t("sessions.filterToken")}: {t("sessions.filterAll")}</option>
                    {filterOptions.token_aliases.map((ta) => (
                      <option key={ta} value={ta}>{ta}</option>
                    ))}
                  </select>
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"
                    className="pointer-events-none absolute right-1.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-fg-muted">
                    <path fillRule="evenodd" d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
                  </svg>
                </div>
              )}
            </div>
          )}

          {/* Batch action bar */}
          {selectMode && (
            <div className="flex items-center gap-2 px-4 py-1.5 border-b border-edge bg-accent/5">
              <button
                onClick={toggleSelectAll}
                className="text-[11px] text-accent hover:text-accent-hover"
              >
                {selectedIds.size === sessions.length ? t("sessions.deselectAll") : t("sessions.selectAll")}
              </button>
              <span className="text-[11px] text-fg-muted flex-1">
                {selectedIds.size} {t("sessions.selected")}
              </span>
              {confirmingBatch ? (
                <button
                  onClick={handleDeleteBatch}
                  onMouseLeave={() => setConfirmingBatch(false)}
                  className="text-[11px] px-2 py-0.5 rounded-md bg-danger text-white font-medium hover:bg-danger/90"
                >
                  {t("sessions.delete")}? ({selectedIds.size})
                </button>
              ) : (
                <button
                  onClick={handleDeleteBatch}
                  disabled={selectedIds.size === 0}
                  className="text-[11px] text-danger hover:text-danger/80 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {t("sessions.deleteSelected")} ({selectedIds.size})
                </button>
              )}
            </div>
          )}

          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center py-12 text-xs text-fg-muted">
                {t("sessions.loading")}
              </div>
            ) : sessions.length === 0 ? (
              <div className="flex items-center justify-center py-12 text-xs text-fg-muted">
                {t("sessions.noSessions")}
              </div>
            ) : (
              sessions.map((s) => (
                <div
                  key={s.id}
                  className={`group relative w-full text-left px-4 py-3 border-b border-edge hover:bg-overlay/50 transition-colors cursor-pointer ${
                    selectedSession?.id === s.id ? "bg-accent/5" : ""
                  } ${selectedIds.has(s.id) ? "bg-accent/8" : ""}`}
                  onClick={() => {
                    if (selectMode) {
                      setSelectedIds((prev) => {
                        const next = new Set(prev);
                        if (next.has(s.id)) next.delete(s.id);
                        else next.add(s.id);
                        return next;
                      });
                    } else {
                      viewSession(s.id);
                    }
                  }}
                >
                  <div className="flex items-center gap-2">
                    {selectMode && (
                      <input
                        type="checkbox"
                        checked={selectedIds.has(s.id)}
                        onChange={() => {}}
                        className="w-3.5 h-3.5 rounded border-edge text-accent shrink-0 cursor-pointer"
                      />
                    )}
                    <div className="flex-1 min-w-0">
                      {/* Title line: alias: first_message  model */}
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-[13px] font-medium text-fg truncate flex-1 min-w-0">
                          {sessionTitle(s)}
                        </span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent/8 text-accent/70 font-medium shrink-0">
                          {s.model}
                        </span>
                        <span
                          className={`text-[10px] px-1.5 py-0.5 rounded-full shrink-0 ${
                            s.status === "ok"
                              ? "bg-success/10 text-success"
                              : "bg-danger/10 text-danger"
                          }`}
                        >
                          {s.status}
                        </span>
                      </div>
                      {/* Meta line */}
                      <div className="flex items-center gap-2 text-[11px] text-fg-muted">
                        <span>{formatTime(s.timestamp)}</span>
                        <span className="text-edge">|</span>
                        <span>{s.api_format}</span>
                        <span className="text-edge">|</span>
                        <span>{s.message_count} msgs</span>
                        <span className="text-edge">|</span>
                        <span>{Math.round(s.duration_ms)}ms</span>
                      </div>
                    </div>
                  </div>

                  {/* Hover delete button */}
                  {!selectMode && (
                    confirmingDeleteId === s.id ? (
                      <button
                        onClick={(e) => handleDeleteSingle(s.id, e)}
                        onMouseLeave={() => setConfirmingDeleteId(null)}
                        className="absolute top-2 right-2 px-2 py-0.5 rounded-md text-[10px] font-medium
                          bg-danger text-white hover:bg-danger/90 transition-colors"
                      >
                        {t("sessions.delete")}?
                      </button>
                    ) : (
                      <button
                        onClick={(e) => handleDeleteSingle(s.id, e)}
                        className="absolute top-2 right-2 p-1 rounded-md
                          opacity-0 group-hover:opacity-100 transition-opacity
                          text-fg-muted hover:text-danger hover:bg-danger/10"
                        title={t("sessions.delete")}
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
                          <path fillRule="evenodd" d="M5 3.25V4H2.75a.75.75 0 0 0 0 1.5h.3l.815 8.15A1.5 1.5 0 0 0 5.357 15h5.285a1.5 1.5 0 0 0 1.493-1.35l.815-8.15h.3a.75.75 0 0 0 0-1.5H11v-.75A2.25 2.25 0 0 0 8.75 1h-1.5A2.25 2.25 0 0 0 5 3.25Zm2.25-.75a.75.75 0 0 0-.75.75V4h3v-.75a.75.75 0 0 0-.75-.75h-1.5ZM6.05 6a.75.75 0 0 1 .787.713l.275 5.5a.75.75 0 0 1-1.498.075l-.275-5.5A.75.75 0 0 1 6.05 6Zm3.9 0a.75.75 0 0 1 .712.787l-.275 5.5a.75.75 0 0 1-1.498-.075l.275-5.5A.75.75 0 0 1 9.95 6Z" clipRule="evenodd" />
                        </svg>
                      </button>
                    )
                  )}
                </div>
              ))
            )}
          </div>

          {/* Pagination */}
          {total > limit && (
            <div className="flex items-center justify-between px-4 py-2 border-t border-edge bg-surface">
              <button
                onClick={() => setOffset(Math.max(0, offset - limit))}
                disabled={offset === 0}
                className="text-xs text-accent disabled:text-fg-muted disabled:cursor-not-allowed"
              >
                {t("sessions.prev")}
              </button>
              <span className="text-[11px] text-fg-muted">
                {offset + 1}-{Math.min(offset + limit, total)} / {total}
              </span>
              <button
                onClick={() => setOffset(offset + limit)}
                disabled={offset + limit >= total}
                className="text-xs text-accent disabled:text-fg-muted disabled:cursor-not-allowed"
              >
                {t("sessions.next")}
              </button>
            </div>
          )}
        </div>

        {/* Drag handle for resizing */}
        <div
          className="w-1 cursor-col-resize hover:bg-accent/30 active:bg-accent/50 transition-colors shrink-0"
          onMouseDown={handleMouseDown}
        />

        {/* Session detail */}
        {detailLoading ? (
          <div className="flex-1 flex items-center justify-center text-xs text-fg-muted">
            {t("sessions.loading")}
          </div>
        ) : !selectedSession ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <div className="w-12 h-12 rounded-lg bg-overlay border border-edge flex items-center justify-center mx-auto mb-3">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-6 h-6 text-fg-muted">
                  <path fillRule="evenodd" d="M4.5 2A1.5 1.5 0 003 3.5v13A1.5 1.5 0 004.5 18h11a1.5 1.5 0 001.5-1.5V7.621a1.5 1.5 0 00-.44-1.06l-4.12-4.122A1.5 1.5 0 0011.378 2H4.5z" clipRule="evenodd" />
                </svg>
              </div>
              <p className="text-fg-muted text-xs">{t("sessions.selectSession")}</p>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex min-w-0">
            {/* Left: Conversation panel */}
            <div className="flex-1 flex flex-col min-w-0">
              {/* Metadata bar */}
              <div className="px-4 py-2.5 border-b border-edge bg-surface shrink-0">
                <div className="flex items-center flex-wrap gap-x-3 gap-y-1 text-xs">
                  <span className="font-semibold text-fg">{selectedSession.model}</span>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                      selectedSession.status === "ok"
                        ? "bg-success/10 text-success"
                        : "bg-danger/10 text-danger"
                    }`}
                  >
                    {selectedSession.status}
                  </span>
                  <span className="text-fg-muted">{formatTime(selectedSession.timestamp)}</span>
                  <span className="text-fg-muted">{Math.round(selectedSession.duration_ms)}ms</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-overlay text-fg-muted font-medium">
                    {selectedSession.api_format}
                  </span>
                  {selectedSession.stream && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent/8 text-accent/70 font-medium">
                      stream
                    </span>
                  )}
                  <span className="text-fg-muted/50 font-mono text-[10px] ml-auto">{selectedSession.id}</span>
                </div>
                {selectedSession.error_message && (
                  <div className="mt-1.5 bg-danger/8 border border-danger/20 text-danger text-xs rounded-md px-3 py-1.5">
                    {selectedSession.error_message}
                  </div>
                )}
              </div>

              {/* Chat messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {conversation.map((msg, idx) => {
                  if (msg.role === "system") {
                    return (
                      <div key={`msg-${idx}`} className="flex justify-center">
                        <div className="max-w-[90%] rounded-lg px-3 py-2 bg-canvas border border-edge/60">
                          <div className="flex items-center gap-1.5 mb-1">
                            <span className="w-4 h-4 rounded-full bg-fg-muted/15 flex items-center justify-center">
                              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="w-2.5 h-2.5 text-fg-muted">
                                <path fillRule="evenodd" d="M6.955 1.45A.5.5 0 0 1 7.452 1h1.096a.5.5 0 0 1 .497.45l.17 1.699c.484.12.94.312 1.356.562l1.321-.916a.5.5 0 0 1 .67.033l.774.775a.5.5 0 0 1 .034.67l-.916 1.32c.25.417.443.873.563 1.357l1.699.17a.5.5 0 0 1 .45.497v1.096a.5.5 0 0 1-.45.497l-1.699.17c-.12.484-.312.94-.562 1.356l.916 1.321a.5.5 0 0 1-.034.67l-.774.774a.5.5 0 0 1-.67.033l-1.32-.916c-.417.25-.874.443-1.357.563l-.17 1.699a.5.5 0 0 1-.497.45H7.452a.5.5 0 0 1-.497-.45l-.17-1.699a4.973 4.973 0 0 1-1.356-.562l-1.321.916a.5.5 0 0 1-.67-.034l-.774-.774a.5.5 0 0 1-.034-.67l.916-1.32a4.971 4.971 0 0 1-.562-1.357l-1.699-.17A.5.5 0 0 1 1 8.548V7.452a.5.5 0 0 1 .45-.497l1.699-.17c.12-.484.312-.94.562-1.356L2.795 4.108a.5.5 0 0 1 .034-.67l.774-.774a.5.5 0 0 1 .67-.033l1.32.916c.417-.25.874-.443 1.357-.563l.17-1.699ZM8 10.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z" clipRule="evenodd" />
                              </svg>
                            </span>
                            <span className="text-[10px] font-medium text-fg-muted uppercase tracking-wider">System</span>
                          </div>
                          <div className="text-[11px] text-fg-muted leading-relaxed whitespace-pre-wrap break-words max-h-32 overflow-y-auto">
                            {msg.content}
                          </div>
                        </div>
                      </div>
                    );
                  }

                  const isUser = msg.role === "user";
                  return (
                    <div
                      key={`msg-${idx}`}
                      className={`flex ${isUser ? "justify-end" : "justify-start"}`}
                    >
                      <div className="max-w-[80%]">
                        <div className={`flex items-center gap-1.5 mb-1 ${isUser ? "justify-end" : "justify-start"}`}>
                          <span className="text-[10px] font-medium text-fg-muted uppercase tracking-wider">
                            {msg.role}
                          </span>
                        </div>
                        {isUser ? (
                          <div className="rounded-2xl rounded-br-sm px-3.5 py-2.5 text-xs leading-relaxed whitespace-pre-wrap break-words bg-accent text-white">
                            {msg.content}
                          </div>
                        ) : (
                          <div
                            className="rounded-2xl rounded-bl-sm px-3.5 py-2.5 text-xs leading-relaxed break-words bg-surface text-fg border border-edge"
                            dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }}
                          />
                        )}
                      </div>
                    </div>
                  );
                })}

                {/* Streaming content */}
                {streamingContent && (
                  <div className="flex justify-start">
                    <div className="max-w-[80%]">
                      <div className="flex items-center gap-1.5 mb-1">
                        <span className="text-[10px] font-medium text-fg-muted uppercase tracking-wider">assistant</span>
                      </div>
                      <div
                        className="rounded-2xl rounded-bl-sm px-3.5 py-2.5 bg-surface text-xs text-fg leading-relaxed border border-edge break-words"
                        dangerouslySetInnerHTML={{ __html: renderMarkdown(streamingContent) }}
                      />
                    </div>
                  </div>
                )}

                {/* Streaming indicator */}
                {sending && (
                  <div className="flex items-center gap-2 text-fg-muted text-xs ml-4 mb-3">
                    <div className="flex gap-1">
                      <span className="w-1.5 h-1.5 bg-accent rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                      <span className="w-1.5 h-1.5 bg-accent rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                      <span className="w-1.5 h-1.5 bg-accent rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                    </div>
                    {t("playground.streaming")}
                  </div>
                )}

                <div ref={chatEndRef} />
              </div>

              {/* Chat input */}
              <div className="flex items-end gap-2 p-3 border-t border-edge bg-surface shrink-0">
                <textarea
                  ref={textareaRef}
                  value={chatInput}
                  onChange={(e) => {
                    setChatInput(e.target.value);
                    const el = textareaRef.current;
                    if (el) {
                      el.style.height = "auto";
                      el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
                    }
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage();
                    }
                  }}
                  placeholder={t("sessions.inputPlaceholder")}
                  disabled={sending}
                  rows={1}
                  className="flex-1 bg-canvas border border-edge text-fg rounded-md px-3 py-2 text-[13px]
                    placeholder-fg-muted focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent
                    disabled:opacity-50 disabled:cursor-not-allowed
                    min-h-[40px] max-h-[200px] overflow-y-auto leading-relaxed resize-none"
                />
                <button
                  onClick={handleSendMessage}
                  disabled={!chatInput.trim() || sending}
                  className="bg-accent hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed
                    text-white rounded-md px-4 py-2 font-medium text-xs
                    flex items-center gap-1.5 shrink-0"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    className="w-3.5 h-3.5"
                  >
                    <path d="M3.105 2.288a.75.75 0 0 0-.826.95l1.414 4.926A1.5 1.5 0 0 0 5.135 9.25h6.115a.75.75 0 0 1 0 1.5H5.135a1.5 1.5 0 0 0-1.442 1.086l-1.414 4.926a.75.75 0 0 0 .826.95 28.897 28.897 0 0 0 15.293-7.155.75.75 0 0 0 0-1.114A28.897 28.897 0 0 0 3.105 2.288Z" />
                  </svg>
                  {t("playground.send")}
                </button>
              </div>
            </div>

            {/* Right: JSON view panel */}
            <div className="w-96 border-l border-edge flex flex-col shrink-0 bg-surface">
              <div className="px-4 py-2.5 border-b border-edge">
                <h3 className="text-sm font-semibold text-fg">JSON</h3>
              </div>
              <div className="flex-1 overflow-auto p-3">
                <pre className="text-[11px] leading-relaxed text-fg-secondary font-mono whitespace-pre-wrap break-all">
                  {JSON.stringify(selectedSession, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}
