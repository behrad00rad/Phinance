from decimal import Decimal
from django.db.models import Sum
from django.utils import timezone
from .models import Account, Asset, GoldPurchase, Transaction

def gold_summary(household):
    totals = GoldPurchase.objects.filter(household=household).aggregate(weight=Sum("weight_grams"), invested=Sum("amount_paid"))
    weight = totals["weight"] or Decimal("0")
    invested = totals["invested"] or 0
    price = getattr(getattr(household, "gold_price", None), "price_per_gram", 0)
    value = int(weight * price)
    return {"weight_grams": str(weight), "amount_invested": invested, "price_per_gram": price,
            "current_value": value, "profit_loss": value - invested}

def dashboard_summary(household):
    today = timezone.localdate()
    tx = Transaction.objects.filter(household=household, date__year=today.year, date__month=today.month)
    income = tx.filter(type="income").aggregate(v=Sum("amount"))["v"] or 0
    expense = tx.filter(type="expense").aggregate(v=Sum("amount"))["v"] or 0
    accounts = Account.objects.filter(household=household)
    account_total = sum(a.balance for a in accounts)
    asset_total = Asset.objects.filter(household=household, active=True).aggregate(v=Sum("current_value"))["v"] or 0
    gold = gold_summary(household)
    return {"net_worth": account_total + asset_total + gold["current_value"], "monthly_income": income,
            "monthly_expense": expense, "monthly_net": income - expense, "account_total": account_total,
            "asset_total": asset_total, "gold": gold}
