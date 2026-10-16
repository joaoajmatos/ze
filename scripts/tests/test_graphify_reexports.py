import importlib.util
import json
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "graphify_reexports", Path(__file__).parents[1] / "graphify_reexports.py"
)
repair = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = repair
_SPEC.loader.exec_module(repair)


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _node(nid, label, file, line=None, file_type="code"):
    return {
        "id": nid,
        "label": label,
        "file_type": file_type,
        "source_file": file,
        "source_location": f"L{line}" if line else "",
    }


def _edge(src, tgt, relation, file, line):
    return {
        "source": src,
        "target": tgt,
        "relation": relation,
        "context": "x",
        "confidence": "EXTRACTED",
        "source_file": file,
        "source_location": f"L{line}",
        "_origin": "ast",
    }


def _build_repo(root: Path) -> dict:
    _write(root, "core/a/pkg_a/__init__.py", "")
    _write(
        root,
        "core/a/pkg_a/store.py",
        "class Store:\n    pass\n\n\ndef make_log():\n    return 1\n",
    )
    _write(
        root,
        "packages/sdk/pkg_sdk/__init__.py",
        "from pkg_a.store import Store, make_log\n",
    )
    _write(
        root,
        "plugins/p/pkg_p/use.py",
        "from pkg_sdk import Store as S, make_log\n\nlog = make_log()\n\n\n"
        "def build(x: S) -> S:\n    return make_log()\n",
    )
    _write(root, "docs/spec.md", "# Store\n")
    nodes = [
        _node("store", "Store", "core/a/pkg_a/store.py", 1),
        _node("make_log", "make_log()", "core/a/pkg_a/store.py", 5),
        _node("use_file", "use.py", "plugins/p/pkg_p/use.py"),
        _node("build", "build()", "plugins/p/pkg_p/use.py", 7),
        _node("phantom_store", "S", "", None),
        _node("phantom_log", "make_log()", "", None),
        _node("spec_store", "Store", "docs/spec.md", None, file_type="concept"),
        _node("third_party", "Path", "", None),
    ]
    links = [
        _edge("build", "phantom_store", "references", "plugins/p/pkg_p/use.py", 7),
        _edge("build", "phantom_log", "calls", "plugins/p/pkg_p/use.py", 8),
        _edge("use_file", "third_party", "imports", "plugins/p/pkg_p/use.py", 1),
    ]
    return {
        "directed": False,
        "multigraph": False,
        "graph": {},
        "nodes": nodes,
        "links": links,
        "hyperedges": [],
    }


def _run(root: Path, graph: dict) -> dict:
    path = root / "graph.json"
    path.write_text(json.dumps(graph))
    assert repair.main(["--graph", str(path), "--root", str(root)]) == 0
    return json.loads(path.read_text())


def _edges(data, relation):
    return {
        (e["source"], e["target"]) for e in data["links"] if e["relation"] == relation
    }


def test_aliased_reexport_phantoms_repoint_to_the_defining_symbol(tmp_path):
    data = _run(tmp_path, _build_repo(tmp_path))
    ids = {n["id"] for n in data["nodes"]}
    assert "phantom_store" not in ids
    assert "phantom_log" not in ids
    assert ("build", "store") in _edges(data, "references")
    assert ("build", "make_log") in _edges(data, "calls")


def test_imports_and_module_level_calls_are_added(tmp_path):
    data = _run(tmp_path, _build_repo(tmp_path))
    assert ("use_file", "store") in _edges(data, "imports")
    assert ("use_file", "make_log") in _edges(data, "imports")
    assert ("use_file", "make_log") in _edges(data, "calls")


def test_third_party_phantoms_are_left_alone(tmp_path):
    data = _run(tmp_path, _build_repo(tmp_path))
    assert "third_party" in {n["id"] for n in data["nodes"]}


def test_spec_node_with_a_code_twin_is_renamed(tmp_path):
    data = _run(tmp_path, _build_repo(tmp_path))
    labels = {n["id"]: n["label"] for n in data["nodes"]}
    assert labels["spec_store"] == "Store (spec)"
    assert labels["store"] == "Store"


def test_edgeless_phantoms_are_removed(tmp_path):
    graph = _build_repo(tmp_path)
    graph["nodes"].append(_node("orphan_phantom", "Store", "", None))
    data = _run(tmp_path, graph)
    assert "orphan_phantom" not in {n["id"] for n in data["nodes"]}


def test_second_run_changes_nothing(tmp_path):
    first = _run(tmp_path, _build_repo(tmp_path))
    second = _run(tmp_path, first)
    assert second == first


def test_dry_run_writes_nothing(tmp_path):
    graph = _build_repo(tmp_path)
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(graph))
    before = path.read_text()
    repair.main(["--graph", str(path), "--root", str(tmp_path), "--dry-run"])
    assert path.read_text() == before
