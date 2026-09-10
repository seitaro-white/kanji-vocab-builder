# Vocab Card V2 — Staged Implementation Plan

## Purpose

Implement a second vocabulary note type that preserves the existing Japanese-to-English recognition card and optionally generates a Japanese-cue-to-Japanese-word recall card.

This is a **handoff plan**, not implementation. Work must proceed through the three gated stages below:

1. prove the Kotobank lookup and extraction path is reliable enough;
2. create and manually validate the Anki V2 note type and templates;
3. integrate the production commit pipeline and dual-toggle TUI.

**Stop at every user gate. Do not begin the next stage until the user has tested the current stage and explicitly approved continuing.**

## Starting state

- Product concept: `new-feature-concept.md`
- Current package: `kanji_vocab_miner/`
- Existing note type: `MyJapaneseVocabulary`
- Existing deck: `KanjiVocabMiner-Vocabulary`
- Existing note fields: `Front`, `Back`, `Expression`, `Kana Reading`, `Grammar`, `Definition`, `Additional Definitions`, `JLPT`
- Existing note type always creates:
  - Card 1: Japanese word → primary English definition
  - Card 2: primary English definition → Japanese word
- Existing `sync_vocab_furigana()` updates only `Front` and runs when the interactive CLI exits.
- The worktree contains an untracked PRD at the time this plan was written. Preserve user files and inspect `git status` before editing.

## Confirmed product decisions

These are settled requirements, not implementation choices to reopen silently.

### Scope and compatibility

- Create a separate note type named `MyJapaneseVocabularyV2` in the existing vocabulary deck.
- Never mutate the legacy note type, its templates, or existing notes.
- Preserve all eight legacy field names in V2 and add exactly:
  - `JapaneseDefinition`
  - `JapaneseCue`
  - `Recall`
  - `DefinitionSource`
  - `DefinitionURL`
- Legacy migration/backfill is out of scope for this release.
- Keep the schema compatible with a future migration command.
- Treat `Expression` as the unique vocabulary identity across legacy and V2 notes.

### Japanese definitions

- Fetch a Japanese definition for **every** committed V2 note, including recognition-only notes. This allows Recall to be enabled later by editing the note in Anki.
- Perform lookups synchronously during final commit. Do not add background or async processing.
- Do not cache Kotobank results in memory or on disk.
- Use a bounded timeout and retry one transient request/server failure.
- Query the direct word URL and trust the returned page; do not validate its headword or reading against the selected Jisho word.
- Prefer `デジタル大辞泉`.
- Fall back only to `精選版 日本国語大辞典`.
- Extract up to two top-level senses from one selected dictionary. Do not combine senses from different dictionaries.
- If the preferred dictionary has one unnumbered definition, store that as one sense.
- Do not detect or redact occurrences of the answer in the cue.
- Store normalized raw definition text, rendered cue HTML, dictionary name, and the page's canonical URL.

### Furigana

- Add Fugashi plus a bundled UniDic package for contextual token readings.
- Align readings to individual kanji where the alignment is unambiguous.
- Fall back to whole-token ruby for irregular or ambiguous readings.
- Apply the existing review-dependent convention: `<rt class="known">` hides a reading on the question when the represented kanji are reviewed.
- Kana, punctuation, whitespace, Latin text, and unsupported non-kanji characters pass through safely.
- Preserve raw Japanese definition text independently of rendered ruby HTML.

### Cards

- Recognition must behave exactly like the current Card 1:
  - question: `Front` with review-dependent furigana;
  - answer: the same word with all furigana visible, then `Back`.
- Recall is optional and controlled by the `Recall` field:
  - blank: no recall card should be generated;
  - non-empty (the CLI writes `1`): generate the recall card.
- Recall question: `JapaneseCue` with review-dependent furigana.
- Recall answer: repeat the cue with all furigana visible, reveal the target word and reading, and show a small linked `DefinitionSource` using `DefinitionURL`.
- Keep English definitions off the recall card unless a later product decision changes this.
- Anki automatically creates a conditional card when `Recall` changes from blank to non-empty.
- Anki intentionally preserves a card that becomes empty when `Recall` is cleared. Document that users must run **Tools → Empty Cards** to remove it.

### Commit-review UX

- Use one custom review screen with separate Add and Recall columns.
- New pending words default to Add on and Recall off.
- `Space`: toggle Add for the focused row.
- `r`: toggle Recall for the focused row.
- Enabling Recall also enables Add.
- Disabling Add keeps the row's Recall preference in memory but makes it inactive for that commit.
- Existing `a`/`n` controls enable/disable Add for all rows only.
- Do not add bulk Recall controls in this release.
- `Enter`: confirm; `Esc`/`q`: abort.
- Aborting preserves pending rows and their Recall choices.
- Confirmed rows with Add off are discarded from pending state.
- Successful additions leave pending state.
- Lookup, preparation, or Anki-add failures remain pending with their Recall choice and a visible reason.
- Commit successful rows even when other rows fail.

## Legal and maintenance constraint

Kotobank has no public API identified during planning. Its terms restrict use to personal purposes and contain restrictions concerning copying/storage beyond permitted use. `robots.txt` allows word pages but is not a content license. The user chose a live Kotobank integration for personal use and accepts this risk.

Before Stage 1 implementation, re-read the current terms at `https://kotobank.jp/rule/`. If access conditions have materially changed, stop and report the change rather than working around it.

---

# Stage 1 — Kotobank feasibility spike

## Goal

Prove that direct page lookup, dictionary selection, sense extraction, retry behavior, and error classification work reliably enough on representative vocabulary **before** changing Anki models or CLI behavior.

## Stage boundary

Stage 1 may add a standalone Kotobank client, its tests, and a manual probe script. It must not change Anki setup/templates, note creation, pending-word state, or the interactive commit UI.

## Proposed files

- Add `kanji_vocab_miner/kotobank.py`
- Add `tests/test_kotobank.py`
- Add `scripts/probe_kotobank.py`
- Update `pyproject.toml`/`uv.lock` only if the spike genuinely needs a new dependency. BeautifulSoup and Requests already exist, so no dependency change should be necessary in this stage.

## Data contract

Define a typed result owned by the Kotobank module, for example:

```python
class JapaneseDefinition(BaseModel):
    expression: str
    senses: List[str]          # one or two normalized senses
    source_name: str           # exact supported dictionary label
    source_url: str            # canonical Kotobank URL
```

Define module-specific exceptions that preserve actionable context:

- `KotobankRequestError`: timeout, connection, retry-exhausted, or HTTP failure;
- `KotobankDefinitionNotFound`: page loaded but neither supported dictionary produced a usable definition;
- `KotobankParseError`: supported dictionary article exists but its structure cannot be interpreted safely.

Each exception must include the expression and URL without dumping whole page content.

## HTTP behavior

- Build `https://kotobank.jp/word/{percent-encoded expression}`.
- Use a `requests.Session` for connection pooling only; this is not result caching.
- Set an identifiable User-Agent and a bounded connect/read timeout.
- Retry once for transient connection failures, timeouts, HTTP 429, and HTTP 5xx responses.
- Do not retry ordinary 4xx responses except 429.
- Honor `Retry-After` when practical, while keeping the retry bounded.
- Call `raise_for_status()`.
- Use the page's `<link rel="canonical">` when available; otherwise retain the requested URL.

## Parser behavior

Keep fetching and parsing separate so parser tests are pure.

1. Parse the `article.dictype.daijisen` article first.
2. If absent or unusable, parse `article.dictype.nikkokuseisen`.
3. Restrict extraction to that article's `section.description`.
4. Remove scripts, styles, ad placeholders, source blocks, examples explicitly marked as examples, and nested historical/example lists.
5. When the description has direct top-level ordered-list items, treat the first two direct items as senses.
6. Do not flatten nested list items into extra senses.
7. When no direct list exists, normalize the section's visible text as one sense.
8. Normalize repeated whitespace while retaining Japanese punctuation.
9. Reject empty results.
10. Do not inspect later encyclopedia articles.

Use hand-authored, minimal HTML fixtures in unit tests rather than storing entire downloaded Kotobank pages.

## Probe script

`scripts/probe_kotobank.py` should exercise production fetch and parse code without writing results to Anki or a persistent cache.

Suggested interface:

```bash
uv run python scripts/probe_kotobank.py 学校 走る すごい
uv run python scripts/probe_kotobank.py --file /path/to/words.txt --delay 0.5
```

Output one bounded row per expression:

- expression;
- outcome category;
- chosen source;
- number of senses;
- canonical URL;
- elapsed time;
- a terminal-only preview of the extracted senses or concise error.

End with counts and latency summary. Avoid writing downloaded HTML or definition caches. Add a polite configurable delay between words in a probe batch.

## Stage 1 test matrix

Unit tests must cover:

- Daijisen with one unnumbered definition;
- Daijisen with two or more top-level numbered senses;
- nested examples do not become senses;
- Seisenban fallback;
- Daijisen wins when both sources exist;
- unsupported encyclopedia-only page returns not-found;
- canonical URL extraction and fallback;
- whitespace/inline-link normalization;
- empty/malformed supported article;
- request timeout followed by successful retry;
- exhausted retry;
- non-retryable HTTP error;
- URL encoding for kanji and kana.

Run:

```bash
uv run pytest tests/test_kotobank.py
uv run python -m compileall kanji_vocab_miner
```

Then run a manual representative probe. Include common kanji words, kana-only words, okurigana, a page with Daijisen, a page requiring Seisenban fallback, and a known unsupported/missing page. Keep the request volume modest.

## Stage 1 completion report

Report:

- exact commands and pass/fail counts;
- sample size and outcome categories;
- extraction failures grouped by cause;
- observed latency range;
- any unexpected page structures;
- several manually inspectable cue previews;
- current terms/access observations.

## User Gate 1 — provider approval

**Stop.** Ask the user whether the extracted definitions and observed reliability are good enough to proceed.

If rejected, revise only the provider spike or choose a different source. Do not create the Anki V2 model.

---

# Stage 2 — V2 model, furigana renderer, and manual Anki prototype

## Goal

Create the isolated V2 note type and validate its recognition/recall behavior manually in Anki before any production TUI integration.

## Stage boundary

Stage 2 may add V2 constants, setup/model functions, cue furigana rendering, focused tests, and a manual sample-note helper. It must not replace the current commit-review UI or route normal vocabulary additions to V2.

## Dependency step

Add the tokenizer and bundled dictionary through uv so project metadata and the lockfile remain synchronized:

```bash
uv add fugashi unidic-lite
```

Before committing to the exact packages, verify Python 3.12 wheel/runtime support in this environment and inspect the installed UniDic feature names. If installation or initialization is unreliable, stop and report alternatives instead of implementing a tokenizer.

## Proposed files

- Add `kanji_vocab_miner/furigana.py`
- Update `kanji_vocab_miner/config.py`
- Update `kanji_vocab_miner/setup.py`
- Update `kanji_vocab_miner/anki/connect.py` only for V2 setup/sample-note seams that do not alter normal production additions
- Add `tests/test_furigana.py`
- Add or update setup/template tests
- Add a clearly manual helper such as `scripts/preview_vocab_v2.py`
- Update `pyproject.toml` and `uv.lock`

## Constants and field ownership

Preserve legacy constants for legacy behavior. Add explicit V2 constants instead of silently repointing `VOCAB_NOTE_TYPE` during this stage:

```python
LEGACY_VOCAB_NOTE_TYPE = "MyJapaneseVocabulary"
VOCAB_NOTE_TYPE_V2 = "MyJapaneseVocabularyV2"

LEGACY_FIELDS = {...existing eight...}
VOCAB_V2_FIELDS = {
    **LEGACY_FIELDS,
    "japanese_definition": "JapaneseDefinition",
    "japanese_cue": "JapaneseCue",
    "recall": "Recall",
    "definition_source": "DefinitionSource",
    "definition_url": "DefinitionURL",
}
```

If retaining `VOCAB_NOTE_TYPE`/`FIELDS` as compatibility aliases reduces churn, keep them pointing to legacy values until Stage 3 deliberately migrates call sites.

## Furigana renderer

Design the cue renderer as pure transformations around one lazy/shared tokenizer instance.

Suggested public seam:

```python
def render_japanese_cue(
    senses: List[str], reviewed_kanji: Set[str]
) -> str:
    """Return escaped ruby HTML with one visual block per sense."""
```

Required behavior:

- escape source text before emitting owned ruby markup;
- preserve sense boundaries with controlled HTML such as `<div class="sense">`;
- pass kana, punctuation, spaces, numerals, and Latin text through;
- normalize tokenizer readings to hiragana for display;
- for a token with no kanji, return its surface form;
- for unambiguous single-kanji/okurigana alignment, place ruby only over the kanji portion;
- for ambiguous compounds and irregular readings, wrap the whole token in one ruby element;
- set `class="known"` only when all kanji represented by that ruby element are reviewed;
- never mutate `JapaneseDefinition` while resyncing visibility classes.

Generalize `_update_furigana_classes()` so it can update both single-kanji and grouped ruby elements. For grouped ruby, hide the reading only when every kanji in the ruby base is reviewed.

## V2 templates

Use descriptive template names:

- `Recognition`
- `Recall`

Recognition should copy the current Card 1 front/back and CSS behavior exactly.

The entire Recall front must be conditional so a blank field produces a blank front and therefore no card:

```html
{{#Recall}}
<div class="japanese-cue">{{JapaneseCue}}</div>
{{/Recall}}
```

Recall answer should:

- repeat the cue inside `.show-all-furigana`;
- show `Front` inside `.show-all-furigana`;
- show `Kana Reading`;
- render a small source link using `DefinitionURL` and `DefinitionSource`;
- avoid English definitions.

Extend CSS only in V2. Do not update legacy styling.

## V2 setup lifecycle

Add V2-specific create/update functions. `setup` should:

- continue creating the existing vocabulary deck idempotently;
- create `MyJapaneseVocabularyV2` when absent;
- update only V2 templates and V2 CSS when present;
- validate V2 field names before updating templates;
- provide an actionable error if the existing V2 model has an incompatible schema;
- never call template, style, or field mutation actions for `MyJapaneseVocabulary`.

Do not make normal CLI startup require V2 until Stage 3 switches additions to it.

## Manual sample-note helper

Provide a bounded helper that adds two clearly tagged sample notes:

1. recognition-only: `Recall` blank;
2. recognition + recall: `Recall` set to `1`.

Use fixed sample content so template testing does not depend on live Kotobank. Put samples in a clearly named temporary test deck or use a unique test tag and print exact cleanup instructions. Do not delete user data automatically.

The helper should print note/card IDs and explain how to:

- inspect both templates;
- edit the recognition-only note's `Recall` field to `1` and verify Anki creates Recall;
- clear `Recall`, run Tools → Empty Cards, and verify removal;
- inspect source-link behavior;
- inspect hidden/revealed furigana;
- delete the sample notes/deck manually.

## Stage 2 tests

Pure tests:

- V2 has all 13 fields in the intended order;
- recognition template matches legacy behavior;
- recall front is fully conditional;
- recall answer contains cue, target, reading, and source but no English definition;
- legacy template functions remain unchanged;
- kana/punctuation/Latin pass-through;
- single-kanji alignment;
- okurigana alignment;
- ambiguous multi-kanji whole-token fallback;
- irregular reading fallback;
- reviewed/unreviewed grouped ruby classes;
- HTML escaping;
- multiple-sense formatting;
- grouped and single ruby class resync.

Optional integration tests, marked `integration`:

- create a uniquely named temporary model/deck;
- add blank-Recall and enabled-Recall notes;
- assert generated card counts/templates through AnkiConnect;
- clean up notes/deck where safe and leave note-type cleanup instructions if AnkiConnect cannot remove it safely.

Run:

```bash
uv run pytest tests/test_furigana.py tests/test_config.py tests/test_anki_integration.py -m "not integration"
uv run python -m compileall kanji_vocab_miner
```

Announce before any live Anki test, as required by `AGENTS.md`.

## User Gate 2 — template approval

**Stop.** Ask the user to run the manual sample-note scenario in Anki and approve:

- recognition visual behavior;
- recall question wording/layout;
- recall answer layout and source link;
- furigana visibility;
- manual Recall enable/disable workflow.

Revise V2 templates/CSS/field presentation until approved. Do not build the production TUI flow before approval.

---

# Stage 3 — production commit pipeline and dual-toggle TUI

## Goal

Route normal approved vocabulary additions through V2 using the validated Kotobank client and approved templates.

## Proposed files

- Add `kanji_vocab_miner/vocab_models.py` or another focused domain-model module
- Update `kanji_vocab_miner/review.py`
- Update `kanji_vocab_miner/cli.py`
- Update `kanji_vocab_miner/anki/connect.py`
- Update `kanji_vocab_miner/setup.py` startup validation
- Update `tests/test_review.py`
- Update `tests/test_cli.py`
- Update `tests/test_anki_connect.py`
- Update `tests/test_config.py`
- Update `README.md`

Keep responsibilities separated:

- `kotobank.py`: fetch and parse Japanese definitions;
- `furigana.py`: render raw Japanese text and update ruby visibility;
- domain model module: pending selection and batch outcome types;
- `review.py`: terminal interaction only;
- `anki/connect.py`: Anki payloads and AnkiConnect operations;
- `cli.py`: orchestration and Rich messaging.

## Domain models

Do not add workflow state to `JishoWord`. Introduce a wrapper, for example:

```python
@dataclass
class PendingVocabItem:
    word: JishoWord
    add_enabled: bool = True
    recall_enabled: bool = False
    last_error: Optional[str] = None
```

Introduce structured outcomes so the connector cannot silently skip failures while the CLI reports total success:

```python
@dataclass
class AddFailure:
    item: PendingVocabItem
    stage: Literal["duplicate", "definition", "furigana", "anki"]
    message: str

@dataclass
class BatchAddResult:
    added: List[PendingVocabItem]
    failed: List[AddFailure]
    skipped_duplicates: List[PendingVocabItem]
```

The exact types may vary, but the outcome must distinguish successes, transient failures retained for retry, and already-existing expressions.

## Existing-note reads and duplicate policy

Replace card-based duplicate collection with a note-level helper such as `get_vocab_expressions()`:

1. query all notes in `KanjiVocabMiner-Vocabulary`;
2. fetch note info;
3. accept any legacy or V2 note with a nonblank `Expression` field;
4. return a deduplicated set.

Keep `get_reviewed_vocab()` as a compatibility wrapper if existing callers/tests need it, but clarify its misleading name in a later cleanup.

Recheck expressions immediately before commit so a stale search result cannot create a cross-model duplicate. Treat an already-existing expression as skipped/already satisfied, not a retryable network failure; remove it from pending and report it separately.

## Custom review application

The current InquirerPy checkbox cannot naturally represent two independent booleans. Build the new prompt on Prompt Toolkit (already an indirect/direct project dependency), or prove an InquirerPy extension is maintainable before choosing it.

Separate a pure state reducer from terminal rendering. State tests should not require a live TTY.

Display at least:

```text
Add  Recall  Word (reading) — primary English definition
 ✓           学校 (がっこう) — school
 ✓     R     覚える (おぼえる) — to remember
```

Behavior:

- Up/Down: move focus; scrolling works for lists taller than the terminal.
- Space: toggle Add.
- `r`: toggle Recall; enabling it also enables Add.
- `a`: enable Add for every row.
- `n`: disable Add for every row without erasing Recall preferences.
- Enter: return confirmed state.
- Esc/`q`: return aborted state, including changed Recall preferences.
- Add-off rows are visibly dim and their Recall marker is inactive but remembered.

Replace `Optional[List[JishoWord]]` with an explicit result carrying submit/abort status and item state. This avoids relying on mutation side effects.

## Pending-state integration

- Wrap a newly selected `JishoWord` in `PendingVocabItem`.
- Deduplicate pending additions by `word.expression`.
- Preserve existing behavior for direct word lookup, numeric selection, commit, and quit.
- On abort, keep every pending item and the current recall choices.
- On confirm:
  - remove Add-off rows;
  - process Add-on rows;
  - remove added and already-existing rows;
  - keep failed rows with their prior recall choice and `last_error`.
- On quit with failures, do not silently exit. Show the remaining failures and ask through the existing quit flow whether to retry, disable/discard, or return to the loop; keep this handling concise and non-destructive.

If this last quit interaction cannot fit the existing control flow cleanly, stop and ask the user rather than discarding failed pending items.

## Commit service

Process included rows sequentially. For each item:

1. fetch a fresh Japanese definition through `kotobank.py` regardless of Recall state;
2. render `JapaneseCue` using a freshly obtained reviewed-kanji set for the commit;
3. render the vocabulary `Front` with the existing behavior;
4. prepare a V2 note payload;
5. set `Recall` to `1` or blank;
6. add the note through AnkiConnect;
7. classify and return the result.

`prepare_note_v2()` should be deterministic after receiving already-fetched definition and rendered strings. Keep network calls outside payload serialization so they are independently testable.

Populate fields:

- legacy eight fields exactly as today;
- `JapaneseDefinition`: normalized senses joined with a stable plain-text separator such as newline;
- `JapaneseCue`: rendered ruby HTML preserving sense boundaries;
- `Recall`: `1` when enabled, otherwise empty;
- `DefinitionSource`: selected Kotobank dictionary label;
- `DefinitionURL`: canonical URL.

Use Rich status/progress in `cli.py`. Business and connector modules should return outcomes instead of printing success claims. Final messaging must report actual added, duplicate, and failed counts.

## Furigana sync across note types

Refactor `sync_vocab_furigana()` to operate once per note rather than once per card:

- query notes in the vocabulary deck;
- feature-detect fields so malformed/older notes are safe;
- update `Front` when present;
- update `JapaneseCue` when present;
- update both fields in one `updateNote` call when both changed;
- leave `JapaneseDefinition` untouched;
- support single-character and grouped ruby;
- return an accurate number of notes updated.

Preserving `Front` in V2 keeps legacy and V2 sync compatible.

## Setup/startup switch

After the production V2 path is ready:

- make prerequisite validation require `MyJapaneseVocabularyV2` for additions;
- report a clear `kanji-vocab-miner setup` remediation when it is absent;
- treat `MyJapaneseVocabulary` as optional;
- ensure `setup` still never mutates the legacy model;
- route new additions exclusively to V2.

## Stage 3 test matrix

### Review state and UI adapter

- defaults: Add on, Recall off;
- Space toggles only Add;
- `r` enables Recall and Add;
- disabling Add remembers Recall;
- `a`/`n` affect Add only;
- abort preserves edited state;
- confirm partitions Add-on/Add-off rows;
- scrolling/focus remains bounded;
- empty list short-circuits.

### Commit orchestration

- definitions fetched for recognition-only and recall rows;
- processing is synchronous and ordered;
- Recall marker serialized correctly;
- mixed success/failure commits successes and retains failures;
- lookup failure is labeled and retained;
- furigana failure is labeled and retained;
- Anki failure is labeled and retained;
- cross-model duplicate is skipped without lookup/add;
- CLI count/message reflects actual outcomes;
- commit and quit preserve their existing continue/exit semantics when no failures remain.

### V2 payload and compatibility

- exact 13-field payload;
- V2 model name and existing deck;
- recognition-only payload still contains Japanese definition/cue/source fields;
- both note types contribute expressions to duplicate detection;
- duplicate expressions are deduplicated;
- notes missing `Expression` remain safely ignored;
- note counting/progress remains model-agnostic;
- furigana sync updates the correct fields once per note.

### Regression suite

Run targeted tests first, then the default non-integration suite:

```bash
uv run pytest tests/test_kotobank.py tests/test_furigana.py
uv run pytest tests/test_review.py tests/test_cli.py tests/test_anki_connect.py tests/test_config.py
uv run pytest
uv run python -m compileall kanji_vocab_miner
```

Announce before manually running live Anki/Jisho/Kotobank checks. The default pytest configuration excludes tests marked `integration`.

## Documentation

Update `README.md` with:

- V2 setup requirement;
- recognition versus recall behavior;
- commit-screen keys and defaults;
- synchronous Kotobank lookup and partial-failure behavior;
- source priority and provenance fields;
- no-cache behavior;
- how to enable Recall by editing `Recall` in Anki;
- how to disable Recall and run Tools → Empty Cards;
- how cue furigana visibility follows reviewed kanji;
- coexistence with legacy notes;
- migration explicitly deferred.

Also correct any stale command/package names encountered in touched documentation, but keep unrelated cleanup out of the feature diff.

## User Gate 3 — end-to-end acceptance

Run the interactive CLI manually with a small batch containing:

- one recognition-only word;
- one recall-enabled word;
- one intentionally failed/unsupported lookup if practical;
- one expression already present in legacy or V2.

Verify:

- dual toggles and defaults;
- synchronous progress is understandable;
- successful rows add despite another failure;
- failed rows remain pending;
- duplicate behavior;
- both card types in Anki;
- recognition remains unchanged;
- recall source link and furigana;
- exit-time furigana sync across legacy and V2.

Report exact commands, screenshots or observations, created note/card IDs where useful, and cleanup performed. Final acceptance belongs to the user.

---

# Out of scope

- Migrating or backfilling legacy notes
- Generating cues with an LLM
- Editing Japanese cues in the commit TUI
- Selecting among Kotobank definitions in the TUI
- Background/async lookup
- Persistent or in-memory definition caching
- Bulk Recall toggles
- Automatic answer-leak detection/redaction
- Supporting Kotobank sources other than デジタル大辞泉 and 精選版 日本国語大辞典
- Automatically deleting empty recall cards
- Changing the current definition of reviewed kanji

# Main risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Kotobank HTML changes or throttles requests | Stage 1 first; narrow selectors; typed errors; timeout/retry; manual gate |
| Terms/licensing are incompatible with use | Recheck current terms before Stage 1; stop on material change; personal-use constraint |
| Dictionary definitions are poor recall cues | Manual Stage 1 review; store raw/source data; future LLM replacement remains possible |
| Full-sentence furigana cannot align every compound | Contextual tokenizer; unambiguous alignment only; explicit whole-token fallback |
| New template creates unwanted cards | Separate V2 model; conditional entire recall front; manual Anki gate |
| Clearing Recall leaves an empty card | Document Anki Tools → Empty Cards behavior |
| Legacy and V2 duplicates bypass model-level checks | Deck-wide note-level `Expression` preflight immediately before commit |
| Partial add failures are reported as full success | Structured batch outcomes; CLI reports actual counts and retains failures |
| Custom TUI becomes tightly coupled to Prompt Toolkit | Pure state reducer plus thin terminal adapter and deterministic tests |

# Handoff checklist

A new implementation session should:

1. Read `AGENTS.md`, `new-feature-concept.md`, and this plan completely.
2. Run `git status --short` and preserve user-owned/untracked files.
3. Start only Stage 1.
4. Mark external-service tests clearly and keep deterministic parser tests offline.
5. Run the Stage 1 checks and present the reliability report.
6. Stop at User Gate 1.
7. Continue to Stage 2 only after explicit approval, then stop at User Gate 2.
8. Continue to Stage 3 only after the user manually approves the Anki templates.
9. Never commit, push, delete notes, or mutate the legacy model without explicit user authorization.
