from datetime import datetime

from ze.agents.identity import build_identity_block
from ze.memory.types import UserProfile


def make_profile(**overrides):
    defaults = dict(
        preferences="Likes brevity.",
        habits="Works mornings.",
        topics="AI and tech.",
        relationships="Has a cat.",
        goals="Ship Ze.",
        updated_at=datetime(2026, 5, 20),
        version=1,
    )
    defaults.update(overrides)
    return UserProfile(**defaults)


def make_persona(**overrides):
    defaults = {"traits": ["direct", "warm"], "verbosity": "balanced"}
    defaults.update(overrides)
    return defaults


def test_identity_block_with_profile():
    block = build_identity_block(make_persona(), "(none)", profile=make_profile())
    assert "## Who this user is" in block
    assert "**Preferences:** Likes brevity." in block
    assert "**Goals:** Ship Ze." in block


def test_identity_block_without_profile():
    block = build_identity_block(make_persona(), "(none)", profile=None)
    assert "## Who this user is" not in block


def test_identity_block_skips_empty_sections():
    profile = make_profile(habits="", relationships="")
    block = build_identity_block(make_persona(), "(none)", profile=profile)
    assert "**Preferences:** Likes brevity." in block
    assert "**Habits:**" not in block
    assert "**Relationships:**" not in block


def test_identity_block_no_profile_section_when_all_empty():
    profile = make_profile(
        preferences="", habits="", topics="", relationships="", goals=""
    )
    block = build_identity_block(make_persona(), "(none)", profile=profile)
    assert "## Who this user is" not in block


def test_identity_block_default_profile_is_none():
    # No profile kwarg — should produce no profile section
    block = build_identity_block(make_persona(), "(none)")
    assert "## Who this user is" not in block
