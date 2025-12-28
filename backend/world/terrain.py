TERRAIN_COSTS = {
    "plains": 1,
    "forest": 2,
    "hills": 2,
    "swamp": 3,
    "water": None,
    "mountain": None,
}

DEFAULT_TERRAIN_COST = 1


def movement_cost(terrain):
    return TERRAIN_COSTS.get(terrain, DEFAULT_TERRAIN_COST)
