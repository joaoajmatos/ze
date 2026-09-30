"""OpenRouter System One client — typed judgments via POST /systemone."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import structlog

from ze_agents.system_one import (
    SkipReason,
    SystemOneAnswer,
    SystemOneQuestion,
    SystemOneResult,
)
from ze_logging import get_logger

_RETRYABLE_STATUS = {429, 500, 502, 503, 504, 529}
_OVERLOAD_STATUS = {429, 529}
_BACKOFFS = [1.0, 2.0, 4.0]
DEFAULT_MODEL = "typesafe/jev-1.13"
DEFAULT_TIMEOUT_MS = 2000
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


def _question_to_wire(question: SystemOneQuestion | dict[str, Any]) -> dict[str, Any]:
    if isinstance(question, SystemOneQuestion):
        return question.to_wire()
    return dict(question)


def _invalid_request(
    state: str | dict,
    questions: dict[str, SystemOneQuestion] | dict[str, Any],
) -> bool:
    if not questions:
        return True
    if state is None or state == "" or state == {}:
        return True
    for question in questions.values():
        kind = question.type if isinstance(question, SystemOneQuestion) else question.get("type")
        instructions = (
            question.instructions
            if isinstance(question, SystemOneQuestion)
            else question.get("instructions")
        )
        if kind not in ("noul", "choice", "score") or not instructions:
            return True
    return False


def _parse_answer(raw: dict[str, Any]) -> SystemOneAnswer:
    kind = raw.get("type") or "noul"
    return SystemOneAnswer(
        type=kind,
        noul=raw.get("noul"),
        choice=raw.get("choice"),
        score=raw.get("score"),
        probabilities=raw.get("probabilities"),
        confidence=raw.get("confidence"),
    )


def _skip(reason: SkipReason, latency_ms: int) -> SystemOneResult:
    return SystemOneResult(outcome="skip", skip_reason=reason, latency_ms=latency_ms)


def _elapsed_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def _result_from_payload(data: dict[str, Any], latency_ms: int) -> SystemOneResult:
    raw_answers = data.get("answers") or {}
    usage = data.get("usage") or {}
    return SystemOneResult(
        outcome="ok",
        model=data.get("model"),
        provider=data.get("provider"),
        id=data.get("id"),
        answers={qid: _parse_answer(raw) for qid, raw in raw_answers.items()},
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
        latency_ms=latency_ms,
    )


class DisabledSystemOneClient:
    async def evaluate(
        self,
        state: str | dict,
        questions: dict[str, SystemOneQuestion],
    ) -> SystemOneResult:
        return _skip("disabled", 0)


class OpenRouterSystemOneClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
        http_referer: str = "https://github.com/ze",
        title: str = "Ze Personal Assistant",
        cost_tracker=None,
        logger: structlog.BoundLogger | None = None,
    ) -> None:
        self._api_key = api_key or ""
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_s = max(timeout_ms, 1) / 1000.0
        self._http_referer = http_referer
        self._title = title
        self._cost_tracker = cost_tracker
        self._log = logger or get_logger(__name__)

    async def evaluate(
        self,
        state: str | dict,
        questions: dict[str, SystemOneQuestion],
    ) -> SystemOneResult:
        start = time.monotonic()
        if _invalid_request(state, questions):
            self._log.warning("system_one_skip", reason="invalid_request")
            return _skip("invalid_request", _elapsed_ms(start))
        if not self._api_key:
            self._log.info("system_one_skip", reason="missing_key")
            return _skip("missing_key", _elapsed_ms(start))

        payload = {
            "model": self._model,
            "state": state,
            "questions": {qid: _question_to_wire(q) for qid, q in questions.items()},
        }
        url = f"{self._base_url}/systemone"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self._http_referer,
            "X-OpenRouter-Title": self._title,
        }

        last_status: int | None = None
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self._timeout_s)) as http:
                for attempt, backoff in enumerate(_BACKOFFS, start=1):
                    try:
                        response = await http.post(url, json=payload, headers=headers)
                    except httpx.TimeoutException:
                        self._log.warning("system_one_skip", reason="timeout")
                        return _skip("timeout", _elapsed_ms(start))
                    except httpx.HTTPError as exc:
                        self._log.warning("system_one_skip", reason="error", error=str(exc))
                        return _skip("error", _elapsed_ms(start))

                    last_status = response.status_code
                    if response.status_code in _RETRYABLE_STATUS and attempt < len(_BACKOFFS):
                        await asyncio.sleep(backoff)
                        continue
                    if response.status_code in _OVERLOAD_STATUS:
                        self._log.warning(
                            "system_one_skip",
                            reason="overload",
                            status=response.status_code,
                        )
                        return _skip("overload", _elapsed_ms(start))
                    if response.status_code >= 400:
                        self._log.warning(
                            "system_one_skip",
                            reason="error",
                            status=response.status_code,
                        )
                        return _skip("error", _elapsed_ms(start))
                    try:
                        data = response.json()
                    except ValueError:
                        self._log.warning("system_one_skip", reason="error", error="bad_json")
                        return _skip("error", _elapsed_ms(start))
                    result = _result_from_payload(data, _elapsed_ms(start))
                    self._record_cost(result)
                    return result
        except httpx.TimeoutException:
            self._log.warning("system_one_skip", reason="timeout")
            return _skip("timeout", _elapsed_ms(start))
        except Exception as exc:
            self._log.warning("system_one_skip", reason="error", error=str(exc))
            return _skip("error", _elapsed_ms(start))

        reason: SkipReason = "overload" if last_status in _OVERLOAD_STATUS else "error"
        return _skip(reason, _elapsed_ms(start))

    def _record_cost(self, result: SystemOneResult) -> None:
        if self._cost_tracker is None or result.outcome != "ok":
            return
        prompt = result.input_tokens or 0
        completion = result.output_tokens or 0
        self._cost_tracker.record(
            model=result.model or self._model,
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=prompt + completion,
            duration_ms=result.latency_ms,
            generation_id=result.id,
        )


def build_system_one_client(settings: Any, *, cost_tracker=None):
    config: dict[str, Any] = {}
    raw = getattr(settings, "config", None)
    if isinstance(raw, dict):
        config = raw.get("system_one") or {}
    if not bool(config.get("enabled", False)):
        return DisabledSystemOneClient()
    return OpenRouterSystemOneClient(
        api_key=getattr(settings, "openrouter_api_key", "") or "",
        base_url=getattr(settings, "openrouter_base_url", DEFAULT_BASE_URL),
        model=config.get("model", DEFAULT_MODEL),
        timeout_ms=int(config.get("timeout_ms", DEFAULT_TIMEOUT_MS)),
        http_referer=getattr(settings, "openrouter_http_referer", "https://github.com/ze"),
        title=getattr(settings, "openrouter_title", "Ze Personal Assistant"),
        cost_tracker=cost_tracker,
    )
