from rest_framework import serializers

from matches.models import Match


class DestinationSerializer(serializers.Serializer):
    q = serializers.IntegerField()
    r = serializers.IntegerField()


class OrderPayloadSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["move", "pass"])
    unit_id = serializers.IntegerField(required=False)
    to = DestinationSerializer(required=False)

    def validate(self, data):
        if data.get("type") == "move":
            errors = {}
            if data.get("unit_id") is None:
                errors["unit_id"] = "This field is required for move orders."
            if data.get("to") is None:
                errors["to"] = "This field is required for move orders."
            if errors:
                raise serializers.ValidationError(errors)
        return data


class SubmitOrderSerializer(serializers.Serializer):
    participant_id = serializers.IntegerField()
    order = OrderPayloadSerializer()


class MaxTurnOverrideSerializer(serializers.Serializer):
    max_turn = serializers.IntegerField(min_value=1, allow_null=True)


class QueueOrdersSerializer(serializers.Serializer):
    participant_id = serializers.IntegerField()
    orders = OrderPayloadSerializer(many=True)


class ParticipantInputSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=False)
    username = serializers.CharField(required=False)
    email = serializers.EmailField(required=False, allow_blank=True)
    seat_order = serializers.IntegerField(required=False, min_value=1)
    kingdom_name = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False, default=True)

    def validate(self, data):
        if not data.get("user_id") and not data.get("username"):
            raise serializers.ValidationError(
                "Provide user_id or username for each participant."
            )
        return data


class CreateMatchSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=Match.STATUS_CHOICES, required=False)
    max_players = serializers.IntegerField(required=False, min_value=1, default=10)
    turn_length_seconds = serializers.IntegerField(
        required=False, min_value=10, default=10800
    )
    start_time = serializers.DateTimeField(required=False, allow_null=True)
    start_now = serializers.BooleanField(required=False, default=False)
    world_seed = serializers.IntegerField(required=False, allow_null=True)
    max_turn_override = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    participants = ParticipantInputSerializer(many=True, required=False)

    def validate(self, data):
        participants = data.get("participants", [])
        max_players = data.get("max_players", 10)
        if len(participants) > max_players:
            raise serializers.ValidationError(
                {"participants": "participants cannot exceed max_players"}
            )
        return data
