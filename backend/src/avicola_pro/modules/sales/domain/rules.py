from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


class SalesConflictError(ValueError):
    pass


CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_tax_line(
    quantity: Decimal, unit_price: Decimal, discount_rate: Decimal, tax_rate: Decimal
) -> tuple[Decimal, Decimal, Decimal]:
    gross = money(quantity * unit_price)
    discount = money(gross * discount_rate)
    base = money(gross - discount)
    tax = money(base * tax_rate)
    return base, tax, money(base + tax)


def calculate_document_totals(lines: list[dict[str, Decimal]]) -> dict[str, Decimal]:
    result = {
        "exempt_subtotal": Decimal("0"),
        "vat_5_base": Decimal("0"),
        "vat_5_amount": Decimal("0"),
        "vat_10_base": Decimal("0"),
        "vat_10_amount": Decimal("0"),
        "discount_total": Decimal("0"),
    }
    for line in lines:
        base, tax, total = calculate_tax_line(
            line["quantity"], line["unit_price"], line.get("discount_rate", Decimal("0")), line["tax_rate"]
        )
        line["base"] = base
        line["tax_amount"] = tax
        line["total"] = total
        result["discount_total"] += money(
            line["quantity"] * line["unit_price"] * line.get("discount_rate", Decimal("0"))
        )
        rate = line["tax_rate"]
        if rate == Decimal("0"):
            result["exempt_subtotal"] += base
        elif rate == Decimal("0.05"):
            result["vat_5_base"] += base
            result["vat_5_amount"] += tax
        elif rate == Decimal("0.10"):
            result["vat_10_base"] += base
            result["vat_10_amount"] += tax
        else:
            raise SalesConflictError("only exempt, 5% and 10% VAT are supported")
    result["subtotal"] = money(result["exempt_subtotal"] + result["vat_5_base"] + result["vat_10_base"])
    result["tax_total"] = money(result["vat_5_amount"] + result["vat_10_amount"])
    result["total"] = money(result["subtotal"] + result["tax_total"])
    return result


def apply_customer_payment(payment_amount: Decimal, allocated_amount: Decimal, balance: Decimal) -> Decimal:
    if payment_amount <= 0:
        raise SalesConflictError("payment amount must be positive")
    if allocated_amount > payment_amount:
        raise SalesConflictError("payment amount exceeds payment")
    if allocated_amount > balance:
        raise SalesConflictError("payment amount exceeds account balance")
    return money(balance - allocated_amount)


def validate_credit_note_amount(original_total: Decimal, credited_total: Decimal, requested: Decimal) -> None:
    if requested <= 0:
        raise SalesConflictError("credit note amount must be positive")
    if credited_total + requested > original_total:
        raise SalesConflictError("credit notes exceed original document")
