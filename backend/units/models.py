from django.db import models


class UnitType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    max_hp = models.PositiveSmallIntegerField(default=10)
    attack = models.PositiveSmallIntegerField(default=1)
    defense = models.PositiveSmallIntegerField(default=1)
    move_points = models.PositiveSmallIntegerField(default=1)

    def __str__(self):
        return self.name


class Unit(models.Model):
    match = models.ForeignKey("matches.Match", on_delete=models.CASCADE, related_name="units")
    owner_kingdom = models.ForeignKey(
        "matches.Kingdom",
        on_delete=models.PROTECT,
        related_name="units",
    )
    unit_type = models.ForeignKey(UnitType, on_delete=models.PROTECT, related_name="units")
    q = models.IntegerField()
    r = models.IntegerField()
    hp = models.PositiveSmallIntegerField(default=10)
    status = models.CharField(max_length=20, default="active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["match", "q", "r"])]

    def __str__(self):
        return f"{self.unit_type} ({self.q},{self.r})"
