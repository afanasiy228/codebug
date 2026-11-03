"""How much of the broken code a participant changed: lines and characters.

The same algorithm lives in line-diff.js for the editor counter, so the
number on screen and the number the server checks always agree.

Rules:
- blank lines, `//` comment lines and all whitespace are ignored, so
  reformatting or a note to yourself never costs anything;
- lines are matched by the longest common subsequence;
- every contiguous edit counts as max(removed, added), so replacing one
  line with another is 1, and moving a line elsewhere is 2;
- characters are counted the same way inside every changed block of lines,
  so `x = 0;` -> `x = 1;` costs 1 character.
"""

MAX_CELLS = 4_000_000


def normalize_lines(text):
    out = []
    for raw in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = "".join(raw.split())
        if not line or line.startswith("//"):
            continue
        out.append(line)
    return out


def _hunks(a, b):
    """Changed blocks between sequences a and b as (removed, added) slices."""
    start = 0
    while start < len(a) and start < len(b) and a[start] == b[start]:
        start += 1
    end_a, end_b = len(a), len(b)
    while end_a > start and end_b > start and a[end_a - 1] == b[end_b - 1]:
        end_a -= 1
        end_b -= 1
    a, b = a[start:end_a], b[start:end_b]
    n, m = len(a), len(b)
    if n == 0 or m == 0:
        return [(a, b)] if n or m else []
    if n * m > MAX_CELLS:
        return [(a, b)]

    # lcs[i][j] = LCS length of a[i:] and b[j:]
    lcs = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        row, below = lcs[i], lcs[i + 1]
        ai = a[i]
        for j in range(m - 1, -1, -1):
            row[j] = below[j + 1] + 1 if ai == b[j] else max(below[j], row[j + 1])

    hunks = []
    i = j = 0
    hi, hj = 0, 0
    while i < n or j < m:
        if i < n and j < m and a[i] == b[j]:
            if hi < i or hj < j:
                hunks.append((a[hi:i], b[hj:j]))
            i += 1
            j += 1
            hi, hj = i, j
        elif j >= m or (i < n and lcs[i + 1][j] >= lcs[i][j + 1]):
            i += 1
        else:
            j += 1
    if hi < n or hj < m:
        hunks.append((a[hi:], b[hj:]))
    return hunks


def _cost(a, b):
    total = 0
    for removed, added in _hunks(a, b):
        if len(removed) * len(added) > MAX_CELLS:
            total += len(removed) + len(added)
        else:
            total += max(len(removed), len(added))
    return total


def count_changed_lines(before, after):
    return _cost(normalize_lines(before), normalize_lines(after))


def count_changed_chars(before, after):
    total = 0
    for removed, added in _hunks(normalize_lines(before), normalize_lines(after)):
        total += _cost("\n".join(removed), "\n".join(added))
    return total
