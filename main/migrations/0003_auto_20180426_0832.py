# Generated by Django 2.0.4 on 2018-04-26 08:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0002_auto_20180425_1202'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='DataLuilin',
            new_name='DataLiulin',
        ),
        migrations.AlterField(
            model_name='datafile',
            name='device',
            field=models.CharField(choices=[('DataEPDN2', 'EPDN2'), ('DataLiulin', 'Liulin')], max_length=256),
        ),
    ]