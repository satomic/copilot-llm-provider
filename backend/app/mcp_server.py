"""
MCP (Model Context Protocol) server for Copilot LLM Provider.

Exposes Copilot-backed LLM models as MCP tools so that MCP clients
(Claude Desktop, Claude Code, etc.) can use them directly.

Usage:
    python -m backend.app.mcp_server

Transport: stdio (standard for MCP servers)
"""

import asyncio
import json
import logging
import sys
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from backend.app.providers.base import ChatCompletionRequest, ChatMessage
from backend.app.services.token_pool import get_token_pool

# Redirect logging to stderr (stdout is reserved for JSON-RPC in stdio transport)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

_pool_started = False


async def _ensure_pool() -> None:
    """Start the token pool if not already started."""
    global _pool_started
    if not _pool_started:
        pool = get_token_pool()
        if pool.active_count() == 0:
            logger.info("Starting token pool...")
            await pool.start_all()
        _pool_started = True
        logger.info(
            "Token pool ready: %d/%d active tokens",
            pool.active_count(),
            pool.token_count(),
        )


@asynccontextmanager
async def mcp_lifespan(server):  # noqa: ANN001
    """Initialize the token pool on MCP server startup."""
    await _ensure_pool()
    yield
    # Shutdown: stop all providers
    logger.info("Shutting down token pool...")
    await get_token_pool().stop_all()


mcp = FastMCP(
    "copilot-llm-provider",
    instructions="Access GitHub Copilot-backed LLM models (GPT-4.1, Claude Sonnet 4, o4-mini, etc.) via MCP tools.",
    lifespan=mcp_lifespan,
)


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def chat(
    message: str,
    model: str = "gpt-4.1",
    system_prompt: str = "",
    temperature: float = 1.0,
    max_tokens: int = 4096,
) -> str:
    """Send a message to a GitHub Copilot-backed LLM model and get a response.

    Args:
        message: The user message to send.
        model: Model ID to use (e.g. gpt-4.1, claude-sonnet-4, o4-mini). Use list_models to see available options.
        system_prompt: Optional system prompt to set context for the model.
        temperature: Sampling temperature (0.0 = deterministic, 2.0 = max randomness).
        max_tokens: Maximum number of tokens to generate.
    """
    await _ensure_pool()
    pool = get_token_pool()
    provider = pool.get_provider()
    if provider is None:
        return "Error: No active GitHub tokens available. Add tokens via the admin dashboard."

    messages: list[ChatMessage] = []
    if system_prompt:
        messages.append(ChatMessage(role="system", content=system_prompt))
    messages.append(ChatMessage(role="user", content=message))

    request = ChatCompletionRequest(
        messages=messages,
        model=model,
        stream=False,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    try:
        response = await provider.chat_completion(request)
        return response.content
    except Exception as exc:
        logger.error("Chat completion failed: %s", exc)
        return f"Error: {exc}"


@mcp.tool()
async def list_models() -> str:
    """List all available LLM models from GitHub Copilot.

    Returns model IDs, names, premium status, and billing multiplier.
    Use these model IDs with the chat tool.
    """
    await _ensure_pool()
    pool = get_token_pool()
    provider = pool.get_provider()
    if provider is None:
        return "Error: No active GitHub tokens available."

    try:
        models = await provider.list_models()
        lines = []
        for m in sorted(models, key=lambda x: (x.is_premium, x.id)):
            tag = "premium" if m.is_premium else "free"
            mult = f" (x{m.billing_multiplier})" if m.billing_multiplier else ""
            lines.append(f"- {m.id} [{tag}{mult}]")
        return f"Available models ({len(models)}):\n" + "\n".join(lines)
    except Exception as exc:
        logger.error("list_models failed: %s", exc)
        return f"Error: {exc}"


@mcp.tool()
async def get_quota() -> str:
    """Check GitHub Copilot premium request quota for all configured tokens.

    Shows entitlement, used requests, remaining percentage, and reset date.
    """
    await _ensure_pool()
    pool = get_token_pool()

    if pool.token_count() == 0:
        return "No GitHub tokens configured."

    try:
        quotas = await pool.fetch_all_quotas()
        lines = []
        for tid, quota_data in quotas.items():
            info = pool.get_token_info(tid)
            alias = info.alias if info else tid

            if "error" in quota_data:
                lines.append(f"**{alias}**: {quota_data['error']}")
                continue

            snapshots = quota_data.get("snapshots", {})
            pi = snapshots.get("premium_interactions") or snapshots.get("chat")
            if pi:
                entitlement = pi.get("entitlement_requests", "?")
                used = pi.get("used_requests", "?")
                remaining = pi.get("remaining_percentage", "?")
                reset = pi.get("reset_date", "unknown")
                lines.append(
                    f"**{alias}**: {used}/{entitlement} used "
                    f"({remaining}% remaining, resets {reset})"
                )
            else:
                lines.append(f"**{alias}**: {json.dumps(snapshots, indent=2)}")

        return "Quota status:\n" + "\n".join(lines)
    except Exception as exc:
        logger.error("get_quota failed: %s", exc)
        return f"Error: {exc}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the MCP server with stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
