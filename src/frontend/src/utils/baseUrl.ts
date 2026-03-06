/**
 * Return the backend origin for display in CLI Reference / API Reference.
 *
 * - Dev mode:  uses VITE_BACKEND_URL (set in .env.development)
 * - Production: frontend is served by the backend, so window.location.origin works.
 */
export function getBaseUrl(): string {
  const env = import.meta.env.VITE_BACKEND_URL;
  if (env) return env.replace(/\/+$/, "");

  const { protocol, hostname, port } = window.location;
  return `${protocol}//${hostname}${port ? `:${port}` : ""}`;
}
