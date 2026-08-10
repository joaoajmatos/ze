"""Tests for FinanceSignalSource (Claim Topology, FR-013)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from ze_agents.claims import ClaimKind

from ze_finance.signals.finance import FinanceSignalSource
from ze_finance.types import Asset, AssetClass, Transaction, TransactionType


def _tx(**kwargs) -> Transaction:
    defaults = dict(
        id="tx1",
        account_id="acc1",
        transaction_type=TransactionType.BUY,
        asset=Asset(ticker="AAPL", name="Apple", asset_class=AssetClass.EQUITY, currency="USD"),
        quantity=Decimal("10"),
        price=Decimal("100"),
        fees=Decimal("0"),
        currency="USD",
        settled_at=datetime.now(timezone.utc),
        notes="Large buy",
    )
    defaults.update(kwargs)
    return Transaction(**defaults)


async def test_source_key():
    assert FinanceSignalSource.source_key == "finance"


async def test_pnl_swing_signal_carries_fact_claim_kind_and_confidence():
    source = FinanceSignalSource()
    source.check_pnl_swing(Decimal("100"))
    source.check_pnl_swing(Decimal("120"))  # 20% swing > 5% threshold

    [signal] = await source.poll(since=datetime.now(timezone.utc))
    assert signal.claim_kind == ClaimKind.FACT
    assert signal.confidence != signal.magnitude
    assert signal.payload["signal_type"] == "finance.pnl_swing"


async def test_large_transaction_signal_carries_fact_claim_kind_and_confidence():
    source = FinanceSignalSource(large_tx_threshold=Decimal("500"))
    source.check_large_transactions([_tx(quantity=Decimal("10"), price=Decimal("100"))])

    [signal] = await source.poll(since=datetime.now(timezone.utc))
    assert signal.claim_kind == ClaimKind.FACT
    assert signal.confidence != signal.magnitude
    assert signal.payload["signal_type"] == "finance.large_transaction"


async def test_below_threshold_transaction_produces_no_signal():
    source = FinanceSignalSource(large_tx_threshold=Decimal("500"))
    source.check_large_transactions([_tx(quantity=Decimal("1"), price=Decimal("10"))])

    signals = await source.poll(since=datetime.now(timezone.utc))
    assert signals == []
