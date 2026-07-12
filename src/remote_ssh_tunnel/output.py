# SPDX-License-Identifier: MIT

from __future__ import annotations

import codecs
import unicodedata


class SafeOutputRenderer:
    """Render remote bytes without allowing terminal control sequences."""

    def __init__(self) -> None:
        self._decoder = codecs.getincrementaldecoder("utf-8")("backslashreplace")

    def feed(self, data: bytes, *, final: bool = False) -> str:
        text = self._decoder.decode(data, final=final)
        rendered: list[str] = []
        for character in text:
            if character in "\t\r\n":
                rendered.append(character)
                continue

            codepoint = ord(character)
            category = unicodedata.category(character)
            if category in {"Cc", "Cf"}:
                if codepoint <= 0xFF:
                    rendered.append(f"\\x{codepoint:02x}")
                elif codepoint <= 0xFFFF:
                    rendered.append(f"\\u{codepoint:04x}")
                else:
                    rendered.append(f"\\U{codepoint:08x}")
                continue
            rendered.append(character)
        return "".join(rendered)
