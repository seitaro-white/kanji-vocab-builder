"""Source-preserving contracts for shared native Sudachi analysis."""

from itertools import pairwise

import pytest

from kanji_vocab_miner.japanese_tokenizer import tokenize_japanese


def test_native_tokens_expose_source_offsets_readings_and_named_pos() -> None:
    source = "  国家公務員\r\n山田 食べました  "
    tokens = list(tokenize_japanese(source))
    lexical = [token for token in tokens if token.part_of_speech.category != "空白"]

    assert [token.surface for token in lexical] == [
        "国家公務員", "山田", "食べ", "まし", "た"
    ]
    assert lexical[0].reading == "コッカコウムイン"
    assert lexical[1].part_of_speech.subclass == "人名"
    assert lexical[2].dictionary_form == "食べる"
    assert lexical[2].part_of_speech.conjugation_form == "連用形-一般"
    assert all(source[token.start:token.end] == token.surface for token in tokens)
    assert "".join(token.surface for token in tokens) == source


@pytest.mark.parametrize("character", ["あ", "㍻", "㌖", "😀"])
def test_long_input_preserves_absolute_offsets_and_every_character(character: str) -> None:
    source = "猫。\r\n" + character * 50_000 + "\n\n\n犬  "
    tokens = list(tokenize_japanese(source))

    assert "".join(token.surface for token in tokens) == source
    assert tokens[0].start == 0
    assert tokens[-1].end == len(source)
    assert all(left.end == right.start for left, right in pairwise(tokens))
    assert all(source[token.start:token.end] == token.surface for token in tokens)


def test_oov_has_no_fabricated_reading() -> None:
    tokens = list(tokenize_japanese("𠮷𠮷"))
    assert [(token.surface, token.reading) for token in tokens] == [("𠮷𠮷", None)]


def test_empty_input_has_no_tokens() -> None:
    assert list(tokenize_japanese("")) == []
