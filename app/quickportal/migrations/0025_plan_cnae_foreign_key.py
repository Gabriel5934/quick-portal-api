import django.db.models.deletion
from django.db import migrations, models


def copy_plan_cnaes(apps, schema_editor):
    Plan = apps.get_model("quickportal", "Plan")
    Cnae = apps.get_model("quickportal", "Cnae")
    cnaes_by_code = dict(Cnae.objects.values_list("code", "pk"))
    missing_codes = set()

    for plan in Plan.objects.all().iterator():
        cnae_id = cnaes_by_code.get(plan.cnae)
        if cnae_id is None:
            missing_codes.add(plan.cnae)
            continue
        plan.cnae_relation_id = cnae_id
        plan.save(update_fields=["cnae_relation"])

    if missing_codes:
        codes = ", ".join(sorted(missing_codes))
        raise RuntimeError(
            "Cannot migrate Plan.cnae because these CNAE codes are not registered: "
            f"{codes}"
        )


class Migration(migrations.Migration):
    dependencies = [("quickportal", "0024_cnae_mcc_business_cnae")]

    operations = [
        migrations.AddField(
            model_name="plan",
            name="cnae_relation",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="plans",
                to="quickportal.cnae",
            ),
        ),
        migrations.RunPython(copy_plan_cnaes, migrations.RunPython.noop),
        migrations.RemoveField(model_name="plan", name="cnae"),
        migrations.RenameField(
            model_name="plan", old_name="cnae_relation", new_name="cnae"
        ),
        migrations.AlterField(
            model_name="plan",
            name="cnae",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="plans",
                to="quickportal.cnae",
            ),
        ),
    ]
