from pathlib import Path
from typing import Literal
from urllib.parse import urlparse
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware
from . import service as svc
from .storage import *
from .media import existing_preview, decode, decode_details

app = FastAPI(title="Episode", version="0.1.0")
app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
)


@app.middleware("http")
async def boundary(request, call_next):
    if request.method not in ["GET", "HEAD", "OPTIONS"]:
        origin = request.headers.get("origin")
        if origin and urlparse(origin).netloc != request.headers.get("host"):
            return JSONResponse(
                {"detail": "Cross-origin writes are disabled"}, status_code=403
            )
    try:
        return await call_next(request)
    except (ValueError, RuntimeError, FileNotFoundError) as e:
        return JSONResponse({"detail": str(e)}, status_code=400)


@app.get("/api/health")
def health():
    return {"status": "ok", "storage_available": (ROOT / ".episode-storage").is_file()}


@app.get("/api/source")
def source():
    with connect() as db:
        r = db.execute("SELECT * FROM sources WHERE id=?", (REVISION,)).fetchone()
    return {
        "repository": REPO,
        "revision": REVISION,
        "info": json.loads(r["info"]) if r else None,
    }


@app.post("/api/selections/preview")
def selection_preview(b: dict):
    all_rows = svc.catalog()
    matching = svc.catalog(b)
    chosen = [e for e in matching if not e["errors"] and e["review"] != "excluded"]
    return {
        "selected": len(chosen),
        "excluded": len(all_rows) - len(chosen),
        "episodes": [e["id"] for e in chosen],
    }


@app.get("/api/episodes")
def catalog(
    search: str = "",
    review: str = "",
    findings: bool = False,
    min_duration: float = 0,
    max_duration: float = 1e9,
    page: int = 1,
    sort: str = "id",
):
    data = svc.catalog(
        dict(
            search=search,
            review=review,
            findings=findings,
            min_duration=min_duration,
            max_duration=max_duration,
        )
    )
    data.sort(key=lambda e: e["duration"] if sort == "duration" else e["id"])
    page = max(1, page)
    return {
        "total": len(data),
        "items": data[(page - 1) * 20 : page * 20],
        "page": page,
    }


@app.get("/api/episodes/{id}")
def episode(id: int):
    return svc.episode(id)


@app.get("/api/episodes/{id}/media/{camera}")
def media(id: int, camera: str):
    e = svc.episode(id)
    return FileResponse(
        existing_preview(svc.media_path(e["metadata"], camera)), media_type="video/webm"
    )


@app.get("/api/episodes/{id}/frame/{camera}")
def frame(id: int, camera: str, time: float = 0):
    e = svc.episode(id)
    if not 0 <= time < e["duration"]:
        raise ValueError("Time outside episode")
    _, png, timing = decode_details(
        svc.media_path(e["metadata"], camera),
        e["metadata"][f"videos/{camera}/from_timestamp"] + time,
    )
    return Response(
        png,
        media_type="image/png",
        headers={
            "X-Episode-Time": str(time),
            "X-Decoded-PTS": str(timing["decoded_pts"]),
            "X-Frame-Index": str(timing["frame_index"]),
            "X-Timing-Policy": "nearest PTS within half nominal period plus 1 ms; physical synchronization unknown",
        },
    )


class Review(BaseModel):
    status: Literal["accepted", "excluded", "unreviewed"]
    outcome: Literal["unknown", "success", "failure"] = "unknown"
    reason: str = Field(min_length=1, max_length=2000)


@app.post("/api/episodes/{id}/review")
def review(id: int, b: Review):
    svc.review(id, **b.model_dump())
    return {"status": "saved"}


class Annotation(BaseModel):
    start: float = Field(ge=0, allow_inf_nan=False)
    end: float = Field(gt=0, allow_inf_nan=False)
    label: str = Field(min_length=1, max_length=100)
    note: str = Field(max_length=2000, default="")


@app.post("/api/episodes/{id}/annotations")
def annotate(id: int, b: Annotation):
    svc.annotate(id, **b.model_dump())
    return {"status": "saved"}


class Selection(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    criteria: dict = Field(default_factory=dict)


@app.get("/api/selections")
def selections():
    with connect() as db:
        return rows(db, "SELECT * FROM selections ORDER BY id DESC")


@app.post("/api/selections")
def selection(b: Selection):
    selected = svc.catalog(b.criteria)
    with connect() as db:
        db.execute(
            "INSERT INTO selections(name,criteria,created) VALUES(?,?,?)",
            (b.name, canonical(b.criteria), now()),
        )
    return {"selected": len(selected), "excluded": len(svc.catalog()) - len(selected)}


class Version(Selection):
    seed: int = 17


@app.post("/api/versions")
def create_version(b: Version):
    return {"id": svc.create_version(b.name, b.criteria, b.seed)}


@app.get("/api/versions")
def versions():
    with connect() as db:
        return rows(db, "SELECT id,name,created FROM versions ORDER BY created DESC")


@app.get("/api/versions/{id}")
def version(id: str):
    return svc.version(id)


@app.get("/api/compare")
def compare(left: str, right: str):
    a = svc.version(left)
    b = svc.version(right)
    return {
        "added": sorted(set(b["episodes"]) - set(a["episodes"])),
        "removed": sorted(set(a["episodes"]) - set(b["episodes"])),
        "configuration_changed": [
            k
            for k in [
                "criteria",
                "split",
                "normalization",
                "rules",
                "transforms",
                "reviews",
                "annotations",
            ]
            if a[k] != b[k]
        ],
    }


class Job(BaseModel):
    kind: Literal["import", "verify"] = "import"
    limit: int = Field(default=50, ge=1, le=50)
    version: str = ""


@app.get("/api/jobs")
def jobs():
    with connect() as db:
        return rows(db, "SELECT * FROM jobs ORDER BY created DESC LIMIT 100")


@app.post("/api/jobs")
def job(b: Job):
    return {"id": svc.enqueue(b.kind, {"limit": b.limit, "version": b.version})}


@app.post("/api/jobs/{id}/cancel")
def cancel(id: str):
    with connect() as db:
        db.execute("UPDATE jobs SET cancel=1 WHERE id=?", (id,))
    return {"status": "cancellation requested"}


@app.post("/api/jobs/{id}/retry")
def retry(id: str):
    with connect() as db:
        r = db.execute("SELECT * FROM jobs WHERE id=?", (id,)).fetchone()
    if not r or r["state"] not in ["failed", "interrupted", "cancelled"]:
        raise ValueError("Only failed, interrupted or cancelled jobs can be retried")
    return {"id": svc.enqueue(r["kind"], json.loads(r["args"]))}


@app.get("/api/validation-runs")
def validation_runs():
    with connect() as db:
        return rows(db, "SELECT * FROM validation_runs ORDER BY created DESC")


@app.get("/api/verifications")
def verifications():
    with connect() as db:
        return rows(db, "SELECT * FROM verifications ORDER BY id DESC")


@app.get("/api/fixtures")
def fixtures():
    from .fixtures import demonstrations

    return demonstrations()


DIST = Path(__file__).resolve().parents[1] / "web/dist"


@app.get("/{path:path}")
def frontend(path: str):
    if path.startswith("api/"):
        raise HTTPException(404)
    p = (DIST / path).resolve()
    if not p.is_relative_to(DIST.resolve()):
        raise HTTPException(404)
    return FileResponse(p if p.is_file() else DIST / "index.html")
