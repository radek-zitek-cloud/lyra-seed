"""Prime number generation helpers."""

from math import isqrt

from prime_cli_writer.exceptions import InputValidationError


def is_prime(value: int) -> bool:
    """Return whether a value is prime.

    Args:
        value: Integer to evaluate.

    Returns:
        True if the value is prime, otherwise False.
    """
    if value < 2:
        return False
    if value == 2:
        return True
    if value % 2 == 0:
        return False
    limit = isqrt(value)
    for candidate in range(3, limit + 1, 2):
        if value % candidate == 0:
            return False
    return True


def generate_first_n_primes(count: int) -> list[int]:
    """Generate the first count prime numbers.

    Args:
        count: Number of primes to generate.

    Returns:
        A list of prime numbers in ascending order.

    Raises:
        InputValidationError: If count is negative.
    """
    if count < 0:
        msg = "N must be a non-negative integer."
        raise InputValidationError(msg)
    primes: list[int] = []
    candidate = 2
    while len(primes) < count:
        if is_prime(candidate):
            primes.append(candidate)
        candidate += 1
    return primes
