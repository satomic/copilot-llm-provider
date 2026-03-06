import { useState, useMemo, useCallback } from "react";
import Layout from "@/components/layout/Layout";
import { useI18n } from "@/contexts/I18nContext";
import { copyToClipboard } from "@/utils/clipboard";
import { getBaseUrl } from "@/utils/baseUrl";

interface ToolDef {
  id: string;
  nameKey: string;
  descKey: string;
  icon: string;
  configs: (baseUrl: string) => {
    labelKey: string;
    os: "all" | "macos" | "linux" | "windows";
    type: "env";
    value: string;
  }[];
}

const TOOLS: ToolDef[] = [
  {
    id: "claude-code",
    nameKey: "tools.claudeCode",
    descKey: "tools.claudeCodeDesc",
    icon: "C",
    configs: (baseUrl) => [
      {
        labelKey: "tools.envVars",
        os: "macos",
        type: "env",
        value: `export ANTHROPIC_AUTH_TOKEN="YOUR_API_KEY"\nexport ANTHROPIC_BASE_URL="${baseUrl}/anthropic"\nexport ANTHROPIC_DEFAULT_SONNET_MODEL="claude-sonnet-4.5"`,
      },
      {
        labelKey: "tools.envVars",
        os: "linux",
        type: "env",
        value: `export ANTHROPIC_AUTH_TOKEN="YOUR_API_KEY"\nexport ANTHROPIC_BASE_URL="${baseUrl}/anthropic"\nexport ANTHROPIC_DEFAULT_SONNET_MODEL="claude-sonnet-4.5"`,
      },
      {
        labelKey: "tools.envVars",
        os: "windows",
        type: "env",
        value: `$env:ANTHROPIC_AUTH_TOKEN = "YOUR_API_KEY"\n$env:ANTHROPIC_BASE_URL = "${baseUrl}/anthropic"\n$env:ANTHROPIC_DEFAULT_SONNET_MODEL = "claude-sonnet-4.5"`,
      },
    ],
  },
  {
    id: "codex-cli",
    nameKey: "tools.codexCli",
    descKey: "tools.codexCliDesc",
    icon: "X",
    configs: (baseUrl) => [
      {
        labelKey: "tools.envVars",
        os: "macos",
        type: "env",
        value: `export OPENAI_API_KEY="YOUR_API_KEY"\nexport OPENAI_BASE_URL="${baseUrl}/openai/v1"`,
      },
      {
        labelKey: "tools.envVars",
        os: "linux",
        type: "env",
        value: `export OPENAI_API_KEY="YOUR_API_KEY"\nexport OPENAI_BASE_URL="${baseUrl}/openai/v1"`,
      },
      {
        labelKey: "tools.envVars",
        os: "windows",
        type: "env",
        value: `$env:OPENAI_API_KEY = "YOUR_API_KEY"\n$env:OPENAI_BASE_URL = "${baseUrl}/openai/v1"`,
      },
    ],
  },
];

function CopyButton({ text }: { text: string }) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    copyToClipboard(text).then((ok) => {
      if (ok) {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }
    });
  }, [text]);

  return (
    <button
      onClick={handleCopy}
      className={`text-[11px] px-2 py-0.5 rounded-md shrink-0 transition-colors ${
        copied
          ? "text-success bg-success/10"
          : "text-fg-muted hover:text-fg hover:bg-overlay"
      }`}
    >
      {copied ? t("settings.copied") : t("settings.copy")}
    </button>
  );
}

const OS_LABELS: Record<string, string> = {
  macos: "macOS",
  linux: "Linux",
  windows: "Windows",
};

export default function ToolConfigPage() {
  const { t } = useI18n();
  const [expandedTools, setExpandedTools] = useState<Set<string>>(
    new Set(TOOLS.map((tool) => tool.id))
  );
  const [selectedOS, setSelectedOS] = useState<string>("macos");

  const baseUrl = useMemo(() => getBaseUrl(), []);

  const toggleTool = (id: string) => {
    setExpandedTools((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <Layout title={t("tools.title")}>
      <div className="p-5 max-w-3xl mx-auto space-y-4">
        {/* OS Selector */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-fg-muted">{t("tools.platform")}:</span>
          {["macos", "linux", "windows"].map((os) => (
            <button
              key={os}
              onClick={() => setSelectedOS(os)}
              className={`px-2.5 py-1 rounded-md text-xs font-medium ${
                selectedOS === os
                  ? "bg-accent/10 text-accent"
                  : "text-fg-secondary hover:text-fg hover:bg-overlay"
              }`}
            >
              {OS_LABELS[os]}
            </button>
          ))}
        </div>

        {/* Tool Cards */}
        {TOOLS.map((tool) => {
          const isExpanded = expandedTools.has(tool.id);
          const allConfigs = tool.configs(baseUrl);
          const filteredConfigs = allConfigs.filter(
            (c) => c.os === "all" || c.os === selectedOS
          );

          return (
            <div
              key={tool.id}
              className="bg-surface border border-edge rounded-lg overflow-hidden"
            >
              {/* Header */}
              <button
                onClick={() => toggleTool(tool.id)}
                className="w-full flex items-center gap-3 p-4 hover:bg-overlay/50 transition-colors text-left"
              >
                <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
                  <span className="text-xs font-bold text-accent">
                    {tool.icon}
                  </span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-fg">
                    {t(tool.nameKey)}
                  </div>
                  <div className="text-xs text-fg-muted truncate">
                    {t(tool.descKey)}
                  </div>
                </div>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  className={`w-4 h-4 text-fg-muted transition-transform ${
                    isExpanded ? "rotate-180" : ""
                  }`}
                >
                  <path
                    fillRule="evenodd"
                    d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z"
                    clipRule="evenodd"
                  />
                </svg>
              </button>

              {/* Expanded configs */}
              {isExpanded && filteredConfigs.length > 0 && (
                <div className="border-t border-edge p-4 space-y-3">
                  {filteredConfigs.map((config, idx) => (
                    <div key={idx}>
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-[11px] font-medium text-fg-muted uppercase tracking-wider">
                          {t(config.labelKey)}
                          {config.os !== "all" && (
                            <span className="ml-1.5 text-fg-muted/60">
                              ({OS_LABELS[config.os]})
                            </span>
                          )}
                        </span>
                        <CopyButton text={config.value} />
                      </div>
                      <pre className="bg-canvas border border-edge rounded-md p-3 overflow-x-auto text-[12px] leading-relaxed">
                        <code className="text-fg-secondary">{config.value}</code>
                      </pre>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}

        {/* Hint */}
        <div className="text-xs text-fg-muted text-center py-2">
          {t("tools.hint")}
        </div>
      </div>
    </Layout>
  );
}
