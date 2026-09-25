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
        outgoing = Transaction.objects.filter(source_account=self).aggregate(v=Sum("amount"))["v"] or 0
        return self.opening_balance + incoming - outgoing

class Category(models.Model):
    TYPES = [("income", "درآمد"), ("expense", "هزینه")]
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=80)
    type = models.CharField(max_length=8, choices=TYPES)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["household", "name", "type"], name="unique_household_category")]

class Transaction(models.Model):
    TYPES = [("income", "درآمد"), ("expense", "هزینه"), ("transfer", "انتقال")]
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="transactions")
    type = models.CharField(max_length=8, choices=TYPES)
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
        for field in ("source_account", "destination_account", "category"):
            obj = getattr(self, field, None)
            if obj and obj.household_id != self.household_id:
                errors[field] = "این مورد متعلق به خانواده شما نیست."
        if self.category_id and self.type != "transfer" and self.category.type != self.type:
            errors["category"] = "نوع دسته با تراکنش سازگار نیست."
        if errors:
            raise ValidationError(errors)

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
    updated_at = models.DateTimeField(auto_now=True)

class GoldPurchase(models.Model):
    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="gold_purchases")
    purchase_date = models.DateField()
    weight_grams = models.DecimalField(max_digits=12, decimal_places=3)
    amount_paid = models.BigIntegerField()
    description = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.weight_grams is None or self.weight_grams <= Decimal("0") or self.amount_paid is None or self.amount_paid <= 0:
            raise ValidationError("وزن و مبلغ خرید باید بیشتر از صفر باشند.")
