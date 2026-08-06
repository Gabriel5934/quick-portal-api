import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import F, Q


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("quickportal", "0029_network_color"),
    ]

    operations = [
        migrations.AddField(
            model_name="business",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="children",
                to="quickportal.business",
            ),
        ),
        migrations.AddField(
            model_name="business",
            name="type",
            field=models.CharField(
                choices=[
                    ("RESELLER", "Reseller"),
                    ("RE_RESELLER", "Re-reseller"),
                    ("STORE", "Store"),
                ],
                default="STORE",
                max_length=20,
            ),
            preserve_default=False,
        ),
        migrations.CreateModel(
            name="BusinessMembership",
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
                    "role",
                    models.CharField(
                        choices=[
                            ("ADMIN", "Admin"),
                            ("MANAGER", "Manager"),
                            ("VIEWER", "Viewer"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to="quickportal.business",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="business_memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"db_table": "business_membership"},
        ),
        migrations.AddConstraint(
            model_name="business",
            constraint=models.CheckConstraint(
                condition=Q(parent__isnull=True) | ~Q(parent=F("id")),
                name="business_parent_not_self",
            ),
        ),
        migrations.AddConstraint(
            model_name="businessmembership",
            constraint=models.UniqueConstraint(
                fields=("user", "business"),
                name="unique_user_business_membership",
            ),
        ),
    ]
