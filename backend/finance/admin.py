from django.contrib import admin

from .models import (
    Account,
    AlertPreference,
    Asset,
    Category,
    Check,
    CheckClearing,
    GoldPrice,
    GoldPurchase,
    GoldSale,
    Household,
    Loan,
    LoanInstallment,
    LoanRepayment,
    Notification,
    Obligation,
    ObligationSettlement,
    Transaction,
)


class HouseholdScopedAdmin(admin.ModelAdmin):
    list_filter = ("household",)
    search_fields = ("id",)


@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "owner", "created_at")
    search_fields = ("name", "owner__username")


@admin.register(Account)
class AccountAdmin(HouseholdScopedAdmin):
    list_display = ("name", "account_type", "opening_balance", "active", "household", "created_at")
    list_filter = ("household", "account_type", "active")
    search_fields = ("name", "description")


@admin.register(Category)
class CategoryAdmin(HouseholdScopedAdmin):
    list_display = ("name", "type", "household")
    list_filter = ("household", "type")
    search_fields = ("name",)


@admin.register(Transaction)
class TransactionAdmin(HouseholdScopedAdmin):
    list_display = ("date", "type", "amount", "description", "source_account", "destination_account", "household")
    list_filter = ("household", "type", "date")
    search_fields = ("description", "source_account__name", "destination_account__name")
    date_hierarchy = "date"


@admin.register(Obligation)
class ObligationAdmin(HouseholdScopedAdmin):
    list_display = ("counterparty", "kind", "amount", "settled_amount", "status", "due_date", "household")
    list_filter = ("household", "kind", "status", "due_date")
    search_fields = ("counterparty", "notes")
    date_hierarchy = "due_date"


@admin.register(ObligationSettlement)
class ObligationSettlementAdmin(admin.ModelAdmin):
    list_display = ("obligation", "transaction", "created_at")
    search_fields = ("obligation__counterparty", "idempotency_key")


@admin.register(Check)
class CheckAdmin(HouseholdScopedAdmin):
    list_display = ("direction", "sender_name", "receiver_name", "amount", "cleared_amount", "due_date", "household")
    list_filter = ("household", "direction", "due_date")
    search_fields = ("sender_name", "receiver_name", "counterparty_account", "notes")
    date_hierarchy = "due_date"


@admin.register(CheckClearing)
class CheckClearingAdmin(admin.ModelAdmin):
    list_display = ("payment_check", "transaction", "created_at")
    search_fields = ("payment_check__sender_name", "payment_check__receiver_name", "idempotency_key")


@admin.register(Loan)
class LoanAdmin(HouseholdScopedAdmin):
    list_display = ("party", "direction", "original_principal", "repaid_principal", "repaid_interest", "start_date", "household")
    list_filter = ("household", "direction", "start_date")
    search_fields = ("party", "notes")
    date_hierarchy = "start_date"


@admin.register(LoanInstallment)
class LoanInstallmentAdmin(admin.ModelAdmin):
    list_display = ("loan", "due_date", "amount")
    list_filter = ("due_date",)
    search_fields = ("loan__party",)
    date_hierarchy = "due_date"


@admin.register(LoanRepayment)
class LoanRepaymentAdmin(admin.ModelAdmin):
    list_display = ("loan", "date", "principal_amount", "interest_amount", "account", "created_at")
    list_filter = ("date",)
    search_fields = ("loan__party", "idempotency_key")
    date_hierarchy = "date"


@admin.register(Asset)
class AssetAdmin(HouseholdScopedAdmin):
    list_display = ("name", "asset_type", "acquisition_cost", "current_value", "active", "household")
    list_filter = ("household", "asset_type", "active")
    search_fields = ("name", "notes")


@admin.register(GoldPrice)
class GoldPriceAdmin(HouseholdScopedAdmin):
    list_display = ("household", "price_per_gram", "source_updated_at", "updated_at")


@admin.register(GoldPurchase)
class GoldPurchaseAdmin(HouseholdScopedAdmin):
    list_display = ("name", "purchase_date", "weight_grams", "remaining_weight_grams", "amount_paid", "household")
    list_filter = ("household", "purchase_date")
    search_fields = ("name", "description")
    date_hierarchy = "purchase_date"


@admin.register(GoldSale)
class GoldSaleAdmin(HouseholdScopedAdmin):
    list_display = ("purchase", "sale_date", "weight_grams", "amount_received", "account", "household")
    list_filter = ("household", "sale_date")
    search_fields = ("purchase__name",)
    date_hierarchy = "sale_date"


@admin.register(AlertPreference)
class AlertPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "bills", "loans", "checks", "expected_income", "high_spending", "days_ahead")
    search_fields = ("user__username",)


@admin.register(Notification)
class NotificationAdmin(HouseholdScopedAdmin):
    list_display = ("title", "kind", "user", "due_date", "read_at", "created_at", "household")
    list_filter = ("household", "kind", "read_at", "created_at")
    search_fields = ("title", "detail", "user__username")
    date_hierarchy = "created_at"
