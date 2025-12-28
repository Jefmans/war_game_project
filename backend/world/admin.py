from django.contrib import admin

from .models import Chunk, Land, Province, Town


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = ("id", "match_id", "match", "chunk_q", "chunk_r", "size", "created_at")
    list_filter = ("match",)


@admin.register(Land)
class LandAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "match_id",
        "match",
        "name",
        "kingdom_id",
        "kingdom",
        "created_at",
    )
    list_filter = ("match", "kingdom")
    search_fields = ("name",)


@admin.register(Province)
class ProvinceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "match_id",
        "match",
        "name",
        "land_id",
        "land",
        "created_at",
    )
    list_filter = ("match", "land")
    search_fields = ("name",)


@admin.register(Town)
class TownAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "match_id",
        "match",
        "province_id",
        "province",
        "q",
        "r",
        "created_at",
    )
    list_filter = ("match",)
