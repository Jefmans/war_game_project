from django.contrib import admin

from .models import Unit, UnitType


@admin.register(UnitType)
class UnitTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "max_hp", "attack", "defense", "move_points")
    search_fields = ("name",)


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "match_id",
        "match",
        "owner_kingdom_id",
        "owner_kingdom",
        "unit_type_id",
        "unit_type",
        "q",
        "r",
        "hp",
        "status",
    )
    list_filter = ("match", "owner_kingdom", "status")
