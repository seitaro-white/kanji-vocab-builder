"""Setup wizard for initializing Anki decks and note types."""

from typing import Tuple, List

from kanji_vocab_miner.anki import connect
from kanji_vocab_miner.config import VOCAB_DECK_NAME, VOCAB_NOTE_TYPE, FIELDS, load_config
from kanji_vocab_miner.render import console


def validate_prerequisites() -> Tuple[bool, List[str]]:
    """Validate all prerequisites for running kanji-vocab-miner.

    Checks:
    1. AnkiConnect connectivity
    2. Vocabulary deck exists
    3. Note type exists
    4. "All In One Kanji" deck exists

    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    config = load_config()
    kanji_deck_name = config.kanji_deck.name

    # 1. Check AnkiConnect connectivity
    try:
        connect.send_request("version")
    except Exception as e:
        errors.append(
            "[red]✗ Cannot connect to AnkiConnect[/red]\n"
            "  Please ensure:\n"
            "  1. Anki is running\n"
            "  2. AnkiConnect plugin is installed\n"
            "     Download: https://ankiweb.net/shared/info/2055492159"
        )
        return False, errors  # Can't check anything else without connectivity

    # 2. Check vocabulary deck exists
    try:
        deck_names = connect.send_request("deckNames")
        if VOCAB_DECK_NAME not in deck_names:
            errors.append(
                f"[red]✗ Vocabulary deck '{VOCAB_DECK_NAME}' not found[/red]\n"
                f"  Run: [bold cyan]kanji-vocab-miner setup[/bold cyan] to create it"
            )
    except Exception:
        errors.append("[red]✗ Failed to check for vocabulary deck[/red]")

    # 3. Check note type exists
    try:
        model_names = connect.send_request("modelNames")
        if VOCAB_NOTE_TYPE not in model_names:
            errors.append(
                f"[red]✗ Note type '{VOCAB_NOTE_TYPE}' not found[/red]\n"
                f"  Run: [bold cyan]kanji-vocab-miner setup[/bold cyan] to create it"
            )
    except Exception:
        errors.append("[red]✗ Failed to check for note type[/red]")

    # 4. Check "All In One Kanji" deck exists
    try:
        deck_names = connect.send_request("deckNames")
        if kanji_deck_name not in deck_names:
            errors.append(
                f"[red]✗ Kanji deck '{kanji_deck_name}' not found[/red]\n"
                f"  This deck is required for the tool to work.\n"
                f"  Download from: https://ankiweb.net/shared/info/1862058740\n"
                f"  Or configure a different kanji deck in: ~/.config/kanji-vocab-miner/config.toml"
            )
    except Exception:
        errors.append("[red]✗ Failed to check for kanji deck[/red]")

    return len(errors) == 0, errors


def run_setup():
    """Create vocab deck and note type in Anki.

    This function:
    1. Tests AnkiConnect connectivity
    2. Creates the vocabulary deck (idempotent)
    3. Creates the note type with required fields (idempotent)

    Returns:
        bool: True if setup completed successfully, False otherwise
    """
    console.print("[bold]Kanji Vocab Miner Setup[/bold]\n")

    # 1. Test AnkiConnect
    console.print("[cyan]Testing AnkiConnect connection...[/cyan]")
    try:
        version = connect.send_request("version")
        console.print(f"[green]✓[/green] AnkiConnect is running (version {version})\n")
    except Exception as e:
        console.print(f"[red]✗ Cannot connect to AnkiConnect: {e}[/red]")
        console.print(
            "\n[yellow]Please ensure:[/yellow]\n"
            "  1. Anki is running\n"
            "  2. AnkiConnect plugin is installed\n"
            "  3. AnkiConnect is listening on http://localhost:8765"
        )
        return False

    # 2. Create vocab deck
    console.print(f"[cyan]Creating deck: {VOCAB_DECK_NAME}...[/cyan]")
    try:
        connect.send_request("createDeck", deck=VOCAB_DECK_NAME)
        console.print(f"[green]✓[/green] Deck '{VOCAB_DECK_NAME}' created\n")
    except Exception as e:
        error_msg = str(e).lower()
        if "already exists" in error_msg or "deck was not created" in error_msg:
            console.print(
                f"[yellow]→[/yellow] Deck '{VOCAB_DECK_NAME}' already exists\n"
            )
        else:
            console.print(f"[red]✗ Failed to create deck: {e}[/red]")
            return False

    # 3. Create note type
    console.print(f"[cyan]Creating note type: {VOCAB_NOTE_TYPE}...[/cyan]")
    try:
        create_note_type()
        console.print(f"[green]✓[/green] Note type '{VOCAB_NOTE_TYPE}' created\n")
    except Exception as e:
        error_msg = str(e).lower()
        if "already exists" in error_msg or "model name already exists" in error_msg:
            console.print(
                f"[yellow]→[/yellow] Note type '{VOCAB_NOTE_TYPE}' already exists\n"
            )
        else:
            console.print(f"[red]✗ Failed to create note type: {e}[/red]")
            return False

    # Success - check if kanji deck exists and provide appropriate message
    config = load_config()
    kanji_deck_name = config.kanji_deck.name

    try:
        deck_names = connect.send_request("deckNames")
        kanji_deck_exists = kanji_deck_name in deck_names
    except Exception:
        kanji_deck_exists = False

    console.print("[bold green]Setup complete![/bold green]\n")

    if not kanji_deck_exists:
        console.print(
            "[yellow]⚠ Important:[/yellow] You also need the kanji deck to use this tool.\n"
            f"  The tool expects: [bold]{kanji_deck_name}[/bold]\n"
            "  Download from: https://ankiweb.net/shared/info/1862058740\n"
            "  Import it into Anki before running [bold cyan]kanji-vocab-miner[/bold cyan]\n"
        )
    else:
        console.print(
            "You can now run [bold cyan]kanji-vocab-miner[/bold cyan] to start using the tool.\n"
        )

    return True


def create_note_type():
    """Create the vocabulary note type via AnkiConnect.

    Creates a note type with:
    - All required fields from FIELDS constant
    - Basic card template (Front → Back)
    - Simple CSS styling

    Raises:
        Exception: If note type creation fails
    """
    # Define card template
    card_template = {
        "Name": "Card 1",
        "Front": "{{Front}}",
        "Back": "{{FrontSide}}\n\n<hr id=answer>\n\n{{Back}}",
    }

    # Define CSS styling
    css = """
.card {
    font-family: "Hiragino Kaku Gothic Pro", "Meiryo", "MS PGothic", sans-serif;
    font-size: 24px;
    text-align: center;
    color: black;
    background-color: white;
}

.front {
    font-size: 32px;
    margin-bottom: 10px;
}

.back {
    font-size: 20px;
    color: #333;
}
"""

    # Create model configuration
    model_config = {
        "modelName": VOCAB_NOTE_TYPE,
        "inOrderFields": list(FIELDS.values()),
        "css": css,
        "cardTemplates": [card_template],
    }

    # Create the note type
    connect.send_request("createModel", **model_config)
