import asyncio
import logging
from pathlib import Path

import yt_dlp

from app.config import settings

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class ExtractionError(Exception):
    pass


def _resolve_stream_url_sync(video_url: str) -> str:
    ydl_opts = {
        # Frame extraction needs a single video stream, not audio, so a video-only
        # DASH stream is ideal. Do NOT require ext=mp4: on datacenter IPs YouTube
        # often returns only webm/av01 or HLS, and a strict mp4 selector then fails
        # with "Requested format is not available". ffmpeg reads any of these.
        "format": "bestvideo[height<=1080]/bestvideo/best[height<=1080]/best",
        # Try several player clients; on flagged IPs some clients return an empty or
        # restricted format list, so falling through them recovers more formats.
        "extractor_args": {
            "youtube": {"player_client": ["default", "android_vr", "web_safari", "tv"]}
        },
        "quiet": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "user_agent": _USER_AGENT,
    }
    cookies_configured = bool(
        settings.youtube_cookies_file and settings.youtube_cookies_file.exists()
    )
    if cookies_configured:
        ydl_opts["cookiefile"] = str(settings.youtube_cookies_file)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        # With the permissive selector above, "Requested format is not available"
        # no longer means a bad selector — it means YouTube returned a response with
        # NO usable video streams (only storyboards/audio). That is what a bot-flagged
        # datacenter IP gets. Surface the real cause instead of yt-dlp's cryptic text.
        if "Requested format is not available" in str(exc):
            raise ExtractionError(
                "YouTube returned no usable video streams. The deployment IP is almost "
                "certainly bot-flagged. Fix: set YOUTUBE_COOKIES_CONTENT (or "
                "YOUTUBE_COOKIES_FILE) with fresh cookies exported from a logged-in "
                "session, then redeploy. YouTube cookies are currently "
                f"{'CONFIGURED' if cookies_configured else 'NOT configured'}."
            ) from exc
        raise

    # A single-format selection exposes "url"; a merged selection (shouldn't happen
    # with the "/"-only selector above, but guard anyway) exposes requested_formats.
    if info.get("url"):
        return info["url"]
    requested = info.get("requested_formats")
    if requested:
        return requested[0]["url"]
    raise KeyError("no playable stream URL in yt-dlp response")


async def resolve_stream_url(video_url: str) -> str:
    try:
        return await asyncio.to_thread(_resolve_stream_url_sync, video_url)
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError(f"could not resolve stream: {exc}") from exc


async def extract_frame(stream_url: str, timestamp: float, output_path: Path) -> None:
    command = [
        "ffmpeg", "-y",
        "-ss", str(timestamp),
        "-i", stream_url,
        "-vframes", "1",
        "-q:v", "2",
        str(output_path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=settings.ffmpeg_timeout_seconds
        )
    except asyncio.TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise ExtractionError(f"timed out extracting frame at {timestamp}s") from exc

    if proc.returncode != 0:
        raise ExtractionError(
            f"ffmpeg failed at {timestamp}s: {stderr.decode(errors='replace').strip()}"
        )


async def extract_frames(
    video_url: str, timestamps: list[float], job_dir: Path
) -> tuple[list[tuple[float, Path]], list[str]]:
    job_dir.mkdir(parents=True, exist_ok=True)
    stream_url = await resolve_stream_url(video_url)

    saved: list[tuple[float, Path]] = []
    errors: list[str] = []
    for ts in timestamps:
        output_path = job_dir / f"frame_{ts}s.jpg"
        try:
            await extract_frame(stream_url, ts, output_path)
            saved.append((ts, output_path))
        except ExtractionError as exc:
            logger.warning("frame extraction failed: %s", exc)
            errors.append(str(exc))

    return saved, errors
