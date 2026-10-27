"""Read-only Anki kanji loading, with HTTP mocked (no running Anki required)."""

from types import SimpleNamespace

import pytest
import requests

from kanji_vocab_miner import config
from kanji_vocab_miner.anki import connect


def test_reader_can_request_strict_kanji_loading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        config,
        "_config",
        SimpleNamespace(
            kanji_deck=SimpleNamespace(name="Kanji"),
            ankiconnect=SimpleNamespace(url="http://unused.invalid"),
        ),
    )

    def unavailable(*args: object, **kwargs: object) -> None:
        raise requests.ConnectionError("Anki unavailable")

    monkeypatch.setattr(requests, "post", unavailable)
    with pytest.raises(Exception, match="Failed to connect to Anki"):
        connect.get_reviewed_kanji(should_raise=True)
    # Other callers retain their existing best-effort behavior.
    assert connect.get_reviewed_kanji() == set()
