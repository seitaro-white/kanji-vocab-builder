# Reader annotation review — human examples v1

**Status: reviewed as reading intent. Native Sudachi boundaries accepted subsequently.**

The user approved these examples, then clarified in Hunk that native Sudachi behavior
is preferable to custom parsing/grouping to force every human lexical boundary.
The original questions and example notes below are retained as historical context,
not outstanding requirements. See the [implemented native preview](reader-sudachi-preview.html)
and [current plan](reader-sudachi-implementation-plan.md) for the accepted first version.

## Open the visual examples

Open [`reader-annotation-draft.html`](reader-annotation-draft.html) in a browser.
It is standalone, works offline, and does not call Anki, the production tokenizer,
or dictionary services. Regenerate it with:

```sh
uv run python scripts/preview_reader_annotations.py
```

The original, manually selected annotations live in
[`tests/fixtures/reader_annotation_draft.json`](../tests/fixtures/reader_annotation_draft.json).
Each case contains original source text and non-overlapping segments that concatenate
back to that text. A segment's optional `lookup` specifies the proposed lexical identity
and display span. Optional `ruby` pairs cover that segment exactly; `null` readings
mean literal text, including okurigana. No runtime parser generated these annotations.

The integrity tests check source coverage, ruby coverage, preview escaping and the
independence of the mock knowledge sets. **They do not test production conformance**
to the historical human lexical boundaries; native-parser regressions are tested separately.

## Proposed interpretation

Keep these layers independent:

1. Morphological analysis: stems, auxiliaries, suffixes, readings and positions.
2. Learner-facing lexical spans: full inflections and suitable compounds for lookup.
3. Vocabulary knowledge: exact lexical identity in a mock or real vocabulary inventory.
4. Kanji knowledge: a separate inventory controlling ruby visibility.
5. JLPT colouring: optional metadata on the selected lexical span, not a reason to
   highlight grammar or arbitrary suffix tokens.

The preview deliberately uses simple known/unknown colours, **not guessed JLPT levels**.
Yellow shows proposed unknown kanji-containing vocabulary, blue underlines indicate
known vocabulary, and outlines expose the exact proposed word boundaries. An optional
control colours known words too. Pure-kana words remain plain, but kana belonging to a
kanji-containing word can share its highlight, including inflected endings.

Ruby is visible unless **all kanji represented by that ruby group** are mock-known.
This is a conservative fallback for inseparable readings, not a claim that we can
reliably split every reading per kanji. Known vocabulary never suppresses ruby.
Missing readings in a future implementation should remain missing, not be guessed.

The mock sets intentionally include counterexamples:

- `図書館`: known vocabulary, unknown kanji → no default unknown-word colour, ruby visible.
- `学生`: unknown vocabulary, known kanji → coloured, ruby hidden.
- `日本語`: mixed kanji knowledge → complete grouped reading remains visible.
- `生き物`: alignable chunks → ruby on known `生` hidden, unknown `物` visible.

## Original review questions (historical)

These were the questions accompanying the human examples. The current implementation
uses native Sudachi boundaries instead of custom logic to reproduce all these choices:

| Cases | Proposed default | Decision needed |
| --- | --- | --- |
| 1 | Independent vocab and kanji inventories | Does grouped ruby for mixed-known kanji work for you? |
| 2–3 | Full lexical inflections, including small kana; separate auxiliary continuations | `歩いた`, `忘れない` together; `降って` + plain `きた`, `学んで` + plain `いる`? |
| 3, 8 | Honorifics attached to a name/noun span | `お客さん`, `山田さん` together or only the lexical core? |
| 4 | Established compounds grouped | `情報処理`, `人工知能`, `四字熟語` as whole words? |
| 5 | Productive noun chains may split at meaningful boundaries | Merge `環境保護活動`? Merge `申込受付期間`? Include `センター` in `国際交流センター`? |
| 6 | Attach 的; keep following な/に outside | `具体的` rather than `具体` + `的`? |
| 7 | Entire mixed-script lexical word coloured | `生ビール` together, but standalone `ビール` plain? |
| 8 | Include proper names; leave numeric counter 年 plain | Should names and counters be highlighted, separately styled, or ignored? |

The synthetic small-kana examples may not reproduce the precise original failure.
If available, add the actual failing sentences (especially the small-っ/ゅ case and
half-highlighted long compounds) as separate cases without replacing these examples.

## Observed current architecture

- `article_reader.py` renders one span per Fugashi/UniDic token and classifies JLPT
  membership on those same units. Morphological tokens are not necessarily the word
  spans a learner wants.
- `article_reader.css` uses `.furigana-mode-unknown .known rt`; `.known` is currently
  vocabulary status. That directly conflates word and kanji knowledge.
- `web.py` injects vocabulary loaders but does not pass a separate known-kanji inventory
  into article analysis/rendering.
- `furigana.py` already accepts a reviewed-kanji set when rendering ruby. That is useful
  existing machinery to evaluate, not justification for a wholesale rewrite yet.

## Original follow-up outline (superseded by the current plan)

1. Record approved and unresolved decisions; preserve draft provenance.
2. Convert approved examples into parser-independent expected span/ruby fixtures.
3. Compare existing parser/dictionary approaches against exactly those examples;
   track span boundaries, lookup forms, readings, filtering and ruby visibility separately.
4. Implement incrementally with mocked vocabulary/kanji inventories, preserving literal
   source text, HTML safety and layout. Wire up real Anki only after local logic is stable.
5. Add real-world failure passages and hold-out cases so we do not merely tune to this draft.

The separate Herdr `research` tab has completed an initial investigation of reusable
parsers and readers; see [the source-linked research summary](reader-parsing-research.md).
Its findings are advisory; they do not approve these annotation choices or authorize a
rewrite.
