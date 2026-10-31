import contextvars
import os
from typing import Any

import httpx
from mcp.server import MCPServer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

GROQ_API_BASE = os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1")
SERVER_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN")

_request_groq_key: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_groq_key", default=None
)


def get_groq_key() -> str:
    key = _request_groq_key.get() or os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError(
            "No Groq API key supplied. Set GROQ_API_KEY on the server or send "
            "X-Groq-API-Key with the MCP request."
        )
    return key


class AuthAndKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if SERVER_AUTH_TOKEN:
            supplied = request.headers.get("authorization", "")
            if supplied != f"Bearer {SERVER_AUTH_TOKEN}":
                return JSONResponse({"error": "Unauthorized"}, status_code=401)

        groq_key = request.headers.get("x-groq-api-key")
        token = _request_groq_key.set(groq_key)
        try:
            return await call_next(request)
        finally:
            _request_groq_key.reset(token)


mcp = MCPServer(
    "Groq Claude MCP Connector",
    version="1.0.0",
    instructions=(
        "Connect Claude to Groq through two tools: list Groq models and run "
        "chat completions. The connector never exposes the Groq API key in "
        "tool results."
    ),
)


@mcp.tool()
async def groq_list_models() -> dict[str, Any]:
    """List models available to the configured Groq API key."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{GROQ_API_BASE}/models",
            headers={"Authorization": f"Bearer {get_groq_key()}"},
        )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def groq_chat(
    model: str,
    messages: list[dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """Run a Groq chat completion using an available model."""
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.post(
            f"{GROQ_API_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {get_groq_key()}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        return response.json()


app = mcp.streamable_http_app(
    streamable_http_path="/mcp",
    json_response=True,
    stateless_http=True,
)

# The MCP SDK's default host protection is intentionally localhost-only.
# When deployed behind a public HTTPS hostname, set MCP_ALLOWED_HOSTS and
# MCP_ALLOWED_ORIGINS to the deployed hostname(s).
#
# For production, wrap `app` with your platform's HTTPS/auth layer.
