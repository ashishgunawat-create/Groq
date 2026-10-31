# Groq MCP Connector for Claude

A real remote MCP server that lets Claude call Groq through:

- `groq_list_models`
- `groq_chat`

This is deliberately an **MCP server**, not a fake plugin manifest pointing at the Groq REST API. Groq's API is an OpenAI-compatible REST API; it is not itself an MCP server.

## Architecture

```text
Claude
  │ Remote MCP / Streamable HTTP
  ▼
This server
  │ HTTPS + Groq API key
  ▼
Groq API
  ├── /openai/v1/models
  └── /openai/v1/chat/completions
```

## 1. Run locally

Python 3.11+ is required.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set `GROQ_API_KEY`, then start:

```bash
uvicorn server:app --host 127.0.0.1 --port 8000
```

The MCP endpoint is:

```text
http://127.0.0.1:8000/mcp
```

A local URL is useful for Claude Desktop development, but Claude's remote custom connector requires a server reachable by Anthropic's cloud.

## 2. Deploy for Claude custom connector

Deploy this project to a service that provides a public HTTPS URL.

Your MCP endpoint should become:

```text
https://YOUR-DOMAIN.example/mcp
```

Set these server environment variables:

```text
GROQ_API_KEY=gsk_...
MCP_AUTH_TOKEN=<long-random-secret>
```

If you use `MCP_AUTH_TOKEN`, configure Claude's connector to send:

```text
Authorization: Bearer <long-random-secret>
```

Do **not** put the Groq key in this README, in the source code, or in a client-side app.

## 3. Claude setup

In Claude:

1. Open **Customize → Connectors**.
2. Choose **Add** → **Custom** → **Web**.
3. Enter a name such as `Groq MCP`.
4. Enter your remote MCP URL:
   `https://YOUR-DOMAIN.example/mcp`
5. Configure authentication/request headers as required by your deployment.
6. Add/connect the connector.
7. Enable the connector in a conversation.

Claude can then use `groq_list_models` to discover models and `groq_chat` to run a completion.

## Request-header alternative

Instead of storing `GROQ_API_KEY` on the server, the server accepts:

```text
X-Groq-API-Key: gsk_...
```

This is useful when you control the connector configuration and want the Groq credential supplied per request. If you expose this publicly, also set `MCP_AUTH_TOKEN` so random callers cannot submit arbitrary Groq keys to your server.

## Security notes

- Never commit `.env` or API keys.
- Prefer a server-side secret or a secure connector request header.
- Use HTTPS in production.
- Keep the Groq API key out of tool outputs.
- Restrict access to the MCP endpoint with an authentication layer.
- Treat the MCP server as trusted code because Claude can invoke its tools.

## Important limitation

This connector does **not** add Groq models to Claude's native model selector. It gives Claude tools that call Groq externally. That distinction matters because apparently AI platforms enjoy making the same word, "model", mean three different things.

## API behavior

`groq_list_models` calls:

```text
GET https://api.groq.com/openai/v1/models
```

`groq_chat` calls:

```text
POST https://api.groq.com/openai/v1/chat/completions
```

The connector forwards the model, messages, temperature, and optional max token limit.
