"""Tests for configuration management."""

from pathlib import Path
from unittest.mock import patch

from kanji_vocab_miner.config import (
    VOCAB_DECK_NAME,
    VOCAB_NOTE_TYPE,
    VOCAB_TAG,
    FIELDS,
    load_config,
)


def test_load_config_defaults():
    """Test that config loads with sensible defaults when no file exists."""
    with patch("kanji_vocab_miner.config.get_config_path") as mock_path:
        mock_path.return_value = Path("/nonexistent/config.toml")
        config = load_config()

        # Verify we got a config object with defaults
        assert config.ankiconnect.url == "http://localhost:8765"
        assert config.kanji_deck.name == "All in One Kanji"


def test_load_config_from_file(tmp_path):
    """Test that config values can be overridden from TOML file."""
    config_file = tmp_path / "config.toml"
    config_content = """
        [ankiconnect]
        url = "http://localhost:9999"

        [kanji_deck]
        name = "My Custom Kanji Deck"
        """
    config_file.write_text(config_content)

    with patch("kanji_vocab_miner.config.get_config_path") as mock_path:
        mock_path.return_value = config_file
        config = load_config()

        assert config.ankiconnect.url == "http://localhost:9999"
        assert config.kanji_deck.name == "My Custom Kanji Deck"


def test_vocab_constants_defined():
    """Test that hardcoded vocab constants are defined."""
    # These are created by the setup command, not configurable
    assert VOCAB_DECK_NAME == "KanjiVocabMiner-Vocabulary"
    assert VOCAB_NOTE_TYPE == "KanjiVocabMiner-Vocab"
    assert VOCAB_TAG == "kanji-vocab-miner"
    assert len(FIELDS) == 8  # Should have 8 fields
