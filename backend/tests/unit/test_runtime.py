from __future__ import annotations

import asyncio

from avicola_pro.bootstrap.runtime import selector_loop_factory


def test_selector_loop_factory_returns_psycopg_compatible_loop() -> None:
    loop = selector_loop_factory()

    try:
        assert isinstance(loop, asyncio.SelectorEventLoop)
    finally:
        loop.close()
