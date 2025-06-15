"""Rendering functions for displaying on CLI"""

from typing import List, Tuple

from rich.console import Console
from rich.table import Table
from rich.text import Text

from jisho_anki_tool.anki import connect
from jisho_anki_tool.jisho import JishoWord

from jamdict.jmdict import JMDEntry

console = Console()


def welcome_message() -> None:
    """Display the welcome message when starting the tool."""

    console.print("[bold red]Welcome to Jisho Anki Tool![/bold red]")
    console.print(
        "[red]This tool allows you to search for Japanese words containing a specific Kanji, "
        "sort them by review status and JLPT level, and add them to your Anki deck.[/red]"
    )
    console.print("Type 'n' to fetch words or 'q' to quit at any time.\n")
    console.print("─" * 80, style="dim")


def words_table(
    sorted_words: List[Tuple[JishoWord, bool]], reviewed_vocab: List[str]
) -> None:
    """Render a table of words with details"""

    table = Table(box=None, show_header=False)

    table.add_column("Index", style="yellow2")
    table.add_column("Word", style="bold chartreuse3")
    table.add_column("Reading", style="cornflower_blue")
    table.add_column("JLPT",)
    table.add_column("Priority", style="magenta")
    table.add_column("Already in Deck", style="light_slate_grey")
    table.add_column("Definition", style="grey74")

    jlpt_colors = {
        5: "#209c05",
        4: "#85e62c",
        3: "#ebff0a",
        2: "#f2ce02",
        1: "#ff0a0a",
        0: "#c3c4c7",
    }

    for idx, (word, priority) in enumerate(sorted_words, 1):
        # JLPT
        jlpt_text = (
            Text(f"N{word.jlpt}", style=jlpt_colors.get(word.jlpt, "#c3c4c7"))
            if word.jlpt
            else Text("")
        )
        # Priority
        priority_text = Text("R", style="#00c18b") if priority else ""
        # Already in deck?
        in_deck = (
            Text("Y", style="#00c18b")
            if word.expression in reviewed_vocab
            else ""
        )

        table.add_row(
            f"{idx}.",
            word.expression,
            word.kana,
            jlpt_text,
            priority_text,
            in_deck,
            word.definitions[0],
        )

    console.print("\nFound words (sorted by reviewed Kanji and JLPT level):")
    console.print(table)
    console.print("─" * 80, style="dim")


def word(word: JishoWord) -> None:
    """Render a single word with its details"""

    console.print(f"[bold green1]{word.expression}[/bold green1] [cornflower_blue]({word.kana})[/cornflower_blue]")

    table = Table(box=None, show_header=False)

    table.add_column("Definition", style="bold yellow2")
    table.add_column("Grammar", style="chartreuse3")


    for i in range(len(word.definitions)):
        definition = word.definitions[i]
        grammar = word.parts_of_speech[i]

        table.add_row(
            Text(definition, style="grey74"),
            Text(grammar, style="light_slate_grey")
        )

    console.print(table)