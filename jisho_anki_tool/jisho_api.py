# %%
import requests
import urllib.parse
from typing import List, Dict, Any

from bs4 import BeautifulSoup

def fetch_jisho_word_search(query: str) -> Dict[str, Any]:
    """
    Fetch raw data from the Jisho API for the given query.

    Args:
        query: The search query to send to Jisho API

    Returns:
        The raw JSON response as a dictionary

    Raises:
        Exception: If the request fails or the response is invalid
    """
    try:
        # Construct the URL with proper encoding
        encoded_query = urllib.parse.quote(query)
        url = f"https://jisho.org/api/v1/search/words?keyword=*{encoded_query}*"

        # Send the request
        response = requests.get(url)
        response.raise_for_status()  # Raise exception for HTTP errors

        return response.json()

    except requests.RequestException as e:
        raise Exception(f"Failed to connect to Jisho API: {str(e)}")
    except Exception as e:
        raise Exception(f"Error processing Jisho API response: {str(e)}")


def fetch_jisho_word_furigana(word: str) -> str:
    """
    While the API is good, it unfortunately does not include exact place information for kanji to hiragana.

    We want to render the correct character above each kanji, which means we need to make a request to the
    Jisho website itself and pull it out the html.

    Return as a ruby string which renders in ANKI.
    """

    response = requests.get("https://jisho.org/word/" + word)
    soup = BeautifulSoup(response.text, "html.parser")

    wordhtml = soup.select("div.concept_light-representation")[0].extract()

    # Convert to ruby
    kanji = list(wordhtml.select_one("span.text").text.strip(" \n"))
    furigana = [i.text for i in wordhtml.select("span.kanji")]

    if not len(furigana) == len(kanji):
        raise Exception("Furigana and kanji length mismatch")

    return (
        "<ruby>"
        + "".join([f"{k}<rp> <rt>{f}</rt>" for k, f in zip(kanji, furigana)])
        + "</ruby>"
    )



def search_words_containing_kanji(kanji: str) -> List[Dict[str, Any]]:
    """
    Search for words containing the given Kanji character using the Jisho API.

    Args:
        kanji: The Kanji character to search for

    Returns:
        A list of dictionaries containing word information:
        - word: The word in Japanese (Kanji/kana)
        - reading: Hiragana or katakana reading
        - jlpt: JLPT level (if available)
        - definitions: List of English definitions (up to 3)
        - other_kanji: Other Kanji characters in the word (excluding the target Kanji)

    Raises:
        Exception: If the request fails or the response is invalid
    """
    if not kanji:
        return []

    # Fetch data from the API
    data = fetch_jisho_word_search(kanji)

    if "data" not in data:
        return []

    result_words = []

    # Process each result
    for item in data["data"]:
        # Skip if no Japanese data
        if "japanese" not in item or not item["japanese"]:
            continue

        # Extract word and reading
        japanese_data = item["japanese"][0]
        word = japanese_data.get("word", japanese_data.get("reading", ""))
        reading = japanese_data.get("reading", "")

        # Skip if the target Kanji isn't in the word
        if kanji not in word:
            continue

        # Extract JLPT level
        jlpt_data = item.get("jlpt", [])
        jlpt_level = None
        if jlpt_data:
            # Extract the numeric level from strings like "jlpt-n5"
            for level in jlpt_data:
                if level.startswith("jlpt-n"):
                    try:
                        jlpt_level = int(level.split("jlpt-n")[1])
                        break
                    except (ValueError, IndexError):
                        pass

        # Extract definitions (up to 3)
        definitions = []
        if "senses" in item:
            for sense in item["senses"][:3]:  # Limit to top 3 senses
                if "english_definitions" in sense:
                    # Join multiple definitions with "; "
                    definition = "; ".join(sense["english_definitions"])
                    if definition:
                        definitions.append(definition)

        # Extract other Kanji characters
        other_kanji = []
        for char in word:
            if char != kanji and is_kanji(char):
                other_kanji.append(char)

        # Create the result dictionary
        result = {
            "word": word,
            "reading": reading,
            "jlpt": jlpt_level,
            "definitions": definitions,
            "other_kanji": other_kanji,
            "meaning": definitions[0]
            if definitions
            else "",  # Add first definition as meaning for display
        }

        result_words.append(result)

    return result_words


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
