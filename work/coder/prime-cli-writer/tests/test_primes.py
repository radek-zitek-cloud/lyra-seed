"""Tests for prime generation functions."""

import pytest

from prime_cli_writer.exceptions import InputValidationError
from prime_cli_writer.primes import generate_first_n_primes, is_prime


def test_is_prime_two_returns_true() -> None:
    assert is_prime(2) is True


def test_is_prime_composite_returns_false() -> None:
    assert is_prime(9) is False


def test_generate_first_n_primes_for_five_returns_expected_values() -> None:
    assert generate_first_n_primes(5) == [2, 3, 5, 7, 11]


def test_generate_first_n_primes_zero_returns_empty_list() -> None:
    assert generate_first_n_primes(0) == []


def test_generate_first_n_primes_one_returns_first_prime() -> None:
    assert generate_first_n_primes(1) == [2]


def test_generate_first_n_primes_negative_count_raises_error() -> None:
    with pytest.raises(InputValidationError):
        generate_first_n_primes(-1)
