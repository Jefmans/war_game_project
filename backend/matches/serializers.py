from rest_framework import serializers


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
