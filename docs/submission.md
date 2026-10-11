# Magical Landscape

**One-paragraph description:** Magical Landscape turns drawing into a way to change an imaginary world. Paint its initial geography with labeled brushes, bring it to life as a fantasy illustration, then apply Time, Water, or Light to selected regions. Time encourages vegetation and weathering, Water suggests floods and channels, and Light adds magical illumination. Every successful transformation becomes the starting point for the next.

## What we built and why

Most sketch-to-image tools polish a drawing. Magical Landscape explores a different interaction: draw a cause and discover a consequence. It is a small creative playground for people who want to shape a magical environment without drawing every detail themselves.

Users establish the composition with seven semantic brushes: Sky, Ground, Hills/Mountains, Water, Trees/Vegetation, Rocks, and Structures. Local Stable Diffusion with ControlNet interprets the sketch's regions, boundaries, and positions as an illustrated landscape.

Then users paint where magic should act. Time matures plants and lets nature reclaim structures. Water mainly floods and carves channels, with some life at its edges. Light illuminates and awakens plants and ancient structures. Optional text adds detail to a selected force.

The engineering challenge is preserving a recognizable, cumulative world rather than generating unrelated pictures. Each edit uses the current image, a region mask, and a force-specific prompt. Mask expansion and feathered compositing preserve pixels outside the selected neighborhood exactly. A serialized inference worker, atomic image commits, revision checking, and restart recovery keep failures from replacing the world.

The frontend uses React, TypeScript, and Canvas 2D. The backend uses FastAPI, PyTorch, Diffusers, Pillow, and OpenCV. Models run locally; there is no paid inference API. One pipeline is resident at a time to reduce memory use. The effects are artistic interpretations rather than physical simulation.

We used pretrained Stable Diffusion 1.5, DreamShaper 8 Inpainting, and Canny ControlNet. Model and library credits are in the README. Codex assisted with planning, coding, and testing. No custom model was trained.

## Submission links

Repository: https://github.com/And850/magical-landscape

Demo: [60-second local-generation results reel](https://github.com/And850/magical-landscape/blob/main/docs/assets/demo.mp4).

Direct video file: https://raw.githubusercontent.com/And850/magical-landscape/main/docs/assets/demo.mp4

The reel shows genuine cumulative local outputs, with generation waits shortened. Its second slide is explicitly labeled as a reconstructed composition sketch, drawn afterward to match the generated landscape. It is a captioned results reel, not a browser interaction recording. Browser workflow tests and native Metal inference were checked separately. Generative effects remain approximate and can introduce unexpected objects.
