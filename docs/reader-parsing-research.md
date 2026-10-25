# Japanese reader parsing — initial research

Research performed by the read-only `jp-reader-research` agent in the Herdr `research`
tab, alongside preparation of the [manual annotation draft](reader-annotation-draft.md).
No production edits, added dependencies or Anki calls were made by the researcher.
This is a recommendation for experiments, not a selected implementation.

## Main finding

A morphological token is not necessarily the learner-facing word we want to highlight.
Changing tokenizers alone will not settle inflection boundaries, productive compounds,
grammatical constructions, suffixes, names or furigana visibility.

Compare two approaches against the **human-approved** annotations:

1. **Existing Fugashi/UniDic plus dictionary-supported span building**, preserving full
   POS and inflection information. This causes the least deployment disruption.
2. **Sudachi multi-granularity candidates plus the same span policy.** Its longer split
   modes can help compounds; smaller subdivisions remain available for fallback lookup.

Use separate morphological tokens, lexical lookup spans, vocabulary status and
kanji-based ruby groups. Respect this user's kana-only highlight suppression as a
presentation preference; kana tokens still matter for parsing grammar and inflections.

## Existing stack and evidence

The researcher inspected the article analyzer, ruby renderer, Flask boundary, frontend,
tests and pinned dependencies. Its existing-environment Fugashi probe reported:

| Text | Current segmentation |
| --- | --- |
| 国家公務員 | 国家 / 公務 / 員 |
| 働いていました | 働い / て / い / まし / た |
| について | に / つい / て |
| 一般的な | 一般 / 的 / な |
| 待ってください | 待っ / て / ください |
| 東京都立大学 | 東京 / 都立 / 大学 |

`つい` can be tagged as an ordinary verb despite its grammatical use here. Excluding
only particles and auxiliaries is not sufficient. Preserve finer POS and construction
information instead of relying on JLPT membership to identify lexical occurrences.

The probe did **not** reproduce small-kana splitting in `きょう` or `ちょっと`.
We still need the user's exact failing sentences before diagnosing that symptom.

The current ruby helper already supports known-kanji classes, but article rendering
does not pass a separate kanji inventory and the frontend hides ruby under known-word
wrappers. There are also alignment edge cases to test: multi-kanji chunks are checked
with a single-kanji regex, and the first matching kana anchor is not necessarily unique.

## Reusable approaches

- **Fugashi / UniDic:** already installed, useful contextual morphology and readings;
  short-unit segmentation needs a learner-span layer. UniDic-lite's older dictionary
  may limit vocabulary/name coverage; dictionary upgrades do not settle span policy.
- **Sudachi:** A/B/C granularities explicitly support examples such as
  `国家 / 公務 / 員`, `国家 / 公務員`, `国家公務員`. Longer mode is not automatically
  the desired study unit. Evaluate engine/dictionary compatibility, native packaging,
  memory and installation size before adding it.
- **Yomitan:** useful design reference for candidate spans, deinflection and dictionary
  validation. Interactive lookup can offer overlapping possibilities; automatic passage
  highlighting must choose them. Naive longest-match selection can over-merge words.
  Relevant source is GPL-3.0-or-later: do not copy it into this MIT project without a
  licensing decision.
- **Jamdict/JMdict:** already available locally for lexical evidence. Validate spelling,
  reading restrictions and POS, not merely string presence; do not invent a compound's
  JLPT level from its components.
- **JmdictFurigana:** word-and-reading-specific ruby alignment data, including irregular
  groups. It is not a sentence parser and does not eliminate ambiguity, especially names.

Prefer local dictionaries for deterministic passage analysis rather than making one
remote Jisho request per candidate. Code licenses and dictionary-data licenses are
separate; check the exact distributed snapshots, attribution and share-alike obligations.

## Ruby policy to validate

Hide a ruby group only if **every kanji represented by that group** is independently
known. Use reliable finer alignment when available; otherwise retain a grouped reading
if any represented kanji is unknown. Never manufacture a per-character split for
`大人 → おとな`. Vocabulary status must not affect ruby visibility.

Contextual readings can still be ambiguous. Test irregular readings, names, `々`,
compatibility forms and kanji outside the current basic CJK range. Preserve original
source spelling and fall back safely when no trustworthy reading exists.

## Suggested comparison after approval

Evaluate the current baseline, improved Fugashi span building, Sudachi A/B/C, and
multi-granularity Sudachi with the same lexical layer. Measure separately:

- exact span precision/recall, harmful over-merges and partial-compound spans;
- grammar and standalone-suffix false positives;
- canonical lookup identity and reading/ruby correctness;
- names, mixed-script words, inflections and kana-only suppression;
- vocabulary known/unknown × kanji all/some/none known;
- cold start, memory, package size and throughput.

Keep real user failures and a held-out set, not just the synthetic development examples.
Choose the smallest approach that meets the approved behavior; no rewrite decision yet.

## Primary sources consulted by the researcher

- [Fugashi](https://github.com/polm/fugashi)
- [UniDic-lite](https://github.com/polm/unidic-lite)
- [Sudachi Python implementation and split modes](https://github.com/WorksApplications/sudachi.rs/tree/develop/python)
- [Sudachi dictionary notices](https://github.com/WorksApplications/SudachiDict/blob/develop/LEGAL)
- [Yomitan lookup/deinflection](https://github.com/yomidevs/yomitan/blob/master/ext/js/language/translator.js)
- [Yomitan Japanese utilities and alignment](https://github.com/yomidevs/yomitan/blob/master/ext/js/language/ja/japanese.js)
- [Jamdict documentation](https://jamdict.readthedocs.io/en/latest/)
- [JmdictFurigana](https://github.com/Doublevil/JmdictFurigana)
- [EDRDG dictionary licensing](https://www.edrdg.org/edrdg/licence.html)
