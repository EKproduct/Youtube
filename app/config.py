from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    rapidapi_key: str | None = None
    serpapi_key: str | None = None

    # Path to a Netscape-format cookies.txt, mounted as a secret/volume in deployment.
    youtube_cookies_file: Path | None = None

    # Raw contents of a Netscape-format cookies.txt, for platforms (e.g. Railway) with
    # no file/volume upload — paste the file's text into this env var instead. Written
    # to disk at startup and takes precedence over youtube_cookies_file if both are set.
    youtube_cookies_content: str | None = None

    output_root: Path = Path("extracted_frames")
    max_timestamps_per_request: int = 25
    ffmpeg_timeout_seconds: int = 30

    class Config:
        env_file = ".env"


settings = Settings()
