from unittest.mock import MagicMock

from ze_agents.settings import Settings
from ze_personal.plugin import PersonalPlugin


def _plugin() -> PersonalPlugin:
    plugin = PersonalPlugin.__new__(PersonalPlugin)
    plugin.morning_briefing = MagicMock()
    plugin.insight_engine = MagicMock()
    plugin.contact_review = MagicMock()
    plugin.contacts_consolidator = MagicMock()
    plugin.social_cooccurrence = MagicMock()
    return plugin


def _cron_job_ids(scheduler: MagicMock) -> list[str]:
    return [c.kwargs["job_id"] for c in scheduler.add_cron_job.call_args_list]


def test_contacts_consolidation_follows_consolidation_flag():
    settings = Settings(openrouter_api_key="", database_url="")
    on, off = MagicMock(), MagicMock()
    _plugin().register_proactive_jobs(on, settings, consolidation_enabled=True)
    _plugin().register_proactive_jobs(off, settings, consolidation_enabled=False)
    assert "contacts_consolidation" in _cron_job_ids(on)
    assert "contacts_consolidation" not in _cron_job_ids(off)
