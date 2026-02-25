from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("deployment", "0004_auto_20260202_1720"),
    ]

    operations = [
        migrations.AddField(
            model_name="deployment",
            name="start_worker",
            field=models.BooleanField(default=False),
        ),
    ]

