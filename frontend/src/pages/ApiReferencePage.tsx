import { useState, useMemo, useCallback } from "react";
import Layout from "@/components/layout/Layout";
import CodeBlock from "@/components/common/CodeBlock";
import { useI18n } from "@/contexts/I18nContext";
import { copyToClipboard } from "@/utils/clipboard";
import { getBaseUrl } from "@/utils/baseUrl";

function EndpointRow({ label, url }: { label: string; url: string }) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    copyToClipboard(url).then((ok) => {
      if (ok) {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }
    });
  }, [url]);

  return (
    <div className="flex items-center justify-between py-2.5 border-b border-edge last:border-b-0">
      <div>
        <div className="text-[13px] font-medium text-fg-secondary">{label}</div>
        <code className="text-xs text-accent mt-0.5 block">{url}</code>
      </div>
      <button
        onClick={handleCopy}
        className={`text-[11px] px-2.5 py-1 rounded-md shrink-0 ml-4 transition-colors ${
          copied
            ? "text-success bg-success/10"
            : "text-fg-muted hover:text-fg hover:bg-overlay"
        }`}
      >
        {copied ? t("settings.copied") : t("settings.copy")}
      </button>
    </div>
  );
}

type OS = "macos" | "linux" | "windows";
type ApiType = "openai" | "anthropic";

const OS_LABELS: Record<OS, string> = {
  macos: "macOS",
  linux: "Linux",
  windows: "Windows",
};

// ---------------------------------------------------------------------------
// Example generators (take baseUrl as parameter)
// ---------------------------------------------------------------------------

type Example = { code: string; language: string; label: string };

function openaiCurl(b: string): Record<OS, Example> {
  const curlCode = `curl ${b}/openai/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -d '{
    "model": "gpt-4o",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ],
    "stream": true
  }'`;
  return {
    macos: { label: "cURL", language: "bash", code: curlCode },
    linux: { label: "cURL", language: "bash", code: curlCode },
    windows: {
      label: "PowerShell",
      language: "powershell",
      code: `$body = @{
    model = "gpt-4o"
    messages = @(
        @{ role = "user"; content = "Hello!" }
    )
    stream = $true
} | ConvertTo-Json -Depth 3

$headers = @{
    "Content-Type"  = "application/json"
    "Authorization" = "Bearer YOUR_API_KEY"
}

Invoke-RestMethod \`
  -Uri "${b}/openai/v1/chat/completions" \`
  -Method POST \`
  -Headers $headers \`
  -Body $body`,
    },
  };
}

function openaiPython(b: string): string {
  return `from openai import OpenAI

client = OpenAI(
    base_url="${b}/openai/v1",
    api_key="YOUR_API_KEY",
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "user", "content": "Hello!"}
    ],
    stream=True,
)

for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")`;
}

function openaiNodejs(b: string): string {
  return `import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "${b}/openai/v1",
  apiKey: "YOUR_API_KEY",
});

const stream = await client.chat.completions.create({
  model: "gpt-4o",
  messages: [
    { role: "user", content: "Hello!" }
  ],
  stream: true,
});

for await (const chunk of stream) {
  const content = chunk.choices[0]?.delta?.content;
  if (content) process.stdout.write(content);
}`;
}

function anthropicCurl(b: string): Record<OS, Example> {
  const curlCode = `curl ${b}/anthropic/v1/messages \\
  -H "Content-Type: application/json" \\
  -H "x-api-key: YOUR_API_KEY" \\
  -H "anthropic-version: 2023-06-01" \\
  -d '{
    "model": "claude-sonnet-4.5",
    "max_tokens": 1024,
    "messages": [
      {"role": "user", "content": "Hello!"}
    ],
    "stream": true
  }'`;
  return {
    macos: { label: "cURL", language: "bash", code: curlCode },
    linux: { label: "cURL", language: "bash", code: curlCode },
    windows: {
      label: "PowerShell",
      language: "powershell",
      code: `$body = @{
    model = "claude-sonnet-4.5"
    max_tokens = 1024
    messages = @(
        @{ role = "user"; content = "Hello!" }
    )
    stream = $true
} | ConvertTo-Json -Depth 3

$headers = @{
    "Content-Type"     = "application/json"
    "x-api-key"        = "YOUR_API_KEY"
    "anthropic-version" = "2023-06-01"
}

Invoke-RestMethod \`
  -Uri "${b}/anthropic/v1/messages" \`
  -Method POST \`
  -Headers $headers \`
  -Body $body`,
    },
  };
}

function anthropicPython(b: string): string {
  return `import anthropic

client = anthropic.Anthropic(
    base_url="${b}/anthropic",
    api_key="YOUR_API_KEY",
)

with client.messages.stream(
    model="claude-sonnet-4.5",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Hello!"}
    ],
) as stream:
    for text in stream.text_stream:
        print(text, end="")`;
}

function anthropicNodejs(b: string): string {
  return `import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic({
  baseURL: "${b}/anthropic",
  apiKey: "YOUR_API_KEY",
});

const stream = client.messages.stream({
  model: "claude-sonnet-4.5",
  max_tokens: 1024,
  messages: [
    { role: "user", content: "Hello!" }
  ],
});

for await (const event of stream) {
  if (
    event.type === "content_block_delta" &&
    event.delta.type === "text_delta"
  ) {
    process.stdout.write(event.delta.text);
  }
}`;
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function ApiReferencePage() {
  const { t } = useI18n();
  const [apiType, setApiType] = useState<ApiType>("openai");
  const [selectedOS, setSelectedOS] = useState<OS>("macos");

  const baseUrl = useMemo(() => getBaseUrl(), []);

  const curlExamples = apiType === "openai" ? openaiCurl(baseUrl) : anthropicCurl(baseUrl);
  const pythonExample = apiType === "openai" ? openaiPython(baseUrl) : anthropicPython(baseUrl);
  const nodejsExample = apiType === "openai" ? openaiNodejs(baseUrl) : anthropicNodejs(baseUrl);
  const pythonLabel = apiType === "openai" ? t("apiRef.pythonOpenai") : t("apiRef.pythonAnthropic");
  const nodejsLabel = apiType === "openai" ? t("apiRef.nodejsOpenai") : t("apiRef.nodejsAnthropic");

  return (
    <Layout title={t("apiRef.title")}>
      <div className="p-5 max-w-3xl mx-auto space-y-5">
        {/* API type toggle */}
        <div className="flex items-center gap-1 bg-surface border border-edge rounded-lg p-1 w-fit">
          {(["openai", "anthropic"] as ApiType[]).map((typ) => (
            <button
              key={typ}
              onClick={() => setApiType(typ)}
              className={`px-4 py-1.5 rounded-md text-xs font-semibold transition-colors ${
                apiType === typ
                  ? "bg-accent text-white"
                  : "text-fg-muted hover:text-fg hover:bg-overlay"
              }`}
            >
              {t(`apiRef.${typ}`)}
            </button>
          ))}
        </div>

        {/* API Endpoints */}
        <div className="bg-surface border border-edge rounded-lg p-4">
          <h3 className="text-sm font-semibold text-fg mb-3">{t("settings.endpoints")}</h3>
          <div>
            {apiType === "openai" ? (
              <>
                <EndpointRow
                  label={t("apiRef.chatCompletions")}
                  url={`${baseUrl}/openai/v1/chat/completions`}
                />
                <EndpointRow
                  label={t("settings.modelsList")}
                  url={`${baseUrl}/openai/v1/models`}
                />
              </>
            ) : (
              <EndpointRow
                label={t("apiRef.messages")}
                url={`${baseUrl}/anthropic/v1/messages`}
              />
            )}
            <EndpointRow
              label={t("settings.healthCheck")}
              url={`${baseUrl}/health`}
            />
          </div>
        </div>

        {/* Usage examples */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-fg">{t("settings.usageExamples")}</h3>
            <div className="flex items-center gap-1.5">
              <span className="text-[11px] text-fg-muted mr-1">{t("settings.platform")}:</span>
              {(["macos", "linux", "windows"] as OS[]).map((os) => (
                <button
                  key={os}
                  onClick={() => setSelectedOS(os)}
                  className={`px-2 py-0.5 rounded-md text-[11px] font-medium ${
                    selectedOS === os
                      ? "bg-accent/10 text-accent"
                      : "text-fg-muted hover:text-fg hover:bg-overlay"
                  }`}
                >
                  {OS_LABELS[os]}
                </button>
              ))}
            </div>
          </div>

          <div>
            <h4 className="text-[11px] font-medium text-fg-muted mb-2 uppercase tracking-wider">
              {curlExamples[selectedOS].label}
            </h4>
            <CodeBlock
              code={curlExamples[selectedOS].code}
              language={curlExamples[selectedOS].language}
            />
          </div>

          <div>
            <h4 className="text-[11px] font-medium text-fg-muted mb-2 uppercase tracking-wider">{pythonLabel}</h4>
            <CodeBlock code={pythonExample} language="python" />
          </div>

          <div>
            <h4 className="text-[11px] font-medium text-fg-muted mb-2 uppercase tracking-wider">{nodejsLabel}</h4>
            <CodeBlock code={nodejsExample} language="javascript" />
          </div>
        </div>
      </div>
    </Layout>
  );
}
