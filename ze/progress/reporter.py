import asyncio

from ze.progress.translations import ProgressTranslations


class ProgressReporter:
    """
    Passed into AgentContext. Agents call emit(key) to push a localized status
    message. The bot layer drains the queue and sends Telegram messages.
    """

    def __init__(self, queue: asyncio.Queue, translations: ProgressTranslations) -> None:
        self._queue = queue
        self._translations = translations

    async def emit(self, key: str, **kwargs: str) -> None:
        """Resolve key to a localized string and enqueue it. No-op if key unknown."""
        text = self._translations.resolve(key, **kwargs)
        if text is None:
            return
        try:
            self._queue.put_nowait(text)
        except asyncio.QueueFull:
            pass
