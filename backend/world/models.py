from django.db import models


class Land(models.Model):
    match = models.ForeignKey("matches.Match", on_delete=models.CASCADE, related_name="lands")
    kingdom = models.ForeignKey(
        "matches.Kingdom",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lands",
    )
    name = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name or f"Land {self.id}"


class Province(models.Model):
    match = models.ForeignKey("matches.Match", on_delete=models.CASCADE, related_name="provinces")
    land = models.ForeignKey(
        Land,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="provinces",
    )
    name = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name or f"Province {self.id}"


class Chunk(models.Model):
    match = models.ForeignKey("matches.Match", on_delete=models.CASCADE, related_name="chunks")
    chunk_q = models.IntegerField()
    chunk_r = models.IntegerField()
    size = models.PositiveSmallIntegerField(default=64)
    tiles = models.JSONField(default=dict, blank=True)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["match", "chunk_q", "chunk_r"],
                name="unique_match_chunk",
            )
        ]
        indexes = [models.Index(fields=["match", "chunk_q", "chunk_r"])]

    def __str__(self):
        return f"Chunk {self.chunk_q},{self.chunk_r}"
