---
name: test-coverage
trigger: test-coverage
description: Identify untested code paths and generate missing unit tests
---

Analyse the test coverage for the target module or file.

Steps:
1. Read the source file(s): {args}
2. Identify all public functions, methods, and edge cases.
3. Cross-reference with existing tests in the tests/ directory.
4. List uncovered paths (functions, branches, error conditions).
5. Generate pytest unit tests for each uncovered path, following the project's existing test style (mocks for external I/O, no real network calls, deterministic fixtures).

Output the new test file content ready to paste into the tests/unit/ directory.
