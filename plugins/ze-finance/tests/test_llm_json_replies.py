"""Finance LLM sites parse JSON from fenced and prose-wrapped replies."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from ze_finance.categoriser import CategoryInferrer
from ze_finance.errors import FinanceParseError
from ze_finance.ingestion.extractor import FinanceIngestionExtractor
from ze_finance.sources.csv import CsvSchemaInferrer
from ze_ingestion.types import ContentType, ProcessedContent

WRAPS = [
    pytest.param(lambda s: s, id="bare"),
    pytest.param(lambda s: f"```json\n{s}\n```", id="fenced"),
    pytest.param(lambda s: f"Here you go:\n```json\n{s}\n```\nCheers.", id="prose"),
    pytest.param(lambda s: f"Result: {s} (done)", id="inline-prose"),
]


def _client(reply: str) -> MagicMock:
    client = MagicMock()
    client.complete = AsyncMock(return_value=reply)
    return client


@pytest.mark.parametrize("wrap", WRAPS)
async def test_categoriser(wrap):
    inf = CategoryInferrer(_client(wrap(json.dumps(["Food & Dining"]))), True)
    assert await inf._call_llm(["UBER EATS"]) == ["Food & Dining"]


_MAPPING = {
    "date_column": "Date",
    "amount_column": "Amount",
    "description_column": "Description",
}


@pytest.mark.parametrize("wrap", WRAPS)
async def test_csv_schema_inferrer(wrap):
    inf = CsvSchemaInferrer(_client(wrap(json.dumps(_MAPPING))), MagicMock())
    mapping = await inf._call_llm("src", ["Date", "Amount", "Description"], [["a"]])
    assert mapping.amount_column == "Amount"


async def test_csv_schema_inferrer_garbage_raises_finance_error():
    inf = CsvSchemaInferrer(_client("no idea"), MagicMock())
    with pytest.raises(FinanceParseError):
        await inf._call_llm("src", ["Date"], [["a"]])


@pytest.mark.parametrize("wrap", WRAPS)
async def test_ingestion_extractor(wrap):
    items = [
        {"date": "2025-01-02", "amount": "-4.50", "description": "Coffee"},
    ]
    ext = FinanceIngestionExtractor(
        transaction_store=MagicMock(),
        llm_client=_client(wrap(json.dumps(items))),
        model="m",
        csv_inferrer=MagicMock(),
    )
    content = ProcessedContent(
        content_type=ContentType.PDF, source_url="https://x/y.pdf", text="stmt"
    )
    assert len(await ext._parse_llm(content)) == 1
