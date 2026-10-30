# %%
# Imports
import re
import urllib.parse
from html import escape
from typing import Any, Dict, List, Optional, Set

import requests
from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel

from kanji_vocab_miner.furigana import render_token_furigana

KANJI_DETAIL_SUFFIX = "%23kanji"
KANJI_BASE_URL = "https://jisho.org/search/"
KANJI_DETAIL_SELECTOR = "div.kanji.details"


# Classes
class JishoWord(BaseModel):
    expression: str  # The proper expression of the word
    kana: str  # The expression of the word in kana
    jlpt: int  # JLPT level
    definitions: List[str]  # A list of definitions
    parts_of_speech: Optional[List[str]] = None  # A list of parts of speech


class KanjiSummary(BaseModel):
    kanji: str
    meanings: List[str]
    kun_readings: List[str]
    on_readings: List[str]
    jlpt: int


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


def fetch_jisho_word_furigana(word: str, reviewed_kanji: Set[str]) -> str:
    """Fetch Jisho ruby while preserving the requested dictionary spelling.

    A missing word page (404 only) uses exact Other forms on Jisho's search page.
    Conflicting readings across matching search entries are rejected.

    Args:
        word: Exact spelling selected by the caller, including alternate forms.
        reviewed_kanji: Kanji whose readings should receive rt.known.

    Returns:
        Ruby HTML using Jisho's per-kanji mapping, or an aligned/grouped reading
        from its matching Other forms entry when the primary spelling differs.

    Raises:
        ValueError: The page has no matching spelling/reading or search entries
            have conflicting readings.
        requests.RequestException: The HTTP request fails; includes the word.
    """
    try:
        response = requests.get("https://jisho.org/word/" + word)
        word_page_missing = response.status_code == 404
        if word_page_missing:
            response = requests.get(
                "https://jisho.org/search/" + urllib.parse.quote(word, safe="")
            )
        response.raise_for_status()
    except requests.RequestException as error:
        raise requests.RequestException(
            f"Failed to fetch furigana for '{word}': {error}"
        ) from error

    soup = BeautifulSoup(response.text, "html.parser")

    if word_page_missing:
        return _render_search_furigana(soup, word, reviewed_kanji)

    wordhtml = soup.select_one("div.concept_light-representation")
    text_node = wordhtml.select_one("span.text") if wordhtml is not None else None
    if wordhtml is None or text_node is None:
        raise ValueError(f"Jisho returned no word representation for '{word}'.")

    characters = text_node.get_text().strip(" \n")
    if characters != word:
        concept = wordhtml.find_parent(class_="concept_light")
        readings = _other_form_readings(
            concept if isinstance(concept, Tag) else soup, word
        )
        if readings:
            return render_token_furigana(word, readings[0], reviewed_kanji)
        raise ValueError(
            f"Jisho displays '{characters}' instead of '{word}' and lists no "
            "reading for the requested spelling."
        )

    return _render_jisho_representation(wordhtml, characters, reviewed_kanji)


def _other_form_readings(concept: Tag, word: str) -> List[str]:
    readings: List[str] = []
    for form in concept.select(".meaning-meaning .break-unit"):
        match = re.fullmatch(r"(.+?)\s*【([^】]+)】", form.get_text(strip=True))
        if match and match.group(1).strip() == word:
            readings.append(match.group(2).strip())
    return readings


def _render_search_furigana(
    soup: BeautifulSoup, word: str, reviewed_kanji: Set[str]
) -> str:
    matches: List[List[str]] = []
    for concept in soup.select(".concept_light"):
        readings = _other_form_readings(concept, word)
        if readings:
            matches.append(readings)

    if not matches:
        raise ValueError(f"Jisho search lists no reading for the exact spelling '{word}'.")
    readings = {reading for match in matches for reading in match}
    if len(matches) > 1 and len(readings) > 1:
        raise ValueError(
            f"Jisho search has conflicting readings for '{word}': "
            + ", ".join(sorted(readings))
        )
    # A single entry may list pronunciation variants (よい/えい). As on a word
    # page, preserve its first-listed reading rather than guessing another one.
    return render_token_furigana(word, matches[0][0], reviewed_kanji)


def _render_jisho_representation(
    wordhtml: Tag, characters: str, reviewed_kanji: Set[str]
) -> str:
    furigana = [escape(i.text) for i in wordhtml.select("span.kanji")]

    kanji_chars = [c for c in characters if is_kanji(c)]

    # Fallback: apply full furigana to the whole word as one ruby
    if len(furigana) != len(kanji_chars):
        rt_class = (
            ' class="known"' if all(c in reviewed_kanji for c in kanji_chars) else ""
        )
        return f'<ruby>{escape(characters)}<rt{rt_class}>{"".join(furigana)}</rt></ruby>'

    # Match each kanji with its furigana; preserve other characters as plain text.
    result, furigana_idx = "", 0
    for c in characters:
        if is_kanji(c):
            rt_class = ' class="known"' if c in reviewed_kanji else ""
            result += f'<ruby>{c}<rt{rt_class}>{furigana[furigana_idx]}</rt></ruby>'
            furigana_idx += 1
        else:
            result += escape(c)

    return result


def fetch_kanji_summary(kanji: str) -> Optional[KanjiSummary]:
    """
    Fetch summary information for a kanji by scraping its Jisho kanji page.
    """

    if not kanji:
        return None

    encoded_kanji = urllib.parse.quote(kanji)
    url = f"{KANJI_BASE_URL}{encoded_kanji}{KANJI_DETAIL_SUFFIX}"

    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise Exception(
            f"Failed to fetch Kanji details for '{kanji}': {str(exc)}"
        ) from exc

    return _parse_kanji_summary_from_html(kanji, response.text)


def _parse_kanji_summary_from_html(kanji: str, html: str) -> Optional[KanjiSummary]:
    soup = BeautifulSoup(html, "html.parser")
    details = soup.select_one(KANJI_DETAIL_SELECTOR)
    if not details:
        return None

    meanings_el = details.select_one(".kanji-details__main-meanings")
    meanings_text = meanings_el.get_text(separator=",", strip=True) if meanings_el else ""
    meanings = [m.strip() for m in meanings_text.split(",") if m.strip()]

    readings_section = details.select_one(".kanji-details__main-readings") or details

    kun_readings = _extract_readings(readings_section, "kun_yomi")
    on_readings = _extract_readings(readings_section, "on_yomi")

    jlpt_el = details.select_one(".kanji_stats .jlpt strong")
    jlpt_value = _parse_jlpt_label(jlpt_el.get_text(strip=True) if jlpt_el else "")

    return KanjiSummary(
        kanji=kanji,
        meanings=meanings,
        kun_readings=kun_readings,
        on_readings=on_readings,
        jlpt=jlpt_value,
    )


def _extract_readings(details_node: Tag, class_name: str) -> List[str]:
    selector = f"dl.dictionary_entry.{class_name} dd"
    node = details_node.select_one(selector)
    if not node:
        return []

    links = node.select("a")
    if links:
        return [link.get_text(strip=True) for link in links if link.get_text(strip=True)]

    text = node.get_text(separator=" ", strip=True)
    if not text:
        return []
    # Some readings are separated by 、 or commas
    candidates: List[str] = []
    for chunk in text.replace("、", ",").split(","):
        stripped = chunk.strip()
        if stripped and stripped.lower() not in {"kun", "on"}:
            candidates.append(stripped)
    return candidates



def _parse_jlpt_label(label: str) -> int:
    if not label:
        return 0
    normalized = label.strip().upper()
    if normalized.startswith("N"):
        try:
            return int(normalized[1:])
        except ValueError:
            return 0
    return 0


def search_words_containing_kanji(kanji: str) -> List[JishoWord]:
    """
    Search for words containing the given Kanji character using the Jisho API.

    Use the first Japanese form containing the target kanji and its reading,
    returning at most one word per dictionary entry.

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

        # A matching spelling may follow a kana-only or alternative form.
        japanese_data = next(
            (
                form
                for form in item["japanese"]
                if kanji in form.get("word", form.get("reading", ""))
            ),
            None,
        )
        if japanese_data is None:
            continue

        word = japanese_data.get("word", japanese_data.get("reading", ""))
        reading = japanese_data.get("reading", "")

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
