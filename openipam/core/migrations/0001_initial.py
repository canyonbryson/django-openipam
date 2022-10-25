# Generated by Django 2.2.4 on 2019-08-09 21:26

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="FeatureRequest",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("feature", "Feature"),
                            ("bug", "Bug"),
                            ("comment", "Comment"),
                        ],
                        max_length=255,
                        verbose_name="Request Type",
                    ),
                ),
                ("comment", models.TextField(verbose_name="Comment Details")),
                (
                    "submitted",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Date Submitted"
                    ),
                ),
                ("is_complete", models.BooleanField(default=False)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"db_table": "feature_requests", "ordering": ("-submitted",)},
        )
    ]
