# Implementation Plan

## Module Structure

- `src/prime_cli_writer/exceptions.py` → domain-specific exception hierarchy → `PrimeCliWriterError`, `InputValidationError`, `OutputWriteError`
- `src/prime_cli_writer/primes.py` → prime generation logic → `is_prime(value: int) -> bool`, `generate_first_n_primes(count: int) -> list[int]`
- `src/prime_cli_writer/io_utils.py` → output serialization and file writing → `format_primes(primes: list[int]) -> str`, `write_primes_to_file(primes: list[int], output_path: str) -> None`
- `src/prime_cli_writer/cli.py` → CLI orchestration and exit codes → `parse_args(argv: list[str]) -> tuple[int, str]`, `run(argv: list[str]) -> int`, `main() -> None`
- `src/prime_cli_writer/__init__.py` → explicit public exports
- `src/prime_cli_writer/py.typed` → typing marker

## Dependency Graph

- `exceptions.py` imports nothing project-local.
- `primes.py` imports `InputValidationError` from `exceptions.py`.
- `io_utils.py` imports `OutputWriteError` from `exceptions.py`.
- `cli.py` imports from `exceptions.py`, `primes.py`, and `io_utils.py`.
- `__init__.py` imports public symbols from `primes.py`.

This graph is acyclic: `exceptions -> {primes, io_utils, cli}` and `{primes, io_utils} -> cli`.

## Test Matrix

- FR1/FR2: CLI accepts exactly two arguments → `tests/test_cli.py::test_parse_args_valid_inputs_returns_values`, `test_run_missing_arguments_returns_usage_error`
- FR3: Parse `N` as integer → `test_parse_args_non_integer_raises_input_validation_error`
- FR4: Calculate first `N` primes → `tests/test_primes.py::test_generate_first_n_primes_for_five_returns_expected_values`
- FR5: Write one number per line → `tests/test_io_utils.py::test_write_primes_to_file_writes_one_prime_per_line`
- FR6: Validate inputs → `test_generate_first_n_primes_negative_count_raises_error`, `test_parse_args_negative_integer_raises_input_validation_error`
- FR7: Handle `N=0`, `N=1`, negative numbers → `test_generate_first_n_primes_zero_returns_empty_list`, `test_generate_first_n_primes_one_returns_first_prime`, `test_run_negative_count_returns_validation_error`
- FR8: Exit with appropriate error codes → `test_run_valid_inputs_returns_success`, `test_run_write_failure_returns_runtime_error`

## Build Order

1. Tests for `exceptions.py` behavior via downstream modules.
2. `tests/test_primes.py`
3. `tests/test_io_utils.py`
4. `tests/test_cli.py`
5. Implement `exceptions.py`
6. Implement `primes.py`
7. Implement `io_utils.py`
8. Implement `cli.py`
9. Implement `__init__.py` and `py.typed`

## Draft pyproject Dependency Section

```toml
[project]
dependencies = []

[dependency-groups]
dev = [
  "mypy>=1.10,<2.0",
  "pytest>=8.0,<9.0",
  "pytest-cov>=5.0,<6.0",
  "ruff>=0.6,<0.7",
]
```
