from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("quickportal", "0027_move_business_acquirer_to_details")]

    operations = [
        migrations.DeleteModel(name="CnaeMccMapping"),
        migrations.DeleteModel(name="MccFee"),
    ]
