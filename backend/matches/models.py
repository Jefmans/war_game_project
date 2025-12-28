from django.conf import settings
from django.db import models


class Match(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_FINISHED = "finished"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_FINISHED, "Finished"),
    ]

    name = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING)
    max_players = models.PositiveSmallIntegerField(default=10)
    turn_length_seconds = models.PositiveIntegerField(default=10800)
    start_time = models.DateTimeField(null=True, blank=True)
    last_resolved_turn = models.PositiveIntegerField(default=0)
    max_turn_override = models.PositiveIntegerField(null=True, blank=True)
    world_seed = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name or f"Match {self.id}"


class Kingdom(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="kingdoms")
    name = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name or f"Kingdom {self.id}"


class MatchParticipant(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="match_participations",
    )
    seat_order = models.PositiveSmallIntegerField()
    kingdom = models.ForeignKey(
        Kingdom,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="participants",
    )
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["match", "user"], name="unique_match_user"),
            models.UniqueConstraint(
                fields=["match", "seat_order"],
                name="unique_match_seat_order",
            ),
        ]

    def __str__(self):
        return f"Participant {self.user_id} in {self.match_id}"


class Turn(models.Model):
    STATUS_PENDING = "pending"
    STATUS_RESOLVED = "resolved"
    STATUS_EXPIRED = "expired"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RESOLVED, "Resolved"),
        (STATUS_EXPIRED, "Expired"),
    ]

    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="turns")
    number = models.PositiveIntegerField()
    active_participant = models.ForeignKey(
        MatchParticipant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="active_turns",
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    state = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["match", "number"], name="unique_match_turn")
        ]
        ordering = ["number"]

    def __str__(self):
        return f"Turn {self.number} (Match {self.match_id})"


class Order(models.Model):
    turn = models.ForeignKey(Turn, on_delete=models.CASCADE, related_name="orders")
    participant = models.ForeignKey(
        MatchParticipant,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["turn", "participant"],
                name="unique_turn_participant",
            )
        ]

    def __str__(self):
        return f"Order {self.id} (Turn {self.turn_id})"
