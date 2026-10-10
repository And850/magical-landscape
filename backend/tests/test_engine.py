import pytest
from PIL import Image
from types import SimpleNamespace
from backend.engine import checked_image


def test_rejected_output_never_becomes_world():
    with pytest.raises(RuntimeError, match="rejected"):
        checked_image(
            SimpleNamespace(
                images=[Image.new("RGB", (32, 32), "red")], nsfw_content_detected=[True]
            )
        )


def test_black_precision_failure_not_accepted():
    with pytest.raises(FloatingPointError):
        checked_image(
            SimpleNamespace(
                images=[Image.new("RGB", (32, 32), "black")],
                nsfw_content_detected=[False],
            )
        )


def test_valid_output_is_rgb():
    out = checked_image(
        SimpleNamespace(
            images=[Image.new("RGBA", (32, 32), "gold")], nsfw_content_detected=[False]
        )
    )
    assert out.mode == "RGB" and out.getpixel((0, 0)) == (255, 215, 0)


def test_reduced_profile_inpainting_uses_the_world_dimensions():
    from backend.engine import DiffusionEngine

    engine = DiffusionEngine(384, 15, device="cpu")

    class Pipeline:
        def __call__(self, **kwargs):
            assert kwargs["padding_mask_crop"] == 32
            size = (kwargs.get("width", 512), kwargs.get("height", 512))
            return SimpleNamespace(
                images=[Image.new("RGB", size, "gold")], nsfw_content_detected=[False]
            )

    engine.pipe = Pipeline()
    engine.mode = "transform"
    original = Image.new("RGB", (384, 384), "green")
    mask = Image.new("L", (384, 384))
    mask.paste(255, (100, 100, 200, 200))
    result = engine.transform(original, mask, mask, "light", "", 1, lambda *_: None)
    assert result.size == (384, 384)
    assert result.getpixel((0, 0)) == (0, 128, 0)
    assert result.getpixel((150, 150)) == (255, 215, 0)


def test_generation_logs_seed_settings_and_model_revisions(tmp_path, monkeypatch):
    import json
    import logging
    import backend.engine as module

    monkeypatch.setattr(module, "RUNTIME", tmp_path)
    engine = module.DiffusionEngine(384, 15, device="cpu")
    engine.revisions = {
        "base": "test-base",
        "control": "test-control",
        "inpaint": "test-inpaint",
    }

    class Pipeline:
        def __call__(self, **kwargs):
            return SimpleNamespace(
                images=[Image.new("RGB", (384, 384), "gold")],
                nsfw_content_detected=[False],
            )

    engine.pipe = Pipeline()
    engine.mode = "transform"
    image = Image.new("RGB", (384, 384), "green")
    mask = Image.new("L", (384, 384), 255)
    engine.transform(image, mask, mask, "light", "", 8741, lambda *_: None)
    path = tmp_path / "generation.jsonl"
    assert path.exists()
    entry = json.loads(path.read_text().splitlines()[-1])
    assert entry["seed"] == 8741 and entry["size"] == 384 and entry["device"] == "cpu"
    assert entry["force"] == "light"
    assert (
        entry["steps"] == 15
        and entry["strength"] == 0.95
        and entry["models"]
        == {"base": "test-base", "control": "test-control", "inpaint": "test-inpaint"}
    )
    for handler in list(engine.log.handlers):
        if getattr(handler, "baseFilename", "") == str(path):
            handler.close()
            engine.log.removeHandler(handler)


def test_loading_deis_checkpoint_selects_our_dpm_solver(monkeypatch):
    from backend.engine import DiffusionEngine
    from diffusers import DEISMultistepScheduler, StableDiffusionInpaintPipeline

    pipe = SimpleNamespace(
        scheduler=DEISMultistepScheduler(algorithm_type="deis", solver_type="logrho"),
        safety_checker=object(),
        enable_attention_slicing=lambda *_: None,
        to=lambda *_: None,
        set_progress_bar_config=lambda **_: None,
    )
    monkeypatch.setattr(
        StableDiffusionInpaintPipeline, "from_pretrained", lambda *_, **__: pipe
    )
    engine = DiffusionEngine(384, 15, device="cpu")
    engine.load("transform", lambda *_: None)
    assert pipe.scheduler.config.algorithm_type == "dpmsolver++"
