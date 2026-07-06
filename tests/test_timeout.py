import time

import pytest

from trade_digest.timeout import with_timeout


def test_with_timeout_returns_result_when_fast_enough():
    assert with_timeout(lambda: 42, timeout=1) == 42


def test_with_timeout_passes_args_and_kwargs():
    def add(a, b, *, c=0):
        return a + b + c

    assert with_timeout(add, 1, 2, c=3, timeout=1) == 6


def test_with_timeout_reraises_original_exception():
    def boom():
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        with_timeout(boom, timeout=1)


def test_with_timeout_raises_timeout_error_when_func_hangs():
    def hang():
        time.sleep(5)
        return "should never get here"

    with pytest.raises(TimeoutError):
        with_timeout(hang, timeout=0.05)
