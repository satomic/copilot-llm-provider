# Copilot LLM Provider — Project Summary

Enterprises invest heavily in GitHub Copilot subscriptions, but this AI capability is locked inside IDE integrations. Teams cannot programmatically access Copilot-backed models for CI/CD automation, internal tooling, or agentic workflows like Claude Code and Codex CLI — forcing separate LLM API procurement with additional cost and compliance overhead.

**Copilot LLM Provider** transforms existing Copilot subscriptions into standard OpenAI- and Anthropic-compatible API endpoints using the GitHub Copilot SDK. Built on FastAPI, it provides a drop-in gateway that any existing client library can use without code changes.

Key enterprise capabilities include: multi-token pooling with round-robin load balancing, managed API keys with per-key model restrictions and usage quotas, full session recording for audit compliance, real-time premium request quota monitoring via the SDK's built-in RPC, and a React-based admin dashboard for operational visibility.

One deployment unlocks your entire Copilot investment for every AI-powered workflow across the organization.
