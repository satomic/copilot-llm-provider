import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import Layout from "@/components/layout/Layout";
import StatusBadge from "@/components/common/StatusBadge";
import { useModels } from "@/hooks/useModels";
import { healthCheck } from "@/services/api";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/contexts/I18nContext";

/**
 * Dashboard page showing server status, available models, and quick links.
 */
export default function DashboardPage() {
  const { apiKey } = useAuth();
  const { t } = useI18n();
  const { models, loading, error, refresh } = useModels();
  const [serverOnline, setServerOnline] = useState(false);
  const [checkingServer, setCheckingServer] = useState(true);

  useEffect(() => {
    let cancelled = false;

    const check = async () => {
      setCheckingServer(true);
      const ok = await healthCheck(apiKey);
      if (!cancelled) {
        setServerOnline(ok);
        setCheckingServer(false);
      }
    };

    check();
    return () => {
      cancelled = true;
    };
  }, [apiKey]);

  return (
    <Layout title={t("dashboard.title")}>
      <div className="p-5 max-w-5xl mx-auto space-y-4">
        {/* Server status card */}
        <div className="bg-surface border border-edge rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-fg mb-0.5">{t("dashboard.serverStatus")}</h3>
              <p className="text-xs text-fg-secondary">
                {checkingServer
                  ? t("dashboard.checking")
                  : serverOnline
                    ? t("dashboard.online")
                    : t("dashboard.offline")}
              </p>
            </div>
            <StatusBadge connected={serverOnline} />
          </div>
        </div>

        {/* Quick links */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Link
            to="/playground"
            className="bg-surface border border-edge rounded-lg p-4 hover:border-accent/40
              transition-colors group"
          >
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center group-hover:bg-accent/15 transition-colors">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-accent">
                  <path fillRule="evenodd" d="M10 3c-4.31 0-8 3.033-8 7 0 2.024.978 3.825 2.499 5.085a3.478 3.478 0 0 1-.522 1.756.75.75 0 0 0 .584 1.143 5.976 5.976 0 0 0 3.243-1.053c.7.196 1.44.302 2.196.302 4.31 0 8-3.033 8-7s-3.69-7-8-7Z" clipRule="evenodd" />
                </svg>
              </div>
              <div>
                <h4 className="text-sm font-semibold text-fg">{t("dashboard.playground")}</h4>
                <p className="text-xs text-fg-secondary">{t("dashboard.playgroundDesc")}</p>
              </div>
            </div>
          </Link>

          <Link
            to="/settings"
            className="bg-surface border border-edge rounded-lg p-4 hover:border-accent/40
              transition-colors group"
          >
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center group-hover:bg-accent/15 transition-colors">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-accent">
                  <path fillRule="evenodd" d="M7.84 1.804A1 1 0 0 1 8.82 1h2.36a1 1 0 0 1 .98.804l.331 1.652a6.993 6.993 0 0 1 1.929 1.115l1.598-.54a1 1 0 0 1 1.186.447l1.18 2.044a1 1 0 0 1-.205 1.251l-1.267 1.113a7.047 7.047 0 0 1 0 2.228l1.267 1.113a1 1 0 0 1 .206 1.25l-1.18 2.045a1 1 0 0 1-1.187.447l-1.598-.54a6.993 6.993 0 0 1-1.929 1.115l-.33 1.652a1 1 0 0 1-.98.804H8.82a1 1 0 0 1-.98-.804l-.331-1.652a6.993 6.993 0 0 1-1.929-1.115l-1.598.54a1 1 0 0 1-1.186-.447l-1.18-2.044a1 1 0 0 1 .205-1.251l1.267-1.114a7.05 7.05 0 0 1 0-2.227L1.821 7.773a1 1 0 0 1-.206-1.25l1.18-2.045a1 1 0 0 1 1.187-.447l1.598.54A6.992 6.992 0 0 1 7.51 3.456l.33-1.652ZM10 13a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" clipRule="evenodd" />
                </svg>
              </div>
              <div>
                <h4 className="text-sm font-semibold text-fg">{t("dashboard.settings")}</h4>
                <p className="text-xs text-fg-secondary">{t("dashboard.settingsDesc")}</p>
              </div>
            </div>
          </Link>
        </div>

        {/* Models list */}
        <div className="bg-surface border border-edge rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-fg">{t("dashboard.models")}</h3>
            <button
              onClick={refresh}
              disabled={loading}
              className="text-xs text-accent hover:text-accent-hover disabled:text-fg-muted
                disabled:cursor-not-allowed"
            >
              {loading ? t("dashboard.refreshing") : t("dashboard.refresh")}
            </button>
          </div>

          {/* Loading state */}
          {loading && (
            <div className="flex items-center gap-2 text-fg-secondary py-6 justify-center text-xs">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              {t("dashboard.loadingModels")}
            </div>
          )}

          {/* Error state */}
          {error && !loading && (
            <div className="bg-danger/8 border border-danger/20 text-danger text-xs rounded-md px-3 py-2.5">
              {error}
            </div>
          )}

          {/* Empty state */}
          {!loading && !error && models.length === 0 && (
            <p className="text-fg-muted text-xs text-center py-6">
              {t("dashboard.noModels")}
            </p>
          )}

          {/* Models grid */}
          {!loading && !error && models.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {models.map((model) => (
                <div
                  key={model.id}
                  className="bg-overlay border border-edge rounded-md px-3 py-2.5 hover:border-accent/30 transition-colors"
                >
                  <div className="text-[13px] font-medium text-fg truncate" title={model.id}>
                    {model.id}
                  </div>
                  <div className="text-[11px] text-fg-muted mt-0.5">
                    {model.owned_by}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
