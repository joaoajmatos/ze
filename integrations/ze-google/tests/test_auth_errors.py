from __future__ import annotations

from google.auth.exceptions import RefreshError

from ze_google import is_auth_failure


def test_direct_refresh_error():
    assert is_auth_failure(RefreshError("invalid_grant"))


def test_refresh_error_as_cause():
    try:
        try:
            raise RefreshError("invalid_grant")
        except RefreshError as err:
            raise RuntimeError("poll failed") from err
    except RuntimeError as exc:
        assert is_auth_failure(exc)


def test_refresh_error_as_context_two_levels_down():
    try:
        try:
            try:
                raise RefreshError("invalid_grant")
            except RefreshError:
                raise ValueError("middle")
        except ValueError:
            raise RuntimeError("outer")
    except RuntimeError as exc:
        assert is_auth_failure(exc)


def test_other_errors_are_not_auth_failures():
    assert not is_auth_failure(RuntimeError("network"))


def test_stops_at_depth_five():
    exc: BaseException = RefreshError("invalid_grant")
    for _ in range(6):
        wrapper = RuntimeError("wrap")
        wrapper.__cause__ = exc
        exc = wrapper
    assert not is_auth_failure(exc)

    exc = RefreshError("invalid_grant")
    for _ in range(5):
        wrapper = RuntimeError("wrap")
        wrapper.__cause__ = exc
        exc = wrapper
    assert is_auth_failure(exc)


def test_cyclic_chain_terminates():
    a = RuntimeError("a")
    b = RuntimeError("b")
    a.__cause__ = b
    b.__cause__ = a
    assert not is_auth_failure(a)
