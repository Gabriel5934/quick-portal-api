import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def copy_business_cnaes(apps, schema_editor):
    Business = apps.get_model("quickportal", "Business")
    Cnae = apps.get_model("quickportal", "Cnae")
    cnaes_by_code = dict(Cnae.objects.values_list("code", "pk"))

    for business in Business.objects.exclude(cod_cnae="").iterator():
        business.cnae_relation_id = cnaes_by_code.get(business.cod_cnae)
        if business.cnae_relation_id is not None:
            business.save(update_fields=["cnae_relation"])


class Migration(migrations.Migration):
    dependencies = [("quickportal", "0023_remove_plan_client_delete_client")]

    operations = [
        migrations.AddField(
            model_name="cnae",
            name="mcc",
            field=models.CharField(
                default="0",
                max_length=20,
                validators=[
                    django.core.validators.RegexValidator(
                        "^\\d+$", "This field must contain only digits."
                    )
                ],
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="business",
            name="cnae_relation",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="businesses",
                to="quickportal.cnae",
            ),
        ),
        migrations.RunPython(copy_business_cnaes, migrations.RunPython.noop),
        migrations.RemoveField(model_name="business", name="cod_cnae"),
        migrations.RenameField(
            model_name="business", old_name="cnae_relation", new_name="cnae"
        ),
    ]
