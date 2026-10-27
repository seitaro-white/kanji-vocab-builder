"""Setup wizard for initializing Anki decks and note types."""

from typing import List, Tuple

from kanji_vocab_miner.anki import connect, model_setup
from kanji_vocab_miner.anki.note_types import VOCAB_DECK_NAME, VOCAB_NOTE_TYPE_V3
from kanji_vocab_miner.config import (
    load_config,
    provision_default_prompt,
)
from kanji_vocab_miner.render import console


def validate_prerequisites() -> Tuple[bool, List[str]]:
    """Check connectivity, required decks and the current V3 note type.

    Settings are loaded fresh. Connectivity failure prevents later service
    checks; deck and model failures otherwise accumulate actionable messages.

    Returns:
        A pair of (is_valid, error_messages). is_valid is True only when every
        check succeeds; messages use Rich markup for presentation by the caller.
    """
    errors = []
    config = load_config()
    kanji_deck_name = config.kanji_deck.name

    # 1. Check AnkiConnect connectivity
    try:
        connect.send_request("version")
    except Exception:
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
        if VOCAB_NOTE_TYPE_V3 not in model_names:
            errors.append(
                f"[red]✗ Note type '{VOCAB_NOTE_TYPE_V3}' not found[/red]\n"
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


def run_setup() -> bool:
    """Run the setup wizard without modifying legacy or V2 vocabulary models.

    Provision the enrichment prompt without overwriting existing content, create
    the vocabulary deck if needed, and create or safely refresh V3. Reusable
    model operations validate field order before refreshing templates and CSS.
    All activity and failure messages are presented through the console.

    Returns:
        True when deck and V3 setup succeed, or False after a provisioning or
        service failure. A missing kanji deck produces guidance, not failure.
    """
    console.print("[bold]Kanji Vocab Miner Setup[/bold]\n")

    config = load_config()
    try:
        provision_default_prompt(config.llm.prompt_path)
    except OSError as error:
        console.print(f"[red]✗ Failed to provision enrichment prompt: {error}[/red]")
        return False

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

    # 3. Create or safely refresh the V3 model.
    try:
        model_names = connect.send_request("modelNames")
    except Exception as e:
        console.print(f"[red]✗ Failed to inspect note types: {e}[/red]")
        return False

    console.print(f"[cyan]Configuring note type: {VOCAB_NOTE_TYPE_V3}...[/cyan]")
    try:
        if VOCAB_NOTE_TYPE_V3 in model_names:
            model_setup.update_note_type_v3()
            console.print("[green]✓[/green] V3 templates and CSS updated\n")
        else:
            model_setup.create_note_type_v3()
            console.print(
                f"[green]✓[/green] Note type '{VOCAB_NOTE_TYPE_V3}' created\n"
            )
    except Exception as e:
        console.print(f"[red]✗ Failed to configure V3 note type: {e}[/red]")
        return False

    # Success - check if kanji deck exists and provide appropriate message
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
