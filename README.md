# Kanji Vocab Miner

A CLI tool that bridges Anki and Jisho for mining Japanese vocabulary. Fetch kanji from your Anki deck, discover vocabulary words containing those kanji from Jisho, and add selected words directly back to Anki.

## What It Does

This tool helps Japanese learners expand their vocabulary by:
1. Pulling kanji you're currently studying from your Anki deck
2. Searching Jisho.org for common vocabulary words that use those kanji
3. Presenting words with readings, meanings, and JLPT levels
4. Adding your selected vocabulary directly to a dedicated Anki deck

The workflow is designed to complement kanji study: as you learn new kanji, you naturally build vocabulary that reinforces those characters.

## Installation

### Recommended: Using pipx

```bash
pipx install kanji-vocab-miner
```

### Alternative: Using pip

```bash
pip install kanji-vocab-miner
```

### From Source (with uv)

```bash
git clone https://github.com/yourusername/kanji-vocab-miner.git
cd kanji-vocab-miner
uv sync
uv run kanji-vocab-miner
```

## Prerequisites

Before using this tool, you need:

1. **Anki Desktop** - Download from [apps.ankiweb.net](https://apps.ankiweb.net/)
2. **AnkiConnect Plugin** - Install from [AnkiWeb](https://ankiweb.net/shared/info/2055492159)
   - In Anki: Tools → Add-ons → Get Add-ons → Enter code `2055492159`
3. **"All in One Kanji" Deck** - Download from [AnkiWeb](https://ankiweb.net/shared/info/1862058740)
   - This is the recommended kanji deck that the tool expects by default
   - File → Import → Browse to downloaded `.apkg` file

## Quick Start

```bash
# 1. Install prerequisites (Anki, AnkiConnect, kanji deck)
# 2. Install the tool
pipx install kanji-vocab-miner

# 3. Make sure Anki is running, then run setup
kanji-vocab-miner setup

# 4. Start using it
kanji-vocab-miner
```

The `setup` command creates:
- A new deck called "Japanese Vocabulary" for storing vocabulary cards
- A custom note type with fields for word, reading, meaning, and JLPT level

## Usage

### Interactive Mode

Run `kanji-vocab-miner` to start the interactive session:

```bash
kanji-vocab-miner
```

**Commands:**
- `n` - Fetch next kanji from your Anki deck
- `c` - Commit selected words to Anki
- `q` - Quit the program
- Type a kanji directly (e.g., `食`) - Search for words containing that kanji
- Type `@word` (e.g., `@食べる`) - Look up a specific word on Jisho

**Typical Workflow:**

1. Type `n` to get your next kanji to study (e.g., `食`)
2. Review the vocabulary list presented from Jisho
3. Enter numbers to select words you want to learn (e.g., `1 3 5` or `1-5`)
4. Type `n` to continue to the next kanji, or `c` to commit selected words
5. Type `c` when ready to add all selected words to your Anki deck

### Setup Command

```bash
kanji-vocab-miner setup
```

Runs the initial setup:
- Tests AnkiConnect connectivity
- Creates the "Japanese Vocabulary" deck
- Creates the custom note type with required fields
- Validates that your kanji deck is present

This command is idempotent - you can run it multiple times safely.

## Configuration

Configuration is optional. The tool works out of the box if you're using:
- Default AnkiConnect URL (`http://localhost:8765`)
- "All in One Kanji" deck name

### Config File Location

`~/.config/kanji-vocab-miner/config.toml`

### Example Configuration

```toml
[ankiconnect]
url = "http://localhost:8765"

[kanji_deck]
name = "All in One Kanji"
```

### When You Need a Config File

Only create/modify the config if:
- You're using a different kanji deck
- AnkiConnect is running on a non-standard port
- You've customized your AnkiConnect setup

### Environment Variables

You can override config values with environment variables:
- `KANJI_VOCAB_MINER_ANKICONNECT__URL` - AnkiConnect URL
- `KANJI_VOCAB_MINER_KANJI_DECK__NAME` - Kanji deck name

Example:
```bash
KANJI_VOCAB_MINER_KANJI_DECK__NAME="My Kanji Deck" kanji-vocab-miner
```

## How It Works

1. **Kanji Source**: Queries your existing kanji deck in Anki to get characters you're studying
2. **Word Discovery**: Searches Jisho.org API for vocabulary containing each kanji
3. **Smart Filtering**: Sorts words by:
   - JLPT level (N5 first, most accessible)
   - Commonality (using Jisho's "common" tag)
   - Character length (shorter words first)
4. **Vocabulary Storage**: Adds selected words to a separate vocabulary deck with:
   - Word (in kanji/kana)
   - Reading (hiragana)
   - English meaning
   - JLPT level (when available)

The tool keeps kanji and vocabulary separate: your kanji deck remains untouched, while vocabulary accumulates in its own dedicated deck.

## Troubleshooting

### "Could not connect to AnkiConnect"

**Problem**: Anki is not running or AnkiConnect is not installed.

**Solutions:**
1. Make sure Anki Desktop is running (not just in the background)
2. Verify AnkiConnect is installed: Anki → Tools → Add-ons → Check for "AnkiConnect"
3. If missing, install it: Tools → Add-ons → Get Add-ons → Code `2055492159`
4. Restart Anki after installing AnkiConnect

### "Deck 'All in One Kanji' not found"

**Problem**: The expected kanji deck is not present in Anki.

**Solutions:**
1. Download the deck from [AnkiWeb](https://ankiweb.net/shared/info/1862058740)
2. Import it: File → Import → Select the `.apkg` file
3. If using a different kanji deck, create a config file with your deck name:
   ```toml
   [kanji_deck]
   name = "Your Deck Name"
   ```

### "Vocab deck or note type not found"

**Problem**: Setup has not been run yet.

**Solution:**
```bash
kanji-vocab-miner setup
```

This creates the vocabulary deck and note type automatically.

### Setup command fails partway through

**Problem**: AnkiConnect or Anki may have issues.

**Solutions:**
1. Restart Anki completely
2. Run setup again (it's safe to re-run)
3. Check Anki → Tools → Add-ons → AnkiConnect → Config for any custom settings
4. Try disabling other Anki add-ons temporarily

### No kanji returned when pressing 'n'

**Problem**: All kanji in your deck have been reviewed, or cards are not due yet.

**Solutions:**
1. Check your deck in Anki - are there cards available to study?
2. The tool queries cards that are due for review
3. You can manually enter a kanji (just type it) to search for words
4. Review some cards in Anki to make them due

### Words not appearing in Anki after commit

**Problem**: Commit may have failed silently.

**Solutions:**
1. Check Anki's "Japanese Vocabulary" deck for new cards
2. Sync your collection: File → Synchronize
3. Check that you actually selected words before pressing `c`
4. Look for error messages in the terminal output

## Development

See [CLAUDE.md](CLAUDE.md) for development setup and contribution guidelines.

Run tests:
```bash
uv run pytest
```

## License

MIT License - See LICENSE file for details.

## Credits

- [Jisho.org](https://jisho.org/) for the excellent Japanese dictionary API
- [AnkiConnect](https://foosoft.net/projects/anki-connect/) for making Anki automation possible
- [All in One Kanji](https://ankiweb.net/shared/info/1862058740) deck creators
