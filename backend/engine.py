"""Single-resident local diffusion pipelines. No hosted inference."""

import gc
import json
import logging
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path(os.environ.get("MAGICAL_DATA_DIR", ROOT / ".runtime")).resolve()
os.environ.setdefault("HF_HOME", str(ROOT / ".runtime" / "huggingface"))
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

from PIL import Image
import numpy as np
from backend.imaging import (
    STYLE,
    prepare_landscape,
    force_prompt,
    composite,
    landscape_prompt,
)

MODELS = {
    "base": "stable-diffusion-v1-5/stable-diffusion-v1-5",
    "control": "lllyasviel/control_v11p_sd15_canny",
    "inpaint": "stable-diffusion-v1-5/stable-diffusion-inpainting",
}
NEGATIVE = "photograph, text, watermark, logo, blurry, low quality, distorted geometry"


def checked_image(output):
    if output.nsfw_content_detected and any(output.nsfw_content_detected):
        raise RuntimeError(
            "The generated output was rejected. Adjust your painted region or description and retry."
        )
    image = output.images[0].convert("RGB")
    arr = np.asarray(image)
    if not np.isfinite(arr).all() or arr.max() < 3:
        raise FloatingPointError(
            "Generation produced an invalid image; retrying with full precision."
        )
    return image


class DiffusionEngine:
    def __init__(self, size=512, steps=20, offline=True, device=None):
        self.size, self.steps, self.offline = size, steps, offline
        self.pipe = None
        self.mode = None
        import torch

        self.device = device or ("mps" if torch.backends.mps.is_available() else "cpu")
        self.precision = "float16" if self.device == "mps" else "float32"
        if self.device == "cpu":
            torch.set_num_threads(8)
        self.log = logging.getLogger("magical.generation")
        self.log.setLevel(logging.INFO)
        RUNTIME.mkdir(parents=True, exist_ok=True)
        log_path = RUNTIME / "generation.jsonl"
        if not any(
            getattr(h, "baseFilename", None) == str(log_path) for h in self.log.handlers
        ):
            handler = logging.FileHandler(log_path)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self.log.addHandler(handler)
        manifest = ROOT / ".runtime" / "model-manifest.json"
        self.revisions = json.loads(manifest.read_text()) if manifest.exists() else {}

    def unload(self):
        self.pipe = None
        self.mode = None
        gc.collect()
        import torch

        if torch.backends.mps.is_available():
            torch.mps.empty_cache()

    def load(self, mode, report):
        if self.mode == mode and self.pipe is not None:
            return
        import torch
        from diffusers import (
            ControlNetModel,
            StableDiffusionControlNetImg2ImgPipeline,
            StableDiffusionInpaintPipeline,
            DPMSolverMultistepScheduler,
        )

        if self.device == "mps" and not torch.backends.mps.is_available():
            raise RuntimeError(
                "Apple Metal GPU is unavailable. Run the backend natively on the Mac."
            )
        self.unload()
        report("Loading local image model", 0, 0)
        opts = dict(
            torch_dtype=getattr(torch, self.precision),
            local_files_only=self.offline,
            use_safetensors=True,
        )
        opts["variant"] = "fp16"

        def options(key):
            result = dict(opts)
            if self.revisions.get(key):
                result["revision"] = self.revisions[key]
            return result

        if mode == "create":
            control = ControlNetModel.from_pretrained(
                MODELS["control"], **options("control")
            )
            pipe = StableDiffusionControlNetImg2ImgPipeline.from_pretrained(
                MODELS["base"], controlnet=control, **options("base")
            )
        else:
            pipe = StableDiffusionInpaintPipeline.from_pretrained(
                MODELS["inpaint"], **options("inpaint")
            )
        if pipe.safety_checker is None:
            raise RuntimeError("Model output checker is missing. Re-run model setup.")
        pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config)
        pipe.enable_attention_slicing("max")
        pipe.to(self.device)
        pipe.set_progress_bar_config(disable=True)
        self.pipe, self.mode = pipe, mode

    def _run(self, mode, seed, kwargs, report):
        import torch

        start = time.monotonic()
        for attempt in range(2):
            self.load(mode, report)
            strength = kwargs.get("strength", 1)
            effective_steps = max(1, int(self.steps * strength))
            report("Generating illustration", 0, effective_steps)

            def callback(pipe, step, timestep, callback_kwargs):
                report("Generating illustration", step + 1, effective_steps)
                return callback_kwargs

            try:
                output = self.pipe(
                    **kwargs,
                    negative_prompt=NEGATIVE,
                    num_inference_steps=self.steps,
                    guidance_scale=7,
                    generator=torch.Generator(device="cpu").manual_seed(seed),
                    callback_on_step_end=callback,
                )
                image = checked_image(output)
                self.log.info(
                    json.dumps(
                        {
                            "mode": mode,
                            "seed": seed,
                            "size": self.size,
                            "steps": self.steps,
                            "guidance_scale": 7,
                            "strength": kwargs.get("strength"),
                            "controlnet_conditioning_scale": kwargs.get(
                                "controlnet_conditioning_scale"
                            ),
                            "padding_mask_crop": kwargs.get("padding_mask_crop"),
                            "control_guidance_end": kwargs.get("control_guidance_end"),
                            "device": self.device,
                            "precision": self.precision,
                            "elapsed_seconds": round(time.monotonic() - start, 2),
                            "models": self.revisions,
                        }
                    )
                )
                return image
            except FloatingPointError:
                if self.precision == "float32" or attempt == 1:
                    raise
                self.precision = "float32"
                self.unload()
        raise RuntimeError("Generation failed.")

    def create(self, labels, seed, report):
        color, edges, description = prepare_landscape(labels, self.size)
        result = self._run(
            "create",
            seed,
            dict(
                image=color,
                control_image=edges,
                prompt=landscape_prompt(description),
                strength=1.0,
                controlnet_conditioning_scale=0.25,
                control_guidance_end=0.6,
            ),
            report,
        )
        self.unload()  # ControlNet is never resident together with the inpainting pipeline.
        return result, description

    def transform(self, image, mask, blend, force, text, seed, report):
        generated = self._run(
            "transform",
            seed,
            dict(
                image=image,
                mask_image=mask,
                width=image.width,
                height=image.height,
                padding_mask_crop=32,
                prompt=force_prompt(force, text),
                strength=0.95,
            ),
            report,
        )
        return composite(image, generated, blend)


def selected_profile():
    path = ROOT / ".runtime" / "profile.json"
    import torch

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    default = {
        "size": 512 if device == "mps" else 384,
        "steps": 20 if device == "mps" else 15,
        "device": device,
        "verified": False,
    }
    if path.exists():
        profile = json.loads(path.read_text())
        if profile.get("device", device) == device:
            return profile
    return default
