"""
13TMOS Corpus Loader -- Direct Document Injection

Reads all .md and .txt files from a directory and formats them
for injection into the system prompt. Not RAG. Direct injection.
At current corpus size this fits in the context window.
"""
import json
from pathlib import Path


def load_corpus(docs_dir: str, extras: list[str] = None) -> str:
    """
    Read all .md and .txt files in docs_dir.
    Optionally include extra file paths (e.g., config/identity.json).

    Returns a formatted string for injection into the system prompt.
    Each document is wrapped with a header showing its filename.
    """
    docs_path = Path(docs_dir)
    sections = []

    # Load .md and .txt files from docs directory
    if docs_path.exists():
        for ext in ("*.md", "*.txt"):
            for filepath in sorted(docs_path.glob(ext)):
                try:
                    content = filepath.read_text(encoding="utf-8").strip()
                    if content:
                        sections.append(
                            f"--- DOCUMENT: {filepath.name} ---\n\n{content}"
                        )
                except Exception:
                    continue

    # Load extra files
    if extras:
        for extra_path_str in extras:
            extra_path = Path(extra_path_str)
            if not extra_path.exists():
                continue
            try:
                content = extra_path.read_text(encoding="utf-8").strip()
                if extra_path.suffix == ".json":
                    # Pretty-format JSON
                    parsed = json.loads(content)
                    content = json.dumps(parsed, indent=2)
                if content:
                    sections.append(
                        f"--- DOCUMENT: {extra_path.name} ---\n\n{content}"
                    )
            except Exception:
                continue

    if not sections:
        return "(no corpus documents found)"

    return "\n\n".join(sections)


def corpus_stats(docs_dir: str) -> dict:
    """Return stats about the corpus: doc count and total characters."""
    docs_path = Path(docs_dir)
    count = 0
    chars = 0
    if docs_path.exists():
        for ext in ("*.md", "*.txt"):
            for filepath in docs_path.glob(ext):
                try:
                    content = filepath.read_text(encoding="utf-8")
                    count += 1
                    chars += len(content)
                except Exception:
                    continue
    return {"doc_count": count, "total_chars": chars}
