import type { ChatCompletionChunk } from "@/types/api";

/**
 * Parses an SSE stream from a fetch Response.
 *
 * The server sends lines in the format:
 *   data: {"id": "...", ...}\n\n
 *
 * The stream terminates with:
 *   data: [DONE]\n\n
 *
 * This function handles partial chunks that may be split across reads.
 */
export async function parseSSEStream(
  response: Response,
  onDelta: (chunk: ChatCompletionChunk) => void,
  onDone: () => void
): Promise<void> {
  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("Response body is not readable");
  }

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        // Stream ended without [DONE] — still call onDone
        onDone();
        break;
      }

      buffer += decoder.decode(value, { stream: true });

      // Process complete lines from the buffer
      const lines = buffer.split("\n");
      // Keep the last (possibly incomplete) line in the buffer
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();

        // Skip empty lines and comments
        if (trimmed === "" || trimmed.startsWith(":")) {
          continue;
        }

        // SSE data lines start with "data: "
        if (trimmed.startsWith("data: ")) {
          const payload = trimmed.slice(6); // Remove "data: " prefix

          if (payload === "[DONE]") {
            onDone();
            return;
          }

          try {
            const parsed: ChatCompletionChunk = JSON.parse(payload);
            onDelta(parsed);
          } catch {
            // Skip malformed JSON lines
            console.warn("Failed to parse SSE chunk:", payload);
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
