"""Recheck tuned force prompts against a real persistent world from verify_live."""

import io, json, time, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx, numpy as np
from PIL import Image, ImageDraw
from backend.engine import ROOT
from backend.imaging import prepare_mask

out = ROOT / ".runtime/acceptance"
report = json.loads((out / "report.json").read_text())
client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=30)
for _ in range(30):
    try:
        client.get("/api/health").raise_for_status()
        break
    except httpx.ConnectError:
        time.sleep(0.5)
w = client.get("/api/worlds/" + report["world_chain"]).json()
for force in ("growth_time", "water", "light"):
    before = Image.open(io.BytesIO(client.get(w["image_url"]).content)).convert("RGB")
    size = w["size"]
    m = Image.new("L", (size, size))
    ImageDraw.Draw(m).ellipse(
        (int(0.48 * size), int(0.45 * size), int(0.95 * size), int(0.9 * size)),
        fill=255,
    )
    stream = io.BytesIO()
    m.save(stream, format="PNG")
    data = stream.getvalue()
    _, blend = prepare_mask(data, size)
    start = time.monotonic()
    r = client.post(
        "/api/worlds/" + w["id"] + "/transform",
        data={"force": force, "text": "", "expected_revision": w["revision"]},
        files={"mask": ("mask.png", data, "image/png")},
    )
    r.raise_for_status()
    job = r.json()["job_id"]
    last = None
    while True:
        j = client.get("/api/jobs/" + job).json()
        state = (j["stage"], j["step"], j["total"])
        if state != last:
            print(force, *state, flush=True)
            last = state
        if j["status"] == "failed":
            raise RuntimeError(j["error"])
        if j["status"] == "succeeded":
            break
        time.sleep(0.5)
    w = j["result"]
    raw = client.get(w["image_url"]).content
    after = Image.open(io.BytesIO(raw)).convert("RGB")
    outside = np.asarray(blend) == 0
    assert np.array_equal(np.asarray(before)[outside], np.asarray(after)[outside])
    assert not np.array_equal(np.asarray(before), np.asarray(after))
    (out / (force + ".png")).write_bytes(raw)
    replacement = {
        "stage": force,
        "seconds": round(time.monotonic() - start, 2),
        "world": w,
    }
    report["records"] = [
        replacement if x["stage"] == force else x for x in report["records"]
    ]
    (out / "report.json").write_text(json.dumps(report, indent=2))
print("EVOLUTION PASS", json.dumps(report), flush=True)
