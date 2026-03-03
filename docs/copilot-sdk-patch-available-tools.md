# github-copilot-sdk Python SDK Patch: `available_tools: []` Bug Fix

## 1. Problem

The `github-copilot-sdk` Python package (tested on version `0.1.0`) has a bug that prevents disabling server-side tool execution when using `available_tools: []`.

### Symptom

When you pass `available_tools: []` (empty list) to `create_session()`, the SDK **silently drops** this parameter. The CLI binary never receives the tool restriction, so **all built-in tools remain active**. The agent framework will execute file read/write/edit operations on the server, even though you intended to disable them.

### Impact

In a gateway/proxy scenario (e.g., exposing Copilot as an OpenAI/Anthropic-compatible API), this causes:

- Files being created/modified on the **server** instead of the **client**.
- Tool calls (`tool_use`) executed server-side instead of being returned to the client for local execution.
- Complete breakdown of the "tool bridge" architecture where tools should execute on the client.

## 2. Root Cause

In Python, an empty list `[]` is **falsy**. The SDK uses truthy checks (`if available_tools:`) instead of explicit `None` checks (`if available_tools is not None:`).

### Affected File

```
<python_site_packages>/copilot/client.py
```

To find the exact path on your system:

```bash
python3 -c "import copilot; print(copilot.__file__.replace('__init__.py', 'client.py'))"
```

### Affected Class

`CopilotClient` (the main client class)

### Affected Locations (2 places)

#### Location 1: `create_session()` method (~line 480-486)

```python
# BEFORE (buggy):
available_tools = cfg.get("available_tools")
if available_tools:                              # BUG: [] is falsy!
    payload["availableTools"] = available_tools
excluded_tools = cfg.get("excluded_tools")
if excluded_tools:                               # BUG: [] is falsy!
    payload["excludedTools"] = excluded_tools
```

#### Location 2: `resume_session()` method (~line 648-654)

```python
# BEFORE (buggy):
available_tools = cfg.get("available_tools")
if available_tools:                              # BUG: [] is falsy!
    payload["availableTools"] = available_tools

excluded_tools = cfg.get("excluded_tools")
if excluded_tools:                               # BUG: [] is falsy!
    payload["excludedTools"] = excluded_tools
```

> **Note**: Line numbers are based on SDK version `0.1.0`. They may shift in future releases, but the pattern (`if available_tools:`) is easy to find with `grep`.

## 3. Fix

Change `if available_tools:` to `if available_tools is not None:` in both locations.

### How to find the lines

```bash
SDK_PATH=$(python3 -c "import copilot; print(copilot.__file__.replace('__init__.py', 'client.py'))")
grep -n "if available_tools:" "$SDK_PATH"
grep -n "if excluded_tools:" "$SDK_PATH"
```

### Patch (4 lines total, 2 locations)

#### Location 1: `create_session()` method

```python
# AFTER (fixed):
available_tools = cfg.get("available_tools")
if available_tools is not None:                  # FIXED
    payload["availableTools"] = available_tools
excluded_tools = cfg.get("excluded_tools")
if excluded_tools is not None:                   # FIXED
    payload["excludedTools"] = excluded_tools
```

#### Location 2: `resume_session()` method

```python
# AFTER (fixed):
available_tools = cfg.get("available_tools")
if available_tools is not None:                  # FIXED
    payload["availableTools"] = available_tools

excluded_tools = cfg.get("excluded_tools")
if excluded_tools is not None:                   # FIXED
    payload["excludedTools"] = excluded_tools
```

### One-liner patch script

```bash
SDK_PATH=$(python3 -c "import copilot; print(copilot.__file__.replace('__init__.py', 'client.py'))")
sed -i.bak \
  -e 's/if available_tools:/if available_tools is not None:/' \
  -e 's/if excluded_tools:/if excluded_tools is not None:/' \
  "$SDK_PATH"
echo "Patched: $SDK_PATH"
echo "Backup:  ${SDK_PATH}.bak"
```

## 4. Verification

After applying the patch, verify:

```python
import copilot, asyncio

async def test():
    client = copilot.CopilotClient({})
    await client.start()
    # This should now actually send availableTools: [] to the CLI binary
    session = await client.create_session({
        "model": "gpt-4.1",
        "available_tools": [],
    })
    # Model should return text only, never execute tools server-side
    response = await session.send_and_wait({"prompt": "Create a file /tmp/test.txt with hello"})
    print(response.data.content)
    # /tmp/test.txt should NOT exist on the server
    await session.destroy()
    await client.stop()

asyncio.run(test())
```

Expected: The model returns text describing what it would do (or a tool_use JSON), but `/tmp/test.txt` is **not** created on the server.

## 5. Why this matters

This fix is **required** for the tool bridge architecture used in `copilot-llm-provider`:

1. Server creates a session with `available_tools: []` to disable all server-side tools.
2. The model outputs tool call intents as JSON text.
3. The server parses the JSON and returns standard Anthropic `tool_use` content blocks.
4. The client (e.g., Claude Code) executes tools locally.

Without this fix, step 1 fails silently, and the SDK's agent framework executes tools on the server — completely breaking the architecture.

## 6. Upstream status

This bug should be reported to the `github-copilot-sdk` maintainers. The fix is a trivial Python falsy-vs-None correction. Until it's merged upstream, apply the patch manually after every SDK install or upgrade.
