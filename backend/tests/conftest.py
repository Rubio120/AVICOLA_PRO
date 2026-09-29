from __future__ import annotations

import asyncio
import selectors
import sys
from collections.abc import Callable, Mapping

import pytest


def _windows_selector_loop() -> asyncio.AbstractEventLoop:
    return asyncio.SelectorEventLoop(selectors.SelectSelector())


def pytest_asyncio_loop_factories(
    config: pytest.Config,
    item: pytest.Item,
) -> Mapping[str, Callable[[], asyncio.AbstractEventLoop]]:
    del config, item
    if sys.platform == "win32":
        return {"windows-selector": _windows_selector_loop}
    return {"default": asyncio.new_event_loop}
