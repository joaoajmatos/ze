from __future__ import annotations

import io
import zipfile

import httpx
import pytest

from ze_skills.errors import SkillParseError
from ze_skills.importer import fetch_skill_source

VALID_SKILL_MD = """---
name: Pirate Speak
description: Ends every response with "Arrr!".
---
Always end your response with the exact phrase "Arrr!" on its own line.
"""


class _FakeAsyncClient:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc
        self.aclose_called = False

    async def get(self, url, follow_redirects=True):
        if self._exc is not None:
            raise self._exc
        return self._response

    async def aclose(self):
        self.aclose_called = True


def _text_response(status_code: int, text: str) -> httpx.Response:
    return httpx.Response(
        status_code, text=text, request=httpx.Request("GET", "http://x")
    )


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_fetch_direct_skill_md_url():
    client = _FakeAsyncClient(_text_response(200, VALID_SKILL_MD))

    result = await fetch_skill_source("http://example.com/SKILL.md", client=client)

    assert result.parsed.name == "Pirate Speak"
    assert result.reference_files == []


@pytest.mark.asyncio
async def test_fetch_zip_archive_with_reference_files():
    archive = _zip_bytes(
        {
            "SKILL.md": VALID_SKILL_MD.encode(),
            "reference.md": b"# Extra reference content",
            "scripts/helper.py": b"print('should not be stored')",
        }
    )
    response = httpx.Response(
        200, content=archive, request=httpx.Request("GET", "http://x")
    )
    client = _FakeAsyncClient(response)

    result = await fetch_skill_source("http://example.com/skill.zip", client=client)

    assert result.parsed.name == "Pirate Speak"
    assert result.parsed.has_unsupported_scripts is True
    filenames = [f.filename for f in result.reference_files]
    assert "reference.md" in filenames
    assert not any("helper.py" in f for f in filenames)


@pytest.mark.asyncio
async def test_fetch_zip_missing_skill_md_raises():
    archive = _zip_bytes({"README.md": b"no SKILL.md here"})
    response = httpx.Response(
        200, content=archive, request=httpx.Request("GET", "http://x")
    )
    client = _FakeAsyncClient(response)

    with pytest.raises(SkillParseError):
        await fetch_skill_source("http://example.com/skill.zip", client=client)


@pytest.mark.asyncio
async def test_unreachable_url_raises_parse_error():
    client = _FakeAsyncClient(exc=httpx.ConnectError("connection refused"))

    with pytest.raises(SkillParseError):
        await fetch_skill_source("http://example.com/SKILL.md", client=client)


@pytest.mark.asyncio
async def test_non_2xx_response_raises_parse_error():
    client = _FakeAsyncClient(_text_response(404, "not found"))

    with pytest.raises(SkillParseError):
        await fetch_skill_source("http://example.com/does-not-exist.md", client=client)


@pytest.mark.asyncio
async def test_invalid_skill_md_content_raises_parse_error():
    client = _FakeAsyncClient(_text_response(200, "not a valid skill file"))

    with pytest.raises(SkillParseError):
        await fetch_skill_source("http://example.com/SKILL.md", client=client)
