from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

import jdatetime
from django.db.models import F, Sum
from django.utils import timezone

from .models import Account, Asset, GoldPurchase, GoldSale, Loan, Obligation, Transaction

PERSIAN_MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
                  "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]


def default_insights_range():
    today = timezone.localdate()
    jalali = jdatetime.date.fromgregorian(date=today)
    month_number = jalali.year * 12 + jalali.month - 1 - 5
    year, month = divmod(month_number, 12)
    return jdatetime.date(year, month + 1, 1).togregorian(), today


def month_keys(start, end):
    first = jdatetime.date.fromgregorian(date=start)
    last = jdatetime.date.fromgregorian(date=end)
    current = first.year * 12 + first.month - 1
    final = last.year * 12 + last.month - 1
    while current <= final:
        year, zero_month = divmod(current, 12)
        month = zero_month + 1
        yield (year, month)
        current += 1


def _local_created_date(record):
    return timezone.localtime(record.created_at).date()


def _net_worth_at(point, accounts, transactions, assets, gold_purchases, gold_sales, gold_price, obligations, loans):
    account_ids = {account.id for account in accounts if _local_created_date(account) <= point}
    account_total = sum(account.opening_balance for account in accounts if account.id in account_ids)
    for tx in transactions:
        if tx.date <= point:
            if tx.destination_account_id in account_ids:
                account_total += tx.amount
            if tx.source_account_id in account_ids:
                account_total -= tx.amount
    for sale in gold_sales:
        if sale.sale_date <= point and sale.account_id in account_ids:
            account_total += sale.amount_received

    asset_total = sum(asset.current_value for asset in assets if asset.active and
                      (asset.purchase_date or _local_created_date(asset)) <= point)
    gold_value = 0
    for purchase in gold_purchases:
        if purchase.purchase_date <= point:
            sold = sum(sale.weight_grams for sale in gold_sales if sale.purchase_id == purchase.id and sale.sale_date <= point)
            gold_value += int(max(Decimal("0"), purchase.weight_grams - sold) * gold_price)

    receivable = payable = 0
    for item in obligations:
        if _local_created_date(item) > point:
            continue
        settled = sum(payment.transaction.amount for payment in item.settlements.all()
                      if payment.transaction.date <= point)
        remaining = max(0, item.amount - settled)
        if item.kind == "debt_receivable":
            receivable += remaining
        elif item.kind in ("debt_owed", "bill"):
            payable += remaining
    for loan in loans:
        if loan.start_date > point:
            continue
        repaid = sum(payment.principal_amount for payment in loan.repayments.all() if payment.date <= point)
        remaining = max(0, loan.original_principal - repaid)
        if loan.direction == "lent":
            receivable += remaining
        else:
            payable += remaining
    return account_total + asset_total + gold_value + receivable - payable


def insights_summary(household, start, end):
    today = timezone.localdate()
    current_transactions = list(Transaction.objects.filter(household=household, date__range=(start, end))
                                .select_related("category"))
    span = (end - start).days + 1
    previous_end = start - timedelta(days=1)
    previous_start = start - timedelta(days=span)
    previous_expenses = Transaction.objects.filter(household=household, type="expense",
                                                    date__range=(previous_start, previous_end)).values(
        "category_id", "category__name").annotate(amount=Sum("amount"))
    category_totals = defaultdict(int)
    for tx in current_transactions:
        if tx.type == "expense":
            category_totals[(tx.category_id, tx.category.name if tx.category else "بدون دسته")] += tx.amount
    previous_totals = {(row["category_id"], row["category__name"] or "بدون دسته"): row["amount"]
                       for row in previous_expenses}
    categories = [{"category_id": key[0], "name": key[1], "amount": category_totals[key],
                   "previous_amount": previous_totals.get(key, 0),
                   "change": category_totals[key] - previous_totals.get(key, 0)}
                  for key in category_totals.keys() | previous_totals.keys()]
    categories.sort(key=lambda row: (-row["amount"], -row["previous_amount"], row["name"]))

    monthly = {(year, month): {"year": year, "month": month, "label": f"{PERSIAN_MONTHS[month - 1]} {year}",
                               "income": 0, "expense": 0, "net": 0}
               for year, month in month_keys(start, end)}
    for tx in current_transactions:
        if tx.type not in ("income", "expense"):
            continue
        jalali = jdatetime.date.fromgregorian(date=tx.date)
        monthly[(jalali.year, jalali.month)][tx.type] += tx.amount
    for row in monthly.values():
        row["net"] = row["income"] - row["expense"]
    month_rows = list(monthly.values())

    due_rows = []
    due_totals = {kind: {"upcoming_count": 0, "upcoming_amount": 0, "overdue_count": 0, "overdue_amount": 0}
                  for kind in ("bill", "expected_payment")}
    for item in Obligation.objects.filter(household=household, kind__in=("bill", "expected_payment"),
                                           settled_amount__lt=F("amount")).order_by("due_date", "id"):
        remaining = item.remaining_amount
        bucket = "overdue" if item.due_date < today else "upcoming" if item.due_date <= today + timedelta(days=30) else None
        if bucket:
            due_totals[item.kind][f"{bucket}_count"] += 1
            due_totals[item.kind][f"{bucket}_amount"] += remaining
            due_rows.append({"id": item.id, "kind": item.kind, "counterparty": item.counterparty,
                             "due_date": item.due_date, "remaining_amount": remaining, "status": bucket})

    loans = Loan.objects.filter(household=household)
    loan_balances = {direction: {"principal": 0, "interest": 0, "total": 0, "count": 0}
                     for direction in ("borrowed", "lent")}
    for loan in loans:
        if loan.remaining_balance:
            row = loan_balances[loan.direction]
            row["principal"] += loan.remaining_principal
            row["interest"] += loan.remaining_interest
            row["total"] += loan.remaining_balance
            row["count"] += 1

    accounts = list(Account.objects.filter(household=household))
    transactions = list(Transaction.objects.filter(household=household, date__lte=end))
    assets = list(Asset.objects.filter(household=household))
    gold_purchases = list(GoldPurchase.objects.filter(household=household, purchase_date__lte=end))
    gold_sales = list(GoldSale.objects.filter(household=household, sale_date__lte=end))
    obligations = list(Obligation.objects.filter(household=household).prefetch_related("settlements__transaction"))
    all_loans = list(loans.prefetch_related("repayments"))
    gold_price = getattr(getattr(household, "gold_price", None), "price_per_gram", 0)
    history = []
    for year, month in month_keys(start, end):
        next_month_number = year * 12 + month
        next_year, next_zero_month = divmod(next_month_number, 12)
        next_start = jdatetime.date(next_year, next_zero_month + 1, 1).togregorian()
        point = min(next_start - timedelta(days=1), end, today)
        if point < start:
            continue
        history.append({"date": point, "label": f"{PERSIAN_MONTHS[month - 1]} {year}",
                        "value": _net_worth_at(point, accounts, transactions, assets, gold_purchases,
                                               gold_sales, gold_price, obligations, all_loans)})

    return {"start": start, "end": end, "previous_start": previous_start, "previous_end": previous_end,
            "monthly": month_rows, "totals": {"income": sum(row["income"] for row in month_rows),
                                                 "expense": sum(row["expense"] for row in month_rows),
                                                 "net": sum(row["net"] for row in month_rows)},
            "expense_categories": categories, "due": {"next_days": 30, "totals": due_totals, "items": due_rows[:8]},
            "loans": loan_balances, "net_worth_history": history,
            "net_worth_estimated": True}
