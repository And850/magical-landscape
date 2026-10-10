"""Fetch only Diffusers inference artifacts and record immutable model revisions."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.engine import MODELS, ROOT
from huggingface_hub import HfApi, snapshot_download

manifest = {}
pinned = json.loads((ROOT / "model-revisions.json").read_text())
for name, model in MODELS.items():
    info = HfApi().model_info(model, revision=pinned[name])
    files = [x.rfilename for x in info.siblings]
    allow = [x for x in files if x.endswith((".json", ".txt")) and "onnx" not in x]
    # Load fp16 artifacts into either fp16 or fp32 compute; avoid duplicate multi-gigabyte weights.
    allow += [x for x in files if x.endswith(".fp16.safetensors")]
    print(f"Downloading {name}: {model} at {info.sha}", flush=True)
    snapshot_download(model, revision=info.sha, allow_patterns=allow, max_workers=4)
    manifest[name] = info.sha
    (ROOT / ".runtime" / "model-manifest.json").write_text(
        json.dumps(manifest, indent=2)
    )
print("All local model artifacts downloaded.", flush=True)
