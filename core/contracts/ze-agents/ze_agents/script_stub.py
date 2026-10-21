"""Pure helpers for programmatic tool use: the ze_tools stub and source identity."""

from __future__ import annotations

import hashlib
import io
import json
import keyword
import tokenize
from typing import Any

from ze_agents.scripts import ScriptError

_IMPORT_LINE = "from ze_tools_base import ToolError, _call, _finish"

_HELPERS = '''def propose(tool: str, **args) -> dict:
    """Describe a write that runs after the script."""
    return {"tool": tool, "args": args}


def finish(result, writes=None):
    """Return the answer and any proposed writes."""
    _finish(result, list(writes or []))'''

_ANNOTATIONS = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "array": "list",
    "object": "dict",
}

_RESERVED = frozenset({"propose", "finish", "ToolError", "_call", "_finish"})


def _is_identifier(name: Any) -> bool:
    return (
        isinstance(name, str)
        and name.isidentifier()
        and not keyword.iskeyword(name)
        and name not in _RESERVED
    )


def _annotation(spec: Any) -> str | None:
    if not isinstance(spec, dict):
        return None
    kind = spec.get("type")
    return _ANNOTATIONS.get(kind) if isinstance(kind, str) else None


def _escape_docstring(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _render_function(name: str, function: dict[str, Any]) -> str:
    parameters = function.get("parameters")
    if not isinstance(parameters, dict):
        parameters = {}
    properties = parameters.get("properties")
    if not isinstance(properties, dict):
        properties = {}
    required = set(parameters.get("required") or [])

    signature: list[str] = []
    entries: list[str] = []
    for prop, spec in properties.items():
        if not _is_identifier(prop):
            continue
        annotation = _annotation(spec)
        param = f"{prop}: {annotation}" if annotation else prop
        if prop not in required:
            param += " = None"
        signature.append(param)
        entries.append(f'"{prop}": {prop}')

    head = (
        f"def {name}({', '.join(['*', *signature])}):"
        if signature
        else f"def {name}():"
    )
    description = _escape_docstring(str(function.get("description") or ""))
    if entries:
        pairs = ", ".join(entries)
        body = (
            f'return _call("{name}", '
            f"{{k: v for k, v in {{{pairs}}}.items() if v is not None}})"
        )
    else:
        body = f'return _call("{name}", {{}})'
    return f'{head}\n    """{description}"""\n    {body}'


def build_stub(schemas: list[dict[str, Any]]) -> str:
    """Render one keyword-only Python function per data tool schema, sorted by name."""
    candidates: list[tuple[str, str, dict[str, Any]]] = []
    for schema in schemas:
        function = schema.get("function") if isinstance(schema, dict) else None
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        if not _is_identifier(name):
            continue
        candidates.append((name, json.dumps(function, sort_keys=True), function))

    functions: list[str] = []
    seen: set[str] = set()
    for name, _, function in sorted(candidates, key=lambda item: item[:2]):
        if name in seen:
            continue
        seen.add(name)
        functions.append(_render_function(name, function))

    return "\n\n\n".join([_IMPORT_LINE, *functions, _HELPERS]) + "\n"


def normalize_source(source: str) -> str:
    """Strip comments, blank lines and trailing whitespace; literals stay as written."""
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, SyntaxError) as exc:
        raise ScriptError("bad_request", f"source does not tokenize: {exc}") from exc

    lines = source.splitlines()
    inside_string: set[int] = set()
    for token in tokens:
        if token.type == tokenize.COMMENT:
            row, col = token.start
            lines[row - 1] = lines[row - 1][:col]
        elif token.type == tokenize.STRING and token.start[0] != token.end[0]:
            inside_string.update(range(token.start[0] + 1, token.end[0] + 1))

    kept: list[str] = []
    for number, line in enumerate(lines, start=1):
        if number in inside_string:
            kept.append(line)
            continue
        stripped = line.rstrip()
        if stripped:
            kept.append(stripped)
    return "\n".join(kept)


def source_hash(source: str) -> str:
    """Hash of the normalized source; used for traces and candidate names."""
    return hashlib.sha256(normalize_source(source).encode()).hexdigest()


def tool_signature(agent: str, inner_tool_names: list[str]) -> str:
    """Identity of a script's tool use: the agent and its distinct tools in first-call order."""
    ordered = list(dict.fromkeys(inner_tool_names))
    return hashlib.sha256(json.dumps([agent, ordered]).encode()).hexdigest()
