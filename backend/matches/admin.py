from django.contrib import admin

from .models import Kingdom, Match, MatchParticipant, Order, Turn


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "status",
        "max_players",
        "turn_length_seconds",
        "start_time",
        "max_turn_override",
        "world_seed",
    )
    list_filter = ("status",)
    search_fields = ("name",)


@admin.register(Kingdom)
class KingdomAdmin(admin.ModelAdmin):
    list_display = ("id", "match_id", "match", "name", "created_at")
    list_filter = ("match",)
    search_fields = ("name",)


@admin.register(MatchParticipant)
class MatchParticipantAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "match_id",
        "match",
        "user_id",
        "user",
        "seat_order",
        "kingdom_id",
        "kingdom",
        "is_active",
    )
    list_filter = ("match", "kingdom", "is_active")


@admin.register(Turn)
class TurnAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "match_id",
        "match",
        "number",
        "status",
        "active_participant_id",
        "active_participant",
        "created_at",
    )
    list_filter = ("match", "status")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "turn_id", "turn", "participant_id", "participant", "created_at")
    list_filter = ("turn",)
