import type { ChatMessage as ChatMessageType } from "@/types/api";
import { useI18n } from "@/contexts/I18nContext";

interface ChatMessageProps {
  message: ChatMessageType;
  timestamp?: Date;
}

/**
 * Renders basic markdown-like formatting for assistant messages:
 * - Code blocks (```...```)
 * - Inline code (`...`)
 * - Bold (**...**)
 * - Line breaks
 */
function renderContent(content: string): string {
  let html = content;

  // Escape HTML entities first
  html = html
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Fenced code blocks: ```lang\n...\n```
  html = html.replace(
    /```(\w*)\n([\s\S]*?)```/g,
    '<pre class="bg-canvas border border-edge rounded-md p-3 my-2 overflow-x-auto text-[13px]"><code>$2</code></pre>'
  );

  // Inline code: `...`
  html = html.replace(
    /`([^`]+)`/g,
    '<code class="bg-canvas px-1 py-0.5 rounded text-[13px] text-accent">$1</code>'
  );

  // Bold: **...**
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

  // Line breaks
  html = html.replace(/\n/g, "<br />");

  return html;
}

/**
 * A single chat message bubble.
 * User messages use accent-tinted bg, assistant messages use overlay bg.
 */
export default function ChatMessage({ message, timestamp }: ChatMessageProps) {
  const isUser = message.role === "user";
  const { t } = useI18n();

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3`}>
      <div
        className={`max-w-[85%] rounded-lg px-4 py-3 border ${
          isUser
            ? "bg-accent/8 border-accent/20 text-fg"
            : "bg-overlay border-edge text-fg"
        }`}
      >
        {/* Role label */}
        <div
          className={`text-[11px] font-medium mb-1 uppercase tracking-wide ${
            isUser ? "text-accent" : "text-fg-muted"
          }`}
        >
          {isUser ? t("chat.you") : t("chat.assistant")}
        </div>

        {/* Message content */}
        {isUser ? (
          <div className="text-[13px] whitespace-pre-wrap break-words leading-relaxed">{message.content}</div>
        ) : (
          <div
            className="text-[13px] break-words leading-relaxed"
            dangerouslySetInnerHTML={{ __html: renderContent(message.content) }}
          />
        )}

        {/* Timestamp */}
        {timestamp && (
          <div className="text-[11px] mt-2 text-fg-muted">
            {timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </div>
        )}
      </div>
    </div>
  );
}
