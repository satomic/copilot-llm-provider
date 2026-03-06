import { useState, useRef, useCallback, useEffect, type KeyboardEvent } from "react";
import { useI18n } from "@/contexts/I18nContext";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled: boolean;
}

/**
 * Auto-growing textarea with a send button.
 * Enter sends the message, Shift+Enter inserts a newline.
 */
export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { t } = useI18n();

  // Auto-resize the textarea to fit content
  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
    }
  }, [value]);

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    // Reset height after clearing
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [value, disabled, onSend]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  return (
    <div className="flex items-end gap-2 p-3 border-t border-edge bg-surface">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={t("playground.inputPlaceholder")}
        disabled={disabled}
        rows={1}
        className="flex-1 bg-canvas border border-edge text-fg rounded-md px-3 py-2 text-[13px]
          placeholder-fg-muted focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent
          disabled:opacity-50 disabled:cursor-not-allowed
          min-h-[40px] max-h-[200px] overflow-y-auto leading-relaxed"
      />
      <button
        onClick={handleSend}
        disabled={disabled || !value.trim()}
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
  );
}
