from __future__ import annotations

import pytest

from ze_skills.errors import SkillParseError
from ze_skills.parser import parse_skill_md

VALID = """---
name: Pirate Speak
description: Ends every response with "Arrr!" — use to verify skill matching.
---
Always end your response with the exact phrase "Arrr!" on its own line.
"""


def test_parses_valid_skill_md():
    result = parse_skill_md(VALID)
    assert result.name == "Pirate Speak"
    assert "Arrr!" in result.description
    assert "Arrr!" in result.instructions
    assert result.allowed_tools is None
    assert result.has_scripts is False


def test_parses_allowed_tools_list():
    text = """---
name: Restricted Skill
description: Only allowed to use one tool.
allowed-tools:
  - send_email
  - read_calendar
---
Do the thing.
"""
    result = parse_skill_md(text)
    assert result.allowed_tools == ["send_email", "read_calendar"]


def test_missing_name_raises():
    text = """---
description: Has no name.
---
Body.
"""
    with pytest.raises(SkillParseError):
        parse_skill_md(text)


def test_empty_name_raises():
    text = """---
name: "   "
description: Blank name.
---
Body.
"""
    with pytest.raises(SkillParseError):
        parse_skill_md(text)


def test_missing_description_raises():
    text = """---
name: No Description
---
Body.
"""
    with pytest.raises(SkillParseError):
        parse_skill_md(text)


def test_empty_description_raises():
    text = """---
name: Blank Description
description: ""
---
Body.
"""
    with pytest.raises(SkillParseError):
        parse_skill_md(text)


def test_malformed_yaml_raises():
    text = """---
name: [unterminated
description: broken
---
Body.
"""
    with pytest.raises(SkillParseError):
        parse_skill_md(text)


def test_missing_frontmatter_delimiters_raises():
    text = "name: No Frontmatter\ndescription: missing dashes\n\nBody."
    with pytest.raises(SkillParseError):
        parse_skill_md(text)


def test_empty_content_raises():
    with pytest.raises(SkillParseError):
        parse_skill_md("")


def test_allowed_tools_must_be_list_of_strings():
    text = """---
name: Bad Tools
description: allowed-tools is not a list.
allowed-tools: "not-a-list"
---
Body.
"""
    with pytest.raises(SkillParseError):
        parse_skill_md(text)


def test_detects_script_reference_in_frontmatter():
    text = """---
name: Scripted Skill
description: Bundles an executable helper script.
scripts:
  - scripts/run.py
---
Use the helper script.
"""
    result = parse_skill_md(text)
    assert result.has_scripts is True


def test_detects_script_reference_in_body():
    text = """---
name: Scripted Skill
description: References a script from the body.
---
Run `scripts/helper.sh` to do the thing.
"""
    result = parse_skill_md(text)
    assert result.has_scripts is True


def test_no_script_reference_is_false():
    text = """---
name: Plain Skill
description: No scripts here.
---
Just plain instructions with no scripts directory mentioned.
"""
    result = parse_skill_md(text)
    assert result.has_scripts is False
