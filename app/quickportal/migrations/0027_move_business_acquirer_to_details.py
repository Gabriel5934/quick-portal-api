import django.db.models.deletion
from django.db import migrations, models


def copy_business_acquirers(apps, schema_editor):
    BusinessDetails = apps.get_model("quickportal", "BusinessDetails")

    for details in BusinessDetails.objects.select_related("business").iterator():
        details.acquirer_id = details.business.acquirer_id
        if details.acquirer_id is not None:
            details.save(update_fields=["acquirer"])


class Migration(migrations.Migration):
    dependencies = [("quickportal", "0026_acquirer_and_cnae_foreign_keys")]

    operations = [
        migrations.AddField(
            model_name="businessdetails",
            name="acquirer",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="business_details",
                to="quickportal.acquirer",
            ),
        ),
        migrations.RunPython(copy_business_acquirers, migrations.RunPython.noop),
        migrations.RemoveField(model_name="business", name="acquirer"),
    ]
