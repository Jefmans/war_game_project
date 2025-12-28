from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Match",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(blank=True, max_length=100)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("active", "Active"), ("finished", "Finished")],
                        default="pending",
                        max_length=12,
                    ),
                ),
                ("max_players", models.PositiveSmallIntegerField(default=10)),
                ("turn_length_seconds", models.PositiveIntegerField(default=10800)),
                ("start_time", models.DateTimeField(blank=True, null=True)),
                ("last_resolved_turn", models.PositiveIntegerField(default=0)),
                ("world_seed", models.BigIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="Kingdom",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(blank=True, max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "match",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="kingdoms",
                        to="matches.match",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="MatchParticipant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("seat_order", models.PositiveSmallIntegerField()),
                ("is_active", models.BooleanField(default=True)),
                ("last_resolved_turn", models.PositiveIntegerField(default=0)),
                ("max_turn_override", models.PositiveIntegerField(blank=True, null=True)),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                (
                    "kingdom",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="participants",
                        to="matches.kingdom",
                    ),
                ),
                (
                    "match",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="participants",
                        to="matches.match",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="match_participations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=["match", "user"], name="unique_match_user"),
                    models.UniqueConstraint(fields=["match", "seat_order"], name="unique_match_seat_order"),
                ],
            },
        ),
        migrations.CreateModel(
            name="Turn",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.PositiveIntegerField()),
                ("history_index", models.PositiveIntegerField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("resolved", "Resolved"), ("expired", "Expired")],
                        default="pending",
                        max_length=10,
                    ),
                ),
                ("state", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                (
                    "match",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="turns",
                        to="matches.match",
                    ),
                ),
                (
                    "participant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="turns",
                        to="matches.matchparticipant",
                    ),
                ),
            ],
            options={
                "ordering": ["history_index", "number"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=["match", "participant", "number"],
                        name="unique_match_participant_turn",
                    ),
                    models.UniqueConstraint(
                        fields=["match", "history_index"],
                        name="unique_match_history_index",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "participant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="orders",
                        to="matches.matchparticipant",
                    ),
                ),
                (
                    "turn",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="orders",
                        to="matches.turn",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=["turn"], name="unique_turn_order"),
                ],
            },
        ),
    ]
