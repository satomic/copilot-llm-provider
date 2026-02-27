/**
 * TypeScript interfaces matching the backend API schemas.
 *
 * These types mirror the Pydantic models in:
 * - backend/app/schemas/openai.py
 * - backend/app/schemas/anthropic.py
 * - backend/app/providers/base.py
 *
 * Keep these in sync with the backend schemas when changes are made.
 */

// =============================================================================
// OpenAI-Compatible Types
// =============================================================================

/** A single message in a chat conversation (OpenAI format). */
export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

/** Token usage statistics. */
export interface Usage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

/** OpenAI Chat Completion request body. */
export interface ChatCompletionRequest {
  model: string;
  messages: ChatMessage[];
  stream?: boolean;
  temperature?: number;
  max_tokens?: number | null;
  top_p?: number | null;
  stop?: string | string[] | null;
  frequency_penalty?: number;
  presence_penalty?: number;
  n?: number;
  user?: string | null;
}

/** Generated message within a completion choice. */
export interface ChoiceMessage {
  role: "assistant";
  content: string;
}

/** A single completion choice. */
export interface Choice {
  index: number;
  message: ChoiceMessage;
  finish_reason: "stop" | "length" | null;
}

/** OpenAI Chat Completion response body (non-streaming). */
export interface ChatCompletionResponse {
  id: string;
  object: "chat.completion";
  created: number;
  model: string;
  choices: Choice[];
  usage: Usage;
}

/** Delta content within a streaming chunk. */
export interface DeltaContent {
  role?: "assistant" | null;
  content?: string | null;
}

/** A single choice within a streaming chunk. */
export interface ChunkChoice {
  index: number;
  delta: DeltaContent;
  finish_reason: "stop" | "length" | null;
}

/** OpenAI Chat Completion streaming chunk. */
export interface ChatCompletionChunk {
  id: string;
  object: "chat.completion.chunk";
  created: number;
  model: string;
  choices: ChunkChoice[];
}

/** A single model object in the models list. */
export interface ModelObject {
  id: string;
  object: "model";
  created: number;
  owned_by: string;
}

/** OpenAI Models list response. */
export interface ModelList {
  object: "list";
  data: ModelObject[];
}

// =============================================================================
// Anthropic-Compatible Types
// =============================================================================

/** A single message in a conversation (Anthropic format — no system role). */
export interface AnthropicMessage {
  role: "user" | "assistant";
  content: string;
}

/** Anthropic Messages API request body. */
export interface MessagesRequest {
  model: string;
  messages: AnthropicMessage[];
  max_tokens: number;
  system?: string | null;
  stream?: boolean;
  temperature?: number;
  top_p?: number | null;
  stop_sequences?: string[] | null;
}

/** A text content block in an Anthropic response. */
export interface TextBlock {
  type: "text";
  text: string;
}

/** Anthropic token usage statistics. */
export interface AnthropicUsage {
  input_tokens: number;
  output_tokens: number;
}

/** Anthropic Messages API response body (non-streaming). */
export interface MessagesResponse {
  id: string;
  type: "message";
  role: "assistant";
  content: TextBlock[];
  model: string;
  stop_reason: "end_turn" | "max_tokens" | "stop_sequence" | null;
  stop_sequence: string | null;
  usage: AnthropicUsage;
}

// =============================================================================
// Anthropic Streaming Event Types
// =============================================================================

/** Sent once at the start of a streaming response. */
export interface MessageStartEvent {
  type: "message_start";
  message: MessagesResponse;
}

/** Sent at the start of each content block. */
export interface ContentBlockStartEvent {
  type: "content_block_start";
  index: number;
  content_block: TextBlock;
}

/** Incremental text delta. */
export interface TextDelta {
  type: "text_delta";
  text: string;
}

/** Sent for each incremental update to a content block. */
export interface ContentBlockDeltaEvent {
  type: "content_block_delta";
  index: number;
  delta: TextDelta;
}

/** Sent when a content block is complete. */
export interface ContentBlockStopEvent {
  type: "content_block_stop";
  index: number;
}

/** Final message metadata. */
export interface MessageDeltaEvent {
  type: "message_delta";
  delta: {
    stop_reason: "end_turn" | "max_tokens" | "stop_sequence" | null;
    stop_sequence: string | null;
  };
  usage: {
    output_tokens: number;
  };
}

/** Final event in a streaming response. */
export interface MessageStopEvent {
  type: "message_stop";
}

/** Union of all Anthropic streaming event types. */
export type AnthropicStreamEvent =
  | MessageStartEvent
  | ContentBlockStartEvent
  | ContentBlockDeltaEvent
  | ContentBlockStopEvent
  | MessageDeltaEvent
  | MessageStopEvent;

// =============================================================================
// Error Types
// =============================================================================

/** OpenAI error response. */
export interface ErrorResponse {
  error: {
    message: string;
    type: string;
    code: string | null;
    param: string | null;
  };
}

/** Anthropic error response. */
export interface AnthropicErrorResponse {
  type: "error";
  error: {
    type: string;
    message: string;
  };
}
