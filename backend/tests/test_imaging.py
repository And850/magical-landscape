import io
import numpy as np
import pytest
from PIL import Image
from backend import imaging


def png(array):
    stream = io.BytesIO()
    Image.fromarray(array).save(stream, format="PNG")
    return stream.getvalue()


def test_labels_validate_and_describe_positions():
    labels = np.zeros((512, 512), dtype=np.uint8)
    labels[256:, :] = 1
    labels[256:400, 40:180] = 6
    decoded = imaging.decode_labels(png(labels))
    color, edges, description = imaging.prepare_landscape(decoded, 512)
    assert color.size == edges.size == (512, 512)
    assert "structures" in description and "left" in description
    assert "ground" in description and "lower" in description
    assert np.asarray(edges).max() == 255
    assert color.getpixel((200, 400)) != color.getpixel((200, 100))


@pytest.mark.parametrize(
    "data",
    [
        b"not png",
        png(np.full((512, 512), 8, np.uint8)),
        png(np.zeros((512, 512), np.uint8)),
        png(np.ones((64, 64), np.uint8)),
    ],
)
def test_invalid_landscapes_rejected(data):
    with pytest.raises(ValueError):
        imaging.decode_labels(data)


def test_mask_expansion_and_composite_preserves_outside():
    mask = np.zeros((512, 512), np.uint8)
    mask[200:240, 200:240] = 255
    binary, blend = imaging.prepare_mask(png(mask), 512)
    b = np.asarray(blend)
    assert b[190, 220] > 0
    assert b[187, 220] == 0
    assert b[210, 220] == 255
    old = Image.new("RGB", (512, 512), (10, 20, 30))
    new = Image.new("RGB", (512, 512), (200, 220, 240))
    result = imaging.composite(old, new, blend)
    r = np.asarray(result)
    assert np.array_equal(r[b == 0], np.asarray(old)[b == 0])
    assert result.getpixel((220, 220)) == (200, 220, 240)


def test_masks_reject_empty_and_wrong_dimensions():
    for a in [np.zeros((512, 512), np.uint8), np.ones((64, 64), np.uint8)]:
        with pytest.raises(ValueError):
            imaging.prepare_mask(png(a), 512)


def test_force_rules_are_distinct_and_text_is_optional():
    growth = imaging.force_prompt("growth_time", "ancient roots reclaim this tower")
    water = imaging.force_prompt("water", "")
    light = imaging.force_prompt("light", "")
    assert "roots" in growth and "weather" in growth
    assert "flood" in water and "vegetation" in water
    assert "glow" in light and "awaken" in light
    assert "ancient roots reclaim this tower" in growth
    with pytest.raises(ValueError):
        imaging.force_prompt("unknown", "")


def test_landscape_prompt_does_not_invent_unpainted_categories():
    labels = np.full((512, 512), 3, dtype=np.uint8)
    labels[:100, :] = 0
    labels[300:400, 40:180] = 1
    _, _, description = imaging.prepare_landscape(Image.fromarray(labels), 384)
    prompt = imaging.landscape_prompt(description)
    assert "water" in prompt and "dominates" in prompt
    assert (
        "mountains" not in prompt
        and "forest" not in prompt
        and "structures" not in prompt
    )


def test_thin_water_region_describes_its_route_instead_of_only_its_centroid():
    labels = np.ones((512, 512), dtype=np.uint8)
    labels[:40] = 0
    for y in range(50, 490):
        x = int(440 - (y - 50) * 0.4)
        labels[y, x : x + 14] = 3
    _, _, description = imaging.prepare_landscape(Image.fromarray(labels), 384)
    assert "winding river upper right to lower center" in description
    labels[:] = 3
    _, _, sea = imaging.prepare_landscape(Image.fromarray(labels), 384)
    assert "dominates" in sea and "winding river" not in sea


def test_default_time_prompt_does_not_request_new_ruins_or_structures():
    prompt = imaging.force_prompt("growth_time", "")
    assert "trees" in prompt and "vines" in prompt and "roots" in prompt
    for unwanted in ("ruins", "structures", "cave", "tower"):
        assert unwanted not in prompt
