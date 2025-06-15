from typing import List


def parse_integer_selection(input_str: str) -> List[int]:
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

def is_kotoba(s: str) -> bool:
    """
    Check if a string is a Japanese word composed of Kanji, Hiragana, or Katakana.:
    """
    if len(s) < 2:
        return False

    for c in s:
        cp = ord(c)
        # Kanji (4E00–9FFF), Hiragana (3040–309F), Katakana (30A0–30FF)
        if not (
            0x4E00 <= cp <= 0x9FFF
            or 0x3040 <= cp <= 0x309F
            or 0x30A0 <= cp <= 0x30FF
        ):
            return False

    return True