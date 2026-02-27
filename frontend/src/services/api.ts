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
function authHeaders(apiKey: string): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (apiKey) {
    headers["Authorization"] = `Bearer ${apiKey}`;
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
export async function fetchModels(apiKey: string): Promise<ModelList> {
  const response = await fetch("/v1/models", {
    headers: authHeaders(apiKey),
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
  apiKey: string,
  request: ChatCompletionRequest
): Promise<ChatCompletionResponse> {
  const response = await fetch("/v1/chat/completions", {
    method: "POST",
    headers: authHeaders(apiKey),
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
  apiKey: string,
  request: ChatCompletionRequest,
  onDelta: (chunk: ChatCompletionChunk) => void,
  onDone: () => void
): Promise<void> {
  const response = await fetch("/v1/chat/completions", {
    method: "POST",
    headers: authHeaders(apiKey),
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
export async function healthCheck(apiKey: string): Promise<boolean> {
  try {
    const response = await fetch("/health", {
      headers: authHeaders(apiKey),
    });
    return response.ok;
  } catch {
    return false;
  }
}
