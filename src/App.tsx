import { useEffect, useRef, useState } from "react";
import {
  Sparkles,
  Sun,
  Waves,
  Leaf,
  Mountain,
  Brush,
  ArrowRight,
  LoaderCircle,
  Eraser,
  RotateCcw,
  Check,
  AlertCircle,
} from "lucide-react";
import { PaintingCanvas, TERRAIN } from "./Canvas";
import { hasPaint, pngBlob } from "./painting";
import {
  request,
  loadArtwork,
  ApiError,
  type World,
  type Job,
  type Health,
  type Force,
} from "./api";
import "./style.css";

const WORLD_KEY = "magical-landscape.world";
const JOB_KEY = "magical-landscape.job";
const FORCES = [
  {
    id: "growth_time" as Force,
    name: "Growth + Time",
    color: "#a1b887",
    icon: Leaf,
    description:
      "Let centuries pass. Forests mature, roots spread, and nature reclaims the old.",
    example: "Ancient roots reclaim this tower",
  },
  {
    id: "water" as Force,
    name: "Water",
    color: "#78b9d1",
    icon: Waves,
    description:
      "Let water reshape the land. Carve channels, flood ruins, and bring life to the edges.",
    example: "A shimmering river floods these ruins",
  },
  {
    id: "light" as Force,
    name: "Light",
    color: "#e6c17b",
    icon: Sun,
    description:
      "Illuminate and awaken. Let flowers glow and ancient places reveal their magic.",
    example: "Golden light awakens these ruins",
  },
];

export default function App() {
  const [world, setWorld] = useState<World | null>(null);
  const [artwork, setArtwork] = useState<HTMLImageElement | null>(null);
  const [pixels, setPixels] = useState(() => new Uint8Array(512 * 512));
  const [version, setVersion] = useState(0);
  const [terrain, setTerrain] = useState(1);
  const [force, setForce] = useState<Force>("growth_time");
  const [brushSize, setBrushSize] = useState(32);
  const [text, setText] = useState("");
  const [health, setHealth] = useState<Health | null>(null);
  const [busy, setBusy] = useState(false);
  const [starting, setStarting] = useState(true);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState("");
  const alive = useRef(true);
  const size = world?.size || 512;
  const selectedForce = FORCES.find((f) => f.id === force)!;
  const painted = hasPaint(pixels);
  const disabled = starting || busy;
  const canGenerate = painted && !disabled && Boolean(health?.models_ready);
  const bump = () => setVersion((v) => v + 1);

  async function acceptWorld(next: World) {
    const image = await loadArtwork(next.image_url);
    if (!alive.current) return;
    setArtwork(image);
    setWorld(next);
    setPixels(new Uint8Array(next.size * next.size));
    bump();
    setText("");
    localStorage.setItem(WORLD_KEY, next.id);
  }

  async function followJob(id: string) {
    localStorage.setItem(JOB_KEY, id);
    setBusy(true);
    while (alive.current) {
      try {
        const current = await request<Job>("/api/jobs/" + id);
        if (!alive.current) return;
        setJob(current);
        if (current.status === "failed") {
          setError(
            current.error ||
              "Generation failed. Adjust your drawing and retry.",
          );
          localStorage.removeItem(JOB_KEY);
          setBusy(false);
          return;
        }
        if (current.status === "succeeded" && current.result) {
          await acceptWorld(
            await request<World>("/api/worlds/" + current.result.id),
          );
          if (!alive.current) return;
          localStorage.removeItem(JOB_KEY);
          setBusy(false);
          setJob(null);
          setError("");
          return;
        }
        setError("");
      } catch (e) {
        if (!alive.current) return;
        if (e instanceof ApiError && e.status === 404) {
          localStorage.removeItem(JOB_KEY);
          setError(e.message);
          setBusy(false);
          setJob(null);
          return;
        }
        setError(
          (e as Error).message + " Reconnecting to the pending generation…",
        );
      }
      await new Promise((r) => setTimeout(r, 800));
    }
  }

  useEffect(() => {
    alive.current = true;
    (async () => {
      try {
        const status = await request<Health>("/api/health");
        if (!alive.current) return;
        setHealth(status);
        const saved = localStorage.getItem(WORLD_KEY);
        if (saved) {
          try {
            await acceptWorld(await request<World>("/api/worlds/" + saved));
          } catch (e) {
            if (e instanceof ApiError && e.status === 404)
              localStorage.removeItem(WORLD_KEY);
            setError((e as Error).message);
          }
        }
        const pending = localStorage.getItem(JOB_KEY);
        if (pending) void followJob(pending);
      } catch (e) {
        if (alive.current)
          setError(
            "Cannot connect to the local image backend. Start it and refresh.",
          );
      } finally {
        if (alive.current) setStarting(false);
      }
    })();
    const timer = setInterval(() => {
      request<Health>("/api/health")
        .then((h) => {
          if (alive.current) setHealth(h);
        })
        .catch(() => {});
    }, 5000);
    return () => {
      alive.current = false;
      clearInterval(timer);
    };
  }, []);

  async function generate() {
    if (!canGenerate) return;
    setBusy(true);
    setError("");
    setJob({
      id: "",
      status: "queued",
      stage: "Preparing your drawing",
      step: 0,
      total: 0,
      result: null,
      error: null,
    });
    try {
      const form = new FormData();
      form.append(
        world ? "mask" : "labels",
        await pngBlob(pixels, size),
        world ? "mask.png" : "labels.png",
      );
      if (world) {
        form.append("force", force);
        form.append("text", text);
        form.append("expected_revision", String(world.revision));
      }
      const result = await request<{ job_id: string; world_id: string }>(
        world ? `/api/worlds/${world.id}/transform` : "/api/worlds",
        { method: "POST", body: form },
      );
      await followJob(result.job_id);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
      setJob(null);
    }
  }

  function clear() {
    if (disabled) return;
    pixels.fill(0);
    bump();
    setError("");
  }
  function resetCanvas() {
    if (disabled) return;
    setWorld(null);
    setArtwork(null);
    setPixels(new Uint8Array(512 * 512));
    setTerrain(1);
    setForce("growth_time");
    setBrushSize(32);
    setText("");
    setJob(null);
    setError("");
    localStorage.removeItem(WORLD_KEY);
    localStorage.removeItem(JOB_KEY);
    bump();
  }
  function chooseForce(next: Force) {
    if (disabled || next === force) return;
    setForce(next);
    pixels.fill(0);
    bump();
    setError("");
  }
  const progress = job?.total ? Math.min(100, (100 * job.step) / job.total) : 0;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">
            <Sparkles size={21} />
          </span>
          <span>Magical Landscape</span>
        </div>
        <div className="connection">
          <span
            className={health?.models_ready ? "status-dot ready" : "status-dot"}
          />
          {!health
            ? "Connecting"
            : !health.models_ready
              ? "Preparing image models"
              : health.device === "cpu"
                ? "CPU generation · slower"
                : "Local image generation"}
        </div>
      </header>
      <main>
        <div className="intro">
          <div>
            <p className="eyebrow">DRAW A CAUSE. DISCOVER A CONSEQUENCE.</p>
            <h1>
              {world ? "Let your world evolve." : "A world, waiting to happen."}
            </h1>
            <p className="subtitle">
              {world
                ? "Paint a little magic. Watch the landscape become something new."
                : "Sketch the landscape. Bring it to life. Then change it with a little magic."}
            </p>
          </div>
          <div className="stages" aria-label="Creation stages">
            <div className={!world ? "stage active" : "stage complete"}>
              <span>{world ? <Check size={15} /> : "01"}</span>Draw your world
            </div>
            <div className={world ? "stage active" : "stage"}>
              <span>02</span>Evolve it
            </div>
          </div>
        </div>
        <div className="workspace">
          <section className="art-panel" aria-label="Drawing workspace">
            <div className="panel-heading">
              <span>
                <Brush size={16} />
                {world ? "Your living landscape" : "Your landscape sketch"}
              </span>
              <span className="canvas-size">
                {size} × {size}
              </span>
            </div>
            <div className="canvas-frame">
              <PaintingCanvas
                pixels={pixels}
                size={size}
                version={version}
                value={world ? 255 : terrain}
                brushSize={brushSize}
                artwork={artwork}
                forceColor={selectedForce.color.slice(1)}
                disabled={disabled}
                onPaint={bump}
              />
              {!world && !painted && !busy && (
                <div className="canvas-hint">
                  <Mountain size={38} strokeWidth={1} />
                  <strong>Every world starts with a mark.</strong>
                  <span>
                    Choose a brush and paint your first piece of land.
                  </span>
                </div>
              )}
              {busy && (
                <div className="generating-overlay">
                  <LoaderCircle className="spin" size={28} />
                  <span>{job?.stage || "Connecting to generation"}</span>
                  {Boolean(job?.total) && (
                    <small>
                      Step {job?.step} of {job?.total}
                    </small>
                  )}
                </div>
              )}
            </div>
            <div className="canvas-footer">
              <span>
                <span
                  className="tiny-dot"
                  style={{
                    background: world
                      ? selectedForce.color
                      : TERRAIN[terrain].color,
                  }}
                />
                {world ? selectedForce.name : TERRAIN[terrain].name} brush
              </span>
              <div className="canvas-actions">
                <button
                  className="text-button"
                  disabled={disabled || !painted}
                  onClick={clear}
                >
                  <Eraser size={14} />
                  Clear strokes
                </button>
                <button
                  className="text-button"
                  disabled={disabled}
                  onClick={resetCanvas}
                >
                  <RotateCcw size={14} />
                  Reset canvas
                </button>
              </div>
            </div>
          </section>
          <aside className="tools-panel">
            <div className="tools-heading">
              <p className="eyebrow">
                {world ? "EVOLVE YOUR WORLD" : "CREATE YOUR WORLD"}
              </p>
              <h2>{world ? "Choose a force" : "Paint the landscape"}</h2>
              <p>
                {world
                  ? "Paint where the magic should happen."
                  : "Build your composition with colored regions. Unpainted areas become sky."}
              </p>
            </div>
            {!world ? (
              <div className="terrain-list">
                {TERRAIN.map((t, i) => (
                  <button
                    key={t.name}
                    className={terrain === i ? "terrain selected" : "terrain"}
                    disabled={disabled}
                    aria-pressed={terrain === i}
                    onClick={() => setTerrain(i)}
                  >
                    <span className="swatch" style={{ background: t.color }} />
                    <span>
                      <strong>{t.name}</strong>
                      <small>{t.hint}</small>
                    </span>
                    {terrain === i && <Check size={15} />}
                  </button>
                ))}
              </div>
            ) : (
              <div className="forces-list">
                {FORCES.map((f) => (
                  <button
                    key={f.id}
                    className={force === f.id ? "force selected" : "force"}
                    disabled={disabled}
                    aria-pressed={force === f.id}
                    onClick={() => chooseForce(f.id)}
                  >
                    <f.icon size={19} style={{ color: f.color }} />
                    <strong>{f.name}</strong>
                    {force === f.id && <Check size={15} />}
                  </button>
                ))}
                <p className="force-description">{selectedForce.description}</p>
              </div>
            )}
            <div className="brush-control">
              <div>
                <label htmlFor="brush-size">Brush size</label>
                <span>{brushSize} px</span>
              </div>
              <input
                id="brush-size"
                type="range"
                min="8"
                max="96"
                value={brushSize}
                disabled={disabled}
                onChange={(e) => setBrushSize(Number(e.target.value))}
              />
              <div className="range-labels">
                <span>Fine detail</span>
                <span>Broad strokes</span>
              </div>
            </div>
            {world && (
              <div className="prompt-control">
                <label htmlFor="magic-text">
                  Describe the magic <span>optional</span>
                </label>
                <textarea
                  id="magic-text"
                  aria-label="Describe the magic"
                  rows={3}
                  maxLength={200}
                  value={text}
                  disabled={disabled}
                  placeholder={selectedForce.example}
                  onChange={(e) => setText(e.target.value)}
                />
                <span className="char-count">{text.length}/200</span>
              </div>
            )}
            <div className="generate-section">
              <button
                className="generate-button"
                disabled={!canGenerate}
                onClick={() => void generate()}
              >
                {busy ? (
                  <LoaderCircle size={18} className="spin" />
                ) : (
                  <Sparkles size={18} />
                )}
                <span>{world ? "Apply magic" : "Bring world to life"}</span>
                {!busy && <ArrowRight size={17} />}
              </button>
              <p>
                {world
                  ? "Each change becomes part of your world."
                  : "Your sketch guides the world’s composition."}
              </p>
            </div>
            {busy && (
              <div className="progress" role="status">
                <span>{job?.stage || "Preparing generation"}</span>
                <div className="progress-track">
                  <div style={{ width: job?.total ? progress + "%" : "20%" }} />
                </div>
                {Boolean(job?.total) && (
                  <small>
                    {job?.step} / {job?.total} steps
                  </small>
                )}
              </div>
            )}
            {error && (
              <div className="error" role="alert">
                <AlertCircle size={16} />
                <span>{error}</span>
              </div>
            )}
          </aside>
        </div>
        <footer className="page-footer">
          <span>
            <Sparkles size={13} />A little imagination changes everything.
          </span>
          <span>Made for Banana Hacks 2026</span>
        </footer>
      </main>
    </div>
  );
}
