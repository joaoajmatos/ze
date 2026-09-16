from ze_memory.fact_identity import fact_identity, normalize_fact_text


def test_normalize_collapses_case_and_space():
    assert normalize_fact_text("  Dark   Mode ") == "dark mode"


def test_identity_is_predicate_and_value():
    assert fact_identity("Preference", "Dark Mode") == ("preference", "dark mode")


def test_different_predicates_are_not_collapsed():
    a = fact_identity("preference", "Lisbon")
    b = fact_identity("identity", "Lisbon")
    assert a != b
