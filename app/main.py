import logging
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.extractor import ExtractionError, extract_frames
from app.models import ExtractionRequest, ExtractionResponse, FrameResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="YouTube Frame Extractor API")

settings.output_root.mkdir(parents=True, exist_ok=True)
app.mount("/frames", StaticFiles(directory=settings.output_root), name="frames")

if settings.youtube_cookies_content:
    # Written outside output_root deliberately: output_root is served publicly at /frames.
    cookies_path = Path(tempfile.gettempdir()) / "youtube_cookies.txt"
    cookies_path.write_text(settings.youtube_cookies_content)
    settings.youtube_cookies_file = cookies_path
    logger.info("wrote YouTube cookies from YOUTUBE_COOKIES_CONTENT to %s", cookies_path)


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "ffmpeg": shutil.which("ffmpeg") is not None}


@app.post("/extract", response_model=ExtractionResponse)
async def extract(request: ExtractionRequest):
    if len(request.timestamps) > settings.max_timestamps_per_request:
        raise HTTPException(
            status_code=422,
            detail=f"at most {settings.max_timestamps_per_request} timestamps per request",
        )

    job_id = uuid.uuid4().hex
    job_dir = settings.output_root / job_id

    try:
        saved, errors = await extract_frames(str(request.url), request.timestamps, job_dir)
    except ExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    frames = [
        FrameResult(timestamp=ts, filename=path.name, url=f"/frames/{job_id}/{path.name}")
        for ts, path in saved
    ]

    if not frames:
        raise HTTPException(status_code=422, detail={"errors": errors} or "no frames extracted")

    return ExtractionResponse(job_id=job_id, frames=frames, errors=errors)
