from pathlib import Path

from conftest import load_process_module

lane = load_process_module("check_lane_plan")
flow = load_process_module("check_speckit_flow")

PLAN = """# Plan

## Lane Plan (Maestri crew)

| Lane | Model / role | Owns (files and dirs, disjoint) | Tasks | Starts after | Reviewer |
|------|--------------|---------------------------------|-------|--------------|----------|
| lead | Sonnet ENG lead | `apps/ze-web/src/app/`, `packages/ze-client/` | T001 | - | Gauge |
| a | Sonnet ENG | `apps/ze-web/src/pages/a/` | T002 | contract | Gauge |
| jr1 | Haiku JR | `apps/ze-web/src/shared/lib/format.ts` | T003 | contract | Caliper |

## Complexity Tracking
"""
TASKS = (
    "- [ ] T001 [L:lead] contract\n- [ ] T002 [L:a] page\n- [ ] T003 [L:jr1] format\n"
)


def feature(
    tmp_path: Path, plan=PLAN, tasks=TASKS, spec="# S\n\n## Clarifications\n\nx\n"
) -> Path:
    d = tmp_path / "200-x"
    d.mkdir()
    (d / "plan.md").write_text(plan)
    (d / "tasks.md").write_text(tasks)
    (d / "spec.md").write_text(spec)
    return d


def test_good_lane_plan(tmp_path):
    assert lane.check(feature(tmp_path)) == []
    assert flow.check(tmp_path / "200-x") == []


def test_missing_section(tmp_path):
    d = feature(tmp_path, plan="# Plan\n")
    assert "no '## Lane Plan'" in lane.check(d)[0]


def test_lead_overlap_is_only_a_note(tmp_path):
    plan = PLAN.replace(
        "`apps/ze-web/src/pages/a/`", "`apps/ze-web/src/app/router.tsx`"
    )
    errs = lane.check(feature(tmp_path, plan=plan))
    assert any(e.startswith("note: ") and "contract-then-extend" in e for e in errs)
    assert not [e for e in errs if not e.startswith("note: ")]


def test_lane_vs_lane_overlap_is_an_error(tmp_path):
    plan = PLAN.replace(
        "`apps/ze-web/src/shared/lib/format.ts`", "`apps/ze-web/src/pages/a/`"
    )
    errs = lane.check(feature(tmp_path, plan=plan))
    assert [e for e in errs if not e.startswith("note: ") and "a and jr1" in e]


def test_glob_overlap(tmp_path):
    plan = PLAN.replace("`apps/ze-web/src/pages/a/`", "`packages/ze-client/**`")
    assert any("both own" in e for e in lane.check(feature(tmp_path, plan=plan)))


def test_untagged_and_unknown_lane_tasks(tmp_path):
    errs = lane.check(
        feature(
            tmp_path,
            tasks="- [ ] T001 [L:lead] a\n- [ ] T002 no tag\n- [ ] T003 [L:zz] b\n",
        )
    )
    assert any("T002 has no [L:x]" in e for e in errs)
    assert any("T003" in e and "does not define" in e for e in errs)


def test_missing_lead_model_and_reviewer(tmp_path):
    plan = PLAN.replace(
        "| lead | Sonnet ENG lead |", "| main | Sonnet ENG lead |"
    ).replace("| Gauge |\n| a", "| [name] |\n| a")
    errs = lane.check(feature(tmp_path, plan=plan, tasks="- [ ] T001 [L:main] x\n"))
    assert any("no `lead` lane" in e for e in errs)
    assert any("no reviewer" in e for e in errs)


def test_jr_lane_with_eng_task(tmp_path):
    errs = lane.check(
        feature(
            tmp_path, tasks="- [ ] T001 [L:lead] a\n- [ ] T003 [L:jr1] [ENG] hard\n"
        )
    )
    assert any("[ENG] but sits in JR lane" in e for e in errs)


def test_flow_artifacts(tmp_path):
    d = feature(tmp_path, spec="# S\n")
    assert any("Clarifications" in e for e in flow.check(d))
    (d / "spec.md").write_text("# S\n\n**Complexity**: complex\n\n## Clarifications\n")
    errs = flow.check(d)
    assert any("checklists" in e for e in errs) and any("analyze" in e for e in errs)
    (d / "checklists").mkdir()
    (d / "checklists" / "ux.md").write_text("- [x] CHK001\n")
    (d / "analysis.md").write_text("ok")
    assert flow.check(d) == []


def test_flow_untagged_tasks(tmp_path):
    assert any(
        "without [L:x]" in e
        for e in flow.check(feature(tmp_path, tasks="- [ ] T001 plain\n"))
    )
