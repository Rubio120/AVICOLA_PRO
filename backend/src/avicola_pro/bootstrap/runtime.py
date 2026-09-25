from __future__ import annotations

import asyncio


def selector_loop_factory() -> asyncio.AbstractEventLoop:
    """Create the event loop required by Psycopg async on Windows."""
    return asyncio.SelectorEventLoop()
