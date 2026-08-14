from __future__ import annotations

from ze_workspace.sanitize import redact


def test_openrouter_key_assignment_redacted():
    raw = "OPENROUTER_API_KEY=sk-or-v1-secret leftover"
    out = redact(raw)
    assert "sk-or-v1-secret" not in out
    assert "OPENROUTER_API_KEY=" not in out
    assert "[redacted]" in out
    assert "leftover" in out


def test_database_url_and_api_key_redacted():
    raw = "DATABASE_URL=postgres://ze:ze@db/ze ZE_API_KEY=abc123"
    out = redact(raw)
    assert "postgres://" not in out
    assert "abc123" not in out


def test_workspace_token_redacted():
    assert "dev-token" not in redact("WORKSPACE_API_TOKEN=dev-token")


def test_generic_secret_token_password_suffixes():
    raw = "FOO_SECRET=aaa BAR_TOKEN=bbb BAZ_PASSWORD=ccc"
    out = redact(raw)
    assert "aaa" not in out
    assert "bbb" not in out
    assert "ccc" not in out


def test_unrelated_text_preserved():
    assert redact("hello world") == "hello world"
    assert redact(None) == ""
    assert redact("") == ""
