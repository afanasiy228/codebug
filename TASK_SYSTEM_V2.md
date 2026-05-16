# CodeBug Task System v2

## Goal

CodeBug uses a Polygon-compatible task layout as the primary format.

```
tasks/<id>/
  problem.json
  statement/
    russian.tex
    russian.html
    assets/
    hint.md
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

## Current Implementation

1. New task structure
   Server writes `problem.json`, `statement/russian.tex`, `statement/russian.html`, `tests/001`, `tests/001.a`, and `solutions/*` when a task is created through `/tasks/create`. New saves are v2-only and no longer create the old `meta.json`, `statement.md`, `code.cpp`, `sol.cpp`, `tests/*.in`, `tests/*.out` mirror.

2. Explicit version
   `problem.json` stores both fields:

   ```json
   {
     "formatVersion": 2,
     "schemaVersion": 2
   }
   ```

3. Test metadata
   Each test is a metadata object, not just a file pair:

   ```json
   {
     "id": 1,
     "name": "001",
     "input": "tests/001",
     "answer": "tests/001.a",
     "visibility": "private",
     "group": 2,
     "subtask": 2,
     "points": 5
   }
   ```

   The public API exposes only open test file paths through `openTests`.

4. Test groups
   `problem.json` supports IOI/Polygon-style groups:

   ```json
   {
     "id": 3,
     "name": "group 3",
     "points": 40,
     "dependencies": [1, 2],
     "tests": ["007", "008"]
   }
   ```

   Judge skips a group if one of its dependencies did not pass. Logs include group verdicts and total score.

5. Subtasks compatibility
   `subtasks` is still written as a compatibility alias for older frontend/admin assumptions. Internally, v2 should use `groups`.

6. Custom checker
   `judge.py` supports `checker.type = "custom"` and compiles `checker/checker.cpp`. Checker protocol is:

   ```
   checker <input-file> <participant-output-file> <answer-file>
   ```

   Exit code `0` means OK, non-zero means WA.

7. Runner abstraction
   Judge uses `runner/cpp.py` and `runner/python.py` for language-specific compile/run commands. This keeps future languages, grader tasks and interactive runners out of the core judge loop.

8. Admin bundle
   Admin can load full task contents from `/tasks/<id>/admin-bundle`, including private tests and reference files. The public API only exposes statement, broken code and open tests.

9. Legacy compatibility
   Server can still read old `meta.json` tasks as a transition path, but existing legacy tasks can be deleted.

## Next Implementation Stages

1. Better group editor: structured UI instead of raw JSON.
2. LaTeX compiler pipeline: `statement/russian.tex` to `statement/russian.html`.
3. Polygon zip importer: parse `problem.xml`, statements, tests, checker, validator, generators.
4. Grader task runner: compile user solution with `grader.cpp`/`grader.h`.
5. Interactive task runner: solution + interactor IPC with protocol logs and strict timeouts.
