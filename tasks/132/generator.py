#!/usr/bin/env python3
import os
import random
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


class Fenwick:
    def __init__(self, n: int) -> None:
        self.n = n
        self.f = [0] * (n + 1)

    def add(self, i: int, v: int) -> None:
        i += 1
        n = self.n
        while i <= n:
            self.f[i] += v
            i += i & -i

    def sum(self, i: int) -> int:
        i += 1
        s = 0
        while i > 0:
            s += self.f[i]
            i -= i & -i
        return s

    def range_sum(self, l: int, r: int) -> int:
        if l > r:
            return 0
        return self.sum(r) - (self.sum(l - 1) if l > 0 else 0)


def solve(n: int, a: List[int], queries: List[Tuple[int, int, int]]) -> str:
    fw = Fenwick(n)
    for i, v in enumerate(a):
        fw.add(i, v)
    out_lines = []
    for q in queries:
        if q[0] == 1:
            _, l, r = q
            out_lines.append(str(fw.range_sum(l, r)))
        else:
            _, i, x = q
            delta = x - a[i]
            a[i] = x
            fw.add(i, delta)
    return "\n".join(out_lines) + ("\n" if out_lines else "")


def build_input(n: int, q: int, a: List[int], queries: List[Tuple[int, int, int]]) -> str:
    lines = [f"{n} {q}", " ".join(map(str, a))]
    for t, x, y in queries:
        lines.append(f"{t} {x} {y}")
    return "\n".join(lines) + "\n"


def gen_case_5() -> Tuple[str, str]:
    n = 10
    q = 10
    a = list(range(1, n + 1))
    queries = [
        (1, 0, 9),
        (2, 4, 100),
        (1, 3, 5),
        (2, 0, -1),
        (1, 0, 4),
        (2, 9, 7),
        (1, 5, 9),
        (2, 2, 0),
        (1, 0, 9),
        (1, 2, 2),
    ]
    inp = build_input(n, q, a, queries)
    out = solve(n, a[:], queries)
    return inp, out


def gen_case_all_type1(n: int, q: int, a: List[int], rng: random.Random) -> Tuple[str, str]:
    queries = []
    pref = [0]
    for v in a:
        pref.append(pref[-1] + v)

    def range_sum(l: int, r: int) -> int:
        return pref[r + 1] - pref[l]

    out_lines = []
    for _ in range(q):
        l = rng.randrange(0, n)
        r = rng.randrange(l, n)
        queries.append((1, l, r))
        out_lines.append(str(range_sum(l, r)))

    inp = build_input(n, q, a, queries)
    out = "\n".join(out_lines) + "\n"
    return inp, out


def gen_case_all_type2(n: int, q: int, a: List[int], rng: random.Random) -> Tuple[str, str]:
    queries = []
    for _ in range(q):
        i = rng.randrange(0, n)
        x = rng.randrange(-10**9, 10**9)
        queries.append((2, i, x))
        a[i] = x
    inp = build_input(n, q, a, queries)
    return inp, ""


def gen_case_alternating(n: int, q: int, a: List[int], rng: random.Random) -> Tuple[str, str]:
    queries = []
    for k in range(q):
        if k % 2 == 0:
            l = rng.randrange(0, n)
            r = rng.randrange(l, n)
            queries.append((1, l, r))
        else:
            i = rng.randrange(0, n)
            x = rng.randrange(-10**9, 10**9)
            queries.append((2, i, x))
    inp = build_input(n, q, a, queries)
    out = solve(n, a[:], queries)
    return inp, out


def main() -> None:
    ensure_dir()
    rng = random.Random(12345)

    # Case 5
    inp, out = gen_case_5()
    write_case(5, inp, out)

    # Case 6
    n = 100000
    q = 100000
    a = [1] * n
    inp, out = gen_case_all_type1(n, q, a, random.Random(6))
    write_case(6, inp, out)

    # Case 7
    n = 200000
    q = 200000
    a = [1] * n
    inp, out = gen_case_alternating(n, q, a, random.Random(7))
    write_case(7, inp, out)

    # Case 8
    n = 200000
    q = 200000
    a = [rng.randrange(-10**9, 10**9) for _ in range(n)]
    inp, out = gen_case_all_type1(n, q, a, random.Random(8))
    write_case(8, inp, out)

    # Case 9
    n = 200000
    q = 200000
    a = [rng.randrange(-10**9, 10**9) for _ in range(n)]
    inp, out = gen_case_all_type2(n, q, a, random.Random(9))
    write_case(9, inp, out)

    # Cases 10-15: max tests with many type-1 queries
    for idx in range(10, 16):
        n = 200000
        q = 200000
        a = [rng.randrange(-10**6, 10**6) for _ in range(n)]
        inp, out = gen_case_all_type1(n, q, a, random.Random(100 + idx))
        write_case(idx, inp, out)


if __name__ == "__main__":
    main()
