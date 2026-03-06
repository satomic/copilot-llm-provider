# Copilot LLM Provider — Project Summary

## The Problem: Wasted Premium Requests

GitHub Copilot subscriptions come with a monthly premium request quota, but most individuals and teams **never use it all**. Quotas reset at the end of each billing cycle — unused requests are simply lost. Across a team of 10, 50, or 100 developers, this waste adds up to thousands of premium requests thrown away every month.

Meanwhile, teams that *could* benefit from LLM API access — for CI/CD automation, internal tooling, agentic workflows (Claude Code, Codex CLI), or custom chatbots — are forced to procure separate OpenAI or Anthropic API contracts, adding cost, vendor relationships, and compliance overhead on top of the Copilot subscriptions they already pay for.

## The Solution: Pool and Expose

**Copilot LLM Provider** solves this by **pooling multiple Copilot subscriptions into a unified resource pool** and exposing them as standard OpenAI- and Anthropic-compatible API endpoints.

```
  Clients & Tools          Unified Resource Pool          Individual Quotas (often underused)

┌────────────────┐      ┌────────────────────────┐      ┌──────────┐
│  OpenAI API    │      │                        │      │ Dev A    │
│ /openai/v1/... │ ───► │  Copilot LLM Provider  │ ───► │ 300/1000 │  70% waste
└────────────────┘      │                        │      └──────────┘
                        │  Round-Robin Balancing │      ┌──────────┐
┌────────────────┐      │  Quota Tracking        │      │ Dev B    │
│ Anthropic API  │ ───► │  Combined: 3000 reqs   │ ───► │  50/1000 │  95% waste
│/anthropic/v1/..│      │                        │      └──────────┘
└────────────────┘      │  ► Near-zero waste     │      ┌──────────┐
                        │                        │      │ Dev C    │
                        └────────────────────────┘ ───► │ 120/1000 │  88% waste
                                                        └──────────┘
```

Each developer's GitHub token is added to the pool. The gateway distributes requests across tokens via round-robin load balancing, tracks per-token quota usage in real time, and ensures no single account is over-utilized. The result: **near-zero waste** and **maximum return on existing Copilot investment**.

## How It Works

Built on FastAPI and the [GitHub Copilot SDK](https://github.com/satomic/github-copilot-sdk), the gateway speaks the same wire protocol as OpenAI and Anthropic APIs. Any existing client library, AI tool, or automation script works without code changes — just point `base_url` at the gateway.

### Key Capabilities

| Capability | Why It Matters |
|---|---|
| **Multi-Token Pooling** | Combine N subscriptions into one pool; round-robin balancing maximizes total quota utilization |
| **Real-Time Quota Monitoring** | Dashboard shows per-token used/remaining/reset date so you always know where you stand |
| **Dual API Compatibility** | Drop-in replacement for both OpenAI and Anthropic SDKs — no client code changes needed |
| **API Key Governance** | Managed keys with per-key model restrictions and usage limits for multi-team access control |
| **Session Recording** | Full audit trail of every request/response for compliance |
| **Streaming Support** | Full SSE streaming in both OpenAI and Anthropic formats |
| **MCP Server** | Expose Copilot models to Claude Desktop, Claude Code, and other MCP clients |

## Who Is This For

- **Teams** where most members don't exhaust their monthly premium requests — pool the unused capacity for shared automation
- **Individuals** who want to use their Copilot quota beyond the IDE — power Claude Code, Codex CLI, or custom tools with it
- **Organizations** evaluating LLM API access — try it with existing Copilot subscriptions before committing to separate API contracts

## Bottom Line

You're already paying for Copilot. **Stop wasting premium requests.** Pool them, expose them as APIs, and put every last request to work.
