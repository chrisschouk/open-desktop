# API keys — plain English

You only need **one key** to run OpenWorker. The two names below are roles, not two separate bills.

---

## The short version (OpenRouter)

1. Get a key from [openrouter.ai/keys](https://openrouter.ai/keys) — it starts with `sk-or-`
2. Put it in `.env`:

```bash
OPENROUTER_API_KEY=sk-or-v1-...
```

3. Done. Chat and desktop automation both use it.

You can also paste the same key in the web UI under **API Key Settings** (localhost only unless you set `OPENDESKTOP_API_TOKEN`).

---

## What are CHAT vs VISION?

| Name | What it does | When it runs |
|------|----------------|--------------|
| **Chat** | Fast text replies — OpenWorker conversation, intent routing | "What can you do?", planning, quick answers |
| **Vision** | Looks at **screenshots** of the sandbox and clicks/types | Research, forms, desktop automation |

Same provider, same key in most setups. We split the env vars so you *can* use a cheap model for chat and a stronger one for desktop — but you don't have to.

```bash
# One key (recommended)
OPENROUTER_API_KEY=sk-or-v1-...

# OR explicitly the same key twice (also fine)
CHAT_API_KEY=sk-or-v1-...
VISION_API_KEY=sk-or-v1-...

# OR split models later (power users)
CHAT_API_KEY=sk-or-v1-...
CHAT_MODEL=openai/gpt-4o-mini
VISION_API_KEY=sk-or-v1-...
VISION_MODEL=anthropic/claude-3.5-sonnet
```

---

## OpenRouter vs OpenAI

| Provider | Env var | Key shape |
|----------|---------|-----------|
| **OpenRouter** (recommended) | `OPENROUTER_API_KEY` | `sk-or-v1-...` |
| OpenAI direct | `CHAT_API_KEY` / `VISION_API_KEY` | `sk-proj-...` or `sk-...` |
| Generic fallback | `API_KEY` | any |

OpenRouter routes to OpenAI, Anthropic, Google, etc. with one account — handy for indie budgets.

---

## Local Ollama (no cloud key)

```bash
CHAT_API_URL=http://localhost:11434/v1/chat/completions
CHAT_MODEL=llama3.1
VISION_API_URL=http://localhost:11434/v1/chat/completions
VISION_MODEL=llava
```

Desktop automation quality depends on the vision model — cloud models are more reliable today.

---

## Security

- **Never commit** `.env` or keys to git
- `POST /api/v1/keys/set` only works from localhost/LAN, or with `OPENDESKTOP_API_TOKEN` when the server is exposed
- For production: set `OPENDESKTOP_API_TOKEN` and keep keys in `.env` only

---

## Check it's working

```bash
curl http://localhost:8000/api/v1/health | jq '.api_key_configured, .llm_provider'
```

Expect: `true` and `"openrouter"` (or `"openai"` / `"custom"`).
