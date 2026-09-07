"""Review screens: pending words before committing to Anki, and JLPT-level
vocab triage."""

import types
import unicodedata
from copy import deepcopy
from dataclasses import dataclass
from typing import Callable, List, Literal, Optional, Tuple

from InquirerPy import get_style, inquirer
from InquirerPy.base.control import Choice
from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.styles import Style

from kanji_vocab_miner import kanji_jlpt
from kanji_vocab_miner.jisho import JishoWord
from kanji_vocab_miner.jlpt import LEVEL_COLORS, LevelWord
from kanji_vocab_miner.vocab_models import PendingVocabItem


REVIEW_KEYBINDINGS = {
    "toggle-all-true": [{"key": "a"}],
    "toggle-all-false": [{"key": "n"}],
    "interrupt": [{"key": "c-c"}, {"key": "escape"}, {"key": "q"}],
}

COMMIT_SYMBOL = "✓"
DISCARD_SYMBOL = " "
COMMIT_STYLE = get_style({"checkbox": "bold #98c379"}, style_override=False)


ReviewAction = Literal[
    "up", "down", "toggle_add", "toggle_recall", "enable_all", "disable_all"
]


@dataclass
class ReviewResult:
    """Return whether review was submitted together with its complete item state."""

    submitted: bool
    items: List[PendingVocabItem]


def reduce_review_state(
    items: List[PendingVocabItem], focus: int, action: ReviewAction
) -> tuple[List[PendingVocabItem], int]:
    """Return review state after one navigation or toggle action.

    The input items are copied before modification so terminal rendering and
    reducer tests do not depend on shared mutation. Recall remains stored when
    Add is disabled, while enabling Recall also enables Add.

    Args:
        items: Current pending rows and their Add and Recall selections.
        focus: Zero-based index of the focused row.
        action: Navigation, per-row toggle, or bulk Add operation.

    Returns:
        A copied item list and a focus index clamped to the available rows.
    """
    updated_items = deepcopy(items)
    if not updated_items:
        return updated_items, 0

    bounded_focus = min(max(focus, 0), len(updated_items) - 1)
    if action == "up":
        return updated_items, max(0, bounded_focus - 1)
    if action == "down":
        return updated_items, min(len(updated_items) - 1, bounded_focus + 1)
    if action == "toggle_add":
        item = updated_items[bounded_focus]
        item.add_enabled = not item.add_enabled
    elif action == "toggle_recall":
        item = updated_items[bounded_focus]
        item.recall_enabled = not item.recall_enabled
        if item.recall_enabled:
            item.add_enabled = True
    elif action == "enable_all":
        for item in updated_items:
            item.add_enabled = True
    elif action == "disable_all":
        for item in updated_items:
            item.add_enabled = False
    return updated_items, bounded_focus


def review_pending_words(
    pending_items: List[PendingVocabItem],
    run_application: Optional[Callable[[Application], ReviewResult]] = None,
) -> ReviewResult:
    """Display the dual-toggle commit review and return explicit submit state.

    Args:
        pending_items: Vocabulary items with their current Add and Recall choices.
        run_application: Optional application runner used to isolate terminal IO in tests.

    Returns:
        The submitted or aborted result, including all edited item choices.
    """
    if not pending_items:
        return ReviewResult(submitted=True, items=[])

    items = deepcopy(pending_items)
    focus = 0
    key_bindings = KeyBindings()

    def apply_action(action: ReviewAction) -> None:
        nonlocal items, focus
        items, focus = reduce_review_state(items, focus, action)

    for key, action in (
        ("up", "up"),
        ("down", "down"),
        (" ", "toggle_add"),
        ("r", "toggle_recall"),
        ("a", "enable_all"),
        ("n", "disable_all"),
    ):
        key_bindings.add(key)(
            lambda event, selected_action=action: apply_action(selected_action)
        )

    @key_bindings.add("enter")
    def submit(event) -> None:
        event.app.exit(result=ReviewResult(submitted=True, items=items))

    @key_bindings.add("escape")
    @key_bindings.add("q")
    def abort(event) -> None:
        event.app.exit(result=ReviewResult(submitted=False, items=items))

    def render_rows() -> FormattedText:
        fragments = [
            ("class:header", "Add  Recall  Word (reading) — primary English definition\n")
        ]
        for index, item in enumerate(items):
            if index == focus:
                fragments.append(("[SetCursorPosition]", ""))
            add_marker = "✓" if item.add_enabled else " "
            recall_marker = "R" if item.recall_enabled else " "
            definition = item.word.definitions[0] if item.word.definitions else ""
            failure_detail = (
                f" [last error: {item.last_error}]" if item.last_error else ""
            )
            row = (
                f" {add_marker}     {recall_marker}     {item.word.expression} "
                f"({item.word.kana}) — {definition}{failure_detail}\n"
            )
            style = "class:focus" if index == focus else ""
            if not item.add_enabled:
                style += " class:disabled"
            fragments.append((style.strip(), row))
        return FormattedText(fragments)

    control = FormattedTextControl(text=render_rows, focusable=True)
    body = Window(content=control, always_hide_cursor=True)
    instructions = Window(
        height=1,
        content=FormattedTextControl(
            "Space=Add  r=Recall  a=all  n=none  Enter=commit  Esc/q=abort"
        ),
    )
    application = Application(
        layout=Layout(HSplit([body, instructions]), focused_element=body),
        key_bindings=key_bindings,
        full_screen=True,
        style=Style.from_dict(
            {
                "header": "bold",
                "focus": "reverse",
                "disabled": "fg:#767676",
            }
        ),
    )
    runner = run_application or (lambda app: app.run())
    return runner(application)


@dataclass
class LevelReviewItem:
    word: LevelWord
    hardest_kanji: str | None  # most difficult kanji in the word, if any
    hardest_kanji_level: int | None  # that kanji's own N-level (1-5)
    hardest_kanji_known: bool  # already reviewed in Anki (or no kanji at all)


def build_level_review_items(
    words: List[LevelWord], reviewed_kanji: set[str]
) -> List[LevelReviewItem]:
    """Pair each word with its hardest kanji and whether that kanji is known."""
    items = []
    for word in words:
        kanji, level = kanji_jlpt.hardest_kanji(word.expression)
        known = kanji is None or kanji in reviewed_kanji
        items.append(
            LevelReviewItem(
                word=word,
                hardest_kanji=kanji,
                hardest_kanji_level=level,
                hardest_kanji_known=known,
            )
        )
    return items


LEVEL_REVIEW_STYLE = get_style(
    {
        "checkbox": "bold #98c379",
        "n1": f"bold {LEVEL_COLORS[1]}",
        "n2": f"bold {LEVEL_COLORS[2]}",
        "n3": f"bold {LEVEL_COLORS[3]}",
        "n4": f"bold {LEVEL_COLORS[4]}",
        "n5": f"bold {LEVEL_COLORS[5]}",
        "known": "#00c18b",
        "unknown": "#e5c07b",
        "col-dim": "#767676",
    },
    style_override=False,
)

_COL_WORD = 12
_COL_READING = 14
_COL_KANJI = 12
_COL_STATUS = 15


def review_level_words(
    items: List[LevelReviewItem],
    prompt_func: Optional[Callable[..., object]] = None,
) -> Optional[List[LevelWord]]:
    """
    Show a checkbox review screen for JLPT-level vocab triage.

    Args:
        items: Candidate words paired with their hardest-kanji info.
        prompt_func: Injectable prompt builder for testing. Defaults to
            InquirerPy's checkbox prompt.

    Returns:
        The words the user marked as known, or None if the review was
        aborted. An empty input list returns an empty list without prompting.
    """
    if not items:
        return []

    using_default_prompt = prompt_func is None
    if prompt_func is None:
        prompt_func = inquirer.checkbox

    prompt = prompt_func(
        message="Mark words you already know",
        instruction="Space=toggle known  a=all  n=none  Enter=confirm  Esc/q=abort",
        long_instruction=(
            f"{'Word'.ljust(_COL_WORD)}{'Reading'.ljust(_COL_READING)}"
            f"{'Hardest kanji'.ljust(_COL_KANJI)}{'Kanji status'.ljust(_COL_STATUS)}Definition"
        ),
        choices=[
            Choice(value=item.word, name=_format_level_choice(item), enabled=False)
            for item in items
        ],
        keybindings=REVIEW_KEYBINDINGS,
        enabled_symbol=COMMIT_SYMBOL,
        disabled_symbol=DISCARD_SYMBOL,
        style=LEVEL_REVIEW_STYLE,
        raise_keyboard_interrupt=True,
    )

    if using_default_prompt:
        _colorize_level_review_choices(prompt, items)

    try:
        return prompt.execute()
    except KeyboardInterrupt:
        return None


def _display_width(text: str) -> int:
    """Approximate terminal cell width, counting wide (CJK) characters as 2."""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _display_width(text))


def _format_level_choice(item: LevelReviewItem) -> str:
    """Plain-text fallback display string (used when no live terminal control
    is available to colorize, e.g. under test)."""
    word = item.word
    definition = word.definition or ""

    if item.hardest_kanji is None:
        kanji_col = "no kanji"
        status_col = ""
    else:
        level_col = f"N{item.hardest_kanji_level}" if item.hardest_kanji_level else "N?"
        kanji_col = f"{item.hardest_kanji} ({level_col})"
        status_col = "reviewed" if item.hardest_kanji_known else "NOT reviewed"

    return (
        f"{_pad(word.expression, _COL_WORD)}"
        f"{_pad(f'({word.kana})', _COL_READING)}"
        f"{_pad(kanji_col, _COL_KANJI)}"
        f"{_pad(status_col, _COL_STATUS)}"
        f"{definition}"
    )


def _level_review_fragments(item: LevelReviewItem) -> List[Tuple[str, str]]:
    """Coloured (style, text) fragments for one review row's columns."""
    word = item.word
    fragments: List[Tuple[str, str]] = [
        ("", _pad(word.expression, _COL_WORD)),
        ("", _pad(f"({word.kana})", _COL_READING)),
    ]

    if item.hardest_kanji is None:
        fragments.append(("class:col-dim", _pad("no kanji", _COL_KANJI)))
        fragments.append(("", _pad("", _COL_STATUS)))
    else:
        level_style = f"class:n{item.hardest_kanji_level}" if item.hardest_kanji_level else ""
        level_text = f"N{item.hardest_kanji_level}" if item.hardest_kanji_level else "N?"
        fragments.append(
            (level_style, _pad(f"{item.hardest_kanji} ({level_text})", _COL_KANJI))
        )
        status_style = "class:known" if item.hardest_kanji_known else "class:unknown"
        status_text = "reviewed" if item.hardest_kanji_known else "NOT reviewed"
        fragments.append((status_style, _pad(status_text, _COL_STATUS)))

    fragments.append(("", word.definition or ""))
    return fragments


def _colorize_level_review_choices(
    prompt, items: List[LevelReviewItem]
) -> None:
    """Patch the live InquirerPy control to render coloured, column-aligned
    rows instead of a single plain-text name per choice.

    InquirerPy's `Choice.name` only supports one flat style per row, so real
    per-column colour requires overriding the control's row-formatting
    methods. This only touches this one prompt instance.

    Choice values round-trip through InquirerPy's internal `asdict()` call as
    a copy, not the original object, so rows are matched back up by
    expression (unique within a single level's word list) rather than by
    identity.
    """
    items_by_expression = {item.word.expression: item for item in items}
    control = prompt.content_control

    def _get_normal_text(self, choice) -> List[Tuple[str, str]]:
        fragments: List[Tuple[str, str]] = [("", len(self._pointer) * " ")]
        if self._pointer:
            fragments.append(("", " "))
        fragments.append(
            ("class:checkbox", self._enabled_symbol if choice["enabled"] else self._disabled_symbol)
        )
        if self._enabled_symbol and self._disabled_symbol:
            fragments.append(("", " "))
        fragments.extend(_level_review_fragments(items_by_expression[choice["value"].expression]))
        return fragments

    def _get_hover_text(self, choice) -> List[Tuple[str, str]]:
        fragments: List[Tuple[str, str]] = [("class:pointer", self._pointer)]
        if self._pointer:
            fragments.append(("", " "))
        fragments.append(
            ("class:checkbox", self._enabled_symbol if choice["enabled"] else self._disabled_symbol)
        )
        if self._enabled_symbol and self._disabled_symbol:
            fragments.append(("", " "))
        fragments.append(("[SetCursorPosition]", ""))
        fragments.extend(_level_review_fragments(items_by_expression[choice["value"].expression]))
        return fragments

    control._get_normal_text = types.MethodType(_get_normal_text, control)
    control._get_hover_text = types.MethodType(_get_hover_text, control)
