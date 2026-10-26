"""Ze application exceptions."""

from ze_agents.errors import ZeError


class ProfileConfigError(ZeError):
    """A ZE_PROFILE config overlay is missing or its name is not a plain profile name."""


class MigrationReadinessError(ZeError):
    """Database migrations are not at the expected Alembic heads."""


class PluginRouteDriftError(ZeError):
    """A plugin mounts a router that the OpenAPI export does not know about."""
