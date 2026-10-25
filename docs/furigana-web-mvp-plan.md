# Furigana Article Reader MVP — Implementation Plan

> Historical plan. For current visual-improvement work, use the
> [frontend polish plan](reader-frontend-plan.md). The
> [Sudachi implementation plan](reader-sudachi-implementation-plan.md) supersedes
> this document's parser, knowledge, colouring and newline decisions.

## 1. Goal

Add a localhost-only web reader to `kanji-vocab-miner`. A user pastes plain
Japanese text, submits it, and receives a safe reading view in which:

- vocabulary is coloured by JLPT N5–N1;
- unknown kanji-bearing tokens show furigana by default;
- known tokens hide furigana by default; and
- the user can switch between unknown-only, all, and no furigana without
  reprocessing the article.

The MVP processes pasted plain text only. It does not extract browser pages,
preserve rich HTML, export results, or replace the existing browser dictionary
extension.

## 2. Agreed product decisions

### Known vocabulary

A word is known when a normalized token identity matches either:

1. an `Expression` from any vocabulary note in the configured Anki vocabulary
   deck; or
2. an entry in `~/.config/kanji-vocab-miner/known_vocab.txt` (through the
   existing `known_words` API).

Anki is queried on every submission. If AnkiConnect is unavailable, processing
is blocked and the page shows a retryable error. The app must call
`get_vocab_expressions()` directly rather than `get_reviewed_vocab()`, because
the latter deliberately converts connection errors to an empty list.

The current measured cost of loading 2,260 expressions is 0.321 seconds, so an
expected request time around 0.3–0.5 seconds is acceptable for the MVP.

### Matching

- Use Fugashi/UniDic, which are already dependencies.
- Match one morphological token at a time.
- Prefer normalized canonical identities: lemma, dictionary orthography, and
  kana forms, with surface form available as a conservative fallback.
- Normalize Unicode consistently and compare kana in a consistent script.
- Do not infer that a compound is known from known component words or kanji.
- Avoid cross-script homophone false positives: a kana candidate may match a
  stored kana spelling, but a stored kanji spelling must not be converted to a
  reading merely to force a match.
- Multi-token expressions are out of scope. For example, Fugashi can split
  `勉強する` into `勉強` and `する`; the MVP does not merge those tokens.

### Furigana and colour

- Generate ruby for every kanji-bearing token with a usable UniDic reading so
  the browser can switch modes without another server request.
- Align ruby to kanji chunks and leave okurigana outside the ruby, reusing or
  extracting the existing alignment behavior in `furigana.py`.
- Fall back to whole-token ruby when chunk alignment is ambiguous.
- Preserve unknown kanji unchanged when UniDic provides no reading.
- Default display mode: furigana on unknown tokens only.
- Other client-side modes: furigana on all tokens, or no tokens.
- Look up JLPT level using the existing `jlpt` index, applying the same ordered
  token identities used for vocabulary matching.
- Apply a readable soft background colour to every JLPT-listed token.
- Leave tokens absent from the JLPT vocabulary list visually neutral.
- Do not fall back to kanji-level JLPT data.

### Page behavior

- Bind only to `127.0.0.1`.
- Accept at most 50,000 Unicode characters.
- Treat input as plain text and escape it before rendering.
- Preserve spaces, newlines, and paragraph breaks.
- A successful result replaces the editor.
- The result view includes a colour legend, three furigana mode controls, and a
  **Start Over** action.
- Do not add token tooltips or a click inspector.

## 3. Proposed architecture

### `kanji_vocab_miner/article_reader.py` — pure article processing

Keep token analysis independent of Flask and Anki IO.

Add typed immutable models such as:

```python
@dataclass(frozen=True)
class ArticleToken:
    surface: str
    leading_whitespace: str
    reading: str | None
    identities: tuple[str, ...]
    is_known: bool
    jlpt_level: int | None
```

Primary functions:

- `normalize_identity(value: str) -> str`
- `token_identities(token: UnidicNode) -> tuple[str, ...]`
- `analyze_article(text: str, known_words: set[str]) -> list[ArticleToken]`
- `render_article_html(tokens: list[ArticleToken]) -> str`

Responsibilities:

1. Tokenize once with the existing cached Fugashi tagger.
2. Derive unique identities in a documented precedence order.
3. Classify known status and JLPT level.
4. Render only application-owned markup using `html.escape`.
5. Preserve leading token whitespace and any tokenizer-unconsumed suffix.

Extract a small general-purpose ruby alignment helper from `furigana.py` if it
can be shared without changing existing Anki card output. Keep the existing
`render_japanese_cue()` contract and tests intact.

### `kanji_vocab_miner/web.py` — Flask application boundary

Use an application factory for testability:

```python
def create_app(
    expression_loader: Callable[[], set[str]] = get_vocab_expressions,
    known_loader: Callable[[], set[str]] = load_known_words,
) -> Flask:
    ...
```

Routes:

- `GET /`: render the paste form.
- `POST /`: validate input, load known vocabulary, analyze, and render result.

Validation and errors:

- Empty input: return the form with an inline validation message.
- More than 50,000 characters: reject without contacting Anki.
- AnkiConnect failure: return the original text and a clear message instructing
  the user to start Anki/AnkiConnect and retry.
- Unexpected processing failure: return a safe generic page message; never
  include unescaped exception content in HTML.

Run with Flask's development server, debug mode disabled, on `127.0.0.1`.

### Web assets

Add:

- `kanji_vocab_miner/templates/article_reader.html`
- `kanji_vocab_miner/static/article_reader.css`
- `kanji_vocab_miner/static/article_reader.js`

Use one template with form/result/error states. The template must treat rendered
article HTML as trusted only because it came from the escaping renderer; no
user-supplied value should otherwise use Jinja's `safe` filter.

JavaScript should only:

- change a mode class on the result container;
- update `aria-pressed` on the three controls; and
- support the Start Over transition/navigation.

No external JavaScript or CSS CDN is required.

### CLI and packaging

- Add Flask to `pyproject.toml` with `uv add flask`; commit the corresponding
  `uv.lock` update.
- Add a Click subcommand:

  ```bash
  uv run kanji-vocab-miner web
  ```

- Lazily import the web module inside the command so normal CLI startup does not
  initialize Flask.
- Ensure templates and static assets are present in built wheel/sdist output;
  add explicit Hatch include configuration if the build does not include them
  automatically.
- Do not automatically expose the server to the LAN or enable Flask debug mode.

## 4. Implementation sequence

### Phase 1 — Establish processing contracts with tests

Create `tests/test_article_reader.py` first.

Cover:

1. plain kana, punctuation, Latin text, and numbers pass through safely;
2. HTML-like input is escaped and cannot inject elements;
3. whitespace, blank lines, and trailing whitespace are preserved;
4. `食べました` exposes `食べる` as the content-word identity;
5. normalized dictionary/kana candidates match intended known entries;
6. orthographically distinct homophones do not become known accidentally;
7. components do not make an unknown compound known;
8. JLPT levels use word data and unlisted words remain neutral;
9. known and unknown tokens receive distinct semantic CSS classes;
10. okurigana receives kanji-chunk ruby;
11. ambiguous/irregular readings use safe whole-token ruby;
12. missing readings preserve the surface text;
13. all output strings are escaped before application markup is added.

Implement the pure models and functions until these tests pass. Refactor shared
furigana alignment only after characterization tests protect existing behavior.

### Phase 2 — Add the web request boundary

Create `tests/test_web.py` using Flask's test client and injected loaders.

Cover:

1. `GET /` shows the editor and submit control;
2. empty text returns a validation error;
3. 50,000 characters are accepted;
4. 50,001 characters are rejected before the Anki loader runs;
5. Anki and manual-known sets are unioned;
6. the Anki loader runs once per valid POST;
7. Anki failure blocks output and preserves the source for retry;
8. successful POST replaces the editor with result controls and Start Over;
9. pasted markup is displayed as text rather than executed;
10. the default result mode is unknown-only.

Then implement `create_app()` and the Flask templates.

### Phase 3 — Add presentation and client-side controls

Implement local CSS and minimal JavaScript.

- Use `white-space: pre-wrap` on the article container.
- Give N5–N1 tokens distinct, contrast-checked soft backgrounds.
- Use semantic classes such as `known`, `unknown`, `jlpt-n5`, and
  `furigana-mode-unknown`.
- Hide/show `<rt>` elements entirely by mode so hidden readings do not leave
  unwanted vertical space.
- Include accessible labels and visible keyboard focus states.
- Keep the layout readable on narrow and desktop screens, without implementing
  a side-by-side editor.

Where practical, assert the required class and control hooks in `test_web.py`.
Manually verify mode switching in a browser because CSS ruby layout is not
meaningfully exercised by Flask's test client.

### Phase 4 — Wire the command and package data

- Add the `web` Click command.
- Start the server on a fixed documented default port (proposed: `8766`) and
  `127.0.0.1`.
- Add CLI tests that monkeypatch the server runner and verify host, port, and
  debug settings without opening a real socket.
- Build the wheel/sdist and inspect them for the template and static files.

### Phase 5 — Documentation and end-to-end verification

Update `README.md` with:

- how to launch the reader;
- the requirement that Anki and AnkiConnect remain running;
- the two sources of known vocabulary;
- the furigana modes and JLPT legend;
- the 50,000-character limit;
- the unofficial/incomplete nature of JLPT vocabulary data; and
- the token-only/multi-token-expression limitation.

Manually test with an article containing:

- a known inflected verb;
- an unknown kanji word;
- a known word from `known_vocab.txt`;
- N5 and N1 vocabulary;
- a word absent from the JLPT list;
- okurigana and an irregular reading;
- multiple paragraphs; and
- literal `<script>` text.

Also stop Anki and confirm submission is blocked with a useful recovery message.

## 5. Verification commands

Run targeted tests first:

```bash
uv run pytest tests/test_article_reader.py
uv run pytest tests/test_web.py tests/test_cli.py
```

Then run the non-integration suite and syntax check:

```bash
uv run pytest
uv run python -m compileall kanji_vocab_miner
```

Build and inspect distributables:

```bash
uv build
unzip -l dist/*.whl | grep -E 'templates|static'
tar -tf dist/*.tar.gz | grep -E 'templates|static'
```

Manual launch:

```bash
uv run kanji-vocab-miner web
# Open http://127.0.0.1:8766
```

Do not run the live Anki integration test module unless explicitly desired; the
manual acceptance test already exercises the required local connection.

## 6. MVP acceptance criteria

The MVP is complete when all of the following are true:

1. The documented command starts a localhost-only reader from an installed
   package.
2. A valid pasted article produces escaped, whitespace-preserving HTML.
3. Known status reflects the live Anki expression set unioned with the manual
   known-word file on every submission.
4. Anki unavailability prevents potentially misleading partial classification.
5. Inflected single-token words match by normalized dictionary identity.
6. Unknown-only, all, and none furigana modes switch without a server request.
7. Furigana aligns to kanji chunks where possible.
8. JLPT-listed tokens use distinct accessible level colours and unlisted tokens
   remain neutral.
9. The 50,000-character boundary is enforced.
10. Start Over returns to an empty editor.
11. Unit/web tests pass, and built artifacts include all web assets.
12. The README clearly states the token-only matching limitation.

## 7. Explicitly deferred work

- Chrome extension or automatic article extraction
- Rich-HTML paste and layout preservation
- Multi-token vocabulary/phrase recognition
- Persistent Anki snapshot or caching
- Token hover/click dictionary details
- Copy-rich-HTML or standalone-file export
- Mark-known/edit-database actions from the result page
- LAN hosting, authentication, and configurable bind settings
- Streaming/progressive rendering for very large texts
- Kanji-level JLPT fallback
