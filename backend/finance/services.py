from decimal import Decimal
from django.db.models import F, Sum
from django.utils import timezone
from .models import Account, Asset, GoldPurchase, Loan, Obligation, Transaction

def gold_summary(household):
    purchases = list(GoldPurchase.objects.filter(household=household).order_by("-purchase_date", "-id"))
    price = getattr(getattr(household, "gold_price", None), "price_per_gram", 0)
    weight = Decimal("0")
    invested = Decimal("0")
    value = 0
    holdings = []
    for purchase in purchases:
        remaining = purchase.remaining_weight_grams
        remaining_cost = (Decimal(purchase.amount_paid) * remaining / purchase.weight_grams) if purchase.weight_grams else Decimal("0")
        current_value = int(remaining * price)
        holding_invested = int(remaining_cost)
        weight += remaining
        invested += remaining_cost
        value += current_value
        if remaining > 0:
            holdings.append({"id": purchase.id, "name": purchase.name, "purchase_date": purchase.purchase_date,
                             "weight_grams": str(purchase.weight_grams), "remaining_weight_grams": str(remaining),
                             "amount_paid": purchase.amount_paid, "invested_remaining": holding_invested,
                             "current_value": current_value, "profit_loss": current_value - holding_invested})
    return {"weight_grams": str(weight), "amount_invested": int(invested), "price_per_gram": price,
            "price_updated_at": getattr(getattr(household, "gold_price", None), "source_updated_at", None),
            "current_value": value, "profit_loss": value - int(invested), "holdings": holdings}

def dashboard_summary(household):
    today = timezone.localdate()
    tx = Transaction.objects.filter(household=household, date__year=today.year, date__month=today.month)
    income = tx.filter(type="income").aggregate(v=Sum("amount"))["v"] or 0
    expense = tx.filter(type="expense").aggregate(v=Sum("amount"))["v"] or 0
    accounts = Account.objects.filter(household=household)
    account_total = sum(a.balance for a in accounts)
    asset_total = Asset.objects.filter(household=household, active=True).aggregate(v=Sum("current_value"))["v"] or 0
    gold = gold_summary(household)
    obligations = Obligation.objects.filter(household=household)
    receivable = obligations.filter(kind="debt_receivable").aggregate(v=Sum(F("amount") - F("settled_amount")))["v"] or 0
    payable = obligations.filter(kind__in=("debt_owed", "bill")).aggregate(v=Sum(F("amount") - F("settled_amount")))["v"] or 0
    loans = Loan.objects.filter(household=household)
    lent_principal = loans.filter(direction="lent").aggregate(v=Sum(F("original_principal") - F("repaid_principal")))["v"] or 0
    borrowed_principal = loans.filter(direction="borrowed").aggregate(v=Sum(F("original_principal") - F("repaid_principal")))["v"] or 0
    return {"net_worth": account_total + asset_total + gold["current_value"] + receivable - payable + lent_principal - borrowed_principal, "monthly_income": income,
            "monthly_expense": expense, "monthly_net": income - expense, "account_total": account_total,
            "asset_total": asset_total, "receivable_total": receivable, "payable_total": payable,
            "lent_principal": lent_principal, "borrowed_principal": borrowed_principal, "gold": gold}
