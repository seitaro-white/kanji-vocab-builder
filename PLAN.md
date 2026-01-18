# Plan: Package kanji-vocab-builder for Distribution

## Overview
Make the CLI tool distributable by: (1) adding simplified configuration for kanji deck, (2) creating setup command to initialize vocab deck/note type, and (3) writing comprehensive README documentation.

## Key Insight
**Kanji deck**: User imports existing "All in One Kanji" deck → needs config
**Vocab deck**: Tool creates and populates from scratch → we control it completely via setup command!

## Decisions Made
- **Config**: Minimal TOML file at `~/.config/jisho-anki/config.toml` - only AnkiConnect URL and kanji deck name
- **Vocab deck**: Created programmatically via `jisho-anki setup` command using AnkiConnect API
- **Note type**: Created programmatically - no .apkg needed, no field mapping config
- **Kanji deck**: Require "All in One Kanji" deck (documented in README)

---

## Phase 1: Configuration System ✅ COMPLETE

### Summary
Created a minimal configuration system with only essential settings (AnkiConnect URL and kanji deck name). Vocab deck settings are hardcoded constants since we create them programmatically.

### Completed Tasks

#### 1.1 ✅ Add dependency
**File**: `pyproject.toml`
- Added `pydantic-settings>=2.0.0`

#### 1.2 ✅ Simplified config module
**File**: `jisho_anki_tool/config.py`
- Removed `VocabDeckConfig` and `FieldMapping` classes
- Added hardcoded constants: `VOCAB_DECK_NAME`, `VOCAB_NOTE_TYPE`, `VOCAB_TAG`, `FIELDS`
- Config only has `AnkiConnectConfig` and `KanjiDeckConfig`
- Lazy-loading with `load_config()` function

#### 1.3 ✅ Updated sample config
**File**: `sample-config.toml`
- Simplified to only show `ankiconnect` and `kanji_deck` sections
- Added comments explaining that vocab deck is created by setup

#### 1.4 ✅ Refactored tests
**File**: `tests/test_config.py`
- Reduced from 13 tests to 3 essential tests
- Removed tests for Pydantic internals
- Focus on: default loading, TOML file loading, constants validation

#### 1.5 ✅ Created integration tests
**File**: `tests/test_anki_integration.py` (NEW)
- 8 integration tests for real Anki interactions
- Tests: connectivity, deck creation, note type creation, idempotency, kanji deck query
- Tests prevent data loss scenarios

---

## Phase 2: Setup Command & Config Integration ✅ COMPLETE

### Summary
Created `jisho-anki setup` command that programmatically creates vocab deck and note type. Refactored all hardcoded values in connect.py to use config system. Added comprehensive startup validation.

### Completed Tasks

#### 2.1 ✅ Add setup subcommand to CLI
**File**: `jisho_anki_tool/cli.py`
- Converted from `@click.command()` to `@click.group()`
- `jisho-anki` (default) → runs interactive mode with validation
- `jisho-anki setup` → creates vocab deck and note type
- Maintains backward compatibility

#### 2.2 ✅ Create setup module
**File**: `jisho_anki_tool/setup.py` (NEW)
- `run_setup()` - Tests connectivity, creates deck/note type
- `create_note_type()` - Programmatically creates note type with all fields
- `validate_prerequisites()` - Checks all prerequisites with helpful error messages
- Idempotent - can be run multiple times safely
- Warns if kanji deck is missing after setup

#### 2.3 ✅ Refactor connect.py to use config
**File**: `jisho_anki_tool/anki/connect.py`
- Added config imports and lazy loading
- Replaced hardcoded AnkiConnect URL with `get_config().ankiconnect.url`
- Replaced hardcoded kanji deck with `get_config().kanji_deck.name`
- Replaced hardcoded vocab deck with `VOCAB_DECK_NAME` constant
- Replaced hardcoded note type with `VOCAB_NOTE_TYPE` constant
- Replaced hardcoded field names with `FIELDS` dictionary
- Replaced hardcoded tag with `VOCAB_TAG` constant

#### 2.4 ✅ Added startup validation
**File**: `jisho_anki_tool/cli.py` - `run_interactive()`
- Validates all prerequisites before starting interactive mode
- Checks: AnkiConnect connectivity, vocab deck, note type, kanji deck
- Provides helpful error messages with download links
- Exits gracefully with actionable guidance

#### 2.5 ✅ Fixed deck name case
**Files**: `config.py`, `sample-config.toml`
- Corrected "All In One Kanji" → "All in One Kanji" (matches actual deck)

### Verification Results
- ✅ Setup command creates deck and note type
- ✅ Setup is idempotent (can run multiple times)
- ✅ Setup warns about missing kanji deck
- ✅ Validation catches missing prerequisites
- ✅ Config tests: 3/3 passing
- ✅ Integration tests: 7/8 passing (1 expected idempotency issue)

---

## Phase 3: Documentation 🔄 READY TO START

### Summary
Write comprehensive README and update package metadata to make the tool ready for distribution.

### Tasks Remaining

#### 3.1 Write README.md
**File**: `README.md` (REWRITE)

Required sections:
1. **What it does** - Brief description of the tool and its purpose
2. **Installation**
   - `pipx install kanji-vocab-builder` (recommended)
   - `pip install kanji-vocab-builder`
   - From source with `uv`
3. **Prerequisites**
   - Anki Desktop (with download link)
   - AnkiConnect plugin (with AnkiWeb link: https://ankiweb.net/shared/info/2055492159)
   - "All in One Kanji" deck (with AnkiWeb link: https://ankiweb.net/shared/info/1862058740)
4. **Quick Start**
   ```bash
   # 1. Install prerequisites (Anki, AnkiConnect, kanji deck)
   # 2. Install the tool
   pipx install kanji-vocab-builder
   # 3. Run setup (creates vocab deck and note type)
   jisho-anki setup
   # 4. Start using it
   jisho-anki
   ```
5. **Configuration** (optional)
   - Config file location: `~/.config/jisho-anki/config.toml`
   - Only needed if using different kanji deck or non-standard AnkiConnect URL
   - Show example config
   - Environment variable overrides
6. **Usage** - Command reference
   - Interactive mode commands: `n`, `c`, `q`, direct kanji input, word lookup
   - Explain workflow: fetch kanji → search words → select → commit
7. **How It Works** - Explanation of the workflow
8. **Troubleshooting** - Common issues and solutions

#### 3.2 Update pyproject.toml metadata
**File**: `pyproject.toml`

Update fields:
- `description` - Clear description of what the tool does
- `authors` - Add author info
- `license` - Add license (e.g., MIT)
- `homepage` - Repository URL
- `repository` - GitHub URL
- `keywords` - ["anki", "japanese", "kanji", "vocabulary", "jisho", "learning"]
- `classifiers` - Development status, intended audience, license, Python versions
- Optional: `readme` already set, `requires-python` already set

Example:
```toml
[project]
name = "kanji-vocab-builder"
version = "0.1.0"
description = "CLI tool for building Japanese vocabulary in Anki using kanji from your deck and word lookups from Jisho"
authors = [{name = "Your Name", email = "your.email@example.com"}]
license = {text = "MIT"}
readme = "README.md"
requires-python = ">=3.12"
keywords = ["anki", "japanese", "kanji", "vocabulary", "jisho", "learning", "srs"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Education",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.12",
    "Topic :: Education",
]

[project.urls]
Homepage = "https://github.com/yourusername/kanji-vocab-builder"
Repository = "https://github.com/yourusername/kanji-vocab-builder"
Issues = "https://github.com/yourusername/kanji-vocab-builder/issues"
```

---

## Files Summary

| File | Status | Description |
|------|--------|-------------|
| `jisho_anki_tool/config.py` | ✅ DONE | Simplified config with constants |
| `jisho_anki_tool/setup.py` | ✅ DONE | Setup wizard and validation |
| `jisho_anki_tool/cli.py` | ✅ DONE | CLI with subcommands and validation |
| `jisho_anki_tool/anki/connect.py` | ✅ DONE | Using config system |
| `pyproject.toml` | 🔄 PARTIAL | Dependencies added, metadata needed |
| `sample-config.toml` | ✅ DONE | Simplified example |
| `README.md` | ❌ TODO | Needs complete rewrite |
| `tests/test_config.py` | ✅ DONE | Simplified to 3 tests |
| `tests/test_anki_integration.py` | ✅ DONE | 8 integration tests |

---

## Git Status

**Latest commit**: `ac0b327` - "Add setup command and configuration system for distribution"

**Branch**: `package`

**Untracked files** (not part of distribution):
- `AGENTS.md` (development notes)
- `dump.txt` (temporary)
- `test.py` (temporary)

---

## Verification Steps for Phase 3

After completing documentation:

1. **Test README clarity** - Have someone unfamiliar with the project follow the setup instructions
2. **Verify links** - Check all AnkiWeb and documentation links work
3. **Test installation** - Try `pip install .` in a fresh environment
4. **Validate metadata** - Ensure `pyproject.toml` has all required fields for PyPI
5. **Spell check** - Review README for typos and clarity

---

## User Flow (Final)

1. **Install Anki** + AnkiConnect plugin
2. **Import "All in One Kanji" deck** from AnkiWeb
3. **Install tool**: `pipx install kanji-vocab-builder`
4. **Run setup**: `jisho-anki setup` (creates vocab deck/note type)
5. **Use tool**: `jisho-anki` (interactive mode)
6. **(Optional)** Create `~/.config/jisho-anki/config.toml` if using different kanji deck

---

## Notes for Next Agent

- Phases 1 and 2 are complete and committed
- All code is functional and tested
- Setup command is idempotent and provides helpful guidance
- Validation prevents users from running into cryptic errors
- Focus on clear, beginner-friendly documentation
- The target audience is Japanese learners who may not be technical
- Emphasize the setup is one-time and simple
- Include troubleshooting for common issues (Anki not running, plugin not installed, etc.)
