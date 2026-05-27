from __future__ import annotations

import logging


class _BoundLogger:
    """Thin structlog-style wrapper around stdlib logging."""

    def __init__(self, logger: logging.Logger, context: dict) -> None:
        self._logger = logger
        self._context = context

    def bind(self, **kwargs: object) -> _BoundLogger:
        return _BoundLogger(self._logger, {**self._context, **kwargs})

    def _format(self, event: str, kwargs: dict) -> str:
        parts = [event]
        merged = {**self._context, **kwargs}
        if merged:
            parts.append(" ".join(f"{k}={v!r}" for k, v in merged.items()))
        return " ".join(parts)

    def debug(self, event: str, **kwargs: object) -> None:
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug(self._format(event, kwargs))

    def info(self, event: str, **kwargs: object) -> None:
        if self._logger.isEnabledFor(logging.INFO):
            self._logger.info(self._format(event, kwargs))

    def warning(self, event: str, **kwargs: object) -> None:
        self._logger.warning(self._format(event, kwargs))

    def error(self, event: str, **kwargs: object) -> None:
        self._logger.error(self._format(event, kwargs))

    def exception(self, event: str, **kwargs: object) -> None:
        self._logger.exception(self._format(event, kwargs))


def get_logger(name: str) -> _BoundLogger:
    return _BoundLogger(logging.getLogger(name), {})
