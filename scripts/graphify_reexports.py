#!/usr/bin/env python3
"""Repair graphify's graph.json so re-exports and aliased imports resolve.

graphify cannot follow ``from ze_sdk import X`` (X is re-exported from another
package) or ``from pkg import X as Y``. It creates a sourceless "phantom" node
per importing file instead, so ``graphify affected X`` / ``explain X`` find a
canonical node with almost no inbound edges. This script, run right after
``graphify update .``:

1. parses every Python file and resolves each ``from M import N [as A]``
   through ``__init__.py`` / ``ze_sdk`` re-export chains to the module that
   defines ``N``;
2. repoints every edge of a phantom node to the canonical node and drops the
   phantom;
3. suffixes " (spec)" on spec-doc nodes whose label equals a uniquely defined code
   symbol, so ``graphify affected GoalStore`` finds one node instead of two;
4. adds the ``imports`` edge (file -> symbol) and the ``calls`` edge (calling
   function or file -> symbol) graphify missed, including module-level
   ``log = get_logger(__name__)``;
5. writes graph.json back (idempotent: a second run changes nothing).

Usage:
    python scripts/graphify_reexports.py                 # repair in place
    python scripts/graphify_reexports.py --dry-run       # report only
    python scripts/graphify_reexports.py --out fixed.json
    python scripts/graphify_reexports.py --graph graphify-out/graph.json --root .
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ORIGIN = "graphify_reexports"
SKIP_DIRS = {
    "node_modules",
    "graphify-out",
    "__pycache__",
    "build",
    "dist",
    "site-packages",
}
CALL_RELATIONS = ("calls", "indirect_call")


@dataclass
class Binding:
    module: str
    name: str | None
    line: int


@dataclass
class ModuleInfo:
    path: str
    dotted: str
    is_package: bool
    defs: dict[str, int] = field(default_factory=dict)
    bindings: dict[str, Binding] = field(default_factory=dict)
    stars: list[str] = field(default_factory=list)
    tree: ast.Module | None = None


def iter_python_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d
            for d in dirnames
            if not d.startswith(".") and d not in SKIP_DIRS and d != ".venv"
        ]
        for name in filenames:
            if name.endswith(".py"):
                yield Path(dirpath, name)


def discover_modules(root: Path) -> dict[str, ModuleInfo]:
    """Map repo-relative path -> ModuleInfo with dotted names for importable packages."""
    files = [p.relative_to(root).as_posix() for p in iter_python_files(root)]
    fileset = set(files)
    dotted_to_paths: dict[str, list[str]] = defaultdict(list)
    modules: dict[str, ModuleInfo] = {}
    package_roots = {
        rel[: -len("/__init__.py")]
        for rel in files
        if rel.endswith("/__init__.py")
        and "/".join(rel.split("/")[:-2] + ["__init__.py"]) not in fileset
    }
    for rel in files:
        parts = rel.split("/")
        d = parts[:-1]
        top = next(
            (i for i in range(len(d)) if "/".join(d[: i + 1]) in package_roots), None
        )
        dotted = ""
        if top is not None:
            leaf = [] if parts[-1] == "__init__.py" else [parts[-1][:-3]]
            dotted = ".".join(d[top:] + leaf)
        info = ModuleInfo(
            path=rel, dotted=dotted, is_package=parts[-1] == "__init__.py"
        )
        modules[rel] = info
        if dotted:
            dotted_to_paths[dotted].append(rel)
    for dotted, paths in dotted_to_paths.items():
        if len(paths) > 1:
            for p in paths:
                modules[p].dotted = ""
    return modules


def parse_module(
    root: Path, info: ModuleInfo, by_dotted: dict[str, ModuleInfo]
) -> None:
    try:
        info.tree = ast.parse((root / info.path).read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return
    for node in info.tree.body:
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            info.defs[node.name] = node.lineno
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                for n in ast.walk(t):
                    if isinstance(n, ast.Name):
                        info.defs.setdefault(n.id, node.lineno)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            info.defs.setdefault(node.target.id, node.lineno)
    for node in ast.walk(info.tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        base = absolute_module(info, node)
        if base is None:
            continue
        for alias in node.names:
            if alias.name == "*":
                info.stars.append(base)
                continue
            bound = alias.asname or alias.name
            info.bindings.setdefault(bound, Binding(base, alias.name, node.lineno))


def absolute_module(info: ModuleInfo, node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module
    if not info.dotted:
        return None
    pkg = info.dotted.split(".")
    if not info.is_package:
        pkg = pkg[:-1]
    up = node.level - 1
    if up > len(pkg):
        return None
    pkg = pkg[: len(pkg) - up]
    return ".".join(pkg + ([node.module] if node.module else []))


def resolve_symbol(
    dotted: str,
    name: str,
    by_dotted: dict[str, ModuleInfo],
    seen: set[tuple[str, str]] | None = None,
) -> tuple[str, str] | None:
    """Follow re-export chains to (defining file, name). None if unresolvable or a module."""
    seen = seen or set()
    if (dotted, name) in seen:
        return None
    seen.add((dotted, name))
    mod = by_dotted.get(dotted)
    if mod is None:
        return None
    if name in mod.defs:
        return mod.path, name
    binding = mod.bindings.get(name)
    if binding is not None and binding.name is not None:
        return resolve_symbol(binding.module, binding.name, by_dotted, seen)
    for star in mod.stars:
        hit = resolve_symbol(star, name, by_dotted, seen)
        if hit:
            return hit
    return None


def norm_label(label: str) -> str:
    label = label.strip()
    if label.endswith("()"):
        label = label[:-2]
    return label


class Graph:
    def __init__(self, data: dict):
        self.data = data
        self.nodes: dict[str, dict] = {n["id"]: n for n in data["nodes"]}
        self.links: list[dict] = data["links"]
        self.by_file_name: dict[tuple[str, str], list[str]] = defaultdict(list)
        self.file_node: dict[str, str] = {}
        self.def_nodes: dict[tuple[str, int], str] = {}
        self.by_name: dict[str, list[str]] = defaultdict(list)
        for nid, n in self.nodes.items():
            sf = n.get("source_file") or ""
            if not sf or n.get("file_type") != "code" or not sf.endswith(".py"):
                continue
            label = n["label"]
            if (
                label == Path(sf).name
                or label == "/".join(Path(sf).parts[-2:])
                or label.endswith(".py")
            ):
                self.file_node.setdefault(sf, nid)
                continue
            if label.startswith("."):
                loc = parse_line(n.get("source_location"))
                if loc:
                    self.def_nodes[(sf, loc)] = nid
                continue
            name = norm_label(label)
            self.by_file_name[(sf, name)].append(nid)
            self.by_name[name].append(nid)
            loc = parse_line(n.get("source_location"))
            if loc:
                self.def_nodes[(sf, loc)] = nid

    def canonical(self, file: str, name: str, line: int | None) -> str | None:
        ids = self.by_file_name.get((file, name), [])
        if len(ids) == 1:
            return ids[0]
        if line is not None:
            for i in ids:
                if parse_line(self.nodes[i].get("source_location")) == line:
                    return i
        return None


def parse_line(loc) -> int | None:
    if isinstance(loc, str) and loc.startswith("L"):
        digits = loc[1:].split("-")[0]
        if digits.isdigit():
            return int(digits)
    return None


@dataclass
class Report:
    phantoms_total: int = 0
    phantoms_resolved: int = 0
    phantoms_left: int = 0
    edges_repointed: int = 0
    edges_dropped: int = 0
    imports_added: int = 0
    spec_nodes_renamed: int = 0
    calls_added: int = 0
    left_labels: Counter = field(default_factory=Counter)


def enclosing_scopes(tree: ast.Module):
    """Yield (call node, enclosing function def line or None) for every Call in the module."""
    out: list[tuple[ast.Call, int | None]] = []

    def visit(node: ast.AST, scope: int | None):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                for deco in child.decorator_list:
                    visit_expr(deco, scope)
                for d in (*child.args.defaults, *child.args.kw_defaults):
                    if d is not None:
                        visit_expr(d, scope)
                visit(child, child.lineno)
            else:
                if isinstance(child, ast.Call):
                    out.append((child, scope))
                visit(child, scope)

    def visit_expr(expr: ast.AST, scope: int | None):
        if isinstance(expr, ast.Call):
            out.append((expr, scope))
        visit(expr, scope)

    visit(tree, None)
    return out


def repair(
    graph: Graph, modules: dict[str, ModuleInfo], by_dotted: dict[str, ModuleInfo]
) -> Report:
    rep = Report()

    def link(
        src: str, tgt: str, relation: str, file: str, line: int, context: str
    ) -> dict:
        return {
            "relation": relation,
            "context": context,
            "confidence": "EXTRACTED",
            "confidence_score": 1.0,
            "source_file": file,
            "source_location": f"L{line}",
            "weight": 1.0,
            "_origin": ORIGIN,
            "source": src,
            "target": tgt,
        }

    phantoms = {
        nid: n
        for nid, n in graph.nodes.items()
        if not n.get("source_file") and n.get("file_type") == "code"
    }
    rep.phantoms_total = len(phantoms)
    incident: dict[str, list[dict]] = defaultdict(list)
    for edge in graph.links:
        for end in (edge["source"], edge["target"]):
            if end in phantoms:
                incident[end].append(edge)

    remap: dict[str, str] = {}
    for pid, node in phantoms.items():
        label = norm_label(node["label"])
        files = {e.get("source_file") for e in incident[pid] if e.get("source_file")}
        targets: set[str] = set()
        for f in files:
            info = modules.get(f)
            binding = info.bindings.get(label) if info else None
            if binding is None or binding.name is None:
                continue
            hit = resolve_symbol(binding.module, binding.name, by_dotted)
            if hit:
                cid = graph.canonical(hit[0], hit[1], modules[hit[0]].defs.get(hit[1]))
                if cid:
                    targets.add(cid)
        if len(targets) == 1:
            remap[pid] = next(iter(targets))
            rep.phantoms_resolved += 1
        else:
            rep.phantoms_left += 1
            rep.left_labels[label] += 1

    new_links: list[dict] = []
    seen_keys: set[tuple] = set()
    for edge in graph.links:
        s, t = (
            remap.get(edge["source"], edge["source"]),
            remap.get(edge["target"], edge["target"]),
        )
        changed = (s, t) != (edge["source"], edge["target"])
        if changed:
            rep.edges_repointed += 1
            edge = {**edge, "source": s, "target": t}
        if s == t:
            rep.edges_dropped += 1
            continue
        key = (
            s,
            t,
            edge["relation"],
            edge.get("source_file"),
            edge.get("source_location"),
            edge.get("context"),
        )
        rkey = (
            t,
            s,
            edge["relation"],
            edge.get("source_file"),
            edge.get("source_location"),
            edge.get("context"),
        )
        if key in seen_keys or rkey in seen_keys:
            rep.edges_dropped += 1
            continue
        seen_keys.add(key)
        new_links.append(edge)
    graph.links = new_links
    for pid in remap:
        graph.nodes.pop(pid, None)
    existing: set[tuple[str, str, str]] = set()
    for edge in graph.links:
        existing.add((edge["source"], edge["target"], edge["relation"]))
        existing.add((edge["target"], edge["source"], edge["relation"]))

    for rel, info in modules.items():
        if info.tree is None:
            continue
        fnode = graph.file_node.get(rel)
        if fnode is None:
            continue
        resolved: dict[str, tuple[str, int]] = {}
        for bound, b in info.bindings.items():
            if b.name is None:
                continue
            hit = resolve_symbol(b.module, b.name, by_dotted)
            if not hit:
                continue
            cid = graph.canonical(hit[0], hit[1], modules[hit[0]].defs.get(hit[1]))
            if cid is None or hit[0] == rel:
                continue
            resolved[bound] = (cid, b.line)
            if (fnode, cid, "imports") not in existing:
                graph.links.append(link(fnode, cid, "imports", rel, b.line, "import"))
                existing.add((fnode, cid, "imports"))
                existing.add((cid, fnode, "imports"))
                rep.imports_added += 1
        if not resolved:
            continue
        for call, scope in enclosing_scopes(info.tree):
            func = call.func
            if not isinstance(func, ast.Name) or func.id not in resolved:
                continue
            cid, _ = resolved[func.id]
            caller = graph.def_nodes.get((rel, scope)) if scope is not None else fnode
            if caller is None:
                caller = fnode
            if caller == cid or any(
                (caller, cid, r) in existing for r in CALL_RELATIONS
            ):
                continue
            graph.links.append(link(caller, cid, "calls", rel, call.lineno, "call"))
            for r in CALL_RELATIONS:
                existing.add((caller, cid, r))
            existing.add((caller, cid, "calls"))
            rep.calls_added += 1
    code_labels = {name.lower(): ids for name, ids in graph.by_name.items()}
    for n in graph.nodes.values():
        sf = n.get("source_file") or ""
        if n.get("file_type") == "code" or not sf.endswith(".md"):
            continue
        ids = code_labels.get(n["label"].lower())
        if ids and len(ids) == 1:
            n["label"] = f"{n['label']} (spec)"
            n["norm_label"] = n["label"].lower()
            rep.spec_nodes_renamed += 1
    graph.data["nodes"] = list(graph.nodes.values())
    graph.data["links"] = graph.links
    for h in graph.data.get("hyperedges", []) or []:
        if isinstance(h.get("nodes"), list):
            h["nodes"] = list(dict.fromkeys(remap.get(n, n) for n in h["nodes"]))
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--graph", default="graphify-out/graph.json", help="graph.json to repair"
    )
    ap.add_argument("--root", default=".", help="repo root the graph was built from")
    ap.add_argument("--out", default=None, help="write here instead of in place")
    ap.add_argument("--dry-run", action="store_true", help="report, write nothing")
    args = ap.parse_args(argv)

    graph_path = Path(args.graph)
    root = Path(args.root).resolve()
    if not graph_path.exists():
        print(
            f"no graph at {graph_path}; run `graphify update .` first", file=sys.stderr
        )
        return 1
    data = json.loads(graph_path.read_text(encoding="utf-8"))

    modules = discover_modules(root)
    by_dotted = {m.dotted: m for m in modules.values() if m.dotted}
    for info in modules.values():
        parse_module(root, info, by_dotted)

    graph = Graph(data)
    rep = repair(graph, modules, by_dotted)

    print(
        f"phantom nodes: {rep.phantoms_total} "
        f"(resolved {rep.phantoms_resolved}, left {rep.phantoms_left})"
    )
    print(
        f"edges: repointed {rep.edges_repointed}, dropped {rep.edges_dropped} (self/duplicate), "
        f"imports added {rep.imports_added}, calls added {rep.calls_added}"
    )
    print(
        f"spec nodes renamed so the code symbol is the unique match: {rep.spec_nodes_renamed}"
    )
    if rep.left_labels:
        top = ", ".join(f"{k} x{v}" for k, v in rep.left_labels.most_common(12))
        print(f"left (third-party or unresolvable): {top}")

    if args.dry_run:
        return 0
    out = Path(args.out) if args.out else graph_path
    out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
