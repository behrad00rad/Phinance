from datetime import date
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from .models import Account, Asset, Category, GoldPrice, GoldPurchase, Household, Transaction
from .services import dashboard_summary, gold_summary

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
        GoldPurchase.objects.create(household=self.household, purchase_date=date.today(), weight_grams=Decimal("2.500"), amount_paid=500)
        GoldPrice.objects.create(household=self.household, price_per_gram=250)
        Asset.objects.create(household=self.household, name="Home", asset_type="property", current_value=2000)
        gold = gold_summary(self.household)
        self.assertEqual(gold["current_value"], 625)
        self.assertEqual(gold["profit_loss"], 125)
        self.assertEqual(dashboard_summary(self.household)["net_worth"], 3625)

    def test_login_requires_csrf(self):
        browser = APIClient(enforce_csrf_checks=True)
        self.assertEqual(browser.post("/api/auth/login/", {"username": "parent", "password": "strong-test-password"}, format="json").status_code, 403)
        browser.get("/api/auth/csrf/")
        token = browser.cookies["csrftoken"].value
        response = browser.post("/api/auth/login/", {"username": "parent", "password": "strong-test-password"}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
