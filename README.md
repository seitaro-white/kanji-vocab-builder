# Kanji Vocab Miner

This is a very simple CLI tool to help with learning Japanese kanji and vocabulary. It glues together Jisho (an online Japanese dictionary) and Anki (the flashcard program), and designed with a context-based learning approach to Kanji in mind; as new kanji are learned, we find new vocabulary that include those Kanji to learn the readings (rather that painful rote memorization of kun and on readings from kanji alone).

![demo.gif](docs/demo.gif)

## What It Does

The tool allows for searching of either specific kanji or words.
- When a word is searched, it will look up the word on Jisho, display its details, and allow you to add it to your Anki vocabulary deck.
- When a kanji is searched, it will first look up the Kanji on Jisho, then fetch a list of vocabulary words that include that kanji, with details including JLPT level, whether the word already exists in your Anki deck and whether the other kanji in the word are already in your list of reviewed kanji. You can then select which words to add to your Anki vocabulary deck.

The workflow is designed to complement kanji study: as you learn new kanji, you naturally build vocabulary that reinforces those characters.

## Who is it for?
Originally just me!

There are literally hundreds of far more polished/sophisticated tools for learning Japanese available on the web. The use-case/workflow here is very niche to my own learning style and circumstances. You might find this tool useful if:
   - You are reading primarily printed Japanese texts (textbooks and novels) rather than online content, where vocabulary mining tools like Rikaichan, or learning apps like Todai are arguably far more useful/convenient.
   - You already have a decent base of spoken Japanese and are focusing on catching up on reading/writing skills (this may apply to learners who grew up speaking, but not reading/writing, Japanese).
   - You hate Duolingo and would actually like to learn a language properly!


## Installation

Using this tool requires some Anki setup:

1. **Anki Desktop** - Download from [apps.ankiweb.net](https://apps.ankiweb.net/)
2. **AnkiConnect Plugin** - Install from [AnkiWeb](https://ankiweb.net/shared/info/2055492159)
   - In Anki: Tools → Add-ons → Get Add-ons → Enter code `2055492159`. This plugin allows external programs to interact with Anki via a local API.
3. **"All in One Kanji" Deck** - Download from [AnkiWeb](https://ankiweb.net/shared/info/1862058740)
   - This is the recommended kanji deck that the tool expects by default.
   - File → Import → Browse to downloaded `.apkg` file
   - The tool will re-order existing cards from this deck for kanji study, while creating entirely

Once this is done (and Anki is running with AnkiConnect enabled), install the tool with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install git+https://github.com/yourusername/kanji-vocab-miner.git
kanji-vocab-miner setup
```

This installs `kanji-vocab-miner` globally so you can run it from any directory. If you don't have uv installed, follow the [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/).

To update to the latest version, upgrade the tool and run setup again so Anki has
the current V3 vocabulary note type and templates:

```bash
uv tool upgrade kanji-vocab-miner
kanji-vocab-miner setup
```

A [DeepSeek API key](https://platform.deepseek.com/) is required when committing
new vocabulary, but not for setup, searching, or reviewing pending words. Export
it in the environment used to launch the tool:

```bash
export KANJI_VOCAB_MINER_LLM__API_KEY="your-api-key"
```

The key is environment-only. **Do not put it in `config.toml`.**


## Usage

### Interactive Mode

Make sure Anki is running and run `kanji-vocab-miner` to start the interactive session:

**Commands:**
- `n` - Look up the kanji on the card currently open in Anki Reviewer
- `a` - Move the most recently looked-up kanji card to the top of its Anki deck
- `c` - Review and commit pending words to Anki
- `q` - Quit the program
- Type a kanji directly (e.g., `食`) - Search for words containing that kanji and show whether its Anki card has been reviewed
- Type `@word` (e.g., `@食べる`) - Look up a specific word on Jisho
- When in word selection mode, enter numbers or ranges (e.g., `1 3 5` or `1-5`) to select words to add

### Vocabulary cards and commit review

Run `kanji-vocab-miner setup` after installing or upgrading. Setup creates or
safely refreshes the required `MyJapaneseVocabularyV3` note type in the existing
`KanjiVocabMiner-Vocabulary` deck. It does not migrate or regenerate existing
cards. Legacy `MyJapaneseVocabulary` and `MyJapaneseVocabularyV2` notes remain
unchanged in the deck.

New pending words default to **Add on** and **Recall off**. The commit review
screen supports:

- `Up`/`Down`: move between rows
- `Space`: toggle Add for the focused row
- `r`: toggle Recall; enabling Recall also enables Add
- `a`/`n`: enable or disable Add for all rows without erasing Recall choices
- `Enter`: commit Add-enabled rows and discard Add-disabled rows
- `Esc`/`q`: abort while preserving pending rows and Recall choices

Each newly committed V3 note receives a Japanese-to-English recognition card.
Its back shows these sections in order:

1. the primary Jisho dictionary definition;
2. **Nuance** — one English sentence about usage beyond the short definition;
3. **Example** — one short Japanese sentence, with the exact used form bold and
   red (no translation or separate reading); and
4. **Why these kanji** — a word-level explanation of the kanji, okurigana, or
   the fact that no kanji applies.

DeepSeek generates the three enrichment sections automatically during commit.
Generation is grounded in the word's first dictionary definition and first part
of speech. There is no generated-content preview or approval step. The existing
recall card behavior is unchanged: enabling Recall also creates a
Japanese-definition-to-Japanese-word card.

The Japanese definition is fetched synchronously from Kotobank for every note,
including recognition-only notes. Definitions prefer デジタル大辞泉 and fall
back to 精選版 日本国語大辞典. Results are not cached. The normalized text,
rendered cue, source name, and canonical source URL are stored on the note.
DeepSeek generation runs concurrently, while successful notes are written to
Anki sequentially in the reviewed order.

Each word gets at most three DeepSeek attempts, with short exponential backoff
and validation feedback after an invalid response. If definition, furigana,
enrichment, or Anki writing fails, that word is skipped while other successful
rows can still be committed. Failed rows remain pending in reviewed order with
their Recall choice for retry. If the API key is missing, all eligible
nonduplicate rows fail clearly at enrichment and remain pending; the tool never
falls back to creating V2 or unenriched V3 notes.

Legacy, V2, and V3 expressions all participate in duplicate detection. Legacy
and V2 notes remain in the deck and continue to participate in furigana sync
when they contain compatible `Front` or `JapaneseCue` fields.

Cue furigana follows the same reviewed-kanji visibility rules as the vocabulary
word. To enable recall later, set the note's `Recall` field to `1` in Anki. To
disable it, clear `Recall`, then run **Tools → Empty Cards** because Anki keeps
previously generated cards until empty cards are removed.

### DeepSeek enrichment settings

Setup creates the default editable prompt at
`~/.config/kanji-vocab-miner/enrichment-prompt.md` only when that file is
absent. Existing prompt edits are never overwritten. Edit this file to change
content guidance for nuance, examples, and kanji explanations. The application
owns the structured response schema, validation, and safe example highlighting;
the editable prompt does not replace that fixed contract.

The prompt path and request concurrency are the only LLM settings in
`~/.config/kanji-vocab-miner/config.toml`:

```toml
[llm]
prompt_path = "~/.config/kanji-vocab-miner/enrichment-prompt.md"
concurrency = 5
```

`concurrency` controls simultaneous DeepSeek generation requests, defaults to
`5`, and accepts values from `1` through `10`. The API key is not a TOML setting.
Set it in the process environment, or put the following in a `.env` file in the
current working directory (the repository `.gitignore` excludes this file):

```dotenv
KANJI_VOCAB_MINER_LLM__API_KEY="your-api-key"
```

An explicitly exported environment variable takes precedence over `.env`. When
running `uv run kanji-vocab-miner` from the repository root, the local `.env`
file is loaded automatically.

### Progress dashboard

Run `kanji-vocab-miner stats` to show your Kanji, Reading, Grammar, and
vocabulary progress. Overall bars appear together at the top, followed by
Kanji and textbook-part breakdowns. Vocabulary is measured against a core
6,000-word target: the tool adds every vocabulary note created on or after the
configured tracking date to the manually estimated baseline.

For now, the file is read from the directory where you run the command. When
working from this repository, edit the included `manual_progress.toml` and run
`uv run kanji-vocab-miner stats` from the repository root.

The file contains:

```toml
vocab_baseline = 4400
vocab_tracking_start = 2026-09-03

reading_i = 0
reading_i_total = 41
reading_ii = 0
reading_ii_total = 29
reading_iii = 0
reading_iii_total = 11
grammar_i = 0
grammar_i_total = 10
grammar_ii = 0
grammar_ii_total = 11
grammar_iii = 0
grammar_iii_total = 5
grammar_iv = 0
grammar_iv_total = 7
grammar_v = 0
grammar_v_total = 3
grammar_vi = 0
grammar_vi_total = 12
```

`vocab_baseline` is the known-word estimate on `vocab_tracking_start`.
Vocabulary notes added to the configured deck from that date onward increase
this count, whether or not they have been reviewed yet.

Each Reading and Grammar count is an independent number of completed sections.
Its matching `_total` value sets the bar's maximum; the overall maximum is the
sum of those section totals. The included file retains Reading totals of I=41,
II=29 (book sections 42–70), III=11, and Grammar totals of I=10, II=11 (book
sections 11–21), III=5 (book sections 22–26), IV=7, V=3, VI=12.
All nine `_total` keys are required.


## Credits

- [Jisho.org](https://jisho.org/) for the excellent Japanese dictionary API
- [AnkiConnect](https://foosoft.net/projects/anki-connect/) for making Anki automation possible
- [All in One Kanji](https://ankiweb.net/shared/info/1862058740) deck creators (whoever you are!)
