import django.db.models.deletion
from django.db import migrations, models


def copy_fee_cnaes(apps, schema_editor):
    Fee = apps.get_model("quickportal", "Fee")
    Cnae = apps.get_model("quickportal", "Cnae")
    cnaes_by_code = dict(Cnae.objects.values_list("code", "pk"))
    missing_codes = set()

    for fee in Fee.objects.all().iterator():
        cnae_id = cnaes_by_code.get(fee.cnae)
        if cnae_id is None:
            missing_codes.add(fee.cnae)
            continue
        fee.cnae_relation_id = cnae_id
        fee.save(update_fields=["cnae_relation"])

    if missing_codes:
        codes = ", ".join(sorted(missing_codes))
        raise RuntimeError(
            "Cannot migrate Fee.cnae because these CNAE codes are not registered: "
            f"{codes}"
        )


def infer_acquirers(apps, schema_editor):
    Plan = apps.get_model("quickportal", "Plan")
    Business = apps.get_model("quickportal", "Business")

    for plan in Plan.objects.all().iterator():
        acquirer_ids = set(
            plan.fees.values_list("fee__acquirer_id", flat=True).distinct()
        )
        if len(acquirer_ids) == 1:
            plan.acquirer_id = acquirer_ids.pop()
            plan.save(update_fields=["acquirer"])

    for business in Business.objects.filter(details__isnull=False).iterator():
        acquirer_id = business.details.plan.acquirer_id
        if acquirer_id is not None:
            business.acquirer_id = acquirer_id
            business.save(update_fields=["acquirer"])


class Migration(migrations.Migration):
    dependencies = [("quickportal", "0025_plan_cnae_foreign_key")]

    operations = [
        migrations.AddField(
            model_name="fee",
            name="cnae_relation",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="fees",
                to="quickportal.cnae",
            ),
        ),
        migrations.RunPython(copy_fee_cnaes, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="fee",
            name="unique_fee_dimensions",
        ),
        migrations.RemoveField(model_name="fee", name="cnae"),
        migrations.RenameField(
            model_name="fee", old_name="cnae_relation", new_name="cnae"
        ),
        migrations.AlterField(
            model_name="fee",
            name="cnae",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="fees",
                to="quickportal.cnae",
            ),
        ),
        migrations.AddConstraint(
            model_name="fee",
            constraint=models.UniqueConstraint(
                fields=("acquirer", "cnae", "network", "installments"),
                name="unique_fee_dimensions",
            ),
        ),
        migrations.AddField(
            model_name="plan",
            name="acquirer",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="plans",
                to="quickportal.acquirer",
            ),
        ),
        migrations.AddField(
            model_name="business",
            name="acquirer",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="businesses",
                to="quickportal.acquirer",
            ),
        ),
        migrations.RunPython(infer_acquirers, migrations.RunPython.noop),
    ]
