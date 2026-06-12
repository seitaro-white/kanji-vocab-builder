"""Persist vocabulary the user knows but hasn't made a flashcard for.

A plain newline-delimited text file of expressions (kanji surface forms),
stored next to the app config. Counted alongside the Anki deck when computing
vocab coverage, so the charts reflect words known-but-not-carded.
"""

from pathlib import Path

from kanji_vocab_miner.config import get_config_path


def known_words_path() -> Path:
    """Location of the known-words file (sibling of the config file)."""
    return get_config_path().parent / "known_vocab.txt"


def load_known_words(path: Path | None = None) -> set[str]:
    """Return the set of known words, or an empty set if the file is absent."""
    path = path or known_words_path()
    if not path.exists():
        return set()
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def add_known_word(word: str, path: Path | None = None) -> bool:
    """Append `word` to the store. Returns False if it was already present."""
    path = path or known_words_path()
    if word in load_known_words(path):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(word + "\n")
    return True
