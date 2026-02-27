# Copilot LLM Provider

Turn your GitHub Copilot subscription into a standard OpenAI- and Anthropic-compatible LLM API server.

This project wraps the `github-copilot-sdk` Python package behind a FastAPI server that speaks the same wire protocol as the OpenAI and Anthropic APIs. Point any existing OpenAI or Anthropic client library at this server and use Copilot-backed models without changing your application code.

## Features

- **OpenAI API compatible** -- `POST /v1/chat/completions` and `GET /v1/models` match the OpenAI specification
- **Anthropic API compatible** -- `POST /v1/messages` matches the Anthropic Messages specification
- **Streaming support** -- Server-Sent Events (SSE) for both OpenAI and Anthropic streaming formats
- **API key authentication** -- Optional `API_KEY` to protect endpoints in production
- **React dashboard** -- Built-in frontend for interactive testing and monitoring
- **Docker ready** -- Multi-stage Dockerfile and Compose file for one-command deployment
- **Fully tested** -- Comprehensive pytest test suite with mocked providers (no real API calls)

## Architecture

```
                       +-------------------+
                       |   Client / SDK    |
                       | (openai, anthropic|
                       |  curl, fetch ...) |
                       +---------+---------+
                                 |
                     HTTP (OpenAI / Anthropic format)
                                 |
                       +---------v---------+
                       |    FastAPI App     |
                       |  (main.py)        |
                       +---+-------+---+---+
                           |       |   |
              +------------+   +---+   +------------+
              |                |                     |
    +---------v------+  +-----v--------+  +---------v--------+
    | OpenAI Routes  |  | Anthropic    |  | Health / Static  |
    | /v1/chat/...   |  | Routes       |  | /health          |
    | /v1/models     |  | /v1/messages |  |                  |
    +-------+--------+  +------+-------+  +------------------+
            |                  |
            +--------+---------+
                     |
          +----------v----------+
          |  Schemas (Pydantic) |
          |  OpenAI / Anthropic |
          +----------+----------+
                     |
          +----------v----------+
          |  Services Layer     |
          |  ChatService        |
          |  ModelService       |
          +----------+----------+
                     |
          +----------v----------+
          |  Provider (ABC)     |
          |  CopilotProvider    |
          +----------+----------+
                     |
          +----------v----------+
          |  github-copilot-sdk |
          |  (CopilotClient)    |
          +---------------------+
```

## Quick Start

### Prerequisites

- Python 3.11 or later
- Node.js 20 or later (for the frontend)
- A GitHub account with an active Copilot subscription
- A GitHub personal access token (PAT) with Copilot access

### Backend Setup

```bash
# Clone the repository
git clone https://github.com/your-org/copilot-llm-provider.git
cd copilot-llm-provider

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate

# Install dependencies (including dev tools)
pip install -e ".[dev]"

# Set your GitHub token
cp .env.example .env
# Edit .env and set GITHUB_TOKEN=ghp_your_token_here

# Start the backend server
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

The API is now available at `http://localhost:8000`.

### Frontend Setup

```bash
# In a separate terminal
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser. The Vite dev server proxies API requests to `localhost:8000`.

### Verify It Works

```bash
# Health check
curl http://localhost:8000/health

# List available models
curl http://localhost:8000/v1/models
```

## Docker Deployment

Build and run everything with Docker Compose:

```bash
# Make sure .env exists with your GITHUB_TOKEN
cp .env.example .env
# Edit .env and set GITHUB_TOKEN

# Build and start
docker compose -f docker/docker-compose.yml up --build

# The server is available at http://localhost:8000
# The frontend is served from the same port at /
```

## API Usage Examples

### OpenAI-compatible (curl)

```bash
# Non-streaming
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4.1",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "What is the capital of France?"}
    ]
  }'

# Streaming
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4.1",
    "messages": [
      {"role": "user", "content": "Write a haiku about coding."}
    ],
    "stream": true
  }'
```

### Anthropic-compatible (curl)

```bash
# Non-streaming
curl http://localhost:8000/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4",
    "max_tokens": 1024,
    "system": "You are a helpful assistant.",
    "messages": [
      {"role": "user", "content": "What is the capital of France?"}
    ]
  }'

# Streaming
curl http://localhost:8000/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4",
    "max_tokens": 1024,
    "messages": [
      {"role": "user", "content": "Write a haiku about coding."}
    ],
    "stream": true
  }'
```

### Python (OpenAI library)

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="your-api-key",  # or any string if API_KEY is not configured
)

response = client.chat.completions.create(
    model="gpt-4.1",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
    ],
)

print(response.choices[0].message.content)
```

### Python (Anthropic library)

```python
from anthropic import Anthropic

client = Anthropic(
    base_url="http://localhost:8000",
    api_key="your-api-key",  # or any string if API_KEY is not configured
)

message = client.messages.create(
    model="claude-sonnet-4",
    max_tokens=1024,
    system="You are a helpful assistant.",
    messages=[
        {"role": "user", "content": "Hello!"},
    ],
)

print(message.content[0].text)
```

### Node.js (OpenAI library)

```javascript
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "http://localhost:8000/v1",
  apiKey: "your-api-key", // or any string if API_KEY is not configured
});

const response = await client.chat.completions.create({
  model: "gpt-4.1",
  messages: [
    { role: "system", content: "You are a helpful assistant." },
    { role: "user", content: "Hello!" },
  ],
});

console.log(response.choices[0].message.content);
```

## Environment Variables

| Variable       | Required | Default   | Description                                      |
|----------------|----------|-----------|--------------------------------------------------|
| `GITHUB_TOKEN` | No*      | --        | GitHub PAT with Copilot access                   |
| `API_KEY`      | No       | --        | API key to protect server endpoints               |
| `HOST`         | No       | `0.0.0.0` | Server bind host                                  |
| `PORT`         | No       | `8000`    | Server bind port                                  |
| `CORS_ORIGINS` | No       | `*`       | Allowed CORS origins (comma-separated)            |
| `LOG_LEVEL`    | No       | `info`    | Logging level (debug, info, warning, error)       |
| `FRONTEND_DIR` | No       | --        | Path to built frontend static files               |

\* If `GITHUB_TOKEN` is not set, the SDK falls back to `GH_TOKEN`, `GITHUB_TOKEN` env vars, or stored OAuth credentials from the GitHub CLI.

## Project Structure

```
copilot-llm-provider/
├── pyproject.toml                  # Python project config, dependencies, tool settings
├── .env.example                    # Environment variable template
├── README.md                       # This file
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app with lifespan, CORS, routing
│   │   ├── core/
│   │   │   ├── config.py           # Settings (pydantic-settings, .env loading)
│   │   │   ├── auth.py             # API key verification dependency
│   │   │   ├── logging.py          # Structured logging setup
│   │   │   └── dependencies.py     # FastAPI DI: get_settings, get_provider
│   │   ├── providers/
│   │   │   ├── base.py             # Abstract Provider interface (the contract)
│   │   │   └── copilot.py          # CopilotProvider implementation
│   │   ├── services/
│   │   │   ├── chat.py             # ChatService (logging, timing wrapper)
│   │   │   ├── models.py           # ModelService (caching, discovery)
│   │   │   └── session_pool.py     # SessionPool (concurrency control)
│   │   ├── api/
│   │   │   ├── openai/
│   │   │   │   ├── chat.py         # POST /v1/chat/completions
│   │   │   │   └── models.py       # GET /v1/models
│   │   │   └── anthropic/
│   │   │       └── messages.py     # POST /v1/messages
│   │   └── schemas/
│   │       ├── openai.py           # OpenAI Pydantic request/response models
│   │       └── anthropic.py        # Anthropic Pydantic request/response models
│   └── tests/
│       ├── conftest.py             # Shared fixtures, MockProvider
│       ├── test_health.py          # Health endpoint tests
│       ├── test_auth.py            # Authentication tests
│       ├── test_openai_chat.py     # OpenAI chat completions tests
│       ├── test_openai_models.py   # OpenAI models listing tests
│       ├── test_anthropic_messages.py  # Anthropic messages tests
│       └── test_schemas.py         # Schema validation tests
├── docker/
│   ├── Dockerfile                  # Multi-stage build (frontend + backend)
│   └── docker-compose.yml          # One-command deployment
├── .github/
│   └── workflows/
│       └── ci.yml                  # GitHub Actions CI (lint, test, build)
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    └── src/
        ├── main.tsx
        ├── App.tsx
        └── types/api.ts
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest backend/tests/test_openai_chat.py

# Run a specific test
pytest backend/tests/test_health.py::test_health_returns_200_with_status_ok
```

### Linting

```bash
# Check for issues
ruff check backend/

# Auto-fix issues
ruff check --fix backend/

# Check formatting
ruff format --check backend/

# Auto-format
ruff format backend/
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run the test suite (`pytest`) and linter (`ruff check backend/`)
5. Commit your changes with a descriptive message
6. Push to your fork and open a pull request

Please ensure:
- All tests pass before submitting a PR
- New features include tests
- Code follows the project conventions in `CLAUDE.md`

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
