from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework import status

from matches.models import Kingdom, Match, MatchParticipant, Order
from matches.resolution import build_turn_state, resolve_turn
from matches.serializers import (
    CreateMatchSerializer,
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
from units.models import Unit, UnitType
from world.pathfinding import find_path, hex_distance
from world.terrain import movement_cost
from world.tiles import TileCache
from world.models import Chunk, Land, Province, Town


def _advance_along_path(tile_cache, path, start_index, move_points):
    spent = 0
    index = start_index
    position = path[index]
    for next_index in range(start_index + 1, len(path)):
        tile = tile_cache.get_tile(*path[next_index])
        if tile is None:
            break
        step_cost = movement_cost(tile.get("terrain"))
        if step_cost is None or spent + step_cost > move_points:
            break
        spent += step_cost
        index = next_index
        position = path[next_index]
    return index, position


def _find_nearest_town_path(tile_cache, start, towns, province_owners, kingdom_id):
    if not towns:
        return None, None
    preferred = [
        town
        for town in towns
        if province_owners.get(town["province_id"]) != kingdom_id
    ]
    candidates = preferred or towns
    candidates = sorted(
        candidates,
        key=lambda town: hex_distance(start, (town["q"], town["r"])),
    )
    for town in candidates:
        goal = (town["q"], town["r"])
        path = find_path(tile_cache, start, goal)
        if path:
            return town, path
    return None, None


@extend_schema(
    request=CreateMatchSerializer,
    examples=[
        OpenApiExample(
            "Create match defaults",
            value={
                "name": "New Match",
                "max_players": 2,
                "turn_length_seconds": 10800,
                "start_now": True,
                "max_turn_override": 100,
                "chunk_size": 32,
                "participants": [
                    {
                        "username": "participant1",
                        "seat_order": 1,
                        "kingdom_name": "kingdom1",
                    },
                    {
                        "username": "participant2",
                        "seat_order": 2,
                        "kingdom_name": "kingdom2",
                    },
                ],
            },
            request_only=True,
        )
    ],
)
@api_view(["POST"])
def create_match(request):
    serializer = CreateMatchSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    data = dict(serializer.validated_data)
    participants_data = data.pop("participants", [])
    start_now = data.pop("start_now", False)
    create_chunk = data.pop("create_chunk", True)
    chunk_options = {
        "chunk_q": data.pop("chunk_q", 0),
        "chunk_r": data.pop("chunk_r", 0),
        "size": data.pop("chunk_size", 64),
        "province_min": data.pop("province_min", 8),
        "province_max": data.pop("province_max", 24),
        "land_min": data.pop("land_min", 8),
        "land_max": data.pop("land_max", 24),
        "kingdom_min": data.pop("kingdom_min", 1),
        "kingdom_max": data.pop("kingdom_max", 4),
    }

    if start_now and data.get("start_time") is None:
        data["start_time"] = timezone.now()

    user_model = get_user_model()
    participants_payload = []

    with transaction.atomic():
        match = Match.objects.create(**data)
        max_players = match.max_players

        if not participants_data:
            default_count = min(max_players, 2)
            participants_data = [
                {
                    "username": f"participant{index + 1}",
                    "seat_order": index + 1,
                    "kingdom_name": f"kingdom{index + 1}",
                }
                for index in range(default_count)
            ]
        used_seat_orders = set()
        used_user_ids = set()

        for entry in participants_data:
            seat_order = entry.get("seat_order")
            if seat_order is None:
                continue
            if seat_order > max_players:
                raise ValidationError(
                    {"participants": f"seat_order {seat_order} exceeds max_players"}
                )
            if seat_order in used_seat_orders:
                raise ValidationError(
                    {"participants": f"seat_order {seat_order} is duplicated"}
                )
            used_seat_orders.add(seat_order)

        next_seat = 1

        for entry in participants_data:
            seat_order = entry.get("seat_order")
            if seat_order is None:
                while next_seat in used_seat_orders:
                    next_seat += 1
                seat_order = next_seat
                used_seat_orders.add(seat_order)

            if seat_order > max_players:
                raise ValidationError(
                    {"participants": f"seat_order {seat_order} exceeds max_players"}
                )

            if entry.get("user_id"):
                user = user_model.objects.filter(id=entry["user_id"]).first()
                if not user:
                    raise ValidationError(
                        {"participants": f"user_id {entry['user_id']} not found"}
                    )
            else:
                username = entry.get("username")
                user = user_model.objects.filter(username=username).first()
                if not user:
                    user = user_model.objects.create_user(
                        username=username,
                        email=entry.get("email") or "",
                        password=None,
                    )

            if user.id in used_user_ids:
                raise ValidationError(
                    {"participants": f"user_id {user.id} is duplicated"}
                )
            used_user_ids.add(user.id)

            kingdom_name = entry.get("kingdom_name") or f"{user.username} Kingdom"
            kingdom = Kingdom.objects.create(match=match, name=kingdom_name)

            participant = MatchParticipant.objects.create(
                match=match,
                user=user,
                seat_order=seat_order,
                kingdom=kingdom,
                is_active=entry.get("is_active", True),
            )
            participants_payload.append(
                {
                    "id": participant.id,
                    "user_id": participant.user_id,
                    "seat_order": participant.seat_order,
                    "kingdom_id": participant.kingdom_id,
                    "is_active": participant.is_active,
                }
            )

        chunk = None
        if create_chunk:
            call_command(
                "generate_world",
                match=match.id,
                chunk_q=chunk_options["chunk_q"],
                chunk_r=chunk_options["chunk_r"],
                size=chunk_options["size"],
                province_min=chunk_options["province_min"],
                province_max=chunk_options["province_max"],
                land_min=chunk_options["land_min"],
                land_max=chunk_options["land_max"],
                kingdom_min=chunk_options["kingdom_min"],
                kingdom_max=chunk_options["kingdom_max"],
            )
            match.refresh_from_db(fields=["world_seed"])
            Land.objects.filter(match=match).update(kingdom=None)
            chunk = Chunk.objects.filter(
                match=match,
                chunk_q=chunk_options["chunk_q"],
                chunk_r=chunk_options["chunk_r"],
            ).first()
            kingdom_ids = [
                payload["kingdom_id"]
                for payload in participants_payload
                if payload.get("kingdom_id")
            ]
            if chunk and kingdom_ids:
                province_ids = []
                province_to_tiles = {}
                for cell in chunk.tiles.get("cells", []):
                    province_id = cell.get("province_id")
                    if province_id is None:
                        continue
                    province_ids.append(province_id)
                    province_to_tiles.setdefault(province_id, []).append(
                        (cell.get("q"), cell.get("r"))
                    )
                unique_provinces = list(dict.fromkeys(province_ids))
                if len(unique_provinces) < len(kingdom_ids):
                    raise ValidationError(
                        {"participants": "not enough provinces for starter ownership"}
                    )
                assignments = []
                for kingdom_id, province_id in zip(kingdom_ids, unique_provinces):
                    starter_land = Land.objects.create(
                        match=match,
                        kingdom_id=kingdom_id,
                    )
                    Province.objects.filter(
                        match=match,
                        id=province_id,
                    ).update(land=starter_land)
                    assignments.append((kingdom_id, province_id))

                unit_type, created = UnitType.objects.get_or_create(
                    name="Infantry",
                    defaults={
                        "max_hp": 10,
                        "attack": 1,
                        "defense": 1,
                        "move_points": 3,
                    },
                )
                if not created and unit_type.move_points != 3:
                    unit_type.move_points = 3
                    unit_type.save(update_fields=["move_points"])

                units_by_kingdom = {}
                for kingdom_id, province_id in assignments:
                    tiles = province_to_tiles.get(province_id) or []
                    if not tiles:
                        continue
                    q, r = tiles[0]
                    unit = Unit.objects.create(
                        match=match,
                        owner_kingdom_id=kingdom_id,
                        unit_type=unit_type,
                        q=q,
                        r=r,
                        hp=unit_type.max_hp,
                    )
                    units_by_kingdom[kingdom_id] = unit

                participants = get_participants(match)
                count = len(participants)
                if count and units_by_kingdom:
                    towns = list(
                        Town.objects.filter(match=match).values(
                            "province_id", "q", "r"
                        )
                    )
                    province_owners = {
                        row["id"]: row["land__kingdom_id"]
                        for row in Province.objects.filter(match=match).values(
                            "id", "land__kingdom_id"
                        )
                    }
                    tile_cache = TileCache(match)
                    max_turn = get_max_turn(match, now=timezone.now(), persist=False)
                    current_turn_number = match.last_resolved_turn + 1

                    for index, participant in enumerate(participants):
                        unit = units_by_kingdom.get(participant.kingdom_id)
                        if not unit:
                            continue
                        next_turn = next_turn_for_index(
                            current_turn_number, index, count
                        )
                        if next_turn is None:
                            continue
                        current_pos = (unit.q, unit.r)
                        path = None
                        target = None
                        path_index = 0
                        while next_turn <= max_turn:
                            if path is None or path_index >= len(path) - 1:
                                target, path = _find_nearest_town_path(
                                    tile_cache,
                                    current_pos,
                                    towns,
                                    province_owners,
                                    participant.kingdom_id,
                                )
                                path_index = 0

                            if target:
                                destination = (target["q"], target["r"])
                            else:
                                destination = current_pos

                            payload = {
                                "type": "move",
                                "unit_id": unit.id,
                                "to": {"q": destination[0], "r": destination[1]},
                            }
                            active_participant = participants[(next_turn - 1) % count]
                            turn = ensure_turn(match, next_turn, active_participant)
                            Order.objects.update_or_create(
                                turn=turn,
                                participant=participant,
                                defaults={"payload": payload},
                            )
                            if path:
                                path_index, current_pos = _advance_along_path(
                                    tile_cache,
                                    path,
                                    path_index,
                                    unit.unit_type.move_points,
                                )
                                if target and current_pos == destination:
                                    province_owners[target["province_id"]] = (
                                        participant.kingdom_id
                                    )
                                    target = None
                                    path = None
                                    path_index = 0
                            next_turn += count

        chunk_payload = None
        if create_chunk and chunk:
            chunk_payload = {
                "id": chunk.id,
                "chunk_q": chunk.chunk_q,
                "chunk_r": chunk.chunk_r,
                "size": chunk.size,
            }

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
                "world_seed": match.world_seed,
            },
            "chunk": chunk_payload,
            "participants": participants_payload,
        },
        status=status.HTTP_201_CREATED,
    )


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


@api_view(["POST"])
def resolve_until_max(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    participants = get_participants(match)
    if not participants:
        return Response(
            {"detail": "match has no participants"},
            status=status.HTTP_409_CONFLICT,
        )

    max_turn = get_max_turn(match, now=timezone.now(), persist=True)
    resolved = []

    while True:
        current_turn = get_current_turn(match)
        if current_turn.number > max_turn:
            break
        previous_resolved = match.last_resolved_turn
        result = resolve_turn(current_turn)
        match.refresh_from_db(fields=["last_resolved_turn"])
        resolved.append({"turn": current_turn.number, "result": result})
        if match.last_resolved_turn == previous_resolved:
            return Response(
                {
                    "detail": "turn could not be resolved",
                    "turn": current_turn.number,
                    "result": result,
                },
                status=status.HTTP_409_CONFLICT,
            )

    return Response(
        {
            "match_id": match.id,
            "max_turn": max_turn,
            "resolved_count": len(resolved),
            "resolved": resolved,
        }
    )


@api_view(["GET"])
def turn_state(request, match_id, turn_number):
    match = get_object_or_404(Match, id=match_id)
    active_participant = get_active_participant(match, turn_number)
    turn = ensure_turn(match, turn_number, active_participant)
    if turn.status != turn.STATUS_RESOLVED:
        return Response(
            {
                "match_id": match.id,
                "turn": turn.number,
                "status": turn.status,
                "resolved_at": turn.resolved_at,
                "state": build_turn_state(match),
            }
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
    land_ids = set()
    if province_ids:
        for province in Province.objects.filter(id__in=province_ids).values(
            "id", "land_id"
        ):
            province_to_land[str(province["id"])] = province["land_id"]
            if province["land_id"] is not None:
                land_ids.add(province["land_id"])
    land_to_kingdom = {}
    if land_ids:
        for land in Land.objects.filter(id__in=land_ids).values("id", "kingdom_id"):
            land_to_kingdom[str(land["id"])] = land["kingdom_id"]
    towns = []
    if province_ids:
        for town in Town.objects.filter(
            match_id=chunk.match_id, province_id__in=province_ids
        ).values("province_id", "q", "r"):
            province_id = town["province_id"]
            land_id = province_to_land.get(str(province_id))
            kingdom_id = (
                land_to_kingdom.get(str(land_id)) if land_id is not None else None
            )
            towns.append(
                {
                    "province_id": province_id,
                    "q": town["q"],
                    "r": town["r"],
                    "kingdom_id": kingdom_id,
                }
            )
    return Response(
        {
            "match_id": chunk.match_id,
            "chunk_q": chunk.chunk_q,
            "chunk_r": chunk.chunk_r,
            "size": chunk.size,
            "tiles": chunk.tiles,
            "meta": chunk.meta,
            "province_to_land": province_to_land,
            "land_to_kingdom": land_to_kingdom,
            "towns": towns,
        }
    )
