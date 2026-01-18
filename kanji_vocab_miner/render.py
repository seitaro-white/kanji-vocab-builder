"""Rendering functions for displaying on CLI"""

from typing import List, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule

from kanji_vocab_miner.anki import connect
from kanji_vocab_miner.jisho import JishoWord, KanjiSummary

from jamdict.jmdict import JMDEntry

console = Console()


def welcome_message() -> None:
    """Display the welcome message when starting the tool."""
    console.clear()
    # a nice panel banner
    banner = Text("Anki 単語 Builder", justify="center", style="bold magenta")
    subtitle = Text("Add vocabulary to Anki", style="yellow")
    panel = Panel(banner, subtitle=subtitle, border_style="bright_blue")
    console.print(panel)
    # tiny help line
    console.print(
        "[dim]山[/dim]: Search Kanji   •  [dim]火山[/dim]: Search Word  •  [dim]c[/dim]: commit  •  [dim]q[/dim]: quit\n"
    )


def kanji_summary(summary: KanjiSummary) -> None:
    """Render a short summary panel for the current kanji."""
    jlpt_label = f"N{summary.jlpt}" if summary.jlpt else "—"
    readings_lines = []
    if summary.kun_readings:
        readings_lines.append(("Kun", "、".join(summary.kun_readings)))
    if summary.on_readings:
        readings_lines.append(("On", "、".join(summary.on_readings)))

    table = Table.grid(expand=True)
    table.add_column(justify="left", style="bold chartreuse3", no_wrap=True)
    table.add_column()

    table.add_row("JLPT", jlpt_label)
    for label, reading in readings_lines:
        table.add_row(label, reading)
    meanings_text = "; ".join(summary.meanings[:3]) or "—"
    table.add_row("Meaning", meanings_text)


    panel = Panel(
        table,
        title=f"[bold yellow]{summary.kanji}[/bold yellow]",
        border_style="bright_blue",
    )
    console.print(panel)



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
    # Add a separator line
    console.print(Rule(style="dim"))
    console.print(table)
    console.print(Rule(style="dim"))


def word(word: JishoWord) -> None:
    """Render a single word with its details"""

    console.print(f"  [bold green1]{word.expression}[/bold green1]  ([cornflower_blue]{word.kana}[/cornflower_blue])")

    table = Table(box=None, show_header=False)

    table.add_column("Index", style="bold yellow2")
    table.add_column("Definition", style="white")
    table.add_column("Grammar", style="chartreuse3")

    for ct, i in enumerate(range(len(word.definitions))):
        definition = word.definitions[i]
        grammar = word.parts_of_speech[i]

        table.add_row(
            f" {ct + 1}.",
            Text(definition, style="grey74"),
            Text(grammar, style="light_slate_grey")
        )

    console.print(table)
    console.print(Rule(style="dim"))


def info(msg: str) -> None:
    console.print(f"  [cyan]{msg}[/cyan]")


def success(msg: str) -> None:
    console.print(f"[bold green]O[/bold green] {msg}")


def error(msg: str) -> None:
    console.print(f"[bold red]X[/bold red] {msg}")
