"""Tests for configuration management."""

from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from kanji_vocab_miner.config import (
    AppConfig,
    FIELDS,
    LEGACY_FIELDS,
    LEGACY_VOCAB_NOTE_TYPE,
    VOCAB_DECK_NAME,
    VOCAB_NOTE_TYPE,
    VOCAB_NOTE_TYPE_V2,
    VOCAB_NOTE_TYPE_V3,
    VOCAB_TAG,
    VOCAB_V2_FIELDS,
    VOCAB_V3_FIELDS,
    get_llm_api_key,
    load_config,
    provision_default_prompt,
    resolve_prompt_path,
)


def test_load_config_defaults():
    """Test that config loads with sensible defaults when no file exists."""
    with patch("kanji_vocab_miner.config.get_config_path") as mock_path:
        mock_path.return_value = Path("/nonexistent/config.toml")
        config = load_config()

        # Verify we got a config object with defaults
        assert config.ankiconnect.url == "http://localhost:8765"
        assert config.kanji_deck.name == "All in One Kanji"
        assert config.llm.concurrency == 5
        assert config.llm.prompt_path == Path(
            "~/.config/kanji-vocab-miner/enrichment-prompt.md"
        )


def test_load_config_from_file(tmp_path):
    """Test that config values can be overridden from TOML file."""
    config_file = tmp_path / "config.toml"
    config_content = """
        [ankiconnect]
        url = "http://localhost:9999"

        [kanji_deck]
        name = "My Custom Kanji Deck"

        [llm]
        prompt_path = "/tmp/custom-enrichment.md"
        concurrency = 3
        """
    config_file.write_text(config_content)

    with patch("kanji_vocab_miner.config.get_config_path") as mock_path:
        mock_path.return_value = config_file
        config = load_config()

        assert config.ankiconnect.url == "http://localhost:9999"
        assert config.kanji_deck.name == "My Custom Kanji Deck"
        assert config.llm.prompt_path == Path("/tmp/custom-enrichment.md")
        assert config.llm.concurrency == 3


def test_resolve_prompt_path_expands_tilde_with_current_home(tmp_path) -> None:
    """Prompt resolution expands the configured home deterministically."""
    with patch("kanji_vocab_miner.config.Path.home", return_value=tmp_path):
        resolved = resolve_prompt_path(Path("~/.config/custom-prompt.md"))

    assert resolved == tmp_path / ".config" / "custom-prompt.md"


def test_llm_api_key_is_not_read_from_toml(tmp_path, monkeypatch) -> None:
    """The secret is never accepted as part of the TOML configuration model."""
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[llm]\napi_key = "toml-secret"\n', encoding="utf-8"
    )
    monkeypatch.delenv("KANJI_VOCAB_MINER_LLM__API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    with patch("kanji_vocab_miner.config.get_config_path", return_value=config_file):
        config = load_config()

    assert not hasattr(config.llm, "api_key")
    assert get_llm_api_key() is None


def test_llm_api_key_is_read_from_current_directory_dotenv(
    tmp_path, monkeypatch
) -> None:
    """A repository-local .env supplies the key without shell setup."""
    (tmp_path / ".env").write_text(
        'KANJI_VOCAB_MINER_LLM__API_KEY="dotenv-secret"\n', encoding="utf-8"
    )
    monkeypatch.delenv("KANJI_VOCAB_MINER_LLM__API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    assert get_llm_api_key() == "dotenv-secret"


def test_llm_api_key_environment_overrides_dotenv(tmp_path, monkeypatch) -> None:
    """An explicitly exported key takes precedence over a local .env value."""
    (tmp_path / ".env").write_text(
        "KANJI_VOCAB_MINER_LLM__API_KEY=dotenv-secret\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KANJI_VOCAB_MINER_LLM__API_KEY", "environment-secret")

    assert get_llm_api_key() == "environment-secret"


def test_invalid_llm_concurrency_is_rejected() -> None:
    """Generation concurrency stays within the supported worker range."""
    for concurrency in (0, 11):
        with pytest.raises(ValidationError):
            AppConfig(llm={"concurrency": concurrency})


def test_provision_default_prompt_creates_missing_parent_and_file(tmp_path) -> None:
    """Provisioning installs the packaged editable prompt on first setup."""
    destination = tmp_path / "nested" / "enrichment-prompt.md"

    result = provision_default_prompt(destination)

    assert result == destination
    assert destination.is_file()
    content = destination.read_text(encoding="utf-8")
    assert "register, connotation" in content
    assert "Why these kanji" in content
    assert "application separately" in content


def test_provision_default_prompt_preserves_existing_bytes(tmp_path) -> None:
    """Provisioning never overwrites a user's edited prompt."""
    destination = tmp_path / "enrichment-prompt.md"
    existing = b"My edited prompt\n\xff"
    destination.write_bytes(existing)

    provision_default_prompt(destination)

    assert destination.read_bytes() == existing


def test_vocab_constants_defined():
    """Test that hardcoded vocab constants are defined."""
    # These are created by the setup command, not configurable
    assert VOCAB_DECK_NAME == "KanjiVocabMiner-Vocabulary"
    assert VOCAB_NOTE_TYPE == "MyJapaneseVocabulary"
    assert VOCAB_TAG == "kanji-vocab-miner"
    assert len(FIELDS) == 8  # Should have 8 fields


def test_v3_fields_extend_v2_fields_in_exact_order() -> None:
    assert VOCAB_NOTE_TYPE_V3 == "MyJapaneseVocabularyV3"
    assert list(VOCAB_V3_FIELDS.values()) == list(VOCAB_V2_FIELDS.values()) + [
        "Nuance",
        "Example",
        "KanjiExplanation",
    ]


def test_v2_fields_extend_legacy_fields_in_intended_order() -> None:
    """V2 retains all legacy fields before its five additional fields."""
    assert LEGACY_VOCAB_NOTE_TYPE == "MyJapaneseVocabulary"
    assert VOCAB_NOTE_TYPE_V2 == "MyJapaneseVocabularyV2"
    assert LEGACY_FIELDS is FIELDS
    assert VOCAB_NOTE_TYPE == LEGACY_VOCAB_NOTE_TYPE
    assert list(VOCAB_V2_FIELDS.values()) == [
        "Front",
        "Back",
        "Expression",
        "Kana Reading",
        "Grammar",
        "Definition",
        "Additional Definitions",
        "JLPT",
        "JapaneseDefinition",
        "JapaneseCue",
        "Recall",
        "DefinitionSource",
        "DefinitionURL",
    ]
