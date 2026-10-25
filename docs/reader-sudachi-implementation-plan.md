# Sudachi reader implementation plan

## Status and scope

**Implemented and validated offline. Real Anki verification and browser visual review remain pending.**

The steps below record the agreed implementation scope. The native preview is available
at [reader-sudachi-preview.html](reader-sudachi-preview.html); run the interactive offline
reader with `uv run python -m kanji_vocab_miner.web --demo`.

Use Sudachi's standard analysis instead of developing our own word-boundary system.
The user's Hunk review clarified that native Sudachi behavior is acceptable, even where
it differs from the manually annotated examples. Name styling is optional: implement
it only where existing parser tags make it straightforward; otherwise defer it.

This supersedes the previous requirements to reproduce every manually chosen compound,
inflection and suffix boundary exactly. The approved examples remain a record of desired
reading behavior and useful review material, not a mandate to build a custom parser.

References:

- [Visual examples](reader-annotation-draft.html)
- [Annotation notes](reader-annotation-draft.md)
- [Initial research](reader-parsing-research.md)
- [Sudachi Python documentation](https://github.com/WorksApplications/sudachi.rs/tree/develop/python)

## What Sudachi supplies versus what we implement

| Capability | First-version approach |
| --- | --- |
| Word/compound segmentation | Use Sudachi C mode directly; accept its boundaries. |
| Inflection analysis and lookup forms | Use Sudachi's dictionary form and POS/inflection metadata. This does not mean an entire polite/negative construction is one token. |
| Readings | Use Sudachi's contextual reading output; it is not a guarantee of the intended reading for every ambiguous word/name. |
| Spelling normalization | Use only for matching where appropriate; never replace displayed source text. |
| Grammar and suffix categories | Use Sudachi POS tags. Our display filter leaves particles, auxiliaries and standalone affix tokens uncoloured. |
| Person/place labels | Use explicit person/place proper-name POS tags where present. Not every proper noun or real name receives such a tag. |
| Vocabulary/Anki status | Our existing inventory matching, using Sudachi dictionary/surface forms. |
| JLPT colours | Our existing JLPT data, matched to the selected Sudachi token; no constituent fallback. |
| Kanji-dependent furigana visibility | Our separate known-kanji inventory and ruby/CSS logic. |
| Ruby alignment, escaping and layout | Our existing rendering helpers, with focused fixes where required. |
| Dotted name underline | A small CSS/rendering addition for directly tagged person/place tokens only, if straightforward. |

Sudachi handles much of the linguistic analysis, but is not an HTML reader and does not
know the user's Anki inventory, JLPT display preferences or known kanji.

## Deliberate simplifications and limitations

- **No extra JMdict validation, candidate ranking, substring scanning, A/B boundary
  selection, manual suffix attachment or custom deinflection in this version.**
- C mode often groups compounds, but does not promise our exact manual boundaries.
  Accept native segmentation for long noun chains and derived forms.
- `食べました` may still contain a lexical token plus separate auxiliaries. Only
  eligible kanji-containing lexical tokens get a background; we will not automatically
  extend it across all endings. This differs from the full-inflection draft examples.
- If a suffix such as 的 or っぽい is a separate token, leave it neutral rather than
  highlight it alone. If Sudachi includes it in the word, render that word as a unit.
  We do not promise every derived form is grouped.
- Preserving all source characters is mandatory; making every visible word ending
  share a background is not. Check the original small-kana failure when a real example
  is available rather than assuming a tokenizer swap fixes every symptom.
- Names use only explicit native person/place tags. No JMnedict lookup, name joining,
  honorific-core subranges, ambiguity resolver or NER model. Dotted styling follows
  those token boundaries; a generic proper-noun tag is insufficient to call it a person
  or place. If even this requires substantial special handling, defer the feature.

Any further grouping work should be driven by observed reader failures after this
version is reviewed, not by trying to anticipate all Japanese constructions.

## Required application behavior

- Colour only eligible kanji-containing vocabulary. Standalone kana words, particles,
  auxiliaries, symbols and standalone affixes stay neutral. Keep kana in the analysis.
- Use the existing JLPT palette and known-word highlight controls. Unlisted words stay
  neutral; do not invent levels from component kanji or constituent words.
- Match vocabulary independently of kanji knowledge. Do not let reading-only homophones
  mark unrelated kanji words as known.
- In unknown-kanji furigana mode, hide a ruby group only when **all represented kanji**
  are known, irrespective of vocabulary status. Keep grouped irregular readings when
  reliable finer alignment is unavailable; do not fabricate missing readings.
- Preserve source characters, whitespace and HTML safety under the existing newline
  policy: normalize CRLF and collapse runs of blank lines as the reader currently does.
- Develop without Anki using separately injected mock vocabulary and kanji sets. Never
  silently substitute mock inventories for failed live loads.
- If cheap native name styling is included, dotted underlines remain independent of
  vocabulary/furigana toggles. Leave those names out of ordinary JLPT colouring and the
  unknown-vocabulary list; add a short legend. No promise of complete name coverage.

## Implementation steps

### 1. Establish the native Sudachi baseline

- Add compatible pinned SudachiPy and SudachiDict-core versions through `uv`; update
  `pyproject.toml` and `uv.lock`, verify `uv sync`, and retain required notices.
  Check engine/dictionary binary-format compatibility rather than blindly choosing
  independently latest packages.
- Tokenize the eight annotated passages in C mode and show native segmentation,
  dictionary forms, readings and relevant POS tags in a small review preview.
- Update stale approval labels while retaining human-annotation provenance. Clearly
  distinguish illustrative human boundaries from expected native-parser behavior.
- Show differences, especially inflected endings, compound/suffix boundaries and name
  tags. Do not change human annotations to pretend they match the parser.

**Exit:** a reviewable native baseline and a concrete account of remaining differences,
not a new custom linguistic layer. Stop and discuss material problems before expanding scope.

### 2. Replace the reader's morphology and keep display rules small

- Replace the reader's Fugashi analysis with a small reusable Sudachi C-mode helper.
  Retain only the data actually needed for matching/rendering, including source offsets,
  surface, dictionary form, reading and POS. Do not expose parser objects in templates.
- Use original source slices/offsets for display and retain intervening whitespace/text.
- Apply the simple kanji/POS display filter, existing vocabulary matching and whole-token
  JLPT lookup. Count eligible unknown dictionary forms, not grammatical pieces.
- Check whether explicit person/place tags support dotted token styling with a small
  conditional and CSS class. Include it if so; otherwise document deferral.
- Leave shared Fugashi-based Anki cue rendering working; this is a reader-only migration.

**Exit:** native Sudachi tokens drive reader output with no custom compound/inflection
engine, and no independent background on grammar or affix tokens.

### 3. Fix furigana knowledge and integrate offline

- Pass known vocabulary and known kanji separately through `web.py` and rendering.
- Reuse ruby helpers with Sudachi readings. Fix directly encountered alignment issues
  such as multi-kanji chunks; retain grouped/plain fallback when alignment/reading is
  unavailable. Do not make this a comprehensive ruby-data project.
- Use separate vocabulary and ruby CSS classes; remove the known-word ancestor rule
  that currently hides readings. Clarify the furigana “Unknown only” label as unknown kanji.
- Keep input validation, escaping, layout, display controls and meaningful loading errors.
- Provide a small explicit offline/demo entry point with mock inventories and test the
  Flask boundary without live Anki.
- Manually review passages in the real reader, including mobile wrapping, ruby and
  optional dotted underlines. Check representative and 50,000-character inputs for
  obvious performance problems; no benchmark framework is required.
- Document setup, native segmentation limitations, offline use and optional names in
  `README.md`.

**Exit:** an offline usable reader with independent kanji-based furigana and native
Sudachi boundaries, ready for user review before any additional grouping work.

## Tests and acceptance

Use focused red → green → refactor tests for application behavior. Snapshot a small set
of actual pinned Sudachi outputs as parser integration regressions, separate from the
human-authored annotation corpus. Assert exact source preservation, not exact agreement
with every human lexical boundary.

Required checks:

- Kanji/POS eligibility: kana-only words, grammar and standalone suffixes have no background.
- Dictionary-form matching, whole-token JLPT metadata and unknown-word counts.
- Vocabulary known/unknown crossed with kanji all/some/none known; vocabulary changes
  never change furigana visibility.
- Irregular/grouped readings, missing readings, literal markup escaping and whitespace.
- Existing furigana controls, input limits, empty inputs and injected-loader failures.
- If included, direct person/place tags yield dotted underlines independent of toggles;
  generic proper nouns are not mislabelled as people/places.
- Shared furigana/cue rendering remains unchanged outside the reader.

Run new targeted tests, then the existing reader regressions:

```sh
uv run pytest tests/test_reader_annotation_corpus.py tests/test_article_reader.py tests/test_furigana.py tests/test_web.py
```

Use configured LSP diagnostics for changed code. No live Anki tests without announcing
that work and checking prerequisites. No dictionary/card writes are needed.

## Later, only as needed

- Verify the read-only known-kanji loader against `anki/connect.py:get_reviewed_kanji`
  when Anki becomes available; confirm its review criterion matches intended knowledge.
  Vocabulary membership must never imply kanji knowledge.
- Revisit specific harmful boundaries the user identifies after seeing native output.
  Do not add an entire grouping system to solve hypothetical disagreements.
- Defer improved name recognition, name-specific dictionaries, larger Sudachi editions,
  organization detection, neural NER, JmdictFurigana and extra UI workflows.

No GPL reader code copying, new remote dictionary calls or whole-project parser migration
is needed for this plan.

## Implementation verification

- SudachiPy 0.6.11 and SudachiDict-core 20260428 are pinned together and installed.
- Native C-mode output drives reader highlighting and unknown-word counts; names use
  only direct person/place POS tags with a dotted border.
- Ruby visibility uses separate known-kanji data. Live loading has an opt-in strict
  error path; existing CLI/card callers retain their previous best-effort behavior.
- All eight human passages are preserved, with a standalone native preview showing
  boundary/reading differences rather than forcing annotation agreement.
- The 50,000-character limit exposed Sudachi byte limits during testing. Long inputs
  are now chunked near punctuation/newlines, with smaller retries for normalization
  expansion; source-preservation tests cover these cases. Review also found Flask's
  default form-size cap rejected 50,000 supplementary characters before reader validation.
  The form cap now accommodates URL-encoded text, and the textarea relies on server
  validation instead of UTF-16 `maxlength` truncation.
- A real localhost HTTP demo smoke test covered the editor, POST, name/ruby classes
  and assets. No browser binary was available, so visual/interactive browser review
  is still explicitly pending; generated HTML and display hooks are covered by tests.
- One local measurement (325-character corpus): first request ~27 ms, warm request
  ~2 ms; a 50,000-character repeated corpus request ~164 ms; peak process RSS ~185 MiB.
  These are observations, not latency guarantees.

Final targeted regression command:

```sh
uv run pytest tests/test_reader_annotation_corpus.py tests/test_reader_preview.py tests/test_article_reader.py tests/test_furigana.py tests/test_web.py tests/test_reader_kanji_loader.py
```

Result after personal `review-changes` review and Hunk readability feedback: **99 passed**.
The Hunk refactor introduced named `PartOfSpeech` fields and separated article text/ruby
HTML into `article_render.py`. Analysis and vocabulary aggregation remain in
`article_reader.py`; the page template renders the vocabulary list. The regenerated
native preview remained byte-for-byte identical. `uv sync`, syntax compilation and `git diff --check` also passed.
Reader/new test modules have no Ruff LSP diagnostics; existing typing/style warnings
remain in shared `furigana.py` and `anki/connect.py`.

The vocabulary data flow is now named explicitly:
`analyze_article` → analyzed tokens → `build_unknown_vocabulary_summary` →
filter eligible unknown-to-inventory words → count normalized dictionary forms by JLPT
level → sorted `JlptVocabularyGroup` records containing `VocabularyCount` records →
page template. Article HTML uses the original analyzed tokens independently; summary
filtering does not remove words from the article.

All HTTP in loader tests is mocked. No real Anki calls, card changes or deck changes
were made. Remaining live verification is described above.
