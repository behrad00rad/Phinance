from rest_framework import serializers
from .models import Account, Asset, Category, Check, CheckClearing, GoldPrice, GoldPurchase, GoldSale, Loan, LoanInstallment, LoanRepayment, Obligation, ObligationSettlement, Transaction
from .loans import equal_installment_amounts, fixed_interest, monthly_due_dates
from django.utils import timezone

class AccountSerializer(serializers.ModelSerializer):
    balance = serializers.IntegerField(read_only=True)
    class Meta:
        model = Account
        fields = ["id", "name", "account_type", "opening_balance", "balance", "description", "active", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def validate_opening_balance(self, value):
        if value < 0:
            raise serializers.ValidationError("موجودی اولیه نمی‌تواند منفی باشد.")
        return value

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "type"]

class TransactionSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    source_name = serializers.CharField(source="source_account.name", read_only=True)
    destination_name = serializers.CharField(source="destination_account.name", read_only=True)
    is_linked = serializers.SerializerMethodField()
    class Meta:
        model = Transaction
        fields = ["id", "type", "amount", "date", "source_account", "destination_account", "category", "category_name", "source_name", "destination_name", "description", "is_linked", "created_at"]
        read_only_fields = ["created_at"]

    def validate(self, attrs):
        if attrs.get("type", getattr(self.instance, "type", None)) in ("debt_receipt", "debt_payment", "loan_borrowed", "loan_lent"):
            raise serializers.ValidationError("جابه‌جایی اصل بدهی و وام را از بخش مربوط ثبت کنید.")
        household = self.context["household"]
        tx = Transaction(household=household, created_by=self.context["request"].user,
                         type=attrs.get("type", getattr(self.instance, "type", None)),
                         amount=attrs.get("amount", getattr(self.instance, "amount", None)),
                         date=attrs.get("date", getattr(self.instance, "date", None)),
                         source_account=attrs.get("source_account", getattr(self.instance, "source_account", None)),
                         destination_account=attrs.get("destination_account", getattr(self.instance, "destination_account", None)),
                         category=attrs.get("category", getattr(self.instance, "category", None)))
        from django.core.exceptions import ValidationError
        try:
            tx.clean()
        except ValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        for field in ("source_account", "destination_account"):
            account = getattr(tx, field)
            if account and not account.active and (not self.instance or account.pk != getattr(self.instance, f"{field}_id")):
                raise serializers.ValidationError("حساب غیرفعال است.")
        return attrs

    def get_is_linked(self, obj):
        return (hasattr(obj, "obligation_settlement") or hasattr(obj, "check_clearing")
                or hasattr(obj, "originated_loan") or hasattr(obj, "loan_principal_repayment")
                or hasattr(obj, "loan_interest_repayment"))

class ObligationSettlementSerializer(serializers.ModelSerializer):
    amount = serializers.IntegerField(source="transaction.amount", read_only=True)
    date = serializers.DateField(source="transaction.date", read_only=True)
    account_name = serializers.SerializerMethodField()
    account = serializers.SerializerMethodField()

    class Meta:
        model = ObligationSettlement
        fields = ["id", "amount", "date", "account", "account_name", "created_at"]

    def get_account(self, obj):
        return obj.transaction.destination_account_id or obj.transaction.source_account_id

    def get_account_name(self, obj):
        account = obj.transaction.destination_account or obj.transaction.source_account
        return account.name if account else ""

class ObligationSerializer(serializers.ModelSerializer):
    destination_account_name = serializers.CharField(source="destination_account.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    remaining_amount = serializers.IntegerField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    settlements = ObligationSettlementSerializer(many=True, read_only=True)

    class Meta:
        model = Obligation
        fields = ["id", "kind", "counterparty", "amount", "settled_amount", "remaining_amount", "due_date",
                  "destination_account", "destination_account_name", "category", "category_name", "notes",
                  "status", "is_overdue", "settlements", "created_at", "updated_at"]
        read_only_fields = ["settled_amount", "remaining_amount", "status", "is_overdue", "created_at", "updated_at"]
        extra_kwargs = {"amount": {"min_value": 1}}

    def validate_counterparty(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("نام شخص یا سازمان را وارد کنید.")
        return value

    def validate(self, attrs):
        household = self.context["household"]
        kind = attrs.get("kind", getattr(self.instance, "kind", None))
        account = attrs.get("destination_account", getattr(self.instance, "destination_account", None))
        category = attrs.get("category", getattr(self.instance, "category", None))
        if kind == "expected_payment":
            if not account or account.household_id != household.id or (not account.active and (not self.instance or account.pk != self.instance.destination_account_id)):
                raise serializers.ValidationError({"destination_account": "یک حساب فعال از خانواده خود انتخاب کنید."})
            if not category or category.household_id != household.id or category.type != "income":
                raise serializers.ValidationError({"category": "یک دسته درآمد از خانواده خود انتخاب کنید."})
        elif account:
            raise serializers.ValidationError({"destination_account": "حساب مقصد فقط برای دریافتی مورد انتظار است."})
        if kind == "bill":
            if not category or category.household_id != household.id or category.type != "expense":
                raise serializers.ValidationError({"category": "یک دسته هزینه از خانواده خود انتخاب کنید."})
        elif kind != "expected_payment" and category:
            raise serializers.ValidationError({"category": "اصل بدهی و طلب دسته درآمد یا هزینه ندارد."})
        return attrs

class SettleObligationSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=1)
    date = serializers.DateField()
    account = serializers.PrimaryKeyRelatedField(queryset=Account.objects.all(), required=False)
    idempotency_key = serializers.UUIDField()

class CheckClearingSerializer(serializers.ModelSerializer):
    amount = serializers.IntegerField(source="transaction.amount", read_only=True)
    date = serializers.DateField(source="transaction.date", read_only=True)

    class Meta:
        model = CheckClearing
        fields = ["id", "amount", "date", "created_at"]

class CheckSerializer(serializers.ModelSerializer):
    sender_account_name = serializers.CharField(source="sender_account.name", read_only=True)
    receiver_account_name = serializers.CharField(source="receiver_account.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    remaining_amount = serializers.IntegerField(read_only=True)
    status = serializers.CharField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    clearings = CheckClearingSerializer(many=True, read_only=True)

    class Meta:
        model = Check
        fields = ["id", "direction", "sender_name", "receiver_name", "counterparty_account", "sender_account", "sender_account_name",
                  "receiver_account", "receiver_account_name", "category", "category_name", "amount", "cleared_amount",
                  "remaining_amount", "due_date", "notes", "status", "is_overdue", "clearings", "created_at"]
        read_only_fields = ["cleared_amount", "created_at"]
        extra_kwargs = {"amount": {"min_value": 1}}

    def validate(self, attrs):
        household = self.context["household"]
        direction = attrs.get("direction", getattr(self.instance, "direction", None))
        for field in ("sender_name", "receiver_name"):
            value = attrs.get(field, getattr(self.instance, field, "")).strip()
            if not value:
                raise serializers.ValidationError({field: "نام فرستنده و گیرنده را وارد کنید."})
            if field in attrs: attrs[field] = value
        own = "receiver_account" if direction == "incoming" else "sender_account"
        other = "sender_account" if direction == "incoming" else "receiver_account"
        account = attrs.get(own, getattr(self.instance, own, None))
        current_account_id = getattr(self.instance, f"{own}_id", None)
        if not account or account.household_id != household.id or (not account.active and account.pk != current_account_id):
            raise serializers.ValidationError({own: "حساب فعال خانواده را انتخاب کنید."})
        if attrs.get(other, getattr(self.instance, other, None)):
            raise serializers.ValidationError({other: "حساب طرف مقابل در خانواده ثبت نمی‌شود."})
        category = attrs.get("category", getattr(self.instance, "category", None))
        if category.household_id != household.id or category.type != ("income" if direction == "incoming" else "expense"):
            raise serializers.ValidationError({"category": "دسته با جهت چک و خانواده سازگار نیست."})
        return attrs

class ClearCheckSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=1)
    date = serializers.DateField()
    idempotency_key = serializers.UUIDField()

class LoanRepaymentSerializer(serializers.ModelSerializer):
    amount = serializers.SerializerMethodField()
    account_name = serializers.CharField(source="account.name", read_only=True)

    class Meta:
        model = LoanRepayment
        fields = ["id", "date", "amount", "principal_amount", "interest_amount", "account", "account_name", "created_at"]

    def get_amount(self, obj):
        return obj.principal_amount + obj.interest_amount

class LoanSerializer(serializers.ModelSerializer):
    installment_count = serializers.IntegerField(write_only=True, min_value=1, max_value=120, required=False, allow_null=True)
    first_due_date = serializers.DateField(write_only=True, required=False, allow_null=True)
    remaining_principal = serializers.IntegerField(read_only=True)
    remaining_interest = serializers.IntegerField(read_only=True)
    remaining_balance = serializers.IntegerField(read_only=True)
    origination_account_name = serializers.CharField(source="origination_account.name", read_only=True)
    repayments = LoanRepaymentSerializer(many=True, read_only=True)
    installments = serializers.SerializerMethodField()

    class Meta:
        model = Loan
        fields = ["id", "direction", "party", "original_principal", "start_date", "maturity_date",
                  "annual_interest_rate", "total_interest", "repaid_principal", "repaid_interest",
                  "remaining_principal", "remaining_interest", "remaining_balance", "origination_account",
                  "origination_account_name", "notes", "installment_count", "first_due_date", "installments",
                  "repayments", "created_at"]
        read_only_fields = ["total_interest", "repaid_principal", "repaid_interest", "created_at"]
        extra_kwargs = {"original_principal": {"min_value": 1}}

    def get_installments(self, obj):
        paid = obj.repaid_principal + obj.repaid_interest
        today = timezone.localdate()
        result = []
        for installment in obj.installments.all():
            allocated = min(installment.amount, max(0, paid))
            paid -= allocated
            remaining = installment.amount - allocated
            result.append({"id": installment.id, "due_date": installment.due_date, "amount": installment.amount,
                           "paid_amount": allocated, "remaining_amount": remaining,
                           "status": "settled" if not remaining else "overdue" if installment.due_date < today else "upcoming"})
        return result

    def validate_party(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("نام شخص یا سازمان را وارد کنید.")
        return value

    def validate_annual_interest_rate(self, value):
        if value is not None and (value < 0 or value > 100):
            raise serializers.ValidationError("نرخ سود سالانه باید بین صفر و صد درصد باشد.")
        return value

    def validate(self, attrs):
        household = self.context["household"]
        account = attrs.get("origination_account", getattr(self.instance, "origination_account", None))
        if account and (account.household_id != household.id or (not account.active and (not self.instance or account.pk != self.instance.origination_account_id))):
            raise serializers.ValidationError({"origination_account": "یک حساب فعال از خانواده خود انتخاب کنید."})
        existing_dates = list(self.instance.installments.values_list("due_date", flat=True)) if self.instance else []
        count = attrs.get("installment_count", len(existing_dates) or None)
        first = attrs.get("first_due_date", existing_dates[0] if existing_dates else None)
        if bool(count) != bool(first):
            raise serializers.ValidationError({"first_due_date": "تعداد اقساط و تاریخ اولین قسط را با هم وارد کنید."})
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        if start > timezone.localdate():
            raise serializers.ValidationError({"start_date": "تاریخ شروع وام نمی‌تواند در آینده باشد."})
        maturity = attrs.get("maturity_date", getattr(self.instance, "maturity_date", None))
        dates = monthly_due_dates(first, count) if count else []
        if first and first <= start:
            raise serializers.ValidationError({"first_due_date": "اولین قسط باید بعد از تاریخ شروع باشد."})
        if dates:
            if maturity and maturity != dates[-1]:
                raise serializers.ValidationError({"maturity_date": "تاریخ پایان باید با آخرین قسط ماهانه برابر باشد."})
            maturity = dates[-1]
            attrs["maturity_date"] = maturity
        if maturity and maturity <= start:
            raise serializers.ValidationError({"maturity_date": "تاریخ پایان باید بعد از تاریخ شروع باشد."})
        rate = attrs.get("annual_interest_rate", getattr(self.instance, "annual_interest_rate", None))
        principal = attrs.get("original_principal", getattr(self.instance, "original_principal", None))
        if rate and not maturity:
            raise serializers.ValidationError({"maturity_date": "برای محاسبه سود، تاریخ پایان یا برنامه اقساط لازم است."})
        interest = fixed_interest(principal, rate, start, maturity)
        if count and principal + interest < count:
            raise serializers.ValidationError({"installment_count": "تعداد اقساط از مبلغ کل بیشتر است."})
        attrs["_dates"] = dates
        attrs["_interest"] = interest
        return attrs

    def create(self, validated_data):
        dates = validated_data.pop("_dates")
        interest = validated_data.pop("_interest")
        validated_data.pop("installment_count", None)
        validated_data.pop("first_due_date", None)
        loan = Loan.objects.create(total_interest=interest, **validated_data)
        if dates:
            amounts = equal_installment_amounts(loan.original_principal + interest, len(dates))
            LoanInstallment.objects.bulk_create([LoanInstallment(loan=loan, due_date=due, amount=amount)
                                                 for due, amount in zip(dates, amounts)])
        return loan

    def update(self, instance, validated_data):
        dates = validated_data.pop("_dates")
        interest = validated_data.pop("_interest")
        schedule_changed = "installment_count" in validated_data or "first_due_date" in validated_data
        validated_data.pop("installment_count", None)
        validated_data.pop("first_due_date", None)
        terms_changed = schedule_changed or any(field in validated_data for field in
                                                ("direction", "original_principal", "start_date", "maturity_date", "annual_interest_rate"))
        if terms_changed:
            validated_data["total_interest"] = interest
            instance.installments.all().delete()
            if dates:
                amounts = equal_installment_amounts(validated_data.get("original_principal", instance.original_principal) + interest, len(dates))
                LoanInstallment.objects.bulk_create([LoanInstallment(loan=instance, due_date=due, amount=amount)
                                                     for due, amount in zip(dates, amounts)])
        return super().update(instance, validated_data)

class RepayLoanSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=1)
    date = serializers.DateField()
    account = serializers.PrimaryKeyRelatedField(queryset=Account.objects.all())
    idempotency_key = serializers.UUIDField()

class InsightsRangeSerializer(serializers.Serializer):
    start = serializers.DateField()
    end = serializers.DateField()

    def validate(self, attrs):
        if attrs["start"] > attrs["end"]:
            raise serializers.ValidationError("تاریخ شروع باید پیش از تاریخ پایان باشد.")
        if attrs["end"] > timezone.localdate():
            raise serializers.ValidationError("گزارش انجام‌شده نمی‌تواند تاریخ پایان آینده داشته باشد.")
        if (attrs["end"] - attrs["start"]).days > 730:
            raise serializers.ValidationError("بازه گزارش حداکثر دو سال است.")
        return attrs

class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = ["id", "name", "asset_type", "acquisition_cost", "current_value", "purchase_date", "notes", "active", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        if attrs.get("acquisition_cost", 0) < 0 or attrs.get("current_value", 0) < 0:
            raise serializers.ValidationError("ارزش دارایی نمی‌تواند منفی باشد.")
        return attrs

class GoldPurchaseSerializer(serializers.ModelSerializer):
    price_per_gram = serializers.SerializerMethodField()
    invested_remaining = serializers.SerializerMethodField()
    current_value = serializers.SerializerMethodField()
    profit_loss = serializers.SerializerMethodField()
    class Meta:
        model = GoldPurchase
        fields = ["id", "name", "purchase_date", "weight_grams", "remaining_weight_grams", "amount_paid", "price_per_gram", "invested_remaining", "current_value", "profit_loss", "description", "created_at"]
        read_only_fields = ["created_at", "remaining_weight_grams", "price_per_gram", "invested_remaining", "current_value", "profit_loss"]

    def get_price_per_gram(self, obj):
        from decimal import Decimal
        return str(Decimal(obj.amount_paid) / obj.weight_grams) if obj.weight_grams else None

    def get_invested_remaining(self, obj):
        from decimal import Decimal
        return int(Decimal(obj.amount_paid) * obj.remaining_weight_grams / obj.weight_grams) if obj.weight_grams else 0

    def get_current_value(self, obj):
        from decimal import Decimal
        price = getattr(getattr(self.context.get("household"), "gold_price", None), "price_per_gram", 0)
        return int(obj.remaining_weight_grams * price)

    def get_profit_loss(self, obj):
        return self.get_current_value(obj) - self.get_invested_remaining(obj)

    def validate(self, attrs):
        if attrs.get("weight_grams", getattr(self.instance, "weight_grams", 0)) <= 0 or attrs.get("amount_paid", getattr(self.instance, "amount_paid", 0)) <= 0:
            raise serializers.ValidationError("وزن و مبلغ خرید باید بیشتر از صفر باشند.")
        if not attrs.get("name", getattr(self.instance, "name", "")).strip():
            raise serializers.ValidationError({"name": "نام طلا را وارد کنید."})
        return attrs

    def create(self, validated_data):
        validated_data["remaining_weight_grams"] = validated_data["weight_grams"]
        return super().create(validated_data)

class GoldSaleSerializer(serializers.ModelSerializer):
    purchase = serializers.PrimaryKeyRelatedField(queryset=GoldPurchase.objects.all())
    account = serializers.PrimaryKeyRelatedField(queryset=Account.objects.all())
    price_per_gram = serializers.IntegerField(write_only=True, min_value=1, required=False)
    holding_name = serializers.CharField(source="purchase.name", read_only=True)
    class Meta:
        model = GoldSale
        fields = ["id", "purchase", "holding_name", "account", "sale_date", "weight_grams", "price_per_gram", "amount_received", "created_at"]
        read_only_fields = ["amount_received", "created_at"]

    def create(self, validated_data):
        validated_data.pop("price_per_gram", None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("price_per_gram", None)
        return super().update(instance, validated_data)

    def validate(self, attrs):
        purchase = attrs.get("purchase", getattr(self.instance, "purchase", None))
        if purchase.household_id != self.context["household"].id:
            raise serializers.ValidationError({"purchase": "این طلا متعلق به خانواده شما نیست."})
        account = attrs.get("account", getattr(self.instance, "account", None))
        if account.household_id != self.context["household"].id or (not account.active and (not self.instance or account.pk != self.instance.account_id)):
            raise serializers.ValidationError({"account": "یک حساب فعال از خانواده خود انتخاب کنید."})
        weight = attrs.get("weight_grams", getattr(self.instance, "weight_grams", None))
        if weight is None or weight <= 0:
            raise serializers.ValidationError({"weight_grams": "وزن فروش باید بیشتر از صفر باشد."})
        available = purchase.remaining_weight_grams + (self.instance.weight_grams if self.instance and purchase.pk == self.instance.purchase_id else 0)
        if weight > available:
            raise serializers.ValidationError({"weight_grams": "وزن فروش از مقدار طلای باقی‌مانده بیشتر است."})
        if not self.instance and not attrs.get("price_per_gram"):
            raise serializers.ValidationError({"price_per_gram": "قیمت فروش هر گرم را وارد کنید."})
        if self.instance and weight != self.instance.weight_grams and not attrs.get("price_per_gram"):
            raise serializers.ValidationError({"price_per_gram": "برای تغییر وزن، قیمت فروش هر گرم را نیز وارد کنید."})
        return attrs

class GoldPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoldPrice
        fields = ["price_per_gram", "updated_at"]
        read_only_fields = ["updated_at"]

    def validate_price_per_gram(self, value):
        if value < 0:
            raise serializers.ValidationError("قیمت نمی‌تواند منفی باشد.")
        return value
