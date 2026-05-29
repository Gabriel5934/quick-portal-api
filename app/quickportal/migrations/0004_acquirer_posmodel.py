from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('quickportal', '0003_promote_id_to_pk'),
    ]

    operations = [
        migrations.CreateModel(
            name='Acquirer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
            ],
            options={
                'db_table': 'acquirer',
            },
        ),
        migrations.CreateModel(
            name='PosModel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('model', models.CharField(max_length=100)),
                ('acquirer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pos_models', to='quickportal.acquirer')),
            ],
            options={
                'db_table': 'pos_model',
            },
        ),
    ]
