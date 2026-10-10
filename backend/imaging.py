"""Semantic painting preparation and strictly regional image compositing."""

import io
import cv2
import numpy as np
from PIL import Image

LABELS = (
    "sky",
    "ground",
    "hills and mountains",
    "water",
    "trees and vegetation",
    "rocks",
    "structures",
)
COLORS = np.array(
    [
        (161, 187, 211),
        (121, 101, 75),
        (109, 122, 111),
        (62, 120, 150),
        (66, 103, 72),
        (133, 136, 138),
        (159, 143, 123),
    ],
    dtype=np.uint8,
)
STYLE = "dreamlike fantasy landscape, painterly illustration, magical atmosphere, coherent terrain, detailed environmental art"
RULES = {
    "growth_time": "a fantasy landscape overgrown with mature trees, dense green foliage, spreading tree roots, climbing vines and thick moss covering existing terrain, weathered surfaces, painterly illustration",
    "water": "flooded terrain, reflective blue pools, flowing water carving deep channels, partially submerged stone structures, modest vegetation along wet edges",
    "light": "brilliant golden magical light rays, bioluminescent flowers and vines glowing gold, ancient structures awakened with radiant golden symbols, luminous pathways, sparkling golden particles",
}


def read_png(data: bytes) -> Image.Image:
    if len(data) > 4 * 1024 * 1024:
        raise ValueError("Image upload is too large.")
    try:
        image = Image.open(io.BytesIO(data))
        if image.format != "PNG" or image.size not in ((512, 512), (384, 384)):
            raise ValueError("Use a 512 × 512 or 384 × 384 PNG.")
        image.load()
        return image
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Upload a valid PNG image.") from exc


def decode_labels(data: bytes) -> Image.Image:
    image = read_png(data)
    if image.size != (512, 512):
        raise ValueError("Landscape labels must be 512 × 512.")
    if image.mode in ("RGB", "RGBA"):
        arr = np.asarray(image)
        if not (
            np.array_equal(arr[:, :, 0], arr[:, :, 1])
            and np.array_equal(arr[:, :, 1], arr[:, :, 2])
        ):
            raise ValueError(
                "Landscape labels must contain integer IDs, not display colors."
            )
        image = image.getchannel("R")
    elif image.mode != "L":
        raise ValueError("Landscape labels must be grayscale integer IDs.")
    a = np.asarray(image)
    if a.max() > 6 or not np.any(a != 0):
        raise ValueError("Paint at least one landscape region using the seven brushes.")
    return image


def prepare_landscape(labels: Image.Image, size: int):
    a = np.asarray(labels.resize((size, size), Image.Resampling.NEAREST))
    color = Image.fromarray(COLORS[a])
    edge = np.zeros_like(a)
    edge[1:, :] |= (a[1:, :] != a[:-1, :]).astype(np.uint8)
    edge[:, 1:] |= (a[:, 1:] != a[:, :-1]).astype(np.uint8)
    edge = cv2.dilate(edge, np.ones((2, 2), np.uint8)) * 255
    phrases = []
    for label, name in enumerate(LABELS):
        yy, xx = np.where(a == label)
        if len(xx) < 8:
            continue
        x, y = xx.mean() / size, yy.mean() / size
        horizontal = "left" if x < 0.4 else "right" if x > 0.6 else "center"
        vertical = "upper" if y < 0.4 else "lower" if y > 0.6 else "middle"
        extent = " dominates" if len(xx) / (size * size) > 0.45 else ""
        route = None
        if label == 3:
            ry, rx = yy, xx
            spans = (np.ptp(rx), np.ptp(ry))
            axis = rx if spans[0] > spans[1] else ry
            bbox_area = (spans[0] + 1) * (spans[1] + 1)
            if (
                max(spans) > size * 0.5
                and len(rx) / bbox_area < 0.55
                and len(rx) / (size * size) < 0.2
            ):

                def position(select):
                    px, py = rx[select].mean() / size, ry[select].mean() / size
                    h = "left" if px < 0.4 else "right" if px > 0.6 else "center"
                    v = "upper" if py < 0.4 else "lower" if py > 0.6 else "middle"
                    return f"{v} {h}"

                start = position(axis <= np.quantile(axis, 0.15))
                end = position(axis >= np.quantile(axis, 0.85))
                route = f"water: winding river {start} to {end}"
        phrases.append(route or f"{name}{extent} {vertical} {horizontal}")
    return color, Image.fromarray(edge).convert("RGB"), "; ".join(phrases)


def prepare_mask(data: bytes, size: int, force: str | None = None):
    image = read_png(data)
    if image.size != (size, size):
        raise ValueError("Mask dimensions must match the current world.")
    if image.mode in ("RGB", "RGBA"):
        a = np.asarray(image)
        if not (
            np.array_equal(a[:, :, 0], a[:, :, 1])
            and np.array_equal(a[:, :, 1], a[:, :, 2])
        ):
            raise ValueError("Mask must be black and white.")
        image = image.getchannel("R")
    elif image.mode != "L":
        raise ValueError("Mask must be grayscale.")
    binary = (np.asarray(image) > 127).astype(np.uint8)
    if not binary.any():
        raise ValueError("Paint a region before applying magic.")
    expanded = cv2.dilate(
        binary, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
    )
    if force == "growth_time":
        # Give canopies space above the strokes without extending downhill.
        rise = round(size / 6)
        expanded = cv2.dilate(expanded, np.ones((rise + 1, 1), np.uint8), anchor=(0, 0))
    # Padding gives a proper inward feather even for masks touching an image edge.
    distance = cv2.distanceTransform(np.pad(expanded, 1), cv2.DIST_L2, 5)[1:-1, 1:-1]
    blend = (np.clip(distance / 8, 0, 1) * 255).astype(np.uint8)
    blend[expanded == 0] = 0
    return Image.fromarray(expanded * 255), Image.fromarray(blend)


def composite(original: Image.Image, generated: Image.Image, blend: Image.Image):
    return Image.composite(generated.convert("RGB"), original.convert("RGB"), blend)


def force_prompt(force: str, text: str):
    if force not in RULES:
        raise ValueError("Choose Time, Water, or Light.")
    if len(text) > 200:
        raise ValueError("Optional text must be 200 characters or fewer.")
    style = "" if force == "growth_time" else f"{STYLE}. "
    return f"{RULES[force]}. {style}" + (
        f"Additional detail within this effect: {text.strip()}." if text.strip() else ""
    )


def landscape_prompt(description: str):
    return f"{STYLE}, atmospheric depth, textured concept painting. {description}."
