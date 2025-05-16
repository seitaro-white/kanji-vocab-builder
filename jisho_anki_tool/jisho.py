# %%
# Imports
import requests
import urllib.parse
from typing import List, Dict, Any, Optional

from bs4 import BeautifulSoup

from pydantic import BaseModel

# Classes
class JishoWord(BaseModel):

    expression: str # The proper expression of the word
    kana: str # The expression of the word in kana
    jlpt: int # JLPT level
    definitions: List[str] # A list of definitions
    parts_of_speech: Optional[List[str]] = None # A list of parts of speech


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

    Return as a string in the format of "漢字[ふりがな] ひらがな"
    """

    response = requests.get("https://jisho.org/word/" + word)
    soup = BeautifulSoup(response.text, "html.parser")

    wordhtml = soup.select("div.concept_light-representation")[0].extract()

    # Convert furigana to anki-friendly format
    characters = wordhtml.select_one("span.text").text.strip(" \n")
    furigana = [i.text for i in wordhtml.select("span.kanji")]

    # In some cases (e.g. 借金) even jisho doesn't have the correct furigana mapping
    # So we'll have to just default to applying the full furigana to the full kanji
    if len(furigana) != len([i for i in characters if is_kanji(i)]):
        return characters + f"[{''.join(furigana)}]"

    # Match up each kanji with its furigana, while just adding spaces for hiragana
    anki_format, furigana_idx = "", 0
    for c in characters:
        if is_kanji(c):
            anki_format += f"{c}[{furigana[furigana_idx]}]"
            furigana_idx += 1
        elif is_hiragana(c):
            anki_format += f"{c} "
        else:
            raise Exception(f"Unknown character type: {c}")


    return anki_format




def search_words_containing_kanji(kanji: str) -> List[JishoWord]:
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
        jlpt_level = 0
        if jlpt_data:
            # Extract the numeric level from strings like "jlpt-n5"
            for level in jlpt_data:
                if level.startswith("jlpt-n"):
                    try:
                        jlpt_level = int(level.split("jlpt-n")[1])
                        break
                    except (ValueError, IndexError):
                        pass

        # Extract definitions and parts of speech (up to 3)
        definitions, parts_of_speech = [], []
        if "senses" in item:
            for sense in item["senses"][:3]:  # Limit to top 3 senses
                definition = "; ".join(sense.get("english_definitions", []))
                pos = "; ".join(sense.get("parts_of_speech", []))

                definitions.append(definition)
                parts_of_speech.append(pos)


        # Results
        jishoword = JishoWord(
            expression=word,
            kana=reading,
            jlpt=jlpt_level,
            definitions=definitions,
            parts_of_speech=parts_of_speech,
        )

        result_words.append(jishoword)

    return result_words


def is_kanji(char: str) -> bool:
    """
    Check if a character is a Kanji.
    """

    if len(char) != 1:
        return False

    # Unicode ranges for Kanji: CJK Unified Ideographs (4E00-9FFF)
    return 0x4E00 <= ord(char) <= 0x9FFF


def is_hiragana(char: str) -> bool:
    """
    Check if a character is Hiragana.
    """
    if len(char) != 1:
        return False

    # Unicode range for Hiragana: U+3040 to U+309F
    return 0x3040 <= ord(char) <= 0x309F

# %%
