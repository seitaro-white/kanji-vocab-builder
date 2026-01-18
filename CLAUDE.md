# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Reference

**Run the CLI:**
```bash
uv run jisho-anki
```

**Run tests:**
```bash
uv run pytest                                    # Full suite
uv run pytest tests/test_card_processor.py       # Single file
uv run pytest tests/test_card_processor.py -k test_sort_and_limit_words  # Single test
```

**Dependency management:**
```bash
uv sync          # Install dependencies
uv add <pkg>     # Add dependency
uv lock          # Regenerate lockfile
```

## Project Overview

CLI tool (`jisho-anki`) that bridges Anki and Jisho for Japanese vocabulary building. Users fetch kanji from their Anki deck, search Jisho for vocabulary containing that kanji, and commit selected words back to Anki.

**External services:**
- AnkiConnect at `http://localhost:8765` (requires Anki running with plugin)
- Jisho API at `https://jisho.org/api/v1/search/words`

## Architecture

```
jisho_anki_tool/
├── cli.py              # Main interactive loop, command handlers
├── jisho.py            # Jisho API client, HTML scraping
├── card_processor.py   # Word sorting/filtering (pure logic, no IO)
├── render.py           # Rich terminal rendering
├── utils.py            # Character validation helpers
└── anki/
    ├── connect.py      # AnkiConnect HTTP client
    └── schemas.py      # Pydantic models for Anki cards
```

**Key principle:** Separation of fetch (jisho.py) → process (card_processor.py) → render (render.py). Keep `card_processor.py` pure for testability.

## Testing Notes

- Tests in `test_anki_connect.py` require Anki running with AnkiConnect
- Prefer mocking HTTP calls for unit tests
- Mark integration tests with `@pytest.mark.integration` when introducing new ones

## Detailed Guidelines

See `AGENTS.md` for comprehensive code style, naming conventions, error handling patterns, and contribution workflow.
