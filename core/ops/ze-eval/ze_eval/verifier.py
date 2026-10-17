"""
DB outcome verification for Ze eval scenarios.

Runs declarative checks against Ze's database after a scenario executes,
then cleans up eval-created rows so runs don't contaminate each other.

Scenario YAML format:

    verify:
      - table: user_reminders
        where:
          label__icontains: dentist   # case-insensitive substring
          sent: false                 # exact match
        expect: exists                # 'exists', 'not_exists' or 'any' (cleanup only)
        cleanup: true                 # delete matching rows after check (default: true)
        created_since_run: true       # only rows with created_at at or after the scenario start

Cleanup deletes every row the where clause matches, so scenarios that match on
words a user could also have written must set created_since_run. Even so, run
evals against a throwaway database.

Requires DATABASE_URL env var (same as Ze).
"""

from __future__ import annotations

import os
from datetime import datetime

import asyncpg

from ze_eval.types import VerifyResult


def _scoped_where(check: dict, since: datetime | None) -> tuple[str, list]:
    where_sql, params = _build_where(check.get("where", {}))
    if check.get("created_since_run"):
        if since is None:
            raise ValueError("created_since_run needs the scenario start time")
        params = [*params, since]
        where_sql = f"({where_sql}) AND created_at >= ${len(params)}"
    return where_sql, params


def _build_where(where: dict) -> tuple[str, list]:
    if not where:
        return "TRUE", []
    clauses: list[str] = []
    params: list = []
    i = 1
    for key, value in where.items():
        if key.endswith("__icontains"):
            col = key[: -len("__icontains")]
            clauses.append(f"{col} ILIKE ${i}")
            params.append(f"%{value}%")
        else:
            if value is True:
                clauses.append(f"{key} = TRUE")
            elif value is False:
                clauses.append(f"{key} = FALSE")
            else:
                clauses.append(f"{key} = ${i}")
                params.append(value)
                i += 1
            continue
        i += 1
    return " AND ".join(clauses), params


async def _check(
    conn: asyncpg.Connection, check: dict, since: datetime | None = None
) -> VerifyResult:
    table = check["table"]
    where = check.get("where", {})
    expect = check.get("expect", "exists")
    where_sql, params = _scoped_where(check, since)

    count = await conn.fetchval(
        f"SELECT COUNT(*) FROM {table} WHERE {where_sql}", *params
    )
    count = int(count)

    if expect == "exists":
        passed = count > 0
    elif expect == "not_exists":
        passed = count == 0
    elif expect == "any":
        passed = True
    else:
        passed = False

    return VerifyResult(
        table=table, where=where, expect=expect, actual_count=count, passed=passed
    )


async def _cleanup(
    conn: asyncpg.Connection, check: dict, since: datetime | None = None
) -> None:
    table = check["table"]
    where = check.get("where", {})
    if not where:
        return
    where_sql, params = _scoped_where(check, since)
    await conn.execute(f"DELETE FROM {table} WHERE {where_sql}", *params)


async def run_verification(
    checks: list[dict], db_url: str | None = None, since: datetime | None = None
) -> list[VerifyResult]:
    """Run all checks then clean up eval-created rows."""
    url = db_url or os.environ.get(
        "DATABASE_URL", "postgresql://ze:ze@localhost:5432/ze"
    )
    results: list[VerifyResult] = []

    try:
        conn = await asyncpg.connect(url)
    except Exception as exc:
        return [
            VerifyResult(
                table=c.get("table", "?"),
                where=c.get("where", {}),
                expect=c.get("expect", "exists"),
                actual_count=0,
                passed=False,
                error=f"DB connection failed: {exc}",
            )
            for c in checks
        ]

    try:
        for check in checks:
            try:
                result = await _check(conn, check, since)
                results.append(result)
                if check.get("cleanup", True):
                    await _cleanup(conn, check, since)
            except Exception as exc:
                results.append(
                    VerifyResult(
                        table=check.get("table", "?"),
                        where=check.get("where", {}),
                        expect=check.get("expect", "exists"),
                        actual_count=0,
                        passed=False,
                        error=str(exc),
                    )
                )
    finally:
        await conn.close()

    return results


def outcome_correct(results: list[VerifyResult]) -> bool:
    """True only if every check passed."""
    return bool(results) and all(r.passed for r in results)
