import re
from typing import List, Dict, Any, Optional

def format_furigana(word: str, reading: str) -> str:
    """
    Format a word with furigana using ruby tags.

    Args:
        word: The word in kanji/kana
        reading: The reading in hiragana/katakana

    Returns:
        Formatted string with furigana in ruby tags
    """
    # If word is the same as reading (kana only), return it as-is
    if word == reading:
        return word

    # If no reading is provided, return the word as-is
    if not reading:
        return word

    # Simple case: one kanji with one reading
    if len(word) == 1:
        return f"<ruby>{word}<rt>{reading}</rt></ruby>"

    # Complex case: Try to align readings with kanji
    # This is a simplified approach; accurate furigana alignment would require morphological analysis

    result = []
    reading_idx = 0

    for char in word:
        if is_kanji(char):
            # Find the likely reading for this kanji
            # This is a very simplified approach that assumes readings are in order
            # A more accurate approach would require more complex analysis
            kana_part = ""
            while reading_idx < len(reading) and is_kana(reading[reading_idx]):
                kana_part += reading[reading_idx]
                reading_idx += 1

                # Stop if we've read a reasonable length of kana
                if len(kana_part) >= 4:  # arbitrary cutoff
                    break

            if kana_part:
                result.append(f"<ruby>{char}<rt>{kana_part}</rt></ruby>")
            else:
                result.append(char)
        else:
            # If it's not kanji, append it as-is
            result.append(char)
            # And advance the reading index if the character matches
            if reading_idx < len(reading) and char == reading[reading_idx]:
                reading_idx += 1

    return "".join(result)

def is_kanji(char: str) -> bool:
    """
    Check if a character is a Kanji.

    Args:
        char: The character to check

    Returns:
        True if the character is a Kanji, False otherwise
    """
    # Unicode ranges for Kanji: CJK Unified Ideographs (4E00-9FFF)
    if len(char) != 1:
        return False

    code_point = ord(char)
    return 0x4E00 <= code_point <= 0x9FFF

def is_kana(char: str) -> bool:
    """
    Check if a character is Hiragana or Katakana.

    Args:
        char: The character to check

    Returns:
        True if the character is Hiragana or Katakana, False otherwise
    """
    if len(char) != 1:
        return False

    code_point = ord(char)
    # Hiragana: 3040-309F, Katakana: 30A0-30FF
    return (0x3040 <= code_point <= 0x309F) or (0x30A0 <= code_point <= 0x30FF)

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
