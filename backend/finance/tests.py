from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from .models import Account, Asset, Category, GoldPrice, GoldPurchase, Household, Loan, LoanInstallment, LoanRepayment, Notification, Obligation, ObligationSettlement, Transaction
from .services import dashboard_summary, gold_summary
from .loans import fixed_interest

class FinanceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="parent", password="strong-test-password")
        self.other = get_user_model().objects.create_user(username="other", password="strong-test-password")
        self.household = Household.objects.create(name="Our family", owner=self.user)
        self.household.members.add(self.user)
        self.other_household = Household.objects.create(name="Other family", owner=self.other)
        self.other_household.members.add(self.other)
        self.bank = Account.objects.create(household=self.household, name="Bank", account_type="bank", opening_balance=1000)
        self.cash = Account.objects.create(household=self.household, name="Cash", account_type="cash")
        self.income = Category.objects.create(household=self.household, name="Salary", type="income")
        self.expense = Category.objects.create(household=self.household, name="Food", type="expense")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def add_transaction(self, kind, amount, source=None, destination=None, category=None):
        return Transaction.objects.create(household=self.household, created_by=self.user, date=timezone.localdate(), type=kind,
                                          amount=amount, source_account=source, destination_account=destination, category=category)

    def test_alert_due_dates_history_and_preferences(self):
        today = timezone.localdate()
        bill = Obligation.objects.create(household=self.household, kind="bill", counterparty="Power", amount=500,
                                         due_date=today + timedelta(days=3), created_by=self.user)
        Obligation.objects.create(household=self.household, kind="expected_payment", counterparty="Client", amount=800,
                                  due_date=today - timedelta(days=1), created_by=self.user)
        response = self.client.get('/api/notifications/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual({row['kind'] for row in response.data['items']}, {'bill_upcoming', 'income_overdue'})
        self.client.get('/api/notifications/')
        self.assertEqual(Notification.objects.count(), 2)
        entry = Notification.objects.get(kind='bill_upcoming')
        self.assertEqual(self.client.post(f'/api/notifications/{entry.id}/read/').status_code, 200)
        self.assertEqual(self.client.get('/api/notifications/').data['unread_count'], 1)
        self.assertEqual(self.client.patch('/api/alert-preferences/', {'days_ahead': 1, 'bills': False}, format='json').status_code, 200)
        self.assertEqual(self.client.patch('/api/alert-preferences/', {'days_ahead': 91}, format='json').status_code, 400)
        self.assertEqual(self.client.patch('/api/alert-preferences/', {'loans': 'false'}, format='json').status_code, 400)
        bill.due_date = today - timedelta(days=1); bill.save()
        self.client.get('/api/notifications/')
        self.assertFalse(Notification.objects.filter(kind='bill_overdue').exists())

    def test_alert_loan_partial_repayment_and_household_isolation(self):
        today = timezone.localdate()
        loan = Loan.objects.create(household=self.household, direction='borrowed', party='Bank', original_principal=1000,
                                   start_date=today - timedelta(days=20), created_by=self.user, repaid_principal=300)
        LoanInstallment.objects.create(loan=loan, due_date=today - timedelta(days=1), amount=500)
        LoanInstallment.objects.create(loan=loan, due_date=today + timedelta(days=2), amount=500)
        other_loan = Loan.objects.create(household=self.other_household, direction='borrowed', party='Private',
                                         original_principal=5000, start_date=today, created_by=self.other)
        LoanInstallment.objects.create(loan=other_loan, due_date=today, amount=5000)
        response = self.client.get('/api/notifications/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['kind'] for row in response.data['items']].count('loan_overdue'), 1)
        self.assertEqual([row['kind'] for row in response.data['items']].count('loan_upcoming'), 1)
        self.assertTrue(any('200' in row['detail'] for row in response.data['items']))
        self.assertFalse(any('Private' in row['detail'] for row in response.data['items']))
        self.assertEqual(self.client.post(f'/api/notifications/{Notification.objects.last().id}/read/').status_code, 200)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get('/api/notifications/').data['unread_count'], 1)
        self.assertEqual(self.client.post(f'/api/notifications/{Notification.objects.filter(user=self.user).first().id}/read/').status_code, 404)

    def test_alert_high_spending_uses_comparable_period(self):
        import jdatetime
        today = timezone.localdate()
        jalali = jdatetime.date.fromgregorian(date=today)
        start = jdatetime.date(jalali.year, jalali.month, 1).togregorian()
        previous_day = start - timedelta(days=1)
        previous = jdatetime.date.fromgregorian(date=previous_day)
        previous_start = jdatetime.date(previous.year, previous.month, 1).togregorian()
        Transaction.objects.create(household=self.household, created_by=self.user, date=previous_start, type='expense',
                                   amount=200_000, source_account=self.bank, category=self.expense)
        self.add_transaction('expense', 400_000, source=self.bank, category=self.expense)
        response = self.client.get('/api/notifications/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Notification.objects.filter(kind='high_spending').count(), 1)

    def test_balances_and_monthly_summary(self):
        self.add_transaction("income", 500, destination=self.bank, category=self.income)
        self.add_transaction("expense", 200, source=self.bank, category=self.expense)
        self.add_transaction("transfer", 300, source=self.bank, destination=self.cash)
        self.assertEqual(self.bank.balance, 1000)
        self.assertEqual(self.cash.balance, 300)
        summary = dashboard_summary(self.household)
        self.assertEqual(summary["monthly_income"], 500)
        self.assertEqual(summary["monthly_expense"], 200)
        self.assertEqual(summary["monthly_net"], 300)
        self.assertEqual(summary["net_worth"], 1300)

    def test_transfer_validation_and_overdraft(self):
        response = self.client.post("/api/transactions/", {"type": "transfer", "amount": 100, "date": str(date.today()),
                                                       "source_account": self.bank.id, "destination_account": self.bank.id}, format="json")
        self.assertEqual(response.status_code, 400)
        response = self.client.post("/api/transactions/", {"type": "expense", "amount": 1001, "date": str(date.today()),
                                                       "source_account": self.bank.id, "category": self.expense.id}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_api_income_expense_transfer_flow(self):
        for payload in [
            {"type": "income", "amount": 500, "destination_account": self.bank.id, "category": self.income.id},
            {"type": "expense", "amount": 200, "source_account": self.bank.id, "category": self.expense.id},
            {"type": "transfer", "amount": 300, "source_account": self.bank.id, "destination_account": self.cash.id},
        ]:
            response = self.client.post("/api/transactions/", {**payload, "date": str(timezone.localdate())}, format="json")
            self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.client.get("/api/dashboard/").data["net_worth"], 1300)
        self.assertEqual(self.client.get(f"/api/accounts/{self.cash.id}/").data["balance"], 300)

    def test_household_isolation(self):
        foreign = Account.objects.create(household=self.other_household, name="Private", account_type="bank")
        self.assertEqual(self.client.get(f"/api/accounts/{foreign.id}/").status_code, 404)
        response = self.client.post("/api/transactions/", {"type": "income", "amount": 50, "date": str(date.today()),
                                                       "destination_account": foreign.id, "category": self.income.id}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_gold_and_net_worth(self):
        GoldPurchase.objects.create(household=self.household, purchase_date=date.today(), weight_grams=Decimal("2.500"), remaining_weight_grams=Decimal("2.500"), amount_paid=500)
        GoldPrice.objects.create(household=self.household, price_per_gram=250)
        Asset.objects.create(household=self.household, name="Home", asset_type="property", current_value=2000)
        gold = gold_summary(self.household)
        self.assertEqual(gold["current_value"], 625)
        self.assertEqual(gold["profit_loss"], 125)
        self.assertEqual(dashboard_summary(self.household)["net_worth"], 3625)

    def test_named_gold_purchase_and_partial_sale(self):
        GoldPrice.objects.create(household=self.household, price_per_gram=300)
        response = self.client.post("/api/gold-purchases/", {"name": "Bracelet", "purchase_date": str(date.today()),
                                                             "weight_grams": "5.000", "amount_paid": 1000}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        holding_id = response.data["id"]
        self.assertEqual(Decimal(response.data["remaining_weight_grams"]), Decimal("5.000"))
        response = self.client.post("/api/gold-sales/", {"purchase": holding_id, "account": self.bank.id,
                                                          "sale_date": str(date.today()), "weight_grams": "2.000",
                                                          "price_per_gram": 300}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["amount_received"], 600)
        self.bank.refresh_from_db()
        self.assertEqual(self.bank.balance, 1600)
        gold = gold_summary(self.household)
        self.assertEqual(gold["weight_grams"], "3.000")
        self.assertEqual(gold["current_value"], 900)
        self.assertEqual(gold["amount_invested"], 600)
        self.assertEqual(gold["holdings"][0]["profit_loss"], 300)
        self.assertEqual(dashboard_summary(self.household)["net_worth"], 2500)

    def test_gold_sale_cannot_exceed_remaining_weight(self):
        holding = GoldPurchase.objects.create(household=self.household, name="Ring", purchase_date=date.today(),
                                              weight_grams=Decimal("1.000"), remaining_weight_grams=Decimal("1.000"), amount_paid=500)
        response = self.client.post("/api/gold-sales/", {"purchase": holding.id, "account": self.bank.id,
                                                          "sale_date": str(date.today()), "weight_grams": "1.001",
                                                          "price_per_gram": 300}, format="json")
        self.assertEqual(response.status_code, 400)
        holding.refresh_from_db()
        self.assertEqual(holding.remaining_weight_grams, Decimal("1.000"))

    def test_login_requires_csrf(self):
        browser = APIClient(enforce_csrf_checks=True)
        self.assertEqual(browser.post("/api/auth/login/", {"username": "parent", "password": "strong-test-password"}, format="json").status_code, 403)
        browser.get("/api/auth/csrf/")
        token = browser.cookies["csrftoken"].value
        response = browser.post("/api/auth/login/", {"username": "parent", "password": "strong-test-password"}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)

    def create_obligation(self, kind, amount=600, **extra):
        payload = {"kind": kind, "counterparty": "Test person", "amount": amount,
                   "due_date": str(timezone.localdate() + timedelta(days=3)), "notes": "Test note", **extra}
        response = self.client.post("/api/obligations/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return response.data["id"]

    def settle_obligation(self, obligation_id, amount, account=None, key=None):
        payload = {"amount": amount, "date": str(timezone.localdate()), "idempotency_key": str(key or uuid4())}
        if account:
            payload["account"] = account.id
        return self.client.post(f"/api/obligations/{obligation_id}/settle/", payload, format="json")

    def test_expected_payment_partial_final_and_idempotent_receipt(self):
        obligation_id = self.create_obligation("expected_payment", destination_account=self.bank.id, category=self.income.id)
        self.assertEqual(self.bank.balance, 1000)
        self.assertEqual(dashboard_summary(self.household)["monthly_income"], 0)
        key = uuid4()
        partial = self.settle_obligation(obligation_id, 250, key=key)
        self.assertEqual(partial.status_code, 201, partial.data)
        self.assertEqual((partial.data["settled_amount"], partial.data["remaining_amount"], partial.data["status"]), (250, 350, "partial"))
        self.assertEqual(self.settle_obligation(obligation_id, 250, key=key).status_code, 200)
        self.assertEqual(self.bank.balance, 1250)
        self.assertEqual(dashboard_summary(self.household)["monthly_income"], 250)
        self.assertEqual(self.settle_obligation(obligation_id, 351).status_code, 400)
        final = self.settle_obligation(obligation_id, 350)
        self.assertEqual(final.status_code, 201, final.data)
        self.assertEqual((final.data["remaining_amount"], final.data["status"]), (0, "settled"))
        self.assertEqual(self.bank.balance, 1600)
        self.assertEqual(dashboard_summary(self.household)["monthly_income"], 600)
        self.assertEqual(Transaction.objects.filter(type="income").count(), 2)
        self.assertEqual(ObligationSettlement.objects.count(), 2)

    def test_bill_partial_payment_totals_and_overdue(self):
        obligation_id = self.create_obligation("bill", 500, category=self.expense.id,
                                               due_date=str(timezone.localdate() - timedelta(days=1)))
        item = self.client.get(f"/api/obligations/{obligation_id}/").data
        self.assertTrue(item["is_overdue"])
        self.assertEqual(item["status"], "pending")
        self.assertEqual(self.bank.balance, 1000)
        self.assertEqual(dashboard_summary(self.household)["monthly_expense"], 0)
        self.assertEqual(dashboard_summary(self.household)["payable_total"], 500)
        partial = self.settle_obligation(obligation_id, 200, account=self.bank)
        self.assertEqual(partial.status_code, 201, partial.data)
        self.assertEqual((partial.data["remaining_amount"], partial.data["status"], partial.data["is_overdue"]), (300, "partial", True))
        self.assertEqual(self.bank.balance, 800)
        self.assertEqual(dashboard_summary(self.household)["monthly_expense"], 200)
        final = self.settle_obligation(obligation_id, 300, account=self.bank)
        self.assertEqual(final.status_code, 201, final.data)
        self.assertEqual((final.data["remaining_amount"], final.data["status"], final.data["is_overdue"]), (0, "settled", False))
        self.assertEqual(self.bank.balance, 500)
        self.assertEqual(dashboard_summary(self.household)["monthly_expense"], 500)
        self.assertEqual(dashboard_summary(self.household)["payable_total"], 0)

    def test_debt_principal_flows_do_not_change_income_expense_or_net_worth(self):
        owed_id = self.create_obligation("debt_owed", 200)
        receivable_id = self.create_obligation("debt_receivable", 300)
        before = dashboard_summary(self.household)
        self.assertEqual((before["receivable_total"], before["payable_total"], before["net_worth"]), (300, 200, 1100))
        self.assertEqual(self.settle_obligation(owed_id, 100, account=self.bank).status_code, 201)
        self.assertEqual(self.settle_obligation(receivable_id, 150, account=self.cash).status_code, 201)
        after = dashboard_summary(self.household)
        self.assertEqual((after["monthly_income"], after["monthly_expense"]), (0, 0))
        self.assertEqual((after["receivable_total"], after["payable_total"], after["net_worth"]), (150, 100, 1100))
        self.assertEqual((self.bank.balance, self.cash.balance), (900, 150))
        self.assertEqual(set(Transaction.objects.values_list("type", flat=True)), {"debt_payment", "debt_receipt"})

    def test_obligation_validation_and_household_isolation(self):
        foreign_account = Account.objects.create(household=self.other_household, name="Private", account_type="bank")
        foreign_category = Category.objects.create(household=self.other_household, name="Private expense", type="expense")
        bad = self.client.post("/api/obligations/", {"kind": "expected_payment", "counterparty": "X", "amount": 0,
                                                    "due_date": str(timezone.localdate()), "destination_account": self.bank.id,
                                                    "category": self.income.id}, format="json")
        self.assertEqual(bad.status_code, 400)
        bad = self.client.post("/api/obligations/", {"kind": "expected_payment", "counterparty": "X", "amount": 100,
                                                    "due_date": str(timezone.localdate()), "destination_account": foreign_account.id,
                                                    "category": self.income.id}, format="json")
        self.assertEqual(bad.status_code, 400)
        bad = self.client.post("/api/obligations/", {"kind": "bill", "counterparty": "X", "amount": 100,
                                                    "due_date": str(timezone.localdate()), "category": foreign_category.id}, format="json")
        self.assertEqual(bad.status_code, 400)
        bill_id = self.create_obligation("bill", 100, category=self.expense.id)
        self.assertEqual(self.settle_obligation(bill_id, 100, account=foreign_account).status_code, 400)
        self.assertEqual(self.settle_obligation(bill_id, 1001, account=self.bank).status_code, 400)
        self.assertEqual(ObligationSettlement.objects.count(), 0)
        other_client = APIClient()
        other_client.force_authenticate(self.other)
        self.assertEqual(other_client.get(f"/api/obligations/{bill_id}/").status_code, 404)
        self.assertEqual(other_client.post(f"/api/obligations/{bill_id}/settle/", {}, format="json").status_code, 404)
        self.assertEqual(self.client.post("/api/transactions/", {"type": "debt_payment", "amount": 50,
            "date": str(timezone.localdate()), "source_account": self.bank.id}, format="json").status_code, 400)

    def test_bill_payment_cannot_overdraw_account(self):
        obligation_id = self.create_obligation("bill", 1200, category=self.expense.id)
        response = self.settle_obligation(obligation_id, 1100, account=self.bank)
        self.assertEqual(response.status_code, 400)
        item = Obligation.objects.get(pk=obligation_id)
        self.assertEqual((item.settled_amount, item.status), (0, "pending"))
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(self.bank.balance, 1000)

    def create_loan(self, direction, principal=500, **extra):
        payload = {"direction": direction, "party": "Loan party", "original_principal": principal,
                   "start_date": str(timezone.localdate()), "notes": "Loan note", **extra}
        response = self.client.post("/api/loans/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def repay_loan(self, loan_id, amount, account=None, key=None, date_value=None):
        return self.client.post(f"/api/loans/{loan_id}/repay/", {
            "amount": amount, "account": (account or self.bank).id,
            "date": str(date_value or timezone.localdate()), "idempotency_key": str(key or uuid4())}, format="json")

    def test_borrowed_loan_origination_and_partial_principal_repayment(self):
        loan = self.create_loan("borrowed", origination_account=self.bank.id)
        self.assertEqual((loan["total_interest"], loan["remaining_principal"], loan["remaining_balance"]), (0, 500, 500))
        self.assertEqual(self.bank.balance, 1500)
        self.assertEqual(dashboard_summary(self.household)["net_worth"], 1000)
        key = uuid4()
        partial = self.repay_loan(loan["id"], 200, key=key)
        self.assertEqual(partial.status_code, 201, partial.data)
        self.assertEqual(partial.data["remaining_principal"], 300)
        self.assertEqual(self.repay_loan(loan["id"], 200, key=key).status_code, 200)
        self.assertEqual(self.repay_loan(loan["id"], 301).status_code, 400)
        self.assertEqual(self.bank.balance, 1300)
        summary = dashboard_summary(self.household)
        self.assertEqual((summary["monthly_income"], summary["monthly_expense"], summary["net_worth"]), (0, 0, 1000))
        self.assertEqual(LoanRepayment.objects.count(), 1)

    def test_lent_loan_interest_and_jalali_monthly_schedule(self):
        today = timezone.localdate()
        start = today - timedelta(days=10)
        first_due = today + timedelta(days=20)
        loan = self.create_loan("lent", principal=600, start_date=str(start), origination_account=self.bank.id,
                                annual_interest_rate="12.00", first_due_date=str(first_due), installment_count=2)
        self.assertEqual(len(loan["installments"]), 2)
        self.assertEqual(loan["installments"][0]["due_date"], first_due)
        self.assertEqual(loan["installments"][0]["status"], "upcoming")
        self.assertEqual(sum(row["amount"] for row in loan["installments"]), loan["remaining_balance"])
        expected_interest = fixed_interest(600, Decimal("12.00"), start, date.fromisoformat(loan["maturity_date"]))
        self.assertEqual(loan["total_interest"], expected_interest)
        self.assertEqual(self.bank.balance, 400)
        self.assertEqual(dashboard_summary(self.household)["net_worth"], 1000)
        payment = self.repay_loan(loan["id"], expected_interest + 200)
        self.assertEqual(payment.status_code, 201, payment.data)
        self.assertEqual((payment.data["remaining_principal"], payment.data["remaining_interest"]), (400, 0))
        self.assertEqual((payment.data["repayments"][0]["principal_amount"], payment.data["repayments"][0]["interest_amount"]),
                         (200, expected_interest))
        self.assertEqual(self.bank.balance, 600 + expected_interest)
        summary = dashboard_summary(self.household)
        self.assertEqual((summary["monthly_income"], summary["monthly_expense"], summary["net_worth"]),
                         (expected_interest, 0, 1000 + expected_interest))
        self.assertEqual(Transaction.objects.filter(type="income", category__name="سود وام").aggregate(v=Sum("amount"))["v"], expected_interest)

    def test_borrowed_loan_interest_is_expense_only_when_paid(self):
        today = timezone.localdate()
        loan = self.create_loan("borrowed", principal=1000, start_date=str(today - timedelta(days=30)),
                                maturity_date=str(today + timedelta(days=30)), annual_interest_rate="24.00",
                                origination_account=self.bank.id)
        interest = loan["total_interest"]
        self.assertGreater(interest, 0)
        self.assertEqual(dashboard_summary(self.household)["monthly_expense"], 0)
        payment = self.repay_loan(loan["id"], interest + 100)
        self.assertEqual(payment.status_code, 201, payment.data)
        self.assertEqual((payment.data["remaining_principal"], payment.data["remaining_interest"]), (900, 0))
        summary = dashboard_summary(self.household)
        self.assertEqual((summary["monthly_income"], summary["monthly_expense"], summary["net_worth"]),
                         (0, interest, 1000 - interest))
        self.assertEqual(self.bank.balance, 2000 - interest - 100)

    def test_loan_schedule_overdue_and_validation(self):
        today = timezone.localdate()
        overdue = self.create_loan("borrowed", principal=100, start_date=str(today - timedelta(days=15)),
                                   first_due_date=str(today - timedelta(days=1)), installment_count=1)
        self.assertEqual(overdue["installments"][0]["status"], "overdue")
        self.assertEqual(self.repay_loan(overdue["id"], 100).status_code, 201)
        self.assertEqual(self.client.get(f"/api/loans/{overdue['id']}/").data["installments"][0]["status"], "settled")
        foreign_account = Account.objects.create(household=self.other_household, name="Foreign", account_type="bank")
        bad = self.client.post("/api/loans/", {"direction": "lent", "party": "X", "original_principal": 100,
            "start_date": str(today), "origination_account": foreign_account.id}, format="json")
        self.assertEqual(bad.status_code, 400)
        bad = self.client.post("/api/loans/", {"direction": "lent", "party": "X", "original_principal": 1001,
            "start_date": str(today), "origination_account": self.bank.id}, format="json")
        self.assertEqual(bad.status_code, 400)
        bad = self.client.post("/api/loans/", {"direction": "borrowed", "party": "X", "original_principal": 100,
            "start_date": str(today), "annual_interest_rate": "10.00"}, format="json")
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(self.repay_loan(overdue["id"], 1, account=foreign_account).status_code, 400)
        other_client = APIClient()
        other_client.force_authenticate(self.other)
        self.assertEqual(other_client.get(f"/api/loans/{overdue['id']}/").status_code, 404)
        self.assertEqual(other_client.post(f"/api/loans/{overdue['id']}/repay/", {}, format="json").status_code, 404)

    def test_insights_actual_cash_range_categories_and_obligations(self):
        today = timezone.localdate()
        start = today - timedelta(days=10)
        previous = start - timedelta(days=1)
        self.add_transaction("income", 400, destination=self.bank, category=self.income)
        self.add_transaction("expense", 120, source=self.bank, category=self.expense)
        Transaction.objects.create(household=self.household, created_by=self.user, date=previous, type="expense",
                                   amount=80, source_account=self.bank, category=self.expense)
        self.create_obligation("bill", 200, category=self.expense.id, due_date=str(today - timedelta(days=1)))
        self.create_obligation("expected_payment", 300, category=self.income.id,
                               destination_account=self.bank.id, due_date=str(today + timedelta(days=5)))
        self.create_loan("borrowed", 100, origination_account=self.bank.id)
        response = self.client.get("/api/insights/", {"start": str(start), "end": str(today)})
        self.assertEqual(response.status_code, 200, response.data)
        report = response.data
        self.assertEqual(report["totals"], {"income": 400, "expense": 120, "net": 280})
        self.assertEqual(report["expense_categories"][0]["amount"], 120)
        self.assertEqual(report["expense_categories"][0]["previous_amount"], 80)
        self.assertEqual(report["due"]["totals"]["bill"]["overdue_amount"], 200)
        self.assertEqual(report["due"]["totals"]["expected_payment"]["upcoming_amount"], 300)
        self.assertEqual(report["loans"]["borrowed"]["principal"], 100)
        self.assertEqual(sum(row["income"] for row in report["monthly"]), 400)
        self.assertEqual(report["net_worth_history"][-1]["value"], dashboard_summary(self.household)["net_worth"])
        self.assertEqual(self.client.get("/api/insights/", {"start": str(today), "end": str(start)}).status_code, 400)
        other_client = APIClient()
        other_client.force_authenticate(self.other)
        other_report = other_client.get("/api/insights/", {"start": str(start), "end": str(today)}).data
        self.assertEqual(other_report["totals"], {"income": 0, "expense": 0, "net": 0})

    def test_insights_net_worth_includes_available_assets_gold_and_loan_principal(self):
        today = timezone.localdate()
        Asset.objects.create(household=self.household, name="Home item", asset_type="other", current_value=200)
        GoldPrice.objects.create(household=self.household, price_per_gram=300)
        GoldPurchase.objects.create(household=self.household, name="Ring", purchase_date=today,
                                    weight_grams=Decimal("2.000"), remaining_weight_grams=Decimal("2.000"), amount_paid=400)
        self.create_obligation("debt_owed", 100)
        self.create_loan("lent", 50)
        report = self.client.get("/api/insights/", {"start": str(today), "end": str(today)}).data
        self.assertEqual(report["net_worth_history"][-1]["value"], 1750)
        self.assertTrue(report["net_worth_estimated"])
        self.assertEqual(dashboard_summary(self.household)["net_worth"], 1750)
