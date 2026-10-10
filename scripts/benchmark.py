"""Live local acceptance probe. Writes genuine outputs for visual inspection."""

import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image, ImageDraw
from backend.engine import DiffusionEngine, ROOT
from backend.imaging import prepare_mask
from scripts.benchmark_fixtures import layout
import io

logging.basicConfig(level=logging.INFO)
out = ROOT / ".runtime" / "benchmark"
out.mkdir(parents=True, exist_ok=True)


def progress(stage, step, total):
    print(f"{stage}: {step}/{total}", flush=True)


import torch

profiles = [(512, 20), (384, 15)] if torch.backends.mps.is_available() else [(384, 15)]
for size, steps in profiles:
    engine = DiffusionEngine(size, steps)
    records = []
    try:
        labels = layout()
        labels.save(out / "labels-a.png")
        start = time.monotonic()
        image, description = engine.create(labels, 41, progress)
        elapsed = time.monotonic() - start
        image.save(out / f"world-a-{size}.png")
        records.append({"stage": "initial-a", "seconds": round(elapsed, 2)})
        labels = layout(True)
        labels.save(out / "labels-b.png")
        start = time.monotonic()
        second, _ = engine.create(labels, 42, progress)
        second.save(out / f"world-b-{size}.png")
        records.append(
            {"stage": "initial-b", "seconds": round(time.monotonic() - start, 2)}
        )
        for i, force in enumerate(("growth_time", "water", "light")):
            painted = Image.new("L", (size, size))
            d = ImageDraw.Draw(painted)
            # A generous selected region including structures and their surroundings.
            d.ellipse(
                (
                    int(0.48 * size),
                    int(0.45 * size),
                    int(0.95 * size),
                    int(0.90 * size),
                ),
                fill=255,
            )
            stream = io.BytesIO()
            painted.save(stream, format="PNG")
            mask, blend = prepare_mask(stream.getvalue(), size, force=force)
            start = time.monotonic()
            image = engine.transform(image, mask, blend, force, "", 100 + i, progress)
            image.save(out / f"{force}-{size}.png")
            records.append(
                {"stage": force, "seconds": round(time.monotonic() - start, 2)}
            )
        result = {
            "size": size,
            "steps": steps,
            "device": engine.device,
            "verified": False,
            "records": records,
            "note": "Actual outputs generated; visual review required before verified=true.",
        }
        (out / f"report-{size}.json").write_text(json.dumps(result, indent=2))
        # Loading overhead included conservatively; a slow first loading step does not decide the profile.
        warm = [r["seconds"] for r in records if r["stage"] in ("water", "light")]
        if max(warm) <= 120 or size == 384:
            (ROOT / ".runtime" / "profile.json").write_text(
                json.dumps(result, indent=2)
            )
            print(json.dumps(result), flush=True)
            break
        print("Selecting reduced profile due to warmed latency.", flush=True)
    except Exception as exc:
        (out / f"failure-{size}.txt").write_text(str(exc))
        print(f"Profile {size} failed: {exc}", flush=True)
        if size == 384:
            raise
    finally:
        engine.unload()
