from ze_components.summary import describe_components


def test_names_each_kind_once_in_order():
    parts = [{"type": "table"}, {"type": "chart"}, {"type": "table"}]
    assert describe_components(parts) == "Showed a table and a chart."


def test_three_kinds_use_commas_and_layout_nodes_read_as_a_card():
    parts = [{"type": "table"}, {"type": "col"}, {"type": "form"}]
    assert describe_components(parts) == "Showed a table, a card and a form."


def test_nothing_rendered_is_empty():
    assert describe_components(None) == ""
    assert describe_components([]) == ""


def test_claim_primitives_are_named_for_history():
    parts = [{"type": "headline"}, {"type": "claim_card"}, {"type": "claim_timeline"}]
    assert describe_components(parts) == "Showed a headline, a card and a timeline."
