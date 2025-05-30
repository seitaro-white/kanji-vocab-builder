import click
import sys
from typing import List, Dict, Any, Optional, Tuple
from rich.console import Console
from rich.table import Table
from rich.text import Text

from jisho_anki_tool.anki import connect
from jisho_anki_tool import jisho
from jisho_anki_tool.jisho import JishoWord
from jisho_anki_tool import card_processor
from jisho_anki_tool import utils
from jisho_anki_tool.anki.schemas import KanjiCard


def display_welcome_message() -> None:
    """Display the welcome message when starting the tool."""
    click.echo("Welcome to the Jisho Anki Tool!")
    click.echo("This tool helps you find and add words containing the current Kanji in your Anki deck.")


def fetch_and_display_words(kanji: str) -> List[JishoWord]:
    """
    Fetch words containing the kanji from Jisho and display them in a rich table.

    Args:
        kanji: The kanji character to search for

    Returns:
        List of sorted words that were displayed to the user
    """
    click.echo(f"Current Kanji: {kanji}")
    click.echo("Searching for words on Jisho...")


    words: List[JishoWord] = jisho.search_words_containing_kanji(kanji)
    if not words:
        click.echo("No words found containing this Kanji.")
        return []

    click.echo("Sorting words by review status and JLPT level...")
    sorted_words = card_processor.sort_and_limit_words(words, kanji, 10)

    # Create a rich table for display
    console = Console()
    table = Table(box=None, show_header=False)

    # Add columns (without headers)
    table.add_column("Index", style="yellow2")
    table.add_column("Word", style="chartreuse3")
    table.add_column("Reading", style="cornflower_blue")
    table.add_column("JLPT")
    table.add_column("Priority", style="magenta")
    table.add_column("Already in Deck", style="light_slate_grey")
    table.add_column("Definition", style="grey74")

    # JLPT level color mapping
    jlpt_colors = {
        5: "#209c05",
        4: "#85e62c",
        3: "#ebff0a",
        2: "#f2ce02",
        1: "#ff0a0a",
        0: "#c3c4c7",
    }

    # Add rows for each word
    for ct, (word, priority) in enumerate(sorted_words, 1):

        if word.jlpt:
            jlpt_text = Text(f"N{word.jlpt}")
            jlpt_text.stylize(jlpt_colors.get(word.jlpt, "#c3c4c7"))  # Default color for unknown levels
        else:
            jlpt_text = ""

        # Create styled priority text - red for "N" (not reviewed), green for "R" (reviewed)
        if priority:
            priority_text = Text("R", style="green")
        else:
            priority_text = Text("N", style="red")

        # Check if the word itself is already in our reviewed vocabulary
        reviewed_vocabulary = connect.get_reviewed_vocab()
        if word.expression in reviewed_vocabulary:
            reviewed_text = Text("Y", style="grey37")
        else:
            reviewed_text = Text("N", style="medium_violet_red")


        table.add_row(
            str(ct) + ".",                # Index
            word.expression,        # Word
            word.kana,     # Reading
            jlpt_text,                   # JLPT level with specific color
            priority_text,
            reviewed_text,               # Whether the other Kanji has been reviewed at some point
            word.definitions[0]     # Meaning
        )

    # Display the table
    click.echo("\nFound words (sorted by reviewed Kanji and JLPT level):")
    console.print(table)

    # Add a separator line after the table for better visual distinction
    console.print("─" * 80, style="dim")

    return [word for word, _ in sorted_words]  # Return the displayed words


def process_word_selection(displayed_words: List[JishoWord],
                           pending_words: List[JishoWord],
                           selection: str) -> List[JishoWord]:
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
                click.echo(f"  - {word.expression} ({word.kana})")

    except ValueError:
        click.echo("Invalid selection format. Please enter space-separated numbers (e.g., '1 3 5').")

    return pending_words


def add_pending_words_to_anki(pending_words: List[JishoWord]) -> None:
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
        connect.add_vocab_note_to_deck(pending_words)
        click.echo("Words successfully added to Anki!")


def handle_next_card() -> Optional[str]:
    """
    Handle the 'n' command to fetch the next card from Anki.

    Returns:
        The kanji from the current card, or None if there was an error
    """
    click.echo("Fetching current Kanji from Anki...")
    try:
        card: KanjiCard = connect.get_current_card()
        kanji = card.fields.Kanji.value
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
    return click.prompt(f"\nPress 'n' to fetch the current card, input a kanji directly, or 'q' to quit.{pending_msg}")


@click.command()
def jisho_anki():
    """
    CLI tool to fetch Kanji cards from Anki, search for words on Jisho,
    and add selected words back to Anki.
    """
    display_welcome_message()

    displayed_words = []  # Store the last displayed word list
    pending_words = []    # Store selected words to add to Anki later

    while True:
        try:
            user_input = get_user_input(len(pending_words))

            # Fetch new card and display words
            if user_input.lower() == 'n':
                kanji = handle_next_card()
                if kanji:
                    displayed_words = fetch_and_display_words(kanji)

            # Select words to add to pending list
            elif any(c.isdigit() for c in user_input):
                pending_words = process_word_selection(displayed_words, pending_words, user_input)

            # Quit the program
            elif user_input.lower() == 'q':
                add_pending_words_to_anki(pending_words)
                click.echo("Goodbye!")
                sys.exit(0)

            # You can also just enter a kanji directly
            elif connect.is_kanji(user_input):
                kanji = user_input
                displayed_words = fetch_and_display_words(kanji)


            else:
                click.echo("Invalid input. Enter 'n', numbers, or 'q'.")

        except KeyboardInterrupt:
            click.echo("\nOperation cancelled.")
            add_pending_words_to_anki(pending_words)
            sys.exit(0)

        except Exception as e:
            click.echo(f"An unexpected error occurred: {str(e)}")


if __name__ == "__main__":
    jisho_anki()
