import { useState, useEffect, useMemo } from "react";
import Layout from "@/components/layout/Layout";
import StatusBadge from "@/components/common/StatusBadge";
import { useModels } from "@/hooks/useModels";
import {
  healthCheck,
  fetchUsageStats,
  fetchGitHubTokens,
  type UsageStats,
  type TokenPoolStatus,
} from "@/services/api";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/contexts/I18nContext";
import type { ModelObject } from "@/types/api";

// ---------------------------------------------------------------------------
// Tier helpers
// ---------------------------------------------------------------------------

type Tier = "free" | "premium";

const TIER = {
  free: {
    fill: "#10b981",
    text: "text-emerald-500",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/30",
    dot: "bg-emerald-500",
  },
  premium: {
    fill: "#f43f5e",
    text: "text-rose-500",
    bg: "bg-rose-500/10",
    border: "border-rose-500/30",
    dot: "bg-rose-500",
  },
} as const;

function tierOf(multiplier: number | null | undefined): Tier {
  if (multiplier != null && multiplier > 0) return "premium";
  return "free";
}

function fmtMult(m: number | null | undefined): string {
  if (m == null) return "x0";
  return `x${parseFloat(m.toFixed(2))}`;
}

// Bar chart label/value column widths (consistent across all bar charts)
const BAR_LABEL_W = "w-40";
const BAR_VALUE_W = "w-24";

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const { token } = useAuth();
  const { t } = useI18n();
  const { models, loading, error, refresh } = useModels();
  const [serverOnline, setServerOnline] = useState(false);
  const [checkingServer, setCheckingServer] = useState(true);
  const [stats, setStats] = useState<UsageStats | null>(null);
  const [tokenPool, setTokenPool] = useState<TokenPoolStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      setCheckingServer(true);
      const ok = await healthCheck(token);
      if (!cancelled) {
        setServerOnline(ok);
        setCheckingServer(false);
      }
    };
    check();
    fetchUsageStats(token)
      .then((s) => { if (!cancelled) setStats(s); })
      .catch(() => {});
    fetchGitHubTokens(token)
      .then((tp) => { if (!cancelled) setTokenPool(tp); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [token]);

  // Multiplier lookup
  const multMap = useMemo(() => {
    const map = new Map<string, number>();
    for (const m of models) map.set(m.id, m.billing_multiplier ?? 0);
    if (stats) {
      for (const [id, info] of Object.entries(stats.models)) {
        if (info.multiplier != null) map.set(id, info.multiplier);
      }
    }
    return map;
  }, [models, stats]);

  // Computed stats
  const computed = useMemo(() => {
    if (!stats) return null;
    let total = 0, weighted = 0, freeCount = 0, premCount = 0, premWeighted = 0;
    for (const [id, info] of Object.entries(stats.models)) {
      const mult = multMap.get(id) ?? (info.multiplier ?? (info.is_premium ? 1 : 0));
      total += info.total_requests;
      weighted += info.total_requests * mult;
      if (tierOf(mult) === "premium") {
        premCount += info.total_requests;
        premWeighted += info.total_requests * mult;
      } else {
        freeCount += info.total_requests;
      }
    }
    return { total, weighted, freeCount, premCount, premWeighted };
  }, [stats, multMap]);

  // Usage models sorted
  const usageModels = useMemo(() => {
    if (!stats) return [];
    return Object.entries(stats.models).sort(([, a], [, b]) => b.total_requests - a.total_requests);
  }, [stats]);
  const maxReqs = usageModels[0]?.[1]?.total_requests ?? 1;

  // Grouped models
  const grouped = useMemo(() => {
    const g: Record<Tier, ModelObject[]> = { free: [], premium: [] };
    for (const m of models) g[tierOf(m.billing_multiplier)].push(m);
    return g;
  }, [models]);

  // Daily trend
  const daily = useMemo(() => {
    if (!stats?.recent_daily) return [];
    return Object.entries(stats.recent_daily)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, d]) => ({ date, label: date.slice(5), total: d.total, premium: d.premium, free: d.free }));
  }, [stats]);
  const maxDay = daily.length > 0 ? Math.max(...daily.map((d) => d.total), 1) : 1;

  // Donut
  const donutSegs = useMemo(() => {
    if (!computed) return [];
    return [
      { label: t("dashboard.free"), value: computed.freeCount, color: TIER.free.fill },
      { label: t("dashboard.premium"), value: computed.premCount, color: TIER.premium.fill },
    ].filter((s) => s.value > 0);
  }, [computed, t]);

  const hasStats = computed != null && computed.total > 0;

  // Alias / token bar chart max values
  const maxAlias = useMemo(() => {
    if (!stats?.by_alias) return 1;
    return Math.max(...Object.values(stats.by_alias).map((a) => a.total_requests), 1);
  }, [stats]);
  const maxTokenStat = useMemo(() => {
    if (!stats?.by_token) return 1;
    return Math.max(...Object.values(stats.by_token).map((a) => a.total_requests), 1);
  }, [stats]);

  return (
    <Layout title={t("dashboard.title")}>
      <div className="p-4 space-y-4 overflow-y-auto h-[calc(100vh-3rem)]">

        {/* ================================================================ */}
        {/* Section 1: Status + Summary */}
        {/* ================================================================ */}
        <div className="flex items-stretch gap-3">
          {/* Server status — compact */}
          <div className="bg-surface border border-edge rounded-lg px-4 py-3 flex items-center gap-3 shrink-0">
            <StatusBadge connected={serverOnline} />
            <div>
              <div className="text-xs font-semibold text-fg">{t("dashboard.serverStatus")}</div>
              <div className="text-[11px] text-fg-muted">
                {checkingServer ? t("dashboard.checking") : serverOnline ? t("dashboard.online") : t("dashboard.offline")}
              </div>
            </div>
          </div>

          {hasStats && (
            <>
              <SummaryCard label={t("dashboard.totalRequests")} value={computed.total} cls="text-fg" />
              <SummaryCard label={t("dashboard.weightedTotal")} value={parseFloat(computed.weighted.toFixed(1))} cls="text-accent" />
              <SummaryCard label={t("dashboard.premiumRequests")} value={computed.premCount} sub={`${t("dashboard.weighted")}: ${computed.premWeighted.toFixed(1)}`} cls="text-rose-500" />
              <SummaryCard label={t("dashboard.freeRequests")} value={computed.freeCount} cls="text-emerald-500" />
            </>
          )}

          {/* Token pool badge */}
          {tokenPool && tokenPool.tokens.length > 0 && (
            <div className="bg-surface border border-edge rounded-lg px-4 py-3 flex items-center gap-3 shrink-0 ml-auto">
              <div className="flex -space-x-1">
                {tokenPool.tokens.slice(0, 5).map((tk) => (
                  <div
                    key={tk.id}
                    className="w-3 h-3 rounded-full border-2 border-surface"
                    style={{ backgroundColor: tk.status === "active" ? "#10b981" : tk.status === "error" ? "#f43f5e" : "#6b7280" }}
                    title={tk.alias}
                  />
                ))}
              </div>
              <div>
                <div className="text-xs font-semibold text-fg">{t("tokens.poolStatus")}</div>
                <div className="text-[11px] text-fg-muted">
                  {tokenPool.active} {t("tokens.activeTokens")} / {tokenPool.total} {t("tokens.totalTokens")}
                </div>
              </div>
            </div>
          )}
        </div>

        {hasStats && (
          <>
            {/* ================================================================ */}
            {/* Section 2: Trend + Distribution */}
            {/* ================================================================ */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {/* Daily trend — takes 2 cols */}
              <div className="lg:col-span-2 bg-surface border border-edge rounded-lg p-4">
                <h3 className="text-sm font-semibold text-fg mb-3">{t("dashboard.dailyTrend")}</h3>
                {daily.length > 0 ? (
                  <>
                    <div className="flex items-end gap-2 h-36">
                      {daily.map((d) => (
                        <div key={d.date} className="flex-1 flex flex-col items-center gap-1">
                          <span className="text-[10px] text-fg-muted">{d.total}</span>
                          <div className="w-full flex flex-col justify-end" style={{ height: "110px" }}>
                            {d.premium > 0 && (
                              <div
                                className="w-full rounded-t-sm"
                                style={{ height: `${(d.premium / maxDay) * 110}px`, backgroundColor: TIER.premium.fill, opacity: 0.8 }}
                              />
                            )}
                            {d.free > 0 && (
                              <div
                                className={`w-full ${d.premium === 0 ? "rounded-t-sm" : ""} rounded-b-sm`}
                                style={{ height: `${(d.free / maxDay) * 110}px`, backgroundColor: TIER.free.fill, opacity: 0.8 }}
                              />
                            )}
                          </div>
                          <span className="text-[9px] text-fg-muted">{d.label}</span>
                        </div>
                      ))}
                    </div>
                    <div className="flex items-center gap-4 mt-3 justify-center">
                      {[
                        { label: t("dashboard.premium"), color: TIER.premium.fill },
                        { label: t("dashboard.free"), color: TIER.free.fill },
                      ].map((item) => (
                        <div key={item.label} className="flex items-center gap-1">
                          <div className="w-2 h-2 rounded-sm" style={{ backgroundColor: item.color, opacity: 0.8 }} />
                          <span className="text-[10px] text-fg-muted">{item.label}</span>
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <p className="text-xs text-fg-muted text-center py-8">{t("dashboard.noStats")}</p>
                )}
              </div>

              {/* Distribution donut — 1 col */}
              <div className="bg-surface border border-edge rounded-lg p-4">
                <h3 className="text-sm font-semibold text-fg mb-3">{t("dashboard.requestDistribution")}</h3>
                {donutSegs.length > 0 && computed ? (
                  <div className="flex flex-col items-center gap-4 py-2">
                    <Donut segments={donutSegs} total={computed.total} />
                    <div className="space-y-2">
                      {donutSegs.map((s) => (
                        <div key={s.label} className="flex items-center gap-2">
                          <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: s.color }} />
                          <span className="text-xs text-fg-secondary">{s.label}</span>
                          <span className="text-xs font-semibold text-fg">{s.value}</span>
                          <span className="text-[10px] text-fg-muted">
                            ({((s.value / computed.total) * 100).toFixed(0)}%)
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-fg-muted text-center py-8">{t("dashboard.noStats")}</p>
                )}
              </div>
            </div>

            {/* ================================================================ */}
            {/* Section 3: Bar Charts — Model / API Key / Token usage */}
            {/* ================================================================ */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Model usage */}
              {usageModels.length > 0 && (
                <div className="bg-surface border border-edge rounded-lg p-4">
                  <h3 className="text-sm font-semibold text-fg mb-3">{t("dashboard.modelUsage")}</h3>
                  <div className="space-y-1.5">
                    {usageModels.map(([id, info]) => {
                      const mult = multMap.get(id) ?? (info.multiplier ?? (info.is_premium ? 1 : 0));
                      const tier = tierOf(mult);
                      const c = TIER[tier];
                      const pct = (info.total_requests / maxReqs) * 100;
                      return (
                        <div key={id} className="flex items-center gap-2">
                          <div className={`flex items-center gap-1.5 ${BAR_LABEL_W} shrink-0 min-w-0`}>
                            <span className="text-[12px] font-medium text-fg truncate" title={id}>{id}</span>
                            <span className={`text-[10px] px-1 py-0.5 rounded-full font-medium shrink-0 ${c.bg} ${c.text}`}>
                              {fmtMult(mult)}
                            </span>
                          </div>
                          <div className="flex-1 h-5 bg-canvas rounded-md overflow-hidden">
                            <div
                              className="h-full rounded-md transition-all duration-500"
                              style={{ width: `${pct}%`, backgroundColor: c.fill, opacity: 0.65 }}
                            />
                          </div>
                          <span className={`text-[11px] text-fg-muted ${BAR_VALUE_W} text-right shrink-0`}>
                            {info.total_requests} {t("dashboard.requests")}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Right column: API Key + Token usage stacked */}
              <div className="space-y-4">
                {/* API Key usage */}
                {stats?.by_alias && Object.keys(stats.by_alias).length > 0 && (
                  <div className="bg-surface border border-edge rounded-lg p-4">
                    <h3 className="text-sm font-semibold text-fg mb-3">{t("dashboard.aliasUsage")}</h3>
                    <div className="space-y-1.5">
                      {Object.entries(stats.by_alias)
                        .sort(([, a], [, b]) => b.total_requests - a.total_requests)
                        .map(([alias, info]) => {
                          const pct = (info.total_requests / maxAlias) * 100;
                          return (
                            <div key={alias} className="flex items-center gap-2">
                              <span className={`text-[12px] font-medium text-fg ${BAR_LABEL_W} shrink-0 truncate`} title={alias}>
                                {alias}
                              </span>
                              <div className="flex-1 h-5 bg-canvas rounded-md overflow-hidden">
                                <div
                                  className="h-full rounded-md transition-all duration-500"
                                  style={{ width: `${pct}%`, backgroundColor: "#8b5cf6", opacity: 0.65 }}
                                />
                              </div>
                              <span className={`text-[11px] text-fg-muted ${BAR_VALUE_W} text-right shrink-0`}>
                                {info.total_requests} {t("dashboard.requests")}
                              </span>
                            </div>
                          );
                        })}
                    </div>
                  </div>
                )}

                {/* GitHub Token usage (from stats) */}
                {stats?.by_token && Object.keys(stats.by_token).length > 0 && (
                  <div className="bg-surface border border-edge rounded-lg p-4">
                    <h3 className="text-sm font-semibold text-fg mb-3">{t("dashboard.tokenUsage")}</h3>
                    <div className="space-y-1.5">
                      {Object.entries(stats.by_token)
                        .sort(([, a], [, b]) => b.total_requests - a.total_requests)
                        .map(([alias, info]) => {
                          const pct = (info.total_requests / maxTokenStat) * 100;
                          return (
                            <div key={alias} className="flex items-center gap-2">
                              <span className={`text-[12px] font-medium text-fg ${BAR_LABEL_W} shrink-0 truncate`} title={alias}>
                                {alias}
                              </span>
                              <div className="flex-1 h-5 bg-canvas rounded-md overflow-hidden">
                                <div
                                  className="h-full rounded-md transition-all duration-500"
                                  style={{ width: `${pct}%`, backgroundColor: "#6366f1", opacity: 0.65 }}
                                />
                              </div>
                              <span className={`text-[11px] text-fg-muted ${BAR_VALUE_W} text-right shrink-0`}>
                                {info.total_requests} {t("dashboard.requests")}
                              </span>
                            </div>
                          );
                        })}
                    </div>
                  </div>
                )}

                {/* Token pool status (runtime) */}
                {tokenPool && tokenPool.tokens.length > 0 && (
                  <div className="bg-surface border border-edge rounded-lg p-4">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-sm font-semibold text-fg">{t("tokens.poolStatus")}</h3>
                      <span className="text-[11px] text-fg-muted">
                        {tokenPool.active} {t("tokens.activeTokens")} / {tokenPool.total} {t("tokens.totalTokens")}
                      </span>
                    </div>
                    <div className="space-y-1.5">
                      {tokenPool.tokens.map((tk) => {
                        const maxTk = Math.max(...tokenPool.tokens.map((t) => t.total_requests), 1);
                        const pct = (tk.total_requests / maxTk) * 100;
                        const statusColor = tk.status === "active" ? "#10b981" : tk.status === "error" ? "#f43f5e" : "#6b7280";
                        return (
                          <div key={tk.id} className="flex items-center gap-2">
                            <div className={`flex items-center gap-1.5 ${BAR_LABEL_W} shrink-0 min-w-0`}>
                              <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: statusColor }} />
                              <span className="text-[12px] font-medium text-fg truncate" title={tk.alias}>{tk.alias}</span>
                            </div>
                            <div className="flex-1 h-5 bg-canvas rounded-md overflow-hidden">
                              <div
                                className="h-full rounded-md transition-all duration-500"
                                style={{ width: `${pct}%`, backgroundColor: "#6366f1", opacity: 0.65 }}
                              />
                            </div>
                            <div className={`text-[11px] text-fg-muted ${BAR_VALUE_W} text-right shrink-0`}>
                              {tk.total_requests}
                              {tk.premium_quota_limit != null && (
                                <span className="text-[10px] ml-0.5">
                                  ({tk.premium_quota_used ?? "?"}/{tk.premium_quota_limit})
                                </span>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </>
        )}

        {/* ================================================================ */}
        {/* Section 4: Available Models */}
        {/* ================================================================ */}
        <div className="bg-surface border border-edge rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-fg">{t("dashboard.models")}</h3>
            <button
              onClick={refresh}
              disabled={loading}
              className="text-xs text-accent hover:text-accent-hover disabled:text-fg-muted disabled:cursor-not-allowed"
            >
              {loading ? t("dashboard.refreshing") : t("dashboard.refresh")}
            </button>
          </div>

          {loading && (
            <div className="flex items-center gap-2 text-fg-secondary py-6 justify-center text-xs">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              {t("dashboard.loadingModels")}
            </div>
          )}

          {error && !loading && (
            <div className="bg-danger/10 border border-danger/20 text-danger text-xs rounded-md px-3 py-2.5">{error}</div>
          )}

          {!loading && !error && models.length === 0 && (
            <p className="text-fg-muted text-xs text-center py-6">{t("dashboard.noModels")}</p>
          )}

          {!loading && !error && models.length > 0 && (() => {
            const paid = grouped.premium;
            const free = grouped.free;
            return (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {paid.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <div className={`w-2 h-2 rounded-full ${TIER.premium.dot}`} />
                      <h4 className={`text-xs font-semibold ${TIER.premium.text}`}>{t("dashboard.premium")}</h4>
                      <span className="text-[10px] text-fg-muted">(x&gt;0)</span>
                      <span className="text-[10px] text-fg-muted">· {paid.length} {t("dashboard.modelsCount")}</span>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-2">
                      {paid.map((m) => {
                        const c = TIER[tierOf(m.billing_multiplier)];
                        return (
                          <div key={m.id} className={`bg-overlay border ${c.border} rounded-md px-3 py-2 hover:brightness-110 transition`}>
                            <div className="flex items-center justify-between">
                              <span className="text-[13px] font-medium text-fg truncate" title={m.id}>{m.id}</span>
                              <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium shrink-0 ml-2 ${c.bg} ${c.text}`}>
                                {fmtMult(m.billing_multiplier)}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
                {free.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <div className={`w-2 h-2 rounded-full ${TIER.free.dot}`} />
                      <h4 className={`text-xs font-semibold ${TIER.free.text}`}>{t("dashboard.free")}</h4>
                      <span className="text-[10px] text-fg-muted">(x0)</span>
                      <span className="text-[10px] text-fg-muted">· {free.length} {t("dashboard.modelsCount")}</span>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-2">
                      {free.map((m) => (
                        <div key={m.id} className={`bg-overlay border ${TIER.free.border} rounded-md px-3 py-2 hover:brightness-110 transition`}>
                          <div className="flex items-center justify-between">
                            <span className="text-[13px] font-medium text-fg truncate" title={m.id}>{m.id}</span>
                            <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium shrink-0 ml-2 ${TIER.free.bg} ${TIER.free.text}`}>
                              {fmtMult(m.billing_multiplier)}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })()}
        </div>
      </div>
    </Layout>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SummaryCard({ label, value, sub, cls }: { label: string; value: number; sub?: string; cls: string }) {
  return (
    <div className="bg-surface border border-edge rounded-lg px-4 py-3 flex-1 min-w-0">
      <div className={`text-xl font-bold ${cls}`}>{value}</div>
      {sub && <div className="text-[10px] text-fg-muted">{sub}</div>}
      <div className="text-[11px] text-fg-muted mt-0.5">{label}</div>
    </div>
  );
}

function Donut({ segments, total }: { segments: { value: number; color: string; label: string }[]; total: number }) {
  let pct = 0;
  const stops = segments.map((s) => {
    const share = (s.value / total) * 100;
    const stop = `${s.color} ${pct}% ${pct + share}%`;
    pct += share;
    return stop;
  });
  return (
    <div className="relative w-28 h-28 shrink-0">
      <div className="w-full h-full rounded-full" style={{ background: `conic-gradient(${stops.join(", ")})` }} />
      <div className="absolute inset-[18px] rounded-full bg-surface flex items-center justify-center">
        <span className="text-lg font-bold text-fg">{total}</span>
      </div>
    </div>
  );
}
