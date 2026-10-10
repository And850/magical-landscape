import { useEffect, useRef, useCallback, type PointerEvent } from "react";
import { canvasPoint, paintSegment, type Point } from "./painting";
export const TERRAIN = [
  { name: "Sky", color: "#a1bbd3", hint: "Open sky & atmosphere" },
  { name: "Ground", color: "#79654b", hint: "Land & terrain" },
  { name: "Hills/Mountains", color: "#6d7a6f", hint: "Elevated terrain" },
  { name: "Water", color: "#3e7896", hint: "Rivers, lakes & seas" },
  { name: "Trees/Vegetation", color: "#426748", hint: "Forests & foliage" },
  { name: "Rocks", color: "#85888a", hint: "Boulders & formations" },
  { name: "Structures", color: "#9f8f7b", hint: "Buildings, bridges & ruins" },
];
const TERRAIN_RGB = TERRAIN.map(t => t.color.slice(1).match(/\w\w/g)!.map(h => parseInt(h,16)));
export function PaintingCanvas({
  pixels,
  size,
  version,
  value,
  brushSize,
  artwork,
  forceColor,
  disabled,
  onPaint,
}: {
  pixels: Uint8Array;
  size: number;
  version: number;
  value: number;
  brushSize: number;
  artwork: HTMLImageElement | null;
  forceColor: string;
  disabled: boolean;
  onPaint: () => void;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const last = useRef<Point | null>(null);
  const render = useCallback(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext("2d")!;
    ctx.clearRect(0, 0, size, size);
    if (artwork) ctx.drawImage(artwork, 0, 0, size, size);
    const buffer = new Uint8ClampedArray(size * size * 4);
    const tint = forceColor.match(/\w\w/g)!.map((h) => parseInt(h, 16));
    pixels.forEach((v, i) => {
      const color = artwork
        ? tint
        : TERRAIN_RGB[v];
      buffer[i * 4] = color[0];
      buffer[i * 4 + 1] = color[1];
      buffer[i * 4 + 2] = color[2];
      buffer[i * 4 + 3] = artwork ? (v ? 105 : 0) : 255;
    });
    const overlay = document.createElement("canvas");
    overlay.width = overlay.height = size;
    overlay
      .getContext("2d")!
      .putImageData(new ImageData(buffer, size, size), 0, 0);
    ctx.drawImage(overlay, 0, 0);
  }, [pixels, size, artwork, forceColor]);
  useEffect(() => {
    render();
  }, [render, version]);
  useEffect(() => {
    if (disabled) last.current = null;
  }, [disabled]);
  const move = (e: PointerEvent<HTMLCanvasElement>, first = false) => {
    if (disabled || (!first && !last.current)) return;
    const p = canvasPoint(
      e.clientX,
      e.clientY,
      e.currentTarget.getBoundingClientRect(),
      size,
    );
    paintSegment(pixels, size, last.current || p, p, brushSize, value);
    last.current = p;
    onPaint();
  };
  return (
    <canvas
      ref={ref}
      width={size}
      height={size}
      aria-label="Landscape canvas"
      aria-disabled={disabled}
      className={disabled ? "canvas busy" : "canvas"}
      onPointerDown={(e) => {
        if (disabled || e.button !== 0) return;
        e.currentTarget.setPointerCapture(e.pointerId);
        last.current = null;
        move(e, true);
      }}
      onPointerMove={(e) => move(e)}
      onPointerUp={() => {
        last.current = null;
      }}
      onPointerCancel={() => {
        last.current = null;
      }}
      onLostPointerCapture={() => {
        last.current = null;
      }}
    />
  );
}
