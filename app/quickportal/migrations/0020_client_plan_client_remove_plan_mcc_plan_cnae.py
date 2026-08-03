import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def populate_existing_plans(apps, schema_editor):
    User = apps.get_model("auth", "User")
    Client = apps.get_model("quickportal", "Client")
    Plan = apps.get_model("quickportal", "Plan")

    user, _ = User.objects.get_or_create(
        username="legacy_plan_owner",
        defaults={"password": "!", "is_active": False},
    )
    client, _ = Client.objects.get_or_create(user=user)

    for plan in Plan.objects.select_related("mcc"):
        old_mcc = plan.mcc.mcc
        plan.client = client
        plan.cnae = old_mcc if old_mcc.isdigit() else "0"
        plan.save(update_fields=["client", "cnae"])


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("quickportal", "0019_network_alter_planfee_unique_together_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Client",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="client",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"db_table": "client"},
        ),
        migrations.AddField(
            model_name="plan",
            name="client",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="plans",
                to="quickportal.client",
            ),
        ),
        migrations.AddField(
            model_name="plan",
            name="cnae",
            field=models.CharField(
                max_length=20,
                null=True,
                validators=[
                    django.core.validators.RegexValidator(
                        "^\\d+$", "This field must contain only digits."
                    )
                ],
            ),
        ),
        migrations.RunPython(populate_existing_plans, migrations.RunPython.noop),
        migrations.RemoveField(model_name="plan", name="mcc"),
        migrations.AlterField(
            model_name="plan",
            name="client",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="plans",
                to="quickportal.client",
            ),
        ),
        migrations.AlterField(
            model_name="plan",
            name="cnae",
            field=models.CharField(
                max_length=20,
                validators=[
                    django.core.validators.RegexValidator(
                        "^\\d+$", "This field must contain only digits."
                    )
                ],
            ),
        ),
    ]
