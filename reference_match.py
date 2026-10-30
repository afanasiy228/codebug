"""Conservative source comparison for the already-judged reference fast path.

Only horizontal layout next to unambiguous delimiters is ignored. This is
deliberately narrower than a formatter or a full token comparison: comments,
strings, Python indentation and preprocessor syntax remain byte-for-byte.
When a source uses multiline lexical constructs we decline the shortcut.
"""

import re


_LAYOUT = re.compile(r"(?<=[()\[\]{},;])[ \t]+|[ \t]+(?=[()\[\]{},;])")
_NEWLINE = re.compile(r"(\r\n|\r|\n)$")
_INDENT = re.compile(r"[ \t]*")
_CPP_DEFINE = re.compile(r"(?m)^[ \t]*#[ \t]*define\b")


def _canonical_layout(source, language):
    if language not in {"cpp", "python"}:
        return None
    if "'''" in source or '"""' in source or "/*" in source or "*/" in source:
        return None
    if language == "cpp" and ("R\"" in source or _CPP_DEFINE.search(source)):
        return None

    result = []
    for line in source.splitlines(keepends=True):
        newline_match = _NEWLINE.search(line)
        newline = newline_match.group(1) if newline_match else ""
        body = line[:-len(newline)] if newline else line
        # Backslash-newline can change token boundaries in either language.
        if body.endswith("\\"):
            return None
        # Protect the entire line when it contains a literal, comment or
        # preprocessor directive. False negatives only cost speed.
        if any(marker in body for marker in ('"', "'", "#", "//")):
            result.append(line)
            continue
        indent = _INDENT.match(body).group(0)
        result.append(indent + _LAYOUT.sub("", body[len(indent):]) + newline)
    return "".join(result)


def matches_reference(candidate, reference, language):
    if candidate == reference:
        return True
    left = _canonical_layout(candidate, language)
    right = _canonical_layout(reference, language)
    return left is not None and right is not None and left == right
