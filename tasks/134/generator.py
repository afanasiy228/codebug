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
        while i <= self.n:
            self.f[i] += v
            i += i & -i

    def sum(self, i: int) -> int:
        s = 0
        while i > 0:
            s += self.f[i]
            i -= i & -i
        return s

    def range_sum(self, l: int, r: int) -> int:
        return self.sum(r) - self.sum(l - 1)


def build_euler(n: int, g: List[List[int]]) -> Tuple[List[int], List[int]]:
    tin = [0] * (n + 1)
    tout = [0] * (n + 1)
    timer = 0
    stack = [(1, 0, 0)]  # (v, idx, state), state 0 enter, 1 exit
    while stack:
        v, idx, state = stack.pop()
        if state == 0:
            timer += 1
            tin[v] = timer
            stack.append((v, 0, 1))
            children = g[v]
            for to in reversed(children):
                stack.append((to, 0, 0))
        else:
            tout[v] = timer
    return tin, tout


def solve(n: int, a: List[int], g: List[List[int]], queries: List[Tuple[int, int, int]]) -> str:
    tin, tout = build_euler(n, g)
    fw = Fenwick(n)
    for v in range(1, n + 1):
        fw.add(tin[v], a[v])
    out_lines = []
    for q in queries:
        if q[0] == 1:
            v = q[1]
            out_lines.append(str(fw.range_sum(tin[v], tout[v])))
        else:
            v, x = q[1], q[2]
            fw.add(tin[v], x - a[v])
            a[v] = x
    return "\n".join(out_lines) + ("\n" if out_lines else "")


def build_input(n: int, q: int, a: List[int], edges: List[Tuple[int, int]], queries: List[Tuple[int, int, int]]) -> str:
    lines = [f"{n} {q}", " ".join(map(str, a[1:]))]
    for u, v in edges:
        lines.append(f"{u} {v}")
    for t, x, y in queries:
        if t == 1:
            lines.append(f"1 {x}")
        else:
            lines.append(f"2 {x} {y}")
    return "\n".join(lines) + "\n"


def gen_chain(n: int) -> List[Tuple[int, int]]:
    return [(i, i + 1) for i in range(1, n)]


def gen_star(n: int) -> List[Tuple[int, int]]:
    return [(1, i) for i in range(2, n + 1)]


def gen_random_tree(n: int, rng: random.Random) -> List[Tuple[int, int]]:
    edges = []
    for v in range(2, n + 1):
        parent = rng.randint(1, v - 1)
        edges.append((parent, v))
    return edges


def build_graph(n: int, edges: List[Tuple[int, int]]) -> List[List[int]]:
    g = [[] for _ in range(n + 1)]
    for u, v in edges:
        g[u].append(v)
    return g


def gen_queries(n: int, q: int, rng: random.Random, update_ratio: float) -> List[Tuple[int, int, int]]:
    queries = []
    for _ in range(q):
        if rng.random() < update_ratio:
            v = rng.randint(1, n)
            x = rng.randint(-10**9, 10**9)
            queries.append((2, v, x))
        else:
            v = rng.randint(1, n)
            queries.append((1, v, 0))
    return queries


def main() -> None:
    ensure_dir()

    # Case 5: chain, alternating
    n = 10
    q = 10
    a = [0] + [1] * n
    edges = gen_chain(n)
    g = build_graph(n, edges)
    rng = random.Random(5)
    queries = gen_queries(n, q, rng, update_ratio=0.5)
    inp = build_input(n, q, a, edges, queries)
    out = solve(n, a[:], g, queries)
    write_case(5, inp, out)

    # Case 6: chain, type-1 only
    n = 100000
    q = 100000
    a = [0] + [1] * n
    edges = gen_chain(n)
    g = build_graph(n, edges)
    rng = random.Random(6)
    queries = [(1, rng.randint(1, n), 0) for _ in range(q)]
    inp = build_input(n, q, a, edges, queries)
    out = solve(n, a[:], g, queries)
    write_case(6, inp, out)

    # Case 7: chain, half updates
    n = 200000
    q = 200000
    a = [0] + [1] * n
    edges = gen_chain(n)
    g = build_graph(n, edges)
    rng = random.Random(7)
    queries = gen_queries(n, q, rng, update_ratio=0.5)
    inp = build_input(n, q, a, edges, queries)
    out = solve(n, a[:], g, queries)
    write_case(7, inp, out)

    # Case 8: star, frequent subtree queries
    n = 200000
    q = 200000
    a = [0] + [rng.randint(1, 10) for _ in range(n)]
    edges = gen_star(n)
    g = build_graph(n, edges)
    rng = random.Random(8)
    queries = gen_queries(n, q, rng, update_ratio=0.2)
    inp = build_input(n, q, a, edges, queries)
    out = solve(n, a[:], g, queries)
    write_case(8, inp, out)

    # Case 9: random tree, random queries
    n = 200000
    q = 200000
    rng = random.Random(9)
    a = [0] + [rng.randint(-10**6, 10**6) for _ in range(n)]
    edges = gen_random_tree(n, rng)
    g = build_graph(n, edges)
    queries = gen_queries(n, q, rng, update_ratio=0.4)
    inp = build_input(n, q, a, edges, queries)
    out = solve(n, a[:], g, queries)
    write_case(9, inp, out)

    # Cases 10-15: max tests, chain, alternating updates and queries
    for idx in range(10, 16):
        n = 200000
        q = 200000
        rng = random.Random(100 + idx)
        a = [0] + [rng.randint(-10**6, 10**6) for _ in range(n)]
        edges = gen_chain(n)
        g = build_graph(n, edges)
        queries = gen_queries(n, q, rng, update_ratio=0.5)
        inp = build_input(n, q, a, edges, queries)
        out = solve(n, a[:], g, queries)
        write_case(idx, inp, out)


if __name__ == "__main__":
    main()
