from __future__ import annotations

from collections.abc import Iterable

from ze_agents.errors import ZeError
from ze_agents.screen import ScreenResolver


class DuplicateScreenKindError(ZeError):
    """Two resolvers claimed the same screen kind."""


class ScreenResolverRegistry:
    def __init__(self, resolvers: Iterable[ScreenResolver] = ()) -> None:
        self._by_kind: dict[str, ScreenResolver] = {}
        for resolver in resolvers:
            self.register(resolver)

    def register(self, resolver: ScreenResolver) -> None:
        for kind in resolver.kinds:
            if kind in self._by_kind:
                raise DuplicateScreenKindError(
                    f"screen kind {kind!r} is already registered by "
                    f"{type(self._by_kind[kind]).__name__}; "
                    f"{type(resolver).__name__} cannot claim it"
                )
        for kind in resolver.kinds:
            self._by_kind[kind] = resolver

    def resolver_for(self, kind: str) -> ScreenResolver | None:
        return self._by_kind.get(kind)

    @property
    def kinds(self) -> frozenset[str]:
        return frozenset(self._by_kind)
