"""Shared dataclasses for the ze_eval package."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class JudgeScore:
    quality: int
    tone: int
    tool_use: int | None
    pass_: bool
    reasoning: str

    def to_dict(self) -> dict:
        return {
            "quality": self.quality,
            "tone": self.tone,
            "tool_use": self.tool_use,
            "pass": self.pass_,
            "reasoning": self.reasoning,
        }


@dataclass
class VerifyResult:
    table: str
    where: dict
    expect: str
    actual_count: int
    passed: bool
    error: str | None = None

    def summary(self) -> str:
        conds = ", ".join(f"{k}={v!r}" for k, v in self.where.items())
        status = "PASS" if self.passed else "FAIL"
        return f"{status} {self.table}({conds}) expect={self.expect} got={self.actual_count}"


@dataclass
class SessionMetrics:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    llm_duration_ms: int
    llm_calls: int
    models: list[str]
