import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from langchain.tools import tool

load_dotenv()

OBSIDIAN_VAULT = os.environ.get("OBSIDIAN_VAULT", "")


@tool
def list_vault_files() -> str:
    """List all markdown files currently in the Obsidian vault.
    Returns a newline-separated list of relative paths (e.g. 'ToDos/Grocery.md', 'Trips/Paris Trip 2026-05.md').
    Use this to discover existing lists before deciding where to file an item."""
    vault = Path(OBSIDIAN_VAULT)
    files = sorted(
        str(p.relative_to(vault))
        for p in vault.glob("**/*.md")
        if p.name != "Inbox.md"
    )
    return "\n".join(files) if files else "(no files yet)"


@tool
def read_file(filename: str) -> str:
    """Read the contents of a markdown file in the Obsidian vault.
    Use this to answer questions like 'what's on my grocery list?' or 'what are my house projects?'.
    Args:
        filename: Relative path within the vault (e.g. 'ToDos/Grocery.md'). Must end with .md.
    """
    if not filename.endswith(".md"):
        filename = filename + ".md"
    path = Path(OBSIDIAN_VAULT) / filename
    if not path.exists():
        return f"{filename} does not exist."
    return path.read_text()


@tool
def add_todo(filename: str, text: str) -> str:
    """Append a timestamped todo bullet entry to a markdown file under the ToDos/ folder.
    If the file does not exist it will be created with a heading derived from the filename.
    Args:
        filename: The .md filename (e.g. 'Grocery.md'). Do NOT include the 'ToDos/' prefix — it is added automatically.
        text: The todo item text to append (without timestamp — that is added automatically).
    """
    if not filename.endswith(".md"):
        filename = filename + ".md"
    # Strip any leading path the model may accidentally include, then place under ToDos/
    filename = Path(filename).name
    path = Path(OBSIDIAN_VAULT) / "ToDos" / filename
    path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d")
    entry = f"\n- [ ] {text} ({timestamp})"

    if not path.exists():
        heading = path.stem.replace("_", " ").replace("-", " ").title()
        path.write_text(f"# {heading}\n")

    with path.open("a") as f:
        f.write(entry)

    return f"Appended to ToDos/{filename}."


@tool
def write_trip_file(filename: str, content: str) -> str:
    """Write or update a trip planning file under the Trips/ folder in the Obsidian vault.
    Use this for flight bookings, hotel reservations, itineraries, and other trip details.
    Unlike add_todo, this writes free-form markdown content (not a todo bullet).
    If the file already exists, the content is appended. If not, it is created.
    Args:
        filename: The .md filename using the DESTINATION city (where they fly TO), NOT the origin/departure city.
            e.g. flight from Seattle to Sacramento → 'Sacramento Trip 2026-05.md' (NEVER 'Seattle Trip 2026-05.md')
            Do NOT include the 'Trips/' prefix — it is added automatically.
        content: The full markdown content to write (structured trip details).
    """
    if not filename.endswith(".md"):
        filename = filename + ".md"
    filename = Path(filename).name
    path = Path(OBSIDIAN_VAULT) / "Trips" / filename
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        with path.open("a") as f:
            f.write(f"\n\n{content.strip()}")
    else:
        path.write_text(content.strip())

    return f"Trip file written: Trips/{filename}."
