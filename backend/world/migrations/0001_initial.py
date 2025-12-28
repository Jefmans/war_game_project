from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("matches", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Land",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(blank=True, max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "kingdom",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="lands",
                        to="matches.kingdom",
                    ),
                ),
                (
                    "match",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lands",
                        to="matches.match",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Province",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(blank=True, max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "land",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="provinces",
                        to="world.land",
                    ),
                ),
                (
                    "match",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="provinces",
                        to="matches.match",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Chunk",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("chunk_q", models.IntegerField()),
                ("chunk_r", models.IntegerField()),
                ("size", models.PositiveSmallIntegerField(default=64)),
                ("tiles", models.JSONField(blank=True, default=dict)),
                ("meta", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "match",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chunks",
                        to="matches.match",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=["match", "chunk_q", "chunk_r"],
                        name="unique_match_chunk",
                    )
                ],
                "indexes": [
                    models.Index(fields=["match", "chunk_q", "chunk_r"]),
                ],
            },
        ),
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
                    models.Index(fields=["match", "q", "r"]),
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
