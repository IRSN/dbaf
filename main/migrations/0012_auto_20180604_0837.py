# Generated by Django 2.0.4 on 2018-06-04 08:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0011_coefficient_device_fk'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='coefficient',
            options={'ordering': ['start']},
        ),
        migrations.AddField(
            model_name='coefficient',
            name='start',
            field=models.DateTimeField(default=None),
            preserve_default=False,
        ),
    ]