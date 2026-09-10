"""Configuration management for kanji-vocab-miner."""

from importlib import resources
import os
from pathlib import Path
from typing import Optional, Union

import tomllib
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AnkiConnectConfig(BaseModel):
    """Configuration for AnkiConnect connection."""

    url: str = "http://localhost:8765"


class KanjiDeckConfig(BaseModel):
    """Configuration for kanji deck."""

    name: str = "All in One Kanji"


class LLMConfig(BaseModel):
    """Non-secret settings for vocabulary enrichment."""

    prompt_path: Path = Path("~/.config/kanji-vocab-miner/enrichment-prompt.md")
    concurrency: int = Field(default=5, ge=1, le=10)


class AppConfig(BaseSettings):
    """Application configuration with environment variable support."""

    model_config = SettingsConfigDict(
        env_prefix="KANJI_VOCAB_MINER_", env_nested_delimiter="__"
    )

    ankiconnect: AnkiConnectConfig = Field(default_factory=AnkiConnectConfig)
    kanji_deck: KanjiDeckConfig = Field(default_factory=KanjiDeckConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)


LLM_API_KEY_ENV_VAR = "KANJI_VOCAB_MINER_LLM__API_KEY"
DEFAULT_PROMPT_RESOURCE = "resources/enrichment-prompt.md"


def resolve_prompt_path(prompt_path: Union[Path, str]) -> Path:
    """Expand a configured prompt path without requiring the path to exist."""
    path = Path(prompt_path)
    path_text = str(path)
    if path_text == "~":
        return Path.home()
    if path_text.startswith("~/"):
        return Path.home() / path_text[2:]
    return path.expanduser()


def get_llm_api_key() -> Optional[str]:
    """Read the DeepSeek API key exclusively from the process environment."""
    api_key = os.environ.get(LLM_API_KEY_ENV_VAR)
    if api_key is None:
        return None
    return api_key.strip() or None


def provision_default_prompt(prompt_path: Union[Path, str]) -> Path:
    """Copy the packaged enrichment prompt when the destination is absent."""
    destination = resolve_prompt_path(prompt_path)
    if destination.exists():
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    prompt_bytes = (
        resources.files("kanji_vocab_miner")
        .joinpath(DEFAULT_PROMPT_RESOURCE)
        .read_bytes()
    )
    try:
        with destination.open("xb") as prompt_file:
            prompt_file.write(prompt_bytes)
    except FileExistsError:
        # Another setup process provisioned the prompt after the existence check.
        pass
    return destination


# Hardcoded vocabulary deck settings (created via setup command)
VOCAB_DECK_NAME = "KanjiVocabMiner-Vocabulary"
LEGACY_VOCAB_NOTE_TYPE = "MyJapaneseVocabulary"
VOCAB_NOTE_TYPE_V2 = "MyJapaneseVocabularyV2"
VOCAB_NOTE_TYPE_V3 = "MyJapaneseVocabularyV3"
VOCAB_NOTE_TYPE = LEGACY_VOCAB_NOTE_TYPE
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
LEGACY_FIELDS = FIELDS
VOCAB_V2_FIELDS = {
    **LEGACY_FIELDS,
    "japanese_definition": "JapaneseDefinition",
    "japanese_cue": "JapaneseCue",
    "recall": "Recall",
    "definition_source": "DefinitionSource",
    "definition_url": "DefinitionURL",
}
VOCAB_V3_FIELDS = {
    **VOCAB_V2_FIELDS,
    "nuance": "Nuance",
    "example": "Example",
    "kanji_explanation": "KanjiExplanation",
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
