from unittest.mock import MagicMock

import pytest
import requests

from kanji_vocab_miner.kotobank import (
    JapaneseDefinition,
    KotobankClient,
    KotobankDefinitionNotFound,
    KotobankParseError,
    KotobankRequestError,
    parse_kotobank_html,
)


def test_parse_daijisen_unnumbered_definition() -> None:
    """Return one normalized sense from an unnumbered Daijisen article."""
    html = """
    <html>
      <head><link rel="canonical" href="https://kotobank.jp/word/example-1"></head>
      <body>
        <article class="dictype daijisen">
          <section class="description"> 学校へ 通う。 </section>
        </article>
      </body>
    </html>
    """

    result = parse_kotobank_html(
        expression="学校",
        requested_url="https://kotobank.jp/word/%E5%AD%A6%E6%A0%A1",
        html=html,
    )

    assert result == JapaneseDefinition(
        expression="学校",
        senses=["学校へ 通う。"],
        source_name="デジタル大辞泉",
        source_url="https://kotobank.jp/word/example-1",
    )


def test_parse_first_two_top_level_daijisen_senses() -> None:
    """Return only the first two top-level Daijisen senses."""
    html = """
    <article class="dictype daijisen">
      <section class="description">
        <ol>
          <li>第一の意味。</li>
          <li>第二の意味。</li>
          <li>第三の意味。</li>
        </ol>
      </section>
    </article>
    """

    result = parse_kotobank_html("語", "https://kotobank.jp/word/%E8%AA%9E", html)

    assert result.senses == ["第一の意味。", "第二の意味。"]


def test_splits_full_width_numbered_definitions_in_one_node() -> None:
    """Split numbered meanings when Kotobank does not use separate list items."""
    html = """
    <article class="dictype daijisen">
      <section class="description">
        １ 第一の意味。「用例」２ 第二の意味。「別の用例」
      </section>
    </article>
    """

    result = parse_kotobank_html("語", "https://kotobank.jp/word/%E8%AA%9E", html)

    assert result.senses == [
        "１ 第一の意味。「用例」",
        "２ 第二の意味。「別の用例」",
    ]


def test_nested_examples_do_not_become_senses() -> None:
    """Exclude nested example lists from extracted senses."""
    html = """
    <article class="dictype daijisen">
      <section class="description">
        <ol>
          <li>第一の意味。<ol><li>古い用例。</li></ol></li>
          <li>第二の意味。</li>
        </ol>
      </section>
    </article>
    """

    result = parse_kotobank_html("語", "https://kotobank.jp/word/%E8%AA%9E", html)

    assert result.senses == ["第一の意味。", "第二の意味。"]


def test_parse_seisenban_fallback() -> None:
    """Use Seisenban when a Daijisen article is absent."""
    html = """
    <article class="dictype nikkokuseisen">
      <section class="description">精選版の意味。</section>
    </article>
    """

    result = parse_kotobank_html("語", "https://kotobank.jp/word/%E8%AA%9E", html)

    assert result.senses == ["精選版の意味。"]
    assert result.source_name == "精選版 日本国語大辞典"


def test_daijisen_wins_when_both_sources_exist() -> None:
    """Prefer Daijisen when both supported dictionaries are present."""
    html = """
    <article class="dictype nikkokuseisen">
      <section class="description">精選版の意味。</section>
    </article>
    <article class="dictype daijisen">
      <section class="description">大辞泉の意味。</section>
    </article>
    """

    result = parse_kotobank_html("語", "https://kotobank.jp/word/%E8%AA%9E", html)

    assert result.senses == ["大辞泉の意味。"]
    assert result.source_name == "デジタル大辞泉"


def test_unsupported_page_returns_not_found() -> None:
    """Reject a page containing only unsupported encyclopedia articles."""
    html = """
    <article class="dictype nipponica">
      <section class="description">百科事典の意味。</section>
    </article>
    """

    with pytest.raises(KotobankDefinitionNotFound) as error:
        parse_kotobank_html("語", "https://kotobank.jp/word/%E8%AA%9E", html)

    assert error.value.expression == "語"
    assert error.value.url == "https://kotobank.jp/word/%E8%AA%9E"


def test_normalizes_inline_text_and_removes_non_definition_content() -> None:
    """Normalize inline text while removing source, ad, and example blocks."""
    html = """
    <article class="dictype daijisen">
      <section class="description">
        第一の <a href="/word/意味">意味</a>。\n 次の文。
        <div class="pc-word-ad">広告</div>
        <p class="source">出典情報</p>
        <div class="example">使用例</div>
      </section>
    </article>
    """

    result = parse_kotobank_html("語", "https://kotobank.jp/word/%E8%AA%9E", html)

    assert result.senses == ["第一の 意味。 次の文。"]


def test_requested_url_is_used_without_canonical_link() -> None:
    """Retain the requested URL when the page has no canonical link."""
    requested_url = "https://kotobank.jp/word/%E3%81%99%E3%81%94%E3%81%84"
    html = """
    <article class="dictype daijisen">
      <section class="description">程度がはなはだしい。</section>
    </article>
    """

    result = parse_kotobank_html("すごい", requested_url, html)

    assert result.source_url == requested_url


def test_unusable_daijisen_falls_back_to_seisenban() -> None:
    """Use Seisenban when the Daijisen article has no usable text."""
    html = """
    <article class="dictype daijisen">
      <section class="description">   </section>
    </article>
    <article class="dictype nikkokuseisen">
      <section class="description">精選版の意味。</section>
    </article>
    """

    result = parse_kotobank_html("語", "https://kotobank.jp/word/%E8%AA%9E", html)

    assert result.senses == ["精選版の意味。"]
    assert result.source_name == "精選版 日本国語大辞典"


@pytest.mark.parametrize(
    "description_html",
    ["", '<section class="description">   </section>'],
)
def test_malformed_supported_article_returns_parse_error(
    description_html: str,
) -> None:
    """Classify missing or empty supported descriptions as parse errors."""
    requested_url = "https://kotobank.jp/word/%E8%AA%9E"
    html = f'<article class="dictype daijisen">{description_html}</article>'

    with pytest.raises(KotobankParseError) as error:
        parse_kotobank_html("語", requested_url, html)

    assert error.value.expression == "語"
    assert error.value.url == requested_url


def test_timeout_is_retried_once_then_returns_definition() -> None:
    """Retry one timeout before returning a successful definition."""
    response = MagicMock()
    response.status_code = 200
    response.text = """
    <article class="dictype daijisen">
      <section class="description">学校の意味。</section>
    </article>
    """
    session = MagicMock()
    session.get.side_effect = [requests.Timeout("slow"), response]
    client = KotobankClient(session=session)

    result = client.lookup("学校")

    assert result.senses == ["学校の意味。"]
    assert session.get.call_count == 2


def test_exhausted_timeout_retry_returns_request_error() -> None:
    """Classify two consecutive timeouts as a request error."""
    session = MagicMock()
    session.get.side_effect = requests.Timeout("slow")
    client = KotobankClient(session=session)

    with pytest.raises(KotobankRequestError) as error:
        client.lookup("学校")

    assert session.get.call_count == 2
    assert error.value.expression == "学校"
    assert error.value.url == "https://kotobank.jp/word/%E5%AD%A6%E6%A0%A1"


def test_non_retryable_http_error_is_not_retried() -> None:
    """Classify an ordinary HTTP 4xx response without retrying it."""
    response = MagicMock()
    response.status_code = 404
    response.raise_for_status.side_effect = requests.HTTPError("not found")
    session = MagicMock()
    session.get.return_value = response
    client = KotobankClient(session=session)

    with pytest.raises(KotobankRequestError) as error:
        client.lookup("不存在")

    assert session.get.call_count == 1
    assert "not found" in str(error.value)


def test_rate_limit_retries_once_after_bounded_retry_after() -> None:
    """Honor a bounded Retry-After delay before retrying HTTP 429."""
    rate_limited = MagicMock()
    rate_limited.status_code = 429
    rate_limited.headers = {"Retry-After": "2"}
    success = MagicMock()
    success.status_code = 200
    success.text = """
    <article class="dictype daijisen">
      <section class="description">意味。</section>
    </article>
    """
    session = MagicMock()
    session.get.side_effect = [rate_limited, success]
    sleep = MagicMock()
    client = KotobankClient(session=session, sleep=sleep)

    result = client.lookup("語")

    assert result.senses == ["意味。"]
    sleep.assert_called_once_with(2.0)


def test_server_error_is_retried_once() -> None:
    """Retry one HTTP 5xx response before returning a definition."""
    server_error = MagicMock()
    server_error.status_code = 503
    server_error.headers = {}
    success = MagicMock()
    success.status_code = 200
    success.text = """
    <article class="dictype daijisen">
      <section class="description">意味。</section>
    </article>
    """
    session = MagicMock()
    session.get.side_effect = [server_error, success]
    client = KotobankClient(session=session)

    result = client.lookup("語")

    assert result.senses == ["意味。"]
    assert session.get.call_count == 2


@pytest.mark.parametrize(
    "expression, encoded_expression",
    [
        ("学校", "%E5%AD%A6%E6%A0%A1"),
        ("すごい", "%E3%81%99%E3%81%94%E3%81%84"),
    ],
)
def test_lookup_percent_encodes_kanji_and_kana(
    expression: str,
    encoded_expression: str,
) -> None:
    """Percent-encode kanji and kana in direct word lookup URLs."""
    response = MagicMock()
    response.status_code = 200
    response.text = """
    <article class="dictype daijisen">
      <section class="description">意味。</section>
    </article>
    """
    session = MagicMock()
    session.get.return_value = response
    client = KotobankClient(session=session)

    client.lookup(expression)

    session.get.assert_called_once_with(
        f"https://kotobank.jp/word/{encoded_expression}",
        timeout=(3.05, 10.0),
    )
