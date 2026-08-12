from __future__ import annotations

from ze_skills.types import Skill, SkillSource, compute_content_hash, slugify


def test_slugify_lowercases_and_hyphenates():
    assert slugify("Pirate Speak") == "pirate-speak"


def test_slugify_strips_non_alphanumeric():
    assert slugify("  My Cool Skill! (v2) ") == "my-cool-skill-v2"


def test_slugify_collapses_repeated_separators():
    assert slugify("foo   bar---baz") == "foo-bar-baz"


def test_skill_derives_slug_from_name_when_not_provided():
    skill = Skill(
        name="Pirate Speak",
        description="desc",
        instructions="instructions",
        source=SkillSource.IMPORTED,
    )
    assert skill.slug == "pirate-speak"


def test_skill_respects_explicit_slug():
    skill = Skill(
        name="Pirate Speak",
        description="desc",
        instructions="instructions",
        source=SkillSource.IMPORTED,
        slug="custom-slug",
    )
    assert skill.slug == "custom-slug"


def test_content_hash_stable_for_same_content():
    h1 = compute_content_hash("name", "desc", "instructions", ["tool_a"])
    h2 = compute_content_hash("name", "desc", "instructions", ["tool_a"])
    assert h1 == h2


def test_content_hash_stable_regardless_of_allowed_tools_order():
    h1 = compute_content_hash("name", "desc", "instructions", ["tool_a", "tool_b"])
    h2 = compute_content_hash("name", "desc", "instructions", ["tool_b", "tool_a"])
    assert h1 == h2


def test_content_hash_sensitive_to_instructions_change():
    h1 = compute_content_hash("name", "desc", "instructions v1", None)
    h2 = compute_content_hash("name", "desc", "instructions v2", None)
    assert h1 != h2


def test_content_hash_sensitive_to_name_change():
    h1 = compute_content_hash("name a", "desc", "instructions", None)
    h2 = compute_content_hash("name b", "desc", "instructions", None)
    assert h1 != h2


def test_content_hash_sensitive_to_description_change():
    h1 = compute_content_hash("name", "desc a", "instructions", None)
    h2 = compute_content_hash("name", "desc b", "instructions", None)
    assert h1 != h2


def test_content_hash_sensitive_to_allowed_tools_change():
    h1 = compute_content_hash("name", "desc", "instructions", ["tool_a"])
    h2 = compute_content_hash("name", "desc", "instructions", ["tool_a", "tool_b"])
    assert h1 != h2


def test_skill_auto_computes_content_hash_when_not_provided():
    skill = Skill(
        name="name",
        description="desc",
        instructions="instructions",
        source=SkillSource.IMPORTED,
    )
    expected = compute_content_hash("name", "desc", "instructions", None)
    assert skill.content_hash == expected
