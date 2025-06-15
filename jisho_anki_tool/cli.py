import sys
from typing import List, Optional

import click

from jisho_anki_tool.anki import connect as ankiconnect

from jisho_anki_tool import card_processor, jisho, render
from jisho_anki_tool.utils import parse_integer_selection, is_kanji, is_kotoba
from jisho_anki_tool.anki.schemas import KanjiCard
from jisho_anki_tool.jisho import JishoWord

from jamdict import Jamdict
from jisho_anki_tool.render import console, info, success, error


# Initialize Jamdict for word lookups
jam = Jamdict()

def fetch_words_from_kanji(kanji: str) -> List[JishoWord]:
    """
    Fetch words containing the kanji from Jisho and display them in a rich table.

    Args:
        kanji: The kanji character to search for

    Returns:
        List of sorted words that were displayed to the user
    """

    # Fetch any words containing Kanji from Jisho
    words: List[JishoWord] = jisho.search_words_containing_kanji(kanji)
    if not words:
        click.echo("No words found containing this Kanji.")
        return []

    # Get list of already reviewed words from Anki
    reviewed_vocab = ankiconnect.get_reviewed_vocab()

    sorted_words = card_processor.sort_and_limit_words(words, kanji, 20)

    render.words_table(sorted_words, reviewed_vocab)

    return [w for w, _ in sorted_words]  # Return the displayed words


def fetch_word_from_word(word: str) -> Optional[JishoWord]:
    """ Fetch a single word using jamdict"""

    result = jam.lookup(word)
    entry = result.entries[0] if result.entries else None

    if entry:
        # Parse jamdict entry to JishoWord
        kanji = entry.kanji_forms[0].text
        kana = entry.kana_forms[0].text
        jplt = 0

        senses = entry[:3]
        glosses = ["; ".join([i.text for i in sense.gloss]) for sense in senses]
        pos = [sense.pos[0] for sense in senses]


        jisho_word = JishoWord(
            expression=kanji,
            kana=kana,
            jlpt=jplt,
            definitions=glosses,
            parts_of_speech=pos,
        )

        render.word(jisho_word)

        return jisho_word

    return None


def process_word_selection(
    displayed_words: List[JishoWord], pending_words: List[JishoWord], selection: str
) -> List[JishoWord]:
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
        selected_indices = parse_integer_selection(selection)
        newly_selected = []

        for idx in selected_indices:
            if 1 <= idx <= len(displayed_words):
                word = displayed_words[idx - 1]
                pending_words.append(word)
                newly_selected.append(word)
            else:
                click.echo(f"Invalid selection: {idx} - out of range.")

        if newly_selected:
            success(f"Added {len(newly_selected)} word(s) to pending list (total: {len(pending_words)})")
            for word in newly_selected:
                info(f"{word.expression} ({word.kana})")

    except ValueError:
        click.echo(
            "Invalid selection format. Please enter space-separated numbers (e.g., '1 3 5')."
        )

    return pending_words


def handle_next_card() -> Optional[str]:
    """Handle the 'n' command to fetch the next card from Anki."""
    with console.status("[bold]Fetching current Kanji from Anki…[/bold]", spinner="dots"):
        try:
            card: KanjiCard = ankiconnect.get_current_card()
        except Exception as e:
            error(f"AnkiConnect error: {e}")
            return None

    kanji = card.fields.Kanji.value
    if not kanji:
        error("No Kanji card is open in Anki.")
        return None

    info(f"[bold yellow]{kanji}[/bold yellow]")
    return kanji


def add_pending_words_to_anki(pending_words: List[JishoWord]) -> None:
    """Add pending words to Anki deck."""
    if not pending_words:
        info("No words to add.")
        return

    with console.status(f"[bold]Adding {len(pending_words)} words to Anki…[/bold]", spinner="bouncingBar"):
        ankiconnect.add_vocab_note_to_deck(pending_words)

    success(f"{len(pending_words)} words successfully added!")


def get_user_input(pending_count: int) -> str:
    """Get user input with a coloured Rich prompt."""
    pending = f"[yellow]({pending_count} pending)[/yellow] " if pending_count else ""
    # use console.input so Rich markup is rendered
    return console.input(f"{pending}[bold green]> [/bold green]")


@click.command()
def jisho_anki():
    """
    CLI tool to fetch Kanji cards from Anki, search for words on Jisho,
    and add selected words back to Anki.
    """

    render.welcome_message()

    displayed_words = []  # Store the last displayed word list
    pending_words = []  # Store selected words to add to Anki later

    while True:
        try:
            user_input = get_user_input(len(pending_words))

            # Fetch new card and display words
            if user_input.lower() == "n":
                kanji = handle_next_card()
                if kanji:
                    displayed_words = fetch_words_from_kanji(kanji)

            # Select words to add to pending list
            elif any(c.isdigit() for c in user_input):
                pending_words = process_word_selection(
                    displayed_words, pending_words, user_input
                )

            # Commit pending words to Anki
            elif user_input.lower() == "c":
                click.echo(f"Committing {len(pending_words)} pending words to Anki...")
                add_pending_words_to_anki(pending_words)
                pending_words.clear()  # I've known python for 5 years and have only just discovered this method!

            # Quit the program
            elif user_input.lower() == "q":
                confirm_add = click.confirm(
                    f"You have {len(pending_words)} words pending. Add them to Anki",
                    default=True,
                )
                if confirm_add:
                    add_pending_words_to_anki(pending_words)
                click.echo("Goodbye!")
                sys.exit(0)

            # You can also just enter a kanji directly
            elif is_kanji(user_input):
                with console.status(f"Searching for words containing [yellow2]{user_input}[/yellow2]…", spinner="dots"):
                    displayed_words = fetch_words_from_kanji(user_input)

            # Or look up a single word
            elif is_kotoba(user_input):
                with console.status(f"[bold]Looking up word {user_input}…[/bold]", spinner="dots"):
                    word = fetch_word_from_word(user_input)

                if word:
                    add_confirm = click.confirm(
                        f"Do you want to add {word.expression} ({word.kana}) to pending words?",
                        default=True,
                    )
                    if add_confirm:
                        pending_words.append(word)
                        success(f"Added [bold]{word.expression}[/bold] to pending words.")

                else:
                    render.error(f"Word '{user_input}' not found in JmDict.")


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
