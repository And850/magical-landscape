export type Point = { x: number; y: number };
export function canvasPoint(
  clientX: number,
  clientY: number,
  rect: { left: number; top: number; width: number; height: number },
  size: number,
): Point {
  return {
    x: ((clientX - rect.left) * size) / rect.width,
    y: ((clientY - rect.top) * size) / rect.height,
  };
}
export function paintSegment(
  pixels: Uint8Array,
  size: number,
  start: Point,
  end: Point,
  width: number,
  value: number,
) {
  const dx = end.x - start.x,
    dy = end.y - start.y;
  const samples = Math.max(
    1,
    Math.ceil(Math.hypot(dx, dy) / Math.max(1, width / 4)),
  );
  const radius = width / 2;
  for (let i = 0; i <= samples; i++) {
    const x = start.x + (dx * i) / samples,
      y = start.y + (dy * i) / samples;
    const x0 = Math.max(0, Math.floor(x - radius)),
      x1 = Math.min(size - 1, Math.ceil(x + radius));
    const y0 = Math.max(0, Math.floor(y - radius)),
      y1 = Math.min(size - 1, Math.ceil(y + radius));
    for (let yy = y0; yy <= y1; yy++)
      for (let xx = x0; xx <= x1; xx++) {
        if ((xx - x) ** 2 + (yy - y) ** 2 <= radius ** 2)
          pixels[yy * size + xx] = value;
      }
  }
}
export function labelPixels(labels: Uint8Array): Uint8ClampedArray {
  const pixels = new Uint8ClampedArray(labels.length * 4);
  labels.forEach((v, i) => {
    pixels[i * 4] = v;
    pixels[i * 4 + 1] = v;
    pixels[i * 4 + 2] = v;
    pixels[i * 4 + 3] = 255;
  });
  return pixels;
}
export function hasPaint(labels: Uint8Array) {
  return labels.some((v) => v !== 0);
}
export async function pngBlob(labels: Uint8Array, size: number): Promise<Blob> {
  const c = document.createElement("canvas");
  c.width = c.height = size;
  c.getContext("2d")!.putImageData(
    new ImageData(labelPixels(labels), size, size),
    0,
    0,
  );
  return new Promise((resolve, reject) =>
    c.toBlob(
      (b) => (b ? resolve(b) : reject(new Error("Could not export drawing."))),
      "image/png",
    ),
  );
}
