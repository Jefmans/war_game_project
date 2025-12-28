from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("world", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Town",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("q", models.IntegerField()),
                ("r", models.IntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "match",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="towns",
                        to="matches.match",
                    ),
                ),
                (
                    "province",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="town",
                        to="world.province",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["match", "q", "r"],
                        name="world_town_match_q_r_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=["match", "q", "r"],
                        name="unique_match_town_tile",
                    )
                ],
            },
        ),
    ]
