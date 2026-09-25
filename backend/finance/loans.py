from decimal import Decimal, ROUND_HALF_UP

import jdatetime


def fixed_interest(principal, annual_rate, start_date, maturity_date):
    """Simple, non-compounding interest fixed for the stated term."""
    if not annual_rate:
        return 0
    days = (maturity_date - start_date).days
    return int((Decimal(principal) * annual_rate * Decimal(days) / Decimal(36500)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP))


def monthly_due_dates(first_due_date, count):
    """Advance by Persian calendar months, retaining the intended day where possible."""
    first = jdatetime.date.fromgregorian(date=first_due_date)
    result = []
    for index in range(count):
        month_number = (first.year * 12 + first.month - 1) + index
        year, month = divmod(month_number, 12)
        month += 1
        day = first.day
        while True:
            try:
                result.append(jdatetime.date(year, month, day).togregorian())
                break
            except ValueError:
                day -= 1
                if day < 1:
                    raise
    return result


def equal_installment_amounts(total, count):
    base, remainder = divmod(total, count)
    if base < 1:
        raise ValueError("تعداد اقساط از مبلغ کل بیشتر است.")
    return [base] * (count - 1) + [base + remainder]
