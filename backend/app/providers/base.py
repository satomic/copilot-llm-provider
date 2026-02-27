"""
Abstract Provider interface — the central contract for all LLM providers.

This is the MOST CRITICAL file in the project. Every layer depends on these
types and the Provider ABC. The API layer converts wire formats to/from these
types; the service layer orchestrates them; concrete providers implement them.

Design principles:
- Provider-agnostic: nothing here references Copilot, OpenAI, or Anthropic specifics.
- Async-native: all I/O methods are async.
- Streaming-first: chat_completion_stream returns an AsyncGenerator of deltas.
- Immutable data: all data classes use frozen=True or are Pydantic models.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field


# =============================================================================
# Data Models
# =============================================================================


@dataclass(frozen=True)
class ChatMessage:
    """A single message in a chat conversation.

    Attributes:
        role: The role of the message author. One of "system", "user", "assistant".
        content: The text content of the message.
    """

    role: str
    content: str


@dataclass(frozen=True)
class Usage:
    """Token usage statistics for a completion.

    Attributes:
        prompt_tokens: Number of tokens in the prompt.
        completion_tokens: Number of tokens in the completion.
        total_tokens: Sum of prompt_tokens and completion_tokens.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class ChatCompletionRequest:
    """Internal representation of a chat completion request.

    This is the provider-agnostic request format. API layers convert
    from OpenAI/Anthropic wire formats into this type before calling
    the provider.

    Attributes:
        messages: The conversation history as a list of ChatMessage.
        model: The model ID to use for completion (e.g., "gpt-4.1").
        stream: Whether to stream the response as deltas.
        temperature: Sampling temperature (0.0 = deterministic, 2.0 = max randomness).
        max_tokens: Maximum number of tokens to generate. None means provider default.
        top_p: Nucleus sampling parameter. None means provider default.
        stop: Stop sequences. Generation stops when any of these are produced.
    """

    messages: list[ChatMessage]
    model: str
    stream: bool = False
    temperature: float = 1.0
    max_tokens: int | None = None
    top_p: float | None = None
    stop: list[str] | None = None


@dataclass(frozen=True)
class ChatCompletionResponse:
    """Internal representation of a chat completion response.

    Returned by Provider.chat_completion() for non-streaming requests.
    The API layer converts this into the appropriate wire format.

    Attributes:
        id: Unique identifier for this completion.
        model: The model ID that generated this completion.
        content: The generated text content.
        usage: Token usage statistics.
        finish_reason: Why generation stopped. One of "stop", "length", "error".
    """

    id: str
    model: str
    content: str
    usage: Usage = field(default_factory=Usage)
    finish_reason: str = "stop"


@dataclass(frozen=True)
class StreamDelta:
    """A single streaming delta from a chat completion.

    Yielded by Provider.chat_completion_stream() as an AsyncGenerator.
    Each delta contains either new content or a finish signal.

    Attributes:
        id: Unique identifier for the parent completion (same across all deltas).
        model: The model ID generating this stream.
        delta_content: New text content in this delta, or None if this is a control delta.
        finish_reason: Set on the final delta to indicate why generation stopped.
                       None for all content deltas.
    """

    id: str
    model: str
    delta_content: str | None = None
    finish_reason: str | None = None


@dataclass(frozen=True)
class ModelInfo:
    """Information about an available LLM model.

    Attributes:
        id: Unique model identifier (e.g., "gpt-4.1", "claude-sonnet-4").
        name: Human-readable display name for the model.
        provider: The provider that serves this model (e.g., "copilot").
    """

    id: str
    name: str
    provider: str


# =============================================================================
# Abstract Provider Interface
# =============================================================================


class Provider(ABC):
    """Abstract base class for LLM providers.

    Concrete implementations (e.g., CopilotProvider) must implement all
    abstract methods. The application uses a single Provider instance
    throughout its lifetime, initialized at startup and stopped at shutdown.

    Lifecycle:
        1. provider = ConcreteProvider(settings)
        2. await provider.start()     # Initialize resources (SDK client, etc.)
        3. ... handle requests ...     # Call list_models, chat_completion, etc.
        4. await provider.stop()      # Clean up resources

    Thread safety:
        Providers must be safe to call concurrently from multiple async tasks.
        The underlying session management handles concurrency control.
    """

    @abstractmethod
    async def start(self) -> None:
        """Initialize the provider and its resources.

        Called once during application startup. Should initialize the
        underlying SDK client, verify authentication, and prepare for
        handling requests.

        Raises:
            RuntimeError: If initialization fails (e.g., auth failure, SDK error).
        """
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully shut down the provider and release resources.

        Called once during application shutdown. Should stop the SDK client,
        destroy all active sessions, and clean up any resources.
        Must not raise exceptions — log errors instead.
        """
        ...

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        """Return the list of available models.

        Queries the underlying provider for available models. Results may
        be cached by the implementation for performance.

        Returns:
            A list of ModelInfo objects describing available models.

        Raises:
            RuntimeError: If the provider is not started or model listing fails.
        """
        ...

    @abstractmethod
    async def chat_completion(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """Generate a complete chat response (non-streaming).

        Creates a session, sends the messages, waits for the full response,
        then destroys the session. This provides stateless API semantics
        on top of the stateful SDK.

        Args:
            request: The chat completion request with messages and parameters.

        Returns:
            A ChatCompletionResponse with the generated content and usage stats.

        Raises:
            ValueError: If the requested model is not available.
            RuntimeError: If the provider encounters an error during generation.
        """
        ...

    @abstractmethod
    async def chat_completion_stream(
        self, request: ChatCompletionRequest
    ) -> AsyncGenerator[StreamDelta, None]:
        """Generate a streaming chat response.

        Creates a session, sends the messages, and yields deltas as they
        arrive from the SDK. The session is destroyed after the stream
        completes (or on error).

        Uses asyncio.Queue internally to bridge SDK event callbacks to
        the async generator pattern.

        Args:
            request: The chat completion request with messages and parameters.

        Yields:
            StreamDelta objects containing incremental content or finish signal.

        Raises:
            ValueError: If the requested model is not available.
            RuntimeError: If the provider encounters an error during streaming.
        """
        ...
        # Required for AsyncGenerator return type annotation
        yield  # type: ignore[misc]  # pragma: no cover
