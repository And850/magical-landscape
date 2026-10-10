export type Force = "growth_time" | "water" | "light";
export type World = {
  id: string;
  revision: number;
  size: number;
  description: string;
  image_url: string;
};
export type Job = {
  id: string;
  world_id?: string;
  status: "queued" | "running" | "succeeded" | "failed";
  stage: string;
  step: number;
  total: number;
  result: World | null;
  error: string | null;
};
export type Health = {
  status: string;
  models_ready: boolean;
  device: "mps" | "cpu";
  busy: boolean;
  size: number;
  steps: number;
  verified: boolean;
};
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function request<T>(
  url: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) {
    const detail = payload.detail;
    throw new ApiError(
      typeof detail === "string"
        ? detail
        : "The request could not be processed. Check your drawing and try again.",
      response.status,
    );
  }
  return payload as T;
}
export function loadArtwork(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () =>
      reject(
        new Error("Could not load the current world. Refresh to reconnect."),
      );
    img.src = url;
  });
}
