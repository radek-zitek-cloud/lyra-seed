"""I/O helpers for serializing and writing prime numbers."""

from pathlib import Path

from prime_cli_writer.exceptions import OutputWriteError


def format_primes(primes: list[int]) -> str:
    """Serialize prime numbers to newline-delimited text.

    Args:
        primes: Prime numbers to serialize.

    Returns:
        Newline-delimited prime numbers, with a trailing newline when non-empty.
    """
    if not primes:
        return ""
    return "\n".join(str(prime) for prime in primes) + "\n"


def write_primes_to_file(primes: list[int], output_path: str) -> None:
    """Write prime numbers to the output path.

    Args:
        primes: Prime numbers to write.
        output_path: Destination file path.

    Raises:
        OutputWriteError: If file writing fails.
    """
    path = Path(output_path)
    try:
        path.write_text(format_primes(primes), encoding="utf-8")
    except OSError as error:
        msg = f"Failed to write output file: {output_path}"
        raise OutputWriteError(msg) from error
