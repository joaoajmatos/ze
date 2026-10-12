"""Dev data seeding entry point — builds the full container, then runs ze-seed."""

from __future__ import annotations

import asyncio
import sys


async def _apply() -> None:
    from ze_api.container import build_container
    from ze_api.settings import get_settings
    from ze_seed.context import SeedContext
    from ze_seed.service import DevDataSeeder, collect_seed_domains

    settings = get_settings()
    container = await build_container(settings)
    try:
        ctx = SeedContext.from_container(container)
        seeder = DevDataSeeder(collect_seed_domains(container.plugins))
        results = await seeder.apply(ctx, force=True)
        print("Seed complete:", results)
    finally:
        await container.close()


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] != "apply":
        print("Usage: python -m ze_api.seed apply", file=sys.stderr)
        raise SystemExit(1)
    asyncio.run(_apply())


if __name__ == "__main__":
    main()
