# Magical Landscape

Draw a cause. Discover a consequence.

![A locally generated fantasy landscape](docs/assets/world-a.png)

[60-second results reel](docs/assets/demo.mp4) · [Submission write-up](docs/submission.md)

A local creative app for Banana Hacks 2026. Paint a landscape, turn it into fantasy art, then evolve selected regions with Time, Water, or Light. Each successful transformation becomes the current world. No undo, accounts, hosted inference, or paid API.

## Run

Requires an Apple Silicon Mac, Python 3, Node.js 22.12 or newer, and internet access for initial installation. Setup downloads an isolated Python 3.11 runtime and approximately 6 GB of model artifacts. Reserve at least 12 GB of free disk space for the environment and caches.

```sh
./scripts/setup.sh
./scripts/run.sh
```

Open http://127.0.0.1:5173 in your browser. The backend binds to 127.0.0.1:8000. After setup, generation uses cached models without calling an external service.

If the environment is already installed, only run `./scripts/run.sh`. Stop existing servers before starting a second copy. `Ctrl+C` stops the launcher and backend.

## Interaction

1. Paint regions with **Sky, Ground, Hills/Mountains, Water, Trees/Vegetation, Rocks, and Structures**. Unpainted space is sky. Later strokes replace earlier labels. At least one non-Sky region is required.
2. Select **Bring world to life**. The drawing's colors, boundaries, and semantic positions guide the illustration.
3. Choose **Time**, **Water**, or **Light**, paint the region to change, optionally describe its magic, and select **Apply magic**.
4. Repeat on the current world. Changing force clears pending strokes and optional text. **Clear strokes** clears unapplied marks only. **Reset canvas** starts over with a blank sketch, clearing the artwork, pending strokes, optional text, and saved world selection. Reset is disabled during generation.

Brush sizes range from 8 to 96 pixels, default 32. Optional text is limited to 200 characters. Drawing and submission are disabled during generation; the app shows actual diffusion-step progress. A failed generation retains the image, strokes, and text. Refresh restores the current world and resumes a known pending job.

## Magical forces

- **Time:** mature plants, spreading roots/vines/moss, weathered structures, nature reclaiming ruins.
- **Water:** primarily floods, pools, carved channels, and submerged structures, with modest vegetation at wet edges.
- **Light:** magical illumination, luminous blooms, awakened structures, glowing symbols, and suggested hidden paths.

These effects are artistic interpretations, not physics or gameplay. The current image is the input to each edit. Changes outside the expanded painted region are preserved exactly.

## Local generation

React/TypeScript/Vite and Canvas 2D frontend; FastAPI/Pillow/OpenCV/PyTorch/Diffusers backend.

- Initial generation: Stable Diffusion 1.5 with Canny ControlNet, using `StableDiffusionControlNetImg2ImgPipeline`.
- Evolution: DreamShaper 8 Inpainting (an art-focused Stable Diffusion fine-tune), using `StableDiffusionInpaintPipeline`.
- Inpainting crops around the selected mask with 64 pixels of context for Time and 32 for Water/Light so small edits receive useful detail. Masks expand by 12 pixels. Time also extends upward by one sixth of the canvas height (64 pixels at 384, 85 at 512), allowing nearby canopies to grow. All masks feather inward over 8 pixels. Compositing leaves everything outside the expanded mask untouched.
- One pipeline and one job are resident at a time; ControlNet is unloaded before inpainting loads.
- Metal is selected automatically when available. Otherwise the interface explicitly shows slower CPU generation; CPU computes in float32.
- Native Metal default: 512 × 512, 20 steps. Reduced/CPU profile: 384 × 384, 15 steps. The drawing label map remains 512 × 512 and is resized with nearest-neighbor sampling. Composition guidance is approximate; individual objects and exact proportions are not guaranteed.
- Initial defaults were tuned after flat-image failures: strength **1.0**, ControlNet scale **0.30**, guidance ending at **0.6**. Time uses strength **0.85** and keeps the profile’s actual diffusion-step count; Water/Light use strength **0.95**. Both pipelines use guidance scale **7**. Time prompts vegetation and weathered existing surfaces, rather than asking for new ruins or structures.
- Thin, elongated water regions include a coarse river route rather than only their centroid. Only painted categories appear; dominant regions are identified without inventing unpainted terrain. The fixed art prompt and selected force come before optional text. Stable Diffusion's text encoder has a finite token budget, so unusually dense descriptions may be truncated.

Model revisions are pinned in `model-revisions.json`; Python and Node dependencies are locked. Stable Diffusion 1.5 and DreamShaper 8 Inpainting use CreativeML OpenRAIL-M; Canny ControlNet is labeled OpenRAIL on its model card. The linked model cards contain the license terms. Model output checking remains enabled.

## Verify

```sh
.venv/bin/python -m pytest backend/tests -q
npm test
npm run build
.venv/bin/python scripts/benchmark.py
# With the app running, exercise real generation through the API:
.venv/bin/python scripts/verify_live.py
```

The benchmark generates two different layouts and cumulative Time → Water → Light images in `.runtime/benchmark/`, recording timings and the selected profile. Inspect the images as well as the timings. It tries the reduced profile if the default fails or warmed edits exceed 120 seconds.

Final verification on October 11 passed 26 backend tests, 9 frontend tests, the production build, and the Playwright browser workflow at a 1440 × 1000 viewport with 2× pixel density. Browser coverage includes drawing, generation state, all three forces, failed-edit retry, refresh restoration, and reset. Real-model inference is checked separately through the API; the browser workflow test uses stubbed responses. Run `npx playwright install chromium` before `npm run test:e2e`. Browser screenshots of the create and restored-world stages were visually inspected.

## Measured results

On October 11, an Apple M1 Pro with 16 GB unified memory completed the full offline API workflow on **Metal (MPS), float16, 512 × 512 / 20 steps**. Initial landscapes took **47.88 and 32.80 seconds**; cumulative Time, Water, and Light took **23.83, 21.84, and 20.81 seconds**. All edits changed the image and preserved every pixel outside the expanded blend mask. These are single-run wall-clock measurements, not a broad performance guarantee. See [Metal measurements](docs/assets/metal-measurements.json). Visual review found more vegetation with Time and golden illumination with Light, but Water also introduced an unexpected tower.

Actual offline CPU generation at 384 × 384 / 15 steps produced two different landscapes in 87–91 seconds. Final regional edits completed in 35.54–39.22 seconds; measurements are in [measurements.json](docs/assets/measurements.json). The API verification checks every pixel outside the expanded mask after each successful edit.

DreamShaper force-edit probes completed in 39–42 seconds with 4.1–4.8 GiB peak process memory. See [the model comparison](docs/model-comparison.md) for images, settings, and limitations.

The approved 60-second, 1080p results reel uses Stable Diffusion 1.5 + Canny for creation and DreamShaper 8 Inpainting for cumulative edits. Its CPU timings were 85.31 seconds for creation, 46.66 for Time, 33.06 for Water, and 35.75 for Light; see [demo measurements](docs/assets/demo-measurements.json). Generation waits are explicitly shortened. The second slide is labeled **reconstructed composition sketch**: it was redrawn afterward to match the initial AI landscape and is not the actual generation input. The AI outputs are genuine and were not regenerated for that sketch revision. The soundtrack is an original synthesized ambient score. The reel is not a browser interaction recording. Force effects vary by seed, region, and image context; unwanted objects and inconsistent tree growth remain possible.

## Storage and recovery

`.runtime/worlds/` contains each world's original label map and current image/metadata; `.runtime/jobs/` journals jobs. Only the current image is served. Metadata replacement is the commit boundary. Committed job IDs reconcile interrupted success journals; interrupted inference fails without replacing the world. Image and metadata files, model caches, and virtual environments are ignored by Git.

World IDs and pending job IDs are stored in the browser's local storage. Old image URLs and stale transformation revisions return 409. Malformed PNGs, invalid labels, empty/mismatched masks, unknown forces, and overlong text are rejected. Additional submissions are rejected while inference is occupied. Local Host and Origin checks reject requests from foreign websites.

## Submission

See `docs/submission.md` for the write-up and `docs/demo-script.md` for the demonstration sequence. No automatic portal submission or organizer message is sent.

The [published schedule](https://www.bananahacks.tech/schedule) says Sunday October 11 at 23:59 EDT (**Monday October 12 at 05:59 in Madrid**), while the [rules](https://www.bananahacks.tech/code-of-conduct) say AoE. Plan around the earlier EDT deadline and confirm the discrepancy in the organizer channel.

## Credits

- [Stable Diffusion 1.5](https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-v1-5)
- [DreamShaper 8 Inpainting](https://huggingface.co/Lykon/dreamshaper-8-inpainting) — selected force-edit model, CreativeML OpenRAIL-M.
- [Stable Diffusion inpainting](https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-inpainting) — previous force-edit model and comparison baseline.
- [ControlNet Canny](https://huggingface.co/lllyasviel/control_v11p_sd15_canny)
- [Diffusers](https://github.com/huggingface/diffusers), [PyTorch](https://pytorch.org/), [FastAPI](https://fastapi.tiangolo.com/), [React](https://react.dev/), [Vite](https://vite.dev/), [OpenCV](https://opencv.org/), [Pillow](https://python-pillow.org/), [Lucide](https://lucide.dev/).
- Codex assisted with planning, implementation, and testing. The app itself uses pretrained local diffusion models; no custom model was trained.
