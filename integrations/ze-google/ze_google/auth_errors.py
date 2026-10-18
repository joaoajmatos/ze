from __future__ import annotations

from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError

_MAX_DEPTH = 5


def is_auth_failure(exc: BaseException) -> bool:
    """True when `exc` or an exception chained under it is a token refresh failure or a 401 from Google."""
    pending: list[tuple[BaseException, int]] = [(exc, 0)]
    seen: set[int] = set()
    while pending:
        current, depth = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, RefreshError):
            return True
        if isinstance(current, HttpError) and current.resp.status == 401:
            return True
        if depth >= _MAX_DEPTH:
            continue
        for link in (current.__cause__, current.__context__):
            if link is not None:
                pending.append((link, depth + 1))
    return False
