from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from avicola_pro.modules.sales.application.service import SalesService
from avicola_pro.modules.sales.domain.rules import SalesConflictError


class CategoryResult:
    def __init__(self, category: Any) -> None:
        self.category = category

    def all(self) -> list[Any]:
        return [] if self.category is None else [self.category]


class CategorySession:
    def __init__(self, category: Any) -> None:
        self.category = category

    async def scalars(self, _: object) -> CategoryResult:
        return CategoryResult(self.category)


@pytest.mark.asyncio
async def test_sales_service_rejects_egg_category_not_explicitly_marked_saleable() -> None:
    service = SalesService()
    category = SimpleNamespace(is_active=True, is_saleable=False)
    with pytest.raises(SalesConflictError, match="not configured for sale"):
        await service._ensure_egg_products_are_saleable(CategorySession(category), {uuid4()})


@pytest.mark.asyncio
async def test_sales_service_rejects_inactive_egg_category() -> None:
    service = SalesService()
    category = SimpleNamespace(is_active=False, is_saleable=True)
    with pytest.raises(SalesConflictError, match="inactive"):
        await service._ensure_egg_products_are_saleable(CategorySession(category), {uuid4()})


@pytest.mark.asyncio
async def test_sales_service_allows_explicitly_active_saleable_egg_category() -> None:
    service = SalesService()
    category = SimpleNamespace(is_active=True, is_saleable=True)
    await service._ensure_egg_products_are_saleable(CategorySession(category), {uuid4()})
