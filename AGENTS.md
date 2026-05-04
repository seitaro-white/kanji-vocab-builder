# AGENTS.md

This document gives every agent working inside `kanji-vocab-builder` the shared context needed to stay productive and consistent. Its scope is the entire repository unless another nested `AGENTS.md` is introduced later. Re-read this file before changing code in this repo.

---

## Project Snapshot

1. **Purpose**: CLI helper (`jisho-anki`) that pulls kanji from Anki, queries Jisho/Jamdict, and lets users push curated vocab back into Anki decks.
2. **Environment**: Python 3.12 managed via `uv` (already bootstrapped). All commands below assume `uv`.
3. **Structure highlights**:
   - `jisho_anki_tool/`: core package (CLI loop, Anki connector, render helpers, card processing, utilities).
   - `tests/`: Pytest suite (mix of pure logic tests and integration tests that expect live Anki/Jisho services).
   - `pyproject.toml`: dependency + script definitions.
4. **External services**: `requests` hits Jisho/Jamdict endpoints; Anki operations go through AnkiConnect on `http://localhost:8765`.

---

## Environment & Dependency Management

1. **Sync virtual environment** (installs pinned dependencies into `.venv`):
   ```bash
   uv sync
   ```
2. **Run commands inside the environment**:
   ```bash
   uv run <python or script command>
   ```
3. **Ad-hoc dep adds** (when user approves):
   ```bash
   uv add <package>
   uv remove <package>
   ```
4. **Lockfile**: `uv.lock` must stay in sync with `pyproject.toml`. Regenerate with `uv lock` after dependency edits.

---

## Build, Lint, and Test Commands

These are the canonical commands. Prefer the most specific scope possible (file or test) before running the entire suite.

| Task | Command | Notes |
| --- | --- | --- |
| Full test suite | `uv run pytest` | Network-heavy tests require Anki running and internet access.
| Single test file | `uv run pytest tests/test_card_processor.py` | Replace path with the target module.
| Single test function | `uv run pytest tests/test_card_processor.py -k test_sort_and_limit_words` | Use `-k` for function substring match.
| Fast unit subset | `uv run pytest tests/test_card_processor.py tests/test_jisho_api.py -m "not integration"` | The suite has no pytest markers yet; feel free to introduce `@pytest.mark.integration` for Anki/Jisho-dependent tests.
| Syntax / lint sanity | `uv run python -m compileall jisho_anki_tool` | Acts as a quick syntax check in absence of a dedicated linter.
| (Optional) Static format check | `uv run python -m ruff check jisho_anki_tool` | Ruff is not bundled; install via `uv tool install ruff` if the user requests linting.
| Build distributables | `uv build` | Produces wheel + sdist under `dist/`.

**Testing etiquette**
- When editing logic that touches Anki/Jisho, prefer writing/expanding unit tests that mock network calls. Only run the full integration suite if the environment allows the required services.
- Tests living under `tests/test_anki_connect.py` make real HTTP requests to AnkiConnect. Announce to the user before running them; failures are common when Anki isn&#39;t open.
- Keep new tests deterministic and mark integration ones with `@pytest.mark.integration` once introduced, so they can be skipped via `-m "not integration"`.

---

## Runtime & CLI Conventions

1. Primary entry point: `uv run jisho-anki`. This executes `jisho_anki_tool.cli:jisho_anki`.
2. Alternate debugging entry: `uv run python -m jisho_anki_tool.cli`.
3. CLI loop behavior:
   - `n`: fetch next Kanji card via AnkiConnect.
   - Digits: select displayed words.
   - `c`: commit pending words back to Anki deck.
   - `q`: prompt to add pending items & exit.
   - Direct kanji input triggers search; pure kana input triggers Jamdict word lookup.
4. Console output uses Rich; keep new messaging consistent (table layouts, color styles, `console.status` spinners for network work).
5. Jamdict is initialized globally in `cli.py`. Avoid re-instantiating it per command to keep lookups fast.

---

## Code Style Guidelines

### Imports
1. Standard library first, third-party next, local modules last, separated by blank lines.
2. Use explicit relative paths (`from jisho_anki_tool...`) instead of implicit relative imports.
3. Keep imports typed (`from typing import List, Optional`) and minimize wildcard imports.
4. Sort alphabetically within each block when practical; match existing patterns.

### Typing & Data Models
1. All new functions should use type hints for parameters and return values.
2. Prefer concrete generics (`List[str]`) over bare containers.
3. Pydantic models (`JishoWord`, `KanjiCard`) already express schema constraints—extend them instead of ad-hoc dicts.
4. When returning tuples or complex structures, document them explicitly in docstrings.

### Formatting & Structure
1. Follow `black`-style spacing (double quotes, trailing commas in multi-line literals, 88 char guidance). Files already resemble this.
2. Use docstrings for public functions; short helper functions can use inline comments.
3. Keep functions focused: fetch/process/render responsibilities are already separated (`jisho.py`, `card_processor.py`, `render.py`). Maintain that separation.
4. Avoid inline lambdas for multi-step transforms; prefer small named helpers for clarity.

### Naming
1. Use descriptive snake_case for functions/variables.
2. Suffix booleans with `_flag`, `_enabled`, or start with `is_/has_/should_`.
3. Class names remain PascalCase (`KanjiCard`).
4. Keep CLI prompt helper functions prefixed with verbs (`get_user_input`, `handle_next_card`).

### Error Handling & Logging
1. Wrap external HTTP calls (`requests`) in `try/except requests.RequestException` and raise informative messages.
2. Prefer `console.status` + `render.error`/`success` helpers for CLI feedback rather than raw `print`.
3. When catching broad `Exception`, immediately log/echo the message and either re-raise or return a safe default to keep the CLI responsive.
4. For AnkiConnect interactions, bubble up meaningful messages (e.g., include `card_id`, `kanji` in errors) so users know what to fix.

### External Service Usage
1. `jisho.fetch_jisho_word_search` and `fetch_jisho_word_furigana` perform live HTTP requests; add caching/memoization only after confirming with the user because results reflect live dictionary data.
2. Respect Jisho rate limits: reuse `requests.Session` if you introduce bulk operations.
3. `Jamdict()` is heavy—do not instantiate it repeatedly.

### Rendering & UX
1. Tables: use `rich.Table` with no headers (matching `render.words_table`). Keep consistent column ordering and color palette.
2. Display counts and statuses via `render.info/success/error` helpers to avoid inconsistent formatting.
3. Escape user-provided strings (`rich.text.Text.from_markup` or `.plain`) when injecting into Rich markup.
4. Keep CLI prompts short; include context like pending word counts as already done in `get_user_input`.

### Testing Style
1. Use `pytest` fixtures for shared setup (`unordered_words` example). Keep fixtures functional (no side effects outside test scope).
2. Prefer explicit assertions over broad truthiness checks; list out expected sequences where order matters.
3. Network/Anki tests must call `pytest.skip` (or use marks) when prerequisites are absent. This prevents CI noise.
4. When mocking AnkiConnect or Jisho, isolate HTTP calls via helper functions so they&#39;re easy to patch.

### File & Module Boundaries
1. `card_processor.py` should remain pure logic (no IO). Keep new utilities there deterministic for testing ease.
2. `render.py` owns Rich-specific presentation logic; avoid bringing Rich into business logic modules.
3. `utils.py` is small; add generic helpers that have no external dependencies there. If a helper is domain-specific, place it in the relevant module instead.
4. Keep `cli.py` as the only infinite loop / orchestrator. New commands or modes should still leverage helper modules for heavy lifting.

---

## Contribution Workflow

1. Confirm `uv sync` succeeds before editing to ensure dependencies match lockfile.
2. For any dependency change, update both `pyproject.toml` and `uv.lock` (`uv add` or `uv remove` handles both) and mention the reason in your summary.
3. Run the most targeted pytest command that covers your change. Share the exact command + outcome with the user.
4. No automated formatter is enforced. Manually ensure spacing/margin consistency before returning work.
5. If you touch CLI flows, try them manually via `uv run jisho-anki` and describe the scenario you covered.
6. Document significant behavior changes in `README.md` until a dedicated docs section is built.

---

## Missing Cursor/Copilot Rules

- No `.cursor/rules/` or `.cursorrules` files exist.
- No `.github/copilot-instructions.md` file exists.
- If such configuration files are added later, incorporate their rules into this document and reference their location.

---

## Final Reminders

1. Keep responses concise but actionable when updating the user.
2. Never commit or push unless explicitly asked.
3. Treat Anki & Jisho APIs with care—wrap risky operations with confirmations when exposing new CLI commands.
4. If unsure about a destructive action (deck edits, deletions), ask the user before proceeding.
5. Update this `AGENTS.md` whenever new tooling, conventions, or rules appear so future agents inherit the context.
