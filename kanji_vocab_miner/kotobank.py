import re
import time
from typing import Callable, List, Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from pydantic import BaseModel


class JapaneseDefinition(BaseModel):
    expression: str
    senses: List[str]
    source_name: str
    source_url: str


class KotobankDefinitionNotFound(Exception):
    def __init__(self, expression: str, url: str) -> None:
        """Create an error for a page without a supported definition."""
        self.expression = expression
        self.url = url
        super().__init__(
            f"No supported Kotobank definition for '{expression}' at {url}"
        )


class KotobankParseError(Exception):
    def __init__(self, expression: str, url: str) -> None:
        """Create an error for an unusable supported dictionary article."""
        self.expression = expression
        self.url = url
        super().__init__(
            f"Could not parse Kotobank definition for '{expression}' at {url}"
        )


class KotobankRequestError(Exception):
    def __init__(self, expression: str, url: str, reason: str) -> None:
        """Create an error for a failed Kotobank request."""
        self.expression = expression
        self.url = url
        super().__init__(
            f"Kotobank request failed for '{expression}' at {url}: {reason}"
        )


class KotobankClient:
    def __init__(
        self,
        session: Optional[requests.Session] = None,
        timeout: tuple[float, float] = (3.05, 10.0),
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Create a Kotobank client with a pooled HTTP session."""
        self.session = session or requests.Session()
        self.timeout = timeout
        self.sleep = sleep
        self.session.headers.update(
            {"User-Agent": "kanji-vocab-miner/0.1 Kotobank personal-use lookup"}
        )

    def lookup(self, expression: str) -> JapaneseDefinition:
        """Fetch and parse a Japanese definition for an expression."""

        url = f"https://kotobank.jp/word/{quote(expression, safe='')}"

        # Retry twice before giving up
        for attempt in range(2):
            try:
                response = self.session.get(url, timeout=self.timeout)
                is_transient_status = (
                    response.status_code == 429 or response.status_code >= 500
                )
                if is_transient_status and attempt == 0:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        self.sleep(min(float(retry_after), 5.0))
                    continue
                response.raise_for_status()

                # Return
                return parse_kotobank_html(expression, url, response.text)

            except (requests.Timeout, requests.ConnectionError) as error:
                if attempt == 1:
                    raise KotobankRequestError(expression, url, str(error)) from error
            except requests.RequestException as error:
                raise KotobankRequestError(expression, url, str(error)) from error
        raise KotobankRequestError(expression, url, "retry exhausted")


def _normalized_text(node: Tag) -> str:
    """Return normalized definition text without excluded content."""
    excluded_selectors = (
        "script, style, .ad, .pc-word-ad, .source, .example, .examples, "
        "ol ol, ol ul, ul ol, ul ul"
    )
    for excluded in node.select(excluded_selectors):
        excluded.decompose()
    return re.sub(r"\s+", " ", node.get_text("")).strip()


def _split_numbered_senses(text: str) -> list[str]:
    """Split the first two full-width numbered meanings in flattened text."""
    if not re.match(r"^１\s", text):
        return [text]
    return re.split(r"(?=２\s)", text, maxsplit=1)


def parse_kotobank_html(
    expression: str,
    requested_url: str,
    html: str,
) -> JapaneseDefinition:
    """Extract a Japanese definition from a Kotobank word page."""

    soup = BeautifulSoup(html, "html.parser")

    # The two different dictionary definitions that we prefer to use
    sources = (
        ("article.dictype.daijisen", "デジタル大辞泉"),
        ("article.dictype.nikkokuseisen", "精選版 日本国語大辞典"),
    )

    supported_article_found = False

    for selector, source_name in sources:
        article = soup.select_one(selector)
        if not article:
            continue

        supported_article_found = True
        description = article.select_one("section.description")

        if not description:
            continue
        ordered_list = description.find("ol", recursive=False)

        if ordered_list:
            sense_nodes = ordered_list.find_all("li", recursive=False)[:2]
        else:
            sense_nodes = [description]

        senses = []
        for node in sense_nodes:
            text = _normalized_text(node)
            if text:
                senses.extend(_split_numbered_senses(text))
            if len(senses) >= 2:
                break
        senses = senses[:2]

        if not senses:
            continue

        canonical = soup.select_one('link[rel="canonical"]')
        source_url = canonical.get("href") if canonical else requested_url
        return JapaneseDefinition(
            expression=expression,
            senses=senses,
            source_name=source_name,
            source_url=source_url,
        )
    if supported_article_found:
        raise KotobankParseError(expression, requested_url)
    raise KotobankDefinitionNotFound(expression, requested_url)
