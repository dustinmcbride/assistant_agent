import os
import threading
from datetime import datetime
from pathlib import Path

import telegram
from dotenv import load_dotenv
from flask import Flask, abort, request, jsonify
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.tools import tool

load_dotenv()

app = Flask(__name__)

OBSIDIAN_VAULT = os.environ.get("OBSIDIAN_VAULT", "")
INBOX_API_KEY = os.environ.get("INBOX_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# ---------------------------------------------------------------------------
# Agent tools
# ---------------------------------------------------------------------------

@tool
def list_vault_files() -> str:
    """List all markdown files currently in the Obsidian vault.
    Returns a newline-separated list of filenames (without the vault path prefix).
    Use this to discover existing lists before deciding where to file an item."""
    vault = Path(OBSIDIAN_VAULT)
    files = sorted(p.name for p in vault.glob("*.md"))
    return "\n".join(files) if files else "(no files yet)"


@tool
def append_to_file(filename: str, text: str) -> str:
    """Append a timestamped bullet entry to a markdown file in the Obsidian vault.
    If the file does not exist it will be created with a heading derived from the filename.
    Args:
        filename: The .md filename to write to (e.g. 'Grocery.md'). Must end with .md.
        text: The todo item text to append (without timestamp — that is added automatically).
    """
    if not filename.endswith(".md"):
        filename = filename + ".md"

    path = Path(OBSIDIAN_VAULT) / filename
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n- {timestamp} — {text}"

    if not path.exists():
        heading = path.stem.replace("_", " ").replace("-", " ").title()
        path.write_text(f"# {heading}\n")

    with path.open("a") as f:
        f.write(entry)

    return f"Appended to {filename}."


# ---------------------------------------------------------------------------
# Agent setup
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a personal organizer assistant. Your job is to classify an incoming
todo/note item and file it into the correct markdown list in the user's Obsidian vault.

Steps:
1. Call list_vault_files to see what lists already exist.
2. Decide which file is the best match for the item. Use your judgment:
   - Grocery or shopping items → something like Grocery.md or Shopping.md
   - Home improvement / repairs → something like House Projects.md
   - Random thoughts, ideas → something like Notes.md or Ideas.md
   - If the item explicitly names a list or category, use that.
3. If a suitable file already exists, use it. Only create a new file if nothing fits.
4. Call append_to_file with the chosen filename and the original item text.
5. New todo should be formatted in markdown as a check box bullet and date such as "- [ ] Buy milk (12/31/2024)"
6. Reply with a single short sentence saying where you filed the item.

Do not ask clarifying questions. Make a confident decision and file it."""

model = init_chat_model("claude-sonnet-4-6", temperature=0)
agent = create_agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[list_vault_files, append_to_file],
)

# ---------------------------------------------------------------------------
# Flask endpoint
# ---------------------------------------------------------------------------

@app.post("/inbox")
def inbox():
    api_key = request.headers.get("X-API-Key") or request.args.get("api_key")
    if not api_key or api_key != INBOX_API_KEY:
        abort(401)

    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    # Also write to Inbox.md immediately as a safety net
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    inbox_path = Path(OBSIDIAN_VAULT) / "Inbox.md"
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    with inbox_path.open("a") as f:
        f.write(f"\n- {timestamp} — {text}")

    # Run the agent in a background thread so the HTTP response is instant
    def run_agent(item: str) -> None:
        try:
            result = agent.invoke({"messages": [{"role": "user", "content": item}]})
            reply = result["messages"][-1].content
            if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
                import asyncio
                bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
                asyncio.run(bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=reply))
        except Exception as e:
            print(f"[inbox agent error] {e}")

    threading.Thread(target=run_agent, args=(text,), daemon=True).start()

    return jsonify({"ok": True}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5055, debug=False)
