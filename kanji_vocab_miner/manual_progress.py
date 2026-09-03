"""Load the vocabulary baseline and manually tracked textbook progress."""

import tomllib
from pathlib import Path

from kanji_vocab_miner.progress import ManualProgressCounts

MANUAL_PROGRESS_FILENAME = "manual_progress.toml"


def manual_progress_path() -> Path:
    """Return the manual progress path in the current directory."""
    return Path.cwd() / MANUAL_PROGRESS_FILENAME


def load_manual_progress(path: Path | None = None) -> ManualProgressCounts:
    """Load vocabulary and completed textbook section counts from TOML."""
    with open(path or manual_progress_path(), "rb") as progress_file:
        return ManualProgressCounts(**tomllib.load(progress_file))
