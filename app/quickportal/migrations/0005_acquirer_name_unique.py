from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quickportal', '0004_acquirer_posmodel'),
    ]

    operations = [
        migrations.AlterField(
            model_name='acquirer',
            name='name',
            field=models.CharField(max_length=100, unique=True),
        ),
    ]
