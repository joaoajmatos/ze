import pytest

from ze_proactive.job import proactive_job


def test_decorator_returns_the_class_unchanged() -> None:
    @proactive_job
    class _Job:
        job_id = "decorated"

        async def run(self) -> None: ...

    assert _Job.job_id == "decorated"


def test_decorator_rejects_a_class_without_job_id() -> None:
    class _NoId:
        async def run(self) -> None: ...

    with pytest.raises(TypeError, match="job_id"):
        proactive_job(_NoId)
