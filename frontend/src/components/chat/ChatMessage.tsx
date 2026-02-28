import type { ChatMessage as ChatMessageType } from "@/types/api";
import { useI18n } from "@/contexts/I18nContext";
import { renderMarkdown } from "@/utils/markdown";

interface ChatMessageProps {
  message: ChatMessageType;
  timestamp?: Date;
}

/**
 * A single chat message bubble.
 * User messages: green bubble on the right (WeChat-style).
 * Assistant messages: white bubble on the left.
 * System messages: centered with muted styling.
 */
export default function ChatMessage({ message, timestamp }: ChatMessageProps) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";
  const { t } = useI18n();

  if (isSystem) {
    return (
      <div className="flex justify-center">
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
            {message.content}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className="max-w-[80%]">
        {/* Role label above bubble */}
        <div className={`flex items-center gap-1.5 mb-1 ${isUser ? "justify-end" : "justify-start"}`}>
          <span className="text-[10px] font-medium text-fg-muted uppercase tracking-wider">
            {isUser ? t("chat.you") : t("chat.assistant")}
          </span>
          {timestamp && (
            <span className="text-[10px] text-fg-muted/60">
              {timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </span>
          )}
        </div>

        {/* Message bubble */}
        {isUser ? (
          <div className="rounded-2xl rounded-br-sm px-3.5 py-2.5 bg-accent text-white text-xs leading-relaxed whitespace-pre-wrap break-words">
            {message.content}
          </div>
        ) : (
          <div
            className="rounded-2xl rounded-bl-sm px-3.5 py-2.5 bg-surface text-fg text-xs leading-relaxed break-words border border-edge"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content) }}
          />
        )}
      </div>
    </div>
  );
}
