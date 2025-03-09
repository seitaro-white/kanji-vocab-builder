import click
import sys
from typing import List, Optional

# Updated imports
from jisho_anki_tool import anki_connect
from jisho_anki_tool import jisho_api
from jisho_anki_tool import card_processor
from jisho_anki_tool import utils

@click.command()
def jisho_anki():
    """
    CLI tool to fetch Kanji cards from Anki, search for words on Jisho,
    and add selected words back to Anki.
    """
    click.echo("Welcome to the Jisho Anki Tool!")
    click.echo("This tool helps you find and add words containing the current Kanji in your Anki deck.")
    click.echo("Press 'n' to fetch the current card, select words by number, or 'q' to quit.")

    displayed_words = []  # Store the last displayed word list

    while True:
        try:
            user_input = click.prompt("\nEnter 'n' for next card, integers to select words, or 'q' to quit")

            # Quit the program
            if user_input.lower() == 'q':
                click.echo("Goodbye!")
                sys.exit(0)

            # Fetch new card and display words
            elif user_input.lower() == 'n':
                click.echo("Fetching current Kanji from Anki...")
                try:
                    kanji = anki_connect.get_current_card()
                    if not kanji:
                        click.echo("No Kanji card is currently displayed in Anki. Please open a card.")
                        continue

                    click.echo(f"Current Kanji: {kanji}")
                    click.echo("Searching for words on Jisho...")

                    words = jisho_api.search_words(kanji)
                    if not words:
                        click.echo("No words found containing this Kanji.")
                        continue

                    click.echo("Sorting words by review status and JLPT level...")
                    sorted_words = card_processor.sort_and_limit_words(words, kanji)

                    # Display words with index
                    click.echo("\nFound words (sorted by reviewed Kanji and JLPT level):")
                    for i, word in enumerate(sorted_words, 1):
                        jlpt = f"(N{word.get('jlpt', 'Common')})" if word.get('jlpt') else "(Common)"
                        click.echo(f"{i}. {word.get('word')} - {word.get('reading')} {jlpt} - {word.get('meaning')}")

                    displayed_words = sorted_words

                except Exception as e:
                    click.echo(f"Error: {str(e)}")

            # Select words to add
            elif any(c.isdigit() for c in user_input):
                if not displayed_words:
                    click.echo("No words have been displayed yet. Press 'n' to fetch words first.")
                    continue

                try:
                    selected_indices = utils.parse_selection(user_input)
                    selected_words = []

                    for idx in selected_indices:
                        if 1 <= idx <= len(displayed_words):
                            selected_words.append(displayed_words[idx - 1])
                        else:
                            click.echo(f"Invalid selection: {idx} - out of range.")

                    if selected_words:
                        click.echo(f"Adding {len(selected_words)} words to Anki...")
                        result = anki_connect.add_words_to_deck(selected_words)
                        click.echo("Words successfully added to Anki!")

                except ValueError:
                    click.echo("Invalid selection format. Please enter space-separated numbers (e.g., '1 3 5').")

            else:
                click.echo("Invalid input. Enter 'n', numbers, or 'q'.")

        except KeyboardInterrupt:
            click.echo("\nOperation cancelled.")
            sys.exit(0)

        except Exception as e:
            click.echo(f"An unexpected error occurred: {str(e)}")


if __name__ == "__main__":
    jisho_anki()
