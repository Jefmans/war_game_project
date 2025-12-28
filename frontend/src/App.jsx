import React, { useEffect, useMemo, useRef, useState } from "react";
import * as PIXI from "pixi.js";
import { getChunk, getMatchState, getTurnState } from "./api";

const DEFAULT_MATCH_ID = Number(import.meta.env.VITE_MATCH_ID || 1);
const DEFAULT_CHUNK_Q = Number(import.meta.env.VITE_CHUNK_Q || 0);
const DEFAULT_CHUNK_R = Number(import.meta.env.VITE_CHUNK_R || 0);
const HEX_SIZE = 12;

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

function axialToPixel(q, r, size) {
  const x = size * Math.sqrt(3) * (q + r / 2);
  const y = size * 1.5 * r;
  return { x, y };
}

function drawHex(graphics, x, y, size, color) {
  const points = [];
  for (let i = 0; i < 6; i += 1) {
    const angle = (Math.PI / 180) * (60 * i - 30);
    points.push(x + size * Math.cos(angle), y + size * Math.sin(angle));
  }
  graphics.beginFill(color);
  graphics.drawPolygon(points);
  graphics.endFill();
}

function colorForKingdom(id) {
  if (!id && id !== 0) {
    return 0xdddddd;
  }
  return KINGDOM_COLORS[id % KINGDOM_COLORS.length];
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
  const [turnState, setTurnState] = useState(null);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);

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
      const unitsLayer = new PIXI.Graphics();

      root.addChild(tilesLayer);
      root.addChild(unitsLayer);
      app.stage.addChild(root);

      layersRef.current = {
        root,
        tilesLayer,
        unitsLayer,
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

    const { tilesLayer, root } = layersRef.current;
    const positions = new Map();
    tilesLayer.clear();
    tilesLayer.lineStyle(1, 0x1b232b, 0.6);

    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;

    tiles.forEach((cell) => {
      const { x, y } = axialToPixel(cell.q, cell.r, HEX_SIZE);
      positions.set(`${cell.q},${cell.r}`, { x, y });
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
      minY = Math.min(minY, y);
      maxY = Math.max(maxY, y);
    });

    tilePositionsRef.current = positions;

    tiles.forEach((cell) => {
      const pos = positions.get(`${cell.q},${cell.r}`);
      const color = TERRAIN_COLORS[cell.terrain] || TERRAIN_COLORS.plains;
      drawHex(tilesLayer, pos.x, pos.y, HEX_SIZE, color);
    });

    const width = appRef.current.renderer.width;
    const height = appRef.current.renderer.height;
    const offsetX = width / 2 - (minX + maxX) / 2;
    const offsetY = height / 2 - (minY + maxY) / 2;
    root.position.set(offsetX, offsetY);
  }, [tiles]);

  useEffect(() => {
    if (!turnState || !layersRef.current) {
      return;
    }

    const { unitsLayer } = layersRef.current;
    const positions = tilePositionsRef.current;

    unitsLayer.clear();
    unitsLayer.lineStyle(2, 0x131d25, 0.7);

    (turnState.units || []).forEach((unit) => {
      const pos = positions.get(`${unit.q},${unit.r}`);
      if (!pos) {
        return;
      }
      unitsLayer.beginFill(colorForKingdom(unit.owner_kingdom_id), 0.95);
      unitsLayer.drawCircle(pos.x, pos.y, HEX_SIZE * 0.45);
      unitsLayer.endFill();
    });
  }, [turnState]);

  const loadTurnState = async (targetTurn) => {
    try {
      const state = await getTurnState(matchId, targetTurn);
      setTurnState(state.state || {});
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

      const nextTurn = Math.min(turnNumber, resolved);
      setTurnNumber(nextTurn);

      const chunk = await getChunk(matchId, chunkQ, chunkR);
      setTiles(chunk.tiles?.cells || []);

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
