from rest_framework import serializers
from .models import Account, Asset, Category, GoldPrice, GoldPurchase, Transaction

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
    class Meta:
        model = Transaction
        fields = ["id", "type", "amount", "date", "source_account", "destination_account", "category", "category_name", "source_name", "destination_name", "description", "created_at"]
        read_only_fields = ["created_at"]

    def validate(self, attrs):
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
        for account in (tx.source_account, tx.destination_account):
            if account and not account.active:
                raise serializers.ValidationError("حساب غیرفعال است.")
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
    class Meta:
        model = GoldPurchase
        fields = ["id", "purchase_date", "weight_grams", "amount_paid", "price_per_gram", "description", "created_at"]
        read_only_fields = ["created_at"]

    def get_price_per_gram(self, obj):
        return str(obj.amount_paid / obj.weight_grams) if obj.weight_grams else None

    def validate(self, attrs):
        if attrs.get("weight_grams", 0) <= 0 or attrs.get("amount_paid", 0) <= 0:
            raise serializers.ValidationError("وزن و مبلغ خرید باید بیشتر از صفر باشند.")
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
