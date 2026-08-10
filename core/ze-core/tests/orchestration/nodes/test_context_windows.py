from ze_core.openrouter.context_windows import (
    DEFAULT_CONTEXT_WINDOW_TOKENS,
    MODEL_CONTEXT_WINDOWS,
    get_context_window,
)


def test_known_model_returns_table_value():
    model = next(iter(MODEL_CONTEXT_WINDOWS))
    assert get_context_window(model) == MODEL_CONTEXT_WINDOWS[model]


def test_unknown_model_returns_default():
    assert get_context_window("some/unlisted-model") == DEFAULT_CONTEXT_WINDOW_TOKENS
