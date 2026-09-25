from django.contrib.auth import authenticate, login, logout
from django.db import transaction as db_transaction
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.csrf import csrf_protect
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.serializers import ValidationError
from .models import Account, Asset, Category, GoldPrice, GoldPurchase, Household, Transaction
from .serializers import AccountSerializer, AssetSerializer, CategorySerializer, GoldPriceSerializer, GoldPurchaseSerializer, TransactionSerializer
from .services import dashboard_summary, gold_summary

DEFAULT_CATEGORIES = {"expense": ["خوراک", "خرید", "قبوض", "حمل و نقل", "درمان", "تفریح", "خانه", "سایر"],
                      "income": ["حقوق", "اجاره", "کسب و کار", "سرمایه‌گذاری", "سایر"]}

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

class GoldPurchaseViewSet(HouseholdModelViewSet):
    queryset = GoldPurchase.objects.order_by("-purchase_date", "-id")
    serializer_class = GoldPurchaseSerializer

@api_view(["GET", "PUT"])
def gold_price(request):
    household = household_for(request)
    obj, _ = GoldPrice.objects.get_or_create(household=household)
    if request.method == "PUT":
        serializer = GoldPriceSerializer(obj, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
    return Response(GoldPriceSerializer(obj).data)

@api_view(["GET"])
def gold_totals(request):
    return Response(gold_summary(household_for(request)))

@api_view(["GET"])
def dashboard(request):
    return Response(dashboard_summary(household_for(request)))
