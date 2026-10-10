// @vitest-environment jsdom
import { afterEach, beforeEach, describe, it, expect, vi } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import App from "./App";

const state = { revision: 0, job: 0, fail: false };
beforeEach(() => {
  state.revision = 0;
  state.job = 0;
  state.fail = false;
  localStorage.clear();
  vi.stubGlobal(
    "ImageData",
    class {
      data: Uint8ClampedArray;
      width: number;
      height: number;
      constructor(data: Uint8ClampedArray, w: number, h: number) {
        this.data = data;
        this.width = w;
        this.height = h;
      }
    },
  );
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(
    () => ({ clearRect() {}, drawImage() {}, putImageData() {} }) as any,
  );
  vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation((cb) =>
    cb(new Blob(["png"], { type: "image/png" })),
  );
  HTMLCanvasElement.prototype.setPointerCapture = () => {};
  vi.stubGlobal(
    "PointerEvent",
    class extends MouseEvent {
      pointerId = 1;
    },
  );
  vi.spyOn(
    HTMLCanvasElement.prototype,
    "getBoundingClientRect",
  ).mockReturnValue({
    left: 0,
    top: 0,
    width: 512,
    height: 512,
    bottom: 512,
    right: 512,
    x: 0,
    y: 0,
    toJSON() {},
  });
  vi.stubGlobal(
    "Image",
    class {
      width = 512;
      height = 512;
      onload: (() => void) | null = null;
      set src(v: string) {
        queueMicrotask(() => this.onload?.());
      }
    },
  );
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, options?: RequestInit) => {
      const world = () => ({
        id: "test-world",
        revision: state.revision,
        size: 512,
        description: "fantasy landscape",
        image_url: "/api/worlds/test-world/image?revision=" + state.revision,
      });
      let payload: any;
      if (url === "/api/health")
        payload = {
          status: "ok",
          models_ready: true,
          device: "mps",
          busy: false,
          size: 512,
          steps: 20,
          verified: true,
        };
      else if (options?.method === "POST") {
        state.job++;
        payload = { job_id: String(state.job), world_id: "test-world" };
      } else if (url.startsWith("/api/jobs/")) {
        if (state.fail) {
          state.fail = false;
          payload = {
            id: String(state.job),
            status: "failed",
            stage: "Generation failed",
            step: 1,
            total: 20,
            result: null,
            error: "Try a smaller painted region.",
          };
        } else {
          state.revision++;
          payload = {
            id: String(state.job),
            status: "succeeded",
            stage: "World ready",
            step: 20,
            total: 20,
            result: world(),
            error: null,
          };
        }
      } else payload = world();
      return { ok: true, json: async () => payload };
    }),
  );
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
function draw() {
  const canvas = screen.getByLabelText("Landscape canvas");
  fireEvent.pointerDown(canvas, { button: 0, clientX: 120, clientY: 350 });
  fireEvent.pointerMove(canvas, { clientX: 260, clientY: 350 });
  fireEvent.pointerUp(canvas);
}

describe("world workflow", () => {
  it("requires painting, clears masks when changing force, keeps failed work, and restores current world", async () => {
    const r = render(<App />);
    await waitFor(() =>
      expect(screen.getByText("Local image generation")).toBeTruthy(),
    );
    const create = screen.getByRole("button", {
      name: "Bring world to life",
    }) as HTMLButtonElement;
    expect(create.disabled).toBe(true);
    draw();
    expect(create.disabled).toBe(false);
    fireEvent.click(create);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Apply magic" })).toBeTruthy(),
    );
    const apply = () =>
      screen.getByRole("button", { name: "Apply magic" }) as HTMLButtonElement;
    expect(apply().disabled).toBe(true);
    draw();
    expect(apply().disabled).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Water" }));
    expect(apply().disabled).toBe(true);
    draw();
    fireEvent.change(screen.getByLabelText("Describe the magic"), {
      target: { value: "a shimmering river" },
    });
    state.fail = true;
    fireEvent.click(apply());
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toContain(
        "Try a smaller painted region.",
      ),
    );
    expect(
      (screen.getByLabelText("Describe the magic") as HTMLTextAreaElement)
        .value,
    ).toBe("a shimmering river");
    expect(apply().disabled).toBe(false);
    fireEvent.click(apply());
    await waitFor(() =>
      expect(
        (screen.getByLabelText("Describe the magic") as HTMLTextAreaElement)
          .value,
      ).toBe(""),
    );
    expect(apply().disabled).toBe(true);
    expect(state.revision).toBe(2);
    r.unmount();
    render(<App />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Apply magic" })).toBeTruthy(),
    );
    expect(screen.queryByRole("button", { name: /undo/i })).toBeNull();
  });
});

it("clears a missing persisted job instead of reconnecting forever", async () => {
  localStorage.setItem("magical-landscape.job", "forgotten");
  const existing = globalThis.fetch;
  vi.stubGlobal("fetch", async (url: string, options?: RequestInit) => {
    if (url === "/api/jobs/forgotten")
      return {
        ok: false,
        status: 404,
        json: async () => ({ detail: "Job not found." }),
      };
    return existing(url, options);
  });
  render(<App />);
  await waitFor(() =>
    expect(screen.getByRole("alert").textContent).toContain("Job not found."),
  );
  await waitFor(() =>
    expect(
      screen.getByLabelText("Landscape canvas").getAttribute("aria-disabled"),
    ).toBe("false"),
  );
  expect(localStorage.getItem("magical-landscape.job")).toBeNull();
});

it("retains the saved world pointer during a transient restore failure", async () => {
  localStorage.setItem("magical-landscape.world", "test-world");
  const existing = globalThis.fetch;
  vi.stubGlobal("fetch", async (url: string, options?: RequestInit) => {
    if (url === "/api/worlds/test-world")
      throw new Error("Temporary connection failure");
    return existing(url, options);
  });
  render(<App />);
  await waitFor(() =>
    expect(screen.getByRole("alert").textContent).toContain(
      "Temporary connection failure",
    ),
  );
  expect(localStorage.getItem("magical-landscape.world")).toBe("test-world");
});

it("resolves completed jobs to the latest world before the next transformation", async () => {
  localStorage.setItem("magical-landscape.job", "old-job");
  const existing = globalThis.fetch;
  state.revision = 2;
  let submittedRevision = "";
  vi.stubGlobal("fetch", async (url: string, options?: RequestInit) => {
    if (url === "/api/jobs/old-job")
      return {
        ok: true,
        json: async () => ({
          id: "old-job",
          status: "succeeded",
          stage: "Done",
          step: 20,
          total: 20,
          error: null,
          result: {
            id: "test-world",
            revision: 1,
            size: 512,
            description: "world",
            image_url: "/api/worlds/test-world/image?revision=1",
          },
        }),
      };
    if (options?.method === "POST")
      submittedRevision = String(
        (options.body as FormData).get("expected_revision"),
      );
    return existing(url, options);
  });
  render(<App />);
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Apply magic" })).toBeTruthy(),
  );
  draw();
  fireEvent.click(screen.getByRole("button", { name: "Apply magic" }));
  await waitFor(() => expect(submittedRevision).toBe("2"));
});

it("resets a generated world to a blank sketch and does not restore it on refresh", async () => {
  const view = render(<App />);
  await waitFor(() =>
    expect(screen.getByText("Local image generation")).toBeTruthy(),
  );
  draw();
  fireEvent.click(screen.getByRole("button", { name: "Bring world to life" }));
  expect(
    (screen.getByRole("button", { name: "Reset canvas" }) as HTMLButtonElement)
      .disabled,
  ).toBe(true);
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Apply magic" })).toBeTruthy(),
  );
  draw();
  fireEvent.change(screen.getByLabelText("Describe the magic"), {
    target: { value: "old roots" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Reset canvas" }));
  expect(screen.queryByRole("button", { name: "Apply magic" })).toBeNull();
  expect(screen.queryByLabelText("Describe the magic")).toBeNull();
  expect(
    (
      screen.getByRole("button", {
        name: "Bring world to life",
      }) as HTMLButtonElement
    ).disabled,
  ).toBe(true);
  expect(localStorage.getItem("magical-landscape.world")).toBeNull();
  expect(localStorage.getItem("magical-landscape.job")).toBeNull();
  view.unmount();
  render(<App />);
  await waitFor(() =>
    expect(screen.getByText("Local image generation")).toBeTruthy(),
  );
  expect(screen.queryByRole("button", { name: "Apply magic" })).toBeNull();
  draw();
  fireEvent.click(screen.getByRole("button", { name: "Reset canvas" }));
  expect(
    (
      screen.getByRole("button", {
        name: "Bring world to life",
      }) as HTMLButtonElement
    ).disabled,
  ).toBe(true);
});
