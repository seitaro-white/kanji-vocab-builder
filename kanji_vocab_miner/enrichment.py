"""Structured LLM enrichment for vocabulary notes."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from html import escape
import json
from pathlib import Path
import time
from typing import Any, Callable, List, Optional, Protocol

from pydantic import BaseModel, ConfigDict, field_validator, model_validator
import requests

from kanji_vocab_miner.jisho import JishoWord
from kanji_vocab_miner.vocab_models import PendingVocabItem

DEEPSEEK_RESPONSES_ENDPOINT = "https://api.deepseek.com/responses"
DEEPSEEK_MODEL = "deepseek-flash"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_ATTEMPTS = 3
FIXED_INSTRUCTIONS = """Return only structured JSON matching the supplied schema.
Ground all content in the supplied primary dictionary sense and part of speech.
Write one concise English nuance sentence beyond the short definition.
Write one short, natural Japanese example adapted to the word's difficulty. Return
both the plain-text sentence and the exact surface form occurring in it. Do not
include a translation, reading, HTML, or Markdown.
Explain why the word uses its kanji, covering compound components, kanji with
okurigana, or a single kanji as applicable. If the word has no kanji, state that
plainly. All fields must be non-empty plain text.
"""


class VocabEnrichment(BaseModel):
    """Validated plain-text enrichment returned by the provider."""

    model_config = ConfigDict(extra="forbid")

    nuance: str
    example_sentence: str
    example_target: str
    kanji_explanation: str

    @field_validator("nuance", "example_sentence", "example_target", "kanji_explanation")
    @classmethod
    def trim_non_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def target_occurs_in_sentence(self) -> "VocabEnrichment":
        if self.example_target not in self.example_sentence:
            raise ValueError("example_target must occur in example_sentence")
        return self


class EnrichmentError(RuntimeError):
    """Raised when vocabulary enrichment fails after all attempts."""


class HTTPTransport(Protocol):
    """Minimal requests-compatible transport used by the client."""

    def post(self, url: str, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class EnrichmentOutcome:
    """The success or failure produced for one pending item."""

    item: PendingVocabItem
    enrichment: Optional[VocabEnrichment] = None
    error: Optional[EnrichmentError] = None

    @property
    def is_success(self) -> bool:
        return self.enrichment is not None


def render_example(enrichment: VocabEnrichment) -> str:
    """Escape an example and highlight only its first exact target occurrence."""
    prefix, target, suffix = enrichment.example_sentence.partition(
        enrichment.example_target
    )
    return (
        f'{escape(prefix)}<strong class="example-target">{escape(target)}</strong>'
        f"{escape(suffix)}"
    )


class DeepSeekEnrichmentClient:
    """Generate validated vocabulary enrichment via DeepSeek Responses API."""

    def __init__(
        self,
        api_key: str,
        prompt_path: Path,
        *,
        transport: HTTPTransport = requests,
        endpoint: str = DEEPSEEK_RESPONSES_ENDPOINT,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        attempts: int = DEFAULT_ATTEMPTS,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key
        self.prompt_path = Path(prompt_path)
        self.transport = transport
        self.endpoint = endpoint
        self.timeout = timeout
        self.attempts = attempts
        self.sleeper = sleeper

    def generate(self, word: JishoWord) -> VocabEnrichment:
        """Generate enrichment for a word, retrying transient/invalid responses."""
        user_prompt = self.prompt_path.read_text(encoding="utf-8").strip()
        base_input = self._build_input(user_prompt, word)
        correction = ""
        last_problem = "unknown provider response"

        for attempt in range(self.attempts):
            try:
                response = self.transport.post(
                    self.endpoint,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=self._request_body(base_input + correction),
                    timeout=self.timeout,
                )
                response.raise_for_status()
                payload = response.json()
                output_text = self._extract_output_text(payload)
                return VocabEnrichment.model_validate_json(output_text)
            except Exception as exc:
                last_problem = self._safe_problem(exc)
                if attempt == self.attempts - 1:
                    break
                correction = (
                    "\n\nCorrection: The previous response was invalid: "
                    f"{last_problem}. Return a corrected response matching the contract."
                )
                self.sleeper(0.25 * (2**attempt))

        raise EnrichmentError(
            f"Enrichment failed after {self.attempts} attempts: {last_problem}"
        )

    def _request_body(self, input_text: str) -> dict[str, Any]:
        schema = VocabEnrichment.model_json_schema()
        return {
            "model": DEEPSEEK_MODEL,
            "instructions": FIXED_INSTRUCTIONS,
            "input": input_text,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "vocab_enrichment",
                    "strict": True,
                    "schema": schema,
                }
            },
        }

    @staticmethod
    def _build_input(user_prompt: str, word: JishoWord) -> str:
        definition = word.definitions[0] if word.definitions else ""
        part_of_speech = (
            word.parts_of_speech[0] if word.parts_of_speech else "not provided"
        )
        return (
            f"{user_prompt}\n\nWord context:\n"
            f"Expression: {word.expression}\n"
            f"Kana reading: {word.kana}\n"
            f"Primary definition: {definition}\n"
            f"Primary part of speech: {part_of_speech}"
        )

    @staticmethod
    def _extract_output_text(payload: Any) -> str:
        if not isinstance(payload, dict):
            raise ValueError("response envelope is not an object")
        direct = payload.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct
        output = payload.get("output")
        if isinstance(output, list):
            for item in output:
                if not isinstance(item, dict):
                    continue
                content = item.get("content")
                if not isinstance(content, list):
                    continue
                for part in content:
                    if (
                        isinstance(part, dict)
                        and part.get("type") == "output_text"
                        and isinstance(part.get("text"), str)
                        and part["text"].strip()
                    ):
                        return part["text"]
        raise ValueError("response contains no output text")

    def _safe_problem(self, exc: Exception) -> str:
        if isinstance(exc, requests.RequestException):
            problem = "provider request failed"
        elif isinstance(exc, json.JSONDecodeError):
            problem = "output was not valid JSON"
        else:
            problem = str(exc).replace(self.api_key, "[redacted]")
        return " ".join(problem.split())[:400]


def generate_enrichments(
    items: List[PendingVocabItem],
    client: DeepSeekEnrichmentClient,
    max_workers: int,
    on_complete: Optional[Callable[[PendingVocabItem], None]] = None,
) -> List[EnrichmentOutcome]:
    """Generate enrichments concurrently and return outcomes in input order."""
    if max_workers < 1:
        raise ValueError("max_workers must be positive")

    outcomes: List[Optional[EnrichmentOutcome]] = [None] * len(items)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_indexes = {
            executor.submit(client.generate, item.word): index
            for index, item in enumerate(items)
        }
        for future in as_completed(future_indexes):
            index = future_indexes[future]
            item = items[index]
            try:
                enrichment = future.result()
                outcome = EnrichmentOutcome(item=item, enrichment=enrichment)
            except EnrichmentError as exc:
                outcome = EnrichmentOutcome(item=item, error=exc)
            except Exception:
                outcome = EnrichmentOutcome(
                    item=item,
                    error=EnrichmentError("Unexpected enrichment worker failure"),
                )
            outcomes[index] = outcome
            if on_complete is not None:
                on_complete(item)

    return [outcome for outcome in outcomes if outcome is not None]
