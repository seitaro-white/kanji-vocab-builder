import re
from typing import List

def format_furigana(word: str, reading: str) -> str:
    """
    Format a Japanese word with furigana using HTML ruby tags.

    Args:
        word: The word in kanji/kana
        reading: The reading in hiragana/katakana

    Returns:
        If the word contains only kana, returns the word as is.
        Otherwise, returns the word with ruby annotations.
    """
    if not word or not reading:
        return word or reading or ""

    # Check if word is kana-only (hiragana or katakana)
    kana_pattern = r'^[ぁ-んァ-ンー]*$'
    if re.match(kana_pattern, word):
        return word

    # Use ruby tags to add furigana
    # This is a simplified implementation that assumes reading aligns with the word
    # For more complex cases, word and reading would need to be parsed character by character
    return f'<ruby>{word}<rt>{reading}</rt></ruby>'

def parse_selection(input_str: str) -> List[int]:
    """
    Parse a space-separated string of integers.

    Args:
        input_str: Space-separated integers (e.g., "1 3 5")

    Returns:
        A list of valid integers
    """
    if not input_str:
        return []

    try:
        # Split the string on whitespace
        parts = input_str.split()

        # Convert each part to an integer, ignoring non-numeric values
        result = []
        for part in parts:
            try:
                num = int(part.strip())
                result.append(num)
            except ValueError:
                # Skip items that can't be converted to integers
                continue

        return result
    except Exception:
        # Return an empty list if any unexpected error occurs
        return []
