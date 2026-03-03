"""
Anthropic-compatible messages endpoint.

Implements POST /v1/messages following the Anthropic Messages API specification.
Supports both streaming (SSE) and non-streaming response modes.
Includes tool bridging: model outputs tool_use JSON which is returned to the
client as proper Anthropic tool_use blocks, ensuring tools execute client-side.
"""

import json
import logging
import re
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from backend.app.core.auth import (
    AuthInfo,
    check_model_permission,
    check_usage_limits,
    record_api_key_usage,
    verify_api_key,
)
from backend.app.core.dependencies import get_provider
from backend.app.providers.base import (
    ChatCompletionRequest as InternalRequest,
    ChatMessage,
    Provider,
)
from backend.app.schemas.anthropic import (
    AnthropicErrorDetail,
    AnthropicErrorResponse,
    AnthropicUsage,
    ContentBlockDeltaEvent,
    ContentBlockStartEvent,
    ContentBlockStopEvent,
    MessageDeltaEvent,
    MessageDeltaPayload,
    MessageDeltaUsage,
    MessageStartEvent,
    MessageStopEvent,
    MessagesRequest,
    MessagesResponse,
    PingEvent,
    TextBlock,
)
from backend.app.services.session_store import SessionRecord, get_session_store
from backend.app.services.usage_tracker import get_usage_tracker

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Content extraction helpers
# =============================================================================


def _extract_text_content(content: str | list[Any]) -> str:
    """Extract plain text from Anthropic message content."""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict):
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
        elif hasattr(block, "text") and block.text is not None:
            parts.append(block.text)
    return "".join(parts)


def _extract_system_text(system: str | list | None) -> str | None:
    """Extract plain text from the system field (string or list of content blocks)."""
    if system is None:
        return None
    if isinstance(system, str):
        return system
    parts: list[str] = []
    for block in system:
        if isinstance(block, dict) and block.get("text"):
            parts.append(block["text"])
    return "\n".join(parts) if parts else None


def _content_blocks_to_text(content: str | list[Any]) -> str:
    """Convert content blocks (including tool_use/tool_result) to text representation."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            if hasattr(block, "text") and block.text is not None:
                parts.append(block.text)
            continue
        block_type = block.get("type")
        if block_type == "text" and isinstance(block.get("text"), str):
            parts.append(block["text"])
        elif block_type == "tool_result":
            tool_use_id = block.get("tool_use_id", "")
            result_content = block.get("content", "")
            if isinstance(result_content, list):
                result_text = _content_blocks_to_text(result_content)
            else:
                result_text = str(result_content)
            parts.append(f"[tool_result id={tool_use_id}] {result_text}")
        elif block_type == "tool_use":
            name = block.get("name", "")
            tool_use_id = block.get("id", "")
            tool_input = block.get("input", {})
            input_json = json.dumps(tool_input, ensure_ascii=False)
            parts.append(
                f"[tool_use id={tool_use_id} name={name}] {input_json}"
            )
    return "\n".join(p for p in parts if p)


# =============================================================================
# Tool bridging: prompt construction
# =============================================================================


def _has_tools(request: MessagesRequest) -> bool:
    return isinstance(request.tools, list) and len(request.tools) > 0


def _is_agentic_client(request: MessagesRequest) -> bool:
    """Detect if the request originates from an agentic coding client
    (e.g. Claude Code, Cursor, Windsurf) by inspecting the system prompt."""
    system_text = _extract_system_text(request.system)
    if not system_text:
        return False
    # Claude Code always includes this in its system prompt
    markers = ["Claude Code", "claude-code", "You are Claude Code"]
    return any(m in system_text for m in markers)


def _build_tool_aware_prompt(request: MessagesRequest) -> list[ChatMessage]:
    """Build ChatMessage list with tool instructions injected into the prompt.

    When tools are present, the prompt includes:
    1. Tool definitions and usage instructions
    2. Full conversation history with tool_use/tool_result serialized
    """
    messages: list[ChatMessage] = []

    # System message
    system_text = _extract_system_text(request.system)
    if system_text:
        messages.append(ChatMessage(role="system", content=system_text))

    # Inject tool instructions when tools are provided
    if _has_tools(request):
        tool_lines: list[str] = []
        for tool in request.tools:
            if not isinstance(tool, dict):
                continue
            name = tool.get("name")
            if not isinstance(name, str):
                continue
            description = tool.get("description", "")
            schema = tool.get("input_schema", {})
            schema_json = json.dumps(schema, ensure_ascii=False)
            tool_lines.append(
                f"- {name}: description={description}; "
                f"input_schema={schema_json}"
            )

        is_agentic = _is_agentic_client(request)

        tool_instruction = (
            "CRITICAL INSTRUCTION — Tool Bridging Proxy\n"
            "You are operating through a tool-bridging proxy. "
            "You DO have full tool access. Your tool calls will be "
            "forwarded to the user's local machine and executed there.\n\n"
            "When you need to perform ANY action (read/write/edit files, "
            "run commands, search, etc.), respond with a JSON object:\n"
            '{"tool_use":{"name":"<tool_name>","input":{...}}}\n\n'
            "For parallel tool calls, use:\n"
            '{"tool_use":{"name":"multi_tool_use.parallel","input":{"tool_uses":['
            '{"recipient_name":"<tool1>","parameters":{...}},'
            '{"recipient_name":"<tool2>","parameters":{...}}'
            "]}}}\n\n"
            "Rules:\n"
            "1. ALWAYS use tools when the task requires actions. "
            "Your tool calls WILL be executed on the user's machine.\n"
            '2. NEVER say "I cannot execute tools", '
            '"I cannot run commands", "环境限制", "无法创建文件", '
            "or suggest manual steps. "
            "You CAN and MUST use tools.\n"
            "3. Output ONLY the JSON tool call — no markdown fences, "
            "no surrounding text.\n"
            "4. For pure text responses (no action needed), "
            "respond normally without JSON.\n"
            "5. Even if previous tool calls in this conversation appeared "
            "to fail or were not executed, KEEP using the JSON format. "
            "The proxy will handle forwarding. Never give up on tools."
        )

        # Agentic clients (Claude Code etc.) expect ALL actions via tools.
        # Never output code blocks for the user to manually save.
        if is_agentic:
            tool_instruction += (
                "\n6. NEVER output file contents as code blocks for the user "
                "to save manually. ALWAYS use the Write tool to create files "
                "and the Edit tool to modify files directly.\n"
                "7. For ANY task involving file creation, file editing, or "
                "command execution, you MUST output a tool call JSON. "
                "The user's IDE will execute it automatically.\n"
                "8. Do NOT ask the user to do anything manually. "
                "You are an autonomous coding agent — act, don't instruct."
            )
        if tool_lines:
            tool_instruction += (
                "\n\nAvailable tools:\n" + "\n".join(tool_lines)
            )

        messages.append(ChatMessage(role="system", content=tool_instruction))

    # Conversation messages (serialize tool_use/tool_result blocks as text)
    for msg in request.messages:
        text = _content_blocks_to_text(msg.content)
        if text:
            messages.append(ChatMessage(role=msg.role, content=text))

    return messages


# =============================================================================
# Tool bridging: response parsing
# =============================================================================


def _extract_inline_json_objects(text: str) -> list[dict[str, Any]]:
    """Extract all top-level JSON objects from a string that may contain mixed text."""
    objs: list[dict[str, Any]] = []
    n = len(text)
    i = 0
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        depth = 0
        in_str = False
        escape = False
        j = i
        while j < n:
            ch = text[j]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        snippet = text[i : j + 1]
                        try:
                            parsed = json.loads(snippet)
                        except Exception:
                            pass
                        else:
                            if isinstance(parsed, dict):
                                objs.append(parsed)
                        break
            j += 1
        i += 1
    return objs


def _resolve_tool_name(
    candidate_name: str,
    candidate_input: dict[str, Any],
    tools: list[dict[str, Any]],
) -> tuple[str, dict[str, Any]] | None:
    """Resolve a candidate tool name against the allowed tool list with fuzzy matching."""
    if not tools:
        return candidate_name, candidate_input

    allowed_names = [
        t.get("name") for t in tools if isinstance(t, dict) and isinstance(t.get("name"), str)
    ]
    if not allowed_names:
        return None

    # Exact match
    if candidate_name in allowed_names:
        return candidate_name, candidate_input

    # Normalized match (lowercase + alphanumeric only)
    def _norm(s: str) -> str:
        return "".join(ch.lower() for ch in s if ch.isalnum())

    wanted = _norm(candidate_name)
    for allowed_name in allowed_names:
        normalized = _norm(allowed_name)
        if normalized == wanted:
            return allowed_name, candidate_input
        if wanted and (wanted in normalized or normalized in wanted):
            return allowed_name, candidate_input

    # Fallback: if only one tool available, bind to it
    if len(allowed_names) == 1:
        return allowed_names[0], candidate_input

    return None


_TOOL_REFUSAL_PATTERNS = [
    # Direct refusal
    "环境限制", "无法创建", "无法直接", "无法自动", "暂时无法",
    "无法执行", "请自行", "请手动",
    "cannot execute", "cannot create", "cannot run",
    "not able to", "unable to execute", "unable to create",
    "environment restriction", "tools are disabled",
    # Passive refusal: giving code for user to save manually
    "你可以将此内容保存", "你可以将以下内容保存", "保存为",
    "你可以手动", "请复制", "可以复制",
    "you can save", "save it as", "copy and paste",
]


def _looks_like_tool_refusal(text: str, is_agentic: bool = False) -> bool:
    """Detect if the model's response is a refusal to use tools.

    For agentic clients, also detect "passive refusal" where the model
    outputs code blocks and tells the user to save them manually.
    """
    lower = text.lower()
    if any(p in lower for p in _TOOL_REFUSAL_PATTERNS):
        return True
    # For agentic clients: code block + instructional text = passive refusal
    if is_agentic and "```" in text and ("手动" in lower or "保存" in lower):
        return True
    return False


def _unpack_parallel_tool_uses(
    tool_input: dict[str, Any], tools: list[dict[str, Any]]
) -> list[tuple[str, dict[str, Any]]]:
    """Unpack a multi_tool_use.parallel input into individual resolved tool calls.

    GPT-4.1 sometimes wraps multiple tool calls in:
    {"name":"multi_tool_use.parallel","input":{"tool_uses":[
        {"recipient_name":"Bash","parameters":{...}},
        {"recipient_name":"Read","parameters":{...}}
    ]}}
    """
    results: list[tuple[str, dict[str, Any]]] = []
    tool_uses = tool_input.get("tool_uses")
    if not isinstance(tool_uses, list):
        return results
    for entry in tool_uses:
        if not isinstance(entry, dict):
            continue
        # recipient_name / parameters is the GPT-4.1 format
        name = entry.get("recipient_name") or entry.get("name")
        params = entry.get("parameters") or entry.get("input") or {}
        if not isinstance(name, str) or not isinstance(params, dict):
            continue
        resolved = _resolve_tool_name(name, params, tools)
        if resolved is not None:
            results.append(resolved)
    return results


def _parse_tool_use_candidates(
    text: str, tools: list[dict[str, Any]]
) -> list[tuple[str, dict[str, Any]]]:
    """Parse model output text for tool_use candidates in various formats."""
    raw = text.strip()
    parsed: list[tuple[str, dict[str, Any]]] = []
    seen: set[tuple[str, str]] = set()

    def _append_unique(item: tuple[str, dict[str, Any]] | None) -> None:
        if item is None:
            return
        name, tool_input = item
        key = (name, json.dumps(tool_input, ensure_ascii=False, sort_keys=True))
        if key in seen:
            return
        seen.add(key)
        parsed.append((name, tool_input))

    # Strip markdown code fences
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()

    # 1) Pure JSON: {"tool_use":{"name":"...","input":{...}}} or {"name":"...","input":{...}}
    try:
        data = json.loads(raw)
    except Exception:
        data = None

    if isinstance(data, dict):
        tool_use = data.get("tool_use")
        candidate = tool_use if isinstance(tool_use, dict) else data
        name = candidate.get("name") or candidate.get("tool_name")
        tool_input = candidate.get("input", {})
        if isinstance(name, str) and isinstance(tool_input, dict):
            # Handle multi_tool_use.parallel: unpack into individual tool calls
            if name == "multi_tool_use.parallel":
                for sub in _unpack_parallel_tool_uses(tool_input, tools):
                    _append_unique(sub)
            else:
                _append_unique(_resolve_tool_name(name, tool_input, tools))

    # 1.5) Mixed text + inline JSON objects
    if not parsed:
        for obj in _extract_inline_json_objects(raw):
            tool_use = obj.get("tool_use") if isinstance(obj, dict) else None
            candidate = tool_use if isinstance(tool_use, dict) else obj
            if not isinstance(candidate, dict):
                continue
            name = candidate.get("name") or candidate.get("tool_name")
            tool_input = candidate.get("input", {})
            if isinstance(name, str) and isinstance(tool_input, dict):
                if name == "multi_tool_use.parallel":
                    for sub in _unpack_parallel_tool_uses(tool_input, tools):
                        _append_unique(sub)
                else:
                    _append_unique(_resolve_tool_name(name, tool_input, tools))

    # 2) Text protocol: [tool_use id=... name=X] {...}
    block_re = re.compile(
        r"\[tool_use[^\]]*name=([^\]\s]+)[^\]]*\]\s*(\{.*?\})(?=\s*\[tool_use|\s*$)",
        flags=re.DOTALL,
    )
    for match in block_re.finditer(raw):
        name = match.group(1).strip().strip("\"'")
        json_part = match.group(2).strip()
        try:
            parsed_input = json.loads(json_part)
        except Exception:
            parsed_input = None
        if isinstance(parsed_input, dict):
            _append_unique(_resolve_tool_name(name, parsed_input, tools))

    # 3) Single textual block fallback
    if not parsed:
        match = re.search(
            r"\[tool_use[^\]]*name=([^\]\s]+)[^\]]*\]\s*(\{.*\})", raw, flags=re.DOTALL
        )
        if match:
            name = match.group(1).strip().strip("\"'")
            json_part = match.group(2).strip()
            try:
                parsed_input = json.loads(json_part)
            except Exception:
                parsed_input = None
            if isinstance(parsed_input, dict):
                _append_unique(_resolve_tool_name(name, parsed_input, tools))

    return parsed


# =============================================================================
# Response builders
# =============================================================================


def _make_msg_id() -> str:
    return f"msg_{uuid.uuid4().hex[:24]}"


def _make_anthropic_error(
    status_code: int, message: str, error_type: str = "api_error"
) -> JSONResponse:
    error_resp = AnthropicErrorResponse(
        error=AnthropicErrorDetail(type=error_type, message=message)
    )
    return JSONResponse(status_code=status_code, content=error_resp.model_dump())


def _build_tool_use_response(
    model: str, tool_calls: list[tuple[str, dict[str, Any]]]
) -> dict[str, Any]:
    """Build an Anthropic response with tool_use content blocks."""
    content: list[dict[str, Any]] = []
    for tool_name, tool_input in tool_calls:
        content.append({
            "type": "tool_use",
            "id": f"toolu_{uuid.uuid4().hex}",
            "name": tool_name,
            "input": tool_input,
        })
    return {
        "id": _make_msg_id(),
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content,
        "stop_reason": "tool_use",
        "stop_sequence": None,
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }


def _messages_to_dicts(request: MessagesRequest) -> list[dict]:
    """Convert Anthropic messages to dicts for session recording."""
    result = []
    system_text = _extract_system_text(request.system)
    if system_text:
        result.append({"role": "system", "content": system_text})
    for msg in request.messages:
        result.append({"role": msg.role, "content": _extract_text_content(msg.content)})
    return result


def _map_finish_reason(internal_reason: str) -> str:
    mapping = {
        "stop": "end_turn",
        "length": "max_tokens",
        "stop_sequence": "stop_sequence",
    }
    return mapping.get(internal_reason, "end_turn")


# =============================================================================
# Endpoint
# =============================================================================


@router.post(
    "/v1/messages",
    response_model=None,
    summary="Create a message",
    description="Send a structured list of input messages and receive a model-generated "
    "response. Compatible with the Anthropic Messages API.",
)
async def create_message(
    request: MessagesRequest,
    fastapi_request: Request,
    provider: Provider = Depends(get_provider),
    auth: AuthInfo = Depends(verify_api_key),
):
    has_tool_defs = _has_tools(request)
    logger.info(
        "Anthropic messages request: model=%s stream=%s messages=%d tools=%d",
        request.model,
        request.stream,
        len(request.messages),
        len(request.tools) if has_tool_defs else 0,
    )

    start_time = time.time()
    client_ip = fastapi_request.client.host if fastapi_request.client else None

    # Capture GitHub token info from the provider selection
    github_token_id = getattr(fastapi_request.state, "github_token_id", None)
    github_token_alias = getattr(fastapi_request.state, "github_token_alias", None)

    # Check model permissions and usage limits for managed API keys
    check_model_permission(auth, request.model)
    is_premium = await provider.is_model_premium(request.model)
    check_usage_limits(auth, is_premium)

    # Track usage
    multiplier = await provider.get_model_multiplier(request.model)
    get_usage_tracker().record_request(
        model=request.model, api_format="anthropic", stream=request.stream,
        is_premium=is_premium, multiplier=multiplier,
        api_key_alias=auth.key_alias,
        github_token_alias=github_token_alias,
    )
    record_api_key_usage(auth, is_premium)

    # Track premium request on the token pool
    if is_premium and github_token_id:
        from backend.app.services.token_pool import get_token_pool
        get_token_pool().record_premium_request(github_token_id)

    # Build internal request with tool-aware prompt when tools are present
    try:
        if has_tool_defs:
            chat_messages = _build_tool_aware_prompt(request)
        else:
            chat_messages = []
            system_text = _extract_system_text(request.system)
            if system_text:
                chat_messages.append(ChatMessage(role="system", content=system_text))
            for msg in request.messages:
                text = _extract_text_content(msg.content)
                chat_messages.append(ChatMessage(role=msg.role, content=text))

        internal_request = InternalRequest(
            messages=chat_messages,
            model=request.model,
            stream=False if has_tool_defs else request.stream,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_p=request.top_p,
            stop=request.stop_sequences,
        )
    except Exception as exc:
        logger.warning("Failed to convert Anthropic request: %s", exc)
        return _make_anthropic_error(400, str(exc), "invalid_request_error")

    # === Non-streaming path (or tool-bridging with stream) ===
    if not request.stream or has_tool_defs:
        try:
            internal_response = await provider.chat_completion(internal_request)
            response_text = internal_response.content

            # Tool bridging: parse model output for tool_use candidates
            if has_tool_defs:
                is_agentic = _is_agentic_client(request)
                tool_calls = _parse_tool_use_candidates(response_text, request.tools)

                # Retry once if model refused instead of using tools
                if not tool_calls and _looks_like_tool_refusal(response_text, is_agentic):
                    logger.warning(
                        "Tool bridge: model refused tools, retrying with reinforcement. "
                        "Original response: %.200s", response_text,
                    )
                    retry_messages = list(internal_request.messages) + [
                        ChatMessage(role="assistant", content=response_text),
                        ChatMessage(
                            role="user",
                            content=(
                                "You MUST use the JSON tool call format. "
                                "Do NOT say you cannot use tools. "
                                "Output the tool call now:\n"
                                '{"tool_use":{"name":"<tool_name>","input":{...}}}'
                            ),
                        ),
                    ]
                    retry_request = InternalRequest(
                        messages=retry_messages,
                        model=internal_request.model,
                        stream=False,
                        temperature=internal_request.temperature,
                        max_tokens=internal_request.max_tokens,
                        top_p=internal_request.top_p,
                        stop=internal_request.stop,
                    )
                    retry_response = await provider.chat_completion(retry_request)
                    response_text = retry_response.content
                    tool_calls = _parse_tool_use_candidates(response_text, request.tools)
                    if tool_calls:
                        logger.info("Tool bridge: retry succeeded with %d tool_use", len(tool_calls))
                    else:
                        logger.warning("Tool bridge: retry also failed, returning text")

                if tool_calls:
                    logger.info(
                        "Tool bridge: parsed %d tool_use from model output", len(tool_calls)
                    )
                    duration_ms = (time.time() - start_time) * 1000
                    record = SessionRecord(
                        model=request.model,
                        api_format="anthropic",
                        messages=_messages_to_dicts(request),
                        response_content="[tool_use] " + json.dumps(
                            [{"name": n, "input": i} for n, i in tool_calls],
                            ensure_ascii=False,
                        ),
                        stream=request.stream,
                        duration_ms=round(duration_ms, 1),
                        client_ip=client_ip,
                        api_key_alias=auth.key_alias,
                        github_token_alias=github_token_alias,
                    )
                    get_session_store().save(record)

                    tool_response = _build_tool_use_response(request.model, tool_calls)

                    # For streaming requests with tools, emit SSE events
                    if request.stream:
                        return StreamingResponse(
                            _stream_tool_use_events(request.model, tool_calls),
                            media_type="text/event-stream",
                            headers={
                                "Cache-Control": "no-cache",
                                "Connection": "keep-alive",
                                "X-Accel-Buffering": "no",
                            },
                        )
                    return JSONResponse(content=tool_response)

            # Normal text response (no tools or no tool_use detected)
            stop_reason = _map_finish_reason(internal_response.finish_reason)
            response = MessagesResponse(
                id=_make_msg_id(),
                content=[TextBlock(text=response_text)],
                model=internal_response.model,
                stop_reason=stop_reason,
                usage=AnthropicUsage(
                    input_tokens=internal_response.usage.prompt_tokens,
                    output_tokens=internal_response.usage.completion_tokens,
                ),
            )

            duration_ms = (time.time() - start_time) * 1000
            record = SessionRecord(
                model=request.model,
                api_format="anthropic",
                messages=_messages_to_dicts(request),
                response_content=response_text,
                stream=False,
                duration_ms=round(duration_ms, 1),
                client_ip=client_ip,
                api_key_alias=auth.key_alias,
                github_token_alias=github_token_alias,
            )
            get_session_store().save(record)

            # For streaming tool requests that had no tool_use, still stream the text
            if request.stream and has_tool_defs:
                return StreamingResponse(
                    _stream_text_response(request.model, response_text),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                    },
                )

            return response

        except ValueError as exc:
            logger.warning("Invalid request: %s", exc)
            return _make_anthropic_error(400, str(exc), "invalid_request_error")
        except Exception as exc:
            logger.exception("Provider error during Anthropic message")
            duration_ms = (time.time() - start_time) * 1000
            record = SessionRecord(
                model=request.model,
                api_format="anthropic",
                messages=_messages_to_dicts(request),
                stream=request.stream,
                duration_ms=round(duration_ms, 1),
                status="error",
                error_message=str(exc),
                client_ip=client_ip,
                api_key_alias=auth.key_alias,
                github_token_alias=github_token_alias,
            )
            get_session_store().save(record)
            return _make_anthropic_error(500, str(exc), "api_error")

    # === Streaming path (no tools) ===
    async def anthropic_stream_generator():
        msg_id = _make_msg_id()
        output_tokens = 0
        collected_content: list[str] = []

        try:
            message_start = MessageStartEvent(
                message=MessagesResponse(
                    id=msg_id,
                    content=[],
                    model=request.model,
                    stop_reason=None,
                    usage=AnthropicUsage(input_tokens=0, output_tokens=0),
                )
            )
            yield f"event: message_start\ndata: {message_start.model_dump_json()}\n\n"

            block_start = ContentBlockStartEvent(
                index=0, content_block={"type": "text", "text": ""}
            )
            yield f"event: content_block_start\ndata: {block_start.model_dump_json()}\n\n"

            ping = PingEvent()
            yield f"event: ping\ndata: {ping.model_dump_json()}\n\n"

            finish_reason = "end_turn"
            async for delta in provider.chat_completion_stream(internal_request):
                if delta.delta_content is not None and delta.delta_content != "":
                    output_tokens += 1
                    collected_content.append(delta.delta_content)
                    block_delta = ContentBlockDeltaEvent(
                        index=0, delta={"type": "text_delta", "text": delta.delta_content}
                    )
                    yield f"event: content_block_delta\ndata: {block_delta.model_dump_json()}\n\n"
                if delta.finish_reason:
                    finish_reason = _map_finish_reason(delta.finish_reason)

            block_stop = ContentBlockStopEvent(index=0)
            yield f"event: content_block_stop\ndata: {block_stop.model_dump_json()}\n\n"

            msg_delta = MessageDeltaEvent(
                delta=MessageDeltaPayload(stop_reason=finish_reason),
                usage=MessageDeltaUsage(output_tokens=output_tokens),
            )
            yield f"event: message_delta\ndata: {msg_delta.model_dump_json()}\n\n"

            msg_stop = MessageStopEvent()
            yield f"event: message_stop\ndata: {msg_stop.model_dump_json()}\n\n"

            duration_ms = (time.time() - start_time) * 1000
            record = SessionRecord(
                model=request.model,
                api_format="anthropic",
                messages=_messages_to_dicts(request),
                response_content="".join(collected_content),
                stream=True,
                duration_ms=round(duration_ms, 1),
                client_ip=client_ip,
                api_key_alias=auth.key_alias,
                github_token_alias=github_token_alias,
            )
            get_session_store().save(record)

        except Exception as exc:
            logger.exception("Error during Anthropic streaming")
            duration_ms = (time.time() - start_time) * 1000
            record = SessionRecord(
                model=request.model,
                api_format="anthropic",
                messages=_messages_to_dicts(request),
                response_content="".join(collected_content),
                stream=True,
                duration_ms=round(duration_ms, 1),
                status="error",
                error_message=str(exc),
                client_ip=client_ip,
                api_key_alias=auth.key_alias,
                github_token_alias=github_token_alias,
            )
            get_session_store().save(record)
            error_data = AnthropicErrorResponse(
                error=AnthropicErrorDetail(type="api_error", message=str(exc))
            )
            yield f"event: error\ndata: {error_data.model_dump_json()}\n\n"

    return StreamingResponse(
        anthropic_stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# =============================================================================
# Streaming helpers for tool-bridge responses
# =============================================================================


async def _stream_tool_use_events(
    model: str, tool_calls: list[tuple[str, dict[str, Any]]]
):
    """Emit SSE events for tool_use content blocks."""
    msg_id = _make_msg_id()

    message_start = MessageStartEvent(
        message=MessagesResponse(
            id=msg_id,
            content=[],
            model=model,
            stop_reason=None,
            usage=AnthropicUsage(input_tokens=0, output_tokens=0),
        )
    )
    yield f"event: message_start\ndata: {message_start.model_dump_json()}\n\n"

    for idx, (tool_name, tool_input) in enumerate(tool_calls):
        tool_use_id = f"toolu_{uuid.uuid4().hex}"
        block_start = ContentBlockStartEvent(
            index=idx,
            content_block={
                "type": "tool_use",
                "id": tool_use_id,
                "name": tool_name,
                "input": {},
            },
        )
        yield f"event: content_block_start\ndata: {block_start.model_dump_json()}\n\n"

        block_delta = ContentBlockDeltaEvent(
            index=idx,
            delta={
                "type": "input_json_delta",
                "partial_json": json.dumps(tool_input, ensure_ascii=False),
            },
        )
        yield f"event: content_block_delta\ndata: {block_delta.model_dump_json()}\n\n"

        block_stop = ContentBlockStopEvent(index=idx)
        yield f"event: content_block_stop\ndata: {block_stop.model_dump_json()}\n\n"

    msg_delta = MessageDeltaEvent(
        delta=MessageDeltaPayload(stop_reason="tool_use"),
        usage=MessageDeltaUsage(output_tokens=0),
    )
    yield f"event: message_delta\ndata: {msg_delta.model_dump_json()}\n\n"

    msg_stop = MessageStopEvent()
    yield f"event: message_stop\ndata: {msg_stop.model_dump_json()}\n\n"


async def _stream_text_response(model: str, text: str):
    """Emit SSE events for a plain text response (fallback when tool parse fails)."""
    msg_id = _make_msg_id()

    message_start = MessageStartEvent(
        message=MessagesResponse(
            id=msg_id,
            content=[],
            model=model,
            stop_reason=None,
            usage=AnthropicUsage(input_tokens=0, output_tokens=0),
        )
    )
    yield f"event: message_start\ndata: {message_start.model_dump_json()}\n\n"

    block_start = ContentBlockStartEvent(
        index=0, content_block={"type": "text", "text": ""}
    )
    yield f"event: content_block_start\ndata: {block_start.model_dump_json()}\n\n"

    block_delta = ContentBlockDeltaEvent(
        index=0, delta={"type": "text_delta", "text": text}
    )
    yield f"event: content_block_delta\ndata: {block_delta.model_dump_json()}\n\n"

    block_stop = ContentBlockStopEvent(index=0)
    yield f"event: content_block_stop\ndata: {block_stop.model_dump_json()}\n\n"

    msg_delta = MessageDeltaEvent(
        delta=MessageDeltaPayload(stop_reason="end_turn"),
        usage=MessageDeltaUsage(output_tokens=0),
    )
    yield f"event: message_delta\ndata: {msg_delta.model_dump_json()}\n\n"

    msg_stop = MessageStopEvent()
    yield f"event: message_stop\ndata: {msg_stop.model_dump_json()}\n\n"
