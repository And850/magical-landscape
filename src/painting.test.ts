import { describe, it, expect } from "vitest";
import { paintSegment, canvasPoint, labelPixels, hasPaint } from "./painting";

describe("semantic painting", () => {
  it("keeps exact integer IDs and lets later strokes replace earlier ones", () => {
    const labels = new Uint8Array(64 * 64);
    paintSegment(labels, 64, { x: 20, y: 20 }, { x: 40, y: 20 }, 8, 4);
    paintSegment(labels, 64, { x: 30, y: 20 }, { x: 30, y: 20 }, 8, 6);
    expect(labels[20 * 64 + 30]).toBe(6);
    expect(labels[20 * 64 + 22]).toBe(4);
    expect(labels[0]).toBe(0);
    expect(new Set(labels)).toEqual(new Set([0, 4, 6]));
    const pixels = labelPixels(labels);
    expect([
      ...pixels.slice((20 * 64 + 30) * 4, (20 * 64 + 30) * 4 + 4),
    ]).toEqual([6, 6, 6, 255]);
  });
  it("covers a fast pointer movement without gaps and clips at edges", () => {
    const mask = new Uint8Array(64 * 64);
    paintSegment(mask, 64, { x: -5, y: 32 }, { x: 70, y: 32 }, 4, 255);
    expect([...mask.slice(32 * 64, 33 * 64)]).toEqual(Array(64).fill(255));
    expect(hasPaint(mask)).toBe(true);
    expect(hasPaint(new Uint8Array(64 * 64))).toBe(false);
  });
  it("maps resized and high-density canvas coordinates into backing pixels", () => {
    const rect = { left: 100, top: 50, width: 256, height: 256 };
    expect(canvasPoint(228, 178, rect, 512)).toEqual({ x: 256, y: 256 });
    expect(canvasPoint(100, 50, rect, 384)).toEqual({ x: 0, y: 0 });
  });
});
