from __future__ import annotations

import pytest
from ze_agents.errors import InvalidComponentError, ZeError

from ze_components import (
    UI_CONTRACT_VERSION,
    AskAction,
    Button,
    ComposeAction,
    NavigateAction,
    ToolAction,
    button,
    connect_account,
)
from ze_components.schema import export_json_schema
from ze_components.serialize import serialize_primitive


def test_each_action_kind_serializes_with_kind_and_fields():
    assert serialize_primitive(AskAction("hi")) == {"kind": "ask", "text": "hi"}
    assert serialize_primitive(NavigateAction("/mind/e1")) == {
        "kind": "navigate",
        "route": "/mind/e1",
    }
    assert serialize_primitive(ComposeAction("slipping")) == {
        "kind": "compose",
        "compose": "slipping",
    }
    assert serialize_primitive(ComposeAction("topic", topic="rent")) == {
        "kind": "compose",
        "compose": "topic",
        "topic": "rent",
    }
    assert serialize_primitive(
        ToolAction("news", "mark_source_read", {"source_id": "s-12", "n": 2})
    ) == {
        "kind": "tool",
        "owner": "news",
        "tool": "mark_source_read",
        "args": {"source_id": "s-12", "n": 2},
    }


def test_navigate_route_must_start_with_slash_and_may_carry_a_section():
    with pytest.raises(InvalidComponentError) as err:
        NavigateAction("mind/e1")
    assert isinstance(err.value, ZeError)
    assert NavigateAction("/governance#connections").route == "/governance#connections"


def test_ask_text_is_one_to_five_hundred_chars():
    with pytest.raises(InvalidComponentError):
        AskAction("")
    with pytest.raises(InvalidComponentError):
        AskAction("x" * 501)
    assert AskAction("x" * 500).text == "x" * 500


def test_tool_args_accept_only_scalars():
    ToolAction("o", "t", {"a": "s", "b": 1, "c": 1.5, "d": True})
    with pytest.raises(InvalidComponentError):
        ToolAction("o", "t", {"a": [1]})
    with pytest.raises(InvalidComponentError):
        ToolAction("o", "t", {"a": {"b": 1}})
    with pytest.raises(InvalidComponentError):
        ToolAction("o", "t", {"a": None})


def test_button_action_serializes_as_an_object():
    data = serialize_primitive(Button("Hi", AskAction("hi")))
    assert data["action"] == {"kind": "ask", "text": "hi"}
    assert (
        serialize_primitive(button("Go", NavigateAction("/ask")))["action"]["kind"]
        == "navigate"
    )


def test_a_string_action_raises():
    with pytest.raises(InvalidComponentError):
        Button("Hi", "rest:foo")  # type: ignore[arg-type]
    with pytest.raises(InvalidComponentError):
        button("Hi", "msg:foo")  # type: ignore[arg-type]


def test_connect_account_navigates_to_governance_connections():
    tree = serialize_primitive(connect_account("c1", "google", "Google", "Mail"))
    buttons = [c for c in tree["children"] if c["type"] == "button"]
    assert buttons[0]["action"] == {
        "kind": "navigate",
        "route": "/governance#connections",
    }


def test_schema_has_the_four_action_shapes_as_a_discriminated_union():
    defs = export_json_schema()["$defs"]
    union = defs["PrimitiveAction"]
    assert [r["$ref"] for r in union["oneOf"]] == [
        "#/$defs/AskAction",
        "#/$defs/ToolAction",
        "#/$defs/NavigateAction",
        "#/$defs/ComposeAction",
    ]
    assert union["discriminator"]["propertyName"] == "kind"
    assert defs["ToolAction"]["properties"]["kind"] == {"const": "tool"}
    assert set(defs["ToolAction"]["required"]) == {"kind", "owner", "tool", "args"}
    assert defs["Button"]["properties"]["action"] == {"$ref": "#/$defs/PrimitiveAction"}
    assert "action" in defs["Button"]["required"]


def test_schema_has_the_new_primitives():
    schema = export_json_schema()
    defs = schema["$defs"]
    for name, tag in (
        ("EntityFacet", "entity_facet"),
        ("StatRow", "stat_row"),
        ("ClaimList", "claim_list"),
        ("Sparkline", "sparkline"),
        ("Card", "card"),
    ):
        assert defs[name]["properties"]["type"] == {"const": tag}
        assert schema["discriminator"]["mapping"][tag] == f"#/$defs/{name}"
    assert defs["Card"]["properties"]["children"]["items"] == {
        "$ref": "#/$defs/Primitive"
    }
    assert defs["Card"]["properties"]["actions"]["items"] == {"$ref": "#/$defs/Button"}
    table = defs["Table"]["properties"]
    assert table["keys"]["items"] == {"type": "string"}
    assert table["row_actions"]["items"] == {"$ref": "#/$defs/RowAction"}
    assert defs["EntityFacet"]["properties"]["more"] == {
        "$ref": "#/$defs/PrimitiveAction"
    }


def test_progress_bar_is_removed():
    from ze_components import PRIMITIVE_TYPES

    assert "ProgressBar" not in {c.__name__ for c in PRIMITIVE_TYPES}


def test_contract_version():
    assert UI_CONTRACT_VERSION == "2.0"


def test_new_primitives_validate_their_shape():
    from ze_components import (
        Card,
        ClaimItem,
        ClaimList,
        ClaimPosture,
        EntityFacet,
        FacetFact,
        Sparkline,
        Stat,
        StatRow,
        Table,
        RowAction,
    )

    posture = ClaimPosture(subject="fact", ref_id="f1")
    EntityFacet("Ana", [FacetFact("likes tea", posture)])
    ClaimList(items=[ClaimItem("a", posture, AskAction("a"))])
    StatRow([Stat("Spend", "€4")])
    with pytest.raises(InvalidComponentError):
        StatRow([])
    with pytest.raises(InvalidComponentError):
        StatRow([Stat("x", "1")] * 7)
    with pytest.raises(InvalidComponentError):
        Sparkline("s", points=[0.0] * 61)
    Card("t", children=[], actions=[Button("Go", AskAction("go"))])
    with pytest.raises(InvalidComponentError):
        Table(headers=["a"], rows=[["1"], ["2"]], keys=["k"])
    Table(
        headers=["a"],
        rows=[["1"]],
        keys=["k"],
        row_actions=[RowAction("Go", AskAction("go"))],
    )


def test_tool_action_bounds():
    with pytest.raises(InvalidComponentError):
        ToolAction("o" * 65, "t", {})
    with pytest.raises(InvalidComponentError):
        ToolAction("o", "", {})
    with pytest.raises(InvalidComponentError):
        ToolAction("o", "t", {f"k{i}": 1 for i in range(13)})
    with pytest.raises(InvalidComponentError):
        ToolAction("o", "t", {"k" * 65: 1})
    with pytest.raises(InvalidComponentError):
        ToolAction("o", "t", {"k": "x" * 201})
    defs = export_json_schema()["$defs"]["ToolAction"]["properties"]
    assert defs["owner"]["maxLength"] == 64
    assert defs["args"]["maxProperties"] == 12


def test_compose_action_bounds():
    with pytest.raises(InvalidComponentError):
        ComposeAction("nope")  # type: ignore[arg-type]
    with pytest.raises(InvalidComponentError):
        ComposeAction("topic", topic="x" * 121)
    assert ComposeAction("topic", topic="x" * 120).topic == "x" * 120
    assert (
        export_json_schema()["$defs"]["ComposeAction"]["properties"]["topic"][
            "maxLength"
        ]
        == 120
    )


@pytest.mark.parametrize("route", ["//evil.example", "/a/../b", "/..", "x"])
def test_navigate_refuses_protocol_relative_and_dotdot(route):
    with pytest.raises(InvalidComponentError):
        NavigateAction(route)


def test_table_keys_must_be_unique():
    from ze_components import Table

    with pytest.raises(InvalidComponentError):
        Table(headers=["a"], rows=[["1"], ["2"]], keys=["k", "k"])
    assert (
        export_json_schema()["$defs"]["Table"]["properties"]["keys"]["uniqueItems"]
        is True
    )


def test_sparkline_points_must_be_finite():
    from ze_components import Sparkline

    for bad in (float("nan"), float("inf")):
        with pytest.raises(InvalidComponentError):
            Sparkline("s", points=[1.0, bad])


def test_summary_names_the_new_primitives():
    from ze_components.summary import describe_components

    text = describe_components([{"type": "stat_row"}, {"type": "sparkline"}])
    assert "stat_row" not in text and "stat row" in text


def test_tool_args_reject_non_finite_floats():
    for bad in (float("nan"), float("inf")):
        with pytest.raises(InvalidComponentError):
            ToolAction("o", "t", {"a": bad})
