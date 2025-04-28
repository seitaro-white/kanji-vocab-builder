import click
import os
import sys
from typing import List, Dict, Any, Optional, Tuple
from tabulate import tabulate
import time
from rich.console import Console
from rich.table import Table
from rich.text import Text

from jisho_anki_tool import anki_connect
from jisho_anki_tool import jisho_api
from jisho_anki_tool import card_processor
from jisho_anki_tool import utils
from jisho_anki_tool.utils import format_furigana


def display_welcome_message() -> None:
    """Display the welcome message when starting the tool."""
    click.echo("Welcome to the Jisho Anki Tool!")
    click.echo("This tool helps you find and add words containing the current Kanji in your Anki deck.")
    click.echo("Press 'n' to fetch the current card, select words by number, or 'q' to quit.")


def fetch_and_display_words(kanji: str) -> List[Dict[str, Any]]:
    """
    Fetch words containing the kanji from Jisho and display them in a rich table.

    Args:
        kanji: The kanji character to search for

    Returns:
        List of sorted words that were displayed to the user
    """
    click.echo(f"Current Kanji: {kanji}")
    click.echo("Searching for words on Jisho...")

    words = jisho_api.search_words(kanji)
    if not words:
        click.echo("No words found containing this Kanji.")
        return []

    click.echo("Sorting words by review status and JLPT level...")
    sorted_words = card_processor.sort_and_limit_words(words, kanji)

    # Create a rich table for display
    console = Console()
    table = Table(box=None, show_header=False)

    # Add columns (without headers)
    table.add_column("Index", style="yellow2")
    table.add_column("Word", style="chartreuse3")
    table.add_column("Reading", style="cornflower_blue")
    table.add_column("JLPT")
    table.add_column("Priority", style="magenta")
    table.add_column("Meaning", style="grey74")

    # JLPT level color mapping
    jlpt_colors = {
        5: "#209c05",
        4: "#85e62c",
        3: "#ebff0a",
        2: "#f2ce02",
        1: "#ff0a0a"
    }

    # Add rows for each word
    for i, word in enumerate(sorted_words, 1):
        jlpt_level = word.get('jlpt')

        # Create styled JLPT text
        if jlpt_level:
            jlpt_text = Text(f"N{jlpt_level}")
            jlpt_text.stylize(jlpt_colors.get(jlpt_level, "white"))
        else:
            jlpt_text = Text("Common", style="white")

        # Create styled priority text - red for "N" (not reviewed), green for "R" (reviewed)
        if word.get('priority'):
            priority_text = Text("R", style="green")
        else:
            priority_text = Text("N", style="red")

        table.add_row(
            str(i) + ".",                # Index
            word.get('word', ''),        # Word
            word.get('reading', ''),     # Reading
            jlpt_text,                   # JLPT level with specific color
            priority_text,               # Priority with color (green for R, red for N)
            word.get('meaning', '')      # Meaning
        )

    # Display the table
    click.echo("\nFound words (sorted by reviewed Kanji and JLPT level):")
    console.print(table)

    # Add a separator line after the table for better visual distinction
    console.print("─" * 80, style="dim")

    return sorted_words


def process_word_selection(displayed_words: List[Dict[str, Any]],
                           pending_words: List[Dict[str, Any]],
                           selection: str) -> List[Dict[str, Any]]:
    """
    Process user selection of words to add to the pending list.

    Args:
        displayed_words: The list of words currently displayed
        pending_words: Current list of pending words
        selection: The user's selection input

    Returns:
        Updated list of pending words
    """
    if not displayed_words:
        click.echo("No words have been displayed yet. Press 'n' to fetch words first.")
        return pending_words

    try:
        selected_indices = utils.parse_selection(selection)
        newly_selected = []

        for idx in selected_indices:
            if 1 <= idx <= len(displayed_words):
                word = displayed_words[idx - 1]
                pending_words.append(word)
                newly_selected.append(word)
            else:
                click.echo(f"Invalid selection: {idx} - out of range.")

        if newly_selected:
            click.echo(f"Added {len(newly_selected)} words to pending list. Total: {len(pending_words)}")
            for word in newly_selected:
                click.echo(f"  - {word.get('word')} ({word.get('reading')})")

    except ValueError:
        click.echo("Invalid selection format. Please enter space-separated numbers (e.g., '1 3 5').")

    return pending_words


def add_pending_words_to_anki(pending_words: List[Dict[str, Any]]) -> None:
    """
    Add pending words to Anki deck.

    Args:
        pending_words: List of words to add to Anki
    """
    if not pending_words:
        return

    should_add = click.confirm(f"You have {len(pending_words)} words pending. Add them to Anki before quitting?", default=True)
    if should_add:
        click.echo(f"Adding {len(pending_words)} words to Anki...")
        anki_connect.add_words_to_deck(pending_words)
        click.echo("Words successfully added to Anki!")


def handle_next_card() -> Optional[str]:
    """
    Handle the 'n' command to fetch the next card from Anki.

    Returns:
        The kanji from the current card, or None if there was an error
    """
    click.echo("Fetching current Kanji from Anki...")
    try:
        kanji = anki_connect.get_current_card()
        if not kanji:
            click.echo("No Kanji card is currently displayed in Anki. Please open a card.")
            return None
        return kanji
    except Exception as e:
        click.echo(f"Error: {str(e)}")
        return None


def get_user_input(pending_count: int) -> str:
    """
    Get user input with context about pending words.

    Args:
        pending_count: Number of pending words

    Returns:
        User input string
    """
    pending_msg = f" ({pending_count} words pending)" if pending_count else ""
    return click.prompt(f"\nEnter 'n' for next card, integers to select words, or 'q' to quit{pending_msg}")


def get_user_selection(max_num: int) -> List[int]:
    """
    Get user selection of word indices.

    Args:
        max_num: Maximum number that can be selected

    Returns:
        List of selected indices (1-based)
    """
    while True:
        selection = click.prompt("Enter numbers to select words (e.g., '1 3 5') or '0' to skip",
                                default="", show_default=False)

        # Skip if user enters 0
        if selection.strip() == "0":
            return []

        try:
            # Parse the input as a list of integers
            selected_indices = [int(s) for s in selection.split() if s.strip()]

            # Validate the indices
            if all(1 <= idx <= max_num for idx in selected_indices):
                return selected_indices
            else:
                click.echo(f"Please enter valid numbers between 1 and {max_num}.")
        except ValueError:
            click.echo("Invalid input. Please enter space-separated numbers.")


def process_kanji(kanji: str) -> List[Dict[str, Any]]:
    """
    Process a single kanji: search for words, display them, get user selection.

    Args:
        kanji: The kanji character to process

    Returns:
        List of selected words
    """
    click.echo(f"\nProcessing kanji: {kanji}")

    # Search for words containing the kanji and display them
    displayed_words = fetch_and_display_words(kanji)

    if not displayed_words:
        click.echo(f"No words found for kanji {kanji}")
        return []

    # Get user selection
    selected_indices = get_user_selection(len(displayed_words))

    if not selected_indices:
        click.echo("No words selected. Skipping...")
        return []

    # Return the selected words
    return [displayed_words[idx - 1] for idx in selected_indices]


@click.group()
def cli():
    """Jisho Anki Tool - Add vocabulary words to Anki based on Kanji cards."""
    pass

@cli.command('add_during')
def add_during():
    """Add vocabulary words for the current Kanji card during review."""
    try:
        display_welcome_message()

        # Main interactive loop
        pending_words = []
        displayed_words = []
        current_kanji = None

        while True:
            command = get_user_input(len(pending_words))

            if command.lower() == 'q':
                add_pending_words_to_anki(pending_words)
                break

            elif command.lower() == 'n':
                card = anki_connect.get_current_card()

                if not card:
                    click.echo("No card is currently being reviewed. Please open Anki and start reviewing.")
                    continue

                # TODO: Ths is fucked currently
                fields = card.get("fields", {})
                front_field = next((f for f in fields.keys() if "front" in f.lower()), None)

                if not front_field or not fields[front_field].get("value"):
                    click.echo("Could not find a front field with Kanji.")
                    continue

                # Get the kanji from the front field (assuming it's the first character)
                kanji_value = fields[front_field]["value"]
                if not kanji_value:
                    click.echo("The current card doesn't have any Kanji.")
                    continue

                # Take the first character as the Kanji
                current_kanji = kanji_value[0]

                # Fetch and display words for this kanji
                displayed_words = fetch_and_display_words(current_kanji)

            else:
                # Process numeric selection
                pending_words = process_word_selection(displayed_words, pending_words, command)

    except Exception as e:
        click.echo(f"Error: {str(e)}")
    except KeyboardInterrupt:
        click.echo("\nOperation interrupted. Exiting...")
        add_pending_words_to_anki(pending_words)


@cli.command('add_prepare')
@click.option('--source-deck', '-s', default="All in one Kanji",
              help="Source deck containing Kanji cards")
@click.option('--target-deck', '-d', default="VocabularyNew",
              help="Target deck for new vocabulary cards")
def add_prepare(source_deck: str, target_deck: str):
    """Add vocabulary words for all new due Kanji cards."""
    try:
        # Get all due cards from the source deck
        click.echo(f"Fetching due cards from deck: {source_deck}")
        due_cards = anki_connect.get_due_cards(source_deck)

        if not due_cards:
            click.echo("No new cards due for review.")
            return

        # Extract kanji from the cards
        kanji_list = anki_connect.extract_kanji_from_cards(due_cards)

        if not kanji_list:
            click.echo("No Kanji found in the due cards.")
            return

        click.echo(f"Found {len(kanji_list)} Kanji to process: {', '.join(kanji_list)}")

        # Process each kanji and collect selected words
        all_selected_words = []

        for i, kanji in enumerate(kanji_list, 1):
            click.echo(f"\n[{i}/{len(kanji_list)}]")
            selected_words = process_kanji(kanji)
            all_selected_words.extend(selected_words)

            # If not the last kanji, ask if user wants to continue
            if i < len(kanji_list):
                click.echo("\nPress Enter to continue to the next kanji or Ctrl+C to exit...")
                try:
                    input()
                except KeyboardInterrupt:
                    click.echo("\nExiting early...")
                    break

        # Add all selected words to Anki
        if all_selected_words:
            click.echo(f"\nAdding {len(all_selected_words)} words to Anki...")
            anki_connect.add_words_to_deck(all_selected_words)
            click.echo("Words successfully added to Anki!")
        else:
            click.echo("\nNo words were selected.")

        click.echo("\nProcessing complete!")

    except Exception as e:
        click.echo(f"Error: {str(e)}")
    except KeyboardInterrupt:
        click.echo("\nOperation interrupted. Exiting...")


if __name__ == '__main__':
    cli()
