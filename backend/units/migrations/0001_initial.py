from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("matches", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="UnitType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True)),
                ("max_hp", models.PositiveSmallIntegerField(default=10)),
                ("attack", models.PositiveSmallIntegerField(default=1)),
                ("defense", models.PositiveSmallIntegerField(default=1)),
                ("move_points", models.PositiveSmallIntegerField(default=1)),
            ],
        ),
        migrations.CreateModel(
            name="Unit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("q", models.IntegerField()),
                ("r", models.IntegerField()),
                ("hp", models.PositiveSmallIntegerField(default=10)),
                ("status", models.CharField(default="active", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "match",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="units",
                        to="matches.match",
                    ),
                ),
                (
                    "owner_kingdom",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="units",
                        to="matches.kingdom",
                    ),
                ),
                (
                    "unit_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="units",
                        to="units.unittype",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["match", "q", "r"], name="units_match_q_r_idx"),
                ],
            },
        ),
    ]
