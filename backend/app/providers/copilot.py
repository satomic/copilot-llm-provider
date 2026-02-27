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

                models.append(
                    ModelInfo(id=model_id, name=model_name, provider="copilot")
                )
            except Exception:
                logger.warning("Skipping unparseable model object: %r", raw, exc_info=True)

        logger.info("Discovered %d models from Copilot", len(models))
        return models

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

        session = None
        try:
            session = await client.create_session({"model": request.model})
            response = await session.send_and_wait({"prompt": prompt})

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

        session = None
        try:
            session = await client.create_session(
                {"model": request.model, "streaming": True}
            )

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
                item = await queue.get()
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
