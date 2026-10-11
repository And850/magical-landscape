import { test, expect } from "@playwright/test";

async function draw(page: any) {
  const box = await page.getByLabel("Landscape canvas").boundingBox();
  await page.mouse.move(box.x + box.width * 0.25, box.y + box.height * 0.7);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.75, box.y + box.height * 0.7, {
    steps: 10,
  });
  await page.mouse.up();
}

test("draw, generate, select forces, recover from failure, and restore on refresh", async ({
  page,
}) => {
  let revision = 0,
    jobCount = 0,
    failNext = false;
  const world = () => ({
    id: "test-world",
    revision,
    size: 512,
    description: "fantasy landscape",
    image_url: "/api/worlds/test-world/image?revision=" + revision,
  });
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/health")
      return route.fulfill({
        json: {
          status: "ok",
          models_ready: true,
          device: "mps",
          busy: false,
          size: 512,
          steps: 20,
          verified: true,
        },
      });
    if (url.pathname.endsWith("/image"))
      return route.fulfill({
        contentType: "image/svg+xml",
        body: '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512"><rect width="512" height="512" fill="#344552"/><path d="M0 350L140 170L310 390L440 230L512 380V512H0" fill="#527565"/></svg>',
      });
    if (route.request().method() === "POST") {
      jobCount++;
      return route.fulfill({
        status: 202,
        json: { job_id: String(jobCount), world_id: "test-world" },
      });
    }
    if (url.pathname.startsWith("/api/jobs/")) {
      if (failNext) {
        failNext = false;
        return route.fulfill({
          json: {
            id: String(jobCount),
            status: "failed",
            stage: "Generation failed",
            step: 1,
            total: 20,
            result: null,
            error: "Try a smaller painted region.",
          },
        });
      }
      revision++;
      return route.fulfill({
        json: {
          id: String(jobCount),
          status: "succeeded",
          stage: "World ready",
          step: 20,
          total: 20,
          result: world(),
          error: null,
        },
      });
    }
    return route.fulfill({ json: world() });
  });
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Bring world to life" }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: /^Ground\b/ }),
  ).toBeVisible();
  await draw(page);
  await expect(
    page.getByRole("button", { name: "Bring world to life" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Bring world to life" }).click();
  await expect(page.getByRole("button", { name: "Apply magic" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Apply magic" }),
  ).toBeDisabled();
  await draw(page);
  await page.getByRole("button", { name: /^Water\b/ }).click();
  await expect(
    page.getByRole("button", { name: "Apply magic" }),
  ).toBeDisabled();
  await draw(page);
  await page.getByLabel("Describe the magic").fill("a shimmering river");
  failNext = true;
  await page.getByRole("button", { name: "Apply magic" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Try a smaller painted region.",
  );
  await expect(page.getByLabel("Describe the magic")).toHaveValue(
    "a shimmering river",
  );
  await expect(page.getByRole("button", { name: "Apply magic" })).toBeEnabled();
  await page.getByRole("button", { name: "Apply magic" }).click();
  await expect(page.getByLabel("Describe the magic")).toHaveValue("");
  await expect(
    page.getByRole("button", { name: "Apply magic" }),
  ).toBeDisabled();
  await page.reload();
  await expect(page.getByRole("button", { name: "Apply magic" })).toBeVisible();
  await expect(page.getByRole("button", { name: /undo/i })).toHaveCount(0);
  for (const force of ["Time", "Light"]) {
    await page.getByRole("button", { name: new RegExp(`^${force}\\b`) }).click();
    await draw(page);
    await page.getByRole("button", { name: "Apply magic" }).click();
    await expect(page.getByRole("button", { name: "Apply magic" })).toBeDisabled();
    await expect(page.getByLabel("Describe the magic")).toHaveValue("");
  }
  await page.getByRole("button", { name: "Reset canvas" }).click();
  await expect(page.getByRole("button", { name: "Bring world to life" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Apply magic" })).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("button", { name: "Bring world to life" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Apply magic" })).toHaveCount(0);
});
