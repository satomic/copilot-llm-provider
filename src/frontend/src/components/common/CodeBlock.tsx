import { useState, useCallback } from "react";
import { useI18n } from "@/contexts/I18nContext";
import { copyToClipboard } from "@/utils/clipboard";

interface CodeBlockProps {
  code: string;
  language: string;
}

/**
 * Displays a code block with a language label and copy-to-clipboard button.
 */
export default function CodeBlock({ code, language }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);
  const { t } = useI18n();

  const handleCopy = useCallback(() => {
    copyToClipboard(code).then((ok) => {
      if (ok) {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }
    });
  }, [code]);

  return (
    <div className="rounded-lg overflow-hidden border border-edge bg-surface">
      {/* Header bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-overlay border-b border-edge">
        <span className="text-[11px] font-medium text-fg-muted uppercase tracking-wider">
          {language}
        </span>
        <button
          onClick={handleCopy}
          className={`text-[11px] px-2 py-0.5 rounded-md transition-colors ${
            copied
              ? "text-success bg-success/10"
              : "text-fg-muted hover:text-fg hover:bg-surface"
          }`}
        >
          {copied ? t("settings.copied") : t("settings.copy")}
        </button>
      </div>
      {/* Code content */}
      <pre className="p-4 overflow-x-auto text-[13px] leading-relaxed">
        <code className="text-fg-secondary">{code}</code>
      </pre>
    </div>
  );
}
