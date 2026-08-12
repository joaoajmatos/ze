from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field

import httpx

from ze_skills.errors import SkillParseError
from ze_skills.parser import ParsedSkill, parse_skill_md

_SCRIPT_EXTENSIONS = {".py", ".sh", ".js", ".ts", ".rb", ".pl"}

_CONTENT_TYPES = {
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
    ".json": "application/json",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
    ".csv": "text/csv",
}


@dataclass
class FetchedReferenceFile:
    filename: str
    content: str
    content_type: str


@dataclass
class FetchedSkill:
    """Result of `fetch_skill_source()` — the parsed `SKILL.md` plus any
    non-script supporting reference files found alongside it (FR-022)."""

    parsed: ParsedSkill
    reference_files: list[FetchedReferenceFile] = field(default_factory=list)


def _content_type_for(filename: str) -> str:
    for ext, ctype in _CONTENT_TYPES.items():
        if filename.lower().endswith(ext):
            return ctype
    return "text/plain"


def _is_script(filename: str) -> bool:
    return any(filename.lower().endswith(ext) for ext in _SCRIPT_EXTENSIONS)


async def _get(url: str, client: httpx.AsyncClient) -> httpx.Response:
    try:
        response = await client.get(url, follow_redirects=True)
    except httpx.HTTPError as exc:
        raise SkillParseError(f"Failed to fetch {url}: {exc}") from exc
    if response.status_code >= 400:
        raise SkillParseError(f"Failed to fetch {url}: HTTP {response.status_code}")
    return response


def _parse_zip_archive(content: bytes, url: str) -> FetchedSkill:
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise SkillParseError(f"{url} is not a valid zip archive: {exc}") from exc

    skill_md_name = next(
        (n for n in archive.namelist() if n.split("/")[-1] == "SKILL.md"), None
    )
    if skill_md_name is None:
        raise SkillParseError(f"Archive at {url} does not contain a SKILL.md file")

    skill_md_text = archive.read(skill_md_name).decode("utf-8")
    parsed = parse_skill_md(skill_md_text)

    reference_files: list[FetchedReferenceFile] = []
    has_script_file = False
    for name in archive.namelist():
        if name == skill_md_name or name.endswith("/"):
            continue
        basename = name.split("/")[-1]
        if not basename:
            continue
        if _is_script(basename):
            has_script_file = True
            continue
        try:
            file_content = archive.read(name).decode("utf-8")
        except UnicodeDecodeError:
            # Binary supporting file — not injectable as context text; skip storing.
            continue
        reference_files.append(
            FetchedReferenceFile(
                filename=name,
                content=file_content,
                content_type=_content_type_for(basename),
            )
        )

    if has_script_file:
        parsed.has_unsupported_scripts = True

    return FetchedSkill(parsed=parsed, reference_files=reference_files)


async def fetch_skill_source(
    url: str, client: httpx.AsyncClient | None = None
) -> FetchedSkill:
    """Fetch and parse a skill from a URL: either a direct `SKILL.md` file or a
    zip archive containing `SKILL.md` plus supporting reference files.

    Raises `SkillParseError` on an unreachable URL, a non-2xx response, an
    invalid archive, or a `SKILL.md` that fails to parse (FR-003).
    """
    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=15.0)
    try:
        response = await _get(url, active_client)
    finally:
        if owns_client:
            await active_client.aclose()

    is_zip = url.lower().endswith(".zip") or response.content[:4] == b"PK\x03\x04"
    if is_zip:
        return _parse_zip_archive(response.content, url)

    try:
        text = response.text
    except UnicodeDecodeError as exc:
        raise SkillParseError(f"Could not decode {url} as text: {exc}") from exc

    parsed = parse_skill_md(text)
    return FetchedSkill(parsed=parsed, reference_files=[])
