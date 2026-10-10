"""Durable jobs and a serialized inference worker."""

import json
import logging
import secrets
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from backend.store import WorldStore, atomic_json
from backend.imaging import decode_labels, prepare_mask, force_prompt


class Conflict(Exception):
    pass


class WorldService:
    def __init__(self, root: Path, engine):
        self.store = WorldStore(root)
        self.engine = engine
        self.directory = root / "jobs"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.busy = False
        self.jobs = {}
        self.worker = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="image-generation"
        )
        for file in self.directory.glob("*.json"):
            job = json.loads(file.read_text())
            if job["status"] in ("queued", "running"):
                try:
                    meta, _ = self.store.read(job.get("world_id", ""))
                except KeyError:
                    meta = None
                if meta and meta.get("job_id") == job["id"]:
                    job.update(
                        status="succeeded",
                        stage="World ready",
                        result=self.store.public(meta),
                        error=None,
                    )
                else:
                    job.update(
                        status="failed",
                        error="Backend restarted before generation finished. Retry your request.",
                        stage="Interrupted",
                    )
                atomic_json(file, job)
            self.jobs[job["id"]] = job

    def close(self):
        self.worker.shutdown(wait=True)

    def job(self, job_id):
        with self.lock:
            if job_id not in self.jobs:
                raise KeyError("Job not found.")
            return dict(self.jobs[job_id])

    def _update(self, job_id, **changes):
        with self.lock:
            self.jobs[job_id].update(changes)
            atomic_json(self.directory / (job_id + ".json"), self.jobs[job_id])

    def _submit(self, world_id, operation):
        with self.lock:
            if self.busy:
                raise Conflict(
                    "An image is already being generated. Wait for it to finish."
                )
            job_id = str(uuid.uuid4())
            job = {
                "id": job_id,
                "world_id": world_id,
                "status": "queued",
                "stage": "Waiting for image model",
                "step": 0,
                "total": 0,
                "result": None,
                "error": None,
            }
            self.jobs[job_id] = job
            atomic_json(self.directory / (job_id + ".json"), job)
            self.busy = True

            def run():
                try:
                    self._update(job_id, status="running")

                    def report(stage, step, total):
                        self._update(job_id, stage=stage, step=step, total=total)

                    result = operation(secrets.randbelow(2**31), report, job_id)
                    try:
                        self._update(
                            job_id,
                            status="succeeded",
                            stage="World ready",
                            result=result,
                        )
                    except OSError:
                        # The world is already committed. Never misreport it as failed.
                        with self.lock:
                            self.jobs[job_id].update(
                                status="succeeded",
                                stage="World ready",
                                result=result,
                                error=None,
                            )
                        logging.getLogger("magical").exception(
                            "Success journal unavailable; committed world will reconcile at restart"
                        )
                except Exception as exc:
                    logging.getLogger("magical").exception("Generation job failed")
                    self._update(
                        job_id,
                        status="failed",
                        stage="Generation failed",
                        error=str(exc),
                    )
                finally:
                    with self.lock:
                        self.busy = False

            self.worker.submit(run)
            return {"job_id": job_id, "world_id": world_id}

    def create(self, data):
        labels = decode_labels(data)
        world_id = str(uuid.uuid4())

        def operation(seed, report, job_id):
            image, description = self.engine.create(labels, seed, report)
            report("Saving world", 1, 1)
            return self.store.commit(
                world_id, image, description, labels, job_id=job_id
            )

        return self._submit(world_id, operation)

    def transform(self, world_id, data, force, text, expected_revision):
        force_prompt(force, text)
        meta, image = self.store.read(world_id)
        if meta["revision"] != expected_revision:
            raise Conflict("The world changed. Refresh and retry.")
        mask, blend = prepare_mask(data, meta["size"], force=force)

        def operation(seed, report, job_id):
            current, current_image = self.store.read(world_id)
            if current["revision"] != expected_revision:
                raise Conflict("The world changed. Refresh and retry.")
            result = self.engine.transform(
                current_image, mask, blend, force, text, seed, report
            )
            report("Saving world", 1, 1)
            return self.store.commit(
                world_id,
                result,
                current["description"],
                expected_revision=expected_revision,
                job_id=job_id,
            )

        return self._submit(world_id, operation)
