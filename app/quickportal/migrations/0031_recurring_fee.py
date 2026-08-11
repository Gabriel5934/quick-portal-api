import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import F, Q


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("quickportal", "0030_business_hierarchy_and_membership"),
    ]

    operations = [
        migrations.CreateModel(
            name="RecurringFee",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("setup_value", models.DecimalField(decimal_places=2, max_digits=15, validators=[django.core.validators.MinValueValidator(0)])),
                ("pricing_mode", models.CharField(choices=[("FIXED", "Fixed"), ("GOAL", "Goal-based")], max_length=10)),
                ("fee_value", models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True, validators=[django.core.validators.MinValueValidator(0)])),
                ("goal_amount", models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True, validators=[django.core.validators.MinValueValidator(0)])),
                ("value_below_goal", models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True, validators=[django.core.validators.MinValueValidator(0)])),
                ("value_at_or_above_goal", models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True, validators=[django.core.validators.MinValueValidator(0)])),
                ("recurrence_unit", models.CharField(choices=[("DAY", "Day"), ("WEEK", "Week"), ("MONTH", "Month"), ("YEAR", "Year")], max_length=10)),
                ("recurrence_interval", models.PositiveIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1)])),
                ("charge_rule", models.CharField(choices=[("INTERVAL", "Interval"), ("WEEKDAY", "Weekday"), ("DAY_OF_MONTH", "Day of month"), ("BUSINESS_DAY_OF_MONTH", "Business day of month"), ("DATE_OF_YEAR", "Date of year")], max_length=30)),
                ("charge_weekday", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("charge_day", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("charge_month", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("business_day_ordinal", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField(blank=True, null=True)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_recurring_fees", to=settings.AUTH_USER_MODEL)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="owned_recurring_fees", to="quickportal.business")),
            ],
            options={"db_table": "recurring_fee", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="RecurringFeeTarget",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("setup_charged_at", models.DateTimeField(blank=True, null=True)),
                ("next_charge_at", models.DateTimeField(blank=True, null=True)),
                ("recurring_fee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="target_links", to="quickportal.recurringfee")),
                ("target", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="recurring_fee_links", to="quickportal.business")),
            ],
            options={"db_table": "recurring_fee_target"},
        ),
        migrations.AddField(
            model_name="recurringfee",
            name="targets",
            field=models.ManyToManyField(related_name="targeted_recurring_fees", through="quickportal.RecurringFeeTarget", to="quickportal.business"),
        ),
        migrations.AddConstraint(
            model_name="recurringfee",
            constraint=models.CheckConstraint(condition=Q(recurrence_interval__gte=1), name="recurring_fee_positive_interval"),
        ),
        migrations.AddConstraint(
            model_name="recurringfee",
            constraint=models.CheckConstraint(condition=Q(end_date__isnull=True) | Q(end_date__gte=F("start_date")), name="recurring_fee_valid_dates"),
        ),
        migrations.AddConstraint(
            model_name="recurringfeetarget",
            constraint=models.UniqueConstraint(fields=("recurring_fee", "target"), name="unique_recurring_fee_target"),
        ),
    ]
