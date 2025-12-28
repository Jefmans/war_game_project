from django.utils import timezone

from matches.models import Order, Turn
from units.models import Unit
from world.pathfinding import find_path
from world.terrain import movement_cost
from world.tiles import TileCache
from world.models import Land, Town


def resolve_turn(turn):
    match = turn.match
    if turn.active_participant is None:
        return {"status": "invalid", "reason": "no active participant"}
    order = Order.objects.filter(turn=turn, participant=turn.active_participant).first()
    if not order:
        order = Order.objects.create(
            turn=turn,
            participant=turn.active_participant,
            payload={"type": "pass"},
        )

    payload = order.payload or {}
    result = {"order_id": order.id, "actions": []}

    if payload.get("type") == "move":
        action_result = _resolve_move(match, payload)
        result["actions"].append(action_result)

    turn.status = Turn.STATUS_RESOLVED
    turn.resolved_at = timezone.now()
    turn.state = build_turn_state(match, result)
    turn.save(update_fields=["status", "resolved_at", "state"])

    if match.last_resolved_turn < turn.number:
        match.last_resolved_turn = turn.number
        match.save(update_fields=["last_resolved_turn"])

    return result


def build_turn_state(match, result=None):
    if result is None:
        result = {"status": "pending"}
    units = (
        Unit.objects.filter(match=match)
        .select_related("unit_type", "owner_kingdom")
        .order_by("id")
    )
    unit_payload = [
        {
            "id": unit.id,
            "type": unit.unit_type.name,
            "owner_kingdom_id": unit.owner_kingdom_id,
            "q": unit.q,
            "r": unit.r,
            "hp": unit.hp,
            "status": unit.status,
        }
        for unit in units
    ]
    return {
        "generated_at": timezone.now().isoformat(),
        "units": unit_payload,
        "result": result,
    }


def _resolve_move(match, payload):
    unit_id = payload.get("unit_id")
    target = payload.get("to") or {}
    target_q = target.get("q")
    target_r = target.get("r")

    if unit_id is None or target_q is None or target_r is None:
        return {"status": "invalid", "reason": "missing unit_id or destination"}

    unit = Unit.objects.filter(match=match, id=unit_id).select_related("unit_type").first()
    if not unit:
        return {"status": "invalid", "reason": "unit not found"}

    start = (unit.q, unit.r)
    goal = (int(target_q), int(target_r))

    tile_cache = TileCache(match)
    blocked = {(u.q, u.r) for u in Unit.objects.filter(match=match).exclude(id=unit.id)}

    path = find_path(tile_cache, start, goal, blocked=blocked)
    if not path:
        return {"status": "blocked", "reason": "no path"}

    move_points = unit.unit_type.move_points
    spent = 0
    new_pos = start

    for step in path[1:]:
        if step in blocked:
            break
        tile = tile_cache.get_tile(*step)
        if tile is None:
            break
        step_cost = movement_cost(tile.get("terrain"))
        if step_cost is None:
            break
        if spent + step_cost > move_points:
            break
        spent += step_cost
        new_pos = step

    capture = None
    if new_pos != start:
        unit.q, unit.r = new_pos
        unit.save(update_fields=["q", "r", "updated_at"])
        capture = _capture_town(match, unit, new_pos)

    return {
        "status": "moved" if new_pos != start else "stayed",
        "unit_id": unit.id,
        "from": {"q": start[0], "r": start[1]},
        "to": {"q": new_pos[0], "r": new_pos[1]},
        "spent": spent,
        "capture": capture,
    }


def _capture_town(match, unit, position):
    town = (
        Town.objects.select_related("province__land")
        .filter(match=match, q=position[0], r=position[1])
        .first()
    )
    if not town:
        return None

    province = town.province
    current_land = province.land
    if current_land and current_land.kingdom_id == unit.owner_kingdom_id:
        return {"status": "already_owned", "province_id": province.id}

    land = (
        Land.objects.filter(match=match, kingdom_id=unit.owner_kingdom_id)
        .order_by("id")
        .first()
    )
    if not land:
        land = Land.objects.create(match=match, kingdom_id=unit.owner_kingdom_id)

    province.land = land
    province.save(update_fields=["land"])

    return {
        "status": "captured",
        "province_id": province.id,
        "kingdom_id": unit.owner_kingdom_id,
    }
