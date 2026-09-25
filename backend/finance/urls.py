from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register("households", views.HouseholdViewSet, basename="households")
router.register("accounts", views.AccountViewSet)
router.register("categories", views.CategoryViewSet)
router.register("transactions", views.TransactionViewSet)
router.register("obligations", views.ObligationViewSet)
router.register("loans", views.LoanViewSet)
router.register("assets", views.AssetViewSet)
router.register("gold-purchases", views.GoldPurchaseViewSet)
router.register("gold-sales", views.GoldSaleViewSet)

urlpatterns = [
    path("auth/csrf/", views.csrf), path("auth/login/", views.sign_in), path("auth/logout/", views.sign_out),
    path("auth/me/", views.me), path("dashboard/", views.dashboard), path("insights/", views.insights),
    path("alert-preferences/", views.alert_preferences), path("notifications/", views.notifications),
    path("notifications/<int:pk>/read/", views.mark_notification_read), path("gold/summary/", views.gold_totals),
    path("gold/price/", views.gold_price), path("", include(router.urls)),
]
