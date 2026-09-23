# V3 LLM Recognition Backmatter — Implementation Plan

## Goal

Create a new `MyJapaneseVocabularyV3` Anki note type for vocabulary added through the normal interactive commit flow. Each V3 recognition card keeps the primary dictionary definition and adds validated LLM-generated nuance, a short Japanese example, and a word-level kanji-composition explanation. Existing legacy and V2 notes remain untouched.

This plan is intentionally staged so a fresh agent can own one stage at a time. Stages are sequential unless explicitly marked otherwise.

## Confirmed product contract

- Rollout: new V3 notes only; no migration or regeneration command.
- V3 schema: all 13 V2 fields followed by `Nuance`, `Example`, and `KanjiExplanation`.
- Recognition back order: primary dictionary definition, **Nuance**, **Example**, **Why these kanji**.
- Recall card: copy V2 behavior unchanged.
- Meaning selection: generated content is grounded in `word.definitions[0]`.
- Nuance: one English sentence explaining use beyond the short definition.
- Example: one short, natural, simple-adaptive Japanese sentence; no translation or separate reading.
- Example highlighting: the model returns plain sentence text and the exact surface form used. Application code validates the surface form, escapes both values, and stores rendered HTML with that occurrence bold and red.
- Kanji explanation: explain compound components, kanji plus okurigana, or a single kanji; state plainly when no kanji applies.
- Provider: DeepSeek Flash. The current official Responses API model identifier is `deepseek-flash`, corresponding to the agreed V4 Flash product choice.
- Generation: automatic during commit, without a preview/approval screen.
- Prompt: user edits content instructions; application code owns the fixed structured-output contract.
- Prompt path: `~/.config/kanji-vocab-miner/enrichment-prompt.md` by default, overrideable in TOML.
- Setup creates the default prompt only when it is absent.
- Secret: environment only via `KANJI_VOCAB_MINER_LLM__API_KEY`.
- Attempts: three total per word, with short exponential backoff and validation feedback on retries.
- Failure: skip the affected word, report an `enrichment` failure, and keep it pending for retry. A missing key causes a clear commit failure rather than creating fallback V2/V3 notes.
- Throughput: DeepSeek generation concurrency is configurable, defaulting to 5. Successful notes are written to Anki sequentially in reviewed order.
- CLI: use one Rich progress display for the commit and summarize failures afterward.
- Out of scope: caching, migration, regeneration, generated-content review/editing, concurrent Anki writes, and changes to legacy/V2 note types.

## Cross-stage guardrails

Every implementation agent must:

1. Read `AGENTS.md`, this plan, and the files named in its assigned stage before editing.
2. Preserve legacy and V2 constants, serializers, note types, and compatibility paths unless the stage explicitly says otherwise.
3. Add deterministic unit tests with all DeepSeek, Jisho, Kotobank, and Anki HTTP calls mocked.
4. Keep Rich imports in `cli.py`/`render.py`; domain and HTTP modules report data/events rather than rendering.
5. Use `requests` directly for DeepSeek; do not add an LLM SDK dependency.
6. Avoid running live Anki/internet integration tests. The default pytest configuration already excludes integration tests.
7. Finish the assigned stage only when its targeted tests and `uv run python -m compileall kanji_vocab_miner` pass.
8. Report exact commands, outcomes, changed files, and any deviation from this plan to the next agent.

## Target architecture

### New module: `kanji_vocab_miner/enrichment.py`

Own provider-neutral enrichment models, prompt loading/assembly, DeepSeek transport, retry behavior, response parsing/validation, example rendering, and bounded concurrent generation. It must not import Rich or AnkiConnect.

Suggested public surface:

```python
class VocabEnrichment(BaseModel):
    nuance: str
    example_sentence: str
    example_target: str
    kanji_explanation: str

class EnrichmentError(RuntimeError):
    ...

class DeepSeekEnrichmentClient:
    def generate(self, word: JishoWord) -> VocabEnrichment: ...

def render_example(enrichment: VocabEnrichment) -> str: ...

def generate_enrichments(
    items: List[PendingVocabItem],
    client: DeepSeekEnrichmentClient,
    max_workers: int,
    on_complete: Optional[Callable[[PendingVocabItem], None]] = None,
) -> List[EnrichmentOutcome]: ...
```

Names may change, but retain these boundaries:

- one validated domain model for the raw structured response;
- one client abstraction that is easy to fake in tests;
- one pure renderer for safe example HTML;
- one concurrency function that preserves input order in its returned outcomes.

### DeepSeek request contract

Use `POST https://api.deepseek.com/responses` with:

- `Authorization: Bearer <key>`;
- `Content-Type: application/json`;
- `model: "deepseek-flash"`;
- `instructions`: the fixed schema/format contract;
- `input`: the editable prompt plus word context;
- `text.format.type: "json_schema"` with a named schema generated from the Pydantic model;
- a finite request timeout.

The word context must include only the fields needed for grounding:

- expression;
- kana reading;
- primary English definition;
- primary part of speech when present.

Parse the Responses API output defensively rather than assuming one list index. Treat HTTP errors, malformed envelopes, missing output text, JSON decode errors, schema violations, blank strings, and invalid example targets as retryable enrichment failures. Never include the API key or full authorization header in errors.

Validation after Pydantic parsing:

- trim all four strings and reject blanks;
- require `example_target` to occur in `example_sentence`;
- locate and partition around the first exact target occurrence in the raw plain-text sentence, allowing repeated words without ambiguous global markup;
- independently HTML-escape the raw prefix, target, and suffix, then concatenate them around `<strong class="example-target">...</strong>`; never search or replace within already escaped text;
- convert newlines in plain-text fields to safe `<br>` only at note serialization/render time.

### Configuration contract

Add an `LLMConfig` nested model to `AppConfig` containing non-secret settings only:

```toml
[llm]
prompt_path = "~/.config/kanji-vocab-miner/enrichment-prompt.md"
concurrency = 5
```

- Expand `~` when resolving the path.
- Validate concurrency as a bounded positive integer; suggested range `1..10`.
- Read `KANJI_VOCAB_MINER_LLM__API_KEY` directly from the process environment through one helper. Do not define or accept `api_key` in TOML.
- Keep endpoint, model, timeout, and retry policy as code constants in the first version unless tests need constructor injection.
- Constructor injection should still allow tests to substitute endpoint, sleeper, and HTTP transport without sleeping or making network calls.

### Commit pipeline contract

Refactor `add_vocab_items()` into explicit phases while preserving `BatchAddResult` behavior:

1. Read existing expressions once and classify duplicates in reviewed order.
2. Check for the API key after duplicate classification. If it is absent, fail every remaining item at the `enrichment` stage before reading reviewed kanji, calling Kotobank/Jisho/DeepSeek, or writing to Anki.
3. Read reviewed kanji once when eligible items remain and a key is available.
4. For each remaining item, perform existing Kotobank lookup and furigana/cue preparation. Preserve `definition` and `furigana` failure stages.
5. Run only DeepSeek generation concurrently, up to the configured limit.
6. Convert failed generation outcomes to `AddFailure(stage="enrichment")`.
7. Serialize successful outcomes as V3 notes.
8. Add successful V3 notes to Anki sequentially in original reviewed order; preserve `anki` failures.
9. Carry the original input index through every phase and reconstruct `added`, `skipped_duplicates`, and especially `failed` in reviewed order before returning, so mixed-stage failures cannot reorder pending words.

Duplicate-detection Anki reads are allowed when the API key is missing; provider calls, reviewed-kanji reads, Kotobank/Jisho work, DeepSeek calls, and Anki writes are not. Return/report enrichment failures clearly for all nonduplicate items so none are silently lost and the pending list remains retryable.

## Stage 1 — Configuration and prompt provisioning

**Owner:** foundation agent  
**Depends on:** nothing  
**Primary files:** `kanji_vocab_miner/config.py`, `kanji_vocab_miner/setup.py`, `sample-config.toml`, new packaged default prompt, `tests/test_config.py`, `tests/test_setup.py`

### Work

1. Add `LLMConfig` with default prompt path and concurrency `5`, including positive/bounded validation.
2. Add helpers for:
   - resolving/expanding the configured prompt path;
   - reading the environment-only API key;
   - copying the packaged default prompt when the configured destination is absent.
3. Add a packaged default prompt based on `.pi/skills/japanese-word-breakdown/SKILL.md`, narrowed to the confirmed three outputs and primary sense. Keep schema key names out of this editable content where possible; fixed response instructions belong in Python.
4. Call prompt provisioning from `run_setup()`. Existing user content must never be overwritten.
5. Document `[llm]` non-secret settings in `sample-config.toml` and document the API-key environment variable in comments without showing a real key.
6. Ensure the packaged prompt is included in wheel/sdist output. Prefer `importlib.resources`; adjust Hatch configuration only if a build test proves it necessary.

### Tests first

- Defaults resolve to XDG prompt location and concurrency 5.
- TOML overrides prompt path and concurrency.
- `~` expansion is deterministic under a patched home directory.
- API key is read from the environment and cannot be sourced from TOML.
- Invalid concurrency is rejected.
- Prompt provisioning creates parent directories and the file when absent.
- Prompt provisioning leaves an existing edited file byte-for-byte unchanged.
- `run_setup()` invokes provisioning without changing the existing Anki failure semantics.

### Acceptance gate

```bash
uv run pytest tests/test_config.py tests/test_setup.py
uv run python -m compileall kanji_vocab_miner
uv build
```

Confirm the built wheel contains the default prompt resource.

### Handoff output

Report the final config attribute names and prompt-resource path; later stages must import those rather than duplicating path or environment logic.

## Stage 2 — Structured DeepSeek enrichment client

**Owner:** provider agent  
**Depends on:** Stage 1  
**Primary files:** new `kanji_vocab_miner/enrichment.py`, new `tests/test_enrichment.py`

### Work

1. Define the validated response model and an internal JSON Schema for the four raw response properties: `nuance`, `example_sentence`, `example_target`, `kanji_explanation`.
2. Implement prompt loading and request assembly. The user prompt governs content; fixed instructions enforce JSON shape, plain text, primary-sense grounding, simple-adaptive Japanese, and kanji edge-case behavior.
3. Implement the DeepSeek Responses API call with `requests`, explicit timeout, safe error messages, and dependency injection for HTTP transport.
4. Parse the response envelope and validate JSON with Pydantic.
5. Implement three total attempts with short exponential backoff. Inject the sleeper for tests. On validation retries, append a concise correction containing validation problems but not secrets.
6. Implement pure safe rendering of the example target as red/bold application-owned HTML.
7. Implement bounded concurrent generation using `ThreadPoolExecutor` (appropriate because `requests` is blocking I/O). Return outcomes in input order even when futures complete out of order. Keep retries inside each worker.
8. Expose completion callbacks/events without importing Rich.

### Tests first

- Exact request endpoint, auth header presence, model, structured schema, editable prompt, and word context.
- Only the primary definition and primary part of speech are sent for grounding.
- A valid response parses into the domain model.
- HTTP, envelope, JSON, schema, blank-value, and target-not-in-sentence errors retry and become one sanitized final error.
- Success on a later attempt stops further retries.
- Backoff uses injected sleep; tests do not actually wait.
- API keys never appear in exception strings.
- HTML-sensitive sentence/target text is escaped.
- Highlighting partitions raw text before escaping; an entity-collision case such as target `&` with an earlier literal `&amp;` highlights the actual target occurrence.
- Only the first exact target occurrence receives `<strong class="example-target">`.
- Concurrent calls never exceed the supplied worker limit.
- Out-of-order completion still returns outcomes in input order.
- One failed future does not cancel successful words.

### Acceptance gate

```bash
uv run pytest tests/test_enrichment.py
uv run python -m compileall kanji_vocab_miner
```

### Handoff output

Provide the exact client constructor, outcome type, and concurrency function signatures for the connector agent.

## Stage 3 — V3 note type, serializer, and templates

**Owner:** Anki-model agent  
**Depends on:** Stage 2 response/renderer contract  
**Primary files:** `kanji_vocab_miner/config.py`, `kanji_vocab_miner/setup.py`, `kanji_vocab_miner/anki/connect.py`, `tests/test_config.py`, `tests/test_setup.py`, `tests/test_anki_connect.py`

### Work

1. Add `VOCAB_NOTE_TYPE_V3 = "MyJapaneseVocabularyV3"`.
2. Define `VOCAB_V3_FIELDS` as all V2 fields in their existing order followed by:
   - `Nuance`;
   - `Example`;
   - `KanjiExplanation`.
3. Add `prepare_note_v3(...)` parallel to `prepare_note_v2(...)`. It receives already-fetched V2 data plus validated enrichment. It stores:
   - escaped/formatted nuance;
   - rendered example HTML from Stage 2;
   - escaped/formatted kanji explanation.
4. Add isolated V3 template/CSS helpers rather than modifying V2 helpers.
5. Recognition front remains the V2 recognition front. Recognition back shows `{{Back}}` first, then labeled conditional sections in the agreed order.
6. Copy the V2 recall template behavior exactly, changing no field references or conditional behavior.
7. Add subdued section-label/layout CSS and `.example-target { color: red; font-weight: bold; }` under V3 styling only.
8. Change production setup/prerequisite behavior to create/update/require V3. Leave installed V2 and legacy models untouched.
9. V3 update must validate the exact ordered field list before changing only V3 templates/styling, matching V2’s safety pattern.

### Tests first

- V3 constants and exact 16-field order.
- V2 constants and field order remain unchanged.
- Exact V3 serialized payload, including three generated fields and `modelName` V3.
- Plain-text nuance/explanation are escaped and newlines are rendered safely.
- Recognition template field order and labels.
- Recognition sections use Anki conditional blocks.
- Example target CSS is red and bold.
- V3 recall template equals V2 recall behavior.
- Setup creates V3 on fresh/current-V2 installations without mutating V2.
- Setup updates only an existing compatible V3.
- Incompatible V3 fields fail before any template/style mutation.
- Prerequisites require V3, not V2 or legacy.

### Acceptance gate

```bash
uv run pytest tests/test_config.py tests/test_setup.py tests/test_anki_connect.py -k "v2 or v3 or prepare_note"
uv run python -m compileall kanji_vocab_miner
```

### Handoff output

Give the pipeline agent the exact `prepare_note_v3()` signature and confirm which values are already escaped/rendered.

## Stage 4 — Commit concurrency, failure retention, and progress UI

**Owner:** orchestration agent  
**Depends on:** Stages 1–3  
**Primary files:** `kanji_vocab_miner/vocab_models.py`, `kanji_vocab_miner/anki/connect.py`, `kanji_vocab_miner/cli.py`, optionally `kanji_vocab_miner/render.py`, `tests/test_vocab_models.py`, `tests/test_anki_connect.py`, `tests/test_cli.py`

### Work

1. Extend `AddFailure.stage` with `"enrichment"`.
2. Introduce a small typed progress event/callback contract in domain code. Include enough information for the CLI to update description and terminal item count, but no Rich objects.
3. Refactor `add_vocab_items()` into the phase contract above.
4. Construct/inject the enrichment client from config. Preserve the existing optional Kotobank-client injection and add an enrichment-client injection for deterministic tests.
5. Run DeepSeek generation concurrently with `config.llm.concurrency`; keep definition/furigana preparation and Anki writes controlled and deterministic.
6. Carry the stable original input index through preparation, enrichment, serialization, and writing; never use future completion order as result order.
7. Serialize and write V3 notes sequentially in original reviewed order.
8. Before the missing-key check, perform only the Anki reads required to classify duplicates. Handle a missing key as a clear enrichment-stage failure for every remaining item; make no provider calls, reviewed-kanji read, or Anki write.
9. Reconstruct every `BatchAddResult` list in original reviewed order before returning. This must keep CLI pending items ordered even when failures arise in different phases.
10. Replace the commit spinner in `add_pending_words_to_anki()` with one Rich `Progress` display. Advance the bar when each word reaches a terminal outcome (added, duplicate, or failed). During generation, update its description/status without creating per-word bars.
11. Preserve the existing final counts and per-failure messages. Enrichment failures remain pending with recall selection and `last_error` intact.

### Tests first

- Duplicates never trigger Kotobank, furigana, or DeepSeek calls.
- Existing definition/furigana failures never trigger DeepSeek for that word.
- Eligible items are submitted to enrichment with configured concurrency.
- Out-of-order generation results still produce sequential Anki `addNote` calls in reviewed order.
- `addNote` payloads use V3.
- One enrichment failure does not prevent later successes.
- Enrichment failures carry stage `enrichment`, remain pending, and appear in CLI messages.
- Missing API key permits duplicate-detection Anki reads, makes no provider calls or Anki writes, and preserves all eligible nonduplicate items as failures.
- Existing `definition`, `furigana`, and `anki` failure classifications remain intact.
- Mixed-stage failures are returned in reviewed order, and the CLI retains pending items in that same order.
- Callback terminal counts cover every input exactly once, including duplicates and failures.
- CLI renders one progress instance and still prints accurate totals.
- Recall choices survive enrichment failures.

### Acceptance gate

```bash
uv run pytest tests/test_enrichment.py tests/test_vocab_models.py tests/test_anki_connect.py tests/test_cli.py
uv run python -m compileall kanji_vocab_miner
```

### Handoff output

Document the final commit phase ordering, progress-event shape, and how missing-key failures are represented.

## Stage 5 — Documentation, end-to-end unit gate, and package verification

**Owner:** integration agent  
**Depends on:** Stages 1–4  
**Primary files:** `README.md`, `sample-config.toml`, tests as needed

### Work

1. Update README vocabulary-card documentation from V2-new-note behavior to V3:
   - V3 setup and no migration;
   - recognition section contents;
   - automatic DeepSeek generation and primary-sense grounding;
   - key environment variable;
   - prompt location/customization contract;
   - concurrency setting and default;
   - retry/skip/pending behavior;
   - setup command needed to install V3.
2. Retain a concise compatibility note: legacy/V2 notes remain in the deck and continue to participate in duplicate detection and furigana sync where compatible.
3. Verify example config matches actual attribute names and defaults.
4. Verify no documentation suggests placing the API key in TOML.
5. Run the complete non-integration suite and build artifacts.
6. Inspect the wheel to confirm the prompt resource ships.
7. If Anki is available and the user explicitly approves a live check, manually verify setup and one note. Otherwise report that live Anki/DeepSeek verification was not run.

### Acceptance gate

```bash
uv run pytest
uv run python -m compileall kanji_vocab_miner
uv build
```

Expected: all non-integration tests pass; wheel and sdist build; default prompt is present in the wheel.

## Final acceptance checklist

- `kanji-vocab-miner setup` installs or safely refreshes V3 and never alters existing V2/legacy notes.
- Setup creates the editable prompt only if absent.
- The interactive CLI remains usable without a key until commit.
- A commit without a key fails clearly and leaves eligible words pending.
- A normal commit makes at most the configured number of simultaneous DeepSeek calls.
- Every provider response is schema-validated and receives at most three total attempts.
- Generated HTML is application-owned and escaped; arbitrary model HTML cannot enter the note.
- Recognition cards show the primary definition plus the three labeled sections in order.
- The exact used form in the Japanese example is bold and red.
- Recall cards behave exactly as V2 recall cards.
- Partial failures do not discard successful or retryable items.
- V3 additions preserve reviewed order even when generation completes out of order.
- Legacy/V2 duplicate detection and furigana synchronization continue to work.
- Unit tests make no real DeepSeek, Jisho, Kotobank, or Anki calls.
- README and sample config match runtime behavior.

## Recommended agent handoff sequence

1. Foundation agent — Stage 1.
2. Provider agent — Stage 2.
3. Anki-model agent — Stage 3.
4. Orchestration agent — Stage 4.
5. Integration/review agent — Stage 5.
6. Fresh read-only reviewer — compare the final diff to this plan, with special focus on secrets, HTML escaping, ordering, partial failures, and V2 compatibility.

One writer should work in the main checkout at a time. Each writer hands off only after its stage gate passes; the next writer starts from the resulting working tree and reads the prior handoff report.