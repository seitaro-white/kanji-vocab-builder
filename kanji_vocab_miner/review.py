"""Review screen for pending words before committing to Anki."""

from typing import Callable, List, Optional

from InquirerPy import inquirer
from InquirerPy.base.control import Choice

from kanji_vocab_miner.jisho import JishoWord


REVIEW_KEYBINDINGS = {
    "toggle-all-true": [{"key": "a"}],
    "toggle-all-false": [{"key": "n"}],
    "interrupt": [{"key": "c-c"}, {"key": "escape"}, {"key": "q"}],
}


def review_pending_words(
    pending_words: List[JishoWord],
    prompt_func: Optional[Callable[..., object]] = None,
) -> Optional[List[JishoWord]]:
    """
    Show a checkbox review screen for pending words.

    Args:
        pending_words: Words waiting to be committed.
        prompt_func: Injectable prompt builder for testing. Defaults to
            InquirerPy's checkbox prompt.

    Returns:
        A list of words to commit, or None if the review was aborted.
        An empty input list returns an empty list without prompting.
    """
    if not pending_words:
        return []

    if prompt_func is None:
        prompt_func = inquirer.checkbox

    prompt = prompt_func(
        message="Review pending words",
        instruction="Space=toggle  a=all  n=none  Enter=commit  Esc/q=abort",
        choices=[
            Choice(value=word, name=_format_choice(word), enabled=True)
            for word in pending_words
        ],
        keybindings=REVIEW_KEYBINDINGS,
        raise_keyboard_interrupt=True,
    )
    try:
        return prompt.execute()
    except KeyboardInterrupt:
        return None


def _format_choice(word: JishoWord) -> str:
    """Format a JishoWord as a display string for the review screen."""
    definition = word.definitions[0] if word.definitions else ""
    return f"{word.expression} ({word.kana}) — {definition}"
