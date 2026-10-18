# Slots Requirements Checklist: Plugin Modules in Slots (191b)

**Purpose**: check the module, slot and News requirements before implementation.
**Created**: 2026-10-18
**Feature**: [spec.md](../spec.md)

- [x] CHK001 Is each slot's subject defined (fields per slot)? [Completeness, Data model]
- [x] CHK002 Is a slot/subject mismatch defined (422)? [Edge Case, Contract]
- [x] CHK003 Are loading, failure and not-applicable states worded? [Coverage, Spec US1, Plan]
- [x] CHK004 Is the provider timeout bounded and its line worded? [Clarity, Plan, T002]
- [x] CHK005 Is it stated that a failing module never changes the rest of the place? [Spec §FR-004, T006]
- [x] CHK006 Is the refresh rule (load, frame, 60 s visible) testable? [Measurability, Clarification Q5, T006]
- [x] CHK007 Is the absence of a World slot recorded? [Clarification Q4, Plan]
- [x] CHK008 Is the News sources match defined (tags vs topic entities)? [Clarity, Research R4]
- [x] CHK009 Is the preset numbering and key rule defined against 187's chips? [Consistency, T008]
- [x] CHK010 Is every removed field and route listed with a grep? [Completeness, Quickstart]
- [x] CHK011 Is the 188 dependency (Doing workflow page) handled if 188 is late? [Dependency, Lane Plan rule]
