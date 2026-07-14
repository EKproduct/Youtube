from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    rapidapi_key: str | None = None
    serpapi_key: str | None = None

    # Path to a Netscape-format cookies.txt, mounted as a secret/volume in deployment.
    youtube_cookies_file: Path | None = None

    output_root: Path = Path("/data/extracted_frames")
    max_timestamps_per_request: int = 25
    ffmpeg_timeout_seconds: int = 30

    class Config:
        env_file = ".env"


settings = Settings()
