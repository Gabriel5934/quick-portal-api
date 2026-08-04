from django.core.validators import RegexValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("quickportal", "0028_delete_cnaemccmapping_delete_mccfee")]

    operations = [
        migrations.AddField(
            model_name="network",
            name="color",
            field=models.CharField(
                blank=True,
                max_length=7,
                validators=[
                    RegexValidator(
                        "^#[0-9a-fA-F]{6}$", "Enter a valid hex color."
                    )
                ],
            ),
        ),
    ]
