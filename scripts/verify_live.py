"""Exercise actual localhost API + real models; no mocked or prepared inference."""

import io, json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
import numpy as np
from PIL import Image, ImageDraw
from scripts.benchmark_fixtures import layout
from backend.engine import ROOT
from backend.imaging import prepare_mask

out = ROOT / ".runtime" / "acceptance"
out.mkdir(parents=True, exist_ok=True)
client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=30)
records = []


def png(image):
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def wait(response, stage):
    response.raise_for_status()
    job = response.json()["job_id"]
    start = time.monotonic()
    last = None
    while True:
        j = client.get("/api/jobs/" + job)
        j.raise_for_status()
        j = j.json()
        progress = (j["stage"], j["step"], j["total"])
        if progress != last:
            print(stage, *progress, flush=True)
            last = progress
        if j["status"] == "failed":
            raise RuntimeError(j["error"])
        if j["status"] == "succeeded":
            w = j["result"]
            r = client.get(w["image_url"])
            r.raise_for_status()
            path = out / (stage + ".png")
            path.write_bytes(r.content)
            records.append(
                {
                    "stage": stage,
                    "seconds": round(time.monotonic() - start, 2),
                    "world": w,
                }
            )
            return w, Image.open(io.BytesIO(r.content)).convert("RGB")
        time.sleep(0.5)


print("Health", client.get("/api/health").json(), flush=True)
labels = layout(False)
labels.save(out / "labels-a.png")
w, image = wait(
    client.post(
        "/api/worlds", files={"labels": ("labels.png", png(labels), "image/png")}
    ),
    "world-a",
)
for force in ("growth_time", "water", "light"):
    size = w["size"]
    painted = Image.new("L", (size, size))
    d = ImageDraw.Draw(painted)
    d.ellipse(
        (int(0.48 * size), int(0.45 * size), int(0.95 * size), int(0.9 * size)),
        fill=255,
    )
    data = png(painted)
    _, blend = prepare_mask(data, size, force=force)
    before = image.copy()
    old = w
    w, image = wait(
        client.post(
            "/api/worlds/" + w["id"] + "/transform",
            data={"force": force, "text": "", "expected_revision": w["revision"]},
            files={"mask": ("mask.png", data, "image/png")},
        ),
        force,
    )
    outside = np.asarray(blend) == 0
    assert np.array_equal(np.asarray(image)[outside], np.asarray(before)[outside]), (
        "Unpainted pixels changed"
    )
    assert not np.array_equal(np.asarray(image), np.asarray(before)), "No visual change"
    assert client.get(old["image_url"]).status_code == 409, "Old image still served"
    assert client.get("/api/worlds/" + w["id"]).json()["revision"] == w["revision"]
labels = layout(True)
labels.save(out / "labels-b.png")
second, _ = wait(
    client.post(
        "/api/worlds", files={"labels": ("labels.png", png(labels), "image/png")}
    ),
    "world-b",
)
report = {
    "device": client.get("/api/health").json()["device"],
    "size": w["size"],
    "steps": client.get("/api/health").json()["steps"],
    "records": records,
    "world_chain": w["id"],
    "visual_review_required": True,
}
(out / "report.json").write_text(json.dumps(report, indent=2))
print("ACCEPTANCE", json.dumps(report), flush=True)
