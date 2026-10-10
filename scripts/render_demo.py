"""Render an honest, captioned sequence of genuine locally generated outputs.

Requires ffmpeg. This is a results reel, not a recording of browser interaction.
"""

import json
import shutil
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / ".runtime/acceptance"
assets = ROOT / "docs/assets"
work = ROOT / ".runtime/demo"
work.mkdir(parents=True, exist_ok=True)
assets.mkdir(parents=True, exist_ok=True)
font = "/System/Library/Fonts/Supplemental/Arial.ttf"
slides = [
    (
        "sketch",
        "Draw a cause. Discover a consequence.",
        "Seven labeled brushes establish the initial geography.",
    ),
    (
        "world-a",
        "Bring the world to life",
        "Actual local generation - 384 x 384 pixels - CPU - 87 seconds.",
    ),
    (
        "growth_time",
        "Time - selected cumulative iteration",
        "Mature vegetation reinterprets the painted region.",
    ),
    (
        "water",
        "Water - selected cumulative iteration",
        "Pools and channels reshape the selected terrain.",
    ),
    (
        "light",
        "Light - selected cumulative iteration",
        "Golden illumination awakens a structure in the selected region.",
    ),
    (
        "world-b",
        "A second, water-dominant composition",
        "Different geography produces a different world - 91 seconds.",
    ),
]
segments = []
for i, (name, title, detail) in enumerate(slides):
    if name != "sketch":
        shutil.copy2(source / f"{name}.png", assets / f"{name}.png")
    frame = Image.new("RGB", (1280, 720), "#17171c")
    artwork = Image.open(assets / f"{name}.png").convert("RGB")
    frame.paste(artwork.resize((512, 512), Image.Resampling.LANCZOS), (384, 90))
    draw = ImageDraw.Draw(frame)
    texts = [
        title,
        detail,
        "Actual local outputs / selected iterations / not a UI recording",
    ]
    for n, text in enumerate(texts):
        typeface = ImageFont.truetype(font, [30, 20, 16][n])
        width = draw.textlength(text, font=typeface)
        draw.text(
            ((1280 - width) / 2, [35, 640, 685][n]), text, font=typeface, fill="white"
        )
    framepath = work / f"{i}.png"
    frame.save(framepath)
    target = work / f"{i}.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-loop",
            "1",
            "-i",
            str(framepath),
            "-t",
            "10",
            "-r",
            "24",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(target),
        ],
        check=True,
    )
    segments.append(target)
listing = work / "concat.txt"
listing.write_text("".join(f"file '{p}'\n" for p in segments))
subprocess.run(
    [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(listing),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(assets / "demo.mp4"),
    ],
    check=True,
)
report = json.loads((source / "report.json").read_text())
summary = {k: report[k] for k in ("device", "size", "steps")}
summary["records"] = [
    {k: r[k] for k in ("stage", "seconds")} for r in report["records"]
]
summary["note"] = (
    "Selected cumulative iterations, genuine local generation. Native Metal and browser visual QA unverified."
)
(assets / "measurements.json").write_text(json.dumps(summary, indent=2) + "\n")
print(assets / "demo.mp4")
