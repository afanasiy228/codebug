#!/usr/bin/env python3
import os
import random
from collections import deque
from typing import List, Tuple

BASE_DIR = os.path.dirname(__file__)
TEST_DIR = os.path.join(BASE_DIR, "tests")
MOD = 1000000007


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


def solve(n: int, edges: List[Tuple[int, int]]) -> str:
    g = [[] for _ in range(n + 1)]
    indeg = [0] * (n + 1)
    for u, v in edges:
        g[u].append(v)
        indeg[v] += 1

    q = deque([i for i in range(1, n + 1) if indeg[i] == 0])
    topo = []
    while q:
        v = q.popleft()
        topo.append(v)
        for to in g[v]:
            indeg[to] -= 1
            if indeg[to] == 0:
                q.append(to)

    dp = [0] * (n + 1)
    dp[1] = 1
    for v in topo:
        for to in g[v]:
            dp[to] += dp[v]
            if dp[to] >= MOD:
                dp[to] -= MOD

    return " ".join(str(dp[i]) for i in range(1, n + 1)) + "\n"


def build_input(n: int, m: int, edges: List[Tuple[int, int]]) -> str:
    lines = [f"{n} {m}"]
    for u, v in edges:
        lines.append(f"{u} {v}")
    return "\n".join(lines) + "\n"


def gen_chain(n: int) -> List[Tuple[int, int]]:
    return [(i, i + 1) for i in range(1, n)]


def gen_star(n: int) -> List[Tuple[int, int]]:
    return [(1, i) for i in range(2, n + 1)]


def gen_random_dag(n: int, m: int, rng: random.Random) -> List[Tuple[int, int]]:
    edges = set()
    # Start with a chain to keep graph connected from 1.
    for i in range(1, min(n, m + 1)):
        if len(edges) >= m:
            break
        edges.add((i, i + 1))
    while len(edges) < m:
        u = rng.randint(1, n - 1)
        v = rng.randint(u + 1, min(n, u + 2000))
        edges.add((u, v))
    return list(edges)


def main() -> None:
    ensure_dir()

    # Case 6: chain 1->2->...->n
    n = 100000
    edges = gen_chain(n)
    inp = build_input(n, n - 1, edges)
    out = solve(n, edges)
    write_case(6, inp, out)

    # Case 7: larger chain
    n = 200000
    edges = gen_chain(n)
    inp = build_input(n, n - 1, edges)
    out = solve(n, edges)
    write_case(7, inp, out)

    # Case 8: star from 1
    n = 200000
    edges = gen_star(n)
    inp = build_input(n, n - 1, edges)
    out = solve(n, edges)
    write_case(8, inp, out)

    # Case 9: random DAG
    n = 200000
    m = 199999
    rng = random.Random(9)
    edges = gen_random_dag(n, m, rng)
    inp = build_input(n, m, edges)
    out = solve(n, edges)
    write_case(9, inp, out)

    # Case 10: many indeg=0
    n = 200000
    m = 199999
    edges = [(i, i + 1) for i in range(1, 100000)]
    rng = random.Random(10)
    while len(edges) < m:
        u = rng.randint(100001, n - 1)
        v = rng.randint(u + 1, n)
        edges.append((u, v))
    inp = build_input(n, m, edges)
    out = solve(n, edges)
    write_case(10, inp, out)

    # Case 11: multiple components
    n = 200000
    edges = gen_chain(100000) + [(i, i + 1) for i in range(100001, 200000)]
    m = len(edges)
    inp = build_input(n, m, edges)
    out = solve(n, edges)
    write_case(11, inp, out)

    # Case 12: multiple indeg=0 vertices, 1 not unique
    n = 200000
    edges = gen_chain(150000) + [(150001, 150002)]
    m = len(edges)
    inp = build_input(n, m, edges)
    out = solve(n, edges)
    write_case(12, inp, out)

    # Case 13: vertices unreachable from 1
    n = 200000
    edges = gen_chain(100000) + [(100001, 100002), (100002, 100003)]
    m = len(edges)
    inp = build_input(n, m, edges)
    out = solve(n, edges)
    write_case(13, inp, out)

    # Case 14: several components with extra edges
    n = 200000
    rng = random.Random(14)
    edges = gen_chain(50000) + [(50001, 50002), (150001, 150002)]
    while len(edges) < 199999:
        u = rng.randint(1, n - 1)
        v = rng.randint(u + 1, n)
        edges.append((u, v))
    m = len(edges)
    inp = build_input(n, m, edges)
    out = solve(n, edges)
    write_case(14, inp, out)

    # Case 15: random DAG, many sources
    n = 200000
    m = 199999
    rng = random.Random(15)
    edges = []
    while len(edges) < m:
        u = rng.randint(1, n - 1)
        v = rng.randint(u + 1, n)
        edges.append((u, v))
    inp = build_input(n, m, edges)
    out = solve(n, edges)
    write_case(15, inp, out)


if __name__ == "__main__":
    main()
