# SPDX-License-Identifier: MIT

from remote_ssh_tunnel.output import SafeOutputRenderer


def test_escapes_terminal_controls_and_invalid_utf8() -> None:
    renderer = SafeOutputRenderer()

    rendered = renderer.feed(b"before\x1b]0;owned\x07after\xff", final=True)

    assert rendered == r"before\x1b]0;owned\x07after\xff"


def test_preserves_text_newlines_and_split_utf8() -> None:
    renderer = SafeOutputRenderer()

    first = renderer.feed(b"line\n\xe3\x81")
    second = renderer.feed(b"\x82\n", final=True)

    assert first == "line\n"
    assert second == "\u3042\n"


def test_escapes_unicode_format_controls() -> None:
    renderer = SafeOutputRenderer()

    rendered = renderer.feed("left\u202eright".encode(), final=True)

    assert rendered == r"left\u202eright"
