import random
from collections import deque

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from matches.models import Kingdom, Match
from world.models import Chunk, Land, Province

NEIGHBOR_OFFSETS = (
    (1, 0),
    (1, -1),
    (0, -1),
    (-1, 0),
    (-1, 1),
    (0, 1),
)


def _chunk_seed(world_seed, chunk_q, chunk_r):
    seed = (world_seed or 0) ^ (chunk_q * 1000003) ^ (chunk_r * 2000003)
    return seed & 0xFFFFFFFFFFFFFFFF


def _tile_neighbors(tile):
    q, r = tile
    return [(q + dq, r + dr) for dq, dr in NEIGHBOR_OFFSETS]


def _grow_group(seed, unassigned, rng, target_size):
    group = []
    queue = deque([seed])
    seen = {seed}

    while queue and len(group) < target_size:
        current = queue.popleft()
        if current not in unassigned:
            continue
        unassigned.remove(current)
        group.append(current)
        neighbors = _tile_neighbors(current)
        rng.shuffle(neighbors)
        for neighbor in neighbors:
            if neighbor in unassigned and neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)

    return group


def _group_graph(node_ids, adjacency, rng, min_size, max_size):
    groups = []
    unassigned = set(node_ids)

    while unassigned:
        seed = rng.choice(tuple(unassigned))
        target_size = rng.randint(min_size, max_size)
        queue = deque([seed])
        seen = {seed}
        group = []

        while queue and len(group) < target_size:
            node = queue.popleft()
            if node not in unassigned:
                continue
            unassigned.remove(node)
            group.append(node)
            neighbors = list(adjacency.get(node, ()))
            rng.shuffle(neighbors)
            for neighbor in neighbors:
                if neighbor in unassigned and neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)

        groups.append(group)

    return groups


def _build_tile_adjacency(tile_to_province):
    adjacency = {}
    for (q, r), province_id in tile_to_province.items():
        adjacency.setdefault(province_id, set())
        for dq, dr in NEIGHBOR_OFFSETS:
            neighbor = (q + dq, r + dr)
            neighbor_province = tile_to_province.get(neighbor)
            if neighbor_province and neighbor_province != province_id:
                adjacency[province_id].add(neighbor_province)
    return adjacency


class Command(BaseCommand):
    help = "Generate procedural chunks, provinces, lands, and kingdoms for a match."

    def add_arguments(self, parser):
        parser.add_argument("--match", type=int, required=True)
        parser.add_argument("--chunk-q", type=int)
        parser.add_argument("--chunk-r", type=int)
        parser.add_argument("--from-q", type=int)
        parser.add_argument("--to-q", type=int)
        parser.add_argument("--from-r", type=int)
        parser.add_argument("--to-r", type=int)
        parser.add_argument("--size", type=int, default=64)
        parser.add_argument("--province-min", type=int, default=8)
        parser.add_argument("--province-max", type=int, default=24)
        parser.add_argument("--land-min", type=int, default=8)
        parser.add_argument("--land-max", type=int, default=24)
        parser.add_argument("--kingdom-min", type=int, default=1)
        parser.add_argument("--kingdom-max", type=int, default=4)

    def handle(self, *args, **options):
        match_id = options["match"]
        chunk_q = options["chunk_q"]
        chunk_r = options["chunk_r"]
        from_q = options["from_q"]
        to_q = options["to_q"]
        from_r = options["from_r"]
        to_r = options["to_r"]
        size = options["size"]
        province_min = options["province_min"]
        province_max = options["province_max"]
        land_min = options["land_min"]
        land_max = options["land_max"]
        kingdom_min = options["kingdom_min"]
        kingdom_max = options["kingdom_max"]

        if (chunk_q is None) != (chunk_r is None):
            raise CommandError("Provide both --chunk-q and --chunk-r.")

        if chunk_q is not None:
            chunk_coords = [(chunk_q, chunk_r)]
        else:
            if None in (from_q, to_q, from_r, to_r):
                raise CommandError("Provide --chunk-q/--chunk-r or a full range.")
            if from_q > to_q or from_r > to_r:
                raise CommandError("Range values must be ascending.")
            chunk_coords = [
                (q, r) for q in range(from_q, to_q + 1) for r in range(from_r, to_r + 1)
            ]

        match = Match.objects.filter(id=match_id).first()
        if not match:
            raise CommandError(f"Match {match_id} not found.")

        if match.world_seed is None:
            match.world_seed = random.SystemRandom().randrange(1, 2**63)
            match.save(update_fields=["world_seed"])
            self.stdout.write(
                self.style.SUCCESS(f"Assigned world_seed={match.world_seed} to match.")
            )

        for chunk_q, chunk_r in chunk_coords:
            if Chunk.objects.filter(match=match, chunk_q=chunk_q, chunk_r=chunk_r).exists():
                self.stdout.write(
                    self.style.WARNING(
                        f"Chunk {chunk_q},{chunk_r} already exists for match {match.id}."
                    )
                )
                continue

            seed = _chunk_seed(match.world_seed, chunk_q, chunk_r)
            rng = random.Random(seed)

            with transaction.atomic():
                chunk = self._generate_chunk(
                    match=match,
                    chunk_q=chunk_q,
                    chunk_r=chunk_r,
                    size=size,
                    rng=rng,
                    province_min=province_min,
                    province_max=province_max,
                    land_min=land_min,
                    land_max=land_max,
                    kingdom_min=kingdom_min,
                    kingdom_max=kingdom_max,
                    seed=seed,
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Generated chunk {chunk.chunk_q},{chunk.chunk_r} "
                    f"with {chunk.meta.get('province_count')} provinces, "
                    f"{chunk.meta.get('land_count')} lands, "
                    f"{chunk.meta.get('kingdom_count')} kingdoms."
                )
            )

    def _generate_chunk(
        self,
        match,
        chunk_q,
        chunk_r,
        size,
        rng,
        province_min,
        province_max,
        land_min,
        land_max,
        kingdom_min,
        kingdom_max,
        seed,
    ):
        base_q = chunk_q * size
        base_r = chunk_r * size
        tiles = [(base_q + dq, base_r + dr) for dq in range(size) for dr in range(size)]

        unassigned = set(tiles)
        tile_to_province = {}
        province_ids = []

        while unassigned:
            seed_tile = rng.choice(tuple(unassigned))
            target_size = rng.randint(province_min, province_max)
            group = _grow_group(seed_tile, unassigned, rng, target_size)
            if not group:
                continue
            province = Province.objects.create(match=match)
            province_ids.append(province.id)
            for tile in group:
                tile_to_province[tile] = province.id

        province_adjacency = _build_tile_adjacency(tile_to_province)
        province_groups = _group_graph(
            province_ids, province_adjacency, rng, land_min, land_max
        )

        land_ids = []
        province_to_land = {}
        for group in province_groups:
            land = Land.objects.create(match=match)
            land_ids.append(land.id)
            Province.objects.filter(id__in=group).update(land=land)
            for province_id in group:
                province_to_land[province_id] = land.id

        land_adjacency = {land_id: set() for land_id in land_ids}
        for province_id, neighbors in province_adjacency.items():
            land_id = province_to_land.get(province_id)
            if land_id is None:
                continue
            for neighbor_province_id in neighbors:
                neighbor_land_id = province_to_land.get(neighbor_province_id)
                if neighbor_land_id and neighbor_land_id != land_id:
                    land_adjacency[land_id].add(neighbor_land_id)

        land_groups = _group_graph(
            land_ids, land_adjacency, rng, kingdom_min, kingdom_max
        )

        kingdom_ids = []
        for group in land_groups:
            kingdom = Kingdom.objects.create(match=match)
            kingdom_ids.append(kingdom.id)
            Land.objects.filter(id__in=group).update(kingdom=kingdom)

        cells = [
            {
                "q": q,
                "r": r,
                "province_id": province_id,
                "terrain": "plains",
            }
            for (q, r), province_id in tile_to_province.items()
        ]

        meta = {
            "seed": seed,
            "province_count": len(province_ids),
            "land_count": len(land_ids),
            "kingdom_count": len(kingdom_ids),
        }

        return Chunk.objects.create(
            match=match,
            chunk_q=chunk_q,
            chunk_r=chunk_r,
            size=size,
            tiles={"cells": cells},
            meta=meta,
        )
