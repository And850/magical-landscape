"""Atomic current-world storage. The metadata pointer is the commit boundary."""

import io
import json
import os
import threading
import uuid
from pathlib import Path
from PIL import Image


def atomic_json(path: Path, data):
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)


class WorldStore:
    def __init__(self, root: Path):
        self.root = root / "worlds"
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def _directory(self, world_id):
        try:
            uuid.UUID(world_id)
        except (ValueError, AttributeError):
            raise KeyError("World not found.")
        return self.root / world_id

    def read(self, world_id):
        with self.lock:
            directory = self._directory(world_id)
            path = directory / "current.json"
            if not path.exists():
                raise KeyError("World not found.")
            meta = json.loads(path.read_text())
            image = Image.open(directory / meta["file"]).convert("RGB")
            return meta, image

    def commit(
        self,
        world_id,
        image,
        description,
        labels=None,
        expected_revision=0,
        job_id=None,
    ):
        with self.lock:
            directory = self._directory(world_id)
            directory.mkdir(exist_ok=True)
            pointer = directory / "current.json"
            old = json.loads(pointer.read_text()) if pointer.exists() else None
            revision = old["revision"] if old else 0
            if revision != expected_revision:
                raise ValueError("The world changed. Refresh and retry.")
            filename = f"image-{uuid.uuid4().hex}.png"
            temporary = directory / (filename + ".tmp")
            image.save(temporary, format="PNG")
            with temporary.open("rb") as f:
                os.fsync(f.fileno())
            os.replace(temporary, directory / filename)
            if labels is not None:
                labels.save(directory / "labels.png")
            meta = {
                "id": world_id,
                "revision": revision + 1,
                "size": image.width,
                "description": description,
                "file": filename,
                "job_id": job_id,
            }
            atomic_json(pointer, meta)
            for path in directory.glob("image-*"):
                if path.name != filename:
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        import logging

                        logging.getLogger("magical").warning(
                            "Could not remove obsolete image after commit"
                        )
            return self.public(meta)

    @staticmethod
    def public(meta):
        return {k: meta[k] for k in ("id", "revision", "size", "description")} | {
            "image_url": f"/api/worlds/{meta['id']}/image?revision={meta['revision']}"
        }
