from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from ze.contacts.types import Person
from ze.telegram.commands import contacts_search, contacts_summary


def _make_person(**kwargs) -> Person:
    defaults = dict(
        id=uuid4(),
        name="João Silva",
        classification="professional",
        relationship_to_user="charter operator",
        contact_info={},
        confirmed=True,
        dismissed=False,
        confidence=0.9,
    )
    defaults.update(kwargs)
    return Person(**defaults)


# ── contacts_summary ──────────────────────────────────────────────────────────

async def test_summary_no_contacts():
    store = MagicMock()
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    store._pool.acquire = MagicMock(return_value=_async_ctx(conn))

    result = await contacts_summary(store)
    assert "No contacts yet" in result


async def test_summary_lists_confirmed_contacts():
    pid = uuid4()
    row = _make_row(pid, "Maria Costa", "personal", "university friend")
    store = MagicMock()
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[row])
    store._pool.acquire = MagicMock(return_value=_async_ctx(conn))

    result = await contacts_summary(store)
    assert "Maria Costa" in result
    assert "personal" in result
    assert "university friend" in result


async def test_summary_includes_count():
    rows = [_make_row(uuid4(), f"Person {i}", "professional", "colleague") for i in range(3)]
    store = MagicMock()
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=rows)
    store._pool.acquire = MagicMock(return_value=_async_ctx(conn))

    result = await contacts_summary(store)
    assert "(3)" in result


async def test_summary_shows_search_hint():
    row = _make_row(uuid4(), "Alice", "personal", "friend")
    store = MagicMock()
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[row])
    store._pool.acquire = MagicMock(return_value=_async_ctx(conn))

    result = await contacts_summary(store)
    assert "/contacts" in result


# ── contacts_search ───────────────────────────────────────────────────────────

async def test_search_no_results():
    store = AsyncMock()
    store.search = AsyncMock(return_value=[])

    result = await contacts_search(store, "nonexistent")
    assert "No contacts matching" in result
    assert "nonexistent" in result


async def test_search_returns_matches():
    person = _make_person(name="Ana Ferreira", relationship_to_user="aviation lawyer")
    store = AsyncMock()
    store.search = AsyncMock(return_value=[person])

    result = await contacts_search(store, "aviation")
    assert "Ana Ferreira" in result
    assert "aviation lawyer" in result


async def test_search_marks_unconfirmed():
    person = _make_person(confirmed=False)
    store = AsyncMock()
    store.search = AsyncMock(return_value=[person])

    result = await contacts_search(store, "joão")
    assert "unconfirmed" in result


async def test_search_does_not_mark_confirmed():
    person = _make_person(confirmed=True)
    store = AsyncMock()
    store.search = AsyncMock(return_value=[person])

    result = await contacts_search(store, "joão")
    assert "unconfirmed" not in result


async def test_search_escapes_html_in_query():
    store = AsyncMock()
    store.search = AsyncMock(return_value=[])

    result = await contacts_search(store, "<script>")
    assert "<script>" not in result
    assert "&lt;script&gt;" in result


async def test_search_uses_confirmed_false_flag():
    store = AsyncMock()
    store.search = AsyncMock(return_value=[])

    await contacts_search(store, "test")
    store.search.assert_awaited_once_with("test", confirmed_only=False)


# ── helpers ───────────────────────────────────────────────────────────────────

class _async_ctx:
    def __init__(self, obj):
        self._obj = obj
    async def __aenter__(self):
        return self._obj
    async def __aexit__(self, *_):
        pass


def _make_row(person_id, name, classification, relationship):
    from unittest.mock import MagicMock
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "id": person_id,
        "name": name,
        "aliases": [],
        "classification": classification,
        "classification_confidence": 0.9,
        "relationship_to_user": relationship,
        "contact_info": {},
        "notes": "",
        "confirmed": True,
        "dismissed": False,
        "confidence": 0.9,
        "first_seen": None,
        "last_mentioned": None,
        "created_at": None,
        "updated_at": None,
    }[key]
    return row
