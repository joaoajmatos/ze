import json
import re
from typing import Any

from ze_agents.errors import LLMJsonParseError

_FENCE = re.compile(r"```[A-Za-z0-9_-]*[ \t]*\r?\n?(.*?)(?:```|\Z)", re.DOTALL)
_DECODER = json.JSONDecoder()
_MISSING = object()


def parse_llm_json(
    raw: object, *, expect: type | tuple[type, ...] | None = None
) -> Any:
    """Parse the JSON value in an LLM reply.

    Models wrap JSON in markdown fences or prose even when ``response_format``
    asks for bare JSON, so try the whole reply, then each fenced block, then
    the first decodable ``{``/``[`` value. ``expect`` (e.g. ``dict``) rejects a
    value of another type. Raises ``LLMJsonParseError`` on failure.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise LLMJsonParseError("LLM returned an empty reply", raw=None)
    text = raw.strip()
    for candidate in _candidates(text):
        value = _decode(candidate, expect)
        if value is not _MISSING:
            return value
    wanted = "JSON" if expect is None else f"a JSON {_type_names(expect)}"
    raise LLMJsonParseError(f"LLM reply did not contain {wanted}", raw=text[:200])


def _type_names(expect: type | tuple[type, ...]) -> str:
    types = expect if isinstance(expect, tuple) else (expect,)
    return "/".join(
        "object" if t is dict else "array" if t is list else t.__name__ for t in types
    )


def _candidates(text: str):
    yield text
    for match in _FENCE.finditer(text):
        yield match.group(1).strip()


def _decode(text: str, expect: type | tuple[type, ...] | None) -> Any:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        pass
    else:
        if expect is None or isinstance(value, expect):
            return value
    for index, char in enumerate(text):
        if char not in "{[":
            continue
        try:
            value, _ = _DECODER.raw_decode(text, index)
        except json.JSONDecodeError:
            continue
        if expect is None or isinstance(value, expect):
            return value
    return _MISSING
