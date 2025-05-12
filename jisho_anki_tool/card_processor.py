from typing import List, Dict, Any, Set, Tuple

from jisho_anki_tool.anki import connect
from jisho_anki_tool.jisho import JishoWord

def sort_and_limit_words(words: List[JishoWord], original_kanji:str, limit: int = 10) -> List[Tuple[int, JishoWord]]:
    """
    Sort words based on whether other Kanji in the word have been reviewed,
    and by JLPT level. Higher priority is given to words where all Kanji
    have been reviewed, and then by higher JLPT level (N5 > N4 > ... > N1).

    Args:
        words: List of word dictionaries from Jisho API
        limit: Maximum number of words to return (default: 10)

    Returns:
        Sorted list of words, limited to the specified count
    """


    if not words:
        return []

    # Get the set of Kanji that have been reviewed
    reviewed_kanji = connect.get_reviewed_kanji()

    # Remove the original Kanji from the list of words
    words = [word for word in words if word.expression != original_kanji]

    # Create a list of (word, priority, jlpt_rank) tuples for sorting
    sortorder = []
    for word in words:

        # Remove the original Kanji from the set of other Kanji
        other_kanji = set(word.expression) - {original_kanji}

        # Priority 1: All other Kanji are reviewed
        # Priority 0: Some other Kanji are not reviewed
        all_reviewed = all(k in reviewed_kanji for k in other_kanji)
        priority = 1 if all_reviewed else 0

        sortorder.append((priority, word.jlpt, word))

    sortorder = sorted(sortorder, reverse=True, key=lambda x: (x[0], x[1]))

    # Return words using the sort order
    sorted_words = [(word, priority) for priority, _, word in sortorder]
    return sorted_words[:limit]
