"""Ze application exceptions."""

from ze_agents.errors import ZeCoreError as ZeError


class ProfileConfigError(ZeError):
    """A ZE_PROFILE config overlay is missing or its name is not a plain profile name."""


class MigrationReadinessError(ZeError):
    """Database migrations are not at the expected Alembic heads."""
