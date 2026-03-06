import { useState, useCallback, useEffect, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { useTheme } from "@/contexts/ThemeContext";
import { useI18n } from "@/contexts/I18nContext";
import { getBaseUrl } from "@/utils/baseUrl";

export default function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const { t, locale, toggleLocale } = useI18n();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasUsers, setHasUsers] = useState<boolean | null>(null);

  useEffect(() => {
    fetch("/api/auth/status")
      .then((r) => r.json())
      .then((data) => setHasUsers(data.has_users))
      .catch(() => setHasUsers(false));
  }, []);

  const isRegister = hasUsers === false;

  const handleSubmit = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      if (!username.trim() || !password.trim()) return;
      setLoading(true);
      setError(null);

      try {
        const endpoint = isRegister ? "/api/auth/register" : "/api/auth/login";
        const response = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username: username.trim(), password }),
        });

        if (!response.ok) {
          const data = await response.json().catch(() => null);
          const msg = data?.detail || `HTTP ${response.status}`;
          setError(typeof msg === "string" ? msg : JSON.stringify(msg));
          return;
        }

        const data = await response.json();
        login(data.token, data.username);
        navigate("/dashboard");
      } catch {
        setError(t("login.error.failed"));
      } finally {
        setLoading(false);
      }
    },
    [username, password, isRegister, login, navigate, t]
  );

  return (
    <div className="relative min-h-screen bg-canvas flex items-center justify-center p-4">
      {/* Theme & Language toggles */}
      <div className="absolute top-4 right-4 flex items-center gap-1">
        <button
          onClick={toggleTheme}
          className="p-2 rounded-md text-fg-muted hover:text-fg hover:bg-overlay"
          title={theme === "dark" ? t("theme.dark") : t("theme.light")}
        >
          {theme === "dark" ? (
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
              <path fillRule="evenodd" d="M7.455 2.004a.75.75 0 0 1 .26.77 7 7 0 0 0 9.958 7.967.75.75 0 0 1 1.067.853A8.5 8.5 0 1 1 6.647 1.921a.75.75 0 0 1 .808.083Z" clipRule="evenodd" />
            </svg>
          ) : (
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
              <path d="M10 2a.75.75 0 0 1 .75.75v1.5a.75.75 0 0 1-1.5 0v-1.5A.75.75 0 0 1 10 2ZM10 15a.75.75 0 0 1 .75.75v1.5a.75.75 0 0 1-1.5 0v-1.5A.75.75 0 0 1 10 15ZM10 7a3 3 0 1 0 0 6 3 3 0 0 0 0-6ZM15.657 5.404a.75.75 0 1 0-1.06-1.06l-1.061 1.06a.75.75 0 0 0 1.06 1.06l1.06-1.06ZM6.464 14.596a.75.75 0 1 0-1.06-1.06l-1.06 1.06a.75.75 0 0 0 1.06 1.06l1.06-1.06ZM18 10a.75.75 0 0 1-.75.75h-1.5a.75.75 0 0 1 0-1.5h1.5A.75.75 0 0 1 18 10ZM5 10a.75.75 0 0 1-.75.75h-1.5a.75.75 0 0 1 0-1.5h1.5A.75.75 0 0 1 5 10ZM14.596 15.657a.75.75 0 0 0 1.06-1.06l-1.06-1.061a.75.75 0 1 0-1.06 1.06l1.06 1.06ZM5.404 6.464a.75.75 0 0 0 1.06-1.06l-1.06-1.06a.75.75 0 1 0-1.06 1.06l1.06 1.06Z" />
            </svg>
          )}
        </button>
        <button
          onClick={toggleLocale}
          className="px-2 py-1.5 rounded-md text-xs font-medium text-fg-muted hover:text-fg hover:bg-overlay"
        >
          {locale === "en" ? "中文" : "EN"}
        </button>
      </div>

      <div className="w-full max-w-sm">
        {/* Branding */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-accent/10 border border-accent/20 mb-3">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6 text-accent">
              <path fillRule="evenodd" d="M14.615 1.595a.75.75 0 0 1 .359.852L12.982 9.75h7.268a.75.75 0 0 1 .548 1.262l-10.5 11.25a.75.75 0 0 1-1.272-.71l1.992-7.302H3.75a.75.75 0 0 1-.548-1.262l10.5-11.25a.75.75 0 0 1 .913-.143Z" clipRule="evenodd" />
            </svg>
          </div>
          <h1 className="text-xl font-bold text-fg">{t("login.title")}</h1>
          <p className="text-fg-secondary mt-1.5 text-[13px]">
            {t("login.subtitle")}
          </p>
        </div>

        {/* Login / Register card */}
        <form
          onSubmit={handleSubmit}
          className="bg-surface border border-edge rounded-lg p-5 space-y-4"
        >
          {hasUsers === null ? (
            <div className="text-center py-4 text-xs text-fg-muted">
              {t("sessions.loading")}
            </div>
          ) : (
            <>
              <div className="text-center mb-2">
                <h2 className="text-sm font-semibold text-fg">
                  {isRegister ? t("login.createAccount") : t("login.signIn")}
                </h2>
                <p className="text-[11px] text-fg-muted mt-1">
                  {isRegister ? t("login.createAccountHint") : t("login.signInHint")}
                </p>
              </div>

              <div>
                <label
                  htmlFor="username"
                  className="block text-xs font-medium text-fg-secondary mb-1.5 uppercase tracking-wide"
                >
                  {t("login.username")}
                </label>
                <input
                  id="username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder={t("login.usernamePlaceholder")}
                  autoComplete="username"
                  className="w-full bg-canvas border border-edge text-fg rounded-md px-3 py-2 text-sm
                    placeholder-fg-muted focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent"
                />
              </div>

              <div>
                <label
                  htmlFor="password"
                  className="block text-xs font-medium text-fg-secondary mb-1.5 uppercase tracking-wide"
                >
                  {t("login.password")}
                </label>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={t("login.passwordPlaceholder")}
                  autoComplete={isRegister ? "new-password" : "current-password"}
                  className="w-full bg-canvas border border-edge text-fg rounded-md px-3 py-2 text-sm
                    placeholder-fg-muted focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent"
                />
              </div>

              {error && (
                <div className="bg-danger/10 border border-danger/20 text-danger text-[13px] rounded-md px-3 py-2.5">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading || !username.trim() || !password.trim()}
                className="w-full bg-accent hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed
                  text-white font-medium py-2 rounded-md text-sm"
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    {t("login.connecting")}
                  </span>
                ) : isRegister ? (
                  t("login.createAccount")
                ) : (
                  t("login.signIn")
                )}
              </button>
            </>
          )}
        </form>

        <p className="text-center text-[11px] text-fg-muted mt-5">
          {t("login.footer")}{" "}
          <code className="text-fg-secondary">{getBaseUrl()}</code>
        </p>
      </div>
    </div>
  );
}
