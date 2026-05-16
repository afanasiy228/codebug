# CodeBug Task System v2

## Goal

CodeBug tasks now use a Polygon-compatible layout as the primary format.

```
tasks/<id>/
  problem.json
  statement/
    russian.tex
    russian.html
    assets/
  tests/
    001
    001.a
  checker/
    checker.cpp
  grader/
    grader.cpp
    grader.h
  generator/
    gen.cpp
  validator/
    validator.cpp
  solutions/
    main.cpp
    wa.cpp
    tl.cpp
```

## Current implementation

1. New task structure
   Server writes `problem.json`, `statement/russian.tex`, `statement/russian.html`, `tests/001`, `tests/001.a`, and `solutions/*` when a task is created through `/tasks/create`.

2. Open/private tests
   `problem.json` stores `visibility: "open" | "private"` per test. The public API exposes only open test file paths through `openTests`.

3. Subtasks
   `problem.json` stores subtasks and test membership. Judge logs test visibility and subtask id.

4. Custom checker
   `judge.py` supports `checker.type = "custom"` and compiles `checker/checker.cpp`. Checker protocol is:

   ```
   checker <input-file> <participant-output-file> <answer-file>
   ```

   Exit code `0` means OK, non-zero means WA.

5. Legacy compatibility
   Server can still read old `meta.json` tasks. New tasks also write a legacy mirror (`meta.json`, `statement.md`, `tests/*.in`, `tests/*.out`) until the frontend/admin tooling is fully v2-native.

## Next implementation stages

1. Native admin UI for v2 fields: checker, validator, subtasks, open/private flags.
2. LaTeX compiler pipeline: `statement/russian.tex` to `statement/russian.html`.
3. Polygon zip importer: parse `problem.xml`, statements, tests, checker, validator, generators.
4. Grader task runner: compile user solution with `grader.cpp`/`grader.h`.
5. Interactive task runner: solution + interactor IPC with protocol logs and strict timeouts.

