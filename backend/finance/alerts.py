from datetime import timedelta

import jdatetime
from django.db.models import F, Sum
from django.utils import timezone

from .models import AlertPreference, Loan, Notification, Obligation, Transaction


def preferences_for(user):
    return AlertPreference.objects.get_or_create(user=user)[0]


def sync_alerts(user, household):
    """Create one history entry per due state or Jalali spending month."""
    preferences = preferences_for(user)
    today = timezone.localdate()
    horizon = today + timedelta(days=preferences.days_ahead)
    candidates = []

    def add(key, kind, title, detail, due_date=None):
        candidates.append(Notification(user=user, household=household, key=key, kind=kind,
                                       title=title, detail=detail, due_date=due_date))

    if preferences.bills or preferences.expected_income:
        for item in Obligation.objects.filter(household=household, kind__in=("bill", "expected_payment"),
                                               settled_amount__lt=F("amount"), due_date__lte=horizon):
            if item.kind == "bill" and not preferences.bills or item.kind == "expected_payment" and not preferences.expected_income:
                continue
            overdue = item.due_date < today
            if item.kind == "bill":
                title = "قبض عقب‌افتاده" if overdue else "سررسید قبض نزدیک است"
                kind = "bill_overdue" if overdue else "bill_upcoming"
            else:
                # Expected income is only flagged after its expected date.
                if not overdue:
                    continue
                title, kind = "دریافتی مورد انتظار نرسیده است", "income_overdue"
            add(f"{kind}:{item.id}:{item.due_date}", kind, title,
                f"{item.counterparty} · مانده {item.remaining_amount:,} تومان", item.due_date)

    if preferences.loans:
        for loan in Loan.objects.filter(household=household, installments__due_date__lte=horizon).distinct().prefetch_related("installments", "repayments"):
            # Payments are allocated to installments in due-date order.
            paid = loan.repaid_principal + loan.repaid_interest
            for installment in loan.installments.all():
                applied = min(paid, installment.amount)
                paid -= applied
                remaining = installment.amount - applied
                if remaining <= 0 or installment.due_date > horizon:
                    continue
                overdue = installment.due_date < today
                kind = "loan_overdue" if overdue else "loan_upcoming"
                title = "قسط وام عقب‌افتاده" if overdue else "سررسید قسط وام نزدیک است"
                add(f"{kind}:{installment.id}:{installment.due_date}", kind, title,
                    f"{loan.party} · مانده قسط {remaining:,} تومان", installment.due_date)

    if preferences.high_spending:
        current = jdatetime.date.fromgregorian(date=today)
        start = jdatetime.date(current.year, current.month, 1).togregorian()
        previous_day = start - timedelta(days=1)
        previous = jdatetime.date.fromgregorian(date=previous_day)
        previous_start = jdatetime.date(previous.year, previous.month, 1).togregorian()
        elapsed = (today - start).days
        comparison_end = min(previous_day, previous_start + timedelta(days=elapsed))
        current_rows = Transaction.objects.filter(household=household, type="expense", date__range=(start, today)).values(
            "category_id", "category__name").annotate(total=Sum("amount"))
        previous_rows = Transaction.objects.filter(household=household, type="expense", date__range=(previous_start, comparison_end)).values(
            "category_id").annotate(total=Sum("amount"))
        previous_totals = {row["category_id"]: row["total"] for row in previous_rows}
        for row in current_rows:
            baseline = previous_totals.get(row["category_id"], 0)
            # Compare equal elapsed days; require meaningful history and increase.
            if baseline >= 100_000 and row["total"] >= baseline * 1.5 and row["total"] - baseline >= 100_000:
                add(f"spending:{current.year}-{current.month}:{row['category_id']}", "high_spending",
                    "هزینه این دسته بیشتر از معمول است",
                    f"{row['category__name'] or 'بدون دسته'} · {row['total']:,} تومان تا امروز؛ دوره مشابه قبل {baseline:,} تومان")

    Notification.objects.bulk_create(candidates, ignore_conflicts=True)
    return preferences
