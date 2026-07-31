"""Hand-rolled YAML subset parser (stdlib only) — see plan §PR 6.

Deliberately NOT a general YAML parser. Handles the shapes actually used in
Zeref's mission and execution-policy files:

- scalars: strings (bare + quoted), ints, floats, booleans, null
- flow scalars only for values (no flow-style maps or sequences)
- block mappings, arbitrary depth
- block sequences of scalars
- block sequences of flat maps (``- key: value`` blocks)
- ``# comments`` on any line
- ``|`` and ``>`` block scalars NOT supported (never appear in our schemas)
- YAML anchors / aliases NOT supported (never appear in our schemas)

Reject anything outside this grammar with ``YAMLSubsetError`` — silent
mis-parse is worse than an explicit failure.
"""

from __future__ import annotations

from pathlib import Path


class YAMLSubsetError(ValueError):
    pass


def parse_file(path: Path | str) -> dict:
    return parse(Path(path).read_text(encoding="utf-8"))


def parse(text: str) -> dict:
    lines = _pre_process(text)
    if not lines:
        return {}
    result, consumed = _parse_block(lines, 0, 0)
    if consumed != len(lines):
        raise YAMLSubsetError(
            f"unparsed trailing lines beginning at line {lines[consumed].line_no}: "
            f"{lines[consumed].raw!r}"
        )
    if not isinstance(result, dict):
        raise YAMLSubsetError("top-level document must be a mapping")
    return result


# ---------------------------------------------------------------------------
# Line pre-processing
# ---------------------------------------------------------------------------

class _Line:
    __slots__ = ("indent", "content", "raw", "line_no")

    def __init__(self, raw: str, line_no: int):
        self.raw = raw
        self.line_no = line_no
        stripped = raw.rstrip("\n").rstrip()
        # strip trailing comment (only if preceded by a space)
        idx = _find_comment(stripped)
        if idx >= 0:
            stripped = stripped[:idx].rstrip()
        indent = 0
        while indent < len(stripped) and stripped[indent] == " ":
            indent += 1
        if indent < len(stripped) and stripped[indent] == "\t":
            raise YAMLSubsetError(
                f"tabs not allowed for indentation on line {line_no}"
            )
        self.indent = indent
        self.content = stripped[indent:]


def _find_comment(s: str) -> int:
    """Return index of a comment-starting ``#``, respecting quoted strings."""
    in_single = in_double = False
    for i, ch in enumerate(s):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            if i == 0 or s[i - 1] == " ":
                return i
    return -1


def _pre_process(text: str) -> list[_Line]:
    out: list[_Line] = []
    for i, raw in enumerate(text.splitlines(), start=1):
        line = _Line(raw, i)
        if line.content == "":
            continue
        if line.content == "---":  # doc separator: allow once at top
            continue
        out.append(line)
    return out


# ---------------------------------------------------------------------------
# Block parser
# ---------------------------------------------------------------------------

def _parse_block(lines: list[_Line], start: int, indent: int):
    """Return (value, next_index). ``value`` is a dict, list, or scalar."""
    if start >= len(lines):
        return {}, start
    first = lines[start]
    if first.indent < indent:
        return {}, start
    # sequence
    if first.content.startswith("- "):
        return _parse_sequence(lines, start, first.indent)
    # mapping
    return _parse_mapping(lines, start, first.indent)


def _parse_mapping(lines: list[_Line], start: int, indent: int):
    result: dict = {}
    i = start
    while i < len(lines):
        line = lines[i]
        if line.indent < indent:
            break
        if line.indent > indent:
            raise YAMLSubsetError(
                f"unexpected extra indentation on line {line.line_no}: "
                f"{line.raw!r}"
            )
        if line.content.startswith("- "):
            raise YAMLSubsetError(
                f"sequence item where mapping expected on line {line.line_no}"
            )
        key, sep, rest = line.content.partition(":")
        if not sep:
            raise YAMLSubsetError(
                f"expected ':' on line {line.line_no}: {line.raw!r}"
            )
        key = key.strip()
        rest = rest.strip()
        if rest == "":
            # nested block: peek next line
            nested_start = i + 1
            child_indent = _peek_indent(lines, nested_start, indent)
            if child_indent <= indent:
                value: object = None
            else:
                value, next_i = _parse_block(lines, nested_start, child_indent)
                i = next_i - 1  # loop will += 1
            result[key] = value
        else:
            result[key] = _parse_scalar(rest, line.line_no)
        i += 1
    return result, i


def _parse_sequence(lines: list[_Line], start: int, indent: int):
    result: list = []
    i = start
    while i < len(lines):
        line = lines[i]
        if line.indent < indent:
            break
        if line.indent > indent:
            raise YAMLSubsetError(
                f"sequence indent mismatch on line {line.line_no}"
            )
        if not line.content.startswith("- "):
            break
        inline = line.content[2:].strip()
        if inline == "":
            # nested block child
            child_indent = _peek_indent(lines, i + 1, indent)
            if child_indent <= indent:
                raise YAMLSubsetError(
                    f"empty sequence item on line {line.line_no}"
                )
            value, next_i = _parse_block(lines, i + 1, child_indent)
            result.append(value)
            i = next_i
            continue
        if ":" in inline:
            # inline key/value; a following-line continuation with deeper
            # indent joins the same map.
            key, sep, rest = inline.partition(":")
            first_pair = (key.strip(), _parse_scalar(rest.strip(), line.line_no)
                          if rest.strip() else None)
            item: dict = {first_pair[0]: first_pair[1]}
            # Look ahead for continuation lines belonging to this item.
            child_indent = indent + 2
            j = i + 1
            while j < len(lines) and lines[j].indent == child_indent \
                    and not lines[j].content.startswith("- "):
                sub_key, sub_sep, sub_rest = lines[j].content.partition(":")
                if not sub_sep:
                    raise YAMLSubsetError(
                        f"expected ':' on line {lines[j].line_no}"
                    )
                sub_rest = sub_rest.strip()
                if sub_rest:
                    item[sub_key.strip()] = _parse_scalar(sub_rest, lines[j].line_no)
                else:
                    nested_indent = _peek_indent(lines, j + 1, child_indent)
                    if nested_indent > child_indent:
                        value, next_j = _parse_block(lines, j + 1, nested_indent)
                        item[sub_key.strip()] = value
                        j = next_j - 1
                    else:
                        item[sub_key.strip()] = None
                j += 1
            result.append(item)
            i = j
        else:
            result.append(_parse_scalar(inline, line.line_no))
            i += 1
    return result, i


def _peek_indent(lines: list[_Line], idx: int, current_indent: int) -> int:
    if idx >= len(lines):
        return current_indent
    return lines[idx].indent


# ---------------------------------------------------------------------------
# Scalars
# ---------------------------------------------------------------------------

_BOOLS = {"true": True, "false": False, "yes": True, "no": False, "on": True, "off": False}


def _parse_scalar(s: str, line_no: int) -> object:
    if s == "":
        return None
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    lower = s.lower()
    if lower == "null" or lower == "~":
        return None
    if lower in _BOOLS:
        return _BOOLS[lower]
    if s.startswith("[") or s.startswith("{"):
        raise YAMLSubsetError(
            f"flow-style collections not supported on line {line_no}: {s!r}"
        )
    # numeric
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s
