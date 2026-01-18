# Plan: Package kanji-vocab-builder for Distribution

## Overview
Make the CLI tool distributable by: (1) adding simplified configuration for kanji deck, (2) creating setup command to initialize vocab deck/note type, and (3) writing comprehensive README documentation.

## Key Insight
**Kanji deck**: User imports existing "All In One Kanji" deck → needs config
**Vocab deck**: Tool creates and populates from scratch → we control it completely via setup command!

## Decisions Made
- **Config**: Minimal TOML file at `~/.config/jisho-anki/config.toml` - only AnkiConnect URL and kanji deck name
- **Vocab deck**: Created programmatically via `jisho-anki setup` command using AnkiConnect API
- **Note type**: Created programmatically - no .apkg needed, no field mapping config
- **Kanji deck**: Require "All In One Kanji" deck (documented in README)

---

## Phase 1: Configuration System ✅ COMPLETE

### 1.1 Add dependency ✅
**File**: `pyproject.toml`
- Added `pydantic-settings>=2.0.0`

### 1.2 Simplify config module
**File**: `jisho_anki_tool/config.py`

**REVISION NEEDED**: Remove `VocabDeckConfig` and `FieldMapping` - these are now hardcoded constants.

```python
from pathlib import Path
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
import tomllib

class AnkiConnectConfig(BaseModel):
    url: str = "http://localhost:8765"

class KanjiDeckConfig(BaseModel):
    name: str = "All In One Kanji"

class AppConfig(BaseSettings):
    ankiconnect: AnkiConnectConfig = Field(default_factory=AnkiConnectConfig)
    kanji_deck: KanjiDeckConfig = Field(default_factory=KanjiDeckConfig)

# Hardcoded vocab deck settings (we create these via setup command)
VOCAB_DECK_NAME = "JishoAnki-Vocabulary"
VOCAB_NOTE_TYPE = "JishoAnki-Vocab"
VOCAB_TAG = "jisho-anki"

# Hardcoded field names (we create the note type with these fields)
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
```

### 1.3 Update sample config
**File**: `sample-config.toml`
- Simplify to only show ankiconnect and kanji_deck sections

### 1.4 Update tests ✅
**File**: `tests/test_config.py`
- Update tests to match simplified config structure

---

## Phase 2: Setup Command & Refactor connect.py

### 2.1 Add setup command to CLI
**File**: `jisho_anki_tool/cli.py`

Convert to Click group with subcommands:
- `jisho-anki` (default) - Run interactive mode
- `jisho-anki setup` - Initialize vocab deck and note type

```python
@click.group(invoke_without_command=True)
@click.pass_context
def jisho_anki(ctx):
    """CLI tool for building Japanese vocabulary from Anki and Jisho."""
    if ctx.invoked_subcommand is None:
        run_interactive()

@jisho_anki.command()
def setup():
    """Initialize vocabulary deck and note type in Anki."""
    from jisho_anki_tool.setup import run_setup
    run_setup()

def run_interactive():
    """Original interactive loop logic."""
    # Move existing jisho_anki() logic here
```

### 2.2 Create setup module
**File**: `jisho_anki_tool/setup.py` (NEW)

```python
"""Setup wizard for initializing Anki decks and note types."""

from jisho_anki_tool.anki import connect
from jisho_anki_tool.config import VOCAB_DECK_NAME, VOCAB_NOTE_TYPE, FIELDS
from jisho_anki_tool.render import console, success, error, info

def run_setup():
    """Create vocab deck and note type in Anki."""

    # 1. Test AnkiConnect
    info("Testing AnkiConnect connection...")
    try:
        connect.send_request("version")
        success("AnkiConnect is running!")
    except Exception as e:
        error(f"Cannot connect to AnkiConnect: {e}")
        return

    # 2. Create vocab deck
    info(f"Creating deck: {VOCAB_DECK_NAME}")
    try:
        connect.send_request("createDeck", deck=VOCAB_DECK_NAME)
        success(f"Deck '{VOCAB_DECK_NAME}' created!")
    except Exception as e:
        if "already exists" in str(e).lower():
            success(f"Deck '{VOCAB_DECK_NAME}' already exists")
        else:
            error(f"Failed to create deck: {e}")
            return

    # 3. Create note type
    info(f"Creating note type: {VOCAB_NOTE_TYPE}")
    try:
        create_note_type()
        success(f"Note type '{VOCAB_NOTE_TYPE}' created!")
    except Exception as e:
        if "already exists" in str(e).lower():
            success(f"Note type '{VOCAB_NOTE_TYPE}' already exists")
        else:
            error(f"Failed to create note type: {e}")
            return

    success("\n✓ Setup complete! You can now run 'jisho-anki' to start using the tool.")

def create_note_type():
    """Create the vocabulary note type via AnkiConnect."""
    # Implementation using AnkiConnect createModel action
    pass
```

### 2.3 Refactor connect.py
**File**: `jisho_anki_tool/anki/connect.py`

Replace hardcoded values with config/constants:

| Line | Current Value | Change |
|------|---------------|--------|
| 14 | `ANKI_CONNECT_URL = "http://localhost:8765"` | Use `config.ankiconnect.url` |
| 157, 301 | `'deck:"All In One Kanji"'` | Use `config.kanji_deck.name` |
| 198 | `"modelName": "MyJapaneseVocabulary"` | Use `VOCAB_NOTE_TYPE` constant |
| 199-207 | Field name strings | Use `FIELDS` constant |
| 209 | `"jisho-anki-tool v2"` | Use `VOCAB_TAG` constant |
| 264, 335 | `"VocabularyNew"` | Use `VOCAB_DECK_NAME` constant |

---

## Phase 3: Documentation

### 3.1 Write README.md
**File**: `README.md` (REWRITE)

Sections:
1. **What it does** - Brief description of the tool
2. **Installation** - pipx/pip/uv instructions
3. **Prerequisites**
   - Anki Desktop + AnkiConnect plugin
   - "All In One Kanji" deck (link to AnkiWeb)
4. **Quick Start**
   ```bash
   # 1. Install the tool
   pipx install kanji-vocab-builder

   # 2. Run setup (creates vocab deck and note type)
   jisho-anki setup

   # 3. Start using it
   jisho-anki
   ```
5. **Configuration** (optional)
   - Config file location
   - Only needed if using different kanji deck or AnkiConnect URL
6. **Usage** - Command reference (n, c, q, kanji input, etc.)
7. **How It Works** - Explanation of the workflow

### 3.2 Update pyproject.toml metadata
**File**: `pyproject.toml`
- Update description
- Add repository URL, author, license, classifiers

---

## Phase 4: Testing

### 4.1 Update config tests ✅ (PARTIAL - needs update for simplified config)
**File**: `tests/test_config.py`
- Remove tests for removed config sections
- Keep tests for AnkiConnect and kanji deck config

### 4.2 Add setup tests
**File**: `tests/test_setup.py` (NEW)
- Test setup command with mocked AnkiConnect
- Test deck creation
- Test note type creation

### 4.3 Update connect.py tests
**File**: `tests/test_anki_connect.py`
- Add mock config fixture
- Update tests to use new constants

---

## Files Summary

| File | Action | Status |
|------|--------|--------|
| `jisho_anki_tool/config.py` | MODIFY (simplify) | ✅ Created, needs simplification |
| `jisho_anki_tool/setup.py` | CREATE | Pending |
| `jisho_anki_tool/cli.py` | MODIFY (add subcommands) | Pending |
| `jisho_anki_tool/anki/connect.py` | MODIFY (use config) | Pending |
| `pyproject.toml` | MODIFY (metadata) | ✅ Dependencies added |
| `sample-config.toml` | MODIFY (simplify) | ✅ Created, needs simplification |
| `README.md` | REWRITE | Pending |
| `tests/test_config.py` | MODIFY | ✅ Created, needs update |
| `tests/test_setup.py` | CREATE | Pending |

---

## Verification Steps

1. **Config loading**: Verify simplified config loads correctly
2. **Setup command**: Run `jisho-anki setup` with Anki open, verify deck and note type are created
3. **CLI works**: Run `jisho-anki` and verify interactive mode works
4. **Tests pass**: Run full test suite
5. **Config optional**: Verify tool works without config file (uses defaults)

---

## User Flow (After Implementation)

1. **Install Anki** + AnkiConnect plugin
2. **Import "All In One Kanji" deck** from AnkiWeb
3. **Install tool**: `pipx install kanji-vocab-builder`
4. **Run setup**: `jisho-anki setup` (creates vocab deck/note type)
5. **Use tool**: `jisho-anki` (interactive mode)
6. **(Optional)** Create `~/.config/jisho-anki/config.toml` if using different kanji deck
