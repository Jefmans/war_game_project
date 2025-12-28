import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import * as PIXI from "pixi.js";
import {
  getChunk,
  getMatchState,
  getTurnState,
  queueOrders,
  submitOrder,
} from "./api";
import swordmanUrl from "./assets/swordman.png";
import townUrl from "./assets/town.png";

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
const OWNED_TILE_ALPHA = 0.3;
const OWNED_BORDER_WIDTH = 2.6;
const OWNED_BORDER_ALPHA = 1;
const SELECTED_TILE_STROKE = { width: 2.4, color: 0xfbbf24, alpha: 0.9 };
const SELECTED_TILE_FILL = { color: 0xfbbf24, alpha: 0.08 };
const MIN_ZOOM = 0.6;
const MAX_ZOOM = 2.8;
const ZOOM_STEP = 1.1;
const PAN_DRAG_THRESHOLD = 4;
const PATH_STROKE = { width: 2, color: 0xfbbf24, alpha: 0.85 };
const PATH_NODE = { radius: 3.5, color: 0xfbbf24, alpha: 0.9 };
const UNIT_CLICK_RADIUS = HEX_SIZE * 0.8;
const MOVEMENT_COSTS = {
  plains: 1,
  forest: 2,
  hills: 2,
  swamp: 3,
  water: null,
  mountain: null,
};

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

function formatColor(color) {
  if (color === null || color === undefined) {
    return "-";
  }
  return `#${color.toString(16).padStart(6, "0")}`;
}

function movementCost(terrain) {
  if (terrain === undefined || terrain === null) {
    return 1;
  }
  if (!Object.prototype.hasOwnProperty.call(MOVEMENT_COSTS, terrain)) {
    return 1;
  }
  return MOVEMENT_COSTS[terrain];
}

function hexDistance(a, b) {
  const [aq, ar] = a;
  const [bq, br] = b;
  return (
    (Math.abs(aq - bq) +
      Math.abs(aq + ar - bq - br) +
      Math.abs(ar - br)) /
    2
  );
}

function findPath(tileIndex, start, goal, blocked = new Set()) {
  if (start[0] === goal[0] && start[1] === goal[1]) {
    return [start];
  }
  const startKey = `${start[0]},${start[1]}`;
  const goalKey = `${goal[0]},${goal[1]}`;
  if (blocked.has(startKey) || blocked.has(goalKey)) {
    return null;
  }
  const startTile = tileIndex.get(startKey);
  const goalTile = tileIndex.get(goalKey);
  if (!startTile || !goalTile) {
    return null;
  }
  if (movementCost(goalTile.terrain) === null) {
    return null;
  }

  const open = [{ key: startKey, q: start[0], r: start[1], f: hexDistance(start, goal) }];
  const cameFrom = new Map();
  const gScore = new Map([[startKey, 0]]);

  while (open.length) {
    open.sort((a, b) => a.f - b.f);
    const current = open.shift();
    if (!current) {
      break;
    }
    if (current.key === goalKey) {
      const path = [[current.q, current.r]];
      let curKey = current.key;
      while (cameFrom.has(curKey)) {
        const prev = cameFrom.get(curKey);
        path.push([prev.q, prev.r]);
        curKey = prev.key;
      }
      path.reverse();
      return path;
    }

    for (const [dq, dr] of NEIGHBOR_OFFSETS) {
      const nq = current.q + dq;
      const nr = current.r + dr;
      const nKey = `${nq},${nr}`;
      if (blocked.has(nKey)) {
        continue;
      }
      const tile = tileIndex.get(nKey);
      if (!tile) {
        continue;
      }
      const stepCost = movementCost(tile.terrain);
      if (stepCost === null) {
        continue;
      }
      const tentative = gScore.get(current.key) + stepCost;
      if (tentative < (gScore.get(nKey) ?? Infinity)) {
        cameFrom.set(nKey, { key: current.key, q: current.q, r: current.r });
        gScore.set(nKey, tentative);
        const f = tentative + hexDistance([nq, nr], goal);
        const existing = open.find((node) => node.key === nKey);
        if (existing) {
          existing.f = f;
        } else {
          open.push({ key: nKey, q: nq, r: nr, f });
        }
      }
    }
  }
  return null;
}

function buildOrdersFromPath(path, tileIndex, movePoints) {
  if (!path || path.length < 2) {
    return [];
  }
  const orders = [];
  let segmentStart = 0;
  let spent = 0;

  for (let i = 1; i < path.length; i += 1) {
    const [q, r] = path[i];
    const tile = tileIndex.get(`${q},${r}`);
    if (!tile) {
      return [];
    }
    const stepCost = movementCost(tile?.terrain);
    if (stepCost === null) {
      return [];
    }
    if (spent + stepCost > movePoints) {
      if (i - 1 === segmentStart) {
        return [];
      }
      const [dq, dr] = path[i - 1];
      orders.push({ q: dq, r: dr });
      segmentStart = i - 1;
      spent = 0;
    }
    spent += stepCost;
    if (spent === movePoints) {
      orders.push({ q, r });
      segmentStart = i;
      spent = 0;
    }
  }

  if (segmentStart < path.length - 1) {
    const [q, r] = path[path.length - 1];
    orders.push({ q, r });
  }
  return orders;
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
  const [participants, setParticipants] = useState([]);
  const [selectedParticipantId, setSelectedParticipantId] = useState(null);
  const [selectedUnitId, setSelectedUnitId] = useState(null);
  const [selectedTile, setSelectedTile] = useState(null);
  const [routePath, setRoutePath] = useState([]);
  const [pendingOrders, setPendingOrders] = useState([]);
  const [orderStatus, setOrderStatus] = useState("");
  const [orderLoading, setOrderLoading] = useState(false);
  const [viewMode, setViewMode] = useState("playback");
  const [liveTurnNumber, setLiveTurnNumber] = useState(1);

  const containerRef = useRef(null);
  const appRef = useRef(null);
  const canvasRef = useRef(null);
  const layersRef = useRef(null);
  const tilePositionsRef = useRef(new Map());
  const tileIndexRef = useRef(new Map());
  const viewRef = useRef({ baseX: 0, baseY: 0, panX: 0, panY: 0, scale: 1 });
  const panRef = useRef({
    isDragging: false,
    startX: 0,
    startY: 0,
    startPanX: 0,
    startPanY: 0,
    wasDrag: false,
  });

  const displayTurn = viewMode === "live" ? liveTurnNumber : turnNumber;
  const canGoPrev = viewMode === "playback" && turnNumber > 1;
  const canGoNext = viewMode === "playback" && turnNumber < lastResolved;

  const selectedParticipant = useMemo(
    () =>
      participants.find((participant) => participant.id === selectedParticipantId) ||
      null,
    [participants, selectedParticipantId]
  );

  const selectedParticipantColor = useMemo(() => {
    if (
      !selectedParticipant ||
      selectedParticipant.kingdom_id === null ||
      selectedParticipant.kingdom_id === undefined
    ) {
      return null;
    }
    const color = kingdomColorMap[String(selectedParticipant.kingdom_id)];
    return color !== undefined ? color : null;
  }, [selectedParticipant, kingdomColorMap]);

  const ownedUnits = useMemo(() => {
    if (!selectedParticipant || !turnState?.units) {
      return [];
    }
    return turnState.units.filter(
      (unit) => unit.owner_kingdom_id === selectedParticipant.kingdom_id
    );
  }, [selectedParticipant, turnState]);

  const selectedUnit = useMemo(
    () => ownedUnits.find((unit) => unit.id === selectedUnitId) || null,
    [ownedUnits, selectedUnitId]
  );

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
    if (!participants.length) {
      setSelectedParticipantId(null);
      return;
    }
    if (
      selectedParticipantId &&
      participants.some((participant) => participant.id === selectedParticipantId)
    ) {
      return;
    }
    const activeCandidate = participants.some(
      (participant) => participant.id === activeParticipant
    )
      ? activeParticipant
      : null;
    setSelectedParticipantId(activeCandidate ?? participants[0].id);
  }, [participants, selectedParticipantId, activeParticipant]);

  useEffect(() => {
    if (!ownedUnits.length) {
      setSelectedUnitId(null);
      return;
    }
    if (selectedUnitId && ownedUnits.some((unit) => unit.id === selectedUnitId)) {
      return;
    }
    setSelectedUnitId(ownedUnits[0].id);
  }, [ownedUnits, selectedUnitId]);

  useEffect(() => {
    setRoutePath([]);
    setSelectedTile(null);
    setPendingOrders([]);
    setOrderStatus("");
  }, [selectedUnitId]);

  useEffect(() => {
    setPendingOrders([]);
    setOrderStatus("");
    setRoutePath([]);
    setSelectedTile(null);
  }, [selectedParticipantId]);

  useEffect(() => {
    if (!selectedTile) {
      return;
    }
    const key = `${selectedTile.q},${selectedTile.r}`;
    if (!tilePositionsRef.current.has(key)) {
      setSelectedTile(null);
    }
  }, [selectedTile, tiles]);

  useEffect(() => {
    let cancelled = false;

    const loadIcons = async () => {
      try {
        const [infantryTexture, castleTexture] = await Promise.all([
          PIXI.Assets.load(swordmanUrl),
          PIXI.Assets.load(townUrl),
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
      canvasRef.current = app.canvas;

      const root = new PIXI.Container();
      const tilesLayer = new PIXI.Graphics();
      const landBordersLayer = new PIXI.Graphics();
      const provinceBordersLayer = new PIXI.Graphics();
      const ownershipBordersLayer = new PIXI.Graphics();
      const pathLayer = new PIXI.Graphics();
      const selectionLayer = new PIXI.Graphics();
      const townLayer = new PIXI.Container();
      const unitFallbackLayer = new PIXI.Graphics();
      const unitIconsLayer = new PIXI.Container();

      root.addChild(tilesLayer);
      root.addChild(landBordersLayer);
      root.addChild(provinceBordersLayer);
      root.addChild(ownershipBordersLayer);
      root.addChild(pathLayer);
      root.addChild(selectionLayer);
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
        pathLayer,
        selectionLayer,
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
      canvasRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!tiles.length || !layersRef.current || !appRef.current) {
      return;
    }

    const {
      tilesLayer,
      landBordersLayer,
      provinceBordersLayer,
      ownershipBordersLayer,
      selectionLayer,
      root,
    } = layersRef.current;
    const positions = new Map();
    const tileIndex = new Map();
    const tileOwnerMap = new Map();
    tilesLayer.clear();
    landBordersLayer.clear();
    provinceBordersLayer.clear();
    ownershipBordersLayer.clear();
    selectionLayer.clear();

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
    tileIndexRef.current = tileIndex;

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
    const view = viewRef.current;
    view.baseX = offsetX;
    view.baseY = offsetY;
    root.scale.set(view.scale);
    root.position.set(offsetX + view.panX, offsetY + view.panY);
  }, [
    tiles,
    provinceToLand,
    landToKingdom,
    kingdomColorMap,
    showLandBorders,
    showProvinceBorders,
  ]);

  useEffect(() => {
    if (!layersRef.current) {
      return;
    }
    const { selectionLayer } = layersRef.current;
    selectionLayer.clear();
    if (!selectedTile) {
      return;
    }
    const pos = tilePositionsRef.current.get(
      `${selectedTile.q},${selectedTile.r}`
    );
    if (!pos) {
      return;
    }
    selectionLayer
      .poly(hexPoints(pos.x, pos.y, HEX_SIZE))
      .fill(SELECTED_TILE_FILL)
      .stroke(SELECTED_TILE_STROKE);
  }, [selectedTile, tiles]);

  useEffect(() => {
    if (!layersRef.current) {
      return;
    }
    const { pathLayer } = layersRef.current;
    pathLayer.clear();
    if (!routePath || routePath.length < 2) {
      return;
    }
    const positions = tilePositionsRef.current;
    const first = positions.get(`${routePath[0][0]},${routePath[0][1]}`);
    if (!first) {
      return;
    }
    pathLayer.moveTo(first.x, first.y);
    for (let i = 1; i < routePath.length; i += 1) {
      const key = `${routePath[i][0]},${routePath[i][1]}`;
      const pos = positions.get(key);
      if (!pos) {
        continue;
      }
      pathLayer.lineTo(pos.x, pos.y);
    }
    pathLayer.stroke(PATH_STROKE);
    routePath.forEach(([q, r]) => {
      const pos = positions.get(`${q},${r}`);
      if (!pos) {
        return;
      }
      pathLayer.circle(pos.x, pos.y, PATH_NODE.radius).fill(PATH_NODE);
    });
  }, [routePath, tiles]);


  const planRouteTo = useCallback((destination) => {
    if (!selectedUnit) {
      setOrderStatus("Select a unit to plan a route.");
      setRoutePath([]);
      return;
    }
    const tileIndex = tileIndexRef.current;
    if (!tileIndex.size) {
      setOrderStatus("Map tiles are not ready yet.");
      setRoutePath([]);
      return;
    }
    const blocked = new Set();
    (turnState?.units || []).forEach((unit) => {
      if (unit.id !== selectedUnit.id) {
        blocked.add(`${unit.q},${unit.r}`);
      }
    });
    const start = [selectedUnit.q, selectedUnit.r];
    const goal = [destination.q, destination.r];
    const path = findPath(tileIndex, start, goal, blocked);
    if (!path) {
      setOrderStatus("No route found to that destination.");
      setRoutePath([]);
      return;
    }
    setRoutePath(path);
    const movePoints = selectedUnit.move_points ?? 3;
    const destinations = buildOrdersFromPath(path, tileIndex, movePoints);
    if (!destinations.length) {
      setOrderStatus("Route is blocked or too costly for this unit.");
      setPendingOrders([]);
      return;
    }
    const orders = destinations.map((dest) => ({
      type: "move",
      unit_id: selectedUnit.id,
      to: { q: dest.q, r: dest.r },
    }));
    setPendingOrders(orders);
    setOrderStatus(
      `Planned route ${path.length - 1} step(s) over ${orders.length} turn(s).`
    );
  }, [selectedUnit, turnState]);
  useEffect(() => {
    const layers = layersRef.current;
    const canvas = canvasRef.current;
    if (!canvas || !layers) {
      return;
    }
    const view = viewRef.current;
    const panState = panRef.current;

    const handleClick = (event) => {
      if (panState.wasDrag) {
        panState.wasDrag = false;
        return;
      }
      const positions = tilePositionsRef.current;
      if (!positions.size) {
        return;
      }
      const rect = canvas.getBoundingClientRect();
      const clickX = event.clientX - rect.left;
      const clickY = event.clientY - rect.top;
      const scale = view.scale || 1;
      const worldX = (clickX - layers.root.position.x) / scale;
      const worldY = (clickY - layers.root.position.y) / scale;

      let clickedUnit = null;
      let closestUnitDist = Infinity;
      ownedUnits.forEach((unit) => {
        const pos = positions.get(`${unit.q},${unit.r}`);
        if (!pos) {
          return;
        }
        const dx = pos.x - worldX;
        const dy = pos.y - worldY;
        const dist = dx * dx + dy * dy;
        if (dist < closestUnitDist) {
          closestUnitDist = dist;
          clickedUnit = unit;
        }
      });

      if (
        clickedUnit &&
        closestUnitDist <= UNIT_CLICK_RADIUS * UNIT_CLICK_RADIUS
      ) {
        if (selectedUnitId === clickedUnit.id) {
          setRoutePath([]);
          setPendingOrders([]);
          setSelectedTile(null);
          setOrderStatus("Route cleared.");
        } else {
          setSelectedUnitId(clickedUnit.id);
          setRoutePath([]);
          setOrderStatus("");
        }
        return;
      }

      let bestKey = null;
      let bestDist = Infinity;
      positions.forEach((pos, key) => {
        const dx = pos.x - worldX;
        const dy = pos.y - worldY;
        const dist = dx * dx + dy * dy;
        if (dist < bestDist) {
          bestDist = dist;
          bestKey = key;
        }
      });

      const maxDist = HEX_SIZE * 1.2;
      if (!bestKey || bestDist > maxDist * maxDist) {
        return;
      }
      const [q, r] = bestKey.split(",").map(Number);
      setSelectedTile({ q, r });
      if (selectedUnit) {
        planRouteTo({ q, r });
      } else {
        setRoutePath([]);
      }
    };

    const handlePointerDown = (event) => {
      if (event.button !== 0) {
        return;
      }
      panState.isDragging = true;
      panState.wasDrag = false;
      panState.startX = event.clientX;
      panState.startY = event.clientY;
      panState.startPanX = view.panX;
      panState.startPanY = view.panY;
      canvas.setPointerCapture(event.pointerId);
    };

    const handlePointerMove = (event) => {
      if (!panState.isDragging) {
        return;
      }
      const dx = event.clientX - panState.startX;
      const dy = event.clientY - panState.startY;
      if (!panState.wasDrag) {
        if (Math.abs(dx) + Math.abs(dy) < PAN_DRAG_THRESHOLD) {
          return;
        }
        panState.wasDrag = true;
      }
      view.panX = panState.startPanX + dx;
      view.panY = panState.startPanY + dy;
      layers.root.position.set(view.baseX + view.panX, view.baseY + view.panY);
    };

    const handlePointerUp = (event) => {
      panState.isDragging = false;
      canvas.releasePointerCapture(event.pointerId);
    };

    const handlePointerLeave = () => {
      panState.isDragging = false;
    };

    const handleWheel = (event) => {
      event.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const cursorX = event.clientX - rect.left;
      const cursorY = event.clientY - rect.top;
      const oldScale = view.scale || 1;
      const zoomFactor = event.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP;
      const nextScale = Math.min(
        MAX_ZOOM,
        Math.max(MIN_ZOOM, oldScale * zoomFactor)
      );
      if (nextScale === oldScale) {
        return;
      }
      const worldX = (cursorX - layers.root.position.x) / oldScale;
      const worldY = (cursorY - layers.root.position.y) / oldScale;
      const nextX = cursorX - worldX * nextScale;
      const nextY = cursorY - worldY * nextScale;
      view.scale = nextScale;
      view.panX = nextX - view.baseX;
      view.panY = nextY - view.baseY;
      layers.root.scale.set(nextScale);
      layers.root.position.set(nextX, nextY);
    };

    canvas.addEventListener("click", handleClick);
    canvas.addEventListener("pointerdown", handlePointerDown);
    canvas.addEventListener("pointermove", handlePointerMove);
    canvas.addEventListener("pointerup", handlePointerUp);
    canvas.addEventListener("pointerleave", handlePointerLeave);
    canvas.addEventListener("wheel", handleWheel, { passive: false });
    return () => {
      canvas.removeEventListener("click", handleClick);
      canvas.removeEventListener("pointerdown", handlePointerDown);
      canvas.removeEventListener("pointermove", handlePointerMove);
      canvas.removeEventListener("pointerup", handlePointerUp);
      canvas.removeEventListener("pointerleave", handlePointerLeave);
      canvas.removeEventListener("wheel", handleWheel);
    };
  }, [tiles, ownedUnits, selectedUnit, turnState, planRouteTo]);

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

  const loadAll = async (mode = viewMode) => {
    setLoading(true);
    setStatus("");
    try {
      const matchState = await getMatchState(matchId);
      const resolved = Math.max(matchState.match.last_resolved_turn || 1, 1);
      setLastResolved(resolved);
      setActiveParticipant(matchState.current_turn.active_participant_id);
      setTurnLength(matchState.match.turn_length_seconds);
      setParticipants(matchState.participants || []);
      const currentTurn = matchState.current_turn.number;
      setLiveTurnNumber(currentTurn);
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
      const nextTurn =
        mode === "live" ? currentTurn : Math.min(turnNumber, resolved);
      if (mode === "playback") {
        setTurnNumber(nextTurn);
      }
      setViewMode(mode);

      await loadTurnState(nextTurn);
    } catch (error) {
      setStatus(error.message || "Failed to load data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll("playback");
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

  const handleAddOrder = () => {
    if (!selectedParticipantId) {
      setOrderStatus("Select a participant first.");
      return;
    }
    if (!selectedUnitId) {
      setOrderStatus("Select a unit to move.");
      return;
    }
    if (!selectedTile) {
      setOrderStatus("Click a destination tile on the map.");
      return;
    }
    setPendingOrders((prev) => [
      ...prev,
      {
        type: "move",
        unit_id: selectedUnitId,
        to: { q: selectedTile.q, r: selectedTile.r },
      },
    ]);
    setOrderStatus("");
  };

  const handleRemoveOrder = (index) => {
    setPendingOrders((prev) => prev.filter((_, idx) => idx !== index));
  };

  const handleClearOrders = () => {
    setPendingOrders([]);
    setOrderStatus("");
  };

  const handleQueueOrders = async () => {
    if (!selectedParticipantId) {
      setOrderStatus("Select a participant first.");
      return;
    }
    if (!pendingOrders.length) {
      setOrderStatus("Add at least one order to queue.");
      return;
    }
    setOrderLoading(true);
    setOrderStatus("Queueing orders...");
    try {
      const response = await queueOrders(matchId, {
        participant_id: selectedParticipantId,
        orders: pendingOrders,
      });
      const queuedCount = response.queued?.length ?? 0;
      const skippedCount = response.skipped?.length ?? 0;
      const extra =
        skippedCount > 0 ? ` Skipped ${skippedCount} beyond max turn.` : "";
      setOrderStatus(`Queued ${queuedCount} order(s).${extra}`);
      setPendingOrders([]);
    } catch (error) {
      setOrderStatus(error.message || "Failed to queue orders.");
    } finally {
      setOrderLoading(false);
    }
  };

  const handleSubmitCurrentTurn = async () => {
    if (!selectedParticipantId) {
      setOrderStatus("Select a participant first.");
      return;
    }
    const pending = pendingOrders[0];
    const unitId = pending?.unit_id ?? selectedUnitId;
    const destination = pending?.to ?? selectedTile;
    if (!unitId) {
      setOrderStatus("Select a unit to move.");
      return;
    }
    if (!destination) {
      setOrderStatus("Click a destination tile on the map.");
      return;
    }
    setOrderLoading(true);
    setOrderStatus("Submitting current turn...");
    try {
      const response = await submitOrder(matchId, {
        participant_id: selectedParticipantId,
        order: {
          type: "move",
          unit_id: unitId,
          to: { q: destination.q, r: destination.r },
        },
      });
      setOrderStatus(
        `Resolved turn ${response.turn}. Next turn ${response.next_turn}.`
      );
      setPendingOrders((prev) => (pending ? prev.slice(1) : prev));
      await loadAll(viewMode);
    } catch (error) {
      setOrderStatus(error.message || "Failed to submit order.");
    } finally {
      setOrderLoading(false);
    }
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
          <button
            className="primary"
            onClick={() => loadAll("playback")}
            disabled={loading}
          >
            Load Playback
          </button>

          <div className="panel-title">View Mode</div>
          <div className="button-row">
            <button
              onClick={() => loadAll("playback")}
              disabled={loading || viewMode === "playback"}
            >
              Playback
            </button>
            <button
              onClick={() => loadAll("live")}
              disabled={loading || viewMode === "live"}
            >
              Live
            </button>
          </div>

          <div className="panel-title">Turn Controls</div>
          <div className="turn-meta">
            <div>
              {viewMode === "live" ? "Live turn" : "Viewing turn"}{" "}
              <strong>{displayTurn}</strong> of{" "}
              <strong>{lastResolved}</strong>
            </div>
            <div>Mode: {viewMode}</div>
            <div>Active participant: {activeParticipant ?? "-"}</div>
            <div>
              Turn length: {turnLength ? `${turnLength}s` : "-"}
            </div>
          </div>
          <div className="panel-title">Player Orders</div>
          <label>
            Participant
            <select
              value={selectedParticipantId ?? ""}
              onChange={(event) => {
                const value = event.target.value;
                setSelectedParticipantId(value ? Number(value) : null);
              }}
            >
              <option value="" disabled>
                Choose participant
              </option>
              {participants.map((participant) => {
                const colorValue =
                  participant.kingdom_id === null ||
                  participant.kingdom_id === undefined
                    ? null
                    : kingdomColorMap[String(participant.kingdom_id)];
                const colorLabel = formatColor(colorValue);
                return (
                  <option key={participant.id} value={participant.id}>
                    {participant.user_id
                      ? `User ${participant.user_id}`
                      : `Participant ${participant.id}`} (seat{" "}
                    {participant.seat_order}) - color {colorLabel}
                  </option>
                );
              })}
            </select>
          </label>
          {selectedParticipant ? (
            <div className="meta">
              participant_id: {selectedParticipant.id} | user_id:{" "}
              {selectedParticipant.user_id ?? "-"} | kingdom_id:{" "}
              {selectedParticipant.kingdom_id ?? "-"} | seat:{" "}
              {selectedParticipant.seat_order ?? "-"} | color:{" "}
              {formatColor(selectedParticipantColor)}{" "}
              <span
                className="color-swatch"
                style={{
                  backgroundColor:
                    selectedParticipantColor !== null
                      ? formatColor(selectedParticipantColor)
                      : "transparent",
                  opacity: selectedParticipantColor !== null ? 1 : 0.35,
                }}
              />
            </div>
          ) : null}
          <label>
            Unit
            <select
              value={selectedUnitId ?? ""}
              onChange={(event) => {
                const value = event.target.value;
                setSelectedUnitId(value ? Number(value) : null);
              }}
              disabled={!ownedUnits.length}
            >
              <option value="" disabled>
                {ownedUnits.length ? "Choose unit" : "No owned units"}
              </option>
              {ownedUnits.map((unit) => (
                <option key={unit.id} value={unit.id}>
                  Unit {unit.id} ({unit.q},{unit.r})
                </option>
              ))}
            </select>
          </label>
          <div className="meta">
            Destination:{" "}
            {selectedTile ? `${selectedTile.q}, ${selectedTile.r}` : "click a tile"}
          </div>
          <div className="button-row">
            <button
              onClick={() => setSelectedTile(null)}
              disabled={!selectedTile}
            >
              Clear target
            </button>
            <button
              className="primary"
              onClick={handleAddOrder}
              disabled={!selectedUnitId || !selectedTile}
            >
              Add move
            </button>
          </div>
          <div className="button-row">
            <button
              className="primary full"
              onClick={handleSubmitCurrentTurn}
              disabled={!selectedUnitId || !selectedTile || orderLoading}
            >
              Submit current turn
            </button>
          </div>
          <div className="orders-list">
            {pendingOrders.length ? (
              pendingOrders.map((order, index) => (
                <div
                  className="order-item"
                  key={`${order.unit_id}-${index}`}
                >
                  <div>
                    <div className="order-title">
                      Move unit {order.unit_id}
                    </div>
                    <div className="order-meta">
                      to {order.to.q}, {order.to.r}
                    </div>
                  </div>
                  <button onClick={() => handleRemoveOrder(index)}>
                    Remove
                  </button>
                </div>
              ))
            ) : (
              <div className="order-empty">No queued orders yet.</div>
            )}
          </div>
          <div className="button-row">
            <button onClick={handleClearOrders} disabled={!pendingOrders.length}>
              Clear list
            </button>
            <button
              className="primary"
              onClick={handleQueueOrders}
              disabled={!pendingOrders.length || orderLoading}
            >
              Queue orders
            </button>
          </div>
          {orderStatus ? <div className="hint">{orderStatus}</div> : null}
          <div className="hint">
            Tip: click your unit, then a destination tile to plan a route. Click
            the unit again to clear.
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
            Tip: queued orders fill upcoming turns for the selected participant.
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
