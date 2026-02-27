import { useState, useCallback } from "react";
import Layout from "@/components/layout/Layout";
import CodeBlock from "@/components/common/CodeBlock";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/contexts/I18nContext";

/** Single endpoint row with a copy button. */
function EndpointRow({ label, url }: { label: string; url: string }) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
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
        className="text-[11px] text-fg-muted hover:text-fg px-2.5 py-1 rounded-md
          hover:bg-overlay shrink-0 ml-4"
      >
        {copied ? t("settings.copied") : t("settings.copy")}
      </button>
    </div>
  );
}

const CURL_EXAMPLE = `curl http://localhost:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -d '{
    "model": "gpt-4o",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ],
    "stream": true
  }'`;

const PYTHON_EXAMPLE = `from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="YOUR_API_KEY",  # or empty string for no-auth
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

const NODEJS_EXAMPLE = `import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "http://localhost:8000/v1",
  apiKey: "YOUR_API_KEY", // or empty string for no-auth
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

/**
 * Settings page displaying API endpoint URLs, example code, and connection info.
 */
export default function SettingsPage() {
  const { apiKey } = useAuth();
  const { t } = useI18n();

  return (
    <Layout title={t("settings.title")}>
      <div className="p-5 max-w-3xl mx-auto space-y-5">
        {/* Connection info */}
        <div className="bg-surface border border-edge rounded-lg p-4">
          <h3 className="text-sm font-semibold text-fg mb-3">{t("settings.connectionInfo")}</h3>
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="text-xs text-fg-muted w-24 uppercase tracking-wide">{t("settings.authMode")}</span>
              <span className="text-xs text-fg">
                {apiKey ? t("settings.apiKeyAuth") : t("settings.noAuth")}
              </span>
            </div>
            {apiKey && (
              <div className="flex items-center gap-3">
                <span className="text-xs text-fg-muted w-24 uppercase tracking-wide">{t("settings.apiKeyLabel")}</span>
                <code className="text-xs text-fg bg-overlay px-2 py-0.5 rounded-md">
                  {apiKey.slice(0, 8)}{"*".repeat(Math.max(0, apiKey.length - 8))}
                </code>
              </div>
            )}
          </div>
        </div>

        {/* API Endpoints */}
        <div className="bg-surface border border-edge rounded-lg p-4">
          <h3 className="text-sm font-semibold text-fg mb-3">{t("settings.endpoints")}</h3>
          <div>
            <EndpointRow
              label={t("settings.openaiChat")}
              url="http://localhost:8000/v1/chat/completions"
            />
            <EndpointRow
              label={t("settings.anthropicMessages")}
              url="http://localhost:8000/v1/messages"
            />
            <EndpointRow
              label={t("settings.modelsList")}
              url="http://localhost:8000/v1/models"
            />
            <EndpointRow
              label={t("settings.healthCheck")}
              url="http://localhost:8000/health"
            />
          </div>
        </div>

        {/* Usage examples */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-fg">{t("settings.usageExamples")}</h3>

          <div>
            <h4 className="text-[11px] font-medium text-fg-muted mb-2 uppercase tracking-wider">{t("settings.curl")}</h4>
            <CodeBlock code={CURL_EXAMPLE} language="bash" />
          </div>

          <div>
            <h4 className="text-[11px] font-medium text-fg-muted mb-2 uppercase tracking-wider">{t("settings.python")}</h4>
            <CodeBlock code={PYTHON_EXAMPLE} language="python" />
          </div>

          <div>
            <h4 className="text-[11px] font-medium text-fg-muted mb-2 uppercase tracking-wider">{t("settings.nodejs")}</h4>
            <CodeBlock code={NODEJS_EXAMPLE} language="javascript" />
          </div>
        </div>
      </div>
    </Layout>
  );
}
