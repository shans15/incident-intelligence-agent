import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class TriageError(Exception):
    """Raised when a triage workflow fails non-transiently."""
    pass


@dataclass
class Config:
    api_key: str
    model: str
    chroma_persist_dir: str


def get_config() -> Config:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise TriageError(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Copy .env.example to .env and add your key."
        )
    return Config(
        api_key=api_key,
        model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
        chroma_persist_dir=os.environ.get(
            "CHROMA_PERSIST_DIR",
            str(Path.home() / ".incident-intel" / "chroma"),
        ),
    )
