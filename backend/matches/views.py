from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from matches.models import Match, MatchParticipant, Order
from matches.resolution import resolve_turn
from matches.serializers import (
    MaxTurnOverrideSerializer,
    QueueOrdersSerializer,
    SubmitOrderSerializer,
)
from matches.services import (
    ensure_turn,
    get_active_participant,
    get_current_turn,
    get_max_turn,
    get_participant_index,
    get_participants,
    next_turn_for_index,
)
from world.models import Chunk, Province


@api_view(["GET"])
def match_state(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    current_turn_number = match.last_resolved_turn + 1
    active_participant = get_active_participant(match, current_turn_number)
    max_turn = get_max_turn(match, now=timezone.now(), persist=False)

    participants = list(
        match.participants.order_by("seat_order").values(
            "id", "user_id", "seat_order", "kingdom_id", "is_active"
        )
    )

    return Response(
        {
            "match": {
                "id": match.id,
                "name": match.name,
                "status": match.status,
                "max_players": match.max_players,
                "turn_length_seconds": match.turn_length_seconds,
                "start_time": match.start_time,
                "last_resolved_turn": match.last_resolved_turn,
                "max_turn_override": match.max_turn_override,
            },
            "current_turn": {
                "number": current_turn_number,
                "active_participant_id": active_participant.id if active_participant else None,
            },
            "max_turn": max_turn,
            "participants": participants,
        }
    )


@extend_schema(request=MaxTurnOverrideSerializer)
@api_view(["POST"])
def set_max_turn_override(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    serializer = MaxTurnOverrideSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    match.max_turn_override = serializer.validated_data.get("max_turn")
    match.save(update_fields=["max_turn_override"])

    effective_max_turn = get_max_turn(match, now=timezone.now(), persist=False)
    return Response(
        {
            "match_id": match.id,
            "max_turn_override": match.max_turn_override,
            "max_turn": effective_max_turn,
        }
    )


@extend_schema(request=QueueOrdersSerializer)
@api_view(["POST"])
def queue_orders(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    serializer = QueueOrdersSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    participant_id = serializer.validated_data["participant_id"]
    orders = serializer.validated_data["orders"]

    participant = get_object_or_404(
        MatchParticipant, match=match, id=participant_id, is_active=True
    )

    participants = get_participants(match)
    count = len(participants)
    if count == 0:
        return Response(
            {"detail": "match has no participants"},
            status=status.HTTP_409_CONFLICT,
        )

    index = get_participant_index(participants, participant.id)
    if index is None:
        return Response(
            {"detail": "participant not in match"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    max_turn = get_max_turn(match, now=timezone.now(), persist=True)
    current_turn_number = match.last_resolved_turn + 1
    next_turn = next_turn_for_index(current_turn_number, index, count)

    queued = []
    skipped = []

    for payload in orders:
        if next_turn is None or next_turn > max_turn:
            skipped.append({"order": payload, "reason": "beyond max_turn"})
            continue

        active_participant = participants[(next_turn - 1) % count]
        turn = ensure_turn(match, next_turn, active_participant)
        order, created = Order.objects.update_or_create(
            turn=turn,
            participant=participant,
            defaults={"payload": payload},
        )
        queued.append({"turn": turn.number, "order_id": order.id, "created": created})
        next_turn += count

    return Response(
        {
            "match_id": match.id,
            "max_turn": max_turn,
            "queued": queued,
            "skipped": skipped,
        }
    )


@api_view(["GET"])
def turn_state(request, match_id, turn_number):
    match = get_object_or_404(Match, id=match_id)
    turn = get_object_or_404(match.turns, number=turn_number)
    if turn.status != turn.STATUS_RESOLVED:
        return Response(
            {"detail": "turn not resolved"},
            status=status.HTTP_409_CONFLICT,
        )

    return Response(
        {
            "match_id": match.id,
            "turn": turn.number,
            "status": turn.status,
            "resolved_at": turn.resolved_at,
            "state": turn.state or {},
        }
    )


@extend_schema(request=SubmitOrderSerializer)
@api_view(["POST"])
def submit_order(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    serializer = SubmitOrderSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    participant_id = serializer.validated_data["participant_id"]
    payload = serializer.validated_data["order"]

    participant = get_object_or_404(
        MatchParticipant, match=match, id=participant_id, is_active=True
    )

    max_turn = get_max_turn(match, now=timezone.now(), persist=True)
    current_turn = get_current_turn(match)
    if current_turn.number > max_turn:
        return Response(
            {"detail": "turn not available yet", "max_turn": max_turn},
            status=status.HTTP_409_CONFLICT,
        )

    if current_turn.active_participant_id != participant.id:
        return Response(
            {
                "detail": "not active participant",
                "active_participant_id": current_turn.active_participant_id,
            },
            status=status.HTTP_409_CONFLICT,
        )

    order, _ = Order.objects.update_or_create(
        turn=current_turn,
        participant=participant,
        defaults={"payload": payload},
    )

    result = resolve_turn(current_turn)
    return Response(
        {
            "turn": current_turn.number,
            "resolved": True,
            "result": result,
            "next_turn": current_turn.number + 1,
        }
    )


@api_view(["GET"])
def chunk_detail(request, match_id, chunk_q, chunk_r):
    chunk = get_object_or_404(
        Chunk, match_id=match_id, chunk_q=chunk_q, chunk_r=chunk_r
    )
    cells = chunk.tiles.get("cells", [])
    province_ids = {
        cell.get("province_id")
        for cell in cells
        if cell.get("province_id") is not None
    }
    province_to_land = {}
    if province_ids:
        for province in Province.objects.filter(id__in=province_ids).values(
            "id", "land_id"
        ):
            province_to_land[str(province["id"])] = province["land_id"]
    return Response(
        {
            "match_id": chunk.match_id,
            "chunk_q": chunk.chunk_q,
            "chunk_r": chunk.chunk_r,
            "size": chunk.size,
            "tiles": chunk.tiles,
            "meta": chunk.meta,
            "province_to_land": province_to_land,
        }
    )
