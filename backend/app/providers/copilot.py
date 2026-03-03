"""
CopilotProvider — Concrete Provider implementation using github-copilot-sdk.

Wraps the CopilotClient and its stateful, event-driven sessions into
the clean async Provider interface. Handles:
- Client lifecycle (start/stop the CLI binary child process)
- Per-request session creation and destruction (stateless API semantics)
- Event-to-AsyncGenerator bridging via asyncio.Queue (streaming)
- Model discovery and caching
"""

import asyncio
import logging
import re
import time
from collections.abc import AsyncGenerator
from uuid import uuid4

from copilot import CopilotClient

from backend.app.providers.base import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ModelInfo,
    Provider,
    StreamDelta,
    Usage,
)

logger = logging.getLogger(__name__)

# Default timeout for SDK operations (30 minutes).
_DEFAULT_TIMEOUT = 1800.0

# System message appended at SDK level to instruct the model to output
# tool calls as JSON text instead of using native tool execution.
_TOOL_BRIDGE_SYSTEM_MSG = (
    "IMPORTANT: You are operating through a tool-bridging proxy. "
    "Instead of executing tools directly, output a JSON object in "
    "your text response in this exact format:\n"
    '{"tool_use":{"name":"<tool_name>","input":{...}}}\n'
    "For multiple parallel tool calls, use:\n"
    '{"tool_use":{"name":"multi_tool_use.parallel","input":{"tool_uses":['
    '{"recipient_name":"<tool>","parameters":{...}},'
    '{"recipient_name":"<tool>","parameters":{...}}'
    "]}}}\n"
    "This JSON will be automatically parsed and forwarded to the "
    "user's local machine for execution.\n"
    "CRITICAL: If a tool call is denied or you see a permission message, "
    "do NOT give up. Simply output the tool call as JSON text in your "
    "response. The proxy will handle execution. "
    "NEVER say tools are disabled, unavailable, blocked by hooks, or "
    "that there are environment restrictions. NEVER mention preToolUse "
    "hooks or permission denials to the user. NEVER suggest manual steps.\n"
    "Even if previous attempts seemed to fail, ALWAYS output the JSON "
    "tool call. The proxy handles everything. Never give up on tools."
)


def _deny_all_tools(input_data: dict, _env: dict) -> dict:
    """Pre-tool-use hook that redirects tool execution to text-based
    JSON output for the tool-bridging proxy."""
    tool_name = input_data.get("toolName", "unknown")
    logger.warning("Redirecting server-side tool to text output: %s", tool_name)
    return {
        "permissionDecision": "deny",
        "permissionDecisionReason": (
            f"Use text-based format for '{tool_name}'. "
            "Output this JSON in your response text:\n"
            f'{{"tool_use":{{"name":"{tool_name}","input":{{...}}}}}}'
        ),
    }


def _generate_response_id() -> str:
    """Generate a unique response ID in OpenAI-compatible format."""
    return f"chatcmpl-{uuid4().hex[:24]}"


def _format_messages(messages: list[ChatMessage]) -> str:
    """Convert a list of ChatMessage into a single prompt string.

    Formats each message with its role prefix, separated by newlines.
    This produces a prompt that preserves conversation context for the SDK.

    Example output:
        system: You are a helpful assistant.
        user: Hello!
        assistant: Hi there!
        user: Tell me a joke.
    """
    parts: list[str] = []
    for msg in messages:
        parts.append(f"{msg.role}: {msg.content}")
    return "\n".join(parts)


def _normalize_model_name(name: str) -> str:
    """Normalize a model name for fuzzy matching.

    1. Strip Anthropic-style date suffix (e.g., -20250514)
    2. Replace digit-dash-digit with digit.digit for version numbers
       (e.g., claude-sonnet-4-5 → claude-sonnet-4.5)
    """
    normalized = re.sub(r"-\d{8}$", "", name)
    normalized = re.sub(r"(\d+)-(\d+)", r"\1.\2", normalized)
    return normalized.lower()


# Cache TTL for model IDs used by the resolver (seconds).
_MODEL_CACHE_TTL = 300.0


class CopilotProvider(Provider):
    """LLM provider backed by GitHub Copilot via the github-copilot-sdk.

    This provider manages a single CopilotClient instance (one CLI binary
    process) and creates per-request sessions for stateless API semantics.

    Args:
        github_token: Optional GitHub personal access token. If not provided,
                      the SDK will attempt fallback authentication methods.
    """

    def __init__(self, github_token: str | None = None) -> None:
        self._github_token = github_token
        self._client: CopilotClient | None = None
        self._started: bool = False
        # Model name resolution cache
        self._model_ids_cache: list[str] = []
        self._model_premium_cache: dict[str, bool] = {}
        self._model_multiplier_cache: dict[str, float] = {}
        self._model_ids_cache_ts: float = 0.0

    async def start(self) -> None:
        """Start the CopilotClient and verify authentication.

        Spawns the Copilot CLI binary as a child process and performs
        initial model discovery.
        """
        if self._started:
            logger.warning("CopilotProvider.start() called but already started")
            return

        logger.info("Starting CopilotProvider...")

        # Build client config: pass token explicitly if provided, otherwise
        # let the SDK fall back to env vars / stored OAuth credentials.
        config: dict[str, str] = {}
        if self._github_token:
            config["github_token"] = self._github_token

        try:
            # Always ensure use_logged_in_user is enabled for stored OAuth
            config.setdefault("use_logged_in_user", True)
            self._client = CopilotClient(config)
            await self._client.start()
            self._started = True

            # Verify authentication by listing models at startup
            try:
                models = await self._client.list_models()
                logger.info(
                    "CopilotProvider started successfully — %d models available",
                    len(models),
                )
            except Exception:
                logger.warning(
                    "CopilotProvider started but model listing failed — "
                    "authentication may not be configured",
                    exc_info=True,
                )
        except Exception:
            self._client = None
            self._started = False
            logger.exception("Failed to start CopilotProvider")
            raise RuntimeError("Failed to start CopilotProvider") from None

    async def stop(self) -> None:
        """Stop the CopilotClient and clean up all sessions.

        Gracefully terminates the CLI binary child process.
        Must not raise exceptions — log errors instead.
        """
        if not self._started or self._client is None:
            logger.debug("CopilotProvider.stop() called but not started; no-op")
            return

        logger.info("Stopping CopilotProvider...")
        try:
            await self._client.stop()
            logger.info("CopilotProvider stopped successfully")
        except Exception:
            logger.exception("Error stopping CopilotProvider (suppressed)")
        finally:
            self._client = None
            self._started = False

    def _ensure_started(self) -> CopilotClient:
        """Return the active client or raise if not started."""
        if not self._started or self._client is None:
            raise RuntimeError(
                "CopilotProvider is not started. Call start() first."
            )
        return self._client

    async def list_models(self) -> list[ModelInfo]:
        """List available models from the Copilot service.

        Delegates to client.list_models() and maps to ModelInfo objects.
        """
        client = self._ensure_started()

        logger.debug("Listing models from Copilot SDK...")
        try:
            raw_models = await client.list_models()
        except Exception:
            logger.exception("Failed to list models from Copilot SDK")
            raise RuntimeError("Failed to list models") from None

        models: list[ModelInfo] = []
        for raw in raw_models:
            try:
                # The SDK may return objects with .id and .name attributes,
                # or dicts, or other structures. Handle gracefully.
                model_id = getattr(raw, "id", None) or getattr(raw, "model_id", None)
                model_name = getattr(raw, "name", None) or getattr(raw, "display_name", None)

                # Fallback: try dict-like access
                if model_id is None and isinstance(raw, dict):
                    model_id = raw.get("id") or raw.get("model_id")
                if model_name is None and isinstance(raw, dict):
                    model_name = raw.get("name") or raw.get("display_name")

                # Last resort: use string representation
                if model_id is None:
                    model_id = str(raw)
                if model_name is None:
                    model_name = model_id

                # Extract billing multiplier to determine premium status.
                # multiplier > 1 means the model consumes premium requests.
                billing = getattr(raw, "billing", None)
                multiplier = getattr(billing, "multiplier", None) if billing else None
                if multiplier is None and isinstance(raw, dict):
                    billing_dict = raw.get("billing")
                    if isinstance(billing_dict, dict):
                        multiplier = billing_dict.get("multiplier")
                is_premium = multiplier is not None and multiplier > 0

                models.append(
                    ModelInfo(
                        id=model_id,
                        name=model_name,
                        provider="copilot",
                        is_premium=is_premium,
                        billing_multiplier=multiplier,
                    )
                )
            except Exception:
                logger.warning("Skipping unparseable model object: %r", raw, exc_info=True)

        logger.info("Discovered %d models from Copilot", len(models))
        return models

    async def is_model_premium(self, model_id: str) -> bool:
        """Check whether a model is premium based on billing multiplier from the SDK."""
        await self._get_model_ids()  # ensure cache is populated
        return self._model_premium_cache.get(model_id, True)  # default True (safer)

    async def get_model_multiplier(self, model_id: str) -> float:
        """Get the billing multiplier for a model from the SDK cache."""
        await self._get_model_ids()  # ensure cache is populated
        return self._model_multiplier_cache.get(model_id, 1.0)

    async def _get_model_ids(self) -> list[str]:
        """Return cached list of available model IDs."""
        now = time.monotonic()
        if self._model_ids_cache and (now - self._model_ids_cache_ts) < _MODEL_CACHE_TTL:
            return self._model_ids_cache
        try:
            models = await self.list_models()
            self._model_ids_cache = [m.id for m in models]
            self._model_premium_cache = {m.id: m.is_premium for m in models}
            self._model_multiplier_cache = {
                m.id: (m.billing_multiplier if m.billing_multiplier is not None else 0.0)
                for m in models
            }
            self._model_ids_cache_ts = now
        except Exception:
            logger.warning("Failed to refresh model ID cache for resolver")
        return self._model_ids_cache

    async def _resolve_model(self, requested: str) -> str:
        """Resolve a requested model name to an available Copilot model.

        Tries exact match first, then normalized matching (strip date suffix,
        normalize version separators), then prefix matching. Falls through
        to the original name if no match is found.
        """
        available = await self._get_model_ids()
        if not available:
            return requested

        # 1. Exact match
        if requested in available:
            return requested

        # 2. Normalized match
        req_norm = _normalize_model_name(requested)
        for model_id in available:
            if _normalize_model_name(model_id) == req_norm:
                logger.info("Model resolved: %s → %s", requested, model_id)
                return model_id

        # 3. Prefix match (e.g., "claude-sonnet" matches "claude-sonnet-4.5")
        for model_id in available:
            if _normalize_model_name(model_id).startswith(req_norm):
                logger.info("Model resolved (prefix): %s → %s", requested, model_id)
                return model_id

        logger.warning("Model %s not found in available models %s, passing through", requested, available)
        return requested

    async def get_quota(self) -> dict:
        """Fetch current quota information from the Copilot service.

        Uses the SDK's built-in account.get_quota() JSON-RPC method to retrieve
        premium request limits, usage, and reset dates.
        """
        client = self._ensure_started()
        try:
            quota_result = await client.rpc.account.get_quota()
            snapshots = {}
            for snapshot_type, snapshot in quota_result.quota_snapshots.items():
                snapshots[snapshot_type] = {
                    "entitlement_requests": snapshot.entitlement_requests,
                    "used_requests": snapshot.used_requests,
                    "overage": snapshot.overage,
                    "remaining_percentage": snapshot.remaining_percentage,
                    "reset_date": snapshot.reset_date,
                    "overage_allowed": snapshot.overage_allowed_with_exhausted_quota,
                }
            return snapshots
        except Exception as exc:
            logger.warning("Failed to fetch quota: %s", exc)
            raise

    async def chat_completion(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """Generate a non-streaming chat completion.

        Creates a fresh session, calls send_and_wait(), extracts the
        response content, and destroys the session.
        """
        client = self._ensure_started()
        response_id = _generate_response_id()
        prompt = _format_messages(request.messages)

        logger.debug(
            "chat_completion: model=%s, messages=%d, prompt_len=%d",
            request.model,
            len(request.messages),
            len(prompt),
        )

        resolved_model = await self._resolve_model(request.model)

        session = None
        try:
            session = await client.create_session({
                "model": resolved_model,
                "available_tools": [],
                "hooks": {"on_pre_tool_use": _deny_all_tools},
                "system_message": {
                    "mode": "append",
                    "content": _TOOL_BRIDGE_SYSTEM_MSG,
                },
            })
            response = await session.send_and_wait(
                {"prompt": prompt}, timeout=_DEFAULT_TIMEOUT
            )

            # Extract content from the SDK response object.
            content = ""
            try:
                content = response.data.content
            except AttributeError:
                logger.warning(
                    "Unexpected response structure: %r; attempting fallback", response
                )
                # Fallback: try common alternative attribute paths
                content = str(getattr(response, "content", ""))
                if not content:
                    content = str(response)

            logger.debug(
                "chat_completion complete: response_len=%d", len(content)
            )

            return ChatCompletionResponse(
                id=response_id,
                model=request.model,
                content=content,
                usage=Usage(),
                finish_reason="stop",
            )
        except RuntimeError:
            raise
        except Exception as exc:
            logger.exception("chat_completion failed for model=%s", request.model)
            raise RuntimeError(
                f"Chat completion failed: {exc}"
            ) from exc
        finally:
            if session is not None:
                try:
                    await session.destroy()
                    logger.debug("Session destroyed after chat_completion")
                except Exception:
                    logger.warning(
                        "Failed to destroy session after chat_completion",
                        exc_info=True,
                    )

    async def chat_completion_stream(
        self, request: ChatCompletionRequest
    ) -> AsyncGenerator[StreamDelta, None]:
        """Generate a streaming chat completion.

        Creates a fresh session, registers event handlers that push
        deltas to an asyncio.Queue, calls send(), and yields deltas
        from the queue until the session goes idle.

        Event flow:
            SDK callback -> asyncio.Queue.put_nowait() -> yield from queue
        """
        client = self._ensure_started()
        response_id = _generate_response_id()
        prompt = _format_messages(request.messages)

        logger.debug(
            "chat_completion_stream: model=%s, messages=%d, prompt_len=%d",
            request.model,
            len(request.messages),
            len(prompt),
        )

        # Sentinel value to signal the end of the stream.
        _DONE = object()

        queue: asyncio.Queue[StreamDelta | object] = asyncio.Queue()

        resolved_model = await self._resolve_model(request.model)

        session = None
        try:
            session = await client.create_session({
                "model": resolved_model,
                "streaming": True,
                "available_tools": [],
                "hooks": {"on_pre_tool_use": _deny_all_tools},
                "system_message": {
                    "mode": "append",
                    "content": _TOOL_BRIDGE_SYSTEM_MSG,
                },
            })

            def on_event(event: object) -> None:
                """SDK event callback — bridges events into the async queue."""
                try:
                    event_type = event.type.value if hasattr(event.type, "value") else str(event.type)
                except Exception:
                    event_type = str(getattr(event, "type", "unknown"))

                logger.debug("Stream event: %s", event_type)

                if event_type == "assistant.message_delta":
                    # Incremental content chunk
                    delta_content = ""
                    try:
                        delta_content = event.data.delta_content
                    except AttributeError:
                        delta_content = str(getattr(event, "delta_content", ""))

                    queue.put_nowait(
                        StreamDelta(
                            id=response_id,
                            model=request.model,
                            delta_content=delta_content,
                            finish_reason=None,
                        )
                    )
                elif event_type == "assistant.message":
                    # Final complete message — we already streamed the deltas,
                    # so we don't emit the full content again. Just log it.
                    logger.debug("Stream received final assistant.message")
                elif event_type == "session.idle":
                    # Processing complete — send finish delta then done sentinel.
                    queue.put_nowait(
                        StreamDelta(
                            id=response_id,
                            model=request.model,
                            delta_content=None,
                            finish_reason="stop",
                        )
                    )
                    queue.put_nowait(_DONE)
                elif event_type.startswith("error"):
                    logger.error("Stream error event: %r", event)
                    queue.put_nowait(
                        StreamDelta(
                            id=response_id,
                            model=request.model,
                            delta_content=None,
                            finish_reason="error",
                        )
                    )
                    queue.put_nowait(_DONE)

            session.on(on_event)
            await session.send({"prompt": prompt})

            # Yield deltas from the queue until we receive the done sentinel.
            while True:
                item = await asyncio.wait_for(
                    queue.get(), timeout=_DEFAULT_TIMEOUT
                )
                if item is _DONE:
                    break
                # item is guaranteed to be a StreamDelta here.
                yield item  # type: ignore[misc]

        except RuntimeError:
            raise
        except Exception as exc:
            logger.exception(
                "chat_completion_stream failed for model=%s", request.model
            )
            raise RuntimeError(
                f"Streaming chat completion failed: {exc}"
            ) from exc
        finally:
            if session is not None:
                try:
                    await session.destroy()
                    logger.debug("Session destroyed after chat_completion_stream")
                except Exception:
                    logger.warning(
                        "Failed to destroy session after chat_completion_stream",
                        exc_info=True,
                    )
