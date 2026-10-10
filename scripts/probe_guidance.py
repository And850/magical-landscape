"""Compare prompt-only diffusion against sketch guidance to diagnose flat output."""

import sys, time, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image
from backend.engine import DiffusionEngine, ROOT, STYLE
from backend.imaging import prepare_landscape

engine = DiffusionEngine(384, 15)
labels = Image.open(ROOT / ".runtime/benchmark/labels-a.png")
color, edges, description = prepare_landscape(labels, 384)
prompt = (
    "An intricate magical fantasy valley, lush forest, ancient stone tower, winding river, misty mountains, cinematic oil painting, richly textured natural landscape. "
    + description
)
for scale in (0.0, 0.25):
    start = time.monotonic()
    image = engine._run(
        "create",
        41,
        dict(
            image=color,
            control_image=edges,
            prompt=prompt,
            strength=1.0,
            controlnet_conditioning_scale=scale,
            control_guidance_end=0.6,
        ),
        lambda stage, step, total: print(stage, step, total, flush=True),
    )
    image.save(ROOT / f".runtime/benchmark/probe-{scale}.png")
    print("PROBE", scale, time.monotonic() - start, flush=True)
engine.unload()
