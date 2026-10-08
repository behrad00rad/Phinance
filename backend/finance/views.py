from django.contrib.auth import authenticate, login, logout
from django.db import transaction as db_transaction
from django.db.models import F
from django.db.models.deletion import ProtectedError
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
from uuid import uuid4
from .models import Account, Asset, Category, Check, CheckClearing, GoldPrice, GoldPurchase, GoldSale, Household, Loan, LoanRepayment, Notification, Obligation, ObligationSettlement, Transaction
from .serializers import AccountSerializer, AssetSerializer, CategorySerializer, CheckSerializer, ClearCheckSerializer, GoldPurchaseSerializer, GoldSaleSerializer, InsightsRangeSerializer, LoanSerializer, ObligationSerializer, RepayLoanSerializer, SettleObligationSerializer, TransactionSerializer
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

def ensure_nonnegative_balances(household):
    if any(account.balance < 0 for account in Account.objects.filter(household=household)):
        raise ValidationError("این تغییر موجودی یکی از حساب‌ها را منفی می‌کند. ابتدا پرداخت‌های وابسته را اصلاح کنید.")

def linked_transaction(transaction):
    return (ObligationSettlement.objects.filter(transaction=transaction).exists()
            or CheckClearing.objects.filter(transaction=transaction).exists()
            or Loan.objects.filter(origination_transaction=transaction).exists()
            or LoanRepayment.objects.filter(principal_transaction=transaction).exists()
            or LoanRepayment.objects.filter(interest_transaction=transaction).exists())

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

ALERT_FIELDS = ("bills", "loans", "checks", "expected_income", "high_spending", "days_ahead")

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

    @db_transaction.atomic
    def perform_update(self, serializer):
        serializer.save()
        ensure_nonnegative_balances(self.get_household())

    def perform_destroy(self, instance):
        instance.active = False
        instance.save(update_fields=["active", "updated_at"])

class CategoryViewSet(HouseholdModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def perform_update(self, serializer):
        instance = serializer.instance
        if "type" in serializer.validated_data and serializer.validated_data["type"] != instance.type:
            if (Transaction.objects.filter(category=instance).exists() or Obligation.objects.filter(category=instance).exists()
                    or Check.objects.filter(category=instance).exists()):
                raise ValidationError("دسته‌ای که در سوابق مالی استفاده شده، نمی‌تواند نوعش را تغییر دهد.")
        serializer.save()

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise ValidationError("این دسته در سوابق مالی استفاده شده و قابل حذف نیست.")

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
        if linked_transaction(serializer.instance):
            raise ValidationError("این تراکنش به پرداخت دیگری متصل است؛ آن را از بخش همان پرداخت اصلاح کنید.")
        serializer.save()
        ensure_nonnegative_balances(self.get_household())

    @db_transaction.atomic
    def perform_destroy(self, instance):
        if linked_transaction(instance):
            raise ValidationError("این تراکنش به پرداخت دیگری متصل است؛ آن را از بخش همان پرداخت حذف کنید.")
        instance.delete()
        ensure_nonnegative_balances(self.get_household())

class AssetViewSet(HouseholdModelViewSet):
    queryset = Asset.objects.all()
    serializer_class = AssetSerializer

class ObligationViewSet(HouseholdModelViewSet):
    queryset = Obligation.objects.select_related("destination_account", "category").prefetch_related(
        "settlements__transaction__source_account", "settlements__transaction__destination_account").order_by("due_date", "id")
    serializer_class = ObligationSerializer

    @db_transaction.atomic
    def perform_update(self, serializer):
        instance = serializer.instance
        if instance.settled_amount:
            locked = ("kind", "destination_account", "category")
            if any(field in serializer.validated_data and serializer.validated_data[field] != getattr(instance, field) for field in locked):
                raise ValidationError("پس از ثبت پرداخت، نوع و حساب و دسته قابل تغییر نیستند.")
            if serializer.validated_data.get("amount", instance.amount) < instance.settled_amount:
                raise ValidationError({"amount": "مبلغ کل نمی‌تواند از پرداخت‌های انجام‌شده کمتر باشد."})
        serializer.save()
        instance.status = "settled" if not instance.remaining_amount else "partial" if instance.settled_amount else "pending"
        instance.save(update_fields=["status"])
        if "counterparty" in serializer.validated_data:
            for settlement in instance.settlements.select_related("transaction"):
                settlement.transaction.description = f"{instance.get_kind_display()}: {instance.counterparty}"
                settlement.transaction.save(update_fields=["description"])

    @db_transaction.atomic
    def perform_destroy(self, instance):
        for settlement in instance.settlements.select_related("transaction"):
            transaction = settlement.transaction
            settlement.delete()
            transaction.delete()
        instance.delete()
        ensure_nonnegative_balances(self.get_household())

    @action(detail=True, methods=["patch", "delete"], url_path=r"settlements/(?P<settlement_id>[^/.]+)")
    def settlement_detail(self, request, pk=None, settlement_id=None):
        obligation = self.get_object()
        with db_transaction.atomic():
            settlement = get_object_or_404(ObligationSettlement.objects.select_related("transaction"), pk=settlement_id, obligation=obligation)
            tx = settlement.transaction
            old_amount = tx.amount
            if request.method == "DELETE":
                settlement.delete()
                tx.delete()
                obligation.settled_amount -= old_amount
            else:
                data = SettleObligationSerializer(data={**request.data, "idempotency_key": str(uuid4())})
                data.is_valid(raise_exception=True)
                values = data.validated_data
                account = values.get("account") or obligation.destination_account or tx.destination_account or tx.source_account
                if not account or account.household_id != obligation.household_id or not account.active:
                    raise ValidationError({"account": "حساب فعال خانواده را انتخاب کنید."})
                if obligation.settled_amount - old_amount + values["amount"] > obligation.amount:
                    raise ValidationError({"amount": "مبلغ از کل تعهد بیشتر است."})
                incoming = obligation.kind in ("expected_payment", "debt_receivable")
                tx.amount, tx.date = values["amount"], values["date"]
                tx.source_account = None if incoming else account
                tx.destination_account = account if incoming else None
                tx.full_clean()
                tx.save()
                obligation.settled_amount += values["amount"] - old_amount
            obligation.status = "settled" if not obligation.remaining_amount else "partial" if obligation.settled_amount else "pending"
            obligation.save(update_fields=["settled_amount", "status"])
            ensure_nonnegative_balances(obligation.household)
        return Response(self.get_serializer(self.get_object()).data) if request.method == "PATCH" else Response(status=status.HTTP_204_NO_CONTENT)

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

class CheckViewSet(HouseholdModelViewSet):
    queryset = Check.objects.select_related("sender_account", "receiver_account", "category").prefetch_related("clearings__transaction").order_by("due_date", "id")
    serializer_class = CheckSerializer

    @db_transaction.atomic
    def perform_update(self, serializer):
        instance = serializer.instance
        if instance.cleared_amount:
            locked = ("direction", "sender_account", "receiver_account", "category")
            if any(field in serializer.validated_data and serializer.validated_data[field] != getattr(instance, field) for field in locked):
                raise ValidationError("پس از تسویه، جهت و حساب و دسته چک قابل تغییر نیستند.")
            if serializer.validated_data.get("amount", instance.amount) < instance.cleared_amount:
                raise ValidationError({"amount": "مبلغ چک نمی‌تواند از تسویه‌های انجام‌شده کمتر باشد."})
        serializer.save()
        if "sender_name" in serializer.validated_data or "receiver_name" in serializer.validated_data:
            for clearing in instance.clearings.select_related("transaction"):
                clearing.transaction.description = f"تسویه چک: {instance.sender_name} ← {instance.receiver_name}"
                clearing.transaction.save(update_fields=["description"])

    @db_transaction.atomic
    def perform_destroy(self, instance):
        for clearing in instance.clearings.select_related("transaction"):
            transaction = clearing.transaction
            clearing.delete()
            transaction.delete()
        instance.delete()
        ensure_nonnegative_balances(self.get_household())

    @action(detail=True, methods=["patch", "delete"], url_path=r"clearings/(?P<clearing_id>[^/.]+)")
    def clearing_detail(self, request, pk=None, clearing_id=None):
        check = self.get_object()
        with db_transaction.atomic():
            clearing = get_object_or_404(CheckClearing.objects.select_related("transaction"), pk=clearing_id, payment_check=check)
            tx = clearing.transaction
            old_amount = tx.amount
            if request.method == "DELETE":
                clearing.delete()
                tx.delete()
                check.cleared_amount -= old_amount
            else:
                data = ClearCheckSerializer(data={**request.data, "idempotency_key": str(uuid4())})
                data.is_valid(raise_exception=True)
                values = data.validated_data
                if values["date"] > timezone.localdate():
                    raise ValidationError({"date": "تسویه آینده را پس از انجام آن ثبت کنید."})
                if check.cleared_amount - old_amount + values["amount"] > check.amount:
                    raise ValidationError({"amount": "مبلغ از کل چک بیشتر است."})
                tx.amount, tx.date = values["amount"], values["date"]
                tx.full_clean()
                tx.save()
                check.cleared_amount += values["amount"] - old_amount
            check.save(update_fields=["cleared_amount"])
            ensure_nonnegative_balances(check.household)
        return Response(self.get_serializer(self.get_object()).data) if request.method == "PATCH" else Response(status=status.HTTP_204_NO_CONTENT)

    def perform_create(self, serializer):
        serializer.save(household=self.get_household(), created_by=self.request.user)

    @action(detail=True, methods=["post"])
    def clear(self, request, pk=None):
        check = self.get_object()
        serializer = ClearCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data["date"] > timezone.localdate():
            raise ValidationError({"date": "تسویه آینده را پس از انجام آن ثبت کنید."})
        with db_transaction.atomic():
            existing = CheckClearing.objects.select_related("transaction").filter(idempotency_key=data["idempotency_key"]).first()
            if existing:
                tx = existing.transaction
                if existing.payment_check_id != check.id or tx.amount != data["amount"] or tx.date != data["date"]:
                    raise ValidationError({"idempotency_key": "این شناسه برای تسویه دیگری استفاده شده است."})
                return Response(self.get_serializer(self.get_object()).data)
            check = Check.objects.select_for_update().get(pk=check.pk, household=check.household)
            amount = data["amount"]
            if amount > check.remaining_amount:
                raise ValidationError({"amount": "مبلغ از مانده چک بیشتر است."})
            incoming = check.direction == "incoming"
            account = Account.objects.select_for_update().get(pk=(check.receiver_account_id if incoming else check.sender_account_id), household=check.household, active=True)
            if not incoming and account.balance < amount:
                raise ValidationError({"amount": "موجودی حساب کافی نیست."})
            tx = Transaction(household=check.household, type="income" if incoming else "expense",
                             amount=amount, date=data["date"], source_account=None if incoming else account,
                             destination_account=account if incoming else None, category=check.category,
                             description=f"تسویه چک: {check.sender_name} ← {check.receiver_name}", created_by=request.user)
            tx.full_clean()
            updated = Check.objects.filter(pk=check.pk, cleared_amount__lte=F("amount") - amount).update(
                cleared_amount=F("cleared_amount") + amount)
            if not updated:
                raise ValidationError({"amount": "مبلغ از مانده چک بیشتر است."})
            tx.save()
            CheckClearing.objects.create(payment_check=check, transaction=tx, idempotency_key=data["idempotency_key"])
        return Response(self.get_serializer(self.get_object()).data, status=status.HTTP_201_CREATED)

class LoanViewSet(HouseholdModelViewSet):
    queryset = Loan.objects.select_related("origination_account").prefetch_related(
        "installments", "repayments__account").order_by("-start_date", "-id")
    serializer_class = LoanSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    @db_transaction.atomic
    def perform_update(self, serializer):
        instance = serializer.instance
        # Financial terms and schedules are immutable once cash has moved.
        if instance.origination_transaction_id or instance.repayments.exists():
            locked = ("direction", "original_principal", "start_date", "maturity_date", "annual_interest_rate", "origination_account")
            if any(field in serializer.validated_data and serializer.validated_data[field] != getattr(instance, field) for field in locked):
                raise ValidationError("پس از جابه‌جایی پول، شرایط مالی وام قابل تغییر نیستند.")
            if "installment_count" in serializer.validated_data or "first_due_date" in serializer.validated_data:
                raise ValidationError("پس از جابه‌جایی پول، برنامه اقساط قابل تغییر نیست.")
        elif "origination_account" in serializer.validated_data and serializer.validated_data["origination_account"] != instance.origination_account:
            raise ValidationError("حساب جابه‌جایی اصل وام را پس از ثبت وام نمی‌توان تغییر داد.")
        serializer.save()
        if "party" in serializer.validated_data:
            if instance.origination_transaction_id:
                Transaction.objects.filter(pk=instance.origination_transaction_id).update(
                    description=f"اصل {instance.get_direction_display()}: {instance.party}")
            for repayment in instance.repayments.all():
                if repayment.principal_transaction_id:
                    Transaction.objects.filter(pk=repayment.principal_transaction_id).update(description=f"بازپرداخت اصل وام: {instance.party}")
                if repayment.interest_transaction_id:
                    Transaction.objects.filter(pk=repayment.interest_transaction_id).update(description=f"سود وام: {instance.party}")

    @db_transaction.atomic
    def perform_destroy(self, instance):
        for repayment in instance.repayments.all():
            principal, interest = repayment.principal_transaction, repayment.interest_transaction
            repayment.delete()
            if principal: principal.delete()
            if interest: interest.delete()
        instance.installments.all().delete()
        origination = instance.origination_transaction
        instance.delete()
        if origination: origination.delete()
        ensure_nonnegative_balances(self.get_household())

    @action(detail=True, methods=["patch", "delete"], url_path=r"repayments/(?P<repayment_id>[^/.]+)")
    def repayment_detail(self, request, pk=None, repayment_id=None):
        loan = self.get_object()
        with db_transaction.atomic():
            repayment = get_object_or_404(LoanRepayment, pk=repayment_id, loan=loan)
            if loan.repayments.order_by("-id").first().id != repayment.id:
                raise ValidationError("برای اصلاح سوابق، از آخرین بازپرداخت شروع کنید.")
            principal, interest = repayment.principal_transaction, repayment.interest_transaction
            loan.repaid_principal -= repayment.principal_amount
            loan.repaid_interest -= repayment.interest_amount
            loan.save(update_fields=["repaid_principal", "repaid_interest"])
            repayment.delete()
            if principal: principal.delete()
            if interest: interest.delete()
            if request.method == "PATCH":
                response = self.repay(request, pk=pk)
                ensure_nonnegative_balances(loan.household)
                response.status_code = status.HTTP_200_OK
                return response
            ensure_nonnegative_balances(loan.household)
        return Response(status=status.HTTP_204_NO_CONTENT)

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

    @db_transaction.atomic
    def perform_update(self, serializer):
        instance = serializer.instance
        new_weight = serializer.validated_data.get("weight_grams", instance.weight_grams)
        sold = instance.weight_grams - instance.remaining_weight_grams
        if new_weight < sold:
            raise ValidationError({"weight_grams": "وزن خرید نمی‌تواند از وزن فروخته‌شده کمتر باشد."})
        serializer.save(remaining_weight_grams=new_weight - sold)

    @db_transaction.atomic
    def perform_destroy(self, instance):
        instance.sales.all().delete()
        instance.delete()
        ensure_nonnegative_balances(self.get_household())

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

    @db_transaction.atomic
    def perform_update(self, serializer):
        instance = serializer.instance
        data = serializer.validated_data
        old_purchase = GoldPurchase.objects.select_for_update().get(pk=instance.purchase_id)
        new_purchase = GoldPurchase.objects.select_for_update().get(pk=data.get("purchase", instance.purchase).pk)
        weight = data.get("weight_grams", instance.weight_grams)
        available = new_purchase.remaining_weight_grams + (instance.weight_grams if new_purchase.pk == old_purchase.pk else 0)
        if weight > available:
            raise ValidationError({"weight_grams": "وزن فروش از طلای باقی‌مانده بیشتر است."})
        if old_purchase.pk == new_purchase.pk:
            old_purchase.remaining_weight_grams = available - weight
            old_purchase.save(update_fields=["remaining_weight_grams"])
        else:
            old_purchase.remaining_weight_grams += instance.weight_grams
            old_purchase.save(update_fields=["remaining_weight_grams"])
            new_purchase.remaining_weight_grams -= weight
            new_purchase.save(update_fields=["remaining_weight_grams"])
        price = data.get("price_per_gram")
        amount = int((weight * price).quantize(Decimal("1"), rounding=ROUND_HALF_UP)) if price else instance.amount_received
        serializer.save(amount_received=amount)
        ensure_nonnegative_balances(self.get_household())

    @db_transaction.atomic
    def perform_destroy(self, instance):
        purchase = GoldPurchase.objects.select_for_update().get(pk=instance.purchase_id)
        purchase.remaining_weight_grams += instance.weight_grams
        purchase.save(update_fields=["remaining_weight_grams"])
        instance.delete()
        ensure_nonnegative_balances(self.get_household())

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
