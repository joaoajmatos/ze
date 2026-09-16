from pathlib import Path

import yaml


def test_conductor_progress_keys_in_companion_locale():
    path = Path(__file__).resolve().parents[3] / "ze_personal" / "locales" / "en.yaml"
    data = yaml.safe_load(path.read_text())
    assert data["conductor"]["checking_calendar"]
    assert data["conductor"]["drafting_mail"]
