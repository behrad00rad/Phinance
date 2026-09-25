from django.contrib.auth import authenticate, login, logout
from django.db import transaction as db_transaction
from django.db.models import F
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.csrf import csrf_protect
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.serializers import ValidationError
from decimal import Decimal, ROUND_HALF_UP
from .models import Account, Asset, Category, GoldPrice, GoldPurchase, GoldSale, Household, Loan, LoanRepayment, Notification, Obligation, ObligationSettlement, Transaction
from .serializers import AccountSerializer, AssetSerializer, CategorySerializer, GoldPurchaseSerializer, GoldSaleSerializer, InsightsRangeSerializer, LoanSerializer, ObligationSerializer, RepayLoanSerializer, SettleObligationSerializer, TransactionSerializer
from .services import dashboard_summary, gold_summary
from .insights import default_insights_range, insights_summary
from .alerts import preferences_for, sync_alerts

DEFAULT_CATEGORIES = {"expense": ["خوراک", "خرید", "قبوض", "حمل و نقل", "درمان", "تفریح", "خانه", "سود وام", "سایر"],
                      "income": ["حقوق", "اجاره", "کسب و کار", "سرمایه‌گذاری", "سود وام", "سایر"]}

def household_for(request):
    household = request.user.households.order_by("id").first()
    if not household:
        household = Household.objects.create(name="خانواده من", owner=request.user)
        household.members.add(request.user)
        Category.objects.bulk_create([Category(household=household, name=name, type=kind)
                                      for kind, names in DEFAULT_CATEGORIES.items() for name in names])
    return household

@ensure_csrf_cookie
@api_view(["GET"])
@permission_classes([AllowAny])
def csrf(request):
    return Response({"ok": True})

@api_view(["POST"])
@permission_classes([AllowAny])
@csrf_protect
def sign_in(request):
    user = authenticate(request, username=request.data.get("username"), password=request.data.get("password"))
    if not user:
        return Response({"detail": "نام کاربری یا رمز عبور درست نیست."}, status=status.HTTP_400_BAD_REQUEST)
    login(request, user)
    household_for(request)
    return Response({"username": user.username})

@api_view(["POST"])
def sign_out(request):
    logout(request)
    return Response({"ok": True})

@api_view(["GET"])
def me(request):
    household = household_for(request)
    return Response({"username": request.user.username, "household": {"id": household.id, "name": household.name}})

ALERT_FIELDS = ("bills", "loans", "expected_income", "high_spending", "days_ahead")

@api_view(["GET", "PATCH"])
def alert_preferences(request):
    preference = preferences_for(request.user)
    if request.method == "PATCH":
        for field in ALERT_FIELDS:
            if field not in request.data:
                continue
            value = request.data[field]
            if field == "days_ahead":
                if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 90:
                    raise ValidationError({field: "بازه هشدار باید عددی بین ۰ تا ۹۰ روز باشد."})
            elif not isinstance(value, bool):
                raise ValidationError({field: "مقدار باید درست یا نادرست باشد."})
            setattr(preference, field, value)
        preference.save()
    return Response({field: getattr(preference, field) for field in ALERT_FIELDS})

@api_view(["GET"])
def notifications(request):
    household = household_for(request)
    sync_alerts(request.user, household)
    rows = Notification.objects.filter(user=request.user, household=household)[:100]
    return Response({"unread_count": Notification.objects.filter(user=request.user, household=household, read_at__isnull=True).count(),
                     "items": [{"id": row.id, "kind": row.kind, "title": row.title, "detail": row.detail,
                                "due_date": row.due_date, "created_at": row.created_at, "read": row.read_at is not None}
                               for row in rows]})

@api_view(["POST"])
def mark_notification_read(request, pk):
    item = get_object_or_404(Notification, pk=pk, user=request.user, household=household_for(request))
    if item.read_at is None:
        item.read_at = timezone.now()
        item.save(update_fields=["read_at"])
    return Response({"ok": True})

class HouseholdViewSet(viewsets.ViewSet):
    def list(self, request):
        h = household_for(request)
        return Response([{"id": h.id, "name": h.name}])

class HouseholdModelViewSet(viewsets.ModelViewSet):
    def get_household(self):
        return household_for(self.request)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["household"] = self.get_household()
        return context

    def get_queryset(self):
        return self.queryset.filter(household=self.get_household())

    def perform_create(self, serializer):
        serializer.save(household=self.get_household())

class AccountViewSet(HouseholdModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer

    def perform_destroy(self, instance):
        instance.active = False
        instance.save(update_fields=["active", "updated_at"])

class CategoryViewSet(HouseholdModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    http_method_names = ["get"]

class TransactionViewSet(HouseholdModelViewSet):
    queryset = Transaction.objects.select_related("category", "source_account", "destination_account").order_by("-date", "-id")
    serializer_class = TransactionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        kind = self.request.query_params.get("type")
        if kind in ("income", "expense", "transfer"):
            qs = qs.filter(type=kind)
        return qs

    @db_transaction.atomic
    def perform_create(self, serializer):
        data = serializer.validated_data
        source = data.get("source_account")
        if source:
            source = Account.objects.select_for_update().get(pk=source.pk)
            if source.balance < data["amount"]:
                raise ValidationError({"amount": "موجودی حساب کافی نیست."})
        serializer.save(household=self.get_household(), created_by=self.request.user)

    @db_transaction.atomic
    def perform_update(self, serializer):
        raise ValidationError("برای اصلاح تراکنش، آن را حذف و دوباره ثبت کنید.")

    def perform_destroy(self, instance):
        raise ValidationError("حذف تراکنش در این نسخه پشتیبانی نمی‌شود.")

class AssetViewSet(HouseholdModelViewSet):
    queryset = Asset.objects.all()
    serializer_class = AssetSerializer

class ObligationViewSet(HouseholdModelViewSet):
    queryset = Obligation.objects.select_related("destination_account", "category").prefetch_related(
        "settlements__transaction__source_account", "settlements__transaction__destination_account").order_by("due_date", "id")
    serializer_class = ObligationSerializer
    http_method_names = ["get", "post", "head", "options"]

    def perform_create(self, serializer):
        serializer.save(household=self.get_household(), created_by=self.request.user)

    @action(detail=True, methods=["post"])
    def settle(self, request, pk=None):
        obligation = self.get_object()
        serializer = SettleObligationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        amount = data["amount"]
        account = data.get("account") or obligation.destination_account
        if not account or account.household_id != obligation.household_id or not account.active:
            raise ValidationError({"account": "یک حساب فعال از خانواده خود انتخاب کنید."})

        with db_transaction.atomic():
            existing = ObligationSettlement.objects.select_related("transaction").filter(idempotency_key=data["idempotency_key"]).first()
            if existing:
                tx = existing.transaction
                if (existing.obligation_id != obligation.id or tx.amount != amount or tx.date != data["date"]
                        or (tx.destination_account_id or tx.source_account_id) != account.id):
                    raise ValidationError({"idempotency_key": "این شناسه برای پرداخت دیگری استفاده شده است."})
                return Response(self.get_serializer(self.get_object()).data)

            obligation = Obligation.objects.select_for_update().get(pk=obligation.pk, household=obligation.household)
            if amount > obligation.remaining_amount:
                raise ValidationError({"amount": "مبلغ از مانده بیشتر است."})
            account = Account.objects.select_for_update().get(pk=account.pk, household=obligation.household, active=True)
            incoming = obligation.kind in ("expected_payment", "debt_receivable")
            if not incoming and account.balance < amount:
                raise ValidationError({"amount": "موجودی حساب کافی نیست."})
            tx_type = {"expected_payment": "income", "bill": "expense", "debt_owed": "debt_payment",
                       "debt_receivable": "debt_receipt"}[obligation.kind]
            tx = Transaction(household=obligation.household, type=tx_type, amount=amount, date=data["date"],
                             source_account=None if incoming else account, destination_account=account if incoming else None,
                             category=obligation.category if obligation.kind in ("expected_payment", "bill") else None,
                             description=f"{obligation.get_kind_display()}: {obligation.counterparty}", created_by=request.user)
            tx.full_clean()
            updated = Obligation.objects.filter(pk=obligation.pk, settled_amount__lte=F("amount") - amount).update(
                settled_amount=F("settled_amount") + amount,
                status="settled" if amount == obligation.remaining_amount else "partial")
            if not updated:
                raise ValidationError({"amount": "مبلغ از مانده بیشتر است."})
            tx.save()
            ObligationSettlement.objects.create(obligation=obligation, transaction=tx, idempotency_key=data["idempotency_key"])
        return Response(self.get_serializer(self.get_object()).data, status=status.HTTP_201_CREATED)

class LoanViewSet(HouseholdModelViewSet):
    queryset = Loan.objects.select_related("origination_account").prefetch_related(
        "installments", "repayments__account").order_by("-start_date", "-id")
    serializer_class = LoanSerializer
    http_method_names = ["get", "post", "head", "options"]

    @db_transaction.atomic
    def perform_create(self, serializer):
        household = self.get_household()
        data = serializer.validated_data
        account = data.get("origination_account")
        if account:
            account = Account.objects.select_for_update().get(pk=account.pk, household=household, active=True)
            if data["direction"] == "lent" and account.balance < data["original_principal"]:
                raise ValidationError({"original_principal": "موجودی حساب برای پرداخت اصل وام کافی نیست."})
        loan = serializer.save(household=household, created_by=self.request.user, origination_account=account)
        if account:
            incoming = loan.direction == "borrowed"
            tx = Transaction(household=household, type="loan_borrowed" if incoming else "loan_lent",
                             amount=loan.original_principal, date=loan.start_date,
                             source_account=None if incoming else account,
                             destination_account=account if incoming else None,
                             description=f"اصل {loan.get_direction_display()}: {loan.party}", created_by=self.request.user)
            tx.full_clean()
            tx.save()
            loan.origination_transaction = tx
            loan.save(update_fields=["origination_transaction"])

    @action(detail=True, methods=["post"])
    def repay(self, request, pk=None):
        loan = self.get_object()
        serializer = RepayLoanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data["date"] > timezone.localdate():
            raise ValidationError({"date": "بازپرداخت آینده را در برنامه اقساط ثبت کنید."})
        account = data["account"]
        if account.household_id != loan.household_id or not account.active:
            raise ValidationError({"account": "یک حساب فعال از خانواده خود انتخاب کنید."})
        with db_transaction.atomic():
            existing = LoanRepayment.objects.filter(idempotency_key=data["idempotency_key"]).first()
            if existing:
                if (existing.loan_id != loan.id or existing.account_id != account.id or existing.date != data["date"]
                        or existing.principal_amount + existing.interest_amount != data["amount"]):
                    raise ValidationError({"idempotency_key": "این شناسه برای بازپرداخت دیگری استفاده شده است."})
                return Response(self.get_serializer(self.get_object()).data)
            loan = Loan.objects.select_for_update().get(pk=loan.pk, household=loan.household)
            amount = data["amount"]
            if amount > loan.remaining_balance:
                raise ValidationError({"amount": "مبلغ از مانده وام بیشتر است."})
            account = Account.objects.select_for_update().get(pk=account.pk, household=loan.household, active=True)
            incoming = loan.direction == "lent"
            if not incoming and account.balance < amount:
                raise ValidationError({"amount": "موجودی حساب کافی نیست."})
            interest_amount = min(amount, loan.remaining_interest)
            principal_amount = amount - interest_amount
            updated = Loan.objects.filter(pk=loan.pk,
                                          repaid_principal__lte=F("original_principal") - principal_amount,
                                          repaid_interest__lte=F("total_interest") - interest_amount).update(
                repaid_principal=F("repaid_principal") + principal_amount,
                repaid_interest=F("repaid_interest") + interest_amount)
            if not updated:
                raise ValidationError({"amount": "مبلغ از مانده وام بیشتر است."})
            principal_tx = interest_tx = None
            if principal_amount:
                principal_tx = Transaction(household=loan.household, type="debt_receipt" if incoming else "debt_payment",
                                           amount=principal_amount, date=data["date"],
                                           source_account=None if incoming else account,
                                           destination_account=account if incoming else None,
                                           description=f"بازپرداخت اصل وام: {loan.party}", created_by=request.user)
                principal_tx.full_clean()
                principal_tx.save()
            if interest_amount:
                category, _ = Category.objects.get_or_create(household=loan.household, name="سود وام",
                                                             type="income" if incoming else "expense")
                interest_tx = Transaction(household=loan.household, type="income" if incoming else "expense",
                                          amount=interest_amount, date=data["date"],
                                          source_account=None if incoming else account,
                                          destination_account=account if incoming else None, category=category,
                                          description=f"سود وام: {loan.party}", created_by=request.user)
                interest_tx.full_clean()
                interest_tx.save()
            LoanRepayment.objects.create(loan=loan, account=account, date=data["date"],
                                         principal_amount=principal_amount, interest_amount=interest_amount,
                                         principal_transaction=principal_tx, interest_transaction=interest_tx,
                                         idempotency_key=data["idempotency_key"])
        return Response(self.get_serializer(self.get_object()).data, status=status.HTTP_201_CREATED)

class GoldPurchaseViewSet(HouseholdModelViewSet):
    queryset = GoldPurchase.objects.order_by("-purchase_date", "-id")
    serializer_class = GoldPurchaseSerializer

class GoldSaleViewSet(HouseholdModelViewSet):
    queryset = GoldSale.objects.select_related("purchase").order_by("-sale_date", "-id")
    serializer_class = GoldSaleSerializer

    @db_transaction.atomic
    def perform_create(self, serializer):
        household = self.get_household()
        data = serializer.validated_data
        purchase = GoldPurchase.objects.select_for_update().get(pk=data["purchase"].pk, household=household)
        account = Account.objects.select_for_update().get(pk=data["account"].pk, household=household, active=True)
        weight = data["weight_grams"]
        if weight > purchase.remaining_weight_grams:
            raise ValidationError({"weight_grams": "وزن فروش از مقدار طلای باقی‌مانده بیشتر است."})
        amount = int((weight * data["price_per_gram"]).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        purchase.remaining_weight_grams -= weight
        purchase.save(update_fields=["remaining_weight_grams"])
        serializer.save(household=household, purchase=purchase, account=account, amount_received=amount)

    def perform_update(self, serializer):
        raise ValidationError("ثبت فروش جدید برای اصلاح فروش قبلی انجام دهید.")

    def perform_destroy(self, instance):
        raise ValidationError("حذف فروش پشتیبانی نمی‌شود.")

@api_view(["GET"])
def gold_price(request):
    household = household_for(request)
    obj, _ = GoldPrice.objects.get_or_create(household=household)
    return Response({"price_per_gram": obj.price_per_gram, "updated_at": obj.source_updated_at})

@api_view(["GET"])
def gold_totals(request):
    return Response(gold_summary(household_for(request)))

@api_view(["GET"])
def dashboard(request):
    return Response(dashboard_summary(household_for(request)))

@api_view(["GET"])
def insights(request):
    default_start, default_end = default_insights_range()
    serializer = InsightsRangeSerializer(data={"start": request.query_params.get("start", default_start.isoformat()),
                                              "end": request.query_params.get("end", default_end.isoformat())})
    serializer.is_valid(raise_exception=True)
    return Response(insights_summary(household_for(request), **serializer.validated_data))
