# Copilot LLM Provider

> Turn GitHub Copilot subscriptions into a standard OpenAI/Anthropic-compatible LLM API gateway for the enterprise.

---

## Problem

Enterprises invest heavily in GitHub Copilot subscriptions for developer productivity, but this powerful AI capability is locked inside IDE integrations. Development teams cannot programmatically access Copilot-backed models for:

- **CI/CD automation** — automated code review, PR summarization, release notes generation
- **Internal tooling** — custom chatbots, knowledge-base assistants, documentation generators
- **Agentic workflows** — Claude Code, Codex CLI, and other AI coding agents that require API endpoints
- **Multi-team access governance** — different teams need different access levels, usage limits, and audit trails

Meanwhile, procuring separate LLM API access (OpenAI, Anthropic) creates additional licensing costs, vendor relationships, and compliance overhead — all while the same models sit unused behind GitHub Copilot.

## Solution

**Copilot LLM Provider** transforms existing GitHub Copilot subscriptions into standard, enterprise-grade LLM API endpoints using the [GitHub Copilot SDK](https://github.com/satomic/github-copilot-sdk). It provides a FastAPI-based gateway that speaks the same wire protocol as OpenAI and Anthropic APIs, enabling any existing client library or AI tool to use Copilot-backed models without code changes.

### Key Capabilities

| Capability | Description |
|---|---|
| **Dual API Compatibility** | Drop-in replacement for both OpenAI (`/openai/v1/chat/completions`, `/openai/v1/models`) and Anthropic (`/anthropic/v1/messages`) APIs, with legacy non-prefixed routes also supported |
| **Multi-Token Pooling** | Pool multiple GitHub accounts with round-robin load balancing for team-wide access |
| **API Key Governance** | Managed API keys with per-key model restrictions, usage quotas, and enable/disable controls |
| **Real-time Dashboard** | Admin UI for monitoring usage, managing tokens, viewing sessions, and tracking quotas |
| **Session Recording** | Full audit trail of every request/response for compliance and debugging |
| **Quota Monitoring** | Live premium request quota tracking per token via the SDK's built-in `account.getQuota()` RPC |
| **Streaming Support** | Full SSE streaming for both OpenAI and Anthropic formats |
| **MCP Server** | Model Context Protocol server for Claude Desktop, Claude Code, and other MCP clients |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                          Clients & Tools                             │
│  OpenAI SDK  │  Anthropic SDK  │  Claude Code  │  Codex CLI  │ curl │
└──────────┬───────────┬──────────────┬────────────┬──────────────────┘
           │           │              │            │
           ▼           ▼              ▼            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      FastAPI Gateway (main.py)                       │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────┐  ┌──────────────┐ │
│  │ Auth Layer  │  │ OpenAI API   │  │Anthropic │  │ Admin API    │ │
│  │ Session/Key │  │/openai/v1/.. │  │ API      │  │ /api/admin/  │ │
│  │ Managed Key │  │/openai/v1/mod│  │/anthropic│  │ tokens/keys  │ │
│  └──────┬──────┘  └──────┬───────┘  └────┬─────┘  └──────┬───────┘ │
│         │                │               │               │         │
│         ▼                ▼               ▼               ▼         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Services Layer                            │   │
│  │  UsageTracker  │  SessionStore  │  ApiKeyStore  │  UserStore │   │
│  └───────────────────────────┬─────────────────────────────────┘   │
│                              │                                      │
│  ┌───────────────────────────▼─────────────────────────────────┐   │
│  │                   Token Pool (Round-Robin)                   │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │   │
│  │  │ Token A  │  │ Token B  │  │ Token C  │  ...              │   │
│  │  │ Provider │  │ Provider │  │ Provider │                   │   │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘                  │   │
│  └───────┼──────────────┼─────────────┼────────────────────────┘   │
│          │              │             │                              │
└──────────┼──────────────┼─────────────┼──────────────────────────────┘
           │              │             │
           ▼              ▼             ▼
┌──────────────────────────────────────────────────────────────────────┐
│              GitHub Copilot SDK (CopilotClient per token)            │
│          JSON-RPC over stdio → Copilot CLI binary process            │
└──────────────────────────────────────────────────────────────────────┘
           │              │             │
           ▼              ▼             ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    GitHub Copilot Service                             │
│              gpt-4.1 │ claude-sonnet-4 │ o4-mini │ ...               │
└──────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
1. Client sends OpenAI/Anthropic format request
2. Auth layer validates session token, managed API key, or legacy key
3. Token Pool selects next GitHub token via round-robin (or explicit selection)
4. CopilotProvider creates a session, sends request, returns response
5. UsageTracker records request (per-model, per-key, per-token, daily)
6. SessionStore persists full request/response for audit
7. API layer converts internal response back to wire format
8. Client receives standard OpenAI/Anthropic response
```

---

## Prerequisites

- **Python 3.11+**
- **Node.js 20+** (for frontend build)
- **GitHub account** with an active Copilot subscription
- **GitHub Personal Access Token** (PAT) with Copilot access

---

## Setup & Deployment

### Option 1: Local Development

```bash
# Clone the repository
git clone https://github.com/satomic/copilot-llm-provider.git
cd copilot-llm-provider

# Backend setup
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env → set GITHUB_TOKEN=ghp_your_token_here

# Start backend
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

### Option 2: Production Build

```bash
# Build frontend
cd frontend && npm ci && npm run build && cd ..

# Run with built frontend
FRONTEND_DIR=frontend/dist uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

### First-Time Setup

1. Navigate to `http://localhost:8000` in your browser
2. Create an admin account (first user becomes admin)
3. Go to **Settings** → manage GitHub tokens and API keys
4. Go to **Dashboard** → verify models are available and quota is loaded

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GITHUB_TOKEN` | No* | — | GitHub PAT with Copilot access |
| `API_KEY` | No | — | Legacy API key for server auth |
| `HOST` | No | `0.0.0.0` | Server bind host |
| `PORT` | No | `8000` | Server bind port |
| `CORS_ORIGINS` | No | `*` | Allowed CORS origins (comma-separated) |
| `LOG_LEVEL` | No | `info` | Logging level |
| `FRONTEND_DIR` | No | — | Path to built frontend static files |

\* If not set, the SDK falls back to `GH_TOKEN`, `GITHUB_TOKEN` env vars, or stored OAuth from GitHub CLI.

---

## API Usage Examples

### OpenAI SDK (Python)

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/openai/v1",
    api_key="your-managed-api-key",
)

response = client.chat.completions.create(
    model="gpt-4.1",
    messages=[{"role": "user", "content": "Hello!"}],
    stream=True,
)
for chunk in response:
    print(chunk.choices[0].delta.content or "", end="")
```

### Anthropic SDK (Python)

```python
from anthropic import Anthropic

client = Anthropic(
    base_url="http://localhost:8000/anthropic",
    api_key="your-managed-api-key",
)

message = client.messages.create(
    model="claude-sonnet-4",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello!"}],
)
print(message.content[0].text)
```

### Claude Code / Codex CLI

```bash
# Claude Code
export ANTHROPIC_BASE_URL=http://localhost:8000/anthropic
export ANTHROPIC_API_KEY=your-managed-api-key
claude

# Codex CLI
export OPENAI_BASE_URL=http://localhost:8000/openai/v1
export OPENAI_API_KEY=your-managed-api-key
codex
```

> **Note:** Legacy non-prefixed routes (`/v1/chat/completions`, `/v1/models`, `/v1/messages`) are also available for backward compatibility.

### MCP Server (Model Context Protocol)

This project also runs as an MCP server, allowing MCP clients (Claude Desktop, Claude Code, etc.) to use Copilot models as tools.

**Available MCP tools:**

| Tool | Description |
|---|---|
| `chat` | Send a message to a Copilot model (supports model selection, system prompt, temperature, max_tokens) |
| `list_models` | List all available models with premium/free status and billing multiplier |
| `get_quota` | Check premium request quota for all configured GitHub tokens |

**Setup — add to your MCP client config** (e.g., `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "copilot-llm-provider": {
      "command": "python",
      "args": ["-m", "backend.app.mcp_server"],
      "cwd": "/absolute/path/to/copilot-llm-provider",
      "env": {
        "GITHUB_TOKEN": "ghp_your_token_here"
      }
    }
  }
}
```

Or run standalone: `python -m backend.app.mcp_server`

---

## Enterprise Features

### Multi-Token Pooling

Pool multiple GitHub Copilot accounts and distribute requests fairly:

- **Round-robin selection** ensures even load distribution across tokens
- **Per-token status monitoring** (active / error / stopped)
- **Live quota tracking** via the SDK's `account.getQuota()` RPC
- **Dynamic token management** — add, remove, enable/disable tokens at runtime via Admin API or Dashboard UI
- **Explicit token selection** via `X-GitHub-Token-Id` header for deterministic routing

### API Key Governance

Create managed API keys with fine-grained controls:

- **Model restrictions** — limit which models each key can access
- **Usage quotas** — set max total and max premium request limits per key
- **Enable/disable** — instantly revoke access without deleting the key
- **Usage tracking** — per-key request counts and model breakdown
- **Alias tagging** — human-readable names for team/service identification

### Observability

- **Real-time Dashboard** — server status, model availability, usage charts, daily trends
- **Session Recording** — every request/response persisted as JSON for audit
- **Usage Statistics** — per-model, per-API-key, per-token breakdown with daily trends
- **Quota Monitoring** — premium request entitlement, used, remaining %, reset date per token

---

## Responsible AI (RAI) Notes

### Data Handling

- **No training data collection** — this is a gateway; it does not fine-tune or train models
- **Session recording is local** — all session data is stored as local JSON files on the server, never transmitted to third parties
- **Token masking** — GitHub tokens are masked in all API responses and logs (only first 10 + last 4 characters shown)
- **No PII extraction** — the system does not extract, store, or process personal information beyond what the user sends in prompts

### Access Control

- **Authentication required** — username/password admin accounts with session tokens
- **Managed API keys** — granular access control with model restrictions and usage limits
- **Audit trail** — every API request is logged with timestamp, model, API key alias, token alias, client IP, and full request/response content
- **No anonymous access** — all endpoints (except `/health`) require authentication when auth is configured

### Model Governance

- **Model visibility** — only models available through the user's Copilot subscription are exposed
- **Billing transparency** — each model's billing multiplier is displayed, distinguishing free (x0) from premium (x>0) models
- **Usage limits** — API keys can be configured with maximum request counts to prevent runaway usage
- **Quota awareness** — real-time premium request quota monitoring prevents unexpected overage

### Limitations

- This project proxies requests to GitHub Copilot's backend models; it inherits the content policies and limitations of those models
- Output quality and safety depend on the underlying models (GPT-4.1, Claude Sonnet 4, etc.)
- Administrators should implement additional content filtering if required by their organization's policies

---

## Project Structure

```
copilot-llm-provider/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app, lifespan, routing
│   │   ├── core/
│   │   │   ├── config.py           # Settings (pydantic-settings)
│   │   │   ├── auth.py             # Multi-method authentication
│   │   │   ├── dependencies.py     # DI: provider selection, token pool
│   │   │   └── runtime_config.py   # Dynamic runtime configuration
│   │   ├── providers/
│   │   │   ├── base.py             # Abstract Provider interface
│   │   │   └── copilot.py          # CopilotProvider + quota fetching
│   │   ├── services/
│   │   │   ├── token_pool.py       # Multi-token round-robin pool
│   │   │   ├── session_store.py    # Session persistence (JSON files)
│   │   │   ├── usage_tracker.py    # Per-model/key/token usage stats
│   │   │   ├── api_key_store.py    # Managed API key CRUD
│   │   │   └── user_store.py       # Admin user management
│   │   ├── api/
│   │   │   ├── openai/chat.py      # POST /openai/v1/chat/completions
│   │   │   ├── openai/models.py    # GET /openai/v1/models
│   │   │   ├── anthropic/messages.py # POST /anthropic/v1/messages
│   │   │   ├── admin.py            # Token/key management endpoints
│   │   │   ├── sessions.py         # Session CRUD + continue-chat
│   │   │   └── stats.py            # Usage statistics endpoint
│   │   └── schemas/
│   │       ├── openai.py           # OpenAI Pydantic models
│   │       └── anthropic.py        # Anthropic Pydantic models
│   └── tests/
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── DashboardPage.tsx    # Usage stats, charts, model list
│       │   ├── PlaygroundPage.tsx   # Interactive chat testing
│       │   ├── SessionsPage.tsx     # Session audit viewer
│       │   ├── SettingsPage.tsx     # Token & API key management
│       │   └── ...
│       ├── contexts/I18nContext.tsx  # EN/ZH internationalization
│       └── services/api.ts         # Centralized API client
├── docs/                           # This documentation
├── presentations/                  # Challenge presentation deck
└── AGENTS.md                       # Multi-agent development architecture
```

---

## Technology Stack

| Layer | Technology |
|---|---|
| **SDK** | `github-copilot-sdk` (Python) — Copilot CLI binary via JSON-RPC over stdio |
| **Backend** | Python 3.11+, FastAPI, Pydantic v2, uvicorn |
| **Frontend** | React 18, TypeScript 5, Vite, Tailwind CSS |
| **Auth** | Session tokens + managed API keys + legacy key |
| **Persistence** | JSON files (zero-dependency, no database required) |
| **Deployment** | uvicorn with production frontend build |
| **Logging** | Python `logging` with JSON structured output |
| **Testing** | pytest, pytest-asyncio, httpx |
| **Linting** | ruff (Python), TypeScript strict mode |

---

## License

MIT License. See [LICENSE](../LICENSE) for details.
