from uuid import uuid4

from ze_agents.label_match import Ambiguous, Miss, Unique, precise_label_match


def test_unique_exact_after_forget_prefix():
    dentist = uuid4()
    result = precise_label_match(
        "forget the dentist appointment",
        [(dentist, "dentist appointment"), (uuid4(), "buy milk")],
    )
    assert isinstance(result, Unique)
    assert result.item_id == dentist


def test_single_long_label_named_in_query():
    dentist = uuid4()
    result = precise_label_match(
        "forget the dentist",
        [(dentist, "Call the dentist")],
    )
    assert isinstance(result, Unique)
    assert result.item_id == dentist


def test_two_dentist_labels_are_ambiguous_or_miss():
    a = uuid4()
    b = uuid4()
    result = precise_label_match(
        "forget the dentist",
        [(a, "Call the dentist"), (b, "Dentist bill")],
    )
    assert isinstance(result, (Ambiguous, Miss))
    if isinstance(result, Ambiguous):
        assert set(result.item_ids) == {a, b}


def test_short_token_does_not_substring_batch():
    result = precise_label_match(
        "forget dentist",
        [(uuid4(), "Call the dentist"), (uuid4(), "Dentist bill")],
    )
    assert isinstance(result, (Ambiguous, Miss))


def test_forget_that_is_miss():
    result = precise_label_match(
        "forget that",
        [(uuid4(), "Call the dentist")],
    )
    assert isinstance(result, Miss)


def test_empty_query_is_miss():
    result = precise_label_match("cancel", [(uuid4(), "Call the dentist")])
    assert isinstance(result, Miss)
