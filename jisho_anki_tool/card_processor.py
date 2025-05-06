from typing import List, Dict, Any, Set

from jisho_anki_tool.anki import connect

def sort_and_limit_words(words: List[Dict[str, Any]], original_kanji:str, limit: int = 10) -> List[Dict[str, Any]]:
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

    # Create a list of (word, priority, jlpt_rank) tuples for sorting
    word_rankings = []

    # Remove the original Kanji from the list of words
    words = [word for word in words if word["word"] != original_kanji]

    for word in words:
        # Check if all other Kanji in the word have been reviewed
        other_kanji = word.get("other_kanji", [])

        # Priority 1: All other Kanji are reviewed
        # Priority 0: Some other Kanji are not reviewed
        all_reviewed = all(k in reviewed_kanji for k in other_kanji)
        priority = 1 if all_reviewed else 0

        # Map JLPT level to rank (higher is better)
        # N5=5, N4=4, N3=3, N2=2, N1=1, none=0
        jlpt_level = word.get("jlpt")
        jlpt_rank = jlpt_level if jlpt_level is not None else 0

        word_rankings.append((word | {"priority": priority}, priority, jlpt_rank, priority))

    # Sort by priority (descending) and JLPT rank (descending)
    # This ensures a stable sort where priority comes first, then JLPT level
    sorted_words = [item[0] for item in sorted(word_rankings,
                                              key=lambda x: (x[1], x[2]),
                                              reverse=True)]

    # Return the top N words
    return sorted_words[:limit]
