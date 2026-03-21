# Todo Buddy

A personal inbox assistant that uses Claude AI to automatically classify and file todo items into your Obsidian vault. Send a note via HTTP and the agent decides where it belongs — then optionally pings you on Telegram with confirmation.

## How it works

1. You POST a text item to the `/inbox` endpoint
2. The item is immediately appended to `Inbox.md` as a safety net
3. A Claude-powered agent runs in the background:
   - Lists existing markdown files in your vault
   - Decides the best file for the item (e.g. groceries → `Grocery.md`, repairs → `House Projects.md`)
   - Appends a timestamped checkbox entry to that file, creating it if needed
4. A Telegram message confirms where the item was filed (optional)

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) for dependency management
- An [Anthropic API key](https://console.anthropic.com/)
- An Obsidian vault accessible on the server's filesystem
- A Telegram bot (optional, for confirmations)

### Install

```bash
uv sync
```

### Configure

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `OBSIDIAN_VAULT` | Path to your Obsidian vault **inside the container** (e.g. `/vault`) — mount your actual vault directory to this path |
| `INBOX_API_KEY` | Secret key to authenticate requests to `/inbox` |
| `TELEGRAM_BOT_TOKEN` | Bot token from [@BotFather](https://t.me/botfather) (optional) |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID (optional) |

### Run

```bash
uv run src/server.py
```

The server starts on port `5055`.

### Help Scripts

```bash
source .env && python scripts/send_inbox.py
```

## API

### `POST /inbox`

Accepts a todo item and files it into the vault.

**Authentication:** Pass your `INBOX_API_KEY` via the `X-API-Key` header or `api_key` query parameter.

**Request body:**

```json
{ "text": "buy oat milk" }
```

**Response:**

```json
{ "ok": true }
```

The response is immediate — the agent runs in the background.

**Example:**

```bash
curl -X POST http://localhost:5055/inbox \
  -H "X-API-Key: your-secret-key-here" \
  -H "Content-Type: application/json" \
  -d '{"text": "fix the leaky faucet in the bathroom"}'
```

## Docker

A Docker image is built and published automatically via GitHub Actions on every push to `main`.

Your Obsidian vault lives on the host machine and must be mounted into the container. Set `OBSIDIAN_VAULT=/vault` in your `.env`, then pass `-v` to mount the real path:

```bash
docker run -p 5055:5055 \
  --env-file .env \
  -v /path/to/your/obsidian/vault:/vault \
  ghcr.io/<your-username>/todo_buddy:latest
```

Or build and run locally:

```bash
docker build -t todo-buddy .
docker run -p 5055:5055 \
  --env-file .env \
  -v ./obsidian_vault:/vault \
  todo-buddy
```

