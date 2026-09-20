from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from importlib import import_module
from typing import Any
from uuid import UUID, uuid4

from avicola_pro.modules.treasury.domain.rules import (
    CashConflictError,
    calculate_expected_balance,
    validate_available_balance,
    validate_movement,
    validate_reversal,
)

select: Any = import_module("sqlalchemy").select
func: Any = import_module("sqlalchemy").func
_models = import_module("avicola_pro.modules.treasury.infrastructure.models")
CashAccount: Any = _models.CashAccount
CashMovement: Any = _models.CashMovement
CashSession: Any = _models.CashSession
CashTransfer: Any = _models.CashTransfer


class CashNotFoundError(LookupError):
    pass


class TreasuryService:
    async def open_session(
        self, session: Any, account_id: UUID, user_id: UUID, opening_balance: Decimal
    ) -> CashSession:
        account = await session.scalar(
            select(CashAccount).where(CashAccount.id == account_id, CashAccount.is_active.is_(True))
        )
        if account is None:
            raise CashNotFoundError("cash account not found")
        existing = await session.scalar(
            select(CashSession)
            .where(CashSession.cash_account_id == account_id, CashSession.status.in_(["OPEN", "REOPENED"]))
            .with_for_update()
        )
        if existing is not None:
            raise CashConflictError("cash account already has an open session")
        if opening_balance < 0:
            raise CashConflictError("opening balance cannot be negative")
        item = CashSession(id=uuid4(), cash_account_id=account_id, opened_by=user_id, opening_balance=opening_balance)
        session.add(item)
        await session.flush()
        return item

    async def create_movement(
        self,
        session: Any,
        session_id: UUID,
        account_id: UUID,
        user_id: UUID,
        movement_type: str,
        direction: str,
        amount: Decimal,
        effective_date: date,
        payment_method_code: str | None = None,
        source_type: str | None = None,
        source_id: UUID | None = None,
        reason: str | None = None,
        idempotency_key: str | None = None,
    ) -> CashMovement:
        validate_movement(amount, direction)
        cash_session = await session.scalar(select(CashSession).where(CashSession.id == session_id).with_for_update())
        if cash_session is None:
            raise CashNotFoundError("cash session not found")
        if cash_session.cash_account_id != account_id or cash_session.status not in {"OPEN", "REOPENED"}:
            raise CashConflictError("cash session is not open")
        rows = (
            await session.execute(
                select(CashMovement.direction, func.sum(CashMovement.amount))
                .where(CashMovement.cash_session_id == session_id)
                .group_by(CashMovement.direction)
            )
        ).all()
        expected = calculate_expected_balance(
            cash_session.opening_balance,
            [value if direction == "IN" else -value for direction, value in rows],
        )
        validate_available_balance(expected, amount, direction)
        if idempotency_key:
            existing = await session.scalar(select(CashMovement).where(CashMovement.idempotency_key == idempotency_key))
            if existing is not None:
                return existing
        item = CashMovement(
            id=uuid4(),
            cash_session_id=session_id,
            cash_account_id=account_id,
            movement_type=movement_type,
            direction=direction,
            amount=amount,
            effective_date=effective_date,
            payment_method_code=payment_method_code,
            source_type=source_type,
            source_id=source_id,
            reason=reason,
            actor_user_id=user_id,
            idempotency_key=idempotency_key,
        )
        session.add(item)
        await session.flush()
        return item

    async def transfer(
        self,
        session: Any,
        source_session_id: UUID,
        destination_session_id: UUID,
        source_account_id: UUID,
        destination_account_id: UUID,
        user_id: UUID,
        amount: Decimal,
        transfer_date: date,
        reason: str | None = None,
    ) -> CashTransfer:
        validate_movement(amount, "OUT")
        source = await session.scalar(select(CashSession).where(CashSession.id == source_session_id).with_for_update())
        destination = await session.scalar(
            select(CashSession).where(CashSession.id == destination_session_id).with_for_update()
        )
        if (
            source is None
            or destination is None
            or source.cash_account_id != source_account_id
            or destination.cash_account_id != destination_account_id
        ):
            raise CashNotFoundError("cash session not found")
        if source.status not in {"OPEN", "REOPENED"} or destination.status not in {"OPEN", "REOPENED"}:
            raise CashConflictError("both cash sessions must be open")
        rows = (
            await session.execute(
                select(CashMovement.direction, func.sum(CashMovement.amount))
                .where(CashMovement.cash_session_id == source_session_id)
                .group_by(CashMovement.direction)
            )
        ).all()
        expected = calculate_expected_balance(
            source.opening_balance,
            [value if direction == "IN" else -value for direction, value in rows],
        )
        validate_available_balance(expected, amount, "OUT")
        outgoing = CashMovement(
            id=uuid4(),
            cash_session_id=source_session_id,
            cash_account_id=source_account_id,
            movement_type="TRANSFER_OUT",
            direction="OUT",
            amount=amount,
            effective_date=transfer_date,
            reason=reason,
            actor_user_id=user_id,
        )
        incoming = CashMovement(
            id=uuid4(),
            cash_session_id=destination_session_id,
            cash_account_id=destination_account_id,
            movement_type="TRANSFER_IN",
            direction="IN",
            amount=amount,
            effective_date=transfer_date,
            reason=reason,
            actor_user_id=user_id,
        )
        session.add_all([outgoing, incoming])
        await session.flush()
        transfer = CashTransfer(
            id=uuid4(),
            source_movement_id=outgoing.id,
            destination_movement_id=incoming.id,
            amount=amount,
            transfer_date=transfer_date,
            reason=reason,
        )
        session.add(transfer)
        await session.flush()
        return transfer

    async def close_session(
        self, session: Any, session_id: UUID, user_id: UUID, counted_balance: Decimal
    ) -> CashSession:
        item = await session.scalar(select(CashSession).where(CashSession.id == session_id).with_for_update())
        if item is None:
            raise CashNotFoundError("cash session not found")
        if item.status not in {"OPEN", "REOPENED"}:
            raise CashConflictError("only an open session can be closed")
        rows = (
            await session.execute(
                select(CashMovement.direction, func.sum(CashMovement.amount))
                .where(CashMovement.cash_session_id == session_id)
                .group_by(CashMovement.direction)
            )
        ).all()
        signed = [amount if direction == "IN" else -amount for direction, amount in rows]
        expected = calculate_expected_balance(item.opening_balance, signed)
        item.expected_balance = expected
        item.counted_balance = counted_balance
        item.difference = counted_balance - expected
        item.status = "CLOSED"
        item.closed_by = user_id
        item.closed_at = datetime.now(UTC)
        item.version += 1
        await session.flush()
        return item

    async def reopen_session(self, session: Any, session_id: UUID, user_id: UUID, reason: str) -> CashSession:
        item = await session.scalar(select(CashSession).where(CashSession.id == session_id).with_for_update())
        if item is None:
            raise CashNotFoundError("cash session not found")
        if item.status != "CLOSED" or not reason.strip():
            raise CashConflictError("closed session and reason are required")
        item.status = "REOPENED"
        item.opened_by = user_id
        item.opened_at = datetime.now(UTC)
        item.version += 1
        await session.flush()
        return item

    async def reverse_movement(self, session: Any, movement_id: UUID, user_id: UUID, reason: str) -> CashMovement:
        original = await session.scalar(select(CashMovement).where(CashMovement.id == movement_id).with_for_update())
        if original is None:
            raise CashNotFoundError("cash movement not found")
        cash_session = await session.scalar(
            select(CashSession).where(CashSession.id == original.cash_session_id).with_for_update()
        )
        if cash_session is None:
            raise CashNotFoundError("cash session not found")
        validate_reversal(cash_session.status, reason)
        already = await session.scalar(select(CashMovement).where(CashMovement.reversal_of_id == movement_id))
        if already is not None:
            raise CashConflictError("movement is already reversed")
        reversal = CashMovement(
            id=uuid4(),
            cash_session_id=original.cash_session_id,
            cash_account_id=original.cash_account_id,
            movement_type="REVERSAL",
            direction="OUT" if original.direction == "IN" else "IN",
            amount=original.amount,
            effective_date=date.today(),
            reason=reason,
            reversal_of_id=original.id,
            actor_user_id=user_id,
        )
        session.add(reversal)
        original.status = "REVERSED"
        await session.flush()
        return reversal


treasury_service = TreasuryService()
