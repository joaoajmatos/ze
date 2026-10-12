from unittest.mock import MagicMock

from ze_agents.settings import Settings
from ze_messenger.plugin import MessengerPlugin


def _plugin(topic: str) -> tuple[MessengerPlugin, MagicMock, Settings]:
    plugin = MessengerPlugin.__new__(MessengerPlugin)
    plugin._polling_job = None
    plugin._gmail_channel = MagicMock(supports_push=True)
    settings = Settings(
        openrouter_api_key="", database_url="", gmail_pubsub_topic=topic
    )
    return plugin, MagicMock(), settings


def test_registers_watch_renewal_from_core_settings_topic():
    plugin, scheduler, settings = _plugin("projects/p/topics/gmail")
    plugin.register_proactive_jobs(scheduler, settings)
    scheduler.register.assert_called_once()
    assert scheduler.register.call_args.args[0]._topic_name == "projects/p/topics/gmail"


def test_skips_watch_renewal_without_topic():
    plugin, scheduler, settings = _plugin("")
    plugin.register_proactive_jobs(scheduler, settings)
    scheduler.register.assert_not_called()
