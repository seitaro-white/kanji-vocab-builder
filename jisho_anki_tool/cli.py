import sys
from typing import List, Optional

import click

from jisho_anki_tool.anki import connect as ankiconnect

from jisho_anki_tool import card_processor, jisho, render
from jisho_anki_tool.utils import parse_integer_selection, is_kanji, is_kotoba
from jisho_anki_tool.anki.schemas import KanjiCard
from jisho_anki_tool.jisho import JishoWord

from jamdict import Jamdict


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

    #　
    click.echo("Sorting words by review status and JLPT level...")
    sorted_words = card_processor.sort_and_limit_words(words, kanji, 20)

    render.words_table(sorted_words, reviewed_vocab)

    return [w for w, _ in sorted_words]  # Return the displayed words

def fetch_word_from_word(word: str) -> str:
    """ Fetch a single word using jamdict"""

    result = jam.lookup(word)
    entry = result.entries[0] if result.entries else None

    if entry:
        # Parse jamdict entry to JishoWord
        kanji = entry.kanji_forms[0].text
        kana = entry.kana_forms[0].text
        jplt = 0

        senses = entry[:3]
        glosses = [sense.gloss[0].text for sense in senses]
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
            click.echo(
                f"Added {len(newly_selected)} words to pending list. Total: {len(pending_words)}"
            )
            for word in newly_selected:
                click.echo(f"  - {word.expression} ({word.kana})")

    except ValueError:
        click.echo(
            "Invalid selection format. Please enter space-separated numbers (e.g., '1 3 5')."
        )

    return pending_words


def add_pending_words_to_anki(pending_words: List[JishoWord]) -> None:
    """
    Add pending words to Anki deck.

    Args:
        pending_words: List of words to add to Anki
    """
    if not pending_words:
        return

    click.echo(f"Adding {len(pending_words)} words to Anki...")
    ankiconnect.add_vocab_note_to_deck(pending_words)
    click.echo("Words successfully added to Anki!")


def handle_next_card() -> Optional[str]:
    """
    Handle the 'n' command to fetch the next card from Anki.

    Returns:
        The kanji from the current card, or None if there was an error
    """
    click.echo("Fetching current Kanji from Anki...")
    try:
        card: KanjiCard = ankiconnect.get_current_card()
        kanji = card.fields.Kanji.value
        if not kanji:
            click.echo(
                "No Kanji card is currently displayed in Anki. Please open a card."
            )
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
    return click.prompt(
        f"\nPress 'n' to fetch the current card, input a kanji directly, c to commit pending words or 'q' to quit.{pending_msg}"
    )


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
                click.echo(f"Current Kanji: {kanji}\nSearching for words on Jisho...")

                displayed_words = fetch_words_from_kanji(user_input)

            # Or look up a single word
            elif is_kotoba(user_input):
                click.echo(f"Looking up word: {user_input}")
                word = fetch_word_from_word(user_input)
                add_confirm = click.confirm(
                    f"Do you want to add {word.expression} ({word.kana}) to pending words?",
                    default=True,
                )
                if add_confirm:
                    pending_words.append(word)
                    click.echo(f"Added {word.expression} to pending words.")




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
