import React, { useEffect, useMemo, useRef, useState } from "react";
import * as PIXI from "pixi.js";
import { getChunk, getMatchState, getTurnState } from "./api";
import infantryUrl from "./assets/infantry.svg";
import castleUrl from "./assets/castle.png";

const DEFAULT_MATCH_ID = Number(import.meta.env.VITE_MATCH_ID || 1);
const DEFAULT_CHUNK_Q = Number(import.meta.env.VITE_CHUNK_Q || 0);
const DEFAULT_CHUNK_R = Number(import.meta.env.VITE_CHUNK_R || 0);
const HEX_SIZE = 12;
const UNIT_ICON_SIZE = HEX_SIZE * 1.2;
const CASTLE_ICON_SIZE = HEX_SIZE * 1.5;
const ICON_BG_ALPHA = 0.75;
const ICON_BG_RADIUS = 0.65;
const TOWN_NEUTRAL_COLOR = 0xcbd5e1;
const UNIT_NEUTRAL_COLOR = 0xd1d5db;
const OWNED_TILE_ALPHA = 0.0;
const OWNED_BORDER_WIDTH = 2.6;
const OWNED_BORDER_ALPHA = 1;

const TERRAIN_COLORS = {
  plains: 0x5b8f64,
  forest: 0x2f5d3a,
  hills: 0x6d6a4a,
  swamp: 0x3e5c51,
  water: 0x2a4f6f,
  mountain: 0x5e5f66,
};

const KINGDOM_COLORS = [
  0xd97c5d,
  0x6fb1c9,
  0xc7b16a,
  0x7f9d72,
  0x8a7aa8,
  0xd1a15d,
];
const PLAYER_TILE_COLORS = [0x3b82f6, 0xef4444];
const TILE_STROKE = { width: 1, color: 0x1b232b, alpha: 0.6 };
const UNIT_STROKE = { width: 2, color: 0x131d25, alpha: 0.7 };
const LAND_STROKE = { width: 3.5, color: 0x2f2522, alpha: 0.85 };
const PROVINCE_STROKE = { width: 2.5, color: 0xe3c878, alpha: 0.8 };
const NEIGHBOR_OFFSETS = [
  [1, 0],
  [1, -1],
  [0, -1],
  [-1, 0],
  [-1, 1],
  [0, 1],
];
const EDGE_CORNER_INDEX = [
  [0, 1],
  [5, 0],
  [4, 5],
  [3, 4],
  [2, 3],
  [1, 2],
];

function axialToPixel(q, r, size) {
  const x = size * Math.sqrt(3) * (q + r / 2);
  const y = size * 1.5 * r;
  return { x, y };
}

function hexPoints(x, y, size) {
  const points = [];
  for (let i = 0; i < 6; i += 1) {
    const angle = (Math.PI / 180) * (60 * i - 30);
    points.push(x + size * Math.cos(angle), y + size * Math.sin(angle));
  }
  return points;
}

function drawHex(graphics, x, y, size, color, alpha = 1) {
  const points = hexPoints(x, y, size);
  graphics
    .poly(points)
    .fill({ color, alpha })
    .stroke(TILE_STROKE);
}

function fillHex(graphics, x, y, size, color, alpha = 1) {
  const points = hexPoints(x, y, size);
  graphics.poly(points).fill({ color, alpha });
}

function hexCorners(x, y, size) {
  const corners = [];
  for (let i = 0; i < 6; i += 1) {
    const angle = (Math.PI / 180) * (60 * i - 30);
    corners.push({
      x: x + size * Math.cos(angle),
      y: y + size * Math.sin(angle),
    });
  }
  return corners;
}

function colorForKingdom(id) {
  if (!id && id !== 0) {
    return 0xdddddd;
  }
  return KINGDOM_COLORS[id % KINGDOM_COLORS.length];
}

function addIconWithBackground(layer, texture, pos, size, tint) {
  const container = new PIXI.Container();
  container.position.set(pos.x, pos.y);

  const background = new PIXI.Graphics();
  background
    .circle(0, 0, size * ICON_BG_RADIUS)
    .fill({ color: tint, alpha: ICON_BG_ALPHA });

  const sprite = new PIXI.Sprite(texture);
  sprite.anchor.set(0.5);
  sprite.width = size;
  sprite.height = size;
  sprite.tint = tint;
  sprite.alpha = 0.95;

  container.addChild(background);
  container.addChild(sprite);
  layer.addChild(container);
}

export default function App() {
  const [matchId, setMatchId] = useState(DEFAULT_MATCH_ID);
  const [chunkQ, setChunkQ] = useState(DEFAULT_CHUNK_Q);
  const [chunkR, setChunkR] = useState(DEFAULT_CHUNK_R);
  const [turnNumber, setTurnNumber] = useState(1);
  const [lastResolved, setLastResolved] = useState(1);
  const [activeParticipant, setActiveParticipant] = useState(null);
  const [turnLength, setTurnLength] = useState(null);
  const [tiles, setTiles] = useState([]);
  const [provinceToLand, setProvinceToLand] = useState({});
  const [landToKingdom, setLandToKingdom] = useState({});
  const [towns, setTowns] = useState([]);
  const [kingdomColorMap, setKingdomColorMap] = useState({});
  const [turnState, setTurnState] = useState(null);
  const [showProvinceBorders, setShowProvinceBorders] = useState(true);
  const [showLandBorders, setShowLandBorders] = useState(true);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [iconTextures, setIconTextures] = useState(null);

  const containerRef = useRef(null);
  const appRef = useRef(null);
  const layersRef = useRef(null);
  const tilePositionsRef = useRef(new Map());

  const canGoPrev = turnNumber > 1;
  const canGoNext = turnNumber < lastResolved;

  const statusMessage = useMemo(() => {
    if (loading) {
      return "Loading map data...";
    }
    if (status) {
      return status;
    }
    return "Ready.";
  }, [loading, status]);

  useEffect(() => {
    let cancelled = false;

    const loadIcons = async () => {
      try {
        const [infantryTexture, castleTexture] = await Promise.all([
          PIXI.Assets.load(infantryUrl),
          PIXI.Assets.load(castleUrl),
        ]);
        if (!cancelled) {
          setIconTextures({
            infantry: infantryTexture,
            castle: castleTexture,
          });
        }
      } catch (error) {
        if (!cancelled) {
          setIconTextures(null);
        }
      }
    };

    loadIcons();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!containerRef.current || appRef.current) {
      return;
    }

    const app = new PIXI.Application();
    let disposed = false;
    let initialized = false;

    appRef.current = app;

    const init = async () => {
      await app.init({
        backgroundAlpha: 0,
        antialias: true,
        resizeTo: containerRef.current,
      });

      initialized = true;
      if (disposed) {
        app.destroy(true);
        return;
      }

      containerRef.current.appendChild(app.canvas);

      const root = new PIXI.Container();
      const tilesLayer = new PIXI.Graphics();
      const landBordersLayer = new PIXI.Graphics();
      const provinceBordersLayer = new PIXI.Graphics();
      const ownershipBordersLayer = new PIXI.Graphics();
      const townLayer = new PIXI.Container();
      const unitFallbackLayer = new PIXI.Graphics();
      const unitIconsLayer = new PIXI.Container();

      root.addChild(tilesLayer);
      root.addChild(landBordersLayer);
      root.addChild(provinceBordersLayer);
      root.addChild(ownershipBordersLayer);
      root.addChild(townLayer);
      root.addChild(unitFallbackLayer);
      root.addChild(unitIconsLayer);
      app.stage.addChild(root);

      layersRef.current = {
        root,
        tilesLayer,
        landBordersLayer,
        provinceBordersLayer,
        ownershipBordersLayer,
        townLayer,
        unitFallbackLayer,
        unitIconsLayer,
      };
    };

    init();

    return () => {
      disposed = true;
      if (initialized) {
        app.destroy(true);
      }
      appRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!tiles.length || !layersRef.current || !appRef.current) {
      return;
    }

    const { tilesLayer, landBordersLayer, provinceBordersLayer, ownershipBordersLayer, root } =
      layersRef.current;
    const positions = new Map();
    const tileIndex = new Map();
    const tileOwnerMap = new Map();
    tilesLayer.clear();
    landBordersLayer.clear();
    provinceBordersLayer.clear();
    ownershipBordersLayer.clear();

    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;

    tiles.forEach((cell) => {
      const { x, y } = axialToPixel(cell.q, cell.r, HEX_SIZE);
      const key = `${cell.q},${cell.r}`;
      positions.set(key, { x, y });
      tileIndex.set(key, cell);
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
      minY = Math.min(minY, y);
      maxY = Math.max(maxY, y);
    });

    tilePositionsRef.current = positions;

    const provinceToLandMap = provinceToLand || {};
    const landToKingdomMap = landToKingdom || {};
    const tileColorMap = kingdomColorMap || {};

    tiles.forEach((cell) => {
      const key = `${cell.q},${cell.r}`;
      const pos = positions.get(key);
      const provinceId = cell.province_id ?? null;
      const landId =
        provinceId !== null
          ? provinceToLandMap[String(provinceId)] ?? null
          : null;
      const kingdomId =
        landId !== null ? landToKingdomMap[String(landId)] ?? null : null;
      tileOwnerMap.set(key, kingdomId ?? null);
      const ownerColor =
        kingdomId !== null
          ? tileColorMap[String(kingdomId)] ?? null
          : null;
      const isOwned = ownerColor !== null && ownerColor !== undefined;
      const terrainColor =
        TERRAIN_COLORS[cell.terrain] ?? TERRAIN_COLORS.plains;
      drawHex(tilesLayer, pos.x, pos.y, HEX_SIZE, terrainColor, 1);
      if (isOwned) {
        fillHex(
          tilesLayer,
          pos.x,
          pos.y,
          HEX_SIZE,
          ownerColor,
          OWNED_TILE_ALPHA
        );
      }
    });

    tiles.forEach((cell) => {
      const key = `${cell.q},${cell.r}`;
      const ownerId = tileOwnerMap.get(key);
      if (ownerId === null || ownerId === undefined) {
        return;
      }
      const ownerColor = tileColorMap[String(ownerId)];
      if (ownerColor === null || ownerColor === undefined) {
        return;
      }
      const pos = positions.get(key);
      if (!pos) {
        return;
      }
      const corners = hexCorners(pos.x, pos.y, HEX_SIZE);

      NEIGHBOR_OFFSETS.forEach(([dq, dr], index) => {
        const neighborKey = `${cell.q + dq},${cell.r + dr}`;
        const neighborOwner = tileOwnerMap.get(neighborKey);
        if (neighborOwner === ownerId) {
          return;
        }

        const [cornerA, cornerB] = EDGE_CORNER_INDEX[index];
        const start = corners[cornerA];
        const end = corners[cornerB];
        ownershipBordersLayer
          .moveTo(start.x, start.y)
          .lineTo(end.x, end.y)
          .stroke({
            width: OWNED_BORDER_WIDTH,
            color: ownerColor,
            alpha: OWNED_BORDER_ALPHA,
          });
      });
    });

    if (showLandBorders) {
      tiles.forEach((cell) => {
        const key = `${cell.q},${cell.r}`;
        const pos = positions.get(key);
        if (!pos) {
          return;
        }
        const corners = hexCorners(pos.x, pos.y, HEX_SIZE);
        const currentProvince = cell.province_id ?? null;
        const currentLand =
          currentProvince !== null
            ? provinceToLandMap[String(currentProvince)] ?? null
            : null;

        NEIGHBOR_OFFSETS.forEach(([dq, dr], index) => {
          const neighborKey = `${cell.q + dq},${cell.r + dr}`;
          const neighbor = tileIndex.get(neighborKey);
          const neighborProvince = neighbor?.province_id ?? null;
          const neighborLand =
            neighborProvince !== null
              ? provinceToLandMap[String(neighborProvince)] ?? null
              : null;

          if (neighbor && neighborLand === currentLand) {
            return;
          }

          if (
            neighbor &&
            neighborLand !== null &&
            currentLand !== null &&
            currentLand > neighborLand
          ) {
            return;
          }

          const [cornerA, cornerB] = EDGE_CORNER_INDEX[index];
          const start = corners[cornerA];
          const end = corners[cornerB];
          landBordersLayer
            .moveTo(start.x, start.y)
            .lineTo(end.x, end.y)
            .stroke(LAND_STROKE);
        });
      });
    }

    if (showProvinceBorders) {
      tiles.forEach((cell) => {
        const key = `${cell.q},${cell.r}`;
        const pos = positions.get(key);
        if (!pos) {
          return;
        }
        const corners = hexCorners(pos.x, pos.y, HEX_SIZE);
        const currentProvince = cell.province_id ?? null;

        NEIGHBOR_OFFSETS.forEach(([dq, dr], index) => {
          const neighborKey = `${cell.q + dq},${cell.r + dr}`;
          const neighbor = tileIndex.get(neighborKey);
          const neighborProvince = neighbor?.province_id ?? null;

          if (neighbor && neighborProvince === currentProvince) {
            return;
          }

          if (
            neighbor &&
            neighborProvince !== null &&
            currentProvince !== null &&
            currentProvince > neighborProvince
          ) {
            return;
          }

          const [cornerA, cornerB] = EDGE_CORNER_INDEX[index];
          const start = corners[cornerA];
          const end = corners[cornerB];
          provinceBordersLayer
            .moveTo(start.x, start.y)
            .lineTo(end.x, end.y)
            .stroke(PROVINCE_STROKE);
        });
      });
    }

    const width = appRef.current.renderer.width;
    const height = appRef.current.renderer.height;
    const offsetX = width / 2 - (minX + maxX) / 2;
    const offsetY = height / 2 - (minY + maxY) / 2;
    root.position.set(offsetX, offsetY);
  }, [
    tiles,
    provinceToLand,
    landToKingdom,
    kingdomColorMap,
    showLandBorders,
    showProvinceBorders,
  ]);

  useEffect(() => {
    if (!tiles.length || !layersRef.current) {
      return;
    }

    const { townLayer } = layersRef.current;
    const positions = tilePositionsRef.current;

    townLayer.removeChildren();

    if (!iconTextures?.castle) {
      return;
    }

    const seenTownTiles = new Set();

    (towns || []).forEach((town) => {
      const key = `${town.q},${town.r}`;
      if (seenTownTiles.has(key)) {
        return;
      }
      seenTownTiles.add(key);
      const pos = positions.get(key);
      if (!pos) {
        return;
      }
      const tint =
        town.kingdom_id !== null && town.kingdom_id !== undefined
          ? kingdomColorMap[String(town.kingdom_id)] ?? TOWN_NEUTRAL_COLOR
          : TOWN_NEUTRAL_COLOR;
      addIconWithBackground(
        townLayer,
        iconTextures.castle,
        pos,
        CASTLE_ICON_SIZE,
        tint
      );
    });
  }, [tiles, towns, kingdomColorMap, iconTextures]);

  useEffect(() => {
    if (!turnState || !layersRef.current) {
      return;
    }

    const { unitFallbackLayer, unitIconsLayer } = layersRef.current;
    const positions = tilePositionsRef.current;

    unitFallbackLayer.clear();
    unitIconsLayer.removeChildren();

    const infantryTexture = iconTextures?.infantry;

    (turnState.units || []).forEach((unit) => {
      const pos = positions.get(`${unit.q},${unit.r}`);
      if (!pos) {
        return;
      }
      const tint =
        kingdomColorMap[String(unit.owner_kingdom_id)] ?? UNIT_NEUTRAL_COLOR;

      if (infantryTexture) {
        addIconWithBackground(
          unitIconsLayer,
          infantryTexture,
          pos,
          UNIT_ICON_SIZE,
          tint
        );
      } else {
        unitFallbackLayer
          .circle(pos.x, pos.y, HEX_SIZE * 0.45)
          .fill({ color: tint, alpha: 0.95 })
          .stroke(UNIT_STROKE);
      }
    });
  }, [turnState, iconTextures, kingdomColorMap]);

  const loadTurnState = async (targetTurn) => {
    try {
      const [state, chunk] = await Promise.all([
        getTurnState(matchId, targetTurn),
        getChunk(matchId, chunkQ, chunkR, targetTurn),
      ]);
      setTurnState(state.state || {});
      setTiles(chunk.tiles?.cells || []);
      setProvinceToLand(chunk.province_to_land || {});
      setLandToKingdom(chunk.land_to_kingdom || {});
      setTowns(chunk.towns || []);
      setStatus("");
    } catch (error) {
      setTurnState(null);
      setStatus(error.message || "Failed to load turn.");
    }
  };

  const loadAll = async () => {
    setLoading(true);
    setStatus("");
    try {
      const matchState = await getMatchState(matchId);
      const resolved = Math.max(matchState.match.last_resolved_turn || 1, 1);
      setLastResolved(resolved);
      setActiveParticipant(matchState.current_turn.active_participant_id);
      setTurnLength(matchState.match.turn_length_seconds);
      const nextKingdomColorMap = {};
      (matchState.participants || [])
        .slice(0, PLAYER_TILE_COLORS.length)
        .forEach((participant, index) => {
          if (participant.kingdom_id) {
            nextKingdomColorMap[String(participant.kingdom_id)] =
              PLAYER_TILE_COLORS[index];
          }
        });
      setKingdomColorMap(nextKingdomColorMap);

      const nextTurn = Math.min(turnNumber, resolved);
      setTurnNumber(nextTurn);

      await loadTurnState(nextTurn);
    } catch (error) {
      setStatus(error.message || "Failed to load data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  const handlePrev = async () => {
    if (!canGoPrev) {
      return;
    }
    const nextTurn = Math.max(1, turnNumber - 1);
    setTurnNumber(nextTurn);
    await loadTurnState(nextTurn);
  };

  const handleNext = async () => {
    if (!canGoNext) {
      return;
    }
    const nextTurn = Math.min(lastResolved, turnNumber + 1);
    setTurnNumber(nextTurn);
    await loadTurnState(nextTurn);
  };

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <div className="title">War Game Viewer</div>
          <div className="subtitle">Turn playback for hex chunks</div>
        </div>
        <div className="status">
          <span>{statusMessage}</span>
        </div>
      </header>

      <div className="layout">
        <aside className="panel controls">
          <div className="panel-title">Session</div>
          <label>
            Match ID
            <input
              type="number"
              min="1"
              value={matchId}
              onChange={(event) =>
                setMatchId(Number(event.target.value || 1))
              }
            />
          </label>
          <div className="field-row">
            <label>
              Chunk Q
              <input
                type="number"
                value={chunkQ}
                onChange={(event) =>
                  setChunkQ(Number(event.target.value || 0))
                }
              />
            </label>
            <label>
              Chunk R
              <input
                type="number"
                value={chunkR}
                onChange={(event) =>
                  setChunkR(Number(event.target.value || 0))
                }
              />
            </label>
          </div>
          <button className="primary" onClick={loadAll} disabled={loading}>
            Load Map
          </button>

          <div className="panel-title">Turn Controls</div>
          <div className="turn-meta">
            <div>
              Viewing turn <strong>{turnNumber}</strong> of{" "}
              <strong>{lastResolved}</strong>
            </div>
            <div>Active participant: {activeParticipant ?? "-"}</div>
            <div>
              Turn length: {turnLength ? `${turnLength}s` : "-"}
            </div>
          </div>
          <div className="panel-title">Overlays</div>
          <label className="toggle">
            <input
              type="checkbox"
              checked={showProvinceBorders}
              onChange={(event) => setShowProvinceBorders(event.target.checked)}
            />
            Province borders
          </label>
          <label className="toggle">
            <input
              type="checkbox"
              checked={showLandBorders}
              onChange={(event) => setShowLandBorders(event.target.checked)}
            />
            Land borders
          </label>
          <div className="button-row">
            <button onClick={handlePrev} disabled={!canGoPrev}>
              Previous
            </button>
            <button onClick={handleNext} disabled={!canGoNext}>
              Next
            </button>
          </div>
          <div className="hint">
            Tip: use the queue orders API to pre-fill future turns.
          </div>
        </aside>

        <main className="panel map-panel">
          <div className="panel-title">Chunk {chunkQ}, {chunkR}</div>
          <div className="map-wrapper">
            <div className="map-canvas" ref={containerRef} />
          </div>
        </main>
      </div>
    </div>
  );
}
