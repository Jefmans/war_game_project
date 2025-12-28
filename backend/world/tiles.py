from world.models import Chunk

DEFAULT_CHUNK_SIZE = 64


class TileCache:
    def __init__(self, match):
        self.match = match
        self._chunk_cache = {}
        self._tile_index_cache = {}

    def _chunk_key(self, chunk_q, chunk_r):
        return f"{chunk_q},{chunk_r}"

    def _load_chunk(self, chunk_q, chunk_r):
        key = self._chunk_key(chunk_q, chunk_r)
        if key in self._chunk_cache:
            return self._chunk_cache[key]

        try:
            chunk = Chunk.objects.get(match=self.match, chunk_q=chunk_q, chunk_r=chunk_r)
        except Chunk.DoesNotExist:
            self._chunk_cache[key] = None
            self._tile_index_cache[key] = {}
            return None

        cells = chunk.tiles.get("cells", [])
        tile_index = {(cell["q"], cell["r"]): cell for cell in cells}
        self._chunk_cache[key] = chunk
        self._tile_index_cache[key] = tile_index
        return chunk

    def get_tile(self, q, r):
        chunk_q = q // DEFAULT_CHUNK_SIZE
        chunk_r = r // DEFAULT_CHUNK_SIZE
        key = self._chunk_key(chunk_q, chunk_r)
        self._load_chunk(chunk_q, chunk_r)
        return self._tile_index_cache.get(key, {}).get((q, r))
