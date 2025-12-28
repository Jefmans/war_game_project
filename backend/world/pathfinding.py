import heapq

from world.terrain import movement_cost

NEIGHBOR_OFFSETS = (
    (1, 0),
    (1, -1),
    (0, -1),
    (-1, 0),
    (-1, 1),
    (0, 1),
)


def hex_distance(a, b):
    aq, ar = a
    bq, br = b
    return (abs(aq - bq) + abs(aq + ar - bq - br) + abs(ar - br)) // 2


def find_path(tile_cache, start, goal, blocked=None, max_nodes=20000):
    if start == goal:
        return [start]

    blocked = blocked or set()
    if start in blocked or goal in blocked:
        return None

    start_tile = tile_cache.get_tile(*start)
    goal_tile = tile_cache.get_tile(*goal)
    if start_tile is None or goal_tile is None:
        return None

    if movement_cost(goal_tile.get("terrain")) is None:
        return None

    open_heap = []
    counter = 0
    heapq.heappush(open_heap, (hex_distance(start, goal), counter, start))
    came_from = {}
    g_score = {start: 0}
    visited = 0

    while open_heap:
        _, _, current = heapq.heappop(open_heap)
        if current == goal:
            return _reconstruct_path(came_from, current)

        visited += 1
        if visited > max_nodes:
            break

        current_cost = g_score[current]
        cq, cr = current
        for dq, dr in NEIGHBOR_OFFSETS:
            neighbor = (cq + dq, cr + dr)
            if neighbor in blocked:
                continue
            tile = tile_cache.get_tile(*neighbor)
            if tile is None:
                continue
            step_cost = movement_cost(tile.get("terrain"))
            if step_cost is None:
                continue
            tentative = current_cost + step_cost
            if tentative < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative
                counter += 1
                priority = tentative + hex_distance(neighbor, goal)
                heapq.heappush(open_heap, (priority, counter, neighbor))

    return None


def _reconstruct_path(came_from, current):
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path
