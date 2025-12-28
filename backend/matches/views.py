from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from matches.models import Match, MatchParticipant, Order
from matches.resolution import resolve_turn
from matches.services import get_active_participant, get_current_turn, get_max_turn
from world.models import Chunk


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
            },
            "current_turn": {
                "number": current_turn_number,
                "active_participant_id": active_participant.id if active_participant else None,
            },
            "max_turn": max_turn,
            "participants": participants,
        }
    )


@api_view(["POST"])
def submit_order(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    data = request.data or {}
    participant_id = data.get("participant_id")
    payload = data.get("order") or {}

    if participant_id is None:
        return Response(
            {"detail": "participant_id is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

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
    return Response(
        {
            "match_id": chunk.match_id,
            "chunk_q": chunk.chunk_q,
            "chunk_r": chunk.chunk_r,
            "size": chunk.size,
            "tiles": chunk.tiles,
            "meta": chunk.meta,
        }
    )
