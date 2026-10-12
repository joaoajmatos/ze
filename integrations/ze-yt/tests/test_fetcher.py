import re
from unittest.mock import AsyncMock

import pytest

from ze_ingestion.errors import FetchError
from ze_ingestion.types import ContentType
from ze_yt.fetcher import YtDlpFetcher


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=abc",
        "https://youtu.be/abc",
        "https://www.instagram.com/reel/abc/",
        "https://www.tiktok.com/@u/video/1",
        "https://vimeo.com/123",
        "https://x.com/user/status/1",
    ],
)
def test_video_urls_match(url: str) -> None:
    assert any(re.search(p, url, re.I) for p in YtDlpFetcher.url_patterns)


def test_plain_page_does_not_match() -> None:
    url = "https://example.com/article"
    assert not any(re.search(p, url, re.I) for p in YtDlpFetcher.url_patterns)


async def test_fetch_returns_audio() -> None:
    client = AsyncMock()
    client.download_audio.return_value = b"mp3"
    raw = await YtDlpFetcher(client=client).fetch("https://youtu.be/abc")
    assert raw.content_type == ContentType.AUDIO
    assert raw.data == b"mp3"
    assert raw.mime_type == "audio/mpeg"


async def test_fetch_wraps_client_errors() -> None:
    client = AsyncMock()
    client.download_audio.side_effect = RuntimeError("boom")
    with pytest.raises(FetchError):
        await YtDlpFetcher(client=client).fetch("https://youtu.be/abc")
