# Web reader visual polish

## Goal and scope

Polish the existing Flask reader with cleaner controls, subtle outlined highlights
and a responsive vocabulary grid. This consolidates the recovered frontend draft
and the subsequent validation-only work into one active plan. Historical parser
work remains in [the Sudachi plan](reader-sudachi-implementation-plan.md).

Keep local assets, system fonts, existing parser output and all knowledge/display
behavior. No new dependencies or framework. Exclude parser changes, new name
recognition, dictionary lookups, search/filtering, clickable vocabulary actions,
Anki writes, dark mode and word-boundary/debug controls.

## Implementation sequence

1. **Page and controls:** introduce a few shared CSS variables; polish editor,
   notices, article panel, responsive spacing and typography. Connect the furigana
   buttons visually, keep the known-word toggle separate, and make the legend and
   Start Over secondary. Preserve semantic buttons, focus, pressed states and JS hooks.
2. **Word outlines:** use existing JLPT/token classes for fine inline outlines and
   restrained rounding. Known words stay neutral until highlighting is enabled.
   Preserve ruby, prose wrapping and dotted name underlines; do not make word chips
   unbreakable. Grammar, kana-only and unlisted words remain neutral.
3. **Vocabulary grid:** keep semantic lists beneath the article, grouped N5 through
   N1 then Unlisted. Derive distinct-entry counts from existing collections. Show
   expressions prominently and frequencies as accessible badges. Preserve ordering,
   exclusions and escaping. Long entries must wrap; tiles are not interactive.
4. **Tests:** extend mocked Flask page tests for counts, badges, escaping, controls
   and empty results. Reuse existing grouping/order/exclusion regressions rather
   than duplicate parser tests. Avoid exact CSS-format assertions.
5. **Finish:** review the explicit offline demo at desktop/mobile sizes, keyboard
   focus, display combinations, ruby wrapping, long/large/empty vocabulary and
   editor/error/demo states. Regenerate the native preview without changing its
   comparison content. Update README; run diagnostics and `git diff --check`.

## Verification

```sh
uv run pytest tests/test_web.py
uv run pytest tests/test_reader_annotation_corpus.py tests/test_reader_preview.py tests/test_article_reader.py tests/test_furigana.py tests/test_web.py tests/test_reader_kanji_loader.py
uv run python -m kanji_vocab_miner.web --demo
uv run python scripts/preview_sudachi_reader.py
```

Use an available browser or an approved temporary browser setup; record unavailable
checks honestly. Live Anki validation is separate and does not block styling work.
Repeat packaging checks only if paths, configuration or dependencies change.

## Definition of done

Coherent desktop/mobile presentation, inline outlines compatible with ruby and
wrapping, scannable vocabulary tiles, unchanged knowledge/grouping/control behavior,
passing regressions and recorded visual-review results or explicit limitations.

## Baseline verification (before redesign)

- `uv sync`: passed, no dependency changes.
- Focused reader regressions: **99 passed**.
- CLI localhost/port/debug test: **1 passed, 15 deselected**.
- Wheel/sdist built with all reader assets. Installed-wheel HTTP smoke outside the
  source tree passed editor/assets/result hooks/escaping, 50,000-character acceptance,
  50,001-character and empty-input rejection, and demo-editor navigation. It used
  synced dependencies, not a clean dependency-resolution install, and was not a
  browser interaction test.
- Syntax compilation and `git diff --check`: passed.
- Live Anki: pending; the read-only version request to `127.0.0.1:8765` was refused.
  No cards/decks were changed.
- Browser review: pending; no browser or Playwright/Puppeteer installation found.

## Implementation results

- Implemented page/editor styling, semantic grouped controls, inline JLPT outlines,
  and responsive non-interactive vocabulary tiles with distinct counts and accessible
  frequency text. Parser, loaders, aggregation and JavaScript remain unchanged.
- `uv sync`: passed with no project dependency or lockfile changes.
- Web tests: **29 passed**. Full focused reader command above: **102 passed**.
  Coverage includes controls/semantics, singular/plural counts, frequency ordering,
  escaping hostile vocabulary values and omission of empty vocabulary results.
- Real localhost HTTP demo smoke passed for the editor, local assets, grouped
  controls, vocabulary tiles/counts and navigation markup. This is not browser JS
  execution or visual validation.
- Regenerated `docs/reader-sudachi-preview.html`. The native comparison section was
  compared against HEAD and is unchanged. The standalone preview omits the new
  navigation wrapper as well as the Start Over link.
- Ruff diagnostics for changed Python files and Biome diagnostics for CSS/template:
  **no diagnostics**. Syntax compilation and `git diff --check` passed.
- Browser review completed using the existing sidecar Chromium through
  `BROWSER_CDP_URL` and `BROWSER_TOKEN`, with Playwright via `uvx` outside project
  dependencies. The earlier local launch failed due to missing libraries, but that
  is not a blocker: the sidecar was available. No OS packages were installed.
- A temporary offline demo was exposed to the sidecar on port 18766; it was stopped
  after checks. The application's normal localhost-only binding is unchanged.
- Chromium checks passed at 1280px, 375px and 320px: all furigana/highlight
  combinations without network requests, pressed states, keyboard activation/focus,
  ruby display rules, known-word outline visibility, no horizontal overflow,
  synthetic long-expression wrapping, empty vocabulary, 50,000-character submission,
  editor/error/demo states and Start Over. No JavaScript errors were observed.
- Screenshots of the desktop/mobile reader and editor/error states were captured and
  visually inspected. Review found single-entry groups stretching tiles across the
  desktop; changing the grid from `auto-fit` to `auto-fill` keeps tile widths
  consistent across groups. Browser checks passed again after that correction.
- Screenshots are temporary artifacts at `/tmp/reader-polish-*.png`; the temporary
  check script is `/tmp/reader-polish-browser-check.py`. This is Chromium-only review,
  not a cross-browser or full assistive-technology audit. Host-browser forwarding
  remains unverified and is separate from the sidecar review.
- After the grid correction, `uv run pytest tests/test_web.py tests/test_reader_preview.py`:
  **42 passed**. Preview regenerated and `git diff --check` passed.
- Live Anki remains separately pending; no live calls or inventory/card/deck changes
  were made during the redesign.
