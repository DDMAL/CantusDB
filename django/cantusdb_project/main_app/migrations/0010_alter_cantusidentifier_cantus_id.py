# Generated by Django 4.2.3 on 2023-11-10 14:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main_app", "0009_cantusidentifier"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cantusidentifier",
            name="cantus_id",
            field=models.CharField(max_length=15),
        ),
    ]
