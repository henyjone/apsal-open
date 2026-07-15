"""Small, dependency-free parser for the safe APSAL YAML 1.2 subset.

APSAL authoring YAML supports indentation-based mappings and sequences plus JSON
scalar types. It deliberately rejects tags, anchors, aliases, merge keys, tabs,
duplicate keys and multi-document streams. Canonical artifacts are always JSON.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


class YamlError(ValueError):
    pass


@dataclass(frozen=True)
class _Line:
    number: int
    indent: int
    content: str


_NUMBER = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$")
_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")


def _strip_comment(raw: str) -> str:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(raw):
        if escaped:
            escaped = False
            continue
        if quote == '"' and char == "\\":
            escaped = True
            continue
        if char in {'"', "'"}:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
            continue
        if char == "#" and quote is None and (index == 0 or raw[index - 1].isspace()):
            return raw[:index].rstrip()
    if quote is not None:
        raise YamlError("unterminated quoted scalar")
    return raw.rstrip()


def _tokenize(text: str) -> list[_Line]:
    lines: list[_Line] = []
    document_marker_seen = False
    for number, raw in enumerate(text.splitlines(), 1):
        if "\t" in raw:
            raise YamlError(f"line {number}: tabs are not allowed")
        content = _strip_comment(raw)
        if not content.strip():
            continue
        stripped = content.strip()
        if stripped == "---" and not lines and not document_marker_seen:
            document_marker_seen = True
            continue
        if stripped in {"---", "..."} or stripped.startswith("%YAML"):
            raise YamlError(f"line {number}: multiple documents and directives are not allowed")
        indent = len(content) - len(content.lstrip(" "))
        if indent % 2:
            raise YamlError(f"line {number}: indentation must use multiples of two spaces")
        value = content[indent:]
        if value.startswith("<<:"):
            raise YamlError(f"line {number}: merge keys are not allowed")
        lines.append(_Line(number, indent, value))
    if not lines:
        raise YamlError("empty YAML document")
    return lines


def _split_mapping(line: _Line, content: str | None = None) -> tuple[str, str]:
    value = line.content if content is None else content
    quote: str | None = None
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if quote == '"' and char == "\\":
            escaped = True
            continue
        if char in {'"', "'"}:
            quote = None if quote == char else char if quote is None else quote
            continue
        if char == ":" and quote is None:
            key = value[:index].strip()
            rest = value[index + 1 :].strip()
            if not _KEY.fullmatch(key):
                raise YamlError(f"line {line.number}: unsupported mapping key {key!r}")
            return key, rest
    raise YamlError(f"line {line.number}: expected a mapping entry")


def _scalar(line: _Line, text: str) -> Any:
    if not text:
        raise YamlError(f"line {line.number}: missing scalar")
    if text[0] in "&*!":
        raise YamlError(f"line {line.number}: anchors, aliases and custom tags are not allowed")
    if re.search(r"(?:^|\s)[&*!][A-Za-z0-9_-]+", text):
        raise YamlError(f"line {line.number}: anchors, aliases and custom tags are not allowed")
    if text == "null" or text == "~":
        return None
    if text == "true":
        return True
    if text == "false":
        return False
    if text.startswith('"'):
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise YamlError(f"line {line.number}: invalid quoted string: {exc.msg}") from exc
        if not isinstance(value, str):
            raise YamlError(f"line {line.number}: expected a quoted string")
        return value
    if text.startswith("'"):
        if len(text) < 2 or not text.endswith("'"):
            raise YamlError(f"line {line.number}: unterminated single-quoted string")
        return text[1:-1].replace("''", "'")
    if text.startswith(("[", "{")):
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise YamlError(f"line {line.number}: inline collections must use JSON syntax") from exc
    if _NUMBER.fullmatch(text):
        return float(text) if any(c in text for c in ".eE") else int(text)
    return text


class _Parser:
    def __init__(self, lines: list[_Line]):
        self.lines = lines

    def parse(self) -> Any:
        value, index = self._block(0, self.lines[0].indent)
        if index != len(self.lines):
            line = self.lines[index]
            raise YamlError(f"line {line.number}: unexpected indentation")
        return value

    def _block(self, index: int, indent: int) -> tuple[Any, int]:
        line = self.lines[index]
        if line.indent != indent:
            raise YamlError(f"line {line.number}: unexpected indentation")
        return self._sequence(index, indent) if line.content == "-" or line.content.startswith("- ") else self._mapping(index, indent)

    def _mapping(self, index: int, indent: int) -> tuple[dict[str, Any], int]:
        result: dict[str, Any] = {}
        while index < len(self.lines):
            line = self.lines[index]
            if line.indent < indent:
                break
            if line.indent > indent:
                raise YamlError(f"line {line.number}: unexpected indentation")
            if line.content == "-" or line.content.startswith("- "):
                break
            key, rest = _split_mapping(line)
            if key in result:
                raise YamlError(f"line {line.number}: duplicate key {key!r}")
            index += 1
            if rest:
                result[key] = _scalar(line, rest)
            else:
                if index >= len(self.lines) or self.lines[index].indent <= indent:
                    raise YamlError(f"line {line.number}: key {key!r} requires a nested value")
                result[key], index = self._block(index, self.lines[index].indent)
        return result, index

    def _sequence(self, index: int, indent: int) -> tuple[list[Any], int]:
        result: list[Any] = []
        while index < len(self.lines):
            line = self.lines[index]
            if line.indent < indent:
                break
            if line.indent > indent:
                raise YamlError(f"line {line.number}: unexpected indentation")
            if not (line.content == "-" or line.content.startswith("- ")):
                break
            rest = line.content[1:].strip()
            index += 1
            if not rest:
                if index >= len(self.lines) or self.lines[index].indent <= indent:
                    raise YamlError(f"line {line.number}: sequence item requires a value")
                item, index = self._block(index, self.lines[index].indent)
                result.append(item)
                continue
            if ":" in rest:
                key, scalar_text = _split_mapping(line, rest)
                item: dict[str, Any] = {}
                if scalar_text:
                    item[key] = _scalar(line, scalar_text)
                else:
                    if index >= len(self.lines) or self.lines[index].indent <= indent:
                        raise YamlError(f"line {line.number}: key {key!r} requires a nested value")
                    item[key], index = self._block(index, self.lines[index].indent)
                if index < len(self.lines) and self.lines[index].indent > indent:
                    continuation_indent = self.lines[index].indent
                    continuation, index = self._mapping(index, continuation_indent)
                    overlap = set(item) & set(continuation)
                    if overlap:
                        raise YamlError(f"line {line.number}: duplicate key {sorted(overlap)[0]!r}")
                    item.update(continuation)
                result.append(item)
            else:
                result.append(_scalar(line, rest))
        return result, index


def loads(text: str) -> Any:
    """Parse a document in the safe APSAL YAML subset."""
    return _Parser(_tokenize(text)).parse()


def _dump_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    raise TypeError(f"unsupported YAML scalar: {type(value).__name__}")


def _dump(value: Any, indent: int, lines: list[str]) -> None:
    prefix = " " * indent
    if isinstance(value, dict):
        for key, child in value.items():
            if not _KEY.fullmatch(str(key)):
                raise TypeError(f"unsupported YAML key: {key!r}")
            if isinstance(child, (dict, list)):
                lines.append(f"{prefix}{key}:")
                _dump(child, indent + 2, lines)
            else:
                lines.append(f"{prefix}{key}: {_dump_scalar(child)}")
        return
    if isinstance(value, list):
        for child in value:
            if isinstance(child, (dict, list)):
                lines.append(f"{prefix}-")
                _dump(child, indent + 2, lines)
            else:
                lines.append(f"{prefix}- {_dump_scalar(child)}")
        return
    raise TypeError("APSAL YAML root must be a mapping or sequence")


def dumps(value: Any) -> str:
    """Serialize JSON-compatible data deterministically as authoring YAML."""
    lines: list[str] = ["---"]
    _dump(value, 0, lines)
    return "\n".join(lines) + "\n"
