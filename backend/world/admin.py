from django.contrib import admin

from .models import Chunk, Land, Province


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = ("id", "match", "chunk_q", "chunk_r", "size", "created_at")
    list_filter = ("match",)


@admin.register(Land)
class LandAdmin(admin.ModelAdmin):
    list_display = ("id", "match", "name", "kingdom", "created_at")
    list_filter = ("match", "kingdom")
    search_fields = ("name",)


@admin.register(Province)
class ProvinceAdmin(admin.ModelAdmin):
    list_display = ("id", "match", "name", "land", "created_at")
    list_filter = ("match", "land")
    search_fields = ("name",)
