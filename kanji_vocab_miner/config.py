"""Configuration management for kanji-vocab-miner."""

from pathlib import Path
from typing import Optional

import tomllib
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AnkiConnectConfig(BaseModel):
    """Configuration for AnkiConnect connection."""

    url: str = "http://localhost:8765"


class KanjiDeckConfig(BaseModel):
    """Configuration for kanji deck."""

    name: str = "All in One Kanji"


class AppConfig(BaseSettings):
    """Application configuration with environment variable support."""

    model_config = SettingsConfigDict(
        env_prefix="KANJI_VOCAB_MINER_", env_nested_delimiter="__"
    )

    ankiconnect: AnkiConnectConfig = Field(default_factory=AnkiConnectConfig)
    kanji_deck: KanjiDeckConfig = Field(default_factory=KanjiDeckConfig)


# Hardcoded vocabulary deck settings (created via setup command)
VOCAB_DECK_NAME = "KanjiVocabMiner-Vocabulary"
VOCAB_NOTE_TYPE = "KanjiVocabMiner-Vocab"
VOCAB_TAG = "kanji-vocab-miner"

# Hardcoded field names (note type created with these fields)
FIELDS = {
    "front": "Front",
    "back": "Back",
    "expression": "Expression",
    "kana_reading": "Kana Reading",
    "grammar": "Grammar",
    "definition": "Definition",
    "additional_definitions": "Additional Definitions",
    "jlpt": "JLPT",
}


def get_config_path() -> Path:
    """Return XDG-compliant config file path.

    Checks for config in order:
    1. ~/.config/kanji-vocab-miner/config.toml (XDG base directory)
    2. ~/.kanji-vocab-miner.toml (fallback)

    Returns the first existing path, or the XDG path if neither exists.
    """
    xdg_config = Path.home() / ".config" / "kanji-vocab-miner" / "config.toml"
    home_config = Path.home() / ".kanji-vocab-miner.toml"

    if xdg_config.exists():
        return xdg_config
    if home_config.exists():
        return home_config

    return xdg_config  # Default location for new configs


def load_config() -> AppConfig:
    """Load configuration from file or use defaults.

    Loads config from TOML file at get_config_path() if it exists.
    Falls back to default values if no config file is found.
    Environment variables with KANJI_VOCAB_MINER_ prefix override all settings.

    Returns:
        AppConfig instance with loaded or default configuration
    """
    config_path = get_config_path()

    if config_path.exists():
        with open(config_path, "rb") as f:
            toml_data = tomllib.load(f)
        return AppConfig(**toml_data)

    return AppConfig()  # Use defaults + env vars
