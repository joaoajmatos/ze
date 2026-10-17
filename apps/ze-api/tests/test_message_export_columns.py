from __future__ import annotations


def test_message_export_selects_supersession_columns():
    import inspect

    from ze_core import bootstrap

    src = inspect.getsource(bootstrap.engine_data_domains)
    assert "SELECT * FROM {tbl}" in src
    assert '_engine_domain("messages.store", "messages")' in src
