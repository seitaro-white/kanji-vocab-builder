"""Domain values describing the review state of a kanji."""

from enum import Enum


class KanjiReviewStatus(str, Enum):
    """Review state for a kanji card in the configured Anki deck."""

    REVIEWED = "reviewed"
    NOT_REVIEWED = "not_reviewed"
    NOT_IN_DECK = "not_in_deck"
    UNKNOWN = "unknown"
