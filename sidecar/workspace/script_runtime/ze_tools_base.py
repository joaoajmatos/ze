"""Sandbox side of ze_tools: one JSON line out per request, one JSON line back."""

import json
import os

_REQ = os.fdopen(int(os.environ["ZE_REQ_FD"]), "w", encoding="utf-8")
_REP = os.fdopen(int(os.environ["ZE_REP_FD"]), "r", encoding="utf-8")
_seq = 0


class ToolError(Exception):
    pass


def _call(tool, args):
    global _seq
    _seq += 1
    _REQ.write(json.dumps({"seq": _seq, "tool": tool, "args": args}) + "\n")
    _REQ.flush()
    line = _REP.readline()
    if not line:
        raise ToolError("sandbox closed")
    reply = json.loads(line)
    if not reply.get("ok"):
        raise ToolError(reply.get("error", "failed"))
    return reply.get("value")


def _finish(value=None, writes=None):
    _REQ.write(json.dumps({"finish": value, "writes": writes or []}) + "\n")
    _REQ.flush()
