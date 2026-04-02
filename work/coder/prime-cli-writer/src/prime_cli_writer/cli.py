"""Command-line interface for generating prime number files."""

import sys

from prime_cli_writer.exceptions import InputValidationError, OutputWriteError
from prime_cli_writer.io_utils import write_primes_to_file
from prime_cli_writer.primes import generate_first_n_primes

USAGE_ERROR = 2
RUNTIME_ERROR = 1
SUCCESS = 0


def parse_args(argv: list[str]) -> tuple[int, str]:
    """Parse CLI arguments.

    Args:
        argv: Positional CLI arguments excluding the program name.

    Returns:
        Parsed prime count and output filename.

    Raises:
        InputValidationError: If arguments are missing, malformed, or invalid.
    """
    if len(argv) != 2:
        msg = "Usage: prime-cli-writer N OUTPUT_FILE"
        raise InputValidationError(msg)
    raw_count, output_file = argv
    try:
        count = int(raw_count)
    except ValueError as error:
        msg = "N must be an integer."
        raise InputValidationError(msg) from error
    if count < 0:
        msg = "N must be a non-negative integer."
        raise InputValidationError(msg)
    return count, output_file


def run(argv: list[str]) -> int:
    """Run the CLI workflow.

    Args:
        argv: Positional CLI arguments excluding the program name.

    Returns:
        Process exit code.
    """
    try:
        count, output_file = parse_args(argv)
        primes = generate_first_n_primes(count)
        write_primes_to_file(primes, output_file)
    except InputValidationError as error:
        print(str(error), file=sys.stderr)
        return USAGE_ERROR
    except OutputWriteError as error:
        print(str(error), file=sys.stderr)
        return RUNTIME_ERROR
    return SUCCESS


def main() -> None:
    """Execute the CLI entry point.

    Raises:
        SystemExit: Always raised with the CLI exit code.
    """
    raise SystemExit(run(sys.argv[1:]))
