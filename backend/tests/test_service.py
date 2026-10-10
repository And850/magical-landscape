import io
import json
import threading
import time
import pytest
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from backend.api import create_app


def upload(value=1, size=512):
    stream = io.BytesIO()
    Image.fromarray(np.full((size, size), value, np.uint8)).save(stream, format="PNG")
    return stream.getvalue()


class Generator:
    size = 512
    steps = 20

    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.release.set()
        self.fail = False

    def create(self, labels, seed, report):
        self.entered.set()
        self.release.wait(5)
        report("Generating illustration", 1, 1)
        return Image.new("RGB", (512, 512), (100, 120, 90)), "green ground"

    def transform(self, image, mask, blend, force, text, seed, report):
        self.entered.set()
        self.release.wait(5)
        if self.fail:
            raise RuntimeError("Deliberate inference failure")
        from backend.imaging import composite

        return composite(image, Image.new("RGB", image.size, (180, 190, 120)), blend)


def wait(client, job):
    for _ in range(200):
        data = client.get("/api/jobs/" + job).json()
        if data["status"] in ("succeeded", "failed"):
            return data
        time.sleep(0.01)
    raise AssertionError("Job did not finish")


def make_world(client):
    r = client.post(
        "/api/worlds", files={"labels": ("labels.png", upload(), "image/png")}
    )
    assert r.status_code == 202
    j = wait(client, r.json()["job_id"])
    assert j["status"] == "succeeded"
    return j["result"]


def test_world_commits_and_transforms_preserve_unpainted_pixels(tmp_path):
    g = Generator()
    with TestClient(create_app(tmp_path, g)) as c:
        w = make_world(c)
        assert w["revision"] == 1
        before = Image.open(io.BytesIO(c.get(w["image_url"]).content))
        mask = np.zeros((512, 512), np.uint8)
        mask[200:230, 200:230] = 255
        stream = io.BytesIO()
        Image.fromarray(mask).save(stream, format="PNG")
        r = c.post(
            f"/api/worlds/{w['id']}/transform",
            data={"force": "light", "text": "golden light", "expected_revision": 1},
            files={"mask": ("mask.png", stream.getvalue(), "image/png")},
        )
        assert r.status_code == 202
        result = wait(c, r.json()["job_id"])["result"]
        assert result["revision"] == 2
        after = Image.open(io.BytesIO(c.get(result["image_url"]).content))
        assert after.getpixel((0, 0)) == before.getpixel((0, 0))
        assert after.getpixel((215, 215)) != before.getpixel((215, 215))
        assert c.get(w["image_url"]).status_code == 409
        assert (
            c.post(
                f"/api/worlds/{w['id']}/transform",
                data={"force": "water", "expected_revision": 1},
                files={"mask": ("x.png", upload(255), "image/png")},
            ).status_code
            == 409
        )
    with TestClient(create_app(tmp_path, Generator())) as c:
        assert c.get("/api/worlds/" + w["id"]).json()["revision"] == 2


def test_failure_does_not_replace_world(tmp_path):
    g = Generator()
    with TestClient(create_app(tmp_path, g)) as c:
        w = make_world(c)
        original = c.get(w["image_url"]).content
        g.fail = True
        r = c.post(
            f"/api/worlds/{w['id']}/transform",
            data={"force": "water", "expected_revision": 1},
            files={"mask": ("mask.png", upload(255), "image/png")},
        )
        j = wait(c, r.json()["job_id"])
        assert j["status"] == "failed" and "failure" in j["error"]
        assert c.get("/api/worlds/" + w["id"]).json()["revision"] == 1
        assert c.get(w["image_url"]).content == original


def test_reject_busy_and_invalid_inputs(tmp_path):
    g = Generator()
    g.release.clear()
    with TestClient(create_app(tmp_path, g)) as c:
        first = c.post(
            "/api/worlds", files={"labels": ("a.png", upload(), "image/png")}
        )
        assert first.status_code == 202 and g.entered.wait(1)
        assert (
            c.post(
                "/api/worlds", files={"labels": ("a.png", upload(), "image/png")}
            ).status_code
            == 409
        )
        g.release.set()
        w = wait(c, first.json()["job_id"])["result"]
        for force, text, mask in [
            ("alien", "", upload(255)),
            ("water", "", upload(0)),
            ("water", "", upload(255, 384)),
            ("light", "x" * 201, upload(255)),
        ]:
            r = c.post(
                f"/api/worlds/{w['id']}/transform",
                data={"force": force, "text": text, "expected_revision": 1},
                files={"mask": ("a.png", mask, "image/png")},
            )
            assert r.status_code in (400, 422)
        assert (
            c.post(
                "/api/worlds", files={"labels": ("a.png", b"bad", "image/png")}
            ).status_code
            == 400
        )
        assert c.get("/api/worlds/not-real").status_code == 404


def test_restart_marks_unfinished_jobs_failed(tmp_path):
    (tmp_path / "jobs").mkdir()
    (tmp_path / "jobs" / "abc.json").write_text(
        json.dumps(
            {
                "id": "abc",
                "status": "running",
                "stage": "Generating",
                "step": 2,
                "total": 20,
                "result": None,
                "error": None,
            }
        )
    )
    with TestClient(create_app(tmp_path, Generator())) as c:
        j = c.get("/api/jobs/abc").json()
        assert j["status"] == "failed" and "restart" in j["error"].lower()


def test_restart_recovers_a_world_committed_before_job_success_journal(tmp_path):
    from backend.store import WorldStore
    import uuid

    world_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    store = WorldStore(tmp_path)
    store.commit(
        world_id, Image.new("RGB", (512, 512), "green"), "forest", job_id=job_id
    )
    (tmp_path / "jobs").mkdir()
    (tmp_path / "jobs" / f"{job_id}.json").write_text(
        json.dumps(
            {
                "id": job_id,
                "world_id": world_id,
                "status": "running",
                "stage": "Saving world",
                "step": 1,
                "total": 1,
                "result": None,
                "error": None,
            }
        )
    )
    with TestClient(create_app(tmp_path, Generator())) as c:
        j = c.get("/api/jobs/" + job_id).json()
        assert j["status"] == "succeeded"
        assert j["result"]["id"] == world_id and j["result"]["revision"] == 1


def test_local_api_rejects_foreign_hosts_and_origins(tmp_path):
    with TestClient(create_app(tmp_path, Generator())) as c:
        file = {"labels": ("a.png", upload(), "image/png")}
        assert (
            c.post(
                "/api/worlds", files=file, headers={"Origin": "https://evil.example"}
            ).status_code
            == 403
        )
        assert (
            c.post(
                "/api/worlds", files=file, headers={"Host": "evil.example"}
            ).status_code
            == 400
        )
        assert (
            c.post("/api/worlds", files=file, headers={"Origin": "null"}).status_code
            == 403
        )
        accepted = c.post(
            "/api/worlds", files=file, headers={"Origin": "http://127.0.0.1:5173"}
        )
        assert accepted.status_code == 202
        assert wait(c, accepted.json()["job_id"])["status"] == "succeeded"


def test_success_journal_failure_does_not_report_committed_world_failed(
    tmp_path, monkeypatch
):
    app = create_app(tmp_path, Generator())
    service = app.state.service
    original = service._update

    def update(job_id, **changes):
        if changes.get("status") == "succeeded":
            raise OSError("Journal disk failure")
        return original(job_id, **changes)

    monkeypatch.setattr(service, "_update", update)
    with TestClient(app) as c:
        w = make_world(c)
        assert c.get("/api/worlds/" + w["id"]).json()["revision"] == 1


def test_health_requires_current_model_revisions(tmp_path, monkeypatch):
    import backend.api as api

    monkeypatch.setattr(api, "ROOT", tmp_path)
    runtime = tmp_path / ".runtime"
    runtime.mkdir()
    pins = {"base": "base-v1", "control": "control-v1", "inpaint": "new-inpaint"}
    (tmp_path / "model-revisions.json").write_text(json.dumps(pins))
    manifest = runtime / "model-manifest.json"
    manifest.write_text(json.dumps(pins | {"inpaint": "old-inpaint"}))
    with TestClient(
        api.create_app(tmp_path / "data"), base_url="http://127.0.0.1"
    ) as c:
        assert c.get("/api/health").json()["models_ready"] is False
        manifest.write_text(json.dumps(pins))
        assert c.get("/api/health").json()["models_ready"] is True
