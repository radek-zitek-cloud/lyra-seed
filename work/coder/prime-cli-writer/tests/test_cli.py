"""Tests for CLI orchestration."""

from pathlib import Path

from prime_cli_writer.cli import parse_args, run
from prime_cli_writer.exceptions import InputValidationError


def test_parse_args_valid_inputs_returns_values() -> None:
    assert parse_args(["5", "primes.txt"]) == (5, "primes.txt")


def test_parse_args_non_integer_raises_input_validation_error() -> None:
    try:
        parse_args(["abc", "primes.txt"])
    except InputValidationError:
        pass
    else:
        msg = "expected InputValidationError"
        raise AssertionError(msg)


def test_parse_args_negative_integer_raises_input_validation_error() -> None:
    try:
        parse_args(["-2", "primes.txt"])
    except InputValidationError:
        pass
    else:
        msg = "expected InputValidationError"
        raise AssertionError(msg)


def test_run_missing_arguments_returns_usage_error(tmp_path: Path) -> None:
    output_file = tmp_path / "unused.txt"
    assert run(["5", str(output_file), "extra"]) == 2


def test_run_valid_inputs_returns_success(tmp_path: Path) -> None:
    output_file = tmp_path / "primes.txt"
    assert run(["3", str(output_file)]) == 0
    assert output_file.read_text(encoding="utf-8") == "2\n3\n5\n"


def test_run_negative_count_returns_validation_error(tmp_path: Path) -> None:
    output_file = tmp_path / "primes.txt"
    assert run(["-1", str(output_file)]) == 2


def test_run_write_failure_returns_runtime_error(tmp_path: Path) -> None:
    output_file = tmp_path / "missing" / "primes.txt"
    assert run(["2", str(output_file)]) == 1
