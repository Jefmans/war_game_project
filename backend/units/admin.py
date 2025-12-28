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
        "participant_id",
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
    list_select_related = ("match", "owner_kingdom", "unit_type")

    @admin.display(description="participant_id")
    def participant_id(self, obj):
        participant = obj.owner_kingdom.participants.first()
        return participant.id if participant else None
