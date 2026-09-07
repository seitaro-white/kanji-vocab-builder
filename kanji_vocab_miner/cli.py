import sys
import unicodedata
from typing import List, Optional

import click
from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.formatted_text import HTML

from kanji_vocab_miner.anki import connect as ankiconnect

from kanji_vocab_miner import (
    card_processor,
    frequency,
    jisho,
    jlpt,
    known_words,
    manual_progress,
    progress,
    render,
    review,
)
from kanji_vocab_miner.utils import parse_integer_selection, is_kanji, is_kotoba
from kanji_vocab_miner.anki.schemas import KanjiCard
from kanji_vocab_miner.jisho import JishoWord
from kanji_vocab_miner.review_status import KanjiReviewStatus
from kanji_vocab_miner.vocab_models import BatchAddResult, PendingVocabItem

from jamdict import Jamdict
from kanji_vocab_miner.render import console, info, success, error


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

    kanji_summary = jisho.fetch_kanji_summary(kanji)

    try:
        review_status = ankiconnect.get_kanji_review_status(kanji)
    except Exception as e:
        review_status = KanjiReviewStatus.UNKNOWN
        console.print(
            f"Warning: Could not retrieve Anki review status: {e}",
            style="yellow",
            markup=False,
        )

    if kanji_summary:
        render.kanji_summary(kanji_summary, review_status)

    words: List[JishoWord] = jisho.search_words_containing_kanji(kanji)
    if not words:
        click.echo("No words found containing this Kanji.")
        return []

    # Get list of already reviewed words from Anki
    reviewed_vocab = ankiconnect.get_reviewed_vocab()

    sorted_words = card_processor.sort_and_limit_words(words, kanji, 20)

    render.words_table(sorted_words, reviewed_vocab, frequency.get_frequency_index())

    return [w for w, _ in sorted_words]  # Return the displayed words


def fetch_word_from_word(word: str) -> Optional[JishoWord]:
    """ Fetch a single word using jamdict"""

    result = jam.lookup(word)
    entry = result.entries[0] if result.entries else None

    if entry:
        # Parse jamdict entry to JishoWord
        kanji = entry.kanji_forms[0].text
        kana = entry.kana_forms[0].text
        level_index = jlpt.get_level_index()
        jplt = level_index.get(kanji) or level_index.get(kana) or 0

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

        render.word(jisho_word, frequency.get_frequency_index())

        return jisho_word

    return None


def process_word_selection(
    displayed_words: List[JishoWord],
    pending_items: List[PendingVocabItem],
    selection: str,
) -> List[PendingVocabItem]:
    """Add selected expressions to pending state without duplicates.

    Args:
        displayed_words: Words currently available by numeric position.
        pending_items: Existing pending state and recall preferences.
        selection: Space-separated indexes or ranges supplied by the user.

    Returns:
        The pending items with newly selected unique expressions appended.
    """
    if not displayed_words:
        click.echo("No words have been displayed yet. Press 'n' to fetch words first.")
        return pending_items

    try:
        selected_indices = parse_integer_selection(selection)
        newly_selected: List[PendingVocabItem] = []
        pending_expressions = {item.word.expression for item in pending_items}

        for index in selected_indices:
            if not 1 <= index <= len(displayed_words):
                click.echo(f"Invalid selection: {index} - out of range.")
                continue

            word = displayed_words[index - 1]
            if word.expression in pending_expressions:
                continue
            item = PendingVocabItem(word=word)
            pending_items.append(item)
            newly_selected.append(item)
            pending_expressions.add(word.expression)

        if newly_selected:
            success(
                f"Added {len(newly_selected)} word(s) to pending list "
                f"(total: {len(pending_items)})"
            )
            for item in newly_selected:
                info(f"{item.word.expression} ({item.word.kana})")

    except ValueError:
        click.echo(
            "Invalid selection format. Please enter space-separated numbers (e.g., '1 3 5')."
        )

    return pending_items


def handle_next_card() -> Optional[str]:
    """Handle the 'n' command to fetch the next card from Anki."""
    with console.status("[bold]Fetching current Kanji from Anki…[/bold]", spinner="dots"):
        try:
            card: Optional[KanjiCard] = ankiconnect.get_current_card()
        except Exception as e:
            error(f"AnkiConnect error: {e}")
            return None

    if card is None:
        error("No Kanji card is open in Anki.")
        return None

    kanji = card.fields.Kanji.value
    if not kanji:
        error("No Kanji card is open in Anki.")
        return None

    info(f"[bold yellow]{kanji}[/bold yellow]")
    return kanji


def add_pending_words_to_anki(
    pending_items: List[PendingVocabItem],
) -> BatchAddResult:
    """Commit included pending items and return their actual outcomes."""
    with console.status(
        f"[bold]Adding {len(pending_items)} words to Anki…[/bold]",
        spinner="bouncingBar",
    ):
        return ankiconnect.add_vocab_items(pending_items)


def handle_review_and_commit(
    pending_items: List[PendingVocabItem], is_quitting: bool
) -> tuple[List[PendingVocabItem], bool]:
    """Review pending choices, commit included rows, and retain failures.

    Aborted reviews preserve all edited choices. Confirmed Add-off rows are
    discarded, while successful and duplicate rows leave pending state. Failed
    rows retain Recall and receive their failure message for a later retry.

    Args:
        pending_items: Current pending vocabulary and commit preferences.
        is_quitting: Whether the quit command opened this review.

    Returns:
        Updated pending state and whether the interactive loop should continue.
    """
    review_result = review.review_pending_words(pending_items)
    if not review_result.submitted:
        return review_result.items, True

    included_items = [
        item for item in review_result.items if item.add_enabled
    ]
    if not included_items:
        info("No words selected to commit.")
        return [], not is_quitting

    batch_result = add_pending_words_to_anki(included_items)
    failed_items: List[PendingVocabItem] = []
    for failure in batch_result.failed:
        failure.item.last_error = failure.message
        failed_items.append(failure.item)
        error(
            f"{failure.item.word.expression}: {failure.stage} failed — "
            f"{failure.message}"
        )

    success(
        f"Added {len(batch_result.added)}; already existed "
        f"{len(batch_result.skipped_duplicates)}; failed "
        f"{len(batch_result.failed)}."
    )
    if failed_items:
        info(
            "Failed words remain pending. Review again to retry, disable Add to "
            "discard, or abort to return to the command loop."
        )
    should_continue = bool(failed_items) or not is_quitting
    return failed_items, should_continue


def normalized_input(prompt: str) -> str:
    """Read a line and normalize full-width ASCII to half-width."""
    return unicodedata.normalize("NFKC", pt_prompt(prompt))


def normalized_confirm(prompt: str, default: bool = False) -> bool:
    """Replacement for click.confirm that accepts full-width y/n input."""
    default_str = "Y/n" if default else "y/N"
    while True:
        answer = normalized_input(f"{prompt} [{default_str}]: ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        if answer == "":
            return default


def get_user_input(pending_count: int) -> str:
    """Get user input with a coloured prompt."""
    if pending_count:
        prompt_text = HTML(f"<ansiyellow>({pending_count} pending)</ansiyellow> <ansigreen><b>&gt; </b></ansigreen>")
    else:
        prompt_text = HTML("<ansigreen><b>&gt; </b></ansigreen>")
    return unicodedata.normalize("NFKC", pt_prompt(prompt_text))


def reposition_kanji(kanji: str) -> bool:
    """Reposition the first matching kanji card to the top of its deck."""
    with console.status(
        f"[bold]Repositioning Kanji card for '{kanji}'…[/bold]", spinner="dots"
    ):
        try:
            card_id = ankiconnect.find_kanji_card_id(kanji)
            if card_id is None:
                error(f"Could not find Kanji card for '{kanji}' in Anki.")
                return False

            ankiconnect.reposition_card_to_top(card_id)
            success(f"Kanji card for '{kanji}' repositioned to top.")
            return True
        except Exception as e:
            error(f"Failed to reposition Kanji card: {e}")
            return False


@click.group(invoke_without_command=True)
@click.pass_context
def jisho_anki(ctx):
    """
    CLI tool to fetch Kanji cards from Anki, search for words on Jisho,
    and add selected words back to Anki.
    """
    # If no subcommand is provided, run the interactive mode
    if ctx.invoked_subcommand is None:
        run_interactive()


@jisho_anki.command()
def setup():
    """Initialize vocabulary deck and note type in Anki."""
    from kanji_vocab_miner.setup import run_setup

    success = run_setup()
    sys.exit(0 if success else 1)


@jisho_anki.command()
def stats():
    """Show kanji, Reading, Grammar, and core vocabulary progress."""
    with console.status("[bold]Crunching your progress…[/bold]", spinner="dots"):
        manual_counts = manual_progress.load_manual_progress()
        try:
            reviewed_kanji = ankiconnect.get_reviewed_kanji()
            all_kanji = ankiconnect.get_all_kanji()
            added_vocab = ankiconnect.count_vocab_notes_added_since(
                manual_counts.vocab_tracking_start
            )
        except Exception as e:
            error(f"AnkiConnect error: {e}")
            sys.exit(1)

        kanji_progress = progress.kanji_coverage(reviewed_kanji, all_kanji)
        textbook_progress = progress.manual_coverage(manual_counts)
        vocab_progress = progress.vocab_progress(
            manual_counts.vocab_baseline, added_vocab
        )

    render.progress_dashboard(kanji_progress, textbook_progress, vocab_progress)


@jisho_anki.command(name="review-level")
@click.argument("level")
def review_level(level):
    """Review words in JLPT LEVEL (N5-N1; N5 = beginner) you haven't carded.

    Shows a scrollable checklist of words not already in your deck or known
    list, alongside each word's hardest kanji and whether you've already
    reviewed it in Anki. Toggle the ones you know with space and confirm to
    record them (without making a flashcard) so they are skipped next time.
    """
    parsed_level = jlpt.parse_level(level)
    if parsed_level is None:
        error("LEVEL must be one of N5, N4, N3, N2, N1.")
        sys.exit(1)

    with console.status(f"[bold]Loading N{parsed_level}…[/bold]", spinner="dots"):
        try:
            deck = set(ankiconnect.get_reviewed_vocab())
            reviewed_kanji = ankiconnect.get_reviewed_kanji()
        except Exception as e:
            error(f"AnkiConnect error: {e}")
            sys.exit(1)
        already_known = known_words.load_known_words()
        words = jlpt.words_in_level(parsed_level)

    skip = deck | already_known
    unknown = [w for w in words if w.expression not in skip]

    if not unknown:
        success(f"Nothing to review — all {len(words)} words in N{parsed_level} are already accounted for.")
        return

    items = review.build_level_review_items(unknown, reviewed_kanji)
    selected = review.review_level_words(items)

    if selected is None:
        info("Review aborted — nothing marked.")
        return

    marked = 0
    for word in selected:
        if known_words.add_known_word(word.expression):
            marked += 1

    success(f"Marked {marked} word(s) as known — they'll be skipped next time.")


def _sync_furigana_and_exit() -> None:
    """Sync furigana on all vocab cards then exit."""
    with console.status("[bold]Syncing furigana on vocab cards…[/bold]", spinner="dots"):
        updated = ankiconnect.sync_vocab_furigana()
    if updated > 0:
        success(f"Updated furigana on {updated} vocab note(s).")
    click.echo("Goodbye!")
    sys.exit(0)


def run_interactive():
    """Run the interactive word selection loop."""
    render.welcome_message()

    # Validate prerequisites before starting
    from kanji_vocab_miner.setup import validate_prerequisites

    is_valid, errors = validate_prerequisites()
    if not is_valid:
        console.print("[bold red]Cannot start - missing prerequisites:[/bold red]\n")
        for error in errors:
            console.print(error)
            console.print()  # Empty line between errors
        sys.exit(1)

    displayed_words: List[JishoWord] = []
    pending_items: List[PendingVocabItem] = []
    active_kanji: Optional[str] = None  # Latest successfully retrieved kanji

    while True:
        try:
            user_input = get_user_input(len(pending_items))

            # Fetch new card and display words
            if user_input.lower() == "n":
                active_kanji = None
                kanji = handle_next_card()
                if kanji:
                    displayed_words = fetch_words_from_kanji(kanji)
                    active_kanji = kanji

            # Reposition the latest successfully retrieved kanji card
            elif user_input == "a":
                if active_kanji is None:
                    info("Retrieve a Kanji before using 'a' to move it to the top.")
                else:
                    reposition_kanji(active_kanji)

            # Select words to add to pending list
            elif any(c.isdigit() for c in user_input):
                pending_items = process_word_selection(
                    displayed_words, pending_items, user_input
                )

            # Commit pending words to Anki
            elif user_input.lower() == "c":
                if not pending_items:
                    info("No words to commit.")
                    continue
                pending_items, continue_loop = handle_review_and_commit(
                    pending_items, is_quitting=False
                )
                if not continue_loop:
                    _sync_furigana_and_exit()

            # Quit the program
            elif user_input.lower() == "q":
                if pending_items:
                    pending_items, continue_loop = handle_review_and_commit(
                        pending_items, is_quitting=True
                    )
                    if continue_loop:
                        continue
                _sync_furigana_and_exit()

            # You can also just enter a kanji directly
            elif is_kanji(user_input):
                active_kanji = None
                kanji = user_input
                with console.status(f"Searching for words containing [yellow2]{kanji}[/yellow2]…", spinner="dots"):
                    displayed_words = fetch_words_from_kanji(kanji)
                active_kanji = kanji

            # Or look up a single word
            elif is_kotoba(user_input):
                with console.status(f"[bold]Looking up word {user_input}…[/bold]", spinner="dots"):
                    word = fetch_word_from_word(user_input)

                if word:
                    add_confirm = normalized_confirm(
                        f"Do you want to add {word.expression} ({word.kana}) to pending words?",
                        default=True,
                    )
                    if add_confirm:
                        pending_expressions = {
                            item.word.expression for item in pending_items
                        }
                        if word.expression not in pending_expressions:
                            pending_items.append(PendingVocabItem(word=word))
                            success(
                                f"Added [bold]{word.expression}[/bold] to pending words."
                            )
                        else:
                            info(f"{word.expression} is already pending.")

                else:
                    render.error(f"Word '{user_input}' not found in JmDict.")


            else:
                click.echo(
                    "Invalid input. Enter 'n' (current Anki card), 'a' (move Kanji "
                    "to top), numbers to select, 'c' (commit), or 'q' (quit)."
                )

        except KeyboardInterrupt:
            click.echo()
            try:
                if not normalized_confirm("Really quit?", default=False):
                    continue
            except (KeyboardInterrupt, EOFError):
                pass
            click.echo("Goodbye!")
            sys.exit(0)

        except Exception as e:
            click.echo(f"An unexpected error occurred: {str(e)}")


if __name__ == "__main__":
    jisho_anki()
