import re
import time
from collections.abc import Iterable, Sequence
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


class KotobankAmbiguousDefinitionError(Exception):
    def __init__(self, expression: str, urls: Iterable[str]) -> None:
        """Reject multiple distinct pages verifying the requested spelling."""
        super().__init__(
            f"Ambiguous Kotobank definition for '{expression}': {', '.join(urls)}"
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


class KotobankPageNotFound(KotobankRequestError):
    """A Kotobank request failed specifically because the page returned HTTP 404."""


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

    def lookup(
        self, expression: str, candidate_spellings: Sequence[str] = ()
    ) -> JapaneseDefinition:
        """Try supplied siblings only after a 404 or unsupported direct page.

        A sibling must list the exact requested spelling in a supported article's
        headword. Missing or ambiguous verified pages remain failures.
        """
        url = f"https://kotobank.jp/word/{quote(expression, safe='')}"
        try:
            response = self._get(expression, url)
            return parse_kotobank_html(expression, url, response.text)
        except (KotobankPageNotFound, KotobankDefinitionNotFound) as error:
            return self._lookup_siblings(expression, candidate_spellings, error)

    def _get(self, expression: str, url: str) -> requests.Response:
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

                return response

            except (requests.Timeout, requests.ConnectionError) as error:
                if attempt == 1:
                    raise KotobankRequestError(expression, url, str(error)) from error
            except requests.HTTPError as error:
                if error.response is not None and error.response.status_code == 404:
                    raise KotobankPageNotFound(expression, url, str(error)) from error
                raise KotobankRequestError(expression, url, str(error)) from error
            except requests.RequestException as error:
                raise KotobankRequestError(expression, url, str(error)) from error
        raise KotobankRequestError(expression, url, "retry exhausted")

    def _lookup_siblings(
        self,
        expression: str,
        candidate_spellings: Sequence[str],
        original_error: Exception,
    ) -> JapaneseDefinition:
        verified: dict[str, JapaneseDefinition] = {}
        for spelling in candidate_spellings:
            url = f"https://kotobank.jp/word/{quote(spelling, safe='')}"
            try:
                response = self._get(expression, url)
            except KotobankPageNotFound:
                continue
            try:
                definition = parse_kotobank_html(
                    expression, url, response.text, listed_spelling=expression
                )
            except KotobankDefinitionNotFound:
                continue
            verified[definition.source_url] = definition
        if len(verified) > 1:
            raise KotobankAmbiguousDefinitionError(expression, verified)
        if not verified:
            raise original_error
        return next(iter(verified.values()))


def _headword_matches(headword: str, expression: str) -> bool:
    notation = re.search(r"【([^】]+)】", headword)
    if not notation:
        return False
    variants = re.split(r"[／・]", notation.group(1))
    return any(
        expression == variant.replace("▽", "").replace("×", "")
        for variant in variants
    )


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
    listed_spelling: str | None = None,
) -> JapaneseDefinition:
    """Extract a definition, optionally requiring a spelling in its headword."""

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

        if listed_spelling is not None:
            heading = article.select_one("h3")
            if not heading or not _headword_matches(
                heading.get_text("", strip=True), listed_spelling
            ):
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
