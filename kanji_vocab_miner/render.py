"""Rendering functions for displaying on CLI"""

from typing import List, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule

from kanji_vocab_miner.anki import connect
from kanji_vocab_miner import frequency, jlpt
from kanji_vocab_miner.jisho import JishoWord, KanjiSummary
from kanji_vocab_miner.progress import KanjiProgress, VocabProgress

from jamdict.jmdict import JMDEntry

console = Console()


def _resolve_jlpt_level(word: JishoWord) -> int:
    """Prefer our vendored JLPT index; fall back to Jisho's live-scraped tag."""
    return jlpt.get_level_index().get(word.expression) or word.jlpt or 0


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
    sorted_words: List[Tuple[JishoWord, bool]],
    reviewed_vocab: List[str],
    freq_map: dict = None,
) -> None:
    """Render a table of words with details"""

    freq_map = freq_map or {}

    table = Table(box=None, show_header=False)

    table.add_column("Index", style="yellow2")
    table.add_column("Word", style="bold chartreuse3")
    table.add_column("Reading", style="cornflower_blue")
    table.add_column("Freq", style="dark_orange3")
    table.add_column("JLPT",)
    table.add_column("Priority", style="magenta")
    table.add_column("Already in Deck", style="light_slate_grey")
    table.add_column("Definition", style="grey74")

    for idx, (word, priority) in enumerate(sorted_words, 1):
        level = _resolve_jlpt_level(word)
        jlpt_text = Text(jlpt.level_label(level), style=jlpt.LEVEL_COLORS.get(level, jlpt.LEVEL_COLORS[0]))
        # Priority
        priority_text = Text("R", style="#00c18b") if priority else ""
        # Already in deck?
        in_deck = (
            Text("Y", style="#00c18b")
            if word.expression in reviewed_vocab
            else ""
        )

        freq_text = frequency.band_label(freq_map.get(word.expression))

        table.add_row(
            f"{idx}.",
            word.expression,
            word.kana,
            freq_text,
            jlpt_text,
            priority_text,
            in_deck,
            word.definitions[0],
        )
    # Add a separator line
    console.print(Rule(style="dim"))
    console.print(table)
    console.print(Rule(style="dim"))


def word(word: JishoWord, freq_map: dict = None) -> None:
    """Render a single word with its details"""

    freq_map = freq_map or {}
    freq_label = frequency.band_label(freq_map.get(word.expression))
    freq_suffix = f"  [dark_orange3]{freq_label}[/dark_orange3]" if freq_label else ""

    level = _resolve_jlpt_level(word)
    level_label = jlpt.level_label(level)
    level_suffix = f"  [{jlpt.LEVEL_COLORS.get(level, jlpt.LEVEL_COLORS[0])}]{level_label}[/]" if level_label else ""

    console.print(
        f"  [bold green1]{word.expression}[/bold green1]  "
        f"([cornflower_blue]{word.kana}[/cornflower_blue]){freq_suffix}{level_suffix}"
    )

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


def _bar(known: int, total: int, width: int = 24) -> Text:
    """Build a coloured progress bar with a 'known/total (pct%)' suffix."""
    pct = (known / total) if total else 0.0
    filled = round(pct * width)
    # Colour by how far along: red -> yellow -> green.
    colour = "#ff5f5f" if pct < 0.34 else "#ebff0a" if pct < 0.67 else "#00c18b"
    bar = Text()
    bar.append("█" * filled, style=colour)
    bar.append("░" * (width - filled), style="grey37")
    bar.append(f"  {known}/{total} ({pct * 100:.0f}%)", style="grey74")
    return bar


def _progress_grid(rows: List[Tuple[str, int, int]]) -> Table:
    """A two-column grid of label + bar for the given (label, known, total) rows."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(justify="right", style="bold chartreuse3", no_wrap=True)
    grid.add_column()
    for label, known, total in rows:
        grid.add_row(label, _bar(known, total))
    return grid


def progress_dashboard(kanji: KanjiProgress, vocab: VocabProgress) -> None:
    """Render the Jouyou-kanji and JLPT vocab coverage dashboard."""
    # --- Kanji panel: coverage bars per JLPT level ---
    kanji_body = Table.grid()
    kanji_body.add_column()
    kanji_body.add_row(_bar(kanji.known_total, kanji.total, width=30))
    kanji_body.add_row("")
    kanji_body.add_row(
        _progress_grid(
            [(f"N{lb.level}", lb.known, lb.total) for lb in kanji.levels]
        )
    )
    kanji_body.add_row("")
    kanji_body.add_row(
        Text(
            f"{kanji.missing_from_deck} Jouyou kanji not yet in your deck  •  "
            f"{kanji.unranked} known kanji with no JLPT level",
            style="dim italic",
        )
    )
    console.print(
        Panel(
            kanji_body,
            title="[bold yellow]Kanji — JLPT coverage[/bold yellow]",
            border_style="bright_blue",
        )
    )

    # --- Vocab panel: coverage bars per JLPT level ---
    pct = (vocab.placed / vocab.total_ranked * 100) if vocab.total_ranked else 0.0

    vocab_body = Table.grid()
    vocab_body.add_column()
    vocab_body.add_row(
        _progress_grid(
            [(f"N{lb.level}", lb.known, lb.total) for lb in vocab.levels]
        )
    )
    vocab_body.add_row("")
    vocab_body.add_row(
        Text(
            f"{vocab.placed}/{vocab.total_ranked} JLPT words known "
            f"({pct:.0f}%)  •  {vocab.unranked} deck words with no JLPT level",
            style="dim italic",
        )
    )
    console.print(
        Panel(
            vocab_body,
            title="[bold yellow]Vocab — JLPT coverage[/bold yellow]",
            border_style="bright_blue",
        )
    )




def info(msg: str) -> None:
    console.print(f"  [cyan]{msg}[/cyan]")


def success(msg: str) -> None:
    console.print(f"[bold green]O[/bold green] {msg}")


def error(msg: str) -> None:
    console.print(f"[bold red]X[/bold red] {msg}")
