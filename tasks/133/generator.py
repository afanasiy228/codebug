#!/usr/bin/env python3
import os
import random
from array import array
from typing import List, Tuple

BASE_DIR = os.path.dirname(__file__)
TEST_DIR = os.path.join(BASE_DIR, "tests")


def ensure_dir() -> None:
    os.makedirs(TEST_DIR, exist_ok=True)


def write_case(idx: int, inp: str, out: str) -> None:
    in_path = os.path.join(TEST_DIR, f"{idx}.in")
    out_path = os.path.join(TEST_DIR, f"{idx}.out")
    if os.path.exists(in_path) or os.path.exists(out_path):
        return
    with open(in_path, "w", encoding="utf-8") as f:
        f.write(inp)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(out)


def build_pref(a: List[int]) -> List[array]:
    n = len(a)
    pref: List[array] = [array('q', [0]) * (n + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        row = pref[i]
        row_up = pref[i - 1]
        for j in range(1, n + 1):
            val = a[(i + j) % n]
            row[j] = row_up[j] + row[j - 1] - row_up[j - 1] + val
    return pref


def rect_sum(pref: List[array], x1: int, y1: int, x2: int, y2: int) -> int:
    return pref[x2][y2] - pref[x1 - 1][y2] - pref[x2][y1 - 1] + pref[x1 - 1][y1 - 1]


def build_input(n: int, q: int, a: List[int], queries: List[Tuple[int, int, int, int]]) -> str:
    lines = [f"{n} {q}", " ".join(map(str, a))]
    for x1, y1, x2, y2 in queries:
        lines.append(f"{x1} {y1} {x2} {y2}")
    return "\n".join(lines) + "\n"


def gen_case(n: int, q: int, a: List[int], queries: List[Tuple[int, int, int, int]]) -> Tuple[str, str]:
    pref = build_pref(a)
    out_lines = [str(rect_sum(pref, x1, y1, x2, y2)) for x1, y1, x2, y2 in queries]
    inp = build_input(n, q, a, queries)
    out = "\n".join(out_lines) + "\n"
    return inp, out


def gen_random_queries(n: int, q: int, rng: random.Random, max_side: int = None) -> List[Tuple[int, int, int, int]]:
    queries = []
    for _ in range(q):
        if max_side is None:
            x1 = rng.randint(1, n)
            x2 = rng.randint(x1, n)
            y1 = rng.randint(1, n)
            y2 = rng.randint(y1, n)
        else:
            x1 = rng.randint(1, n)
            y1 = rng.randint(1, n)
            x2 = min(n, x1 + rng.randint(0, max_side))
            y2 = min(n, y1 + rng.randint(0, max_side))
        queries.append((x1, y1, x2, y2))
    return queries


def main() -> None:
    ensure_dir()

    # Case 7
    n = 500
    q = 1
    a = [2] * n
    queries = [(1, 1, 500, 500)]
    inp, out = gen_case(n, q, a, queries)
    write_case(7, inp, out)

    # Case 8
    n = 1000
    q = 10
    a = [i % 5 for i in range(n)]
    rng = random.Random(8)
    queries = gen_random_queries(n, q, rng)
    inp, out = gen_case(n, q, a, queries)
    write_case(8, inp, out)

    # Case 9
    n = 2000
    q = 1000
    rng = random.Random(9)
    a = [rng.randint(-10**6, 10**6) for _ in range(n)]
    queries = gen_random_queries(n, q, rng)
    inp, out = gen_case(n, q, a, queries)
    write_case(9, inp, out)

    # Case 10
    n = 3000
    q = 100000
    rng = random.Random(10)
    a = [rng.randint(-10**6, 10**6) for _ in range(n)]
    queries = gen_random_queries(n, q, rng, max_side=50)
    inp, out = gen_case(n, q, a, queries)
    write_case(10, inp, out)

    # Case 11
    n = 3500
    q = 150000
    rng = random.Random(11)
    a = [rng.randint(-10**6, 10**6) for _ in range(n)]
    queries = gen_random_queries(n, q, rng)
    inp, out = gen_case(n, q, a, queries)
    write_case(11, inp, out)

    # Case 12
    n = 3800
    q = 180000
    rng = random.Random(12)
    a = [rng.randint(-10**6, 10**6) for _ in range(n)]
    queries = gen_random_queries(n, q, rng)
    inp, out = gen_case(n, q, a, queries)
    write_case(12, inp, out)

    # Case 13
    n = 3900
    q = 190000
    rng = random.Random(13)
    a = [rng.randint(-10**6, 10**6) for _ in range(n)]
    queries = gen_random_queries(n, q, rng)
    inp, out = gen_case(n, q, a, queries)
    write_case(13, inp, out)

    # Case 14
    n = 4000
    q = 200000
    rng = random.Random(14)
    a = [rng.randint(-10**6, 10**6) for _ in range(n)]
    queries = gen_random_queries(n, q, rng)
    inp, out = gen_case(n, q, a, queries)
    write_case(14, inp, out)

    # Case 15
    n = 4000
    q = 200000
    a = [1] * n
    rng = random.Random(15)
    queries = gen_random_queries(n, q, rng)
    inp, out = gen_case(n, q, a, queries)
    write_case(15, inp, out)


if __name__ == "__main__":
    main()
