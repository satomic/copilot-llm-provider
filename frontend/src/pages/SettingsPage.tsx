import { useState, useCallback, useEffect } from "react";
import Layout from "@/components/layout/Layout";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/contexts/I18nContext";
import { useModels } from "@/hooks/useModels";
import { copyToClipboard } from "@/utils/clipboard";

interface ManagedApiKey {
  key: string;
  key_preview: string;
  alias: string;
  created_at: number;
  allowed_models: string[] | null;
  max_requests: number | null;
  max_premium_requests: number | null;
  current_requests: number;
  current_premium_requests: number;
  enabled: boolean;
}

function authHeaders(token: string): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

export default function SettingsPage() {
  const { token } = useAuth();
  const { t } = useI18n();
  const { models } = useModels();

  const [keys, setKeys] = useState<ManagedApiKey[]>([]);
  const [loading, setLoading] = useState(true);

  // Create key form
  const [newAlias, setNewAlias] = useState("");
  const [newAllowedModels, setNewAllowedModels] = useState<string[]>([]);
  const [newMaxReqs, setNewMaxReqs] = useState("");
  const [newMaxPremReqs, setNewMaxPremReqs] = useState("");
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Edit key form
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editAlias, setEditAlias] = useState("");
  const [editAllowedModels, setEditAllowedModels] = useState<string[]>([]);
  const [editMaxReqs, setEditMaxReqs] = useState("");
  const [editMaxPremReqs, setEditMaxPremReqs] = useState("");

  const fetchKeys = useCallback(() => {
    setLoading(true);
    fetch("/api/admin/api-keys", { headers: authHeaders(token) })
      .then((r) => r.json())
      .then((data) => setKeys(data.keys || []))
      .catch(() => setKeys([]))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    fetchKeys();
  }, [fetchKeys]);

  const handleCreate = useCallback(async () => {
    if (!newAlias.trim()) return;
    setMessage(null);
    try {
      const body: Record<string, unknown> = { alias: newAlias.trim() };
      if (newAllowedModels.length > 0) body.allowed_models = newAllowedModels;
      if (newMaxReqs) body.max_requests = parseInt(newMaxReqs, 10);
      if (newMaxPremReqs) body.max_premium_requests = parseInt(newMaxPremReqs, 10);

      const res = await fetch("/api/admin/api-keys", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setCreatedKey(data.key);
      setNewAlias("");
      setNewAllowedModels([]);
      setNewMaxReqs("");
      setNewMaxPremReqs("");
      fetchKeys();
    } catch (err) {
      setMessage({ type: "error", text: err instanceof Error ? err.message : "Failed" });
    }
  }, [newAlias, newAllowedModels, newMaxReqs, newMaxPremReqs, token, fetchKeys]);

  const handleDelete = useCallback(async (key: string) => {
    try {
      await fetch(`/api/admin/api-keys/${encodeURIComponent(key)}`, {
        method: "DELETE",
        headers: authHeaders(token),
      });
      fetchKeys();
    } catch { /* ignore */ }
  }, [token, fetchKeys]);

  const handleToggle = useCallback(async (key: string, enabled: boolean) => {
    try {
      await fetch(`/api/admin/api-keys/${encodeURIComponent(key)}`, {
        method: "PUT",
        headers: authHeaders(token),
        body: JSON.stringify({ enabled }),
      });
      fetchKeys();
    } catch { /* ignore */ }
  }, [token, fetchKeys]);

  const handleResetUsage = useCallback(async (key: string) => {
    try {
      await fetch(`/api/admin/api-keys/${encodeURIComponent(key)}/reset-usage`, {
        method: "POST",
        headers: authHeaders(token),
      });
      fetchKeys();
    } catch { /* ignore */ }
  }, [token, fetchKeys]);

  const startEdit = useCallback((k: ManagedApiKey) => {
    setEditingKey(k.key);
    setEditAlias(k.alias);
    setEditAllowedModels(k.allowed_models ?? []);
    setEditMaxReqs(k.max_requests != null ? String(k.max_requests) : "");
    setEditMaxPremReqs(k.max_premium_requests != null ? String(k.max_premium_requests) : "");
  }, []);

  const cancelEdit = useCallback(() => {
    setEditingKey(null);
  }, []);

  const handleUpdate = useCallback(async () => {
    if (!editingKey || !editAlias.trim()) return;
    setMessage(null);
    try {
      const body: Record<string, unknown> = { alias: editAlias.trim() };
      body.allowed_models = editAllowedModels.length > 0 ? editAllowedModels : null;
      body.max_requests = editMaxReqs ? parseInt(editMaxReqs, 10) : null;
      body.max_premium_requests = editMaxPremReqs ? parseInt(editMaxPremReqs, 10) : null;

      const res = await fetch(`/api/admin/api-keys/${encodeURIComponent(editingKey)}`, {
        method: "PUT",
        headers: authHeaders(token),
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setEditingKey(null);
      setMessage({ type: "success", text: t("settings.keyUpdated") });
      fetchKeys();
    } catch (err) {
      setMessage({ type: "error", text: err instanceof Error ? err.message : "Failed" });
    }
  }, [editingKey, editAlias, editAllowedModels, editMaxReqs, editMaxPremReqs, token, fetchKeys, t]);

  const toggleEditModel = (modelId: string) => {
    setEditAllowedModels((prev) =>
      prev.includes(modelId) ? prev.filter((m) => m !== modelId) : [...prev, modelId]
    );
  };

  const handleCopyKey = useCallback((key: string) => {
    copyToClipboard(key).then((ok) => {
      if (ok) {
        setCopiedKey(key);
        setTimeout(() => setCopiedKey(null), 2000);
      }
    });
  }, []);

  const toggleModel = (modelId: string) => {
    setNewAllowedModels((prev) =>
      prev.includes(modelId) ? prev.filter((m) => m !== modelId) : [...prev, modelId]
    );
  };

  return (
    <Layout title={t("settings.title")}>
      <div className="p-5 max-w-4xl mx-auto space-y-5">
        {/* API Key Management */}
        <div className="bg-surface border border-edge rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-sm font-semibold text-fg">{t("settings.apiKeys")}</h3>
              <p className="text-xs text-fg-muted mt-0.5">{t("settings.apiKeysDesc")}</p>
            </div>
            <button
              onClick={() => { setShowCreateForm(!showCreateForm); setCreatedKey(null); }}
              className="bg-accent hover:bg-accent-hover text-white px-3 py-1.5 rounded-md text-xs font-medium"
            >
              {showCreateForm ? t("settings.cancel") : t("settings.createKey")}
            </button>
          </div>

          {/* Create form */}
          {showCreateForm && (
            <div className="bg-canvas border border-edge rounded-md p-4 mb-4 space-y-3">
              <div>
                <label className="block text-xs font-medium text-fg-secondary mb-1">{t("settings.keyAlias")}</label>
                <input
                  type="text"
                  value={newAlias}
                  onChange={(e) => setNewAlias(e.target.value)}
                  placeholder={t("settings.keyAliasPlaceholder")}
                  className="w-full bg-surface border border-edge text-fg rounded-md px-3 py-1.5 text-xs
                    placeholder-fg-muted focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-fg-secondary mb-1">{t("settings.allowedModels")}</label>
                <p className="text-[11px] text-fg-muted mb-2">{t("settings.allowedModelsHint")}</p>
                <div className="flex flex-wrap gap-1.5">
                  {models.map((m) => (
                    <button
                      key={m.id}
                      onClick={() => toggleModel(m.id)}
                      className={`px-2 py-0.5 rounded-md text-[11px] font-medium border ${
                        newAllowedModels.includes(m.id)
                          ? "bg-accent/10 border-accent/30 text-accent"
                          : "border-edge text-fg-muted hover:text-fg hover:bg-overlay"
                      }`}
                    >
                      {m.id}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-fg-secondary mb-1">{t("settings.maxRequests")}</label>
                  <input
                    type="number"
                    value={newMaxReqs}
                    onChange={(e) => setNewMaxReqs(e.target.value)}
                    placeholder={t("settings.unlimited")}
                    className="w-full bg-surface border border-edge text-fg rounded-md px-3 py-1.5 text-xs
                      placeholder-fg-muted focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-fg-secondary mb-1">{t("settings.maxPremiumRequests")}</label>
                  <input
                    type="number"
                    value={newMaxPremReqs}
                    onChange={(e) => setNewMaxPremReqs(e.target.value)}
                    placeholder={t("settings.unlimited")}
                    className="w-full bg-surface border border-edge text-fg rounded-md px-3 py-1.5 text-xs
                      placeholder-fg-muted focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent"
                  />
                </div>
              </div>

              <button
                onClick={handleCreate}
                disabled={!newAlias.trim()}
                className="bg-accent hover:bg-accent-hover disabled:opacity-50 text-white px-4 py-1.5 rounded-md text-xs font-medium"
              >
                {t("settings.createKey")}
              </button>

              {createdKey && (
                <div className="bg-success/10 border border-success/20 rounded-md p-3 mt-2">
                  <p className="text-xs font-semibold text-success mb-1">{t("settings.keyCreated")}</p>
                  <div className="flex items-center gap-2">
                    <code className="text-xs font-mono text-fg bg-canvas px-2 py-1 rounded-md flex-1 break-all">
                      {createdKey}
                    </code>
                    <button
                      onClick={() => handleCopyKey(createdKey)}
                      className={`text-[11px] px-2 py-1 rounded-md shrink-0 transition-colors ${
                        copiedKey === createdKey
                          ? "text-success bg-success/10"
                          : "text-fg-muted hover:text-fg hover:bg-overlay"
                      }`}
                    >
                      {copiedKey === createdKey ? t("settings.copied") : t("settings.copy")}
                    </button>
                  </div>
                  <p className="text-[11px] text-fg-muted mt-1.5">{t("settings.keyCreatedHint")}</p>
                </div>
              )}
            </div>
          )}

          {message && (
            <div className={`mb-3 text-xs px-3 py-2 rounded-md ${
              message.type === "success"
                ? "bg-success/10 text-success border border-success/20"
                : "bg-danger/10 text-danger border border-danger/20"
            }`}>
              {message.text}
            </div>
          )}

          {loading ? (
            <div className="text-center py-6 text-xs text-fg-muted">{t("sessions.loading")}</div>
          ) : keys.length === 0 ? (
            <div className="text-center py-6 text-xs text-fg-muted">{t("settings.noKeys")}</div>
          ) : (
            <div className="space-y-2">
              {keys.map((k) => (
                <div
                  key={k.key}
                  className={`border rounded-md p-3 ${
                    k.enabled ? "border-edge bg-overlay/30" : "border-danger/20 bg-danger/5 opacity-60"
                  }`}
                >
                  {editingKey === k.key ? (
                    /* Inline edit form */
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-fg">{t("settings.editKey")}</span>
                        <code className="text-[11px] text-fg-muted font-mono">{k.key_preview}</code>
                      </div>

                      <div>
                        <label className="block text-xs font-medium text-fg-secondary mb-1">{t("settings.keyAlias")}</label>
                        <input
                          type="text"
                          value={editAlias}
                          onChange={(e) => setEditAlias(e.target.value)}
                          className="w-full bg-surface border border-edge text-fg rounded-md px-3 py-1.5 text-xs
                            placeholder-fg-muted focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent"
                        />
                      </div>

                      <div>
                        <label className="block text-xs font-medium text-fg-secondary mb-1">{t("settings.allowedModels")}</label>
                        <p className="text-[11px] text-fg-muted mb-2">{t("settings.allowedModelsHint")}</p>
                        <div className="flex flex-wrap gap-1.5">
                          {models.map((m) => (
                            <button
                              key={m.id}
                              onClick={() => toggleEditModel(m.id)}
                              className={`px-2 py-0.5 rounded-md text-[11px] font-medium border ${
                                editAllowedModels.includes(m.id)
                                  ? "bg-accent/10 border-accent/30 text-accent"
                                  : "border-edge text-fg-muted hover:text-fg hover:bg-overlay"
                              }`}
                            >
                              {m.id}
                            </button>
                          ))}
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="block text-xs font-medium text-fg-secondary mb-1">{t("settings.maxRequests")}</label>
                          <input
                            type="number"
                            value={editMaxReqs}
                            onChange={(e) => setEditMaxReqs(e.target.value)}
                            placeholder={t("settings.unlimited")}
                            className="w-full bg-surface border border-edge text-fg rounded-md px-3 py-1.5 text-xs
                              placeholder-fg-muted focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-fg-secondary mb-1">{t("settings.maxPremiumRequests")}</label>
                          <input
                            type="number"
                            value={editMaxPremReqs}
                            onChange={(e) => setEditMaxPremReqs(e.target.value)}
                            placeholder={t("settings.unlimited")}
                            className="w-full bg-surface border border-edge text-fg rounded-md px-3 py-1.5 text-xs
                              placeholder-fg-muted focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent"
                          />
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          onClick={handleUpdate}
                          disabled={!editAlias.trim()}
                          className="bg-accent hover:bg-accent-hover disabled:opacity-50 text-white px-4 py-1.5 rounded-md text-xs font-medium"
                        >
                          {t("settings.save")}
                        </button>
                        <button
                          onClick={cancelEdit}
                          className="text-fg-muted hover:text-fg px-4 py-1.5 rounded-md text-xs font-medium hover:bg-overlay"
                        >
                          {t("settings.cancel")}
                        </button>
                      </div>
                    </div>
                  ) : (
                    /* Display mode */
                    <>
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-[13px] font-semibold text-fg">{k.alias}</span>
                          <code className="text-[11px] text-fg-muted font-mono">{k.key_preview}</code>
                          {!k.enabled && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-danger/10 text-danger font-medium">
                              {t("settings.disabled")}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => handleCopyKey(k.key)}
                            className={`text-[11px] px-2 py-0.5 rounded-md transition-colors ${
                              copiedKey === k.key
                                ? "text-success bg-success/10"
                                : "text-fg-muted hover:text-fg hover:bg-overlay"
                            }`}
                          >
                            {copiedKey === k.key ? t("settings.copied") : t("settings.copy")}
                          </button>
                          <button
                            onClick={() => startEdit(k)}
                            className="text-[11px] text-fg-muted hover:text-fg px-2 py-0.5 rounded-md hover:bg-overlay"
                          >
                            {t("settings.edit")}
                          </button>
                          <button
                            onClick={() => handleToggle(k.key, !k.enabled)}
                            className="text-[11px] text-fg-muted hover:text-fg px-2 py-0.5 rounded-md hover:bg-overlay"
                          >
                            {k.enabled ? t("settings.disable") : t("settings.enable")}
                          </button>
                          <button
                            onClick={() => handleResetUsage(k.key)}
                            className="text-[11px] text-fg-muted hover:text-fg px-2 py-0.5 rounded-md hover:bg-overlay"
                          >
                            {t("settings.resetUsage")}
                          </button>
                          <button
                            onClick={() => handleDelete(k.key)}
                            className="text-[11px] text-danger hover:bg-danger/10 px-2 py-0.5 rounded-md"
                          >
                            {t("sessions.delete")}
                          </button>
                        </div>
                      </div>

                      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-fg-muted">
                        <span>
                          {t("settings.usage")}: {k.current_requests}
                          {k.max_requests != null ? ` / ${k.max_requests}` : ""}
                        </span>
                        <span>
                          {t("dashboard.premium")}: {k.current_premium_requests}
                          {k.max_premium_requests != null ? ` / ${k.max_premium_requests}` : ""}
                        </span>
                        <span>
                          {t("settings.models")}: {k.allowed_models ? k.allowed_models.join(", ") : t("settings.allModels")}
                        </span>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
