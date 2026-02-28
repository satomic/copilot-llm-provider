import type {
  ChatCompletionRequest,
  ChatCompletionResponse,
  ChatCompletionChunk,
  ModelList,
} from "@/types/api";
import { parseSSEStream } from "@/hooks/useSSE";

/**
 * Build the Authorization header if an API key is provided.
 */
function authHeaders(token: string): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

/**
 * Generic error extractor — tries to parse the OpenAI error format,
 * falls back to status text.
 */
async function handleErrorResponse(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (body?.error?.message) {
      return body.error.message;
    }
    return JSON.stringify(body);
  } catch {
    return response.statusText || `HTTP ${response.status}`;
  }
}

/**
 * Fetch the list of available models.
 */
export async function fetchModels(token: string): Promise<ModelList> {
  const response = await fetch("/v1/models", {
    headers: authHeaders(token),
  });

  if (!response.ok) {
    const msg = await handleErrorResponse(response);
    throw new Error(`Failed to fetch models: ${msg}`);
  }

  return response.json();
}

/**
 * Non-streaming chat completion.
 */
export async function chatCompletion(
  token: string,
  request: ChatCompletionRequest
): Promise<ChatCompletionResponse> {
  const response = await fetch("/v1/chat/completions", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ ...request, stream: false }),
  });

  if (!response.ok) {
    const msg = await handleErrorResponse(response);
    throw new Error(`Chat completion failed: ${msg}`);
  }

  return response.json();
}

/**
 * Streaming chat completion — parses SSE and delivers chunks via callbacks.
 */
export async function chatCompletionStream(
  token: string,
  request: ChatCompletionRequest,
  onDelta: (chunk: ChatCompletionChunk) => void,
  onDone: () => void
): Promise<void> {
  const response = await fetch("/v1/chat/completions", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ ...request, stream: true }),
  });

  if (!response.ok) {
    const msg = await handleErrorResponse(response);
    throw new Error(`Streaming chat completion failed: ${msg}`);
  }

  await parseSSEStream(response, onDelta, onDone);
}

/**
 * Health check — returns true if the server is reachable.
 */
export async function healthCheck(token: string): Promise<boolean> {
  try {
    const response = await fetch("/health", {
      headers: authHeaders(token),
    });
    return response.ok;
  } catch {
    return false;
  }
}

// ============================================================================
// Admin API
// ============================================================================

export interface AuthStatus {
  auth_enabled: boolean;
  api_key_preview: string | null;
}

/**
 * Get the current authentication status from the server.
 */
export async function getAuthStatus(): Promise<AuthStatus> {
  const response = await fetch("/api/admin/auth-status");
  return response.json();
}

/**
 * Set the server API key. Requires current key if one is already set.
 */
export async function setServerApiKey(
  newKey: string,
  currentKey?: string
): Promise<void> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (currentKey) {
    headers["Authorization"] = `Bearer ${currentKey}`;
  }
  const response = await fetch("/api/admin/set-api-key", {
    method: "POST",
    headers,
    body: JSON.stringify({ api_key: newKey }),
  });
  if (!response.ok) {
    const msg = await handleErrorResponse(response);
    throw new Error(msg);
  }
}

/**
 * Remove the server API key (disable authentication).
 */
export async function removeServerApiKey(currentKey: string): Promise<void> {
  const response = await fetch("/api/admin/api-key", {
    method: "DELETE",
    headers: authHeaders(currentKey),
  });
  if (!response.ok) {
    const msg = await handleErrorResponse(response);
    throw new Error(msg);
  }
}

// ============================================================================
// Usage Stats API
// ============================================================================

export interface UsageStats {
  total_requests: number;
  premium_requests: number;
  free_requests: number;
  models: Record<
    string,
    {
      total_requests: number;
      stream_requests: number;
      is_premium: boolean;
      multiplier?: number;
      last_used: string;
    }
  >;
  recent_daily: Record<
    string,
    { total: number; premium: number; free: number }
  >;
  by_alias?: Record<
    string,
    { total_requests: number; premium_requests: number; models: Record<string, number> }
  >;
}

/**
 * Fetch usage statistics.
 */
export async function fetchUsageStats(token: string): Promise<UsageStats> {
  const response = await fetch("/api/stats", {
    headers: authHeaders(token),
  });
  if (!response.ok) {
    throw new Error("Failed to fetch usage stats");
  }
  return response.json();
}
