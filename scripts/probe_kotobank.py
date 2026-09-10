import argparse
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from kanji_vocab_miner.kotobank import (
    KotobankClient,
    KotobankDefinitionNotFound,
    KotobankParseError,
    KotobankRequestError,
)


@dataclass
class ProbeResult:
    expression: str
    outcome: str
    source: str
    sense_count: int
    url: str
    elapsed_seconds: float
    preview: str


def parse_args() -> argparse.Namespace:
    """Parse expressions, an optional word file, and the batch delay."""
    parser = argparse.ArgumentParser(description="Probe Kotobank word definitions")
    parser.add_argument("expressions", nargs="*")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--delay", type=float, default=0.5)
    return parser.parse_args()


def load_expressions(expressions: List[str], file_path: Optional[Path]) -> List[str]:
    """Return command-line expressions followed by nonblank file entries."""
    if file_path is None:
        return expressions
    file_expressions = [
        line.strip() for line in file_path.read_text(encoding="utf-8").splitlines()
    ]
    return expressions + [expression for expression in file_expressions if expression]


def probe_expression(client: KotobankClient, expression: str) -> ProbeResult:
    """Probe one expression and return its bounded display result."""
    started_at = time.perf_counter()
    try:
        definition = client.lookup(expression)
    except KotobankDefinitionNotFound as error:
        outcome, source, sense_count, url, preview = (
            "not-found",
            "-",
            0,
            error.url,
            str(error),
        )
    except KotobankParseError as error:
        outcome, source, sense_count, url, preview = (
            "parse-error",
            "-",
            0,
            error.url,
            str(error),
        )
    except KotobankRequestError as error:
        outcome, source, sense_count, url, preview = (
            "request-error",
            "-",
            0,
            error.url,
            str(error),
        )
    else:
        outcome = "success"
        source = definition.source_name
        sense_count = len(definition.senses)
        url = definition.source_url
        preview = " / ".join(definition.senses)
    return ProbeResult(
        expression=expression,
        outcome=outcome,
        source=source,
        sense_count=sense_count,
        url=url,
        elapsed_seconds=time.perf_counter() - started_at,
        preview=preview[:120],
    )


def print_result(result: ProbeResult) -> None:
    """Print one compact probe result row."""
    print(
        f"{result.expression} | {result.outcome} | {result.source} | "
        f"{result.sense_count} | {result.url} | "
        f"{result.elapsed_seconds:.2f}s | {result.preview}"
    )


def print_summary(results: List[ProbeResult]) -> None:
    """Print outcome counts and the observed latency range."""
    outcomes = Counter(result.outcome for result in results)
    counts = ", ".join(
        f"{outcome}={count}" for outcome, count in sorted(outcomes.items())
    )
    latencies = [result.elapsed_seconds for result in results]
    print(f"Summary | total={len(results)} | {counts}")
    print(
        f"Latency | min={min(latencies):.2f}s | max={max(latencies):.2f}s | "
        f"avg={sum(latencies) / len(latencies):.2f}s"
    )


def main() -> int:
    """Run a polite, non-persistent Kotobank probe batch."""
    args = parse_args()
    expressions = load_expressions(args.expressions, args.file)
    if not expressions:
        raise SystemExit("Provide expressions or --file")
    client = KotobankClient()
    results = []
    for index, expression in enumerate(expressions):
        result = probe_expression(client, expression)
        results.append(result)
        print_result(result)
        if index < len(expressions) - 1:
            time.sleep(args.delay)
    print_summary(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
