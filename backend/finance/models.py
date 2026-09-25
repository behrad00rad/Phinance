from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, Sum

class Household(models.Model):
    name = models.CharField(max_length=120)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_households")
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="households")
    created_at = models.DateTimeField(auto_now_add=True)

class Account(models.Model):
    TYPES = [("cash", "نقد"), ("bank", "بانک"), ("wallet", "کیف پول")]
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="accounts")
    name = models.CharField(max_length=120)
    account_type = models.CharField(max_length=12, choices=TYPES)
    opening_balance = models.BigIntegerField(default=0)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def balance(self):
        incoming = Transaction.objects.filter(destination_account=self).aggregate(v=Sum("amount"))["v"] or 0
        gold_sales = GoldSale.objects.filter(account=self).aggregate(v=Sum("amount_received"))["v"] or 0
        outgoing = Transaction.objects.filter(source_account=self).aggregate(v=Sum("amount"))["v"] or 0
        return self.opening_balance + incoming + gold_sales - outgoing

class Category(models.Model):
    TYPES = [("income", "درآمد"), ("expense", "هزینه")]
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=80)
    type = models.CharField(max_length=8, choices=TYPES)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["household", "name", "type"], name="unique_household_category")]

class Transaction(models.Model):
    TYPES = [("income", "درآمد"), ("expense", "هزینه"), ("transfer", "انتقال"),
             ("debt_receipt", "دریافت اصل طلب"), ("debt_payment", "پرداخت اصل بدهی"),
             ("loan_borrowed", "دریافت اصل وام"), ("loan_lent", "پرداخت اصل وام")]
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="transactions")
    type = models.CharField(max_length=16, choices=TYPES)
    amount = models.BigIntegerField()
    date = models.DateField()
    source_account = models.ForeignKey(Account, null=True, blank=True, on_delete=models.PROTECT, related_name="outgoing_transactions")
    destination_account = models.ForeignKey(Account, null=True, blank=True, on_delete=models.PROTECT, related_name="incoming_transactions")
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.PROTECT)
    description = models.CharField(max_length=250, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        errors = {}
        if self.amount is None or self.amount <= 0:
            errors["amount"] = "مبلغ باید بیشتر از صفر باشد."
        if self.type == "income" and (self.source_account_id or not self.destination_account_id or not self.category_id):
            errors["type"] = "درآمد به حساب مقصد و دسته نیاز دارد."
        if self.type == "expense" and (not self.source_account_id or self.destination_account_id or not self.category_id):
            errors["type"] = "هزینه به حساب مبدأ و دسته نیاز دارد."
        if self.type == "transfer" and (not self.source_account_id or not self.destination_account_id or self.category_id or self.source_account_id == self.destination_account_id):
            errors["type"] = "انتقال به دو حساب متفاوت نیاز دارد و دسته ندارد."
        if self.type in ("debt_receipt", "loan_borrowed") and (self.source_account_id or not self.destination_account_id or self.category_id):
            errors["type"] = "دریافت اصل وام یا طلب به حساب مقصد نیاز دارد و دسته ندارد."
        if self.type in ("debt_payment", "loan_lent") and (not self.source_account_id or self.destination_account_id or self.category_id):
            errors["type"] = "پرداخت اصل وام یا بدهی به حساب مبدأ نیاز دارد و دسته ندارد."
        if self.type not in dict(self.TYPES):
            errors["type"] = "نوع تراکنش نامعتبر است."
        for field in ("source_account", "destination_account", "category"):
            obj = getattr(self, field, None)
            if obj and obj.household_id != self.household_id:
                errors[field] = "این مورد متعلق به خانواده شما نیست."
        if self.category_id and self.type != "transfer" and self.category.type != self.type:
            errors["category"] = "نوع دسته با تراکنش سازگار نیست."
        if errors:
            raise ValidationError(errors)

class Obligation(models.Model):
    KINDS = [("expected_payment", "دریافت مورد انتظار"), ("bill", "قبض"),
             ("debt_owed", "بدهی خانواده"), ("debt_receivable", "طلب خانواده")]
    STATUSES = [("pending", "در انتظار"), ("partial", "بخشی تسویه شده"), ("settled", "تسویه شده")]
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="obligations")
    kind = models.CharField(max_length=20, choices=KINDS)
    counterparty = models.CharField(max_length=120)
    amount = models.BigIntegerField()
    settled_amount = models.BigIntegerField(default=0)
    due_date = models.DateField()
    destination_account = models.ForeignKey(Account, null=True, blank=True, on_delete=models.PROTECT, related_name="expected_payments")
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.PROTECT, related_name="obligations")
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=8, choices=STATUSES, default="pending")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="obligation_positive_amount"),
            models.CheckConstraint(condition=Q(settled_amount__gte=0) & Q(settled_amount__lte=models.F("amount")), name="obligation_valid_settled_amount"),
        ]

    @property
    def remaining_amount(self):
        return self.amount - self.settled_amount

    @property
    def is_overdue(self):
        from django.utils import timezone
        return self.remaining_amount > 0 and self.due_date < timezone.localdate()

class ObligationSettlement(models.Model):
    obligation = models.ForeignKey(Obligation, on_delete=models.PROTECT, related_name="settlements")
    transaction = models.OneToOneField(Transaction, on_delete=models.PROTECT, related_name="obligation_settlement")
    idempotency_key = models.UUIDField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Loan(models.Model):
    DIRECTIONS = [("borrowed", "وام گرفته‌شده"), ("lent", "وام داده‌شده")]
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="loans")
    direction = models.CharField(max_length=8, choices=DIRECTIONS)
    party = models.CharField(max_length=120)
    original_principal = models.BigIntegerField()
    start_date = models.DateField()
    maturity_date = models.DateField(null=True, blank=True)
    annual_interest_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    total_interest = models.BigIntegerField(default=0)
    repaid_principal = models.BigIntegerField(default=0)
    repaid_interest = models.BigIntegerField(default=0)
    origination_account = models.ForeignKey(Account, null=True, blank=True, on_delete=models.PROTECT, related_name="originated_loans")
    origination_transaction = models.OneToOneField(Transaction, null=True, blank=True, on_delete=models.PROTECT, related_name="originated_loan")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(original_principal__gt=0), name="loan_positive_principal"),
            models.CheckConstraint(condition=Q(repaid_principal__gte=0) & Q(repaid_principal__lte=models.F("original_principal")), name="loan_valid_repaid_principal"),
            models.CheckConstraint(condition=Q(total_interest__gte=0) & Q(repaid_interest__gte=0) & Q(repaid_interest__lte=models.F("total_interest")), name="loan_valid_interest"),
        ]

    @property
    def remaining_principal(self):
        return self.original_principal - self.repaid_principal

    @property
    def remaining_interest(self):
        return self.total_interest - self.repaid_interest

    @property
    def remaining_balance(self):
        return self.remaining_principal + self.remaining_interest

class LoanInstallment(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.PROTECT, related_name="installments")
    due_date = models.DateField()
    amount = models.BigIntegerField()
    class Meta:
        ordering = ["due_date", "id"]
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="loan_installment_positive")]

class LoanRepayment(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.PROTECT, related_name="repayments")
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    date = models.DateField()
    principal_amount = models.BigIntegerField(default=0)
    interest_amount = models.BigIntegerField(default=0)
    principal_transaction = models.OneToOneField(Transaction, null=True, blank=True, on_delete=models.PROTECT, related_name="loan_principal_repayment")
    interest_transaction = models.OneToOneField(Transaction, null=True, blank=True, on_delete=models.PROTECT, related_name="loan_interest_repayment")
    idempotency_key = models.UUIDField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "id"]
        constraints = [models.CheckConstraint(condition=Q(principal_amount__gte=0) & Q(interest_amount__gte=0) & (Q(principal_amount__gt=0) | Q(interest_amount__gt=0)), name="loan_repayment_positive")]

class AlertPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="alert_preference")
    bills = models.BooleanField(default=True)
    loans = models.BooleanField(default=True)
    expected_income = models.BooleanField(default=True)
    high_spending = models.BooleanField(default=True)
    days_ahead = models.PositiveSmallIntegerField(default=7)

class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="finance_notifications")
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="notifications")
    key = models.CharField(max_length=160)
    kind = models.CharField(max_length=24)
    title = models.CharField(max_length=160)
    detail = models.CharField(max_length=300)
    due_date = models.DateField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["user", "household", "key"], name="unique_user_household_alert")]

class Asset(models.Model):
    TYPES = [("property", "ملک"), ("vehicle", "خودرو"), ("investment", "سرمایه‌گذاری"), ("other", "سایر")]
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="assets")
    name = models.CharField(max_length=120)
    asset_type = models.CharField(max_length=12, choices=TYPES)
    acquisition_cost = models.BigIntegerField(default=0)
    current_value = models.BigIntegerField(default=0)
    purchase_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.acquisition_cost < 0 or self.current_value < 0:
            raise ValidationError("ارزش دارایی نمی‌تواند منفی باشد.")

class GoldPrice(models.Model):
    household = models.OneToOneField(Household, on_delete=models.CASCADE, related_name="gold_price")
    price_per_gram = models.BigIntegerField(default=0)
    source_updated_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

class GoldPurchase(models.Model):
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="gold_purchases")
    name = models.CharField(max_length=120, default="Gold")
    purchase_date = models.DateField()
    weight_grams = models.DecimalField(max_digits=12, decimal_places=3)
    remaining_weight_grams = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    amount_paid = models.BigIntegerField()
    description = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.weight_grams is None or self.weight_grams <= Decimal("0") or self.amount_paid is None or self.amount_paid <= 0:
            raise ValidationError("وزن و مبلغ خرید باید بیشتر از صفر باشند.")
        if self.remaining_weight_grams is None or self.remaining_weight_grams < 0 or self.remaining_weight_grams > self.weight_grams:
            raise ValidationError("وزن باقی‌مانده نامعتبر است.")

class GoldSale(models.Model):
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="gold_sales")
    purchase = models.ForeignKey(GoldPurchase, on_delete=models.PROTECT, related_name="sales")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="gold_sale_deposits")
    sale_date = models.DateField()
    weight_grams = models.DecimalField(max_digits=12, decimal_places=3)
    amount_received = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
