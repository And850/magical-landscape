"""Local API for canvas painting and persistent image generation."""

import io
import json
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware
from backend.engine import DiffusionEngine, RUNTIME, ROOT, selected_profile
from backend.service import WorldService, Conflict


def create_app(data_dir=None, engine=None):
    root = Path(data_dir or RUNTIME)
    root.mkdir(parents=True, exist_ok=True)
    profile = selected_profile()
    injected = engine is not None
    generator = engine or DiffusionEngine(profile["size"], profile["steps"])
    service = WorldService(root, generator)

    @asynccontextmanager
    async def lifespan(app):
        yield
        service.close()

    app = FastAPI(title="Magical Landscape", lifespan=lifespan)
    app.state.service = service
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1"] + (["testserver"] if injected else []),
    )
    allowed_origins = {
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    }

    @app.middleware("http")
    async def local_origin(request, call_next):
        origin = request.headers.get("origin")
        if origin is not None and origin not in allowed_origins:
            return JSONResponse(
                status_code=403,
                content={"detail": "Only the local landscape app may access this API."},
            )
        return await call_next(request)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse(status_code=404, content={"detail": str(exc.args[0])})

    @app.exception_handler(Conflict)
    async def conflict(request, exc):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    async def contents(upload):
        data = await upload.read(4 * 1024 * 1024 + 1)
        await upload.close()
        if len(data) > 4 * 1024 * 1024:
            raise ValueError("Image upload is too large.")
        return data

    @app.get("/api/health")
    def health():
        manifest = ROOT / ".runtime" / "model-manifest.json"
        downloaded = False
        if manifest.exists():
            try:
                cached = json.loads(manifest.read_text())
                pinned = json.loads((ROOT / "model-revisions.json").read_text())
                downloaded = all(cached.get(key) == rev for key, rev in pinned.items())
            except (ValueError, OSError):
                pass
        return {
            "status": "ok",
            "models_ready": injected or downloaded,
            "busy": service.busy,
            "device": getattr(generator, "device", "mps"),
            "size": generator.size,
            "steps": generator.steps,
            "verified": profile.get("verified", False),
        }

    @app.post("/api/worlds", status_code=202)
    async def create_world(labels: UploadFile = File(...)):
        return service.create(await contents(labels))

    @app.get("/api/worlds/{world_id}")
    def get_world(world_id: str):
        meta, _ = service.store.read(world_id)
        return service.store.public(meta)

    @app.get("/api/worlds/{world_id}/image")
    def get_image(world_id: str, revision: int):
        meta, image = service.store.read(world_id)
        if revision != meta["revision"]:
            raise Conflict("This image has been replaced by a newer world.")
        stream = io.BytesIO()
        image.save(stream, format="PNG")
        return Response(
            stream.getvalue(),
            media_type="image/png",
            headers={"Cache-Control": "no-store"},
        )

    @app.post("/api/worlds/{world_id}/transform", status_code=202)
    async def transform_world(
        world_id: str,
        mask: UploadFile = File(...),
        force: str = Form(...),
        text: str = Form(""),
        expected_revision: int = Form(...),
    ):
        return service.transform(
            world_id, await contents(mask), force, text, expected_revision
        )

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str):
        return service.job(job_id)

    return app
