from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0006_alertpreference_notification"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="alertpreference", name="checks", field=models.BooleanField(default=True),
        ),
        migrations.CreateModel(
            name="Check",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("direction", models.CharField(choices=[("incoming", "چک دریافتی"), ("outgoing", "چک پرداختی")], max_length=8)),
                ("sender_name", models.CharField(max_length=120)),
                ("receiver_name", models.CharField(max_length=120)),
                ("amount", models.BigIntegerField()),
                ("cleared_amount", models.BigIntegerField(default=0)),
                ("due_date", models.DateField()),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("category", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="checks", to="finance.category")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("household", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="checks", to="finance.household")),
                ("receiver_account", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="received_checks", to="finance.account")),
                ("sender_account", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="issued_checks", to="finance.account")),
            ],
            options={"constraints": [
                models.CheckConstraint(condition=models.Q(("amount__gt", 0)), name="check_positive_amount"),
                models.CheckConstraint(condition=models.Q(("cleared_amount__gte", 0), ("cleared_amount__lte", models.F("amount"))), name="check_valid_cleared"),
            ]},
        ),
        migrations.CreateModel(
            name="CheckClearing",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("idempotency_key", models.UUIDField(unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("payment_check", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="clearings", to="finance.check")),
                ("transaction", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="check_clearing", to="finance.transaction")),
            ],
        ),
    ]
