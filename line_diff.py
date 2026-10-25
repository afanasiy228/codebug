"""How many lines a participant changed in the broken code.

The same algorithm lives in line-diff.js for the editor counter, so the
number on screen and the number the server checks always agree.

Rules:
- blank lines, `//` comment lines and all whitespace are ignored, so
  reformatting or a note to yourself never costs anything;
- lines are matched by the longest common subsequence;
- every contiguous edit counts as max(removed, added), so replacing one
  line with another is 1, and moving a line elsewhere is 2.
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


def count_changed_lines(before, after):
    a = normalize_lines(before)
    b = normalize_lines(after)
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
        return max(n, m)
    if n * m > MAX_CELLS:
        return n + m

    # lcs[i][j] = LCS length of a[i:] and b[j:]
    lcs = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        row, below = lcs[i], lcs[i + 1]
        ai = a[i]
        for j in range(m - 1, -1, -1):
            row[j] = below[j + 1] + 1 if ai == b[j] else max(below[j], row[j + 1])

    changed = removed = added = 0
    i = j = 0
    while i < n or j < m:
        if i < n and j < m and a[i] == b[j]:
            changed += max(removed, added)
            removed = added = 0
            i += 1
            j += 1
        elif j >= m or (i < n and lcs[i + 1][j] >= lcs[i][j + 1]):
            removed += 1
            i += 1
        else:
            added += 1
            j += 1
    return changed + max(removed, added)
